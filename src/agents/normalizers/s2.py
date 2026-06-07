"""S2 市场进入场景规整器"""
from src.agents.normalizers._common import (
    CONFIDENCE_MAP, DIRECTION_MAP, INTENSITY_MAP, drop_keys, each, map_enum,
)

MARKET_ROLE_MAP = {
    "incumbent": "incumbent",
    "challenger": "challenger",
    "emerging": "emerging",
    "niche": "niche",
    "substitute": "substitute",
    "leader": "incumbent",
    "在位者": "incumbent",
    "在位玩家": "incumbent",
    "头部": "incumbent",
    "挑战者": "challenger",
    "follower": "challenger",
    "新兴": "emerging",
    "新兴玩家": "emerging",
    "small": "niche",
    "细分": "niche",
    "替代品": "substitute",
}

CONCENTRATION_MAP = {
    "fragmented": "fragmented",
    "moderate": "moderate",
    "concentrated": "concentrated",
    "分散": "fragmented",
    "中等": "moderate",
    "集中": "concentrated",
    "高度集中": "concentrated",
}

TIME_HORIZON_MAP = {
    "short_term": "short_term", "mid_term": "mid_term", "long_term": "long_term",
    "短期": "short_term", "中期": "mid_term", "长期": "long_term",
}

IMPACT_ENTRY_MAP = {
    "positive": "positive", "negative": "negative", "mixed": "mixed",
    "正面": "positive", "利好": "positive",
    "负面": "negative", "不利": "negative",
    "混合": "mixed", "中性": "mixed",
}

ADDRESSABILITY_MAP = {
    "easy": "easy", "moderate": "moderate", "hard": "hard",
    "容易": "easy", "中等": "moderate", "困难": "hard",
}

ENTRY_MODE_MAP = {
    "direct_competition": "direct_competition", "niche_focus": "niche_focus",
    "differentiation": "differentiation", "partnership": "partnership",
    "acquisition": "acquisition", "wait_and_see": "wait_and_see",
    "正面竞争": "direct_competition",
    "细分聚焦": "niche_focus", "聚焦": "niche_focus",
    "差异化": "differentiation",
    "合作": "partnership",
    "收购": "acquisition",
    "观望": "wait_and_see",
}

PESTEL_IMPACT_MAP = {
    "opportunity": "opportunity", "threat": "threat", "neutral": "neutral",
    "机会": "opportunity", "威胁": "threat", "中性": "neutral",
}

SELECTION_METHOD_MAP = {
    "search_api_top_n": "search_api_top_n",
    "llm_inference": "llm_inference",
    "hybrid": "hybrid",
    "search": "search_api_top_n",
    "搜索": "search_api_top_n",
    "推断": "llm_inference",
    "混合": "hybrid",
}


def _normalize_s2_raw(raw: dict) -> dict:
    # five_forces 五力 intensity
    ff = raw.get("five_forces")
    if isinstance(ff, dict):
        for force_key in ("new_entrants", "supplier_power", "buyer_power",
                          "substitute_threat", "competitive_rivalry"):
            force = ff.get(force_key)
            if isinstance(force, dict) and "intensity" in force:
                force["intensity"] = map_enum(force["intensity"], INTENSITY_MAP, default="medium")

    # players.market_role
    for p in each(raw.get("players")):
        if "market_role" in p:
            p["market_role"] = map_enum(p["market_role"], MARKET_ROLE_MAP, default="niche")

    # market_concentration
    if "market_concentration" in raw:
        raw["market_concentration"] = map_enum(
            raw["market_concentration"], CONCENTRATION_MAP, default="moderate"
        )

    # consumer_segments.addressability
    for seg in each(raw.get("consumer_segments")):
        if "addressability" in seg:
            seg["addressability"] = map_enum(
                seg["addressability"], ADDRESSABILITY_MAP, default="moderate"
            )

    # key_trends: direction / time_horizon / impact_on_entry
    for t in each(raw.get("key_trends")):
        if "direction" in t:
            t["direction"] = map_enum(t["direction"], DIRECTION_MAP, default="flat")
        if "time_horizon" in t:
            t["time_horizon"] = map_enum(t["time_horizon"], TIME_HORIZON_MAP, default="mid_term")
        if "impact_on_entry" in t:
            t["impact_on_entry"] = map_enum(t["impact_on_entry"], IMPACT_ENTRY_MAP, default="mixed")

    # entry_strategy.recommended_mode + main_risks (likelihood/impact)
    es = raw.get("entry_strategy")
    if isinstance(es, dict):
        if "recommended_mode" in es:
            es["recommended_mode"] = map_enum(
                es["recommended_mode"], ENTRY_MODE_MAP, default="niche_focus"
            )
        for risk in each(es.get("main_risks")):
            if "likelihood" in risk:
                risk["likelihood"] = map_enum(risk["likelihood"], INTENSITY_MAP, default="medium")
            if "impact" in risk:
                risk["impact"] = map_enum(risk["impact"], INTENSITY_MAP, default="medium")

    # pestel 6 维 factor
    pestel = raw.get("pestel")
    if isinstance(pestel, dict):
        for axis in ("political", "economic", "social", "technological",
                     "environmental", "legal"):
            for f in each(pestel.get(axis)):
                if "impact" in f:
                    f["impact"] = map_enum(f["impact"], PESTEL_IMPACT_MAP, default="neutral")
                if "severity" in f:
                    f["severity"] = map_enum(f["severity"], INTENSITY_MAP, default="medium")

    # competitor_recommendations
    cr = raw.get("competitor_recommendations")
    if isinstance(cr, dict):
        if "selection_method" in cr:
            cr["selection_method"] = map_enum(
                cr["selection_method"], SELECTION_METHOD_MAP, default="hybrid"
            )
        for r in each(cr.get("recommended_competitors")):
            if "confidence" in r:
                r["confidence"] = map_enum(r["confidence"], CONFIDENCE_MAP, default="medium")

    # 删 LLM 误填的 scenario_type 之外的 computed_field（S2 当前无 computed_field，留作未来扩展）
    drop_keys(raw, [])

    return raw
