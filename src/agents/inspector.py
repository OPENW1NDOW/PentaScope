"""InspectorAgent 桩级过渡版。

旧版基于 FinalReport 的 _programmatic_checks 已无法工作（A 大类删除了 FinalReport
及其 sections / action_items / executive_summary 旧 4 段字段）。
F 阶段 Task 21.0e2-3 会重写为按 scenario 分支硬查 + quality_score 三项加权。

本过渡版：
- 修复 import（FinalReport → BaseReport）让全链路 import 不崩
- inspect 方法仅做最小 LLM 质检（保留 LLM 调用通路），程序化 checks 暂留空
- 让 graph 在 D/E 阶段能跑通（即使质检几乎不产 issue），F 阶段全面重写
"""
import logging
from src.schemas.report import BaseReport
from src.schemas.feedback import RejectionFeedback, FeedbackIssue
from src.agents.prompts import INSPECTOR_SYSTEM

logger = logging.getLogger(__name__)


def _minor_only_pass(issues) -> bool:
    """只有 minor issue（或无 issue）时视为通过；critical/major 阻断。"""
    return all(i.severity == "minor" for i in issues)


class InspectorAgent:
    """质检 Agent 过渡版。F 阶段重写。"""

    def __init__(self, llm):
        self.llm = llm

    def _programmatic_checks(self, report: BaseReport, competitors: list[str]) -> list[FeedbackIssue]:
        """程序化检查暂留空（旧实现依赖 FinalReport.sections/action_items 已删）。

        F 阶段 Task 21.0e2 重写为 _check_common + _check_s1..s5 dispatcher。
        """
        return []

    async def inspect(self, report: BaseReport, competitors: list[str] | None = None,
                      retry_count: int = 0, max_retries: int = 2) -> RejectionFeedback:
        """执行质量检查（过渡版：仅 LLM 检查 + 容错）"""
        logger.info("[inspector] 开始质检（过渡版）, retry_count=%d", retry_count)
        competitors = competitors or []

        programmatic_issues = self._programmatic_checks(report, competitors)

        # LLM 质检：失败时不阻断（过渡阶段优先保证流水线能跑）
        llm_issues: list[FeedbackIssue] = []
        try:
            report_text = report.model_dump_json()
            llm_result = await self.llm.call_json(INSPECTOR_SYSTEM, f"请检查以下报告：\n\n{report_text}")
            for issue in llm_result.get("issues", []):
                try:
                    llm_issues.append(FeedbackIssue(**issue))
                except Exception as e:
                    logger.warning("[inspector] LLM issue 解析失败: %s, raw=%s", e, issue)
        except Exception as e:
            logger.warning("[inspector] LLM 质检失败（过渡阶段不阻断）: %s", e)

        all_issues = programmatic_issues + llm_issues

        seen = set()
        unique_issues = []
        for issue in sorted(all_issues, key=lambda i: {"critical": 0, "major": 1, "minor": 2}[i.severity]):
            key = (issue.agent, getattr(issue, "field", ""))
            if key not in seen:
                seen.add(key)
                unique_issues.append(issue)

        passed = _minor_only_pass(unique_issues)

        feedback = RejectionFeedback(
            passed=passed,
            issues=unique_issues,
            retry_count=retry_count,
            max_retries=max_retries,
        )
        minor_cnt = sum(1 for i in unique_issues if i.severity == "minor")
        logger.info("[inspector] 质检完成（过渡版）, passed=%s, issues=%d (minor=%d)",
                    passed, len(unique_issues), minor_cnt)
        return feedback
