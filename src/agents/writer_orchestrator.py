"""WriterOrchestrator — 4 阶段编排（v3 spec Task 21.1+21.2 部分）。

阶段 3-C1 范围：骨架 + Phase 1 outline。Phase 2/3/4 由 C3-C5 后续 task 实现。
"""
import asyncio
import json
import logging
from typing import Any, Optional

from pydantic import ValidationError

from src.agents.prompts.writer import WRITER_OUTLINE_PROMPTS
from src.schemas.input import ScenarioInput
from src.schemas.profile import CompetitorProfile
from src.schemas.report import BaseReport
from src.tools.llm_client import LLMClient
from src.utils.config import settings

logger = logging.getLogger(__name__)


def collect_profile_urls(profile: CompetitorProfile) -> set[str]:
    """[v3-R01] 从 3 个真实来源收集 URL：metadata.data_sources / recent_updates / sample_reviews。

    严格仅取这 3 处，不从 basic_info 等其他字段拼凑（避免幻觉与字段误用）。
    """
    urls: set[str] = set()
    for url in profile.metadata.data_sources or []:
        if url:
            urls.add(url)
    for ru in profile.recent_updates:
        if ru.source_url:
            urls.add(ru.source_url)
    for sr in profile.user_reviews.sample_reviews:
        if sr.source_url:
            urls.add(sr.source_url)
    return urls


