"""InspectorAgent：BaseReport 程序化硬查 + LLM 质检 + quality_score 三项加权。

硬查规则按 scenario 分支（spec Part 2/3/7/8/9 + Part 4.5）。
绝大多数 schema-level 约束已由 Pydantic 校验，inspector 主要做：
1. 跨字段一致性（如 ReportScope.competitors ⊆ vendor_profiles）
2. 语义合理性（如 source_refs 覆盖、recommendations 结构）
3. 量化指标（quality_score 三项加权）
"""
import logging
from typing import Optional
from src.schemas.report import BaseReport
from src.schemas.feedback import RejectionFeedback, FeedbackIssue
from src.agents.prompts import INSPECTOR_SYSTEM
from src.agents.quality_score import calc_quality_score

logger = logging.getLogger(__name__)


def _minor_only_pass(issues) -> bool:
    """只有 minor issue（或无 issue）时视为通过；critical/major 阻断。"""
    return all(i.severity == "minor" for i in issues)


class InspectorAgent:
    """质检 Agent：按 scenario 分支硬查 + LLM 质量评估 + spec Part 4.5 quality_score 公式"""

    def __init__(self, llm):
        self.llm = llm

    # ------------------------------------------------------------------
    # 通用骨架检查
    # ------------------------------------------------------------------
    def _check_common(self, report: BaseReport) -> list[FeedbackIssue]:
        issues: list[FeedbackIssue] = []

        # recommendations source_refs 非空：每条建议必须有溯源
        for idx, rec in enumerate(report.recommendations):
            if not rec.source_refs:
                issues.append(FeedbackIssue(
                    agent="writer",
                    field=f"recommendations[{idx}].source_refs",
                    severity="major",
                    reason=f"行动建议「{rec.action[:20]}」无溯源",
                    suggestion="补充支撑该建议的来源 URL",
                ))

        # analysis_sections source_refs 非空：每个章节必须有溯源
        for idx, sec in enumerate(report.analysis_sections):
            if not sec.source_refs:
                issues.append(FeedbackIssue(
                    agent="writer",
                    field=f"analysis_sections[{idx}].source_refs",
                    severity="major",
                    reason=f"章节「{sec.heading}」无溯源",
                    suggestion="标注该章节引用的来源 URL",
                ))

        # SWOT 4 象限每条 source_refs 软查（minor）
        for cat in ("strengths", "weaknesses", "opportunities", "threats"):
            for idx, entry in enumerate(getattr(report.swot, cat)):
                if not entry.source_refs:
                    issues.append(FeedbackIssue(
                        agent="analyzer",
                        field=f"swot.{cat}[{idx}].source_refs",
                        severity="minor",
                        reason=f"SWOT {cat}[{idx}] 无溯源",
                        suggestion="为 SWOT 条目补充来源",
                    ))

        # key_findings source_refs 软查（minor）
        for idx, finding in enumerate(report.key_findings):
            if not finding.source_refs:
                issues.append(FeedbackIssue(
                    agent="writer",
                    field=f"key_findings[{idx}].source_refs",
                    severity="minor",
                    reason=f"关键发现 {idx} 无溯源",
                    suggestion="补充支撑该发现的来源",
                ))

        return issues

    # ------------------------------------------------------------------
    # S1 功能迭代场景
    # ------------------------------------------------------------------
    def _check_s1(self, report: BaseReport) -> list[FeedbackIssue]:
        issues: list[FeedbackIssue] = []
        payload = report.scenario_payload
        scope_competitors = set(report.scope.competitors)

        # vendor_profiles 必须覆盖 scope.competitors
        vendor_names = {vp.competitor_name for vp in payload.vendor_profiles}
        missing = scope_competitors - vendor_names
        if missing:
            issues.append(FeedbackIssue(
                agent="writer",
                field="scenario_payload.vendor_profiles",
                severity="critical",
                reason=f"vendor_profiles 缺竞品 {sorted(missing)}（不在 scope.competitors）",
                suggestion="为缺失的每个竞品补一份 S1VendorProfile",
            ))

        # roadmap.must_build 非空（Part 2 P0）
        if not payload.roadmap_recommendations.must_build:
            issues.append(FeedbackIssue(
                agent="writer",
                field="scenario_payload.roadmap_recommendations.must_build",
                severity="major",
                reason="roadmap.must_build 为空",
                suggestion="至少给出 1 项 must_build 建议",
            ))

        # FeatureScore source_refs 软查：score!=0 应有 evidence_url
        # 注：score=2 已被 schema 强制；这里查 score=1 的覆盖率
        score1_total = 0
        score1_with_url = 0
        for cat in payload.feature_matrix.categories:
            for row in cat.features:
                for fs in row.scores.values():
                    if fs.score == 1:
                        score1_total += 1
                        if fs.evidence_url:
                            score1_with_url += 1
        if score1_total > 0 and score1_with_url / score1_total < 0.5:
            issues.append(FeedbackIssue(
                agent="writer",
                field="scenario_payload.feature_matrix",
                severity="minor",
                reason=f"score=1 的字段中仅 {score1_with_url}/{score1_total} 有 evidence_url",
                suggestion="为部分支持的功能补充来源",
            ))

        return issues

    # ------------------------------------------------------------------
    # S2 市场进入场景
    # ------------------------------------------------------------------
    def _check_s2(self, report: BaseReport) -> list[FeedbackIssue]:
        issues: list[FeedbackIssue] = []
        payload = report.scenario_payload

        # market_sizing 不全 unknown：tam/sam/som amount 至少 1 个非 None
        ms = payload.market_sizing
        amounts = [ms.tam.amount, ms.sam.amount, ms.som.amount]
        if all(a is None for a in amounts):
            issues.append(FeedbackIssue(
                agent="writer",
                field="scenario_payload.market_sizing",
                severity="major",
                reason="TAM/SAM/SOM 全无金额数据",
                suggestion="至少为 TAM 给出 amount 或在 value_basis 标注 inferred",
            ))

        # competitor_recommendations.recommended_competitors 必填覆盖
        rec_count = len(payload.competitor_recommendations.recommended_competitors)
        if rec_count < 3:
            issues.append(FeedbackIssue(
                agent="writer",
                field="scenario_payload.competitor_recommendations.recommended_competitors",
                severity="major",
                reason=f"推荐竞品仅 {rec_count} 个（< 3）",
                suggestion="至少推荐 3 个，覆盖头部+挑战者+新兴",
            ))

        # players source_refs 覆盖：>=70% 有 source_refs
        players_with_refs = sum(1 for p in payload.players if p.source_refs)
        if players_with_refs / len(payload.players) < 0.7:
            issues.append(FeedbackIssue(
                agent="writer",
                field="scenario_payload.players",
                severity="minor",
                reason=f"仅 {players_with_refs}/{len(payload.players)} 个 player 有 source_refs",
                suggestion="为多数 player 补充来源",
            ))

        return issues

    # ------------------------------------------------------------------
    # S3 定价策略场景
    # ------------------------------------------------------------------
    def _check_s3(self, report: BaseReport) -> list[FeedbackIssue]:
        issues: list[FeedbackIssue] = []
        payload = report.scenario_payload

        # rollout_plan 必有 ≥3 步（schema 已 min_length=3，兜底）
        if len(payload.rollout_plan) < 3:
            issues.append(FeedbackIssue(
                agent="writer",
                field="scenario_payload.rollout_plan",
                severity="major",
                reason="rollout_plan 步骤不足 3 个",
                suggestion="完整定价 rollout 计划至少 3 步",
            ))

        # PricingRecommendationsSummary.main_risks 非空
        if not payload.recommendations_summary.main_risks:
            issues.append(FeedbackIssue(
                agent="writer",
                field="scenario_payload.recommendations_summary.main_risks",
                severity="major",
                reason="定价建议缺主要风险列表",
                suggestion="补充至少 1 项 risk",
            ))

        # WTPResearch 若用 proxy 方法 confidence 已被 schema 强制为 low；
        # 这里检查若有 wtp_research 但 confidence=low，给 minor 提示注意可信度
        if payload.wtp_research and payload.wtp_research.confidence == "low":
            issues.append(FeedbackIssue(
                agent="writer",
                field="scenario_payload.wtp_research.confidence",
                severity="minor",
                reason="WTP 研究置信度为 low",
                suggestion="向客户解释 WTP 数据局限，建议追加问卷",
            ))

        return issues

    # ------------------------------------------------------------------
    # S4 持续监控场景
    # ------------------------------------------------------------------
    def _check_s4(self, report: BaseReport) -> list[FeedbackIssue]:
        issues: list[FeedbackIssue] = []
        payload = report.scenario_payload

        # 5 类 changes 至少有 1 类非空（否则报告无内容）
        all_change_lists = [
            payload.feature_changes, payload.pricing_changes,
            payload.messaging_changes, payload.news_events, payload.org_changes,
        ]
        total_changes = sum(len(c) for c in all_change_lists)
        if total_changes == 0:
            issues.append(FeedbackIssue(
                agent="writer",
                field="scenario_payload.changes",
                severity="critical",
                reason="所有 5 类变化（feature/pricing/messaging/news/org）全为空",
                suggestion="监控期内必须至少识别 1 项变化，否则报告无价值",
            ))

        # battlecards 至少 1 张（schema 已 min_length=1，兜底）
        if not payload.battlecards:
            issues.append(FeedbackIssue(
                agent="writer",
                field="scenario_payload.battlecards",
                severity="major",
                reason="无任何 battlecard",
                suggestion="至少为 1 个核心竞品产出 battlecard",
            ))

        # battlecard 完整度：full+partial 比例
        full_partial = sum(
            1 for bc in payload.battlecards
            if bc.overall_completeness in ("full", "partial")
        )
        if full_partial / max(1, len(payload.battlecards)) < 0.5:
            issues.append(FeedbackIssue(
                agent="writer",
                field="scenario_payload.battlecards",
                severity="minor",
                reason="多数 battlecard overall_completeness=empty",
                suggestion="补充 sales objection / proof points 等核心段",
            ))

        return issues

    # ------------------------------------------------------------------
    # S5 战略定位场景
    # ------------------------------------------------------------------
    def _check_s5(self, report: BaseReport) -> list[FeedbackIssue]:
        issues: list[FeedbackIssue] = []
        payload = report.scenario_payload

        # vendor_profiles 必须覆盖 scope.competitors
        scope_competitors = set(report.scope.competitors)
        vendor_names = {vp.competitor_name for vp in payload.vendor_profiles}
        missing = scope_competitors - vendor_names
        if missing:
            issues.append(FeedbackIssue(
                agent="writer",
                field="scenario_payload.vendor_profiles",
                severity="critical",
                reason=f"vendor_profiles 缺竞品 {sorted(missing)}",
                suggestion="为缺失竞品补一份 S5VendorProfile",
            ))

        # PerceptualMap.display_watermark：spec 要求显式标记 AI 推断
        if not payload.perceptual_map.display_watermark:
            issues.append(FeedbackIssue(
                agent="writer",
                field="scenario_payload.perceptual_map.display_watermark",
                severity="major",
                reason="perceptual_map 未启用 display_watermark",
                suggestion="设置 display_watermark=True 标记 AI 推断结果",
            ))

        # PositioningStatement.confidence == low_confidence 时提醒
        if payload.positioning_statement.confidence == "low_confidence":
            issues.append(FeedbackIssue(
                agent="writer",
                field="scenario_payload.positioning_statement.confidence",
                severity="minor",
                reason="定位陈述置信度为 low_confidence",
                suggestion="建议对客户标注此为低置信度推断，需访谈验证",
            ))

        return issues

    # ------------------------------------------------------------------
    # 统一 dispatcher
    # ------------------------------------------------------------------
    def _programmatic_checks(
        self, report: BaseReport, competitors: list[str]
    ) -> list[FeedbackIssue]:
        issues = self._check_common(report)
        scenario = report.scenario
        if scenario == "S1":
            issues.extend(self._check_s1(report))
        elif scenario == "S2":
            issues.extend(self._check_s2(report))
        elif scenario == "S3":
            issues.extend(self._check_s3(report))
        elif scenario == "S4":
            issues.extend(self._check_s4(report))
        elif scenario == "S5":
            issues.extend(self._check_s5(report))
        return issues

    # ------------------------------------------------------------------
    # 主入口
    # ------------------------------------------------------------------
    async def inspect(
        self,
        report: BaseReport,
        competitors: Optional[list[str]] = None,
        retry_count: int = 0,
        max_retries: int = 2,
    ) -> RejectionFeedback:
        logger.info("[inspector] 开始质检, scenario=%s, retry=%d", report.scenario, retry_count)
        competitors = competitors or []

        programmatic_issues = self._programmatic_checks(report, competitors)

        report_text = report.model_dump_json()
        llm_result = await self.llm.call_json(
            INSPECTOR_SYSTEM, f"请检查以下报告：\n\n{report_text}"
        )
        llm_issues_raw = llm_result.get("issues", [])
        llm_issues: list[FeedbackIssue] = []
        for raw in llm_issues_raw:
            try:
                llm_issues.append(FeedbackIssue(**raw))
            except Exception as e:  # noqa: BLE001
                logger.warning("[inspector] 解析 LLM issue 失败, 跳过: %s, raw=%s", e, raw)

        all_issues = programmatic_issues + llm_issues

        seen = set()
        unique_issues = []
        for issue in sorted(all_issues, key=lambda i: {"critical": 0, "major": 1, "minor": 2}[i.severity]):
            key = (issue.agent, issue.field)
            if key not in seen:
                seen.add(key)
                unique_issues.append(issue)

        # 写入 quality_score（spec Part 4.5）
        score, note = calc_quality_score(report, unique_issues)
        report.metadata.quality_score = score
        report.metadata.quality_score_calculation_note = note

        passed = _minor_only_pass(unique_issues)

        feedback = RejectionFeedback(
            passed=passed,
            issues=unique_issues,
            retry_count=retry_count,
            max_retries=max_retries,
        )
        minor_cnt = sum(1 for i in unique_issues if i.severity == "minor")
        logger.info(
            "[inspector] 质检完成, passed=%s, issues=%d (minor=%d), score=%s",
            passed, len(unique_issues), minor_cnt, score,
        )
        return feedback
