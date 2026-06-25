"""WriterOrchestrator — 4 阶段编排（v3 spec Task 21.1+21.2+21.3+21.4+21.5）。

阶段 3-C1 范围：骨架 + Phase 1 outline。
阶段 3-C3 范围：Phase 2 payload（含 normalize 接通 + S2/S4 前置注入 + 实例化场景 Payload schema）。
阶段 3-C4 范围：Phase 3 narrative（并行 + 半数闸门 + 占位降级 + Semaphore 限速）。
阶段 3-C5 范围：Phase 4 assemble（代码合成 BaseReport，0 LLM 调用；SWOT 透传 + URL 双通道收集 +
                 全字段 DataSource 构造 + scope.competitors S2 union + ReportMetadata 构造）。
"""
import asyncio
import json
import logging
import uuid
from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, ValidationError

from src.agents.normalizers import normalize_for_scenario
from src.agents.prompts.writer import WRITER_OUTLINE_PROMPTS, WRITER_PAYLOAD_PROMPTS
from src.agents.prompts.writer.narrative import (
    NARRATIVE_TEMPLATE,
    SECTION_CONTEXT_MAP,
    SECTION_FOCUS_HINTS,
    SECTION_LABELS,
)
from src.schemas.common import DataSource
from src.schemas.input import ScenarioInput
from src.schemas.profile import CompetitorProfile
from src.schemas.report import (
    AnalysisSection,
    Appendix,
    BaseReport,
    ExecutiveSummary,
    Finding,
    Methodology,
    Recommendation,
    ReportMetadata,
    ReportScope,
    Swot,
    SwotEntry,
)
from src.schemas.scenarios.s1 import S1FeatureIterationPayload
from src.schemas.scenarios.s2 import S2MarketEntryPayload
from src.schemas.scenarios.s3 import S3PricingStrategyPayload
from src.schemas.scenarios.s4 import S4MonitoringPayload
from src.schemas.scenarios.s5 import S5PositioningPayload
from src.tools.llm_client import LLMClient
from src.utils.config import settings

logger = logging.getLogger(__name__)


# ============= [v3-R02] writer 异常路由错误码（D3 code review C1 修法 a）=============
# 用 isinstance 区分路由意图，不再依赖 builder 端中文措辞子串匹配。
class WriterRouteToCollector(RuntimeError):
    """writer 阶段错误，需上游 collector 重新采集（如 profiles URL 0、半数 section 失败）。"""


class WriterRouteToWriter(RuntimeError):
    """writer 自身可重试错误（如 final_urls 空、单 section narrative 异常但未触发闸门）。"""


class WriterRouteToEnd(RuntimeError):
    """writer 不可恢复错误，应直接终止图（LLM quota 超限、scope 全空、scope 无法构造）。"""


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
    # section_id schema 3-40 字。"placeholder-" = 12 字，section_type 截断至 28 → 12+28=40 ✓
    # 最长 section_type 实测 35 字（如 opportunity_identification_analysis），截断后保留前 28 字仍可识别 section
    section_id = f"placeholder-{section_type[:28]}"
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


# ========== Phase 4: assemble 模块级工具 ==========

# [v3-R07] 裸 url 字段名白名单（仅取 url 字符串，不构造 SourceRef 全字段）
# 覆盖 S1 FeatureScore.evidence_url / S3 PricingPageAudit.pricing_page_url /
# S3 RolloutStep.evidence_url / RecentUpdate.source_url / SampleReview.source_url 等。
_BARE_URL_FIELDS = frozenset({
    "evidence_url", "pricing_page_url", "source_url", "official_url", "url",
})


# [fix11] data_collection_approach 代码合成模板：5 场景共用，输出 ≥200 字符
_SCENARIO_LABELS: dict[str, str] = {
    "S1": "S1 功能迭代",
    "S2": "S2 市场进入",
    "S3": "S3 定价策略",
    "S4": "S4 持续监控",
    "S5": "S5 战略定位",
}


def _build_data_collection_approach(
    profiles: list[CompetitorProfile],
    scenario: str,
    discovered_url_count: int,
) -> str:
    """[fix11] 代码合成 Methodology.data_collection_approach 文本。

    Why：phase 1 outline LLM 反复写不够 200 字符，每次 graph 重试栽在同一处。
    本字段属于"我们怎么采的数据"的元描述，不需要 LLM 创作，模板化即可。
    """
    label = _SCENARIO_LABELS.get(scenario, scenario)
    competitor_count = len(profiles)
    competitor_names = "、".join(p.basic_info.name for p in profiles) or "（无）"
    avg_completeness = (
        sum(p.metadata.completeness_score for p in profiles) / max(1, len(profiles))
    )
    collected_dates = sorted({(p.metadata.collected_at or "")[:10] for p in profiles if p.metadata and p.metadata.collected_at})
    date_window = (
        f"{collected_dates[0]} 至 {collected_dates[-1]}" if collected_dates else "本次会话内"
    )

    return (
        f"本报告面向 {label} 场景，由「采集→分析→撰写→质检」四 Agent 流水线协作产出。"
        f"采集 Agent 基于 Tavily 检索 API 对 {competitor_count} 个竞品（{competitor_names}）"
        f"分别发起场景化关键词查询，单次返回 5 条结果并附带正文，按 quality_gate 过滤反爬/低质页面后"
        f"得到 {discovered_url_count} 条有效溯源 URL。分析 Agent 在收集到的画像数据上做四维结构化对比"
        f"（定位 / 功能矩阵 / 商业模式 / 用户口碑）+ SWOT + 雷达评分。撰写 Agent 通过 4 阶段 LLM 编排"
        f"（outline → payload → narrative → assemble）合成结构化报告，溯源 URL 经过双通道收集与幻觉过滤。"
        f"质检 Agent 按场景分派硬查 + LLM 语义审，按 issue 严重度路由打回上游。"
        f"采集时间窗口：{date_window}；平均画像完整度：{avg_completeness:.2f}。"
    )


# Appendix.glossary 动态场景化术语表
_COMMON_GLOSSARY: dict[str, str] = {
    "SWOT": "Strengths/Weaknesses/Opportunities/Threats，针对单一主体的四象限分析框架。",
    "JTBD": "Jobs To Be Done，用户要完成的任务；从用户视角描述其目标与场景，而非功能本身。",
    "Tier1": "竞品分级中的最高优先级层级，通常代表核心或行业头部玩家。",
    "Tier2": "竞品分级中的次优先级层级，通常代表细分市场玩家或潜在挑战者。",
}

