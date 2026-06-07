import pytest
from unittest.mock import AsyncMock

from src.agents.recommender import RecommenderAgent
from src.schemas.scenarios.s2 import CompetitorRecommendations


@pytest.mark.asyncio
async def test_recommender_produces_top_n():
    """recommender 调用搜索 + LLM，产出 CompetitorRecommendations"""
    mock_search = AsyncMock()
    mock_search.search.return_value = [
        {"title": "飞书官网", "url": "https://feishu.cn", "snippet": "字节协作"},
        {"title": "语雀", "url": "https://yuque.com", "snippet": "蚂蚁知识库"},
        {"title": "Notion", "url": "https://notion.so", "snippet": "国际标杆"},
    ]
    mock_llm = AsyncMock()
    mock_llm.call_json.return_value = {
        "recommended_competitors": [
            {"name": "飞书", "company": "字节跳动", "why_recommended": "国内行业头部协作平台代表", "confidence": "high"},
            {"name": "语雀", "company": "蚂蚁集团", "why_recommended": "国内重要竞品文档玩家", "confidence": "medium"},
            {"name": "Notion", "company": "Notion Labs", "why_recommended": "国际标杆 all-in-one 产品", "confidence": "high"},
        ],
        "selection_rationale": "基于搜索 Top + LLM 综合判断行业玩家覆盖度与代表性",
    }

    rec = RecommenderAgent(llm=mock_llm, search_source=mock_search)
    result = await rec.recommend(industry="知识管理 SaaS", context="找头部玩家")

    assert isinstance(result, CompetitorRecommendations)
    assert result.user_provided_industry == "知识管理 SaaS"
    assert len(result.recommended_competitors) == 3
    assert result.recommended_competitors[0].name == "飞书"
    assert result.selection_method == "hybrid"


@pytest.mark.asyncio
async def test_recommender_excludes_user_provided():
    """user_provided_competitors 透传，并写入 CompetitorRecommendations.user_provided_competitors"""
    mock_search = AsyncMock()
    mock_search.search.return_value = []
    mock_llm = AsyncMock()
    mock_llm.call_json.return_value = {
        "recommended_competitors": [
            {"name": "Notion", "company": "", "why_recommended": "国际标杆 all-in-one 产品", "confidence": "high"},
            {"name": "Confluence", "company": "Atlassian", "why_recommended": "企业级老牌知识平台代表", "confidence": "medium"},
            {"name": "Coda", "company": "", "why_recommended": "新兴挑战者代表性文档产品", "confidence": "low"},
        ],
        "selection_rationale": "用户已有飞书/语雀两家，补充国际标杆 Notion 与挑战者 Coda 覆盖完整性",
    }

    rec = RecommenderAgent(llm=mock_llm, search_source=mock_search)
    result = await rec.recommend(
        industry="知识管理 SaaS",
        context="找头部玩家",
        user_provided_competitors=["飞书", "语雀"],
    )

    assert result.user_provided_competitors == ["飞书", "语雀"]
    assert len(result.recommended_competitors) == 3
