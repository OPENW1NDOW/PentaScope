"""S5 战略定位场景规整器"""
from src.agents.normalizers._common import (
    CONFIDENCE_MAP, drop_keys, each, map_enum,
)

QUADRANT_MAP = {
    "top_right": "top_right", "top_left": "top_left",
    "bottom_right": "bottom_right", "bottom_left": "bottom_left",
    "center": "center",
    "右上": "top_right", "左上": "top_left",
    "右下": "bottom_right", "左下": "bottom_left",
    "中心": "center", "中间": "center",
}

FOCUS_MAP = {
    "focused": "focused", "scattered": "scattered", "uncertain": "uncertain",
    "聚焦": "focused", "聚焦清晰": "focused",
    "分散": "scattered",
    "不确定": "uncertain", "未定": "uncertain",
}

DIVERGENCE_MAP = {
    "divergent": "divergent", "overlapping": "overlapping", "uncertain": "uncertain",
    "差异": "divergent", "差异化": "divergent",
    "重叠": "overlapping", "趋同": "overlapping",
    "不确定": "uncertain",
}

POS_CONFIDENCE_MAP = {
    "from_user_brief": "from_user_brief",
    "llm_inferred": "llm_inferred",
    "low_confidence": "low_confidence",
    "用户提供": "from_user_brief",
    "用户输入": "from_user_brief",
    "AI推断": "llm_inferred",
    "推断": "llm_inferred",
    "低可信": "low_confidence",
    "低可信度": "low_confidence",
}


def _normalize_s5_raw(raw: dict) -> dict:
    # vendor_profiles: 删 mq_quadrant computed_field
    for vp in each(raw.get("vendor_profiles")):
        drop_keys(vp, ["mq_quadrant"])

    # perceptual_map.plotted_brands.confidence
    pm = raw.get("perceptual_map")
    if isinstance(pm, dict):
        for b in each(pm.get("plotted_brands")):
            if "confidence" in b:
                b["confidence"] = map_enum(b["confidence"], CONFIDENCE_MAP, default="medium")
        for ws in each(pm.get("white_space")):
            if "quadrant" in ws:
                ws["quadrant"] = map_enum(ws["quadrant"], QUADRANT_MAP, default="center")

    # errc_grid: LLM 常把 raise_level 写成 raise（保留字陷阱）
    errc = raw.get("errc_grid")
    if isinstance(errc, dict):
        if "raise" in errc and "raise_level" not in errc:
            errc["raise_level"] = errc.pop("raise")

    # blue_ocean_move: focus_assessment + divergence_assessment
    bom = raw.get("blue_ocean_move")
    if isinstance(bom, dict):
        if "focus_assessment" in bom:
            bom["focus_assessment"] = map_enum(
                bom["focus_assessment"], FOCUS_MAP, default="uncertain"
            )
        if "divergence_assessment" in bom:
            bom["divergence_assessment"] = map_enum(
                bom["divergence_assessment"], DIVERGENCE_MAP, default="uncertain"
            )

    # positioning_statement: 删 full_statement_text（computed_field）+ confidence 兜底
    ps = raw.get("positioning_statement")
    if isinstance(ps, dict):
        drop_keys(ps, ["full_statement_text"])
        if "confidence" in ps:
            ps["confidence"] = map_enum(
                ps["confidence"], POS_CONFIDENCE_MAP, default="llm_inferred"
            )

    return raw
