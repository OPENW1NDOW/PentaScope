"""5 场景规整器：把 LLM 原始 JSON 兜底到 schema 允许的 Literal 值，并清掉 LLM 误填的 computed_field。

不替 LLM 编缺失字段——缺字段让 Pydantic 报错走重试，否则会污染溯源。
"""
import copy

from src.agents.normalizers.s1 import _normalize_s1_raw
from src.agents.normalizers.s2 import _normalize_s2_raw
from src.agents.normalizers.s3 import _normalize_s3_raw
from src.agents.normalizers.s4 import _normalize_s4_raw
from src.agents.normalizers.s5 import _normalize_s5_raw

_DISPATCH = {
    "S1": _normalize_s1_raw,
    "S2": _normalize_s2_raw,
    "S3": _normalize_s3_raw,
    "S4": _normalize_s4_raw,
    "S5": _normalize_s5_raw,
}


def normalize_for_scenario(scenario: str, raw: dict) -> dict:
    """对 LLM 输出的场景 payload dict 做规整，返回新 dict（不修改输入）"""
    fn = _DISPATCH[scenario]
    return fn(copy.deepcopy(raw))


__all__ = ["normalize_for_scenario"]
