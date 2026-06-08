"""S3 定价策略场景规整器"""
from typing import Optional

from src.agents.normalizers._common import (
    CONFIDENCE_MAP, INTENSITY_MAP, drop_keys, each, map_enum,
)

PRICING_MODEL_MAP = {
    "per_seat": "per_seat",
    "flat_rate": "flat_rate",
    "usage_based": "usage_based",
    "hybrid": "hybrid",
    "freemium": "freemium",
    "platform_fee": "platform_fee",
    "unknown": "unknown",
    "按席位": "per_seat",
    "按人头": "per_seat",
    "包年包月": "flat_rate",
    "按量计费": "usage_based",
    "按用量": "usage_based",
    "免费增值": "freemium",
    "平台抽成": "platform_fee",
}

POSITION_MAP = {
    "good": "good", "better": "better", "best": "best",
    "enterprise": "enterprise", "free": "free",
    "免费": "free", "免费版": "free",
    "基础": "good", "基础版": "good",
    "标准": "better", "标准版": "better",
    "高级": "best", "高级版": "best", "旗舰": "best",
    "企业": "enterprise", "企业版": "enterprise",
}

BILLING_UNIT_MAP = {
    "per_seat": "per_seat",
    "flat_rate": "flat_rate",
    "usage_based": "usage_based",
    "tier_subscription": "tier_subscription",
    "按席位": "per_seat",
    "按用量": "usage_based",
    "套餐订阅": "tier_subscription",
    "固定": "flat_rate",
}

WTP_METHOD_MAP = {
    "conjoint_analysis": "conjoint_analysis",
    "van_westendorp": "van_westendorp",
    "gabor_granger": "gabor_granger",
    "interviews": "interviews",
    "ab_testing": "ab_testing",
    "proxy_from_competitor_pricing": "proxy_from_competitor_pricing",
    "联合分析": "conjoint_analysis",
    "访谈": "interviews",
    "ab测试": "ab_testing",
    "竞品代理": "proxy_from_competitor_pricing",
}

ARR_BASIS_MAP = {
    "measured_pilot": "measured_pilot",
    "competitor_benchmark": "competitor_benchmark",
    "industry_estimate": "industry_estimate",
    "llm_inferred": "llm_inferred",
    "试点实测": "measured_pilot",
    "竞品对标": "competitor_benchmark",
    "行业估算": "industry_estimate",
    "推断": "llm_inferred",
    "AI推断": "llm_inferred",
}

FREE_PLAN_MAP = {
    "freemium": "freemium",
    "free_trial": "free_trial",
    "no_free_plan": "no_free_plan",
    "免费增值": "freemium",
    "免费试用": "free_trial",
    "无免费版": "no_free_plan",
}

CURRENCY_MAP = {
    "CNY": "CNY", "USD": "USD", "EUR": "EUR", "JPY": "JPY", "unknown": "unknown",
    "人民币": "CNY", "美元": "USD", "欧元": "EUR", "日元": "JPY",
    "￥": "CNY", "$": "USD", "€": "EUR", "¥": "JPY",
}


def _normalize_pricing_baseline(pb: dict) -> None:
    if "current_pricing_model" in pb:
        pb["current_pricing_model"] = map_enum(
            pb["current_pricing_model"], PRICING_MODEL_MAP, default="unknown"
        )


def _normalize_value_drivers(items: list) -> None:
    for vd in each(items):
        if "importance" in vd:
            vd["importance"] = map_enum(vd["importance"], INTENSITY_MAP, default="medium")


def _normalize_tier(tier: dict) -> None:
    if "position" in tier:
        tier["position"] = map_enum(tier["position"], POSITION_MAP, default="better")
    if "billing_unit" in tier:
        tier["billing_unit"] = map_enum(tier["billing_unit"], BILLING_UNIT_MAP, default="flat_rate")
    if "currency" in tier:
        tier["currency"] = map_enum(tier["currency"], CURRENCY_MAP, default="unknown")


def _has_valid_source_refs(item: dict) -> bool:
    """[v3-R14] 判断条目是否有 ≥1 个非空 source_ref（含 url 字段非空字符串）"""
    refs = item.get("source_refs")
    if not isinstance(refs, list) or not refs:
        return False
    for r in refs:
        if isinstance(r, dict) and r.get("url"):
            return True
    return False


