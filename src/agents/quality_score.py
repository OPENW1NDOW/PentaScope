"""quality_score 计算（spec Part 4.5 三项加权公式）。

quality_score = 0.4 × source_coverage + 0.3 × confidence_avg + 0.3 × inspector_pass_rate

- source_coverage = 有 source_refs 的字段实例数 / 总实例数（递归遍历 BaseModel，颗粒度细）
- confidence_avg = 平均 confidence 数值化（high/from_user_brief=1.0, medium/llm_inferred=0.6, low/low_confidence=0.3）
- inspector_pass_rate = 1 - 严重度加权和 / 满分（critical=0.4, major=0.2, minor=0.05；满分恒为 1.0）
"""
from __future__ import annotations
from typing import Iterable, Optional
from pydantic import BaseModel


_CONFIDENCE_MAP = {
    # 通用 + s2/s3/s5 PlottedBrand
    "high": 1.0,
    "medium": 0.6,
    "low": 0.3,
    # s5 PositioningStatement 特殊枚举
    "from_user_brief": 1.0,
    "llm_inferred": 0.6,
    "low_confidence": 0.3,
}

_SEVERITY_PENALTY = {"critical": 0.4, "major": 0.2, "minor": 0.05}


def _walk_models(node, visited: Optional[set[int]] = None) -> Iterable[BaseModel]:
    """递归遍历 BaseModel 实例（包括 list/dict 内嵌套）。"""
    if visited is None:
        visited = set()
    if isinstance(node, BaseModel):
        if id(node) in visited:
            return
        visited.add(id(node))
        yield node
        for field_name in type(node).model_fields:
            value = getattr(node, field_name, None)
            yield from _walk_models(value, visited)
    elif isinstance(node, (list, tuple)):
        for item in node:
            yield from _walk_models(item, visited)
    elif isinstance(node, dict):
        for item in node.values():
            yield from _walk_models(item, visited)


def calc_source_coverage(report: BaseModel) -> Optional[float]:
    """统计所有 BaseModel 实例中声明了 source_refs 字段的实例：
    分母 = 声明字段的实例总数；分子 = source_refs 非空的实例数。
    若分母为 0（理论不会，BaseReport 必有声明）则返回 None。
    """
    total = 0
    has = 0
    for model in _walk_models(report):
        if "source_refs" not in type(model).model_fields:
            continue
        total += 1
        refs = getattr(model, "source_refs", None)
        if refs:
            has += 1
    return None if total == 0 else has / total


def calc_confidence_avg(report: BaseModel) -> Optional[float]:
    """收集所有 confidence/confidence_level 字段的数值化平均值。"""
    values: list[float] = []
    for model in _walk_models(report):
        fields = type(model).model_fields
        for fname in ("confidence", "confidence_level"):
            if fname not in fields:
                continue
            raw = getattr(model, fname, None)
            if raw is None:
                continue
            mapped = _CONFIDENCE_MAP.get(str(raw))
            if mapped is not None:
                values.append(mapped)
    return None if not values else sum(values) / len(values)


def calc_inspector_pass_rate(issues) -> float:
    """1 - 严重度加权和（critical=0.4 / major=0.2 / minor=0.05），clamp[0,1]。

    与 builder.py 现有公式一致：满分恒为 1.0，多个 critical 会快速将分数拉到 0。
    """
    penalty_sum = sum(_SEVERITY_PENALTY.get(getattr(i, "severity", ""), 0) for i in issues)
    return max(0.0, 1.0 - penalty_sum)


def calc_quality_score(report: BaseModel, issues) -> tuple[float, str]:
    """spec Part 4.5：三项加权汇总。

    返回 (score, calculation_note)。calculation_note 落入 metadata.quality_score_calculation_note，
    用于让审阅者看清三项分量的权重与缺值情况。
    """
    src_cov = calc_source_coverage(report)
    conf_avg = calc_confidence_avg(report)
    pass_rate = calc_inspector_pass_rate(issues)

    # 缺值时降权重新归一化，避免空 confidence 把整个分数拉成 0
    parts: list[tuple[str, float, float]] = []
    if src_cov is not None:
        parts.append(("source_coverage", src_cov, 0.4))
    if conf_avg is not None:
        parts.append(("confidence_avg", conf_avg, 0.3))
    parts.append(("inspector_pass_rate", pass_rate, 0.3))

    weight_sum = sum(w for _, _, w in parts)
    if weight_sum == 0:
        return 0.0, "无可用维度，强制 0.0"
    score = sum(v * w for _, v, w in parts) / weight_sum

    note_parts = [f"{name}={v:.2f}*{w}" for name, v, w in parts]
    note = " + ".join(note_parts) + f" → {score:.2f}"
    return round(max(0.0, min(1.0, score)), 2), note
