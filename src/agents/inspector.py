import logging
from src.schemas.report import FinalReport
from src.schemas.feedback import RejectionFeedback, FeedbackIssue
from src.agents.prompts import INSPECTOR_SYSTEM

logger = logging.getLogger(__name__)


def _MINOR_ONLY_PASS(issues) -> bool:
    """只有 minor issue（或无 issue）时视为通过；critical/major 阻断。"""
    return all(i.severity == "minor" for i in issues)


class InspectorAgent:
    """质检 Agent：Schema 校验 + 溯源检查 + LLM 质量评估"""

    def __init__(self, llm):
        self.llm = llm

    def _programmatic_checks(self, report: FinalReport, competitors: list[str]) -> list[FeedbackIssue]:
        """程序化检查：不依赖 LLM 的硬性规则"""
        issues = []

        # 检查执行摘要四段是否填写
        es = report.executive_summary
        for field_name, field_value in [
            ("what_competitors_did_right", es.what_competitors_did_right),
            ("what_competitors_did_wrong", es.what_competitors_did_wrong),
            ("our_opportunities", es.our_opportunities),
            ("next_steps_summary", es.next_steps_summary),
        ]:
            if not field_value or len(field_value.strip()) < 10:
                issues.append(FeedbackIssue(
                    agent="writer", field=f"executive_summary.{field_name}",
                    severity="critical", reason="执行摘要该段为空或过短",
                    suggestion="补充 50-150 字的内容"
                ))

        # 检查行动建议每个时间层至少 1 条
        ai = report.action_items
        for layer_name, layer_items in [
            ("immediate", ai.immediate), ("short_term", ai.short_term), ("long_term", ai.long_term)
        ]:
            if len(layer_items) == 0:
                issues.append(FeedbackIssue(
                    agent="writer", field=f"action_items.{layer_name}",
                    severity="major", reason=f"行动建议 {layer_name} 层为空",
                    suggestion="至少添加 1 条行动建议"
                ))

        # 检查报告章节是否为空
        if not report.sections:
            issues.append(FeedbackIssue(
                agent="writer", field="sections",
                severity="major", reason="报告无章节内容",
                suggestion="至少添加 1 个章节"
            ))

        # SWOT 四象限至少各 1 条
        sw = report.swot
        if not (sw.strengths and sw.weaknesses and sw.opportunities and sw.threats):
            issues.append(FeedbackIssue(
                agent="analyzer", field="swot",
                severity="major", reason="SWOT 四象限不完整",
                suggestion="每个象限至少 1 条"))

        # 雷达：每个竞品一条
        radar_comps = {r.competitor for r in report.radar_scores}
        if not all(c in radar_comps for c in competitors):
            issues.append(FeedbackIssue(
                agent="analyzer", field="radar_scores",
                severity="major", reason="雷达评分缺竞品",
                suggestion="每个竞品填一条 0-5 五维评分"))

        # 功能矩阵非空
        if not report.feature_matrix:
            issues.append(FeedbackIssue(
                agent="analyzer", field="feature_matrix",
                severity="major", reason="功能矩阵为空",
                suggestion="至少补充关键功能对比"))

        # 维度级溯源：有内容的 section 必须有 source_refs
        for idx, sec in enumerate(report.sections):
            if sec.content.strip() and not sec.source_refs:
                issues.append(FeedbackIssue(
                    agent="writer", field=f"sections[{idx}].source_refs",
                    severity="major", reason=f"章节「{sec.title}」无溯源",
                    suggestion="标注该章节引用的来源 URL"))

        # action_item 溯源：软查（minor，不阻断 pass）
        for layer_name, layer in [("immediate", report.action_items.immediate),
                                   ("short_term", report.action_items.short_term),
                                   ("long_term", report.action_items.long_term)]:
            for j, item in enumerate(layer):
                if not item.source_urls:
                    issues.append(FeedbackIssue(
                        agent="writer", field=f"action_items.{layer_name}[{j}].source_urls",
                        severity="minor", reason="行动建议未标注来源",
                        suggestion="补充支撑该建议的来源 URL"))

        return issues

    async def inspect(self, report: FinalReport, competitors: list[str] | None = None,
                      retry_count: int = 0, max_retries: int = 2) -> RejectionFeedback:
        """执行质量检查"""
        logger.info("[inspector] 开始质检, retry_count=%d", retry_count)
        competitors = competitors or []

        programmatic_issues = self._programmatic_checks(report, competitors)

        report_text = report.model_dump_json()
        llm_result = await self.llm.call_json(INSPECTOR_SYSTEM, f"请检查以下报告：\n\n{report_text}")

        llm_issues = [FeedbackIssue(**issue) for issue in llm_result.get("issues", [])]
        all_issues = programmatic_issues + llm_issues

        seen = set()
        unique_issues = []
        for issue in sorted(all_issues, key=lambda i: {"critical": 0, "major": 1, "minor": 2}[i.severity]):
            key = (issue.agent, issue.field)
            if key not in seen:
                seen.add(key)
                unique_issues.append(issue)

        passed = _MINOR_ONLY_PASS(unique_issues)

        feedback = RejectionFeedback(
            passed=passed,
            issues=unique_issues,
            retry_count=retry_count,
            max_retries=max_retries,
        )
        logger.info("[inspector] 质检完成, passed=%s, issues=%d", passed, len(unique_issues))
        return feedback
