"""InspectorAgent v4：程序硬查 + LLM-as-critic 4 维 rubric 评分 + quality_score 回填。

spec v4 路线 A：critic 内嵌 inspector，单次 LLM 调用同时输出 rubric 评分 + 关联 issues。
"""
import hashlib
import json
import logging

from pydantic import ValidationError

from src.agents.prompts.inspector import CRITIC_SYSTEM, CRITIC_PROMPT_VERSION
from src.agents.quality_score import _DIMENSION_WEIGHTS as _SEVERITY_WEIGHTS, calc_critic_score
from src.schemas.feedback import CriticScores, FeedbackIssue, RejectionFeedback
from src.schemas.report import BaseReport

logger = logging.getLogger(__name__)


# [#11 常量分叉] _SEVERITY_WEIGHTS 复用 quality_score._DIMENSION_WEIGHTS，避免两份相同常量分叉
# （调权重时漏改一处会导致 severity 判定与 quality_score 静默不一致）


def _score_to_severity(dim_score: int, all_scores: dict) -> str:
    """spec v3 cycle2/M2 + v4 cycle3/M1 — D' 阈值规则。

    规则（按优先级）：
      1. dim_score == 1 → critical（单维度灾难）
      2. dim_score == 2 → major（维度不及格）
      3. dim_score >= 4 → minor（v4/M1：显式处理防 fall-through）
      4. dim_score == 3 → 看聚合分：< 0.50 major / 否则 minor
    """
    if dim_score <= 1:
        return "critical"
    if dim_score == 2:
        return "major"
    if dim_score >= 4:
        return "minor"
    # dim_score == 3：纯内联计算，不依赖 quality_score.py（S2 消除循环依赖）
    weighted_raw = sum(w * all_scores.get(d, 0) for d, w in _SEVERITY_WEIGHTS.items())
    if (weighted_raw - 1) / 3 < 0.50:
        return "major"
    return "minor"


# ============ Critic 子函数（spec v4） ============

_ISSUE_TYPE_TO_AGENT = {
    # evidence 类（全部打回 writer：编造 URL / 引用错误都是 writer 的问题）
    "url_not_discovered": "writer",
    "source_mismatch": "writer",
    "source_irrelevant": "writer",
    # 写作质量
    "vague_description": "writer",
    "cross_field_contradiction": "writer",
    "vague_recommendation": "writer",
    # critic_failed 特殊路由（spec v4 cycle3/C5）
    "critic_failed": "end",
}


def _map_issue_type_to_agent(issue_type: str | None) -> str:
    """spec v3 cycle2/m6 + v4 cycle3/M11 — issue_type → agent 映射。"""
    if issue_type is None:
        return "writer"
    return _ISSUE_TYPE_TO_AGENT.get(issue_type, "writer")


def _safe_minimal_fallback() -> tuple[None, list[FeedbackIssue]]:
    """spec v4 cycle3/C4 — 二次兜底协议（fallback 自身失败时的"绝对安全"返回）。"""
    safe_issue = FeedbackIssue(
        agent="end",
        field="critic_check",
        severity="critical",
        reason="critic 评分系统失败（最终兜底）",
        suggestion="人工 review 或排查 inspector 日志",
        dimension="critic_failed",
        issue_type="critic_failed",
    )
    return None, [safe_issue]


def _sample_items_deterministic(
    items: list[dict],
    n: int = 5,
    seed_field: str = "id",
) -> list[dict]:
    """spec v3 cycle2/M7 + v4 cycle3/M7 — deterministic 抽样。"""
    if len(items) <= n:
        return list(items)

    def _key(item):
        if seed_field in item and item[seed_field] is not None:
            return ("a", str(item[seed_field]))
        canonical = json.dumps(item, sort_keys=True, ensure_ascii=False)
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return ("b", digest)

    sorted_items = sorted(items, key=_key)
    return sorted_items[:n]


