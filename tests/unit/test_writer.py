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


@pytest.mark.asyncio
async def test_writer_mechanically_transfers_structured_fields():
    from src.agents.writer import WriterAgent
    from src.schemas.analysis import (
        CompetitiveAnalysis, Swot, SwotEntry, RadarScore, RadarDimensions,
        FeatureMatrixEntry,
    )
    analysis = CompetitiveAnalysis(
        swot=Swot(strengths=[SwotEntry(point="强")]),
        radar_scores=[RadarScore(competitor="X", dimensions=RadarDimensions(
            feature_breadth=4, usability=4, cost_effectiveness=3, stability=4, design_quality=5))],
        feature_matrix=[FeatureMatrixEntry(feature="f")],
    )

    class _LLM:
        async def call_json(self, system, user):
            return {
                "title": "报告",
                "executive_summary": {
                    "what_competitors_did_right": "x" * 20,
                    "what_competitors_did_wrong": "x" * 20,
                    "our_opportunities": "x" * 20,
                    "next_steps_summary": "x" * 20,
                },
                "sections": [{"title": "概览", "content": "c"}],
                "action_items": {"immediate": [{"priority": "高", "description": "d"}],
                                 "short_term": [{"priority": "中", "description": "d"}],
                                 "long_term": [{"priority": "低", "description": "d"}]},
            }

    report = await WriterAgent(llm=_LLM()).write(analysis, ["X"])
    assert report.swot.strengths[0].point == "强"
    assert report.radar_scores[0].competitor == "X"
    assert report.feature_matrix[0].feature == "f"
