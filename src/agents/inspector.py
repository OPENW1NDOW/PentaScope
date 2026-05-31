import logging
from src.schemas.report import FinalReport
from src.schemas.feedback import RejectionFeedback, FeedbackIssue
from src.agents.prompts import INSPECTOR_SYSTEM

logger = logging.getLogger(__name__)


class InspectorAgent:
    """质检 Agent：Schema 校验 + 溯源检查 + LLM 质量评估"""

    def __init__(self, llm):
        self.llm = llm

    def _programmatic_checks(self, report: FinalReport) -> list[FeedbackIssue]:
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

        return issues

    async def inspect(self, report: FinalReport, retry_count: int = 0, max_retries: int = 2) -> RejectionFeedback:
        """执行质量检查"""
        logger.info("[inspector] 开始质检, retry_count=%d", retry_count)

        # 程序化检查
        programmatic_issues = self._programmatic_checks(report)

        # LLM 质量评估
        report_text = report.model_dump_json()
        llm_result = await self.llm.call_json(INSPECTOR_SYSTEM, f"请检查以下报告：\n\n{report_text[:15000]}")

        # 合并结果
        llm_issues = [
            FeedbackIssue(**issue) for issue in llm_result.get("issues", [])
        ]
        all_issues = programmatic_issues + llm_issues

        # 去重（同一 agent+field 的 critical 优先）
        seen = set()
        unique_issues = []
        for issue in sorted(all_issues, key=lambda i: {"critical": 0, "major": 1, "minor": 2}[i.severity]):
            key = (issue.agent, issue.field)
            if key not in seen:
                seen.add(key)
                unique_issues.append(issue)

        passed = len(unique_issues) == 0

        feedback = RejectionFeedback(
            passed=passed,
            issues=unique_issues,
            retry_count=retry_count,
            max_retries=max_retries,
        )

        logger.info("[inspector] 质检完成, passed=%s, issues=%d", passed, len(unique_issues))
        return feedback
