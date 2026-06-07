"""规整器公共工具：枚举模糊匹配、computed_field 删除、批量映射"""
from typing import Any


def map_enum(value: Any, mapping: dict[str, str], default: str | None = None) -> Any:
    """把 value 通过 mapping 映射到合法枚举。

    顺序：精确命中 → 子串包含 → default。default=None 时保留原值（让 Pydantic 报错）。
    """
    if not isinstance(value, str):
        return value
    if value in mapping.values():
        return value
    if value in mapping:
        return mapping[value]
    for k, v in mapping.items():
        if k and k in value:
            return v
    return default if default is not None else value


def drop_keys(d: Any, keys: list[str]) -> None:
    """从 dict 删除多个 key（in-place，已经 deepcopy 过）"""
    if not isinstance(d, dict):
        return
    for k in keys:
        d.pop(k, None)


def each(items: Any) -> list[dict]:
    """安全遍历 list[dict]：非 list 或非 dict 元素跳过"""
    if not isinstance(items, list):
        return []
    return [x for x in items if isinstance(x, dict)]


# ---------- 通用枚举字典 ----------

INTENSITY_MAP = {
    "low": "low", "medium": "medium", "high": "high",
    "低": "low", "中": "medium", "高": "high",
    "弱": "low", "中等": "medium", "强": "high",
}

# direction：上升/下降/持平。包含中英文+箭头
DIRECTION_MAP = {
    "up": "up", "flat": "flat", "down": "down",
    "上升": "up", "上行": "up", "走高": "up", "增长": "up",
    "持平": "flat", "稳定": "flat", "横盘": "flat",
    "下降": "down", "下行": "down", "走低": "down", "下跌": "down",
    "↑": "up", "→": "flat", "↓": "down",
}

PRIORITY_MAP = {
    "critical": "critical", "important": "important", "consider": "consider",
    "高": "critical", "中": "important", "低": "consider",
    "关键": "critical", "重要": "important", "可考虑": "consider",
    "紧急": "critical",
}

CONFIDENCE_MAP = {
    "high": "high", "medium": "medium", "low": "low",
    "高": "high", "中": "medium", "低": "low",
}
