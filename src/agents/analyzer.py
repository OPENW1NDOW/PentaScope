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

        # 序列化完整 profile 数据
        import json
        profiles_data = [p.model_dump() for p in profiles]
        profiles_text = json.dumps(profiles_data, ensure_ascii=False, indent=2)
        if len(profiles_text) > 12000:
            profiles_text = profiles_text[:12000] + "\n...(数据已截断)"

        prompt = f"请基于以下竞品数据进行四维度分析：\n\n{profiles_text}"
        result = await self.llm.call_json(ANALYZER_SYSTEM, prompt)

        analysis = CompetitiveAnalysis(**result)
        logger.info("[analyzer] 分析完成, 功能矩阵 %d 条, SWOT %d/%d/%d/%d",
                    len(analysis.feature_matrix),
                    len(analysis.swot.strengths), len(analysis.swot.weaknesses),
                    len(analysis.swot.opportunities), len(analysis.swot.threats))
        return analysis