_SCENARIO_GLOSSARY: dict[str, dict[str, str]] = {
    "S1": {
        "Forrester Wave": "Forrester 研究机构的竞品评估模型，按 strategy 和 current offering 两轴对厂商打分排位。",
        "Feature Matrix": "功能矩阵，以表格形式横向对比多个竞品在各功能维度上的支持程度。",
        "White Space": "功能空白区，指市场上所有现有玩家都尚未覆盖的功能或场景。",
        "Roadmap": "产品路线图，按时间维度规划未来功能迭代的优先级与节奏。",
    },
    "S2": {
        "TAM": "Total Addressable Market，潜在总市场规模，假设 100% 占有率下的市场总量。",
        "SAM": "Serviceable Addressable Market，可服务市场，受地理/行业/合规等限制后的可触达市场。",
        "SOM": "Serviceable Obtainable Market，可获取市场，结合自身资源现实可拿下的市场份额。",
        "CAGR": "Compound Annual Growth Rate，复合年增长率，衡量市场或业务的长期增速。",
        "Porter Five Forces": "波特五力模型，从新进入者/供应商/买家/替代品/现有竞争五个维度评估行业吸引力。",
        "MQ": "Magic Quadrant，按两轴（如执行能力 × 愿景完整性）划分玩家的二维定位象限图。",
        "ICP": "Ideal Customer Profile，理想客户画像，最适合产品的目标客户特征集合。",
        "niche": "细分市场 / 利基市场，规模较小但竞争弱、需求明确的目标人群或场景。",
    },
    "S3": {
        "GBB": "Good-Better-Best，三档定价分层策略，用价值阶梯促成升档转化。",
        "WTP": "Willingness To Pay，支付意愿，客户对产品/功能愿意支付的最高价格。",
        "ARPU": "Average Revenue Per User，每用户平均收入，衡量单客户贡献的核心指标。",
        "ARR": "Annual Recurring Revenue，年度经常性收入，订阅业务核心指标。",
        "Freemium": "免费增值模式，基础功能免费、高级功能付费的商业模型。",
        "Churn": "客户流失率，一定周期内停止付费或使用的客户比例。",
        "Price Anchor": "价格锚点，通过展示高价选项使目标价位显得更合理的定价心理学策略。",
    },
    "S4": {
        "FIA": "Fact-Impact-Act，竞品情报三元组：事实→影响→行动，结构化记录竞品动态。",
        "Battlecard": "活体战卡，面向销售团队的竞品对抗速查手册，含话术与差异点。",
        "OSCOM": "Opportunity Scoring Model，机会评分模型，按投入/影响/紧迫度量化竞争机会。",
        "Baseline": "监控基线，首次采集的竞品状态快照，后续增量对比的参照点。",
        "Severity": "严重度等级（low/medium/high），衡量竞品变更对我方的影响程度。",
    },
    "S5": {
        "MQ": "Magic Quadrant，按两轴（如执行能力 × 愿景完整性）划分玩家的二维定位象限图。",
        "Perceptual Map": "感知地图，以二维坐标展示品牌在用户心智中的相对位置。",
        "Strategy Canvas": "战略画布，以折线图展示各竞品在关键竞争要素上的投入水平差异。",
        "ERRC": "Eliminate-Reduce-Raise-Create，蓝海战略四动作框架，重塑价值曲线。",
        "Blue Ocean": "蓝海战略，通过价值创新开辟无竞争的新市场空间，而非在红海中拼杀。",
        "Positioning Statement": "定位陈述，Geoffrey Moore 6 位模板，一句话定义产品的目标客户、品类、差异化。",
    },
}


def _build_glossary(scenario: str) -> dict[str, str]:
    """根据场景类型动态组装术语表：通用术语 + 场景专属术语。"""
    glossary = dict(_COMMON_GLOSSARY)
    glossary.update(_SCENARIO_GLOSSARY.get(scenario, {}))
    return glossary


def _derive_fallback_accessed_at(profiles: list[CompetitorProfile]) -> Optional[date]:
    """[fix8] 从 profiles.metadata.collected_at 派生 DataSource.accessed_at 兜底值。

    取所有 collected_at 中最晚一个的日期部分（最近一次采集为准）。
    profiles 为空 / collected_at 全无效时返回 None（schema 允许 accessed_at=None）。
    """
    candidates: list[date] = []
    for p in profiles:
        ts = (p.metadata.collected_at or "").strip() if p.metadata else ""
        if not ts:
            continue
        try:
            # 兼容 "2026-06-08T00:00:00" / "2026-06-08T00:00:00+00:00" / "2026-06-08"
            iso = ts.replace("Z", "+00:00")
            candidates.append(datetime.fromisoformat(iso).date())
        except (ValueError, TypeError):
            continue
    if not candidates:
        return None
    return max(candidates)


def _build_placeholder_swot() -> Swot:
    """[v3-R12] analysis.swot 缺失时的占位 SWOT。

    字符数硬约束（schema min=10，留 ≥15 字硬缓冲防文案微调跌破）：
    - point_text 41 字 ≥25 + 16 字硬缓冲
    - evidence_text 51 字 ≥25 + 26 字硬缓冲
    """
    point_text = "采集数据不足，本象限当前由代码自动占位，等待数据补齐后由 LLM 重新生成具体条目"
    evidence_text = "详见报告 metadata.warnings 中以 placeholder_swot 为前缀的告警条目"
    placeholder = SwotEntry(
        point=point_text,
        evidence=evidence_text,
        dimension="overall",
    )
    return Swot(
        strengths=[placeholder],
        weaknesses=[placeholder],
        opportunities=[placeholder],
        threats=[placeholder],
    )


