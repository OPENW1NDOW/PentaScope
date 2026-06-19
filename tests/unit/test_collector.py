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
                                                        [{"step": "route"}],
                                                        "【来源: https://www.alipay.com/features】\n" + "支付宝 移动支付正文" * 10))
        agent = CollectorAgent(llm=mock_llm, pipeline=mock_pipeline)
        user_input = CompetitorInput(
            scenario="S1",
            our_product_name="MyProduct",
            competitors=[CompetitorBasic(name="支付宝")],
            analysis_context="分析支付宝",
        )
        profiles, _, _ = await agent.collect(user_input)
        assert len(profiles) == 1
        assert isinstance(profiles[0], CompetitorProfile)
        assert profiles[0].metadata.pipeline_trace == [{"step": "route"}]

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
        mock_pipeline.collect = AsyncMock(return_value=("有效正文" * 30, ["https://a.com"], [],
                                                        "【来源: https://a.com】\n" + "有效正文" * 30))
        agent = CollectorAgent(llm=mock_llm, pipeline=mock_pipeline)
        user_input = CompetitorInput(
            scenario="S1",
            our_product_name="MyProduct",
            competitors=[CompetitorBasic(name="甲竞品"), CompetitorBasic(name="乙竞品")],
            analysis_context="对比",
        )
        profiles, _, _ = await agent.collect(user_input)
        assert len(profiles) == 2
        assert profiles[1].metadata.completeness_score == 0.0

    @pytest.mark.asyncio
    async def test_extract_failure_preserves_pipeline_sources(self):
        """[prove-it] pipeline 成功拿到 URL 但 LLM 抽取失败时，占位 profile 必须保留 pipeline sources。"""
        mock_llm = MagicMock()
        mock_llm.call_json = AsyncMock(side_effect=[
            {"goal_type": "competitive_monitoring", "product_stage": "growing", "focus_area": "", "output_expectation": "action"},
            {"competitor_type": "核心竞品", "reason": "ok"},
            TimeoutError("LLM 超时"),  # extract 第 1 次
            TimeoutError("LLM 超时"),  # extract 第 2 次（重试）
        ])
        mock_pipeline = MagicMock()
        mock_pipeline.collect = AsyncMock(return_value=(
            "正文内容" * 30,
            ["https://a.com", "https://b.com"],
            [{"step": "tavily_query", "results": 2}],
            "【来源: https://a.com】\n正文",
        ))
        agent = CollectorAgent(llm=mock_llm, pipeline=mock_pipeline)
        user_input = CompetitorInput(
            scenario="S1", our_product_name="MyProduct",
            competitors=[CompetitorBasic(name="某竞品")], analysis_context="x",
        )
        profiles, _, _ = await agent.collect(user_input)
        assert len(profiles) == 1
        # 关键断言：pipeline 拿到的 URL 必须保留在 data_sources 中
        assert profiles[0].metadata.data_sources == ["https://a.com", "https://b.com"]
        assert profiles[0].metadata.completeness_score == 0.0

    @pytest.mark.asyncio
    async def test_all_empty_produces_placeholder_no_extract_llm(self):
        mock_llm = MagicMock()
        mock_llm.call_json = AsyncMock(side_effect=[
            {"goal_type": "competitive_monitoring", "product_stage": "growing", "focus_area": "", "output_expectation": "action"},
            {"competitor_type": "核心竞品", "reason": "ok"},
        ])  # only parse_goal + classify, NO extract
        mock_pipeline = MagicMock()
        mock_pipeline.collect = AsyncMock(return_value=("", [], [{"step": "all_empty"}], ""))  # empty
        agent = CollectorAgent(llm=mock_llm, pipeline=mock_pipeline)
        user_input = CompetitorInput(
            scenario="S1",
            our_product_name="MyProduct",
            competitors=[CompetitorBasic(name="空竞品")], analysis_context="x",
        )
        profiles, _, _ = await agent.collect(user_input)
        assert profiles[0].metadata.completeness_score == 0.0
        assert mock_llm.call_json.call_count == 2  # extract NOT called (else side_effect StopIteration)


@pytest.mark.asyncio
async def test_extract_profile_truncates_oversize_text():
    """[bug1 prove-it] labeled_text 超 100K 字符时必须截断，避免 Doubao 400 token 上限。

    现象（trace 20260609-150301-df17ff / 20260609-161001-a2db5b）：
    飞书文档 raw_content 拼起来 >150K 字符，Doubao 直接返 400
    'Total tokens of multi-modal content and text exceed max message tokens'。
    """
    captured = {}

    class _LLM:
        async def call_json(self, system, user, **kwargs):
            captured["user"] = user
            return {
                "basic_info": {"name": "X", "company": ""},
                "feature_tree": [],
                "pricing": {"model": "免费", "tiers": []},
                "user_reviews": {"rating": 0, "total_reviews": 0, "sample_reviews": []},
                "recent_updates": [],
            }

    agent = CollectorAgent(llm=_LLM(), pipeline=None)
    # 400K 字符正文，远超 300K 阈值
    huge_text = "【来源: https://a.com】\n" + "正文一段" * 100000
    await agent._extract_profile(
        "X", huge_text, {"competitor_type": "核心竞品", "reason": "r"},
        ["https://a.com"], [],
    )
    # 实际喂给 LLM 的 user prompt 长度应受截断保护：≤ 300K + 头部 prefix(~500 字符)
    assert len(captured["user"]) < 301_000, (
        f"user prompt 长度 {len(captured['user'])} 超 300K，截断未生效"
    )


