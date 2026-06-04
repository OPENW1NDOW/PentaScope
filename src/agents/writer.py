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
    def _collect_analysis_urls(analysis) -> dict:
        """收集 analysis 各维度的 source_urls，返回 {dimension_key: [urls]}。"""
        return {
            "positioning": list(analysis.positioning.source_urls),
            "business_model": list(analysis.business_model.source_urls),
            "operations": list(analysis.operations.source_urls),
            "user_sentiment": list(analysis.user_sentiment.source_urls),
            "feature_matrix": sorted({u for e in analysis.feature_matrix for u in e.source_urls}),
            "swot": sorted({
                u for key in ("strengths", "weaknesses", "opportunities", "threats")
                for entry in getattr(analysis.swot, key)
                for u in entry.source_urls
            }),
        }

    @classmethod
    def _fill_section_source_refs(cls, report, analysis) -> None:
        """按 section.dimension 下沉 source_refs；过滤幻觉 URL（原地修改）。"""
        dim_urls = cls._collect_analysis_urls(analysis)
        all_urls = sorted({u for urls in dim_urls.values() for u in urls})
        pool = set(all_urls)
        for sec in report.sections:
            candidate = list(all_urls) if sec.dimension == "overview" else list(dim_urls.get(sec.dimension, []))
            if sec.source_refs:
                # LLM 已填：只保留在 analysis URL 池里的，过滤幻觉；全过滤掉则回退机械下沉
                filtered = [u for u in sec.source_refs if u in pool]
                sec.source_refs = filtered or candidate
            else:
                sec.source_refs = candidate
        for layer in (report.action_items.immediate, report.action_items.short_term,
                      report.action_items.long_term):
            for item in layer:
                item.source_urls = [u for u in item.source_urls if u in pool]

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
        """基于分析结果生成最终报告（结构化字段由代码透传，不赌 LLM）"""
        logger.info("[writer] 开始撰写报告, 竞品: %s", competitors)

        analysis_data = analysis.model_dump()
        analysis_text = json.dumps(analysis_data, ensure_ascii=False, indent=2)

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

        # 结构化产物由代码直接透传，100% 不丢（不依赖 LLM 输出）
        report.swot = analysis.swot
        report.radar_scores = analysis.radar_scores
        report.feature_matrix = analysis.feature_matrix

        # 按 dimension 下沉 source_refs，过滤幻觉 URL
        self._fill_section_source_refs(report, analysis)

        logger.info("[writer] 报告撰写完成: %s", report.title)
        return report
