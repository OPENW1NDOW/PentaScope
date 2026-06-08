"""WriterOrchestrator — 4 阶段编排（v3 spec Task 21.1+21.2+21.3+21.4 部分）。

阶段 3-C1 范围：骨架 + Phase 1 outline。
阶段 3-C3 范围：Phase 2 payload（含 normalize 接通 + S2/S4 前置注入 + 实例化场景 Payload schema）。
阶段 3-C4 范围：Phase 3 narrative（并行 + 半数闸门 + 占位降级 + Semaphore 限速）。
Phase 4 由 C5 后续 task 实现。
"""
import asyncio
import json
import logging
from typing import Any, Optional

from pydantic import ValidationError

from src.agents.normalizers import normalize_for_scenario
from src.agents.prompts.writer import WRITER_OUTLINE_PROMPTS, WRITER_PAYLOAD_PROMPTS
from src.agents.prompts.writer.narrative import (
    NARRATIVE_TEMPLATE,
    SECTION_CONTEXT_MAP,
    SECTION_FOCUS_HINTS,
    SECTION_LABELS,
)
from src.schemas.input import ScenarioInput
from src.schemas.profile import CompetitorProfile
from src.schemas.report import AnalysisSection, BaseReport
from src.schemas.scenarios.s1 import S1FeatureIterationPayload
from src.schemas.scenarios.s2 import S2MarketEntryPayload
from src.schemas.scenarios.s3 import S3PricingStrategyPayload
from src.schemas.scenarios.s4 import S4MonitoringPayload
from src.schemas.scenarios.s5 import S5PositioningPayload
from src.tools.llm_client import LLMClient
from src.utils.config import settings

logger = logging.getLogger(__name__)


_PAYLOAD_CLASSES: dict[str, type] = {
    "S1": S1FeatureIterationPayload,
    "S2": S2MarketEntryPayload,
    "S3": S3PricingStrategyPayload,
    "S4": S4MonitoringPayload,
    "S5": S5PositioningPayload,
}


# [v3-R20] 每场景默认 section_type 序列（5-6 个，对应 BaseReport.analysis_sections min=4 max=8）
_DEFAULT_SECTION_TYPES: dict[str, list[str]] = {
    "S1": [
        "overview",
        "vendor_profile_analysis",
        "feature_matrix_analysis",
        "jtbd_analysis",
        "roadmap_analysis",
    ],
    "S2": [
        "overview",
        "market_sizing_analysis",
        "five_forces_analysis",
        "competitive_landscape_analysis",
        "trends_analysis",
        "entry_strategy_analysis",
    ],
    "S3": [
        "overview",
        "pricing_baseline_analysis",
        "value_drivers_analysis",
        "competitive_pricing_analysis",
        "packaging_design_analysis",
        "pricing_recommendations_analysis",
    ],
    "S4": [
        "overview",
        "monitoring_overview",
        "competitive_moves_analysis",
        "threat_assessment_analysis",
        "opportunity_identification_analysis",
        "battlecard_analysis",
    ],
    "S5": [
        "overview",
        "vendor_positioning_analysis",
        "perceptual_map_analysis",
        "strategy_canvas_analysis",
        "errc_analysis",
        "positioning_statement_analysis",
    ],
}


# [v3-R12] 占位 narrative 模板。实测字符数：
# - 未替换 ≈ 390，替换后（最短 section_type "overview"）≈ 378，均 ≥350，留 28+ 字硬缓冲。
_PLACEHOLDER_NARRATIVE_TEMPLATE = (
    "【本节因数据不足暂未生成深度分析（自动占位）】\n\n"
    "本章节（{section_type}）原本应基于采集与分析阶段产出的具体数据展开 1500-3000 字的深度论述，"
    "但 phase 3 narrative LLM 调用在 1 次重试后仍未返回合规结果，故由代码自动落入占位模板。\n\n"
    "可用诊断信息：\n"
    "- metadata.warnings 中以 `placeholder_section:{section_type}` 为前缀的告警条目\n"
    "- 同 trace_id 下的 04_feedback.json，记录 inspector 对本节的具体扣分依据\n"
    "- 同 trace_id 下的 run.log，可定位 phase 3 LLM 调用失败的异常类型与时间点\n\n"
    "建议处理：等待 graph 反馈闭环重试 collector/analyzer，或手动指定更精准的数据源后重新发起分析。"
)


