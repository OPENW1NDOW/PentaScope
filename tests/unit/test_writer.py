import pytest
from unittest.mock import AsyncMock, MagicMock
from src.schemas.report import FinalReport
from src.agents.writer import WriterAgent


class TestWriterAgent:
    @pytest.mark.asyncio
    async def test_write_returns_final_report(self, sample_competitive_analysis, sample_final_report):
        mock_llm = MagicMock()
        mock_llm.call_json = AsyncMock(return_value=sample_final_report)

        agent = WriterAgent(llm=mock_llm)
        from src.schemas.analysis import CompetitiveAnalysis
        analysis = CompetitiveAnalysis(**sample_competitive_analysis)

        result = await agent.write(analysis, ["支付宝"])
        assert isinstance(result, FinalReport)
        assert result.executive_summary.what_competitors_did_right != ""
        assert len(result.action_items.immediate) >= 1
