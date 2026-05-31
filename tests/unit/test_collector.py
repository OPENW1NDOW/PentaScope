import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from src.schemas.input import CompetitorInput, CompetitorBasic, AnalysisGoal
from src.schemas.profile import CompetitorProfile
from src.agents.collector import CollectorAgent


class TestCollectorAgent:
    @pytest.mark.asyncio
    async def test_parse_goal_returns_analysis_goal(self):
        mock_llm = MagicMock()
        mock_llm.call_json = AsyncMock(return_value={
            "goal_type": "feature_iteration", "product_stage": "growing",
            "focus_area": "支付", "output_expectation": "action"
        })

        agent = CollectorAgent(llm=mock_llm, http=MagicMock(), parser=MagicMock())
        goal = await agent.parse_goal("分析支付宝的支付功能")
        assert goal.goal_type == "feature_iteration"
        assert goal.focus_area == "支付"

    @pytest.mark.asyncio
    async def test_classify_competitor_returns_type(self):
        mock_llm = MagicMock()
        mock_llm.call_json = AsyncMock(return_value={
            "competitor_type": "核心竞品", "reason": "目标用户相同"
        })

        agent = CollectorAgent(llm=mock_llm, http=MagicMock(), parser=MagicMock())
        result = await agent.classify_competitor("支付宝", AnalysisGoal())
        assert result["competitor_type"] == "核心竞品"

    @pytest.mark.asyncio
    async def test_collect_returns_profiles(self, sample_competitor_profile):
        mock_llm = MagicMock()
        mock_llm.call_json = AsyncMock(side_effect=[
            # parse_goal
            {"goal_type": "competitive_monitoring", "product_stage": "growing", "focus_area": "", "output_expectation": "action"},
            # classify
            {"competitor_type": "核心竞品", "reason": "test"},
            # extract_profile - return raw data without classification and metadata
            {k: v for k, v in sample_competitor_profile.items() if k not in ("classification", "metadata")},
        ])

        mock_http = MagicMock()
        mock_http.get = AsyncMock(return_value="<html><body>支付宝</body></html>")

        mock_parser = MagicMock()
        mock_parser.extract_text.return_value = "支付宝 移动支付"
        mock_parser.extract_meta.return_value = {}

        agent = CollectorAgent(llm=mock_llm, http=mock_http, parser=mock_parser)
        user_input = CompetitorInput(
            competitors=[CompetitorBasic(name="支付宝")],
            analysis_context="分析支付宝"
        )
        profiles = await agent.collect(user_input)
        assert len(profiles) == 1
        assert isinstance(profiles[0], CompetitorProfile)
