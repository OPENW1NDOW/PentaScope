"""S5 战略定位场景规整器

═══════════════════════════════════════════════════════════════════════════════
[LLM-CAPABILITY-WORKAROUND - 2026-06-10]

本文件中带 [fix20] 标记的「占位补齐」逻辑是针对**弱模型服从性不足**的代码层
兜底，不是项目正确性需求。

S5 场景下 LLM 反复在以下三处违反 schema（即使 prompt 已显式列出约束）：
1. vendor_profiles[*].strengths 少于 schema 要求条数（多 vendor 时尾部 vendor 缩水）
2. perceptual_map 轴标签写成单字
3. category_strategy 给空 dict {} 占位，子字段全 missing

【后续迭代提示】
切换到更强的模型后，这部分代码应**优先撤回**——LLM 服从性提升后兜底只会
污染报告。撤回前请先在新模型上跑 S5 端到端验证若干次，确认 LLM 能稳定满足
约束，再删除标 [fix20] 的代码块及测试。
═══════════════════════════════════════════════════════════════════════════════
"""
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


_AXIS_LABEL_SUFFIX = {
    "低": "低端", "高": "高端",
    "弱": "弱势", "强": "强势",
    "少": "少量", "多": "多元",
    "差": "差等", "优": "优等",
}


def _pad_axis_label(label) -> str:
    """[fix20] 单字轴标签兜底补字（schema 要 ≥2 字符）。已知映射用映射表，否则原字 + '端'。"""
    if not isinstance(label, str):
        return label
    if len(label) >= 2:
        return label
    return _AXIS_LABEL_SUFFIX.get(label, label + "端")


def _normalize_s5_raw(raw: dict) -> dict:
    # vendor_profiles: 删 mq_quadrant computed_field + strengths/cautions 不足时补齐（fix20）
    for vp in each(raw.get("vendor_profiles")):
        drop_keys(vp, ["mq_quadrant"])
        # [fix20] strengths < 2 时复制最后一条凑齐（LLM 反复在多 vendor 时把后续 vendor 缩水）
        strengths = vp.get("strengths")
        if isinstance(strengths, list) and 0 < len(strengths) < 2:
            last = strengths[-1]
            if isinstance(last, dict):
                strengths.append({**last, "point": (last.get("point", "") + "（补充条目）")})

    # perceptual_map.plotted_brands.confidence + 轴标签 ≥2 字符兜底（fix20）
    pm = raw.get("perceptual_map")
    if isinstance(pm, dict):
        for b in each(pm.get("plotted_brands")):
            if "confidence" in b:
                b["confidence"] = map_enum(b["confidence"], CONFIDENCE_MAP, default="medium")
        for ws in each(pm.get("white_space")):
            if "quadrant" in ws:
                ws["quadrant"] = map_enum(ws["quadrant"], QUADRANT_MAP, default="center")
        # [fix20] 4 个轴标签单字时补字
        for axis_key in ("x_axis", "y_axis"):
            axis = pm.get(axis_key)
            if isinstance(axis, dict):
                for lbl_key in ("low_label", "high_label"):
                    if lbl_key in axis:
                        axis[lbl_key] = _pad_axis_label(axis[lbl_key])

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

    # [fix20] category_strategy 是必填，LLM 常给空 dict / 缺子字段 → 用占位填齐
    cs = raw.get("category_strategy")
    if not isinstance(cs, dict) or not cs:
        cs = {}
        raw["category_strategy"] = cs
    if not cs.get("chosen_category") or len(str(cs.get("chosen_category", ""))) < 4:
        cs["chosen_category"] = "AI 协作工具"
    if not cs.get("why_this_category") or len(str(cs.get("why_this_category", ""))) < 30:
        cs["why_this_category"] = "本字段由 normalizer 占位填充：因 LLM 输出未给出该字段或长度不达标。"
    if not isinstance(cs.get("competitors_implied"), list) or not cs["competitors_implied"]:
        cs["competitors_implied"] = ["（normalizer 占位，LLM 未提供）"]

    return raw
