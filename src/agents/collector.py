import asyncio
import logging
from datetime import datetime, timezone
from pydantic import ValidationError
from src.schemas.input import CompetitorInput, CompetitorBasic, AnalysisGoal
from src.schemas.profile import CompetitorProfile, Classification, BasicInfo, ProfileMetadata
from src.agents.prompts import COLLECTOR_GOAL_SYSTEM, COLLECTOR_CLASSIFY_SYSTEM, COLLECTOR_EXTRACT_SYSTEM

logger = logging.getLogger(__name__)

# 喂给 LLM 的 labeled_text 字符上限：100K 字符 ≈ 70K-100K Doubao token，
# Doubao-Seed-2.0-lite 输入上限 224K token，留 50%+ 安全垫防中文 BPE 计数偏差。
# 飞书 trace 实测 raw_content 拼起来 >150K 字符会触发 400 错误。
_EXTRACT_TEXT_MAX_CHARS = 100_000


class CollectorAgent:
    """采集 Agent：目标解析 → 竞品分类 → 差异化采集"""

    def __init__(self, llm, pipeline):
        self.llm = llm
        self.pipeline = pipeline

    def _build_placeholder_profile(self, comp: CompetitorBasic, classification: dict, trace: list[dict]) -> CompetitorProfile:
        """全空时构造占位 profile：不调 LLM，completeness 显式 0.0。"""
        return CompetitorProfile(
            classification=Classification(**classification),
            basic_info=BasicInfo(name=comp.name, company=comp.company or ""),
            metadata=ProfileMetadata(
                collected_at=datetime.now(timezone.utc).isoformat(),
                data_sources=[],
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

    async def classify_competitor(self, name: str, goal: AnalysisGoal) -> dict:
        """判断竞品类型"""
        prompt = f"竞品名称：{name}\n分析目标：{goal.goal_type}，关注领域：{goal.focus_area or '未指定'}"
        result = await self.llm.call_json(COLLECTOR_CLASSIFY_SYSTEM, prompt)
        # 校验必要字段
        if "competitor_type" not in result or "reason" not in result:
            logger.warning("[collector] classify_competitor 返回缺少字段, 重试: %s", result)
            result = await self.llm.call_json(COLLECTOR_CLASSIFY_SYSTEM, prompt)
            if "competitor_type" not in result or "reason" not in result:
                logger.error("[collector] classify_competitor 重试后仍缺少字段: %s", result)
                result.setdefault("competitor_type", "核心竞品")
                result.setdefault("reason", "无法判断，默认归类")
        return result

    @staticmethod
    def _normalize_raw(raw: dict, classification: dict, sources: list[str], pipeline_trace: list[dict]) -> dict:
        """规整 LLM 输出：补充 classification/metadata，兜底纠正常见结构偏差"""
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

        labeled_text 超 _EXTRACT_TEXT_MAX_CHARS 时硬截断（保头部），防 Doubao 输入超限。
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
            raw = self._normalize_raw(await self.llm.call_json(COLLECTOR_EXTRACT_SYSTEM, prompt),
                                      classification, sources, pipeline_trace)
            try:
                return CompetitorProfile(**raw)
            except ValidationError as e2:
                logger.error("[collector] _extract_profile 重试后仍然失败: %s, raw=%s", e2, raw)
                raise ValueError(f"Collector _extract_profile validation failed after retry: {e2}") from e2

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
        """采集单个竞品：分类 → 类别路由 → scenario 化管线采集 → 抽取/占位。"""
        classification = await self.classify_competitor(comp.name, goal)
        merged_text, sources, trace, labeled_text = await self.pipeline.collect(
            comp.name, scenario=scenario,
        )
        if not labeled_text.strip():
            logger.info("[collector] %s 全空, 产占位 profile", comp.name)
            return self._build_placeholder_profile(comp, classification, trace)
        profile = await self._extract_profile(comp.name, labeled_text, classification, sources, trace)
        logger.info("[collector] %s 采集完成, completeness=%.2f", comp.name, profile.metadata.completeness_score)
        return profile

    async def collect(self, user_input: CompetitorInput) -> list[CompetitorProfile]:
        """完整采集流程：目标解析 → 并行采集所有竞品（单竞品失败产占位，不拖垮全局）。"""
        goal = await self.parse_goal(user_input.analysis_context)
        scenario = getattr(user_input, "scenario", None)
        results = await asyncio.gather(
            *[self._collect_single(comp, goal, scenario=scenario) for comp in user_input.competitors],
            return_exceptions=True,
        )
        profiles: list[CompetitorProfile] = []
        for comp, r in zip(user_input.competitors, results):
            if isinstance(r, CompetitorProfile):
                profiles.append(r)
            else:
                logger.error("[collector] %s 采集彻底失败, 产占位: %s", comp.name, r)
                profiles.append(self._build_placeholder_profile(
                    comp, {"competitor_type": "核心竞品", "reason": "采集失败占位"},
                    trace=[{"step": "collect_failed", "error": str(r)}],
                ))
        return profiles, goal
