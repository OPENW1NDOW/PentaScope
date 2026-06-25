import asyncio
import json
import logging
from datetime import datetime, timezone
from pydantic import ValidationError
from src.schemas.input import CompetitorInput, CompetitorBasic, AnalysisGoal
from src.schemas.profile import CompetitorProfile, Classification, BasicInfo, ProfileMetadata
from src.agents.prompts import COLLECTOR_GOAL_SYSTEM, COLLECTOR_EXTRACT_SYSTEM

logger = logging.getLogger(__name__)

# 喂给 LLM 的 labeled_text 字符上限（适配 1M 上下文模型，留安全垫防 BPE 计数偏差）
_EXTRACT_TEXT_MAX_CHARS = 500_000


class CollectorAgent:
    """采集 Agent：目标解析 → 竞品分类 → 差异化采集"""

    def __init__(self, llm, pipeline):
        self.llm = llm
        self.pipeline = pipeline

    def _build_placeholder_profile(
        self, comp: CompetitorBasic, classification: dict, trace: list[dict],
        sources: list[str] | None = None,
    ) -> CompetitorProfile:
        """构造占位 profile：不调 LLM，completeness 显式 0.0。

        sources: pipeline 已采集的 URL 列表。LLM 抽取失败时传入，避免丢失已采集的 sources。
        """
        return CompetitorProfile(
            classification=Classification(**classification),
            basic_info=BasicInfo(name=comp.name, company=comp.company or ""),
            metadata=ProfileMetadata(
                collected_at=datetime.now(timezone.utc).isoformat(),
                data_sources=sources or [],
                completeness_score=0.0,
                pipeline_trace=trace,
            ),
        )

    async def parse_goal(self, context: str) -> AnalysisGoal:
        """从自然语言描述中解析分析目标"""
        logger.info("[collector] 解析分析目标: %s", context[:50])
        result = await self.llm.call_json(COLLECTOR_GOAL_SYSTEM, f"用户输入：{context}")
        try:
            return AnalysisGoal(**result)
        except ValidationError as e:
            logger.warning("[collector] parse_goal 校验失败, 重试: %s", e)
            result = await self.llm.call_json(COLLECTOR_GOAL_SYSTEM, f"用户输入：{context}")
            try:
                return AnalysisGoal(**result)
            except ValidationError as e2:
                logger.error("[collector] parse_goal 重试后仍然失败: %s, raw=%s", e2, result)
                raise ValueError(f"Collector parse_goal validation failed after retry: {e2}") from e2

    _DEFAULT_CLASSIFICATION = {"competitor_type": "核心竞品", "reason": "默认分类（专源路由已移除）"}

    @staticmethod
    def _normalize_raw(raw: dict, classification: dict, sources: list[str], pipeline_trace: list[dict]) -> dict:
        """规整 LLM 输出：补充 classification/metadata，兜底纠正常见结构偏差"""
        # [#防御] LLM 偶发输出 JSON null / 非 dict（call_json 可能返回 None），
        # 此处先规整成空 dict，避免 raw.get 抛 AttributeError 被 _collect_single 吞成占位。
        if not isinstance(raw, dict):
            raw = {}
        # [#13 防御] LLM 偶发把 user_reviews/pricing 填成非 dict（字符串/列表/null），
        # 此时 .get 会抛 AttributeError 被 _collect_single 吞成占位，丢失已采集正文。
        # 此处先规整成空 dict，保留其余字段继续抽取。
        if not isinstance(raw.get("user_reviews"), dict):
            raw["user_reviews"] = {}
        if not isinstance(raw.get("pricing"), dict):
            raw["pricing"] = {}
        # sample_reviews 偶尔被 LLM 填成字符串数组，转成 SampleReview 结构
        reviews = raw.get("user_reviews", {}).get("sample_reviews")
        if isinstance(reviews, list):
            raw["user_reviews"]["sample_reviews"] = [
                {"content": r, "rating": 3} if isinstance(r, str) else r
                for r in reviews
            ]
        raw["classification"] = classification
        raw["metadata"] = {
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "data_sources": sources,
            "completeness_score": CollectorAgent._calc_completeness_static(raw),
            "pipeline_trace": pipeline_trace,
        }
        return raw

    async def _extract_profile(self, name: str, text: str, classification: dict,
                               sources: list[str], pipeline_trace: list[dict]) -> CompetitorProfile:
        """从带来源标记的文本中抽取结构化竞品画像。

        labeled_text 超 _EXTRACT_TEXT_MAX_CHARS 时硬截断（保头部），防 LLM 输入超限。
        """
        if len(text) > _EXTRACT_TEXT_MAX_CHARS:
            logger.warning(
                "[collector] %s labeled_text %d 字符超 %d 上限，截断头部以避免 LLM 输入超限",
                name, len(text), _EXTRACT_TEXT_MAX_CHARS,
            )
            text = text[:_EXTRACT_TEXT_MAX_CHARS]
        prompt = f"竞品名称：{name}\n\n网页文本内容（每段前有【来源: URL】标记）：\n{text}"
        raw = self._normalize_raw(await self.llm.call_json(COLLECTOR_EXTRACT_SYSTEM, prompt),
                                  classification, sources, pipeline_trace)
        try:
            return CompetitorProfile(**raw)
        except ValidationError as e:
            logger.warning("[collector] _extract_profile 校验失败, 重试: %s", e)
            error_summary = self._serialize_validation_error(e)
            retry_prompt = f"{prompt}\n\n【上次校验失败，请逐条修复】\n{error_summary}"
            raw = self._normalize_raw(await self.llm.call_json(COLLECTOR_EXTRACT_SYSTEM, retry_prompt),
                                      classification, sources, pipeline_trace)
            try:
                return CompetitorProfile(**raw)
            except ValidationError as e2:
                logger.error("[collector] _extract_profile 重试后仍然失败: %s, raw=%s", e2, raw)
                raise ValueError(f"Collector _extract_profile validation failed after retry: {e2}") from e2

    @staticmethod
    def _serialize_validation_error(e: ValidationError, max_chars: int = 1500) -> str:
        errs = e.errors()[:5]
        simplified = [{"loc": list(err["loc"]), "msg": err["msg"], "type": err["type"]} for err in errs]
        text = json.dumps(simplified, ensure_ascii=False)
        return text[:max_chars]

    @staticmethod
    def _calc_completeness_static(data: dict) -> float:
        """计算数据完整度"""
        score = 1.0
        if not data.get("feature_tree"):
            score -= 0.3
        if not data.get("pricing", {}).get("model") or data.get("pricing", {}).get("model") == "unknown":
            score -= 0.15
        if not data.get("user_reviews", {}).get("rating"):
            score -= 0.15
        if not data.get("recent_updates"):
            score -= 0.1
        return max(0, round(score, 2))

    async def _collect_single(
        self, comp: CompetitorBasic, goal: AnalysisGoal, scenario: str | None = None,
    ) -> CompetitorProfile:
        """采集单个竞品：scenario 化管线搜索 → LLM 抽取结构化 profile → 占位兜底。"""
        classification = self._DEFAULT_CLASSIFICATION
        merged_text, sources, trace, labeled_text = await self.pipeline.collect(
            comp.name, scenario=scenario,
        )
        if not labeled_text.strip():
            logger.info("[collector] %s 全空, 产占位 profile", comp.name)
            return self._build_placeholder_profile(comp, classification, trace)
        try:
            profile = await self._extract_profile(comp.name, labeled_text, classification, sources, trace)
        except Exception as e:
            logger.warning("[collector] %s LLM 抽取失败, 保留 pipeline sources 产占位: %s", comp.name, e)
            return self._build_placeholder_profile(comp, classification, trace, sources=sources)
        logger.info("[collector] %s 采集完成, completeness=%.2f", comp.name, profile.metadata.completeness_score)
        return profile

    async def collect(self, user_input: CompetitorInput) -> tuple[list, object, list[dict]]:
        """完整采集流程：目标解析 → 并行采集所有竞品（单竞品失败产占位，不拖垮全局）。

        返回 (profiles, goal, discovered_sources)。
        discovered_sources 供 inspector evidence rubric 使用（spec v4 cycle3/C3）。
        """
        goal = await self.parse_goal(user_input.analysis_context)
        scenario = getattr(user_input, "scenario", None)
        results = await asyncio.gather(
            *[self._collect_single(comp, goal, scenario=scenario) for comp in user_input.competitors],
            return_exceptions=True,
        )
        profiles = []
        all_sources: list[dict] = []
        auth_failed = False
        for comp, r in zip(user_input.competitors, results):
            if isinstance(r, CompetitorProfile):
                profiles.append(r)
                # [#13] 检测 TavilyAuthError：pipeline_trace 会记录每个 query 的 error
                for entry in getattr(r.metadata, "pipeline_trace", []) or []:
                    err = str(entry.get("error", "")) if isinstance(entry, dict) else ""
                    if "TavilyAuthError" in err:
                        auth_failed = True
            else:
                logger.error("[collector] %s 采集彻底失败, 产占位: %s", comp.name, r)
                profiles.append(self._build_placeholder_profile(
                    comp, {"competitor_type": "核心竞品", "reason": "采集失败占位"},
                    trace=[{"step": "collect_failed", "error": str(r)}],
                ))
        # [#13] key 配错/失效时给明确信号，避免「全占位报告无报错」难定位
        if auth_failed:
            logger.error(
                "[collector] 检测到 Tavily 鉴权失败（TAVILY_API_KEY 错误/失效），"
                "所有竞品采集将走占位降级。请检查 .env 的 TAVILY_API_KEY。"
            )
        # 收集所有搜索源 URL（ProfileMetadata.data_sources 是 list[str]）
        for profile in profiles:
            for url in getattr(profile.metadata, "data_sources", []):
                if isinstance(url, str) and url:
                    all_sources.append({"url": url, "title": "", "snippet": ""})
        return profiles, goal, all_sources
