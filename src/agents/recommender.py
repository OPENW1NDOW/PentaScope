import logging
from typing import Optional

from src.schemas.scenarios.s2 import CompetitorRecommendations, RecommendedCompetitor
from src.agents.prompts import RECOMMENDER_SYSTEM

logger = logging.getLogger(__name__)


class RecommenderAgent:
    """S2 专用：根据 industry 推荐 Top 玩家（搜索 + LLM 选）"""

    def __init__(self, llm, search_source):
        self.llm = llm
        self.search_source = search_source

    async def recommend(
        self,
        industry: str,
        context: str,
        user_provided_competitors: Optional[list[str]] = None,
    ) -> CompetitorRecommendations:
        logger.info("[recommender] 推荐 Top 玩家, industry=%s", industry)

        search_results = await self.search_source.search(
            f"{industry} 头部玩家 头部企业 2026"
        )

        prompt = (
            f"行业：{industry}\n"
            f"用户意图：{context}\n"
            f"用户已提供竞品：{user_provided_competitors or '无'}\n"
            f"搜索结果（Top）：\n"
            + "\n".join(
                f"- {r.get('title', '')}: {r.get('snippet', '')[:200]}"
                for r in search_results[:10]
            )
        )
        result = await self.llm.call_json(RECOMMENDER_SYSTEM, prompt)

        return CompetitorRecommendations(
            user_provided_industry=industry,
            user_provided_competitors=user_provided_competitors or [],
            recommended_competitors=[
                RecommendedCompetitor(**c) for c in result["recommended_competitors"]
            ],
            selection_method="hybrid",
            selection_rationale=result.get(
                "selection_rationale",
                "基于搜索 Top 与 LLM 综合判断行业玩家覆盖度",
            ),
        )
