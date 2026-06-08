"""S2 市场进入场景专用 RecommenderAgent。

职责：根据用户提供的 industry + analysis_context（+ 可选用户已知竞品），
通过搜索 + LLM 推理产出 CompetitorRecommendations（recommended_competitors ≥3 条）。

在 graph 中作为 conditional_entry_point 的 S2 路径首节点，先于 collector。
"""
import logging
from typing import Optional

from src.agents.prompts import RECOMMENDER_SYSTEM
from src.schemas.scenarios.s2 import CompetitorRecommendations, RecommendedCompetitor

logger = logging.getLogger(__name__)


class RecommenderAgent:
    """S2 推荐 agent。"""

    def __init__(self, llm, search_source):
        self.llm = llm
        self.search_source = search_source

    async def recommend(
        self,
        *,
        industry: str,
        context: str,
        user_provided_competitors: Optional[list[str]] = None,
    ) -> CompetitorRecommendations:
        """推荐 Top 3-5 玩家。

        步骤：
        1. 搜索行业头部玩家（Tavily）
        2. LLM 综合搜索结果 + 用户上下文产出 ≥3 条推荐
        3. 实例化 CompetitorRecommendations（让 schema 校验把关 min_length=3）

        失败语义：搜索为空时仍会调 LLM（让 LLM 基于自身知识产出）；
        LLM 漏字段或不足 3 条时 ValidationError 直接抛给 graph 层。
        """
        user_provided = user_provided_competitors or []
        logger.info(
            "[recommender] 开始推荐 Top 玩家, industry=%s, user_known=%d",
            industry,
            len(user_provided),
        )

        # 步骤 1：搜索行业头部
        search_query = f"{industry} 头部玩家 头部企业 行业排名"
        try:
            search_results = await self.search_source.search(search_query)
        except Exception as e:
            logger.warning("[recommender] 搜索失败，仅靠 LLM 内部知识: %s", e)
            search_results = []
        logger.info("[recommender] 搜索得 %d 条结果", len(search_results))

        # 步骤 2：LLM 选 ≥3 个最相关玩家
        search_snippets = "\n".join(
            f"- {r.url}: {r.text[:200]}"
            for r in search_results[:10]
        ) or "（无搜索结果，请基于公开知识推荐）"

        user_prompt = (
            f"行业：{industry}\n"
            f"用户分析意图：{context}\n"
            f"用户已知竞品：{user_provided or '无'}\n"
            f"搜索结果（Top）：\n{search_snippets}"
        )

        result = await self.llm.call_json(RECOMMENDER_SYSTEM, user_prompt)

        # 步骤 3：实例化 schema（min_length=3 由 Pydantic 把关）
        rec = CompetitorRecommendations(
            user_provided_industry=industry,
            user_provided_competitors=user_provided,
            recommended_competitors=[
                RecommendedCompetitor(**item)
                for item in result.get("recommended_competitors", [])
            ],
            selection_method=result.get("selection_method", "hybrid"),
            selection_rationale=result.get(
                "selection_rationale",
                "基于行业搜索 Top 5 玩家加 LLM 综合判断（兜底说明）",
            ),
        )
        logger.info(
            "[recommender] 推荐完成: %d 条",
            len(rec.recommended_competitors),
        )
        return rec