def _build_limited_pairs(report: BaseReport) -> list[dict]:
    """构造 coherence 对照 pairs：3 个通用 + 场景特有。

    通用 pairs（5 场景共享）：
      Pair 1: SWOT strengths vs vendor cautions（仅 S1 有 vendor_profiles）
      Pair 2: key_findings vs recommendations
      Pair 3: executive_summary.implications vs recommendations

    场景特有 pairs：
      S2: market_sizing vs entry_strategy（规模判断 vs 进入方式应自洽）
      S3: packaging vs recommendations_summary（套餐设计 vs ARR 预期应自洽）
      S4: threats vs monitoring_actions（高危威胁 vs 行动优先级应对齐）
      S5: perceptual_map (is_self) vs positioning_statement（定位坐标 vs 定位陈述应一致）
    """
    pairs: list[dict] = []
    payload = report.scenario_payload

    # === 通用 Pair 1: SWOT strengths vs vendor cautions ===
    swot_strengths = list(report.swot.strengths) if report.swot else []
    vendor_cautions: list = []
    if payload and hasattr(payload, "vendor_profiles"):
        for vp in payload.vendor_profiles:
            if hasattr(vp, "cautions"):
                for c in vp.cautions:
                    vendor_cautions.append({"vendor": vp.competitor_name, "caution": c.point})

    if swot_strengths and vendor_cautions:
        pairs.append({
            "id": "swot_vs_vendor_cautions",
            "data_a": {"swot.strengths": [s.point for s in swot_strengths]},
            "data_b": {"vendor_profiles[*].cautions": vendor_cautions},
        })
    else:
        pairs.append({
            "id": "swot_vs_vendor_cautions",
            "data_a": None, "data_b": None, "skip_reason": "missing",
        })

    # === 通用 Pair 2: key_findings vs recommendations ===
    findings = list(report.key_findings)
    recs = list(report.recommendations)
    if findings and recs:
        pairs.append({
            "id": "findings_vs_recommendations",
            "data_a": {"key_findings": [f.statement for f in findings]},
            "data_b": {"recommendations": [r.action for r in recs]},
        })
    else:
        pairs.append({
            "id": "findings_vs_recommendations",
            "data_a": None, "data_b": None, "skip_reason": "missing",
        })

    # === 通用 Pair 3: executive_summary.implications vs recommendations ===
    impl = report.executive_summary.implications if report.executive_summary else None
    if impl and recs:
        pairs.append({
            "id": "exec_summary_vs_recommendations",
            "data_a": {"executive_summary.implications": impl},
            "data_b": {"recommendations": [r.action for r in recs]},
        })
    else:
        pairs.append({
            "id": "exec_summary_vs_recommendations",
            "data_a": None, "data_b": None, "skip_reason": "missing",
        })

    # === 场景特有 Pair ===
    if payload is None:
        return pairs

    scenario = getattr(payload, "scenario_type", None)

    if scenario == "S2" and hasattr(payload, "market_sizing") and hasattr(payload, "entry_strategy"):
        ms = payload.market_sizing
        es = payload.entry_strategy
        ms_summary = {
            "TAM": ms.tam.amount if ms.tam else None,
            "SAM": ms.sam.amount if ms.sam else None,
            "SOM": ms.som.amount if ms.som else None,
            "TAM_basis": ms.tam.value_basis if ms.tam else None,
        }
        es_summary = {
            "recommended_mode": es.recommended_mode,
            "target_segments": es.target_segments,
            "initial_positioning": es.initial_positioning,
        }
        if any(v for v in ms_summary.values()) and any(v for v in es_summary.values()):
            pairs.append({
                "id": "s2_market_sizing_vs_entry_strategy",
                "data_a": {"market_sizing": ms_summary},
                "data_b": {"entry_strategy": es_summary},
            })

    elif scenario == "S3" and hasattr(payload, "packaging") and hasattr(payload, "recommendations_summary"):
        pkg = payload.packaging
        rec_sum = payload.recommendations_summary
        pkg_summary = {
            "tiers": [{"name": t.name, "position": t.position, "monthly_price": t.monthly_price} for t in pkg.tiers],
            "default_billing_cycle": pkg.default_billing_cycle,
        }
        rec_sum_summary = {
            "expected_arr_uplift_pct": rec_sum.expected_arr_uplift_pct,
            "expected_arr_uplift_basis": rec_sum.expected_arr_uplift_basis,
            "recommended_packaging_summary": rec_sum.recommended_packaging_summary[:200],
        }
        if pkg.tiers and rec_sum.recommended_packaging_summary:
            pairs.append({
                "id": "s3_packaging_vs_recommendations_summary",
                "data_a": {"packaging": pkg_summary},
                "data_b": {"recommendations_summary": rec_sum_summary},
            })

    elif scenario == "S4" and hasattr(payload, "threats") and hasattr(payload, "monitoring_actions"):
        threats = payload.threats
        actions = payload.monitoring_actions
        if threats and actions:
            pairs.append({
                "id": "s4_threats_vs_monitoring_actions",
                "data_a": {"threats": [
                    {"title": t.title, "severity": t.severity, "likelihood": t.likelihood}
                    for t in threats
                ]},
                "data_b": {"monitoring_actions": [
                    {"description": a.description[:100], "priority_tier": a.priority_tier, "owner_team": a.owner_team}
                    for a in actions
                ]},
            })

    elif scenario == "S5" and hasattr(payload, "perceptual_map") and hasattr(payload, "positioning_statement"):
        pm = payload.perceptual_map
        ps = payload.positioning_statement
        if pm and hasattr(pm, "plotted_brands") and ps:
            self_brand = [b for b in pm.plotted_brands if b.is_self]
            self_info = {}
            if self_brand:
                sb = self_brand[0]
                self_info = {
                    "competitor_name": sb.competitor_name,
                    "axis_x": sb.x_score,
                    "axis_y": sb.y_score,
                }
            ps_info = {
                "target_customer": ps.target_customer,
                "key_benefit": ps.key_benefit,
                "primary_differentiation": ps.primary_differentiation,
            }
            if self_info and any(ps_info.values()):
                pairs.append({
                    "id": "s5_perceptual_map_vs_positioning",
                    "data_a": {"perceptual_map_self": self_info},
                    "data_b": {"positioning_statement": ps_info},
                })

    return pairs


