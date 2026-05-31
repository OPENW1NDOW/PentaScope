import logging
from datetime import datetime, timezone
from src.schemas.analysis import CompetitiveAnalysis
from src.schemas.report import FinalReport
from src.agents.prompts import WRITER_SYSTEM

logger = logging.getLogger(__name__)


class WriterAgent:
    """撰写 Agent：四段式执行摘要 + 时间分层行动建议"""

    def __init__(self, llm):
        self.llm = llm

    async def write(self, analysis: CompetitiveAnalysis, competitors: list[str]) -> FinalReport:
        """基于分析结果生成最终报告"""
        logger.info("[writer] 开始撰写报告, 竞品: %s", competitors)

        # 序列化分析数据
        analysis_text = (
            f"功能矩阵: {len(analysis.feature_matrix)} 条\n"
            f"定位分析: {len(analysis.positioning.per_competitor)} 个竞品\n"
            f"商业模式: {len(analysis.business_model.per_competitor)} 个竞品\n"
            f"运营策略: {len(analysis.operations.per_competitor)} 个竞品\n"
            f"用户情感: {analysis.user_sentiment.summary}\n"
            f"SWOT: 优势{len(analysis.swot.strengths)}/劣势{len(analysis.swot.weaknesses)}/机会{len(analysis.swot.opportunities)}/威胁{len(analysis.swot.threats)}\n"
        )

        prompt = f"请基于以下分析数据撰写竞品报告：\n\n竞品列表：{competitors}\n\n{analysis_text}"
        result = await self.llm.call_json(WRITER_SYSTEM, prompt)

        # 补充 metadata
        result.setdefault("metadata", {})
        result["metadata"]["competitors_analyzed"] = competitors
        result["metadata"]["generated_at"] = datetime.now(timezone.utc).isoformat()

        report = FinalReport(**result)
        logger.info("[writer] 报告撰写完成: %s", report.title)
        return report
