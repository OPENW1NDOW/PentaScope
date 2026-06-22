"""枚举值翻译：英文 → "中文 (英文)" 格式。

前端 render.py、HTML exporter、Markdown exporter 共用此模块，
避免跨层依赖（backend 不应 import frontend）。
"""
from __future__ import annotations

_TRANSLATIONS: dict[str, str] = {
    "high": "高 (high)", "medium": "中 (medium)", "low": "低 (low)",
    "wave_leader": "领导者 (wave_leader)",
    "wave_strong_performer": "强劲表现者 (wave_strong_performer)",
    "wave_contender": "竞争者 (wave_contender)",
    "wave_follower": "跟随者 (wave_follower)",
    "challenger": "挑战者 (challenger)", "incumbent": "在位者 (incumbent)",
    "emerging": "新兴 (emerging)",
    "hard": "困难 (hard)", "moderate": "适中 (moderate)", "easy": "容易 (easy)",
    "up": "上升 (up)", "down": "下降 (down)", "flat": "持平 (flat)",
    "short_term": "短期 (short_term)", "mid_term": "中期 (mid_term)",
    "long_term": "长期 (long_term)",
    "mixed": "混合 (mixed)", "negative": "负面 (negative)", "positive": "正面 (positive)",
    "differentiation": "差异化 (differentiation)",
    "niche_first": "利基优先 (niche_first)",
    "cost_leadership": "成本领先 (cost_leadership)",
    "concentrated": "集中 (concentrated)", "fragmented": "分散 (fragmented)",
    "unknown": "未知 (unknown)", "freemium": "免费增值 (freemium)",
    "hybrid": "混合模式 (hybrid)", "subscription": "订阅制 (subscription)",
    "critical": "紧急 (critical)", "important": "重要 (important)",
    "consider": "可选 (consider)",
    "new_feature": "新功能 (new_feature)",
    "removed_feature": "功能下架 (removed_feature)",
    "feature_updated": "功能更新 (feature_updated)",
    "tier_added": "新增层级 (tier_added)", "tier_removed": "移除层级 (tier_removed)",
    "price_increased": "涨价 (price_increased)",
    "price_decreased": "降价 (price_decreased)",
    "packaging_restructured": "套餐重组 (packaging_restructured)",
    "discount_changed": "折扣变更 (discount_changed)",
    "headline_changed": "标语变更 (headline_changed)",
    "positioning_shift": "定位转变 (positioning_shift)",
    "brand_update": "品牌更新 (brand_update)",
    "campaign_launch": "活动上线 (campaign_launch)",
    "funding": "融资 (funding)", "partnership": "合作 (partnership)",
    "leadership": "高管变动 (leadership)", "legal": "法律/合规 (legal)",
    "product_launch": "产品发布 (product_launch)",
    "acquisition": "收购 (acquisition)", "ipo": "IPO (ipo)",
    "layoff": "裁员 (layoff)", "other": "其他 (other)",
    "hired": "入职 (hired)", "departed": "离职 (departed)",
    "promoted": "晋升 (promoted)", "demoted": "降级 (demoted)",
    "joined_board": "加入董事会 (joined_board)",
    "title_changed": "头衔变更 (title_changed)",
    "founder_exit": "创始人离开 (founder_exit)",
    "act_now": "立即行动 (act_now)", "contingency": "应急准备 (contingency)",
    "monitor": "持续监控 (monitor)", "deprioritize": "低优先 (deprioritize)",
    "product_gap": "产品差距 (product_gap)",
    "abandoned_segment": "放弃的细分市场 (abandoned_segment)",
    "messaging_white_space": "信息空白 (messaging_white_space)",
    "operational_weakness": "运营弱点 (operational_weakness)",
    "partial": "部分 (partial)", "complete": "完整 (complete)",
    "quick_summary": "快速摘要 (quick_summary)",
    "primary_threat": "核心威胁 (primary_threat)",
    "why_they_win": "为何他们赢 (why_they_win)",
    "why_we_win": "为何我们赢 (why_we_win)",
    "landmines": "竞争陷阱 (landmines)",
    "talk_track": "话术要点 (talk_track)",
    "leaders": "领导者 (leaders)", "challengers": "挑战者 (challengers)",
    "visionaries": "远见者 (visionaries)", "niche_players": "利基者 (niche_players)",
}


def _t(val) -> str:
    """翻译枚举值为「中文 (英文)」格式。非字符串或未命中则原样返回。"""
    if val is None:
        return ""
    if not isinstance(val, str):
        return str(val)
    if not val:
        return ""
    return _TRANSLATIONS.get(val, val)
