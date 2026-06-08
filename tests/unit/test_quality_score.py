"""quality_score 三项加权单测。

为避免构造完整 BaseReport（依赖 scenario_payload 5 套 schema fixture），
本测试用 SimpleNamespace 拼出 calc_* 函数实际访问的最小字段集合：
- key_findings / analysis_sections / recommendations / swot.{strengths,weaknesses,opportunities,threats}
- metadata.data_sources
"""
from types import SimpleNamespace

import pytest

from src.agents.quality_score import (
    calc_confidence_avg,
    calc_inspector_pass_rate,
    calc_quality_score,
    calc_source_coverage,
)
from src.schemas.feedback import FeedbackIssue


def _item(refs_count: int):
    return SimpleNamespace(source_refs=["x"] * refs_count)


def _mock_report(items_with_refs: int, items_total: int, data_sources_confidence: list[str]):
    """构造一个最小可用的 mock：均摊 items 到 7 个槽位，data_sources 全填到 metadata。"""
    items = [_item(1) for _ in range(items_with_refs)] + [_item(0) for _ in range(items_total - items_with_refs)]
    # 均摊到 4 类（key_findings / analysis_sections / recommendations / swot）：
    # 简化为 key_findings 全占（其他三类空），覆盖率公式只看总和。
    swot = SimpleNamespace(strengths=[], weaknesses=[], opportunities=[], threats=[])
    metadata = SimpleNamespace(
        data_sources=[SimpleNamespace(confidence=c) for c in data_sources_confidence],
    )
    return SimpleNamespace(
        key_findings=items,
        analysis_sections=[],
        recommendations=[],
        swot=swot,
        metadata=metadata,
    )


# ============ calc_source_coverage ============

def test_source_coverage_full():
    """全部条目都有 source_refs → 1.0"""
    report = _mock_report(items_with_refs=5, items_total=5, data_sources_confidence=["high"])
    assert calc_source_coverage(report) == 1.0


def test_source_coverage_partial():
    """3/5 有 ref → 0.6"""
    report = _mock_report(items_with_refs=3, items_total=5, data_sources_confidence=["high"])
    assert calc_source_coverage(report) == pytest.approx(0.6)


def test_source_coverage_empty_returns_none():
    """全 4 类都空 → None（触发缺值降权）"""
    report = _mock_report(items_with_refs=0, items_total=0, data_sources_confidence=["high"])
    assert calc_source_coverage(report) is None


def test_source_coverage_includes_swot_entries():
    """swot 4 类的 entries 也被计入分母（不仅 key_findings）"""
    swot = SimpleNamespace(
        strengths=[_item(1)],
        weaknesses=[_item(0)],
        opportunities=[_item(1)],
        threats=[_item(0)],
    )
    metadata = SimpleNamespace(data_sources=[SimpleNamespace(confidence="high")])
    report = SimpleNamespace(
        key_findings=[],
        analysis_sections=[],
        recommendations=[],
        swot=swot,
        metadata=metadata,
    )
    assert calc_source_coverage(report) == 0.5


# ============ calc_confidence_avg ============

def test_confidence_avg_all_high():
    report = _mock_report(0, 0, ["high", "high", "high"])
    assert calc_confidence_avg(report) == 1.0


def test_confidence_avg_mixed():
    """high(1.0) + medium(0.6) + low(0.3) = 1.9 / 3 ≈ 0.633"""
    report = _mock_report(0, 0, ["high", "medium", "low"])
    assert calc_confidence_avg(report) == pytest.approx(1.9 / 3)


def test_confidence_avg_empty_returns_none():
    report = _mock_report(0, 0, [])
    assert calc_confidence_avg(report) is None


# ============ calc_inspector_pass_rate ============

def test_pass_rate_no_issues():
    assert calc_inspector_pass_rate([]) == 1.0


def test_pass_rate_critical_only():
    """1 critical = 0.4 → 1 - 0.4 = 0.6"""
    issues = [FeedbackIssue(agent="writer", field="x", severity="critical", reason="r")]
    assert calc_inspector_pass_rate(issues) == pytest.approx(0.6)


def test_pass_rate_mixed():
    """1c + 1m + 2 minor = 0.4 + 0.2 + 0.1 = 0.7 → 0.3"""
    issues = [
        FeedbackIssue(agent="writer", field="a", severity="critical", reason="r"),
        FeedbackIssue(agent="writer", field="b", severity="major", reason="r"),
        FeedbackIssue(agent="writer", field="c", severity="minor", reason="r"),
        FeedbackIssue(agent="writer", field="d", severity="minor", reason="r"),
    ]
    assert calc_inspector_pass_rate(issues) == pytest.approx(0.3)


def test_pass_rate_clamps_to_zero():
    """5 critical 累计 -2.0，clamp 到 0.0"""
    issues = [
        FeedbackIssue(agent="writer", field=f"{i}", severity="critical", reason="r")
        for i in range(5)
    ]
    assert calc_inspector_pass_rate(issues) == 0.0


# ============ calc_quality_score（三项加权 + 缺值降权） ============

def test_quality_score_all_three_present():
    """三项齐全：coverage=1.0 + confidence=1.0 + pass_rate=1.0 → 1.0"""
    report = _mock_report(items_with_refs=3, items_total=3, data_sources_confidence=["high"])
    score, note = calc_quality_score(report, [])
    assert score == 1.0
    assert "coverage=1.00" in note and "confidence=1.00" in note and "pass_rate=1.00" in note


def test_quality_score_one_critical():
    """1 critical 把 pass_rate 从 1.0 降到 0.6，其他两项 1.0 → (1+1+0.6)/3 ≈ 0.867"""
    report = _mock_report(3, 3, ["high"])
    issues = [FeedbackIssue(agent="writer", field="x", severity="critical", reason="r")]
    score, _ = calc_quality_score(report, issues)
    assert score == pytest.approx(2.6 / 3, abs=0.01)


def test_quality_score_drops_missing_coverage():
    """source 全空 → coverage None → 仅取 confidence + pass_rate 平均"""
    report = _mock_report(0, 0, ["high"])  # key_findings/sections/rec/swot 都空 → cov=None
    score, note = calc_quality_score(report, [])
    assert "coverage" not in note  # coverage 项被剔除
    assert score == 1.0  # (confidence=1.0 + pass_rate=1.0) / 2


def test_quality_score_drops_missing_confidence():
    """data_sources 空 → confidence None → 仅 coverage + pass_rate"""
    report = _mock_report(2, 4, [])  # 2/4 = 0.5 coverage
    score, note = calc_quality_score(report, [])
    assert "confidence" not in note
    assert score == pytest.approx((0.5 + 1.0) / 2)


def test_quality_score_only_pass_rate_when_both_others_missing():
    """coverage None + confidence None → 仅 pass_rate"""
    report = _mock_report(0, 0, [])
    score, note = calc_quality_score(report, [
        FeedbackIssue(agent="writer", field="x", severity="major", reason="r"),
    ])
    assert "coverage" not in note and "confidence" not in note
    assert score == 0.8  # 1.0 - 0.2


def test_quality_score_returned_to_3_decimal_places():
    report = _mock_report(1, 3, ["medium"])
    score, _ = calc_quality_score(report, [])
    # score 是 round 到 3 位的 float，断言它是合法范围
    assert 0.0 <= score <= 1.0
    assert isinstance(score, float)
