import json
import logging
from pydantic import ValidationError
from src.schemas.profile import CompetitorProfile
from src.schemas.analysis import CompetitiveAnalysis
from src.agents.prompts import ANALYZER_SYSTEM

logger = logging.getLogger(__name__)


class AnalyzerAgent:
    """分析 Agent：四维框架对比 + SWOT + 雷达评分"""

    def __init__(self, llm):
        self.llm = llm

    @staticmethod
    def _coerce_enum(value: str, allowed: list[str], default: str) -> str:
        """把 LLM 填的枚举值规整到合法集合：精确→包含匹配→默认"""
        if value in allowed:
            return value
        for a in allowed:
            if a in value:  # LLM 常加主语，如 "小米领先" → "领先"
                return a
        return default

    @classmethod
    def _normalize(cls, result: dict) -> dict:
        """规整 LLM 输出中的 Literal 枚举字段，避免主语污染导致校验失败"""
        for entry in result.get("feature_matrix", []):
            if not isinstance(entry, dict):
                continue
            if "gap_level" in entry:
                entry["gap_level"] = cls._coerce_enum(
                    str(entry["gap_level"]), ["领先", "持平", "落后", "差异化"], "持平"
                )
            if "our_product" in entry:
                entry["our_product"] = cls._coerce_enum(
                    str(entry["our_product"]), ["有", "无", "计划中", "不适用"], "无"
                )
            comp = entry.get("competitors")
            if isinstance(comp, dict):
                entry["competitors"] = {
                    k: cls._coerce_enum(str(v), ["有", "无", "部分支持"], "无")
                    for k, v in comp.items()
                }
        for key in ("strengths", "weaknesses", "opportunities", "threats"):
            for item in result.get("swot", {}).get(key, []):
                if isinstance(item, dict) and "dimension" in item:
                    item["dimension"] = cls._coerce_enum(
                        str(item["dimension"]),
                        ["positioning", "feature", "business", "operations"], "feature"
                    )
        return result

    @staticmethod
    def _backfill_source_urls(result: dict, profiles: list) -> dict:
        """维度级 source_urls 兜底：LLM 漏填则用所有 profile 的 data_sources 回填。"""
        all_urls = sorted({
            u for p in profiles
            for u in (p.metadata.data_sources if hasattr(p, "metadata") else [])
        })
        if not all_urls:
            return result
        for dim_key in ("positioning", "business_model", "operations", "user_sentiment"):
            dim = result.get(dim_key)
            if isinstance(dim, dict) and not dim.get("source_urls"):
                dim["source_urls"] = list(all_urls)
        for entry in result.get("feature_matrix", []):
            if isinstance(entry, dict) and not entry.get("source_urls"):
                entry["source_urls"] = list(all_urls)
        return result

    async def analyze(self, profiles: list[CompetitorProfile]) -> CompetitiveAnalysis:
        """对采集数据进行结构化分析"""
        logger.info("[analyzer] 开始分析 %d 个竞品", len(profiles))

        # 序列化完整 profile 数据
        profiles_data = [p.model_dump() for p in profiles]
        profiles_text = json.dumps(profiles_data, ensure_ascii=False, indent=2)
        if len(profiles_text) > 12000:
            profiles_text = profiles_text[:12000] + "\n...(数据已截断)"

        prompt = f"请基于以下竞品数据进行四维度分析：\n\n{profiles_text}"
        result = self._backfill_source_urls(
            self._normalize(await self.llm.call_json(ANALYZER_SYSTEM, prompt)),
            profiles,
        )

        try:
            analysis = CompetitiveAnalysis(**result)
        except ValidationError as e:
            logger.warning("[analyzer] Pydantic 校验失败, 重试: %s", e)
            result = self._backfill_source_urls(
                self._normalize(await self.llm.call_json(ANALYZER_SYSTEM, prompt)),
                profiles,
            )
            try:
                analysis = CompetitiveAnalysis(**result)
            except ValidationError as e2:
                logger.error("[analyzer] 重试后仍然失败: %s, raw=%s", e2, result)
                raise ValueError(f"Analyzer output validation failed after retry: {e2}") from e2

        logger.info("[analyzer] 分析完成, 功能矩阵 %d 条, SWOT %d/%d/%d/%d",
                    len(analysis.feature_matrix),
                    len(analysis.swot.strengths), len(analysis.swot.weaknesses),
                    len(analysis.swot.opportunities), len(analysis.swot.threats))
        return analysis
