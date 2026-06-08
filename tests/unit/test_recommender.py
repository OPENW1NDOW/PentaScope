"""RecommenderAgent 单测。"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from src.agents.recommender import RecommenderAgent
from src.schemas.scenarios.s2 import CompetitorRecommendations
from src.tools.sources import SourceResult


@pytest.mark.asyncio
async def test_recommender_produces_recommendations():
    """recommender 调用搜索 + LLM 选 ≥3 个推荐"""
    mock_search = MagicMock()
    mock_search.search = AsyncMock(return_value=[
        SourceResult(url="https://feishu.cn", text="飞书：字节跳动旗下协作工具"),
        SourceResult(url="https://yuque.com", text="语雀：蚂蚁金服旗下文档平台"),
    ])

    mock_llm = MagicMock()
    mock_llm.call_json = AsyncMock(return_value={
        "recommended_competitors": [
            {"name": "飞书", "why_recommended": "行业头部协作工具，市占率领先", "confidence": "high"},
            {"name": "语雀", "why_recommended": "重要文档平台竞品，专注知识管理", "confidence": "medium"},
            {"name": "Notion", "why_recommended": "国际标杆产品，AI 化方向值得参考", "confidence": "high"},
        ],
        "selection_method": "hybrid",
        "selection_rationale": "基于行业 Top 5 搜索 + LLM 综合判断（市场覆盖+技术影响力）" * 1,
    })

    rec = RecommenderAgent(llm=mock_llm, search_source=mock_search)
    result = await rec.recommend(industry="知识管理 SaaS", context="找头部玩家")

    assert isinstance(result, CompetitorRecommendations)
    assert len(result.recommended_competitors) == 3
    assert result.user_provided_industry == "知识管理 SaaS"
    assert result.recommended_competitors[0].name == "飞书"
    # 验证搜索查询包含行业关键词
    assert "知识管理 SaaS" in mock_search.search.call_args.args[0]


@pytest.mark.asyncio
async def test_recommender_handles_empty_search_results():
    """搜索返回空时仍调 LLM（基于 LLM 内部知识）"""
    mock_search = MagicMock()
    mock_search.search = AsyncMock(return_value=[])

    mock_llm = MagicMock()
    mock_llm.call_json = AsyncMock(return_value={
        "recommended_competitors": [
            {"name": "A", "why_recommended": "头部玩家 A 占据主要市场份额", "confidence": "low"},
            {"name": "B", "why_recommended": "挑战者 B 增长速度领先", "confidence": "low"},
            {"name": "C", "why_recommended": "新兴 C 在小众场景突破", "confidence": "low"},
        ],
        "selection_method": "llm_inference",
        "selection_rationale": "无搜索结果，仅基于 LLM 内部知识推荐 + confidence 全 low 反映不确定性",
    })

    rec = RecommenderAgent(llm=mock_llm, search_source=mock_search)
    result = await rec.recommend(industry="某新兴赛道", context="探索可行性")

    assert len(result.recommended_competitors) == 3
    assert result.selection_method == "llm_inference"
    # 验证 LLM 仍被调用了
    mock_llm.call_json.assert_awaited_once()


@pytest.mark.asyncio
async def test_recommender_passes_user_known_competitors():
    """用户已知竞品列表透传到 prompt + recommendations"""
    mock_search = MagicMock()
    mock_search.search = AsyncMock(return_value=[])

    mock_llm = MagicMock()
    mock_llm.call_json = AsyncMock(return_value={
        "recommended_competitors": [
            {"name": "X", "why_recommended": "头部玩家 X 持续领跑市场份额", "confidence": "high"},
            {"name": "Y", "why_recommended": "重要 Y 战略价值高，值得关注", "confidence": "medium"},
            {"name": "Z", "why_recommended": "新兴 Z 增长迅猛，潜力较大", "confidence": "low"},
        ],
        "selection_method": "hybrid",
        "selection_rationale": "用户已提供 A/B 作参考，再补充 3 个相关玩家以扩大视野和定位面",
    })

    rec = RecommenderAgent(llm=mock_llm, search_source=mock_search)
    result = await rec.recommend(
        industry="测试行业",
        context="...",
        user_provided_competitors=["A", "B"],
    )

    assert result.user_provided_competitors == ["A", "B"]
    # prompt 含 user_provided 信息
    user_prompt = mock_llm.call_json.call_args.args[1]
    assert "A" in user_prompt and "B" in user_prompt
