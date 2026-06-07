"""S1 功能迭代场景规整器"""
from src.agents.normalizers._common import INTENSITY_MAP, drop_keys, each, map_enum

WAVE_POSITION_MAP = {
    "wave_leader": "wave_leader",
    "wave_strong_performer": "wave_strong_performer",
    "wave_contender": "wave_contender",
    "leader": "wave_leader",
    "领导者": "wave_leader",
    "领先者": "wave_leader",
    "strong_performer": "wave_strong_performer",
    "强势表现者": "wave_strong_performer",
    "强势表现": "wave_strong_performer",
    "contender": "wave_contender",
    "竞争者": "wave_contender",
    "挑战者": "wave_contender",
}

RECOMMENDATION_MAP = {
    "build": "build",
    "skip": "skip",
    "differentiate": "differentiate",
    "做": "build", "立刻做": "build", "建造": "build",
    "跳过": "skip", "放弃": "skip", "不做": "skip",
    "差异化": "differentiate", "另辟蹊径": "differentiate",
}


def _normalize_s1_raw(raw: dict) -> dict:
    # vendor_profiles.wave_position
    for vp in each(raw.get("vendor_profiles")):
        if "wave_position" in vp:
            vp["wave_position"] = map_enum(
                vp["wave_position"], WAVE_POSITION_MAP, default="wave_contender"
            )

    # feature_matrix: 删 computed_field
    fm = raw.get("feature_matrix")
    if isinstance(fm, dict):
        drop_keys(fm, ["weighted_scores"])
        for cat in each(fm.get("categories")):
            drop_keys(cat, ["weight"])

    # feature_gaps: recommendation + estimated_effort + estimated_impact
    for fg in each(raw.get("feature_gaps")):
        if "recommendation" in fg:
            fg["recommendation"] = map_enum(
                fg["recommendation"], RECOMMENDATION_MAP, default="build"
            )
        if "estimated_effort" in fg:
            fg["estimated_effort"] = map_enum(fg["estimated_effort"], INTENSITY_MAP, default="medium")
        if "estimated_impact" in fg:
            fg["estimated_impact"] = map_enum(fg["estimated_impact"], INTENSITY_MAP, default="medium")

    # white_space_features.opportunity_estimate
    for ws in each(raw.get("white_space_features")):
        if "opportunity_estimate" in ws:
            ws["opportunity_estimate"] = map_enum(
                ws["opportunity_estimate"], INTENSITY_MAP, default="medium"
            )

    return raw