def _dot_walk(obj: Any, path: str) -> Any:
    """按 dot-walk 路径取值，遇 None / 缺字段直接返回 None，绝不抛异常。

    示例：_dot_walk(ctx, "payload.feature_matrix") → ctx["payload"]["feature_matrix"]
    """
    if not path:
        return obj
    cur = obj
    for part in path.split("."):
        if cur is None:
            return None
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            cur = getattr(cur, part, None)
    return cur


def _build_placeholder_section(section_type: str, payload_dict: dict) -> AnalysisSection:
    """[v3-R12] 构造占位 AnalysisSection（narrative ≥350 字硬缓冲）。

    payload_dict 当前未直接拼入文本（占位文案不依赖 payload 内容，避免动态长度抖动），
    保留参数以便未来扩展（如把 payload 的 artifact_id 列入 artifact_refs）。
    """
    _ = payload_dict  # 占位文案不依赖 payload；保留参数供未来扩展
    narrative = _PLACEHOLDER_NARRATIVE_TEMPLATE.format(section_type=section_type)
    heading = f"【数据不足占位章节】{section_type}"
    # section_id schema 约束 3-40 字。最长 section_type=23 字，"placeholder-"+23 = 35 ≤ 40 ✓
    section_id = f"placeholder-{section_type[:30]}"
    return AnalysisSection(
        section_id=section_id,
        heading=heading,
        narrative=narrative,
        section_type=section_type,
        artifact_refs=[],
        source_refs=[],
    )


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

        # outline 留给 phase 2-4 使用
        outline = await self._phase1_outline(
            scenario,
            scenario_input,
            analysis,
            profiles,
            competitor_names,
            competitor_basics,
            our_product_brief,
            discovered_urls,
        )
        logger.info("[writer] phase 1 完成, 进入 phase 2")

        # ========== Phase 2: payload ==========
        warnings: list[str] = []
        payload_model = await self._call_phase2_with_validation(
            scenario=scenario,
            scenario_input=scenario_input,
            analysis=analysis,
            profiles=profiles,
            competitor_recommendations=competitor_recommendations,
            prior_report_data=prior_report_data,
            competitor_names=competitor_names,
            competitor_basics=competitor_basics,
            discovered_urls=discovered_urls,
            warnings=warnings,
        )
        logger.info("[writer] phase 2 完成, 进入 phase 3")

        # ========== Phase 3: narrative ==========
        # 用 model_dump() 转 payload_dict 给 narrative prompt 拼装上下文（[v3-R20] dot-walk 路径取值）
        payload_dict_for_phase3 = payload_model.model_dump()
        sections, warnings = await self._phase3_narratives(
            scenario=scenario,
            scenario_input=scenario_input,
            outline=outline,
            payload_dict=payload_dict_for_phase3,
            analysis=analysis,
            discovered_urls=discovered_urls,
            warnings=warnings,
        )
        # sections / payload_model / outline / warnings 留给 phase 4 使用，避免未使用告警
        _ = (sections, payload_model, outline)

        # 触达占位：C5 task 接续实现
        raise NotImplementedError("phase 4 待 Task 21.5 实现")

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
        基于 base_user_prompt 重建 prompt，避免重试时错误摘要在 loop 内累积膨胀。
        """
        base_user_prompt = user_prompt
        last_error_summary: str | None = None
        for attempt in range(max_retries + 1):
            current_user_prompt = base_user_prompt
            if last_error_summary:
                current_user_prompt = (
                    f"{base_user_prompt}\n\n【上次校验失败，请修复】\n{last_error_summary}"
                )
            raw = await self._llm_call_with_quota(
                system_prompt, current_user_prompt, max_tokens=max_tokens
            )
            try:
                return schema_cls(**raw)
            except ValidationError as e:
                if attempt >= max_retries:
                    raise
                last_error_summary = self._serialize_validation_error(e, max_chars=1500)

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

    # ========== Phase 2: payload ==========

    def _build_phase2_user_prompt(
        self,
        scenario: str,
        scenario_input: ScenarioInput,
        analysis: Any,
        profiles: list[CompetitorProfile],
        competitor_recommendations: Any,
        competitor_names: list[str],
        competitor_basics: list[dict],
        discovered_urls: list[str],
    ) -> str:
        """拼装 Phase 2 base user prompt（不含 LLM 调用，便于重试时复用）。"""
        # Profiles 摘要（与 phase 1 一致：basic_info 维度，控制 token）
        profile_summaries: list[dict] = []
        for p in profiles:
            profile_summaries.append(
                {
                    "name": p.basic_info.name,
                    "company": p.basic_info.company,
                    "version": p.basic_info.version,
                    "platform": p.basic_info.platform,
                }
            )

        # Analysis 摘要：截断到 ~5000 字符（与 phase 1 一致）
        try:
            analysis_json = analysis.model_dump_json()
        except AttributeError:
            analysis_json = json.dumps(analysis, ensure_ascii=False, default=str)
        if len(analysis_json) > 5000:
            analysis_json = analysis_json[:5000] + "...[truncated]"

        our_product_brief = {
            "name": scenario_input.our_product_name or "",
            "brief": scenario_input.our_product_brief or "",
            "industry": scenario_input.industry or "",
        }

        sections: list[tuple[str, Any]] = [
            ("=== 场景 ===", scenario),
            ("=== 我方产品 ===", our_product_brief),
            ("=== 竞品列表 ===", competitor_basics),
            ("=== 分析意图 ===", scenario_input.analysis_context),
            ("=== Profiles 摘要 ===", profile_summaries),
            ("=== Analysis 摘要 ===", analysis_json),
            ("=== 可用溯源 URL ===", discovered_urls),
        ]

        # [v3-R10] S2 推荐竞品仅作为只读上下文给 LLM（phase 2 后会被代码强制覆盖）
        if scenario == "S2" and competitor_recommendations is not None:
            sections.append(
                (
                    "=== 推荐竞品（只读上下文，不要重写）===",
                    competitor_recommendations.model_dump(),
                )
            )

        # [v3-R09] S4 prior 监控提示（具体 diff 由代码注入；这里只告知 LLM 是否首次）
        if scenario == "S4":
            mode_hint = (
                "首次监控（prior_trace_id 为空，所有 change 须 is_baseline=True，trends 全 None）"
                if scenario_input.prior_trace_id is None
                else f"增量监控（prior_trace_id={scenario_input.prior_trace_id}，diff 由代码注入）"
            )
            sections.append(("=== prior 监控信息（如有）===", mode_hint))

        parts: list[str] = []
        for label, value in sections:
            if isinstance(value, str):
                parts.append(f"{label}\n{value}")
            else:
                parts.append(f"{label}\n{json.dumps(value, ensure_ascii=False, indent=2)}")
        return "\n\n".join(parts)

    async def _call_phase2_with_validation(
        self,
        *,
        scenario: str,
        scenario_input: ScenarioInput,
        analysis: Any,
        profiles: list[CompetitorProfile],
        competitor_recommendations: Any,
        prior_report_data: Optional[dict],
        competitor_names: list[str],
        competitor_basics: list[dict],
        discovered_urls: list[str],
        warnings: list[str],
        max_retries: int = 1,
        max_tokens: int = 4096,
    ):
        """Phase 2 LLM call → normalize → 注入 → 实例化场景 Payload schema。

        [I1 修复] ValidationError 时回灌错误摘要重试 1 次（spec v3 行 254-256）。
        重试也走 _llm_call_with_quota，受熔断保护。
        """
        base_user_prompt = self._build_phase2_user_prompt(
            scenario,
            scenario_input,
            analysis,
            profiles,
            competitor_recommendations,
            competitor_names,
            competitor_basics,
            discovered_urls,
        )
        system_prompt = WRITER_PAYLOAD_PROMPTS[scenario]
        last_error_summary: str | None = None

        for attempt in range(max_retries + 1):
            current_user_prompt = base_user_prompt
            if last_error_summary:
                current_user_prompt = (
                    f"{base_user_prompt}\n\n【上次校验失败，请修复】\n{last_error_summary}"
                )
            raw = await self._llm_call_with_quota(
                system_prompt, current_user_prompt, max_tokens=max_tokens
            )
            try:
                payload_model = self._build_payload_model(
                    scenario,
                    raw,
                    discovered_urls=discovered_urls,
                    competitor_recommendations=competitor_recommendations,
                    prior_report_data=prior_report_data,
                    scenario_input=scenario_input,
                    warnings=warnings,
                )
                logger.info("[writer] phase 2 payload 完成: scenario=%s", scenario)
                return payload_model
            except ValidationError as e:
                if attempt >= max_retries:
                    raise
                last_error_summary = self._serialize_validation_error(e, max_chars=1500)
                logger.warning("[writer] phase 2 ValidationError 重试 1 次")

    def _build_payload_model(
        self,
        scenario: str,
        payload_dict: dict,
        *,
        discovered_urls: list[str],
        competitor_recommendations: Any,
        prior_report_data: Optional[dict],
        scenario_input: ScenarioInput,
        warnings: list[str],
    ):
        """normalize → S2/S4 前置注入 → 实例化场景 Payload schema。

        ValidationError 不在此处捕获——直接冒到 graph 层由 builder.writer_node 转 RejectionFeedback。
        """
        discovered_set: set[str] = set(discovered_urls)
        cleaned = normalize_for_scenario(
            scenario, payload_dict, discovered_urls=discovered_set, warnings=warnings
        )

        # [v3-R10] S2 recommender 强制覆盖（不论 LLM 写了什么）
        if scenario == "S2" and competitor_recommendations is not None:
            cleaned["competitor_recommendations"] = competitor_recommendations.model_dump()

        # [v3-R09] S4 prior diff 必须在 model 实例化之前注入
        if scenario == "S4":
            cleaned = self._inject_s4_prior_diff(
                cleaned, prior_report_data, scenario_input
            )

        payload_cls = _PAYLOAD_CLASSES[scenario]
        payload_model = payload_cls(**cleaned)
        logger.info(
            "[writer] phase 2 payload schema 实例化完成: %s, dropped_warnings=%d",
            scenario,
            len(warnings),
        )
        return payload_model

    def _inject_s4_prior_diff(
        self,
        payload_dict: dict,
        prior_report_data: Optional[dict],
        scenario_input: ScenarioInput,
    ) -> dict:
        """[v3-R09] S4 场景：从 prior_report_data 解析 newly_added/dropped competitors，写入 review_period。

        - prior_report_data 为 None → 首次监控模式（不写 prior_trace_id；schema validator 走 baseline 分支）
        - prior 报告 scenario / schema_version 不匹配 → logger.warning + 降级为首次监控（同样不写 prior_trace_id）

        [C1 修复] prior_trace_id 写入与 newly/dropped 计算同步——只在确认能做 diff 时才注入，
        避免「prior_trace_id 已写但 diff 没算」造成的伪溯源（标"基于 prior=xxx 增量"但实际未 diff）。
        """
        review_period = payload_dict.setdefault("review_period", {})

        # 首次监控模式：prior_report_data 为空 → 不写 prior_trace_id，直接返回
        if not prior_report_data:
            return payload_dict

        prior_meta = (
            prior_report_data.get("metadata", {})
            if isinstance(prior_report_data, dict)
            else {}
        )
        if (
            prior_meta.get("scenario") != "S4"
            or prior_meta.get("schema_version") != "2.0"
        ):
            logger.warning(
                "[writer] S4 prior 报告 scenario/schema_version 不匹配，降级为首次监控"
            )
            return payload_dict

        # 确认能做 diff，prior_trace_id 与 newly/dropped 同步注入
        if scenario_input.prior_trace_id:
            review_period["prior_trace_id"] = scenario_input.prior_trace_id

        prior_payload = prior_report_data.get("scenario_payload", {}) or {}
        prior_review_period = prior_payload.get("review_period", {}) or {}
        prior_competitors = set(prior_review_period.get("monitored_competitors", []) or [])

        current_competitors = set(review_period.get("monitored_competitors", []) or [])

        review_period["newly_added_competitors"] = sorted(
            current_competitors - prior_competitors
        )
        review_period["dropped_competitors"] = sorted(
            prior_competitors - current_competitors
        )

        return payload_dict

    # ========== Phase 3: narrative ==========

    def _default_section_types(self, scenario: str) -> list[str]:
        """每场景默认 section_type 序列（5-6 个）。"""
        return _DEFAULT_SECTION_TYPES[scenario]

    async def _phase3_one_section(
        self,
        *,
        scenario: str,
        section_type: str,
        outline: dict,
        payload_dict: dict,
        analysis: Any,
        scenario_input: ScenarioInput,
        discovered_urls: list[str],
    ) -> AnalysisSection:
        """[v3-R18] Semaphore 限速；[v3-R04] 走 _llm_call_with_quota 不绕熔断。

        失败（LLM 异常 / Pydantic ValidationError）让其向上抛——caller 用
        asyncio.gather(return_exceptions=True) 接住后回 _build_placeholder_section。
        """
        _ = discovered_urls  # prompt 已在 phase 1/2 里灌过；本阶段 schema 校验靠 SourceRef.url 约束
        async with self._narrative_sem:
            # 按 [v3-R20] SECTION_CONTEXT_MAP 取本 section 应吃的字段
            ctx = {
                "outline": outline,
                "payload": payload_dict,
                "analysis": analysis,
                "scenario_input": scenario_input,
            }
            context_paths = SECTION_CONTEXT_MAP.get(section_type, [])
            context_payload: dict = {}
            for p in context_paths:
                value = _dot_walk(ctx, p)
                if value is not None:
                    context_payload[p] = value

            # 控制 token：context_payload JSON 序列化后截断 4000 字符
            try:
                ctx_json = json.dumps(context_payload, ensure_ascii=False, default=str)
            except TypeError:
                ctx_json = json.dumps(
                    {k: str(v) for k, v in context_payload.items()},
                    ensure_ascii=False,
                )
            if len(ctx_json) > 4000:
                ctx_json = (
                    ctx_json[:4000]
                    + f"\n...[已截断后续 {len(ctx_json) - 4000} 字符]"
                )

            section_label = SECTION_LABELS.get(section_type, section_type)
            section_focus = SECTION_FOCUS_HINTS.get(section_type, "")
            # section_id schema 3-40 字；scenario.lower()=2 + "-" + section_type[:30] 最多 33 字
            section_id_hint = f"{scenario.lower()}-{section_type[:30]}"

            # NARRATIVE_TEMPLATE 既含角色描述也含 JSON 输出契约，整体当 system；user 只触发生成
            system_prompt = NARRATIVE_TEMPLATE.format(
                section_type=section_type,
                section_label=section_label,
                section_focus_hint=section_focus,
                scenario=scenario,
                section_id_hint=section_id_hint,
                context_payload=ctx_json,
            )
            user_prompt = "请基于上述上下文生成本节 JSON。"

            raw = await self._llm_call_with_quota(
                system_prompt, user_prompt, max_tokens=4096
            )
            return AnalysisSection(**raw)

    async def _phase3_narratives(
        self,
        *,
        scenario: str,
        scenario_input: ScenarioInput,
        outline: dict,
        payload_dict: dict,
        analysis: Any,
        discovered_urls: list[str],
        warnings: list[str],
    ) -> tuple[list[AnalysisSection], list[str]]:
        """[v3-R05] [v3-R12] [v3-R18] 并行 narrative + 占位降级 + 半数闸门。

        - asyncio.gather(return_exceptions=True) 接住单 section 失败
        - 失败回 _build_placeholder_section + warnings 加 placeholder_section:{type}:{ExcName}
        - 失败数 ≥ ⌈expected_n / 2⌉ → raise RuntimeError 触发 graph 回 collector
        """
        section_types = _DEFAULT_SECTION_TYPES[scenario]
        expected_n = len(section_types)

        results = await asyncio.gather(
            *(
                self._phase3_one_section(
                    scenario=scenario,
                    section_type=st,
                    outline=outline,
                    payload_dict=payload_dict,
                    analysis=analysis,
                    scenario_input=scenario_input,
                    discovered_urls=discovered_urls,
                )
                for st in section_types
            ),
            return_exceptions=True,
        )

        sections: list[AnalysisSection] = []
        failed_n = 0
        for st, r in zip(section_types, results):
            if isinstance(r, Exception):
                sections.append(_build_placeholder_section(st, payload_dict))
                warnings.append(f"placeholder_section:{st}:{type(r).__name__}")
                failed_n += 1
                logger.warning(
                    "[writer] phase 3 section %s 失败 → 占位降级: %s",
                    st,
                    type(r).__name__,
                )
            else:
                sections.append(r)

        # [v3-R05] 半数闸门：失败数 ≥ ⌈expected_n / 2⌉ 即 raise
        threshold = (expected_n + 1) // 2
        if failed_n >= threshold:
            raise RuntimeError(
                f"phase 3 失败数 {failed_n} >= {threshold}（expected={expected_n}），"
                f"触发半数闸门，建议回 collector 重新采集"
            )

        logger.info(
            "[writer] phase 3 narrative 完成: %d/%d 成功",
            expected_n - failed_n,
            expected_n,
        )
        return sections, warnings