@pytest.mark.asyncio
async def test_extract_profile_does_not_truncate_short_text():
    """[bug1 prove-it] 短文本（<100K）不应被截断，避免误伤"""
    captured = {}

    class _LLM:
        async def call_json(self, system, user, **kwargs):
            captured["user"] = user
            return {
                "basic_info": {"name": "X", "company": ""},
                "feature_tree": [],
                "pricing": {"model": "免费", "tiers": []},
                "user_reviews": {"rating": 0, "total_reviews": 0, "sample_reviews": []},
                "recent_updates": [],
            }

    agent = CollectorAgent(llm=_LLM(), pipeline=None)
    short_text = "【来源: https://a.com】\n" + "短正文" * 1000  # ~3K 字符
    await agent._extract_profile(
        "X", short_text, {"competitor_type": "核心竞品", "reason": "r"},
        ["https://a.com"], [],
    )
    # 完整原文必须出现在 prompt 里
    assert short_text in captured["user"]


@pytest.mark.asyncio
async def test_extract_uses_labeled_text_and_binds_source_url():
    """_extract_profile 把 labeled_text 传给 LLM，LLM 填的 feature source_url 被保留。"""
    captured = {}

    class _LLM:
        async def call_json(self, system, user):
            captured["user"] = user
            return {
                "basic_info": {"name": "X", "company": ""},
                "feature_tree": [{"module": "M", "features": [
                    {"name": "f1", "description": "d", "source_url": "https://a.com"}
                ]}],
                "pricing": {"model": "免费", "tiers": []},
                "user_reviews": {"rating": 0, "total_reviews": 0, "sample_reviews": []},
                "recent_updates": [],
            }

    agent = CollectorAgent(llm=_LLM(), pipeline=None)
    profile = await agent._extract_profile(
        "X", "【来源: https://a.com】\n正文", {"competitor_type": "核心竞品", "reason": "r"},
        ["https://a.com"], [],
    )
    assert "【来源: https://a.com】" in captured["user"]
    assert profile.feature_tree[0].features[0].source_url == "https://a.com"


@pytest.mark.asyncio
async def test_collect_returns_goal_with_profiles():
    from src.agents.collector import CollectorAgent
    from src.schemas.input import CompetitorInput, CompetitorBasic

    class _LLM:
        async def call_json(self, system, user):
            if "goal_type" in system:
                return {"goal_type": "feature_iteration", "product_stage": "growing",
                        "focus_area": "协作功能", "output_expectation": "action"}
            return {"competitor_type": "核心竞品", "reason": "r"}

    class _Pipe:
        async def collect(self, name, category):
            return ("", [], [], "")

    agent = CollectorAgent(llm=_LLM(), pipeline=_Pipe())
    user_input = CompetitorInput(scenario="S1",
                                 our_product_name="MyProduct",
                                 competitors=[CompetitorBasic(name="XX")],
                                 analysis_context="分析协作功能")
    profiles, goal, _ = await agent.collect(user_input)
    assert goal.focus_area == "协作功能"
    assert len(profiles) == 1


@pytest.mark.asyncio
async def test_collect_returns_discovered_sources_with_urls():
    """spec v4：collector 返回的 discovered_sources 必须包含 profile 中的 data_sources URL。"""
    from src.agents.collector import CollectorAgent
    from src.schemas.input import CompetitorInput, CompetitorBasic

    mock_llm = MagicMock()
    mock_llm.call_json = AsyncMock(side_effect=[
        {"goal_type": "competitive_monitoring", "product_stage": "growing", "focus_area": "", "output_expectation": "action"},
        {"competitor_type": "核心竞品", "reason": "test"},
        {"basic_info": {"name": "TestProduct", "company": "TestCo"},
         "feature_tree": [], "pricing": {}, "user_reviews": {}, "recent_updates": []},
    ])
    mock_pipeline = MagicMock()
    mock_pipeline.collect = AsyncMock(return_value=(
        "正文内容" * 30,
        ["https://official.com/page1", "https://review.com/article1"],
        [{"step": "tavily"}],
        "【来源: https://official.com/page1】\n正文",
    ))
    agent = CollectorAgent(llm=mock_llm, pipeline=mock_pipeline)
    user_input = CompetitorInput(
        scenario="S1", our_product_name="MyProduct",
        competitors=[CompetitorBasic(name="TestProduct")], analysis_context="test",
    )
    profiles, goal, discovered_sources = await agent.collect(user_input)

    # discovered_sources 必须包含 URL（C1 修复验证）
    assert len(discovered_sources) > 0
    urls = [s["url"] for s in discovered_sources]
    assert "https://official.com/page1" in urls
    assert "https://review.com/article1" in urls
    # URL 不能为空字符串
    for s in discovered_sources:
        assert s["url"], f"discovered_sources URL 不应为空: {s}"
