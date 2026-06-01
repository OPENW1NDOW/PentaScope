import json
import logging
from datetime import datetime, timezone
from pydantic import ValidationError
from src.schemas.analysis import CompetitiveAnalysis
from src.schemas.report import FinalReport
from src.agents.prompts import WRITER_SYSTEM

logger = logging.getLogger(__name__)


class WriterAgent:
    """撰写 Agent：四段式执行摘要 + 时间分层行动建议"""

    def __init__(self, llm):
        self.llm = llm

    @staticmethod
    def _normalize(result: dict, competitors: list[str]) -> dict:
        """规整 action_items 的 priority 枚举，补充 metadata"""
        allowed = ["高", "中", "低"]
        for layer in result.get("action_items", {}).values():
            if not isinstance(layer, list):
                continue
            for item in layer:
                if isinstance(item, dict) and "priority" in item:
                    p = str(item["priority"])
                    item["priority"] = p if p in allowed else next((a for a in allowed if a in p), "中")
        result.setdefault("metadata", {})
        result["metadata"]["competitors_analyzed"] = competitors
        result["metadata"]["generated_at"] = datetime.now(timezone.utc).isoformat()
        return result

    async def write(self, analysis: CompetitiveAnalysis, competitors: list[str]) -> FinalReport:
        """基于分析结果生成最终报告"""
        logger.info("[writer] 开始撰写报告, 竞品: %s", competitors)

        # 序列化完整分析数据
        analysis_data = analysis.model_dump()
        analysis_text = json.dumps(analysis_data, ensure_ascii=False, indent=2)
        if len(analysis_text) > 8000:
            analysis_text = analysis_text[:8000] + "\n...(数据已截断)"

        prompt = f"请基于以下分析数据撰写竞品报告：\n\n竞品列表：{competitors}\n\n分析数据：\n{analysis_text}"
        result = self._normalize(await self.llm.call_json(WRITER_SYSTEM, prompt), competitors)

        try:
            report = FinalReport(**result)
        except ValidationError as e:
            logger.warning("[writer] Pydantic 校验失败, 重试: %s", e)
            result = self._normalize(await self.llm.call_json(WRITER_SYSTEM, prompt), competitors)
            try:
                report = FinalReport(**result)
            except ValidationError as e2:
                logger.error("[writer] 重试后仍然失败: %s, raw=%s", e2, result)
                raise ValueError(f"Writer output validation failed after retry: {e2}") from e2

        logger.info("[writer] 报告撰写完成: %s", report.title)
        return report