def _build_critic_inputs(
    report: BaseReport,
    discovered_sources: list[dict],
) -> str:
    """拼装 critic LLM user_prompt。

    包含完整 report_brief（含 scenario_payload）+ discovered_sources +
    limited_pairs + 全量 findings/narratives/recommendations。
    """
    report_dict = report.model_dump()

    # 仅裁剪 appendix（纯术语表/附加展览，critic 不需要）和过长 methodology
    report_dict.pop("appendix", None)
    methodology = report_dict.get("methodology", {})
    for k in ("data_collection_approach", "sample_size_note"):
        v = methodology.get(k, "")
        if len(v) > 500:
            methodology[k] = v[:500] + "...[truncated]"

    sections = report_dict.get("analysis_sections", [])
    for s in sections:
        nar = s.get("narrative", "")
        if len(nar) > 2000:
            s["narrative"] = nar[:2000] + "...[truncated]"

    # 全量传递，消除抽样偏差
    findings = report_dict.get("key_findings", [])
    narratives = [{"section_id": s.get("section_id", ""), "narrative": s.get("narrative", "")}
                  for s in sections]
    recs = report_dict.get("recommendations", [])

    pairs = _build_limited_pairs(report)

    inputs = {
        "report_brief": report_dict,
        "discovered_sources": discovered_sources,
        "limited_pairs": pairs,
        "all_findings": findings,
        "all_narratives": narratives,
        "all_recommendations": recs,
    }
    if not discovered_sources:
        inputs["__warning__"] = (
            "discovered_sources 为空。evidence 维度仅能基于 URL 字段判断，"
            "不要要求严格相关性。"
        )

    return json.dumps(inputs, ensure_ascii=False, default=str)


# ============ 通用硬查 ============

