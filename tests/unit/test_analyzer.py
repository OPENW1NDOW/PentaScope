import pytest
from unittest.mock import AsyncMock, MagicMock
from src.schemas.analysis import CompetitiveAnalysis
from src.agents.analyzer import AnalyzerAgent


class TestAnalyzerAgent:
    @pytest.mark.asyncio
    async def test_analyze_returns_competitive_analysis(self, sample_competitor_profile, sample_competitive_analysis):
        mock_llm = MagicMock()
        mock_llm.call_json = AsyncMock(return_value=sample_competitive_analysis)

        agent = AnalyzerAgent(llm=mock_llm)
        from src.schemas.profile import CompetitorProfile
        profiles = [CompetitorProfile(**sample_competitor_profile)]

        result = await agent.analyze(profiles)
        assert isinstance(result, CompetitiveAnalysis)
        assert len(result.feature_matrix) == 1
        assert len(result.radar_scores) == 1