def _normalize_s3_raw(
    raw: dict,
    *,
    discovered_urls: Optional[set[str]] = None,
    warnings: Optional[list[str]] = None,
) -> dict:
    # pricing_baseline
    pb = raw.get("pricing_baseline")
    if isinstance(pb, dict):
        _normalize_pricing_baseline(pb)

    # value_drivers
    _normalize_value_drivers(raw.get("value_drivers"))

    # wtp_research
    wtp = raw.get("wtp_research")
    if isinstance(wtp, dict):
        if "method" in wtp:
            wtp["method"] = map_enum(wtp["method"], WTP_METHOD_MAP, default="proxy_from_competitor_pricing")
        if "confidence" in wtp:
            wtp["confidence"] = map_enum(wtp["confidence"], CONFIDENCE_MAP, default="low")
        # [v3-R15] method=proxy_from_competitor_pricing 强制 confidence=low（不论 LLM 填了什么）
        if wtp.get("method") == "proxy_from_competitor_pricing":
            wtp["confidence"] = "low"
            # 同步补 limitations 占位（schema model_validator 要求）
            if not wtp.get("limitations"):
                wtp["limitations"] = "基于公开竞品定价反推，未做正式 WTP 调研（normalizer 自动补占位）"

    # packaging.tiers (RecommendedPriceTier)
    pkg = raw.get("packaging")
    if isinstance(pkg, dict):
        for tier in each(pkg.get("tiers")):
            _normalize_tier(tier)

    # competitive_pricing_matrix.tiers (ObservedCompetitorTier)
    # [v3-R14] 删除空 source_refs 的 ObservedCompetitorTier 与整条 CompetitorPricing
    cp_list = raw.get("competitive_pricing_matrix")
    if isinstance(cp_list, list):
        cleaned_cp_list = []
        dropped_tier_count = 0
        for cp in cp_list:
            if not isinstance(cp, dict):
                continue
            if "pricing_model" in cp:
                cp["pricing_model"] = map_enum(cp["pricing_model"], PRICING_MODEL_MAP, default="unknown")
            if "free_plan_strategy" in cp and cp["free_plan_strategy"] is not None:
                cp["free_plan_strategy"] = map_enum(
                    cp["free_plan_strategy"], FREE_PLAN_MAP, default="no_free_plan"
                )
            # 过滤无 source_refs 的 ObservedCompetitorTier
            tiers = cp.get("tiers")
            if isinstance(tiers, list):
                cleaned_tiers = []
                for tier in tiers:
                    if not isinstance(tier, dict):
                        continue
                    _normalize_tier(tier)
                    if _has_valid_source_refs(tier):
                        cleaned_tiers.append(tier)
                    else:
                        dropped_tier_count += 1
                cp["tiers"] = cleaned_tiers
            # CompetitorPricing 自身 source_refs 也要 ≥1
            if _has_valid_source_refs(cp) and cp.get("tiers"):
                cleaned_cp_list.append(cp)
            else:
                dropped_tier_count += 1
        raw["competitive_pricing_matrix"] = cleaned_cp_list
        if dropped_tier_count and warnings is not None:
            warnings.append(
                f"dropped_unverified_entries:s3.competitive_pricing_matrix:{dropped_tier_count}"
            )

    # pricing_page_audit: 删 computed_field overall_score_pct
    for pa in each(raw.get("pricing_page_audit")):
        drop_keys(pa, ["overall_score_pct"])

    # recommendations_summary
    rs = raw.get("recommendations_summary")
    if isinstance(rs, dict):
        if "expected_arr_uplift_basis" in rs:
            rs["expected_arr_uplift_basis"] = map_enum(
                rs["expected_arr_uplift_basis"], ARR_BASIS_MAP, default="llm_inferred"
            )
        for risk in each(rs.get("main_risks")):
            if "likelihood" in risk:
                risk["likelihood"] = map_enum(risk["likelihood"], INTENSITY_MAP, default="medium")
            if "impact" in risk:
                risk["impact"] = map_enum(risk["impact"], INTENSITY_MAP, default="medium")

    return raw