def _check_common(report: BaseReport) -> list[FeedbackIssue]:
    """跨场景通用硬查（Pydantic 已拦截结构性问题，本函数补语义级）"""
    issues: list[FeedbackIssue] = []

    # analysis_sections section_id 唯一性
    sec_ids = [s.section_id for s in report.analysis_sections]
    dup_ids = {sid for sid in sec_ids if sec_ids.count(sid) > 1}
    if dup_ids:
        issues.append(FeedbackIssue(
            agent="writer", field="analysis_sections.section_id",
            severity="major",
            reason=f"section_id 有重复: {sorted(dup_ids)}",
            suggestion="确保每个 section_id 唯一",
        ))

    # at_a_glance 占位检测：单条少于 8 字 或全 N/A
    placeholder_glance = [g for g in report.at_a_glance if len(g) < 8 or g.strip() in {"N/A", "无", "..."}]
    if placeholder_glance:
        issues.append(FeedbackIssue(
            agent="writer", field="at_a_glance",
            severity="minor",
            reason=f"at_a_glance 含 {len(placeholder_glance)} 条占位/过短",
            suggestion="每条至少 8 字、提供具体洞察",
        ))

    # recommendations 全 critical 不合理（应有梯度）
    if report.recommendations:
        priorities = [r.priority for r in report.recommendations]
        if len(set(priorities)) == 1 and priorities[0] == "critical" and len(priorities) >= 3:
            issues.append(FeedbackIssue(
                agent="writer", field="recommendations.priority",
                severity="minor",
                reason=f"全部 {len(priorities)} 条 recommendations 都标 critical，缺乏优先级区分",
                suggestion="区分 critical/important/consider，至少有 1 条非 critical",
            ))

    # data_sources 数量过少（<3）
    if len(report.metadata.data_sources) < 3:
        issues.append(FeedbackIssue(
            agent="collector", field="metadata.data_sources",
            severity="major",
            reason=f"data_sources 仅 {len(report.metadata.data_sources)} 条，溯源不足",
            suggestion="至少采集 3 个不同来源",
        ))

    return issues


# ============ S1-S5 各场景硬查 ============

def _check_s1(payload) -> list[FeedbackIssue]:
    """S1 功能迭代：vendor 缺竞品 / 全 0 评分 / feature_gaps 占位"""
    issues: list[FeedbackIssue] = []

    # vendor_profiles 必须覆盖所有"竞品"（feature_matrix.competitors 含我方，需排除）
    matrix_competitors = set(payload.feature_matrix.competitors)
    our_name = payload.feature_matrix.our_product_name
    expected_vendor_names = matrix_competitors - {our_name}
    vendor_names = {vp.competitor_name for vp in payload.vendor_profiles}
    missing = expected_vendor_names - vendor_names
    if missing:
        issues.append(FeedbackIssue(
            agent="writer", field="scenario_payload.vendor_profiles",
            severity="major",
            reason=f"vendor_profiles 缺少 {sorted(missing)} 的画像（已采集竞品 {len(vendor_names)} 个，期望 {len(expected_vendor_names)} 个）",
            suggestion="为 feature_matrix.competitors 中每个非我方竞品都提供 vendor_profile",
        ))

    # feature_matrix 全 score=0
    all_zero = True
    for cat in payload.feature_matrix.categories:
        for f in cat.features:
            for fs in f.scores.values():
                if fs.score != 0:
                    all_zero = False
                    break
    if all_zero:
        issues.append(FeedbackIssue(
            agent="analyzer", field="scenario_payload.feature_matrix",
            severity="critical",
            reason="feature_matrix 所有评分均为 0，分析失效",
            suggestion="检查采集数据或重新评估",
        ))

    # white_space_features 与 feature_gaps 都空（功能迭代核心产出缺失）
    # 防御性兜底：feature_gaps 已被 schema min_length=1 强制 ≥1，正常路径此条件恒 False；
    # 保留以拦截绕过 schema 的异常输入（如 trace 回放/SimpleNamespace 测试场景）。
    if not payload.white_space_features and not payload.feature_gaps:
        issues.append(FeedbackIssue(
            agent="analyzer", field="scenario_payload.feature_gaps",
            severity="major",
            reason="white_space_features 和 feature_gaps 都为空，无功能迭代建议",
            suggestion="至少识别 1 条 feature gap 或 white space",
        ))

    return issues


