"""S4 持续监控场景规整器"""
from src.agents.normalizers._common import (
    DIRECTION_MAP, INTENSITY_MAP, PRIORITY_MAP, drop_keys, each, map_enum,
)

CHANGE_TYPE_FEATURE_MAP = {
    "new_feature": "new_feature",
    "removed_feature": "removed_feature",
    "feature_updated": "feature_updated",
    "新增": "new_feature", "新功能": "new_feature",
    "下线": "removed_feature", "移除": "removed_feature",
    "更新": "feature_updated", "迭代": "feature_updated",
}

CHANGE_TYPE_PRICING_MAP = {
    "tier_added": "tier_added", "tier_removed": "tier_removed",
    "price_increased": "price_increased", "price_decreased": "price_decreased",
    "packaging_restructured": "packaging_restructured",
    "discount_changed": "discount_changed",
    "新增套餐": "tier_added", "下线套餐": "tier_removed",
    "涨价": "price_increased", "降价": "price_decreased",
    "重组套餐": "packaging_restructured", "折扣变化": "discount_changed",
}

CHANGE_TYPE_MESSAGING_MAP = {
    "headline_changed": "headline_changed",
    "positioning_shift": "positioning_shift",
    "brand_update": "brand_update",
    "campaign_launch": "campaign_launch",
    "标语变更": "headline_changed",
    "定位变化": "positioning_shift",
    "品牌升级": "brand_update",
    "活动上线": "campaign_launch",
}

NEWS_CATEGORY_MAP = {
    "funding": "funding", "partnership": "partnership", "leadership": "leadership",
    "legal": "legal", "product_launch": "product_launch", "acquisition": "acquisition",
    "ipo": "ipo", "layoff": "layoff", "other": "other",
    "融资": "funding", "合作": "partnership",
    "高管": "leadership", "法务": "legal", "诉讼": "legal",
    "产品发布": "product_launch", "收购": "acquisition",
    "上市": "ipo", "裁员": "layoff",
}

ORG_ACTION_MAP = {
    "hired": "hired", "departed": "departed", "promoted": "promoted",
    "demoted": "demoted", "joined_board": "joined_board",
    "title_changed": "title_changed", "founder_exit": "founder_exit",
    "入职": "hired", "离职": "departed", "晋升": "promoted",
    "降职": "demoted", "进入董事会": "joined_board",
    "头衔变更": "title_changed", "创始人退出": "founder_exit",
}

OPP_TYPE_MAP = {
    "abandoned_segment": "abandoned_segment",
    "product_gap": "product_gap",
    "messaging_white_space": "messaging_white_space",
    "operational_weakness": "operational_weakness",
    "被忽视细分": "abandoned_segment",
    "产品空白": "product_gap",
    "信息空白": "messaging_white_space",
    "运营薄弱": "operational_weakness",
}

OWNER_TEAM_MAP = {
    "product": "product", "marketing": "marketing", "sales": "sales",
    "exec": "exec", "engineering": "engineering", "support": "support",
    "产品": "product", "市场": "marketing", "营销": "marketing",
    "销售": "sales", "高管": "exec", "工程": "engineering",
    "研发": "engineering", "支持": "support", "客服": "support",
}

COMPLETENESS_MAP = {
    "full": "full", "partial": "partial", "empty": "empty",
    "完整": "full", "部分": "partial", "空": "empty", "无": "empty",
}

BATTLECARD_SECTION_MAP = {
    "quick_summary": "quick_summary",
    "primary_threat": "primary_threat",
    "messaging_positioning": "messaging_positioning",
    "pricing_packaging": "pricing_packaging",
    "product_strategy": "product_strategy",
    "customer_sentiment": "customer_sentiment",
    "win_loss_themes": "win_loss_themes",
    "monitoring_priorities": "monitoring_priorities",
}


def _set_baseline_default(items: list, baseline: bool) -> None:
    """list 内每个 dict 项缺 is_baseline 时填 default"""
    for item in each(items):
        item.setdefault("is_baseline", baseline)


def _normalize_change_severity(items: list) -> None:
    for item in each(items):
        if "severity" in item:
            item["severity"] = map_enum(item["severity"], INTENSITY_MAP, default="medium")


