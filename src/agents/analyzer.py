import logging
from src.schemas.profile import CompetitorProfile
from src.schemas.analysis import CompetitiveAnalysis
from src.agents.prompts import ANALYZER_SYSTEM

logger = logging.getLogger(__name__)


class AnalyzerAgent:
    """分析 Agent：四维框架对比 + SWOT + 雷达评分"""

    def __init__(self, llm):
        self.llm = llm

    async def analyze(self, profiles: list[CompetitorProfile]) -> CompetitiveAnalysis:
        """对采集数据进行结构化分析"""
        logger.info("[analyzer] 开始分析 %d 个竞品", len(profiles))

        # 将 profiles 序列化为文本传给 LLM
        profiles_text = "\n\n".join([
            f"=== {p.basic_info.name} ===\n"
            f"分类: {p.classification.competitor_type}\n"
            f"基本信息: 公司={p.basic_info.company}, 版本={p.basic_info.version}, 平台={p.basic_info.platform}\n"
            f"功能模块: {[m.module for m in p.feature_tree]}\n"
            f"定价模式: {p.pricing.model}\n"
            f"用户评分: {p.user_reviews.rating} ({p.user_reviews.total_reviews}条评论)\n"
            f"好评: {p.user_reviews.positive_summary}\n"
            f"差评: {p.user_reviews.negative_summary}\n"
            f"近期更新: {[(u.title, u.summary) for u in p.recent_updates]}"
            for p in profiles
        ])

        prompt = f"请基于以下竞品数据进行四维度分析：\n\n{profiles_text}"
        result = await self.llm.call_json(ANALYZER_SYSTEM, prompt)

        analysis = CompetitiveAnalysis(**result)
        logger.info("[analyzer] 分析完成, 功能矩阵 %d 条, SWOT %d/%d/%d/%d",
                    len(analysis.feature_matrix),
                    len(analysis.swot.strengths), len(analysis.swot.weaknesses),
                    len(analysis.swot.opportunities), len(analysis.swot.threats))
        return analysis