def _check_s2(payload) -> list[FeedbackIssue]:
    """S2 市场进入：market_sizing 全 unknown / players 仅 incumbent / consumer_segments 缺失"""
    issues: list[FeedbackIssue] = []

    # market_sizing TAM/SAM/SOM 全 value_basis=unknown 或 amount=None（无可信数据）
    ms = payload.market_sizing
    unknown_count = sum(
        1 for v in [ms.tam, ms.sam, ms.som]
        if v.value_basis == "unknown" or v.amount is None
    )
    if unknown_count == 3:
        issues.append(FeedbackIssue(
            agent="analyzer", field="scenario_payload.market_sizing",
            severity="critical",
            reason="TAM/SAM/SOM 全部为 unknown 或 amount=None，市场规模无支撑",
            suggestion="至少一项需有具体数值 + measured/estimated 口径",
        ))

    # players 多样性：全是 incumbent 或单一 role
    roles = {p.market_role for p in payload.players}
    if len(roles) == 1:
        issues.append(FeedbackIssue(
            agent="analyzer", field="scenario_payload.players",
            severity="major",
            reason=f"players 全部是 {list(roles)[0]} 单一 role，市场层级判断不足",
            suggestion="至少覆盖 incumbent + challenger 两类",
        ))

    # is_recommended 与 is_collected 都全 False（recommender 无产出）
    if payload.players and not any(p.is_recommended or p.is_collected for p in payload.players):
        issues.append(FeedbackIssue(
            agent="writer", field="scenario_payload.players",
            severity="major",
            reason="players 全部 is_recommended=False 且 is_collected=False，scope 来源不明",
            suggestion="至少标记一个 is_recommended 或 is_collected",
        ))

    return issues


def _check_s3(payload) -> list[FeedbackIssue]:
    """S3 定价策略：packaging tier 数 / wtp_research 缺失 / arr_uplift 兜底 llm_inferred"""
    issues: list[FeedbackIssue] = []

    # packaging tiers 数量 < 3（GBB 三层套餐法的最低）
    tier_n = len(payload.packaging.tiers)
    if tier_n < 3:
        issues.append(FeedbackIssue(
            agent="writer", field="scenario_payload.packaging.tiers",
            severity="minor",
            reason=f"packaging 仅 {tier_n} 个 tier，未达 GBB 三层推荐",
            suggestion="补充至 3 层（good/better/best）",
        ))

    # wtp_research 缺失（信号：定价无支付意愿研究支撑）
    if payload.wtp_research is None:
        issues.append(FeedbackIssue(
            agent="analyzer", field="scenario_payload.wtp_research",
            severity="minor",
            reason="wtp_research 缺失，定价缺乏支付意愿研究支撑",
            suggestion="补充任一方法的 WTP 研究或注明限制",
        ))

    # arr_uplift basis=llm_inferred（提示采集层无更强证据）
    if payload.recommendations_summary.expected_arr_uplift_basis == "llm_inferred":
        issues.append(FeedbackIssue(
            agent="collector", field="scenario_payload.recommendations_summary.expected_arr_uplift_basis",
            severity="minor",
            reason="arr_uplift_basis=llm_inferred，无 measured/competitor_benchmark 支撑",
            suggestion="若可能，采集行业基准或 pilot 数据替代 llm_inferred",
        ))

    # competitive_pricing_matrix 数量校验已被 schema min_length=2 覆盖（死代码已移除）

    return issues