def _normalize_s4_raw(raw: dict) -> dict:
    rp = raw.get("review_period") or {}
    is_first_review = rp.get("prior_trace_id") in (None, "", "null")

    # feature_changes
    for fc in each(raw.get("feature_changes")):
        if "change_type" in fc:
            fc["change_type"] = map_enum(
                fc["change_type"], CHANGE_TYPE_FEATURE_MAP, default="feature_updated"
            )
    _normalize_change_severity(raw.get("feature_changes"))

    # pricing_changes
    for pc in each(raw.get("pricing_changes")):
        if "change_type" in pc:
            pc["change_type"] = map_enum(
                pc["change_type"], CHANGE_TYPE_PRICING_MAP, default="discount_changed"
            )
    _normalize_change_severity(raw.get("pricing_changes"))

    # messaging_changes
    for mc in each(raw.get("messaging_changes")):
        if "change_type" in mc:
            mc["change_type"] = map_enum(
                mc["change_type"], CHANGE_TYPE_MESSAGING_MAP, default="headline_changed"
            )
    _normalize_change_severity(raw.get("messaging_changes"))

    # news_events.category
    for ne in each(raw.get("news_events")):
        if "category" in ne:
            ne["category"] = map_enum(ne["category"], NEWS_CATEGORY_MAP, default="other")
    _normalize_change_severity(raw.get("news_events"))

    # org_changes.action
    for oc in each(raw.get("org_changes")):
        if "action" in oc:
            oc["action"] = map_enum(oc["action"], ORG_ACTION_MAP, default="title_changed")
    _normalize_change_severity(raw.get("org_changes"))

    # 首次监控模式：所有 change 强制 is_baseline=True
    if is_first_review:
        for key in ("feature_changes", "pricing_changes", "messaging_changes",
                    "news_events", "org_changes"):
            for item in each(raw.get(key)):
                item["is_baseline"] = True
    else:
        for key in ("feature_changes", "pricing_changes", "messaging_changes",
                    "news_events", "org_changes"):
            _set_baseline_default(raw.get(key), False)

    # threats: 删 quadrant + severity/likelihood 兜底
    for t in each(raw.get("threats")):
        drop_keys(t, ["quadrant"])
        if "severity" in t:
            t["severity"] = map_enum(t["severity"], INTENSITY_MAP, default="medium")
        if "likelihood" in t:
            t["likelihood"] = map_enum(t["likelihood"], INTENSITY_MAP, default="medium")

    # opportunities
    for op in each(raw.get("opportunities")):
        if "opportunity_type" in op:
            op["opportunity_type"] = map_enum(
                op["opportunity_type"], OPP_TYPE_MAP, default="product_gap"
            )
        if "estimated_effort" in op:
            op["estimated_effort"] = map_enum(op["estimated_effort"], INTENSITY_MAP, default="medium")
        if "expected_impact" in op:
            op["expected_impact"] = map_enum(op["expected_impact"], INTENSITY_MAP, default="medium")

    # trends 4 个方向
    trends = raw.get("trends")
    if isinstance(trends, dict):
        for k in ("sentiment_trend", "pricing_trend",
                  "release_velocity_trend", "threat_level_trend"):
            v = trends.get(k)
            if v is not None:
                trends[k] = map_enum(v, DIRECTION_MAP, default=None)

    # monitoring_actions
    for ma in each(raw.get("monitoring_actions")):
        if "owner_team" in ma:
            ma["owner_team"] = map_enum(ma["owner_team"], OWNER_TEAM_MAP, default="product")
        if "priority_tier" in ma:
            ma["priority_tier"] = map_enum(ma["priority_tier"], PRIORITY_MAP, default="important")

    # battlecards: 删 last_updated_at（computed_field）+ 各 section
    for bc in each(raw.get("battlecards")):
        drop_keys(bc, ["last_updated_at"])
        if "overall_completeness" in bc:
            bc["overall_completeness"] = map_enum(
                bc["overall_completeness"], COMPLETENESS_MAP, default="partial"
            )
        for sec in each(bc.get("sections")):
            if "section_name" in sec:
                sec["section_name"] = map_enum(
                    sec["section_name"], BATTLECARD_SECTION_MAP, default="quick_summary"
                )
            if "completeness" in sec:
                sec["completeness"] = map_enum(
                    sec["completeness"], COMPLETENESS_MAP, default="empty"
                )

    return raw
