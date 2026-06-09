"""InspectorAgent 重写版：_check_common + _check_s1..s5 dispatcher + LLM 质检 + quality_score 三项加权。

设计原则：
- 不重复 Pydantic 已查的硬约束（vendor↔matrix 一致性、is_self 唯一、tier_added baseline 等已被各 scenario 的 model_validator 拦截）
- 只查 Pydantic 不查的「语义级问题」：占位文本、显著缺值、低质模式
- LLM 质检保留（issue 严重度由 LLM 自评）
- quality_score 由 calc_quality_score 三项加权得出，写回 metadata（v3-R22 锁定 inspector 一次性回填）

E3 后续在 _check_warnings_prefix 中实现 metadata.warnings 前缀降分。
"""
import logging

from src.agents.prompts import INSPECTOR_SYSTEM
from src.agents.quality_score import calc_quality_score
from src.schemas.feedback import FeedbackIssue, RejectionFeedback
from src.schemas.report import BaseReport

logger = logging.getLogger(__name__)


# ============ Placeholder warnings 前缀（v3-R17） ============

# writer 在 metadata.warnings 中以这些前缀标记 placeholder 输出，inspector 必须降分
_PLACEHOLDER_WARNING_PREFIXES = (
    "placeholder_section:",
    "placeholder_swot",
    "dropped_unverified_entries:",
)
_QUALITY_SCORE_CAP_ON_PLACEHOLDER = 0.5


def _detect_placeholder_warnings(report: BaseReport) -> list[str]:
    """从 metadata.warnings 中过滤出含 placeholder 前缀的 warning"""
    return [
        w for w in report.metadata.warnings
        if any(w.startswith(p) for p in _PLACEHOLDER_WARNING_PREFIXES)
    ]


def _check_warnings_prefix(report: BaseReport) -> list[FeedbackIssue]:
    """v3-R17：将 placeholder warnings 转为 inspector issues（同时触发 quality_score cap 0.5）"""
    placeholder_warnings = _detect_placeholder_warnings(report)
    if not placeholder_warnings:
        return []
    return [FeedbackIssue(
        agent="writer",
        field="metadata.warnings",
        severity="major",
        reason=f"writer 产出 {len(placeholder_warnings)} 个 placeholder/dropped warnings: {placeholder_warnings[:3]}",
        suggestion="检查 collector 数据完整度或重写 affected sections",
    )]


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

    # competitive_pricing_matrix 数 < scope.competitors 的一半
    cpm_n = len(payload.competitive_pricing_matrix)
    return issues if cpm_n >= 2 else issues + [FeedbackIssue(
        agent="collector", field="scenario_payload.competitive_pricing_matrix",
        severity="major",
        reason=f"竞品定价矩阵仅 {cpm_n} 条，覆盖不足",
        suggestion="至少采集 2 个竞品的完整定价",
    )]


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


# ============ InspectorAgent ============

class InspectorAgent:
    """质检 Agent v3：通用硬查 + 场景硬查 + LLM 质检 + quality_score 回填"""

    def __init__(self, llm):
        self.llm = llm

    def _programmatic_checks(self, report: BaseReport) -> list[FeedbackIssue]:
        """通用硬查 + 场景硬查 + placeholder warnings 前缀检查（v3-R17）"""
        return (
            _check_common(report)
            + _dispatch_scenario_check(report)
            + _check_warnings_prefix(report)
        )

    async def _llm_check(self, report: BaseReport) -> list[FeedbackIssue]:
        """LLM 内容质量与深度检查（非阻断：失败仅 warning）"""
        try:
            report_text = report.model_dump_json()
            llm_result = await self.llm.call_json(
                INSPECTOR_SYSTEM, f"请检查以下报告：\n\n{report_text}",
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("[inspector] LLM 质检失败（非阻断）: %s", e)
            return []

        issues: list[FeedbackIssue] = []
        for raw in llm_result.get("issues", []):
            try:
                issues.append(FeedbackIssue(**raw))
            except Exception as e:  # noqa: BLE001
                logger.warning("[inspector] LLM issue 解析失败: %s, raw=%s", e, raw)
        return issues

    async def inspect(
        self,
        report: BaseReport,
        competitors: list[str] | None = None,
        retry_count: int = 0,
        max_retries: int = 2,
    ) -> RejectionFeedback:
        """执行质检 + 回填 quality_score。

        competitors 参数保留兼容旧 graph 调用，本版未使用（scope 由 report.scope 自带）。
        """
        logger.info("[inspector] 开始质检 v3, scenario=%s, retry=%d", report.scenario, retry_count)
        _ = competitors  # 兼容 graph 旧 signature

        prog_issues = self._programmatic_checks(report)
        llm_issues = await self._llm_check(report)
        all_issues = prog_issues + llm_issues

        # 去重 (agent, field) 保留最严重的
        seen: dict[tuple[str, str], FeedbackIssue] = {}
        sev_rank = {"critical": 0, "major": 1, "minor": 2}
        for issue in sorted(all_issues, key=lambda i: sev_rank[i.severity]):
            key = (issue.agent, issue.field)
            if key not in seen:
                seen[key] = issue
        unique_issues = list(seen.values())

        # 回填 quality_score（v3-R22 inspector 一次性写入）
        score, note = calc_quality_score(report, unique_issues)
        # v3-R17：placeholder warnings 强制 cap 到 0.5
        if _detect_placeholder_warnings(report) and score > _QUALITY_SCORE_CAP_ON_PLACEHOLDER:
            note = f"{note}; capped to {_QUALITY_SCORE_CAP_ON_PLACEHOLDER} due to placeholder warnings (v3-R17)"
            score = _QUALITY_SCORE_CAP_ON_PLACEHOLDER
        report.metadata.quality_score = score
        report.metadata.quality_score_calculation_note = note
        logger.info("[inspector] quality_score=%.3f (%s)", score, note)

        passed = all(i.severity == "minor" for i in unique_issues)
        feedback = RejectionFeedback(
            passed=passed,
            issues=unique_issues,
            retry_count=retry_count,
            max_retries=max_retries,
        )
        logger.info(
            "[inspector] 质检完成 v3, passed=%s, issues=%d (prog=%d, llm=%d)",
            passed, len(unique_issues), len(prog_issues), len(llm_issues),
        )
        return feedback
