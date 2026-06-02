import pytest
from unittest.mock import AsyncMock, MagicMock
from src.schemas.report import FinalReport
from src.agents.inspector import InspectorAgent


class TestInspectorAgent:
    @pytest.mark.asyncio
    async def test_pass_good_report(self, sample_final_report):
        mock_llm = MagicMock()
        mock_llm.call_json = AsyncMock(return_value={"passed": True, "issues": []})

        agent = InspectorAgent(llm=mock_llm)
        report = FinalReport(**sample_final_report)

        result = await agent.inspect(report)
        assert result.passed is True
        assert len(result.issues) == 0

    @pytest.mark.asyncio
    async def test_reject_bad_report(self, sample_final_report):
        mock_llm = MagicMock()
        mock_llm.call_json = AsyncMock(return_value={
            "passed": False,
            "issues": [
                {"agent": "writer", "field": "executive_summary", "severity": "critical", "reason": "摘要为空", "suggestion": "补充摘要"}
            ]
        })

        agent = InspectorAgent(llm=mock_llm)
        report = FinalReport(**sample_final_report)

        result = await agent.inspect(report)
        assert result.passed is False
        assert result.issues[0].agent == "writer"

    @pytest.mark.asyncio
    async def test_programmatic_checks_catch_empty_summary(self):
        """即使 LLM 说通过，程序化检查也应捕获空摘要"""
        mock_llm = MagicMock()
        mock_llm.call_json = AsyncMock(return_value={"passed": True, "issues": []})

        agent = InspectorAgent(llm=mock_llm)
        from src.schemas.report import ExecutiveSummary, ActionItems
        report = FinalReport(
            title="测试报告",
            executive_summary=ExecutiveSummary(
                what_competitors_did_right="",  # 空！
                what_competitors_did_wrong="test",
                our_opportunities="test",
                next_steps_summary="test"
            ),
            action_items=ActionItems(immediate=[], short_term=[], long_term=[])  # 空！
        )

        result = await agent.inspect(report)
        assert result.passed is False
        severity_critical = [i for i in result.issues if i.severity == "critical"]
        assert len(severity_critical) >= 1