class WriterOrchestrator:
    """Writer 4 阶段编排器（C1 仅实现 Phase 1，后续 phase 由 C3-C5 接续）。"""

    def __init__(self, llm: LLMClient):
        self.llm = llm
        self._call_counter = 0  # M2 熔断计数
        # [v3-R18] phase 3 并发限速（C1 暂未用，提前创建供 C4 使用）
        self._narrative_sem = asyncio.Semaphore(settings.WRITER_NARRATIVE_CONCURRENCY)

    async def write(
        self,
        *,
        scenario_input: ScenarioInput,
        analysis: Any,
        profiles: list[CompetitorProfile],
        analysis_goal: Any = None,
        competitor_recommendations: Any = None,
        prior_report_data: Optional[dict] = None,
        trace_id: str = "",
    ) -> BaseReport:
        """4 阶段编排入口。C1 在 phase 1 完成后 raise NotImplementedError。"""
        self._call_counter = 0
        scenario = scenario_input.scenario
        logger.info("[writer] 开始 4 阶段编排, scenario=%s, trace_id=%s", scenario, trace_id)

        competitor_names: list[str] = [c.name for c in scenario_input.competitors]
        # [v3-R26] 保留结构信息（model_dump），不只丢 names
        competitor_basics: list[dict] = [
            c.model_dump(exclude_none=True) for c in scenario_input.competitors
        ]
        our_product_brief: dict = {
            "name": scenario_input.our_product_name or "",
            "brief": scenario_input.our_product_brief or "",
            "industry": scenario_input.industry or "",
        }
        # [v3-R01] 用 collect_profile_urls，不是 p.source_urls
        discovered_urls: list[str] = sorted(
            {u for p in profiles for u in collect_profile_urls(p)}
        )
        if not discovered_urls:
            raise RuntimeError(
                "writer phase 4: profiles 中收集到 0 个 URL，无法构造可溯源报告。"
                "建议 graph 回 collector 重新采集。"
            )

        # outline 留给 phase 2-4 使用；C1 在 phase 1 后即终止
        await self._phase1_outline(
            scenario,
            scenario_input,
            analysis,
            profiles,
            competitor_names,
            competitor_basics,
            our_product_brief,
            discovered_urls,
        )
        logger.info("[writer] phase 1 完成, 进入 phase 2-4（待实现）")

        # 触达占位：C3-C5 task 接续实现
        raise NotImplementedError("phase 2-4 待 Task 21.3-21.5 实现")

    async def _llm_call_with_quota(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        max_tokens: int | None = None,
    ) -> dict:
        """[v3-R04] 所有 LLM 调用必须走这里（含 _call_with_validation 重试），统一熔断。"""
        self._call_counter += 1
        if self._call_counter > settings.WRITER_MAX_LLM_CALLS:
            raise RuntimeError(
                f"writer LLM 调用超限 {self._call_counter} 次"
                f"（上限 {settings.WRITER_MAX_LLM_CALLS}），疑似无限重试"
            )
        return await self.llm.call_json(system_prompt, user_prompt, max_tokens=max_tokens)

    async def _call_with_validation(
        self,
        system_prompt: str,
        user_prompt: str,
        schema_cls: type,
        *,
        max_retries: int = 1,
        max_tokens: int = 4096,
    ):
        """LLM 调用 + Pydantic 校验，校验失败时把错误回灌给 LLM 重试一次。

        [v3-R04] 重试也走 _llm_call_with_quota，绕开熔断会让最坏情况无限。
        """
        for attempt in range(max_retries + 1):
            raw = await self._llm_call_with_quota(
                system_prompt, user_prompt, max_tokens=max_tokens
            )
            try:
                return schema_cls(**raw)
            except ValidationError as e:
                if attempt >= max_retries:
                    raise
                error_summary = self._serialize_validation_error(e, max_chars=1500)
                user_prompt = (
                    f"{user_prompt}\n\n【上次校验失败，请修复】\n{error_summary}"
                )

    @staticmethod
    def _serialize_validation_error(e: ValidationError, max_chars: int = 1500) -> str:
        """ValidationError → 短 JSON。仅前 5 条 + 三字段，最终截断防 token 爆炸。"""
        errs = e.errors()[:5]
        simplified = [
            {"loc": list(err["loc"]), "msg": err["msg"], "type": err["type"]}
            for err in errs
        ]
        text = json.dumps(simplified, ensure_ascii=False)
        return text[:max_chars]

    async def _phase1_outline(
        self,
        scenario: str,
        scenario_input: ScenarioInput,
        analysis: Any,
        profiles: list[CompetitorProfile],
        competitor_names: list[str],
        competitor_basics: list[dict],
        our_product_brief: dict,
        discovered_urls: list[str],
    ) -> dict:
        """Phase 1：一次 LLM 调用产出 BaseReport 全部非 payload/sections/swot 字段。

        不在此处实例化 Pydantic 校验（留给 phase 4 BaseReport 实例化时统一报错）。
        不做 retry（重试由 phase 4 BaseReport 失败 + graph writer 重试承接）。
        """
        # Profiles 摘要（控制 token；不灌完整 model_dump）
        profile_summaries: list[dict] = []
        for p in profiles:
            profile_summaries.append(
                {
                    "name": p.basic_info.name,
                    "company": p.basic_info.company,
                    "version": p.basic_info.version,
                    "platform": p.basic_info.platform,
                    "classification": p.classification.competitor_type,
                    "feature_modules": [ft.module for ft in p.feature_tree],
                    "user_rating": p.user_reviews.rating,
                    "total_reviews": p.user_reviews.total_reviews,
                    "completeness_score": p.metadata.completeness_score,
                }
            )

        # Analysis 摘要：截断到 ~5000 字符
        try:
            analysis_json = analysis.model_dump_json()
        except AttributeError:
            analysis_json = json.dumps(analysis, ensure_ascii=False, default=str)
        if len(analysis_json) > 5000:
            analysis_json = analysis_json[:5000] + "...[truncated]"

        sections = [
            ("=== 场景 ===", scenario),
            ("=== 我方产品 ===", our_product_brief),
            ("=== 竞品列表 ===", competitor_basics),
            ("=== 竞品名（便于引用） ===", competitor_names),
            ("=== 分析目标 ===", scenario_input.analysis_context),
            ("=== Profiles 摘要 ===", profile_summaries),
            ("=== Analysis 摘要 ===", analysis_json),
            ("=== 可用溯源 URL ===", discovered_urls),
        ]
        parts: list[str] = []
        for label, value in sections:
            if isinstance(value, str):
                parts.append(f"{label}\n{value}")
            else:
                parts.append(f"{label}\n{json.dumps(value, ensure_ascii=False, indent=2)}")
        user_prompt = "\n\n".join(parts)

        system_prompt = WRITER_OUTLINE_PROMPTS[scenario]
        outline = await self._llm_call_with_quota(
            system_prompt, user_prompt, max_tokens=4096
        )
        title_preview = (outline.get("title") or "(no title)")[:30] if isinstance(outline, dict) else "(no title)"
        logger.info("[writer] phase 1 outline 完成: %s", title_preview)
        return outline