def _check_s4(payload) -> list[FeedbackIssue]:
    """S4 持续监控：5 类 changes 全空 / threats opportunities 全空 / battlecard completeness=empty"""
    issues: list[FeedbackIssue] = []

    # 5 类 changes 全空（监控价值缺失，除非首次监控）
    is_first_review = payload.review_period.prior_trace_id is None
    total_changes = (
        len(payload.feature_changes) + len(payload.pricing_changes)
        + len(payload.messaging_changes) + len(payload.news_events)
        + len(payload.org_changes)
    )
    if total_changes == 0 and not is_first_review:
        issues.append(FeedbackIssue(
            agent="collector", field="scenario_payload.feature_changes",
            severity="major",
            reason="5 类 changes 全部为空（且非首次监控），无变更检出",
            suggestion="检查采集是否覆盖目标周期，或确认无变更需注明",
        ))

    # threats + opportunities 全空（监控产出缺失）
    if not payload.threats and not payload.opportunities:
        issues.append(FeedbackIssue(
            agent="analyzer", field="scenario_payload.threats",
            severity="major",
            reason="threats 和 opportunities 都为空，监控无可执行洞察",
            suggestion="至少识别 1 条威胁或机会",
        ))

    # battlecards 全部 overall_completeness=empty
    if all(bc.overall_completeness == "empty" for bc in payload.battlecards):
        issues.append(FeedbackIssue(
            agent="writer", field="scenario_payload.battlecards",
            severity="major",
            reason="所有 battlecard 都 completeness=empty，活体战卡未填实",
            suggestion="至少为主竞品填到 partial",
        ))

    return issues


def _check_s5(payload) -> list[FeedbackIssue]:
    """S5 战略定位：perceptual_map 缺自己 / blue_ocean 缺失 / category 与 competitors 不一致"""
    issues: list[FeedbackIssue] = []

    # perceptual_map 不含 is_self（我方未定位）
    has_self = any(b.is_self for b in payload.perceptual_map.plotted_brands)
    if not has_self:
        issues.append(FeedbackIssue(
            agent="writer", field="scenario_payload.perceptual_map.plotted_brands",
            severity="major",
            reason="perceptual_map 未标记我方品牌（is_self=True 缺失）",
            suggestion="至少一个 plotted_brand 必须 is_self=True",
        ))

    # blue_ocean_move 缺失（蓝海战略核心产出）
    if payload.blue_ocean_move is None:
        issues.append(FeedbackIssue(
            agent="analyzer", field="scenario_payload.blue_ocean_move",
            severity="minor",
            reason="blue_ocean_move 缺失，未基于 ERRC 推导新价值曲线",
            suggestion="基于 errc_grid 派生 blue_ocean_move",
        ))

    # positioning_statement.confidence=low_confidence（信号：定位语句缺乏依据）
    if payload.positioning_statement.confidence == "low_confidence":
        issues.append(FeedbackIssue(
            agent="writer", field="scenario_payload.positioning_statement",
            severity="minor",
            reason="positioning_statement.confidence=low_confidence，定位陈述弱",
            suggestion="补充 user_brief 输入或加强差异化论据",
        ))

    return issues


# ============ Dispatcher ============

def _dispatch_scenario_check(report: BaseReport) -> list[FeedbackIssue]:
    """按 report.scenario 路由到对应 _check_sX。

    通过 globals() 间接查找，便于测试用 monkeypatch 替换单个 _check_sX。
    """
    scenario = report.scenario
    fn = globals().get(f"_check_{scenario.lower()}")
    if fn is None:
        logger.warning("[inspector] 未知 scenario=%s, 跳过场景硬查", scenario)
        return []
    return fn(report.scenario_payload)


# ============ InspectorAgent v4 ============

