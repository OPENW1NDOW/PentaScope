import pytest
from unittest.mock import AsyncMock, MagicMock
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

        agent = CollectorAgent(llm=mock_llm, pipeline=MagicMock())
        goal = await agent.parse_goal("分析支付宝的支付功能")
        assert goal.goal_type == "feature_iteration"
        assert goal.focus_area == "支付"

    @pytest.mark.asyncio
    async def test_classify_competitor_returns_type(self):
        mock_llm = MagicMock()
        mock_llm.call_json = AsyncMock(return_value={
            "competitor_type": "核心竞品", "reason": "目标用户相同"
        })

        agent = CollectorAgent(llm=mock_llm, pipeline=MagicMock())
        result = await agent.classify_competitor("支付宝", AnalysisGoal())
        assert result["competitor_type"] == "核心竞品"

    @pytest.mark.asyncio
    async def test_collect_returns_profiles(self, sample_competitor_profile):
        mock_llm = MagicMock()
        mock_llm.call_json = AsyncMock(side_effect=[
            {"goal_type": "competitive_monitoring", "product_stage": "growing", "focus_area": "", "output_expectation": "action"},
            {"competitor_type": "核心竞品", "reason": "test"},
            {k: v for k, v in sample_competitor_profile.items() if k not in ("classification", "metadata")},
        ])
        mock_pipeline = MagicMock()
        mock_pipeline.collect = AsyncMock(return_value=("支付宝 移动支付正文" * 10,
                                                        ["https://www.alipay.com/features"],
                                                        [{"step": "route"}]))
        agent = CollectorAgent(llm=mock_llm, pipeline=mock_pipeline)
        user_input = CompetitorInput(
            competitors=[CompetitorBasic(name="支付宝")],
            analysis_context="分析支付宝",
        )
        profiles = await agent.collect(user_input)
        assert len(profiles) == 1
        assert isinstance(profiles[0], CompetitorProfile)
        assert profiles[0].metadata.pipeline_trace == [{"step": "route"}]

    def test_detect_category_uses_input_category(self):
        agent = CollectorAgent(llm=MagicMock(), pipeline=MagicMock())
        comp = CompetitorBasic(name="Notion", category="协作软件")
        assert agent.detect_category(comp) == "saas"

    def test_detect_category_default_when_unknown(self):
        agent = CollectorAgent(llm=MagicMock(), pipeline=MagicMock())
        comp = CompetitorBasic(name="某硬件", category="消费电子")
        assert agent.detect_category(comp) == "default"

    def test_detect_category_calls_no_llm(self):
        mock_llm = MagicMock()
        mock_llm.call_json = AsyncMock()
        agent = CollectorAgent(llm=mock_llm, pipeline=MagicMock())
        agent.detect_category(CompetitorBasic(name="XX", category="工具"))
        mock_llm.call_json.assert_not_called()

    def test_build_placeholder_profile(self):
        agent = CollectorAgent(llm=MagicMock(), pipeline=MagicMock())
        comp = CompetitorBasic(name="某竞品", company="某公司")
        classification = {"competitor_type": "核心竞品", "reason": "占位"}
        profile = agent._build_placeholder_profile(comp, classification, trace=[{"step": "all_empty"}])
        assert isinstance(profile, CompetitorProfile)
        assert profile.metadata.completeness_score == 0.0
        assert profile.metadata.data_sources == []
        assert profile.basic_info.name == "某竞品"
        assert profile.metadata.pipeline_trace == [{"step": "all_empty"}]

    @pytest.mark.asyncio
    async def test_partial_failure_one_competitor_placeholder(self, sample_competitor_profile):
        mock_llm = MagicMock()
        raw_profile = {k: v for k, v in sample_competitor_profile.items() if k not in ("classification", "metadata")}
        # parse_goal, A:classify, A:extract, B:classify(raises)
        mock_llm.call_json = AsyncMock(side_effect=[
            {"goal_type": "competitive_monitoring", "product_stage": "growing", "focus_area": "", "output_expectation": "action"},
            {"competitor_type": "核心竞品", "reason": "ok"},
            raw_profile,
            RuntimeError("B classify 炸了"),
        ])
        mock_pipeline = MagicMock()
        mock_pipeline.collect = AsyncMock(return_value=("有效正文" * 30, ["https://a.com"], []))
        agent = CollectorAgent(llm=mock_llm, pipeline=mock_pipeline)
        user_input = CompetitorInput(
            competitors=[CompetitorBasic(name="甲竞品"), CompetitorBasic(name="乙竞品")],
            analysis_context="对比",
        )
        profiles = await agent.collect(user_input)
        assert len(profiles) == 2
        assert profiles[1].metadata.completeness_score == 0.0

    @pytest.mark.asyncio
    async def test_all_empty_produces_placeholder_no_extract_llm(self):
        mock_llm = MagicMock()
        mock_llm.call_json = AsyncMock(side_effect=[
            {"goal_type": "competitive_monitoring", "product_stage": "growing", "focus_area": "", "output_expectation": "action"},
            {"competitor_type": "核心竞品", "reason": "ok"},
        ])  # only parse_goal + classify, NO extract
        mock_pipeline = MagicMock()
        mock_pipeline.collect = AsyncMock(return_value=("", [], [{"step": "all_empty"}]))  # empty
        agent = CollectorAgent(llm=mock_llm, pipeline=mock_pipeline)
        user_input = CompetitorInput(
            competitors=[CompetitorBasic(name="空竞品")], analysis_context="x",
        )
        profiles = await agent.collect(user_input)
        assert profiles[0].metadata.completeness_score == 0.0
        assert mock_llm.call_json.call_count == 2  # extract NOT called (else side_effect StopIteration)
