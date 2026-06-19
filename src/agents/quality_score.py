"""quality_score 计算 — LLM-as-critic v4 重写。

v4 修订：删除 calc_source_coverage / calc_confidence_avg / calc_inspector_pass_rate
三个旧函数（v3 三项加权废弃，详见 spec v4）。新版本只有一个 calc_critic_score。

注意：calling code 必须先实例化 CriticScores 或传 dict 含 4 个维度 key。
critic 失败降级时（critic_scores=None），quality_score 由 inspector 直接写 0.5
（不走本函数）。
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from src.schemas.feedback import CriticScores


_DIMENSION_WEIGHTS = {
    "evidence": 0.30,
    "specificity": 0.30,
    "coherence": 0.20,
    "actionability": 0.20,
}

_VALID_DIMENSIONS = set(_DIMENSION_WEIGHTS.keys())


def calc_critic_score(scores: CriticScores | Mapping[str, Any]) -> float:
    """4 维加权（0.30/0.30/0.20/0.20）+ 归一化到 [0, 1] + clamp。

    输入：CriticScores 实例 或 dict[str, Any]——dict 时仅读 4 个维度 key，
          忽略其他 key（如 reasoning）（spec v3 cycle2/m4）。
    输出：quality_score ∈ [0.0, 1.0]，永远非空（spec v4 验收 6）。

    算法：
      weighted_raw = Σ(weight[dim] * score[dim])  # 1-4 区间
      quality_score = clamp((weighted_raw - 1) / 3, 0.0, 1.0)  # 归一化 + clamp
    """
    if isinstance(scores, CriticScores):
        score_dict = scores.model_dump()
    else:
        score_dict = dict(scores)

    # 仅读 4 个维度 key，缺失或非数值时填 0（让 clamp 兜底到 [0, 1]）
    weighted_raw = 0.0
    for dim, weight in _DIMENSION_WEIGHTS.items():
        raw_value = score_dict.get(dim)
        try:
            score_int = int(raw_value) if raw_value is not None else 0
        except (TypeError, ValueError):
            score_int = 0
        weighted_raw += weight * score_int

    # weighted_raw ∈ [0, 4] → 归一化到 [-1/3, 1] → clamp 到 [0, 1]
    quality_score = (weighted_raw - 1) / 3
    return max(0.0, min(1.0, round(quality_score, 3)))