class InspectorAgent:
    """质检 Agent v4：程序硬查 + LLM-as-critic 4 维 rubric + quality_score 回填"""

    def __init__(self, llm):
        self.llm = llm

    def _programmatic_checks(self, report: BaseReport) -> list[FeedbackIssue]:
        """通用硬查 + 场景硬查"""
        return _check_common(report) + _dispatch_scenario_check(report)

    # ---- critic 子流程 ----

    async def _critic_check(
        self,
        report: BaseReport,
        discovered_sources: list[dict],
    ) -> tuple[CriticScores | None, list[FeedbackIssue]]:
        """spec v4 — critic 内嵌主流程。外层 broad except 兜底。"""
        try:
            return await self._critic_check_inner(report, discovered_sources)
        except Exception as critic_err:
            logger.error("[critic] LLM 调用最外层异常 → 二次兜底: %s", critic_err)
            try:
                return self._build_fallback_result(error_code="unexpected_error")
            except Exception as fallback_err:
                logger.error("[critic] 二次兜底也失败 → _safe_minimal_fallback: %s", fallback_err)
                return _safe_minimal_fallback()

    async def _critic_check_inner(
        self,
        report: BaseReport,
        discovered_sources: list[dict],
    ) -> tuple[CriticScores | None, list[FeedbackIssue]]:
        """正常 LLM 调用 + retry 逻辑。"""
        user_prompt = _build_critic_inputs(report, discovered_sources)

        max_retries = 1
        last_error_code = None

        for attempt in range(max_retries + 1):
            try:
                raw = await self.llm.call_json(
                    CRITIC_SYSTEM, user_prompt, max_tokens=8192,
                )
                critic_scores = self._parse_critic_response(raw)
                critic_issues = self._extract_critic_issues(raw, critic_scores)
                logger.info(
                    "[critic] 评分通过 ev=%d sp=%d co=%d ac=%d",
                    critic_scores.evidence, critic_scores.specificity,
                    critic_scores.coherence, critic_scores.actionability,
                )
                return critic_scores, critic_issues

            except (ValidationError, ValueError, KeyError) as e:
                last_error_code = self._classify_error(e)
                logger.warning("[critic] attempt %d/%d 失败：%s", attempt + 1, max_retries + 1, e)

        return self._build_fallback_result(error_code=last_error_code or "unknown")

    def _parse_critic_response(self, raw: dict) -> CriticScores:
        """从 LLM 响应构造 CriticScores。"""
        scores_kwargs = {}
        reasoning = {}
        for dim in ("evidence", "specificity", "coherence", "actionability"):
            if dim not in raw:
                raise KeyError(f"缺 {dim} 维度对象")
            dim_data = raw[dim]
            if "score" not in dim_data:
                raise KeyError(f"{dim}.score 缺失")
            scores_kwargs[dim] = dim_data["score"]
            reasoning[dim] = dim_data.get("reasoning", []) or []

        return CriticScores(**scores_kwargs, reasoning=reasoning)

    def _extract_critic_issues(
        self,
        raw: dict,
        critic_scores: CriticScores,
    ) -> list[FeedbackIssue]:
        """从 LLM 响应提取 issues + 用 _score_to_severity 计算 severity。"""
        all_scores = {
            "evidence": critic_scores.evidence,
            "specificity": critic_scores.specificity,
            "coherence": critic_scores.coherence,
            "actionability": critic_scores.actionability,
        }
        issues: list[FeedbackIssue] = []
        for dim in ("evidence", "specificity", "coherence", "actionability"):
            dim_data = raw.get(dim, {})
            for raw_issue in dim_data.get("issues", []):
                try:
                    issue_type = raw_issue.get("issue_type")
                    issue = FeedbackIssue(
                        agent=_map_issue_type_to_agent(issue_type),
                        field=raw_issue.get("field", "<unknown>"),
                        severity=_score_to_severity(all_scores[dim], all_scores),
                        reason=raw_issue.get("reason", ""),
                        suggestion=raw_issue.get("suggestion", ""),
                        dimension=dim,
                        issue_type=issue_type,
                    )
                    issues.append(issue)
                except (ValidationError, KeyError) as e:
                    logger.warning("[critic] issue 构造失败跳过：%s, raw=%s", e, raw_issue)
        return issues

    def _classify_error(self, e: Exception) -> str:
        msg = str(e).lower()
        if "json" in msg or isinstance(e, ValueError):
            return "json_parse_error"
        if "score" in msg and ("range" in msg or "le" in msg or "ge" in msg):
            return "score_out_of_range"
        if isinstance(e, KeyError):
            return "field_missing"
        return "unexpected_error"

    def _build_fallback_result(
        self,
        error_code: str,
    ) -> tuple[None, list[FeedbackIssue]]:
        """spec v4 cycle2/C3 + cycle3/C5 — 失败降级。"""
        fallback_issue = FeedbackIssue(
            agent="end",
            field="critic_check",
            severity="critical",
            reason=f"critic 系统故障：{error_code}（非报告内容问题）",
            suggestion="检查 critic LLM 配置 / 重新跑整个分析；不要让 writer 重写",
            dimension="critic_failed",
            issue_type="critic_failed",
        )
        return None, [fallback_issue]

    # ---- 主入口 ----

    async def inspect(
        self,
        report: BaseReport,
        competitors: list[str] | None = None,
        retry_count: int = 0,
        max_retries: int = 2,
        discovered_sources: list[dict] | None = None,
    ) -> RejectionFeedback:
        """执行质检 + 回填 quality_score。spec v4 重写。"""
        logger.info("[inspector] 开始质检 v4, scenario=%s, retry=%d", report.scenario, retry_count)
        _ = competitors
        discovered_sources = discovered_sources or []

        # Step 1: 程序硬查
        prog_issues = self._programmatic_checks(report)

        # Step 2: critic 评分
        critic_scores, critic_issues = await self._critic_check(report, discovered_sources)

        # Step 3: 合并 + 去重
        all_issues = prog_issues + critic_issues
        seen: dict[tuple[str, str, str | None], FeedbackIssue] = {}
        sev_rank = {"critical": 0, "major": 1, "minor": 2}
        for issue in sorted(all_issues, key=lambda i: sev_rank[i.severity]):
            key = (issue.agent, issue.field, issue.dimension)
            if key not in seen:
                seen[key] = issue
        unique_issues = list(seen.values())

        # Step 4: quality_score 计算
        if critic_scores is not None:
            quality_score = calc_critic_score(critic_scores)
            score_source = "critic"
            report.metadata.critic_scores = critic_scores
            report.metadata.critic_prompt_version = CRITIC_PROMPT_VERSION
        else:
            quality_score = 0.5
            score_source = "fallback"
            report.metadata.critic_scores = None
            report.metadata.critic_prompt_version = None
            existing_warnings = list(report.metadata.warnings or [])
            error_code = "unknown"
            for i in critic_issues:
                if i.issue_type == "critic_failed":
                    if "：" in i.reason:
                        error_code = i.reason.split("：")[1].split("（")[0].strip()
                    break
            existing_warnings.append(f"critic_failed:{error_code}")
            report.metadata.warnings = existing_warnings

        report.metadata.quality_score = max(0.0, min(1.0, quality_score))
        report.metadata.raw_quality_score = report.metadata.quality_score  # v4 无 cap，raw == final
        report.metadata.score_source = score_source

        prog_critical = sum(1 for i in prog_issues if i.severity == "critical")
        prog_major = sum(1 for i in prog_issues if i.severity == "major")

        if critic_scores is not None:
            cs = critic_scores
            report.metadata.quality_score_calculation_note = (
                f"{CRITIC_PROMPT_VERSION} | "
                f"ev={cs.evidence} sp={cs.specificity} co={cs.coherence} ac={cs.actionability} "
                f"→ norm={quality_score:.3f} | "
                f"prog_issues={prog_critical} critical / {prog_major} major"
            )
        else:
            report.metadata.quality_score_calculation_note = (
                f"fallback | quality_score=0.5 | "
                f"prog_issues={prog_critical} critical / {prog_major} major"
            )

        # Step 5: passed 判定
        passed = not any(
            issue.severity in {"critical", "major"} for issue in unique_issues
        )

        feedback = RejectionFeedback(
            passed=passed,
            issues=unique_issues,
            retry_count=retry_count,
            max_retries=max_retries,
        )
        logger.info(
            "[inspector] 质检完成 v4, passed=%s, issues=%d (prog=%d, critic=%d), score=%.3f source=%s",
            passed, len(unique_issues), len(prog_issues), len(critic_issues),
            report.metadata.quality_score, score_source,
        )
        return feedback
