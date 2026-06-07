import pytest
from datetime import date
from pydantic import ValidationError
from src.schemas.scenarios.s4 import (
    S4MonitoringPayload, ReviewPeriod, FIATuple, FeatureChange,
    MonitoringThreat,
    MonitoringTrends, Battlecard, BattlecardSection,
)
from src.schemas.common import SourceRef


def test_fia_tuple_fact_required_impact_act_optional():
    """fact 必填，impact + act Optional"""
    fia = FIATuple(fact="发现的事实描述足够长一些字数")
    assert fia.impact is None
    assert fia.act is None


def test_monitoring_threat_quadrant_computed():
    """quadrant 由 severity x likelihood 自动派生"""
    long_desc = "x" * 40
    long_resp = "y" * 25
    t = MonitoringThreat(
        artifact_id="threat-1", title="威胁 A 描述足够长一些字数",
        severity="high", likelihood="high",
        description=long_desc,
        recommended_response=long_resp,
    )
    assert t.quadrant == "act_now"

    t2 = MonitoringThreat(
        artifact_id="threat-2", title="威胁 B 描述足够长一些字数",
        severity="low", likelihood="low",
        description=long_desc,
        recommended_response=long_resp,
    )
    assert t2.quadrant == "deprioritize"


def _ok_battlecard(name="A"):
    return Battlecard(
        artifact_id=f"bc-{name}", competitor_name=name,
        sections=[
            BattlecardSection(section_name="quick_summary"),
            BattlecardSection(section_name="primary_threat"),
            BattlecardSection(section_name="messaging_positioning"),
            BattlecardSection(section_name="pricing_packaging"),
        ],
    )


def test_first_review_baseline_enforced():
    """首次监控（prior_trace_id=None）所有 changes 必须 is_baseline=True"""
    review = ReviewPeriod(
        current_review_date=date(2026, 6, 7),
        review_period_label="2026 Q2",
        monitored_competitors=["A"],
    )
    fia = FIATuple(fact="发现的事实描述足够长字数")
    bad_change = FeatureChange(
        artifact_id="feat-c1", competitor_name="A",
        change_type="new_feature", feature_name="新功能",
        fia=fia, severity="medium",
        source_refs=[SourceRef(url="https://example.com")],
        is_baseline=False,
    )
    bc = _ok_battlecard("A")
    with pytest.raises(ValidationError, match="is_baseline=True"):
        S4MonitoringPayload(
            review_period=review,
            feature_changes=[bad_change],
            trends=MonitoringTrends(),
            battlecards=[bc],
        )


def test_monitor_competitor_consistency():
    """change 中的 competitor_name 必须在 monitored_competitors 中"""
    review = ReviewPeriod(
        current_review_date=date(2026, 6, 7),
        review_period_label="2026 Q2",
        monitored_competitors=["A"],
    )
    bad_change = FeatureChange(
        artifact_id="feat-c1", competitor_name="X",
        change_type="new_feature", feature_name="新功能",
        fia=FIATuple(fact="x" * 20), severity="medium",
        source_refs=[SourceRef(url="https://example.com")],
        is_baseline=True,
    )
    bc = _ok_battlecard("A")
    with pytest.raises(ValidationError, match="不在 monitored_competitors"):
        S4MonitoringPayload(
            review_period=review,
            feature_changes=[bad_change],
            trends=MonitoringTrends(),
            battlecards=[bc],
        )


def test_first_review_trends_must_be_none():
    """首次监控模式下 trends 全部必须 None"""
    review = ReviewPeriod(
        current_review_date=date(2026, 6, 7),
        review_period_label="2026 Q2",
        monitored_competitors=["A"],
    )
    bc = _ok_battlecard("A")
    bad_trends = MonitoringTrends(sentiment_trend="up")
    with pytest.raises(ValidationError, match="trends 必须全部为 None"):
        S4MonitoringPayload(
            review_period=review,
            trends=bad_trends,
            battlecards=[bc],
        )


def test_minimal_first_review_payload_constructs():
    """首次监控最小合法 payload"""
    review = ReviewPeriod(
        current_review_date=date(2026, 6, 7),
        review_period_label="2026 Q2",
        monitored_competitors=["A"],
    )
    bc = _ok_battlecard("A")
    p = S4MonitoringPayload(
        review_period=review,
        trends=MonitoringTrends(),
        battlecards=[bc],
    )
    assert p.scenario_type == "S4"
    assert p.review_period.prior_trace_id is None
