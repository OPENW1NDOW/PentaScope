"""S1 功能迭代场景规整器"""
from typing import Optional

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


def _normalize_s1_raw(raw: dict, *, discovered_urls: Optional[set[str]] = None) -> dict:
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
            # [v3-R14] FeatureScore evidence_url 不在 discovered_urls 时降 score=2 → score=1
            # 保护 score=2 必须有合法 evidence_url 的 model_validator
            if discovered_urls is not None:
                for f in each(cat.get("features")):
                    scores = f.get("scores")
                    if isinstance(scores, dict):
                        for comp_name, fs in scores.items():
                            if not isinstance(fs, dict):
                                continue
                            ev_url = fs.get("evidence_url")
                            if fs.get("score") == 2 and (
                                not ev_url or ev_url not in discovered_urls
                            ):
                                # 降为 score=1 + 清空非法 evidence_url + 设 source_missing_reason
                                fs["score"] = 1
                                fs["evidence_url"] = None
                                fs.setdefault(
                                    "source_missing_reason",
                                    "evidence_url 不在采集发现的 URL 列表中（normalizer 自动降级）",
                                )
                            elif fs.get("score") == 0 and ev_url and ev_url not in discovered_urls:
                                # score=0 时也清掉幻觉 URL，但保留 source_missing_reason
                                fs["evidence_url"] = None

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
