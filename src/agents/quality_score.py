"""quality_score 三项加权计算。

三项（各 1/3 等权，缺项时剩余项重新归一化）：
1. source_coverage   — BaseReport 中需 source_refs 的字段，实际填了 ≥1 条 ref 的占比
2. confidence_avg    — metadata.data_sources 各 DataSource.confidence 数值化平均（high=1.0/medium=0.6/low=0.3）
3. inspector_pass_rate — 1.0 - sum(severity_penalty), clamp[0,1]
                        penalty: critical=0.4 / major=0.2 / minor=0.05

最终 quality_score ∈ [0, 1]；source_coverage 全空或 data_sources 全空时跳过该项重新归一化；
全部三项都缺时返回 0.0（极端兜底）。

由 inspector 在质检结束时一次性调用 `calc_quality_score(report, issues)` 写入
metadata.quality_score；writer phase 4 不参与（与 confidence_level 语义边界由 v3-R22 锁定）。
"""
from __future__ import annotations

from src.schemas.feedback import FeedbackIssue
from src.schemas.report import BaseReport


_CONFIDENCE_NUM = {"high": 1.0, "medium": 0.6, "low": 0.3}
_SEVERITY_PENALTY = {"critical": 0.4, "major": 0.2, "minor": 0.05}


def calc_source_coverage(report: BaseReport) -> float | None:
    """统计需 source_refs 的字段覆盖率：分母 = 所有需 ref 的条目数，分子 = 实际 ref ≥1 条的条目数。

    范围：BaseReport.key_findings + analysis_sections + recommendations + swot 4 类。
    全部为 0（不该发生，但 schema 允许 swot 各 list min=1，4 类合计 ≥7）→ 返回 None 触发缺值降权。
    """
    items = []
    items.extend(report.key_findings)
    items.extend(report.analysis_sections)
    items.extend(report.recommendations)
    items.extend(report.swot.strengths)
    items.extend(report.swot.weaknesses)
    items.extend(report.swot.opportunities)
    items.extend(report.swot.threats)

    if not items:
        return None
    with_refs = sum(1 for it in items if getattr(it, "source_refs", None))
    return with_refs / len(items)


def calc_confidence_avg(report: BaseReport) -> float | None:
    """metadata.data_sources 各 DataSource.confidence 数值化平均。

    data_sources 全空（schema min=1 应不发生）→ 返回 None。
    confidence 字段缺失或非合法值（schema 已约束三档）→ 默认 medium。
    """
    sources = report.metadata.data_sources
    if not sources:
        return None
    nums = [_CONFIDENCE_NUM.get(s.confidence, 0.6) for s in sources]
    return sum(nums) / len(nums)


def calc_inspector_pass_rate(issues: list[FeedbackIssue]) -> float:
    """1.0 - sum(severity_penalty)，clamp 到 [0, 1]。"""
    penalty = sum(_SEVERITY_PENALTY.get(i.severity, 0.0) for i in issues)
    return max(0.0, min(1.0, 1.0 - penalty))


def calc_quality_score(
    report: BaseReport,
    issues: list[FeedbackIssue],
) -> tuple[float, str]:
    """三项加权计算 quality_score，返回 (score, calculation_note)。

    note 格式：`coverage=0.85 confidence=0.73 pass_rate=0.80 → score=0.793`，
    inspector 写入 metadata.quality_score_calculation_note 用于追溯。
    """
    cov = calc_source_coverage(report)
    conf = calc_confidence_avg(report)
    rate = calc_inspector_pass_rate(issues)

    parts = []
    if cov is not None:
        parts.append(("coverage", cov))
    if conf is not None:
        parts.append(("confidence", conf))
    parts.append(("pass_rate", rate))

    if not parts:
        return 0.0, "no metrics available → 0.0"

    score = sum(v for _, v in parts) / len(parts)
    note = " ".join(f"{name}={val:.2f}" for name, val in parts) + f" → score={score:.3f}"
    return round(score, 3), note