def _collect_source_refs_recursive(obj: Any) -> tuple[list[dict], set[str]]:
    """[v3-R07/R08] 双通道 URL 收集。

    返回 (source_refs_full, bare_urls)：
    - source_refs_full：SourceRef-like dict 列表（保留 url/title/accessed_at/source_type 全字段）
    - bare_urls：仅从 _BARE_URL_FIELDS 字段名白名单收集的 url 字符串集合

    [v3-R08] 区分 SourceRef vs DataSource：DataSource 含 confidence 字段，
    报告级 metadata.data_sources 不应再被回收当 source_ref。
    """
    refs: list[dict] = []
    bare: set[str] = set()
    if isinstance(obj, dict):
        if {"url", "source_type"} <= obj.keys() and "confidence" not in obj:
            if obj.get("url"):
                refs.append({
                    "url": obj["url"],
                    "title": obj.get("title", ""),
                    "accessed_at": obj.get("accessed_at"),
                    "source_type": obj.get("source_type", "other"),
                })
        for k, v in obj.items():
            if k in _BARE_URL_FIELDS and isinstance(v, str) and v.startswith("http"):
                bare.add(v)
            sub_refs, sub_bare = _collect_source_refs_recursive(v)
            refs.extend(sub_refs)
            bare |= sub_bare
    elif isinstance(obj, list):
        for item in obj:
            sub_refs, sub_bare = _collect_source_refs_recursive(item)
            refs.extend(sub_refs)
            bare |= sub_bare
    return refs, bare


