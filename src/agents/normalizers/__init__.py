"""5 场景规整器：把 LLM 原始 JSON 兜底到 schema 允许的 Literal 值，并清掉 LLM 误填的 computed_field。

不替 LLM 编缺失字段——缺字段让 Pydantic 报错走重试，否则会污染溯源。

v3 升级（[v3-R14/R15]）：
- s1: FeatureScore evidence_url 不在 discovered_urls 时降 score=1
- s3: WTP method=proxy 强制 confidence=low + 删除空 source_refs 的 ObservedCompetitorTier
- s4: 删除空 source_refs 的 5 类 changes
"""
import copy
from typing import Optional

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


def normalize_for_scenario(
    scenario: str,
    raw: dict,
    *,
    discovered_urls: Optional[set[str]] = None,
    warnings: Optional[list[str]] = None,
) -> dict:
    """对 LLM 输出的场景 payload dict 做规整，返回新 dict（不修改输入）。

    Args:
        scenario: "S1" / "S2" / "S3" / "S4" / "S5"
        raw: LLM 原始 JSON dict
        discovered_urls: 采集阶段发现的合法 URL 集合（v3-R14 用于过滤幻觉 URL + 降级 score=2）。
            为 None 时不做 URL 相关兜底（向后兼容）。
        warnings: 调用方传入的 mutable list，normalizer 把"删除无来源条目"等动作 append 进去
            （如 "dropped_unverified_entries:s3.competitive_pricing_matrix:2"）。
            为 None 时丢弃这类 warning（向后兼容）。

    Returns:
        规整后的新 dict。
    """
    fn = _DISPATCH[scenario]
    cleaned = copy.deepcopy(raw)
    # s3/s4 接受 warnings；s1 接受 discovered_urls；s2/s5 忽略
    if scenario == "S1":
        return fn(cleaned, discovered_urls=discovered_urls)
    if scenario in ("S3", "S4"):
        return fn(cleaned, discovered_urls=discovered_urls, warnings=warnings)
    return fn(cleaned)


__all__ = ["normalize_for_scenario"]