class WriterOrchestrator:
    """Writer 4 阶段编排器（C1 仅实现 Phase 1，后续 phase 由 C3-C5 接续）。"""

    def __init__(self, llm: LLMClient):
        self.llm = llm
        self._call_counter = 0  # M2 熔断计数
        # [v3-R18] phase 3 并发限速（C1 暂未用，提前创建供 C4 使用）
        self._narrative_sem = asyncio.Semaphore(settings.WRITER_NARRATIVE_CONCURRENCY)
        self._grouped_urls: dict[str, list[str]] = {}

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
        feedback_issues: list | None = None,
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
        # 按竞品分组的 URL 字典（用于 phase 2/3 prompt 注入）
        grouped_urls: dict[str, list[str]] = {}
        for p in profiles:
            name = p.basic_info.name
            urls = sorted(collect_profile_urls(p))
            if urls:
                grouped_urls[name] = urls
        self._grouped_urls = grouped_urls

        if not discovered_urls:
            raise WriterRouteToCollector(
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
            prior_report_data=prior_report_data,
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
        # phase 4 也复用此 dump 结果避免重复序列化
        payload_dict = payload_model.model_dump()
        sections, warnings = await self._phase3_narratives(
            scenario=scenario,
            scenario_input=scenario_input,
            outline=outline,
            payload_dict=payload_dict,
            analysis=analysis,
            discovered_urls=discovered_urls,
            warnings=warnings,
            feedback_issues=feedback_issues,
        )
        logger.info("[writer] phase 3 完成, 进入 phase 4")

        # ========== Phase 4: assemble ==========
        report = self._phase4_assemble(
            scenario=scenario,
            scenario_input=scenario_input,
            outline=outline,
            payload_model=payload_model,
            sections=sections,
            profiles=profiles,
            analysis=analysis,
            trace_id=trace_id,
            warnings=warnings,
            competitor_recommendations=competitor_recommendations,
            discovered_urls=discovered_urls,
            competitor_names=competitor_names,
            payload_dict=payload_dict,  # 复用 phase 3 已 dump 的结果
        )
        logger.info("[writer] phase 4 完成: %s", (report.title or "")[:30])
        return report

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
            raise WriterRouteToEnd(
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
                last_error_summary = self._serialize_validation_error_enhanced(e, max_chars=1500)

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

    @staticmethod
    def _serialize_validation_error_enhanced(
        e: ValidationError, max_chars: int = 2000
    ) -> str:
        """S5 专用增强错误反馈：人类可读字段路径 + 期望值描述。

        相比 _serialize_validation_error 的 JSON dump：
        1. 字段路径用点号串联（vendor_profiles.0.strengths），LLM 易读
        2. type 翻译为具体期望值（string_too_short → 要求 ≥N 字符）
        3. 每条独立成行带序号，便于 LLM 逐条修正
        """
        _TYPE_HINTS = {
            "string_too_short": lambda err: (
                f"长度不足（要求 ≥{err.get('ctx', {}).get('min_length', '?')} 字符）"
            ),
            "string_too_long": lambda err: (
                f"长度超限（要求 ≤{err.get('ctx', {}).get('max_length', '?')} 字符）"
            ),
            "too_short": lambda err: (
                f"条目数不足（要求 ≥{err.get('ctx', {}).get('min_length', '?')} 条）"
            ),
            "too_long": lambda err: (
                f"条目数超限（要求 ≤{err.get('ctx', {}).get('max_length', '?')} 条）"
            ),
            "missing": lambda err: "必填字段缺失",
            "value_error": lambda err: err.get("msg", "校验失败"),
            "int_parsing": lambda err: "应为整数",
            "float_parsing": lambda err: "应为浮点数",
            "enum": lambda err: (
                f"应为 {err.get('ctx', {}).get('expected', '指定值')} 之一"
            ),
            "literal_error": lambda err: (
                f"应为 {err.get('ctx', {}).get('expected', '指定值')} 之一"
            ),
            "less_than_equal": lambda err: (
                f"应 ≤{err.get('ctx', {}).get('le', '?')}"
            ),
            "greater_than_equal": lambda err: (
                f"应 ≥{err.get('ctx', {}).get('ge', '?')}"
            ),
        }

        errs = e.errors()[:8]
        lines: list[str] = []
        for i, err in enumerate(errs, 1):
            loc = ".".join(str(p) for p in err["loc"])
            err_type = err.get("type", "")
            hint_fn = _TYPE_HINTS.get(err_type)
            hint = hint_fn(err) if hint_fn else err.get("msg", err_type)
            lines.append(f"{i}. {loc}: {hint}")

        text = "\n".join(lines)
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
        prior_report_data: Optional[dict] = None,
    ) -> dict:
        """Phase 1：一次 LLM 调用产出 BaseReport 全部非 payload/sections/swot 字段。

        [2026-06-18 修复] 对 executive_summary 子结构做即时 Pydantic 校验，
        失败时回灌错误反馈重试（max_retries=2），避免漏字段拖到 phase 4 才炸
        浪费 phase 2/3 的 ~10 分钟计算预算。

        其他顶层字段（title / scope / methodology 等）仍在 phase 4 BaseReport
        实例化时统一校验——它们结构简单，LLM 漏填罕见。
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
        # 用 isinstance 判 BaseModel，比 try/except AttributeError 更精准（C4 carry-over M7）
        if isinstance(analysis, BaseModel):
            analysis_json = analysis.model_dump_json()
        else:
            analysis_json = json.dumps(analysis, ensure_ascii=False, default=str)
        if len(analysis_json) > 5000:
            analysis_json = analysis_json[:5000] + "...[truncated]"

        sections = [
            ("=== 当前日期 ===", date.today().isoformat()),
            ("=== 场景 ===", scenario),
            ("=== 我方产品 ===", our_product_brief),
            ("=== 竞品列表 ===", competitor_basics),
            ("=== 竞品名（便于引用） ===", competitor_names),
            ("=== 分析目标 ===", scenario_input.analysis_context),
            ("=== Profiles 摘要 ===", profile_summaries),
            ("=== Analysis 摘要 ===", analysis_json),
            ("=== 可用溯源 URL（按竞品归属）===", self._grouped_urls),
        ]

        # [v3-R09 / #3] S4 prior 监控提示：判「prior 是否真正可用」而非「用户是否填了 prior_trace_id」。
        # prior 报告丢失/损坏时 prior_report_data=None，必须降级为首次监控提示，
        # 否则 LLM 生成 is_baseline=False 与 schema _check_first_review_baseline 冲突必崩。
        if scenario == "S4":
            if self._prior_is_usable(prior_report_data):
                mode_hint = f"增量监控（prior_trace_id={scenario_input.prior_trace_id}，diff 由代码注入）"
            else:
                mode_hint = "首次监控（prior_trace_id 为空，所有 change 须 is_baseline=True，trends 全 None）"
            sections.append(("=== prior 监控信息 ===", mode_hint))

        parts: list[str] = []
        for label, value in sections:
            if isinstance(value, str):
                parts.append(f"{label}\n{value}")
            else:
                parts.append(f"{label}\n{json.dumps(value, ensure_ascii=False, indent=2)}")
        user_prompt = "\n\n".join(parts)

        system_prompt = WRITER_OUTLINE_PROMPTS[scenario]

        # [2026-06-18 修复] outline 即时校验 executive_summary 子结构，
        # 失败时回灌增强错误反馈重试，最多 max_retries=2 次。
        max_retries = 2
        last_error_summary: str | None = None
        for attempt in range(max_retries + 1):
            current_user_prompt = user_prompt
            if last_error_summary:
                current_user_prompt = (
                    f"{user_prompt}\n\n【上次 outline 校验失败，请逐条修复】\n{last_error_summary}"
                )
            outline = await self._llm_call_with_quota(
                system_prompt, current_user_prompt, max_tokens=6144
            )
            try:
                # 仅对最易漏字段的 executive_summary 子结构做即时校验。
                # 其他顶层字段在 phase 4 统一校验。
                es_dict = outline.get("executive_summary", {}) if isinstance(outline, dict) else {}
                ExecutiveSummary(**es_dict)
                title_preview = (
                    (outline.get("title") or "(no title)")[:30]
                    if isinstance(outline, dict) else "(no title)"
                )
                logger.info("[writer] phase 1 outline 完成: %s", title_preview)
                return outline
            except ValidationError as e:
                if attempt >= max_retries:
                    raise
                last_error_summary = self._serialize_validation_error_enhanced(
                    e, max_chars=1500
                )
                logger.warning(
                    "[writer] phase 1 outline executive_summary 校验失败重试: %s",
                    last_error_summary[:300].replace("\n", " | "),
                )

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
        prior_report_data: Optional[dict] = None,
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
        # 用 isinstance 判 BaseModel，比 try/except AttributeError 更精准（C4 carry-over M7）
        if isinstance(analysis, BaseModel):
            analysis_json = analysis.model_dump_json()
        else:
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
            ("=== 可用溯源 URL（按竞品归属）===", self._grouped_urls),
        ]

        # [v3-R10] S2 推荐竞品仅作为只读上下文给 LLM（phase 2 后会被代码强制覆盖）
        if scenario == "S2" and competitor_recommendations is not None:
            sections.append(
                (
                    "=== 推荐竞品（只读上下文，不要重写）===",
                    competitor_recommendations.model_dump(),
                )
            )

        # [v3-R09 / #3] S4 prior 监控提示：判 prior 是否真正可用（与 phase1 / inject 统一判空对象）
        if scenario == "S4":
            if self._prior_is_usable(prior_report_data):
                mode_hint = f"增量监控（prior_trace_id={scenario_input.prior_trace_id}，diff 由代码注入）"
            else:
                mode_hint = "首次监控（prior_trace_id 为空，所有 change 须 is_baseline=True，trends 全 None）"
            sections.append(("=== prior 监控信息（如有）===", mode_hint))

        parts: list[str] = []
        for label, value in sections:
            if isinstance(value, str):
                parts.append(f"{label}\n{value}")
            else:
                parts.append(f"{label}\n{json.dumps(value, ensure_ascii=False, indent=2)}")
        return "\n\n".join(parts)

    # ========== S5 Phase 2 拆分（2026-06-16 优化） ==========

    async def _call_s5_phase2a(
        self,
        *,
        scenario_input: ScenarioInput,
        analysis: Any,
        profiles: list[CompetitorProfile],
        competitor_names: list[str],
        competitor_basics: list[dict],
        discovered_urls: list[str],
        max_retries: int = 2,
        max_tokens: int = 8192,
    ) -> dict:
        """S5 Phase 2a：数据层 LLM 调用，产出 vendor_profiles + perceptual_map + strategy_canvas。

        失败时回灌增强错误反馈重试，最多 max_retries 次。
        失败超限直接 raise ValidationError，由调用方决定是否走 WriterRouteToWriter。
        """
        from src.agents.prompts.writer.payload import S5_SPLIT_PROMPTS
        from src.schemas.scenarios.s5 import (
            PerceptualMap,
            S5VendorProfile,
            StrategyCanvas,
        )

        system_prompt = S5_SPLIT_PROMPTS["phase2a"]
        base_user_prompt = self._build_phase2_user_prompt(
            "S5",
            scenario_input,
            analysis,
            profiles,
            None,  # competitor_recommendations: S5 无推荐路径
            competitor_names,
            competitor_basics,
            discovered_urls,
        )
        last_error_summary: str | None = None

        for attempt in range(max_retries + 1):
            current_user_prompt = base_user_prompt
            if last_error_summary:
                current_user_prompt = (
                    f"{base_user_prompt}\n\n【上次校验失败，请逐条修复】\n{last_error_summary}"
                )

            raw = await self._llm_call_with_quota(
                system_prompt, current_user_prompt, max_tokens=max_tokens
            )

            try:
                # 逐模块校验
                for vp in raw.get("vendor_profiles", []):
                    S5VendorProfile(**vp)
                PerceptualMap(**raw.get("perceptual_map", {}))
                StrategyCanvas(**raw.get("strategy_canvas", {}))
                logger.info("[writer] S5 phase 2a 数据层校验通过")
                return raw
            except ValidationError as e:
                if attempt >= max_retries:
                    raise
                last_error_summary = self._serialize_validation_error_enhanced(
                    e, max_chars=2000
                )
                logger.warning(
                    "[writer] S5 phase 2a ValidationError 重试: %s",
                    last_error_summary[:400].replace("\n", " | "),
                )

    async def _call_s5_phase2b(
        self,
        *,
        phase2a_output: dict,
        scenario_input: ScenarioInput,
        analysis: Any,
        discovered_urls: list[str],
        max_retries: int = 2,
        max_tokens: int = 8192,
    ) -> dict:
        """S5 Phase 2b：战略层 LLM 调用，产出 errc_grid + blue_ocean_move + positioning_statement + category_strategy。

        phase2a_output 提供 competitive_factors 名称 + vendor_names 作为只读上下文。
        blue_ocean_move 是 Optional——LLM 省略或返回空 dict 都接受。
        """
        from src.agents.prompts.writer.payload import S5_SPLIT_PROMPTS
        from src.schemas.scenarios.s5 import (
            BlueOceanMove,
            CategoryStrategy,
            ERRCGrid,
            PositioningStatement,
        )

        system_prompt = S5_SPLIT_PROMPTS["phase2b"]

        # 构建 phase2a 上下文摘要
        factors = [
            f.get("name", "")
            for f in phase2a_output.get("strategy_canvas", {}).get("competitive_factors", [])
        ]
        vendor_names = [
            vp.get("competitor_name", "")
            for vp in phase2a_output.get("vendor_profiles", [])
        ]
        phase2a_context = (
            f"competitive_factors: {factors}\nvendor_names: {vendor_names}"
        )

        base_user_prompt = (
            f"=== 前序阶段产出 ===\n{phase2a_context}\n\n"
            + self._build_phase2_user_prompt(
                "S5",
                scenario_input,
                analysis,
                [],  # profiles：phase 2b 不需要重复传 profiles 摘要
                None,  # competitor_recommendations
                vendor_names,
                [{"name": n} for n in vendor_names],
                discovered_urls,
            )
        )
        last_error_summary: str | None = None

        for attempt in range(max_retries + 1):
            current_user_prompt = base_user_prompt
            if last_error_summary:
                current_user_prompt = (
                    f"{base_user_prompt}\n\n【上次校验失败，请逐条修复】\n{last_error_summary}"
                )

            raw = await self._llm_call_with_quota(
                system_prompt, current_user_prompt, max_tokens=max_tokens
            )

            try:
                # 逐模块校验（blue_ocean_move Optional：空 dict / 缺失都跳过校验）
                if raw.get("errc_grid"):
                    ERRCGrid(**raw["errc_grid"])
                if raw.get("blue_ocean_move"):
                    BlueOceanMove(**raw["blue_ocean_move"])
                PositioningStatement(**raw.get("positioning_statement", {}))
                CategoryStrategy(**raw.get("category_strategy", {}))
                logger.info("[writer] S5 phase 2b 战略层校验通过")
                return raw
            except ValidationError as e:
                if attempt >= max_retries:
                    raise
                last_error_summary = self._serialize_validation_error_enhanced(
                    e, max_chars=2000
                )
                logger.warning(
                    "[writer] S5 phase 2b ValidationError 重试: %s",
                    last_error_summary[:400].replace("\n", " | "),
                )

    def _merge_s5_payload(self, phase2a: dict, phase2b: dict) -> dict:
        """合并 S5 phase 2a + 2b 为完整的 S5PositioningPayload dict。

        - 补充 scenario_type="S5"
        - blue_ocean_move Optional：phase2b 有则带上，无则不加
        - artifact_id 缺失自动补占位（避免 ArtifactBase 校验失败）
        """
        merged = {
            "scenario_type": "S5",
            "vendor_profiles": phase2a.get("vendor_profiles", []),
            "perceptual_map": phase2a.get("perceptual_map", {}),
            "strategy_canvas": phase2a.get("strategy_canvas", {}),
            "errc_grid": phase2b.get("errc_grid", {}),
            "positioning_statement": phase2b.get("positioning_statement", {}),
            "category_strategy": phase2b.get("category_strategy", {}),
        }
        if phase2b.get("blue_ocean_move"):
            merged["blue_ocean_move"] = phase2b["blue_ocean_move"]

        for key in ("perceptual_map", "strategy_canvas", "errc_grid", "blue_ocean_move"):
            value = merged.get(key)
            # blue_ocean_move 是 Optional——不存在就跳过
            if isinstance(value, dict) and not value.get("artifact_id"):
                value["artifact_id"] = f"{key}_auto"

        return merged

    async def _call_s5_phase2_split(
        self,
        *,
        scenario_input: ScenarioInput,
        analysis: Any,
        profiles: list[CompetitorProfile],
        competitor_names: list[str],
        competitor_basics: list[dict],
        discovered_urls: list[str],
        warnings: list[str],
    ):
        """S5 专用：phase 2a + 2b 拆分调用 → merge → normalize → 实例化。"""
        phase2a_raw = await self._call_s5_phase2a(
            scenario_input=scenario_input,
            analysis=analysis,
            profiles=profiles,
            competitor_names=competitor_names,
            competitor_basics=competitor_basics,
            discovered_urls=discovered_urls,
        )

        phase2b_raw = await self._call_s5_phase2b(
            phase2a_output=phase2a_raw,
            scenario_input=scenario_input,
            analysis=analysis,
            discovered_urls=discovered_urls,
        )

        merged = self._merge_s5_payload(phase2a_raw, phase2b_raw)

        # Normalize（仅 merge 后运行一次，与现有行为一致）
        discovered_set: set[str] = set(discovered_urls)
        cleaned = normalize_for_scenario(
            "S5", merged, discovered_urls=discovered_set, warnings=warnings
        )

        payload_model = S5PositioningPayload(**cleaned)
        logger.info(
            "[writer] S5 phase 2 拆分完成: vendor=%d, factors=%d, dropped_warnings=%d",
            len(payload_model.vendor_profiles),
            len(payload_model.strategy_canvas.competitive_factors),
            len(warnings),
        )
        return payload_model

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
        max_retries: int = 2,  # [fix5] 1→2: LLM 一次只能修一两个字段错位，多给一次机会逐次修正
        max_tokens: int = 12288,
    ):
        """Phase 2 LLM call → normalize → 注入 → 实例化场景 Payload schema。

        [I1 修复] ValidationError 时回灌错误摘要重试 1 次（spec v3 行 254-256）。
        重试也走 _llm_call_with_quota，受熔断保护。

        [2026-06-16 优化] S5 单次输出复杂度过高，走拆分路径（phase 2a + 2b 串行）。
        其他场景保持原有单次调用路径。
        """
        if scenario == "S5":
            return await self._call_s5_phase2_split(
                scenario_input=scenario_input,
                analysis=analysis,
                profiles=profiles,
                competitor_names=competitor_names,
                competitor_basics=competitor_basics,
                discovered_urls=discovered_urls,
                warnings=warnings,
            )

        base_user_prompt = self._build_phase2_user_prompt(
            scenario,
            scenario_input,
            analysis,
            profiles,
            competitor_recommendations,
            competitor_names,
            competitor_basics,
            discovered_urls,
            prior_report_data=prior_report_data,
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
                last_error_summary = self._serialize_validation_error_enhanced(e, max_chars=1500)
                # 把摘要落 log 便于诊断（log 只取前 400 字防爆）
                logger.warning(
                    "[writer] phase 2 ValidationError 重试 1 次, 错误摘要: %s",
                    last_error_summary[:400].replace("\n", " | "),
                )

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

    @staticmethod
    def _prior_is_usable(prior_report_data: Optional[dict]) -> bool:
        """[#3] 判断 prior 报告是否真正可用（能做 diff）。

        prior_report_data 为 None（文件丢失/JSON 失败）或 scenario/schema_version 不匹配 → False。
        phase1/phase2 mode_hint 与 _inject_s4_prior_diff 三处统一用此判空，避免判错对象导致
        「prompt 说增量但 schema 走首次」的失败循环。
        """
        if not prior_report_data or not isinstance(prior_report_data, dict):
            return False
        prior_meta = prior_report_data.get("metadata", {}) or {}
        return (
            prior_meta.get("scenario") == "S4"
            and prior_meta.get("schema_version") == "2.0"
        )

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

        # [#3] 首次监控模式：prior 不可用（丢失/损坏/schema 不匹配）→ 不写 prior_trace_id，直接返回
        if not self._prior_is_usable(prior_report_data):
            if prior_report_data:
                logger.warning(
                    "[writer] S4 prior 报告不可用（scenario/schema_version 不匹配），降级为首次监控"
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
        retry_error_hint: str | None = None,
        feedback_issues: list | None = None,
    ) -> AnalysisSection:
        """[v3-R18] Semaphore 限速；[v3-R04] 走 _llm_call_with_quota 不绕熔断。

        失败（LLM 异常 / Pydantic ValidationError）让其向上抛——caller 用
        asyncio.gather(return_exceptions=True) 接住后回 _build_placeholder_section。

        [C5 carry-over] Semaphore scope 仅包裹 LLM 调用本身——ctx 收集 / JSON 序列化 / format prompt
        都是纯 CPU 工作，不应占用并发名额（否则 N>concurrency 时纯 CPU 也被串行化）。
        """
        _ = discovered_urls  # 保留参数兼容性，实际用 self._grouped_urls

        # 按 [v3-R20] SECTION_CONTEXT_MAP 取本 section 应吃的字段（CPU 工作，semaphore 外）
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

        # NARRATIVE_TEMPLATE 当前是"角色+上下文+输出契约"三合一形态（见 narrative/_common.py），
        # 整体当 system 给；user 仅作为 chat-completion 必需的触发消息，无实际语义。
        # 优化项：未来把 context 部分剥到 user 侧（B4 prompts 重构）。
        system_prompt = NARRATIVE_TEMPLATE.format(
            section_type=section_type,
            section_label=section_label,
            section_focus_hint=section_focus,
            scenario=scenario,
            section_id_hint=section_id_hint,
            context_payload=ctx_json,
        )
        # 按竞品分组的溯源 URL + 引用规则
        if self._grouped_urls:
            url_section = "\n".join(
                f"- {name}: {', '.join(urls)}"
                for name, urls in self._grouped_urls.items()
            )
            system_prompt += (
                f"\n\n【溯源引用规则】\n"
                f"可用 URL（按竞品归属）：\n{url_section}\n\n"
                f"规则：\n"
                f"1. 论述哪个竞品时，source_refs 只能从该竞品对应的 URL 中选取\n"
                f"2. 尽量为每个事实性论断（产品功能、市场数据、用户反馈等）附上至少 1 个 source_ref\n"
                f"3. 找不到对应 URL 时 source_refs 留空 []，绝不编造、绝不跨竞品引用"
            )

        if feedback_issues:
            issue_lines = []
            for iss in feedback_issues:
                if getattr(iss, "dimension", None) == "evidence":
                    issue_lines.append(f"- {iss.field}: {iss.reason} 建议：{iss.suggestion}")
            if issue_lines:
                system_prompt += (
                    "\n\n【质检打回：以下引用存在问题，请修正】\n"
                    + "\n".join(issue_lines)
                )

        if retry_error_hint:
            system_prompt += f"\n\n【上次生成失败，请修复】\n{retry_error_hint}"

        user_prompt = "请基于上述上下文生成本节 JSON。"

        # 仅 LLM 调用进 semaphore，CPU 序列化在外面
        async with self._narrative_sem:
            raw = await self._llm_call_with_quota(
                system_prompt, user_prompt, max_tokens=12288
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
        feedback_issues: list | None = None,
    ) -> tuple[list[AnalysisSection], list[str]]:
        """[v3-R05] [v3-R12] [v3-R18] 并行 narrative + 占位降级 + 半数闸门。

        - asyncio.gather(return_exceptions=True) 接住单 section 失败
        - 失败回 _build_placeholder_section + warnings 加 placeholder_section:{type}:{ExcName}
        - 失败数 ≥ ⌈expected_n / 2⌉ → raise WriterRouteToCollector 触发 graph 回 collector
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
                    feedback_issues=feedback_issues,
                )
                for st in section_types
            ),
            return_exceptions=True,
        )

        # 首跑失败的 section 收集起来做一轮重试
        retry_indices: list[int] = []
        first_pass_results: list[AnalysisSection | Exception] = []
        for i, (st, r) in enumerate(zip(section_types, results)):
            # [#1] 路由异常（WriterRouteToEnd/Collector/Writer）必须冒泡到 builder，
            # 不能被 gather(return_exceptions=True) 当普通 section 失败吞掉降级
            if isinstance(r, (WriterRouteToEnd, WriterRouteToCollector, WriterRouteToWriter)):
                raise r
            if isinstance(r, Exception):
                retry_indices.append(i)
                logger.info("[writer] phase 3 section %s 首次失败，排队重试: %s", st, type(r).__name__)
            first_pass_results.append(r)

        # 逐个重试失败的 section（串行，避免再次并发压力）
        for i in retry_indices:
            st = section_types[i]
            first_err = first_pass_results[i]
            error_hint = f"{type(first_err).__name__}: {str(first_err)[:500]}" if isinstance(first_err, Exception) else None
            try:
                retry_result = await self._phase3_one_section(
                    scenario=scenario,
                    section_type=st,
                    outline=outline,
                    payload_dict=payload_dict,
                    analysis=analysis,
                    scenario_input=scenario_input,
                    discovered_urls=discovered_urls,
                    retry_error_hint=error_hint,
                    feedback_issues=feedback_issues,
                )
                first_pass_results[i] = retry_result
                logger.info("[writer] phase 3 section %s 重试成功", st)
            except (WriterRouteToEnd, WriterRouteToCollector, WriterRouteToWriter) as retry_err:
                # [#1] 重试中触发路由异常也必须冒泡，不被 except Exception 吞
                logger.warning(
                    "[writer] phase 3 section %s 重试触发路由异常，冒泡: %s",
                    st, type(retry_err).__name__,
                )
                raise
            except Exception as retry_err:
                logger.warning("[writer] phase 3 section %s 重试仍失败: %s", st, type(retry_err).__name__)

        # 汇总最终结果
        sections: list[AnalysisSection] = []
        failed_n = 0
        for st, r in zip(section_types, first_pass_results):
            if isinstance(r, Exception):
                sections.append(_build_placeholder_section(st, payload_dict))
                warnings.append(f"placeholder_section:{st}:{type(r).__name__}")
                failed_n += 1
                logger.warning(
                    "[writer] phase 3 section %s 重试后仍失败 → 占位降级: %s",
                    st,
                    type(r).__name__,
                )
            else:
                sections.append(r)

        # [v3-R05] 半数闸门：失败数 ≥ ⌈expected_n / 2⌉ 即 raise
        threshold = (expected_n + 1) // 2
        if failed_n >= threshold:
            raise WriterRouteToCollector(
                f"phase 3 失败数 {failed_n} >= {threshold}（expected={expected_n}），"
                f"触发半数闸门，建议回 collector 重新采集"
            )

        logger.info(
            "[writer] phase 3 narrative 完成: %d/%d 成功",
            expected_n - failed_n,
            expected_n,
        )
        return sections, warnings

    # ========== Phase 4: assemble ==========

    def _phase4_assemble(
        self,
        *,
        scenario: str,
        scenario_input: ScenarioInput,
        outline: dict,
        payload_model: Any,
        sections: list[AnalysisSection],
        profiles: list[CompetitorProfile],
        analysis: Any,
        trace_id: str,
        warnings: list[str],
        competitor_recommendations: Any,
        discovered_urls: list[str],
        competitor_names: list[str],
        payload_dict: dict | None = None,
    ) -> BaseReport:
        """[Q1=C][v3-R06/R07/R08/R11/R13/R19/R24] 代码合成 BaseReport，0 LLM 调用。

        9 步：SWOT 透传 → URL 双通道聚合 → 全字段 DataSource → 空集合兜底 raise →
        confidence_level 派生 → uuid fallback report_id → ReportMetadata →
        scope.competitors S2 union → BaseReport 实例化。

        payload_dict：可选，调用方已 dump 过的 payload_model.model_dump() 结果。
        提供时复用避免重复序列化（性能优化，对大 S2 payload 可省 50-100ms）。
        """
        _ = competitor_names  # 为对外签名稳定保留；scope.competitors 来自 scenario_input + recommender

        # ----- 步骤 1：SWOT 透传（[Q1=C] 决策）-----
        analysis_swot = getattr(analysis, "swot", None)
        if analysis_swot is not None:
            swot = analysis_swot
        else:
            swot = _build_placeholder_swot()
            warnings.append("placeholder_swot")

        # ----- 步骤 2：URL 双通道聚合 + 幻觉过滤（[v3-R07/R08] + [v3-R06]）-----
        # 注意：SWOT 也吃进 dump（SwotEntry.source_refs 也是 SourceRef-like，参与回收）
        discovered_set: set[str] = set(discovered_urls)
        # 复用 phase 3 已 dump 过的 payload_dict，避免再 dump 一次
        payload_for_dump = payload_dict if payload_dict is not None else payload_model.model_dump()
        dump = {
            "outline": outline,
            "payload": payload_for_dump,
            "sections": [s.model_dump() for s in sections],
            "swot": swot.model_dump(),
        }
        collected_refs, collected_bare = _collect_source_refs_recursive(dump)

        # 全字段去重 by url，过滤幻觉（不在 discovered 的 URL 直接弃）
        ref_by_url: dict[str, dict] = {}
        for r in collected_refs:
            if r["url"] in discovered_set and r["url"] not in ref_by_url:
                ref_by_url[r["url"]] = r

        # 裸 url 字段补充：构造最小 SourceRef（title/accessed_at 留空）
        for u in collected_bare:
            if u in discovered_set and u not in ref_by_url:
                ref_by_url[u] = {
                    "url": u,
                    "title": "",
                    "accessed_at": None,
                    "source_type": "other",
                }

        final_refs = list(ref_by_url.values())

        # [fix8] accessed_at 兜底：取 profiles 里 collected_at 最晚的日期作为缺省值
        # ProfileMetadata.collected_at 是 ISO 字符串（如 "2026-06-08T00:00:00"），
        # 取日期部分塞给 DataSource.accessed_at（date 类型）。
        fallback_accessed_at = _derive_fallback_accessed_at(profiles)

        # ----- 步骤 3：[v3-R11] 全字段 DataSource 构造 -----
        data_sources_models = [
            DataSource(
                url=r["url"],
                title=r["title"],
                accessed_at=r["accessed_at"] or fallback_accessed_at,
                source_type=r["source_type"],
                confidence="medium",
            )
            for r in sorted(final_refs, key=lambda x: x["url"])
        ]

        # ----- 步骤 4：[v3-R06] final_urls 空集合时 raise（让 graph 回 writer 重试）-----
        if not data_sources_models:
            raise WriterRouteToWriter(
                "writer phase 4: 报告内 0 个 source_refs 引用了 profiles 中的真实 URL，"
                "无法构造合规 ReportMetadata（data_sources min_length=1）。"
                "建议 graph 回 writer 重试。"
            )

        # ----- 步骤 5：[v3-R13] confidence_level 派生 + ZeroDivisionError 兜底 -----
        if profiles:
            avg_completeness = sum(
                p.metadata.completeness_score for p in profiles
            ) / len(profiles)
        else:
            avg_completeness = 0.0

        if avg_completeness >= 0.8:
            confidence_level = "high"
        elif avg_completeness >= 0.5:
            confidence_level = "medium"
        else:
            confidence_level = "low"

        # ----- 步骤 6：[v3-R24] uuid fallback report_id（trace_id 空时防碰撞）-----
        report_id_seed = trace_id or uuid.uuid4().hex
        report_id = f"r-{report_id_seed[:8]}"

        # ----- 步骤 7：构造 ReportMetadata -----
        metadata = ReportMetadata(
            report_id=report_id,
            trace_id=trace_id,
            scenario=scenario,
            publication_date=date.today(),
            data_sources=data_sources_models,
            confidence_level=confidence_level,
            contributing_agents=["collector", "analyzer", "writer"],
            warnings=warnings,
            citation_format="GB/T 7714-2015",  # 中国国家标准引文格式（修 inspector minor 报警）
            quality_score_calculation_note=(
                "confidence_level 由采集 completeness 平均值派生（writer 阶段一次性）"
            ),
        )

        # ----- 步骤 8：[v3-R19] scope.competitors S2 union -----
        if scenario == "S2":
            user_names = [c.name for c in scenario_input.competitors]
            rec_names = (
                [r.name for r in competitor_recommendations.recommended_competitors]
                if competitor_recommendations is not None
                else []
            )
            seen: set[str] = set()
            scope_competitors: list[str] = []
            for name in user_names + rec_names:
                if name and name not in seen:
                    seen.add(name)
                    scope_competitors.append(name)
            if not scope_competitors:
                raise WriterRouteToEnd(
                    "S2 scope.competitors 空：用户未填且 recommender 也未产出"
                )
        elif scenario_input.competitors:
            scope_competitors = [c.name for c in scenario_input.competitors]
        else:
            raise WriterRouteToEnd(
                f"scope.competitors 无法构造：scenario={scenario}, competitors=[]，"
                f"ScenarioInput model_validator 应该先一步 raise"
            )

        # ----- 步骤 9：构造 BaseReport（outline 字段映射 + Pydantic 实例化）-----
        outline_scope = outline.get("scope", {}) or {}
        outline_meth = outline.get("methodology", {}) or {}
        outline_es = outline.get("executive_summary", {}) or {}

        scope = ReportScope(
            competitors=scope_competitors,
            time_window=outline_scope.get("time_window", "未指定"),
            regions=outline_scope.get("regions", []) or [],
            exclusions=outline_scope.get("exclusions", []) or [],
        )
        executive_summary = ExecutiveSummary(**outline_es)
        # [fix11] data_collection_approach 改为代码合成，覆盖 LLM 输出（无论 LLM 写没写够 200 字符）
        outline_meth = dict(outline_meth)  # 浅拷贝避免污染调用方
        outline_meth["data_collection_approach"] = _build_data_collection_approach(
            profiles=profiles,
            scenario=scenario,
            discovered_url_count=len(discovered_urls),
        )
        methodology = Methodology(**outline_meth)

        # [06-09 source_refs 透传修复] outline phase 1 LLM 不写 source_refs（prompt 故意不要求）
        # 但 schema 允许空 → 透传到最终报告 → inspector 报"全空缺溯源" major issue。
        # 修法：从 final_refs 池里轮换分配 SourceRef 给每个无 ref 的 Finding/Recommendation。
        # 轮换而非全用前 N 条——避免所有结论指向同一来源被 inspector 抓"引用与结论不匹配"。
        # 每条 item 取 2 条 ref（覆盖度 + 不膨胀）。
        ref_pool = [
            {"url": r["url"], "title": r["title"], "accessed_at": r["accessed_at"], "source_type": r["source_type"]}
            for r in final_refs
        ]

        def _inject_default_refs(items: list[dict]) -> list[dict]:
            if not ref_pool:
                return items
            n = len(ref_pool)
            for idx, it in enumerate(items):
                if not it.get("source_refs"):
                    # 轮换：每条 item 从池里取 2 条（idx*2, idx*2+1），mod n 防越界
                    it["source_refs"] = [
                        ref_pool[(idx * 2) % n],
                        ref_pool[(idx * 2 + 1) % n],
                    ] if n >= 2 else [ref_pool[0]]
            return items

        key_findings = [
            Finding(**f) for f in _inject_default_refs(outline.get("key_findings", []) or [])
        ]
        recommendations = [
            Recommendation(**r) for r in _inject_default_refs(outline.get("recommendations", []) or [])
        ]

        report = BaseReport(
            metadata=metadata,
            title=outline.get("title", ""),
            subtitle=outline.get("subtitle"),
            at_a_glance=outline.get("at_a_glance", []) or [],
            executive_summary=executive_summary,
            background=outline.get("background", ""),
            scope=scope,
            methodology=methodology,
            key_findings=key_findings,
            analysis_sections=sections,
            swot=swot,
            conclusions=outline.get("conclusions", ""),
            recommendations=recommendations,
            appendix=Appendix(glossary=_build_glossary(scenario)),
            scenario_payload=payload_model,
        )
        return report
