from unittest.mock import MagicMock
from src.graph.builder import _route_evidence_issue


def test_empty_discovered_returns_none():
    state = {"discovered_sources": [], "report": None}
    assert _route_evidence_issue(state) is None


def test_no_discovered_key_returns_none():
    state = {"report": None}
    assert _route_evidence_issue(state) is None


def test_report_none_returns_none():
    state = {"discovered_sources": [{"url": "https://a.com", "title": "", "snippet": ""}], "report": None}
    assert _route_evidence_issue(state) is None


def test_high_discovered_low_coverage_routes_writer():
    """discovered >= 8, report used_urls 为空 → coverage=0 → writer"""
    report = MagicMock()
    report.model_dump.return_value = {}
    state = {
        "discovered_sources": [{"url": f"https://src{i}.com", "title": "", "snippet": ""} for i in range(10)],
        "report": report,
    }
    result = _route_evidence_issue(state)
    assert result == "writer"


def test_low_discovered_routes_collector():
    """discovered < 5 → collector"""
    report = MagicMock()
    report.model_dump.return_value = {}
    state = {
        "discovered_sources": [{"url": f"https://src{i}.com", "title": "", "snippet": ""} for i in range(3)],
        "report": report,
    }
    result = _route_evidence_issue(state)
    assert result == "collector"


def test_prev_coverage_not_improved_returns_end():
    """第二次打回（retry_count>=1）且 coverage 未提升 → end"""
    report = MagicMock()
    report.model_dump.return_value = {}
    state = {
        "discovered_sources": [{"url": f"https://src{i}.com", "title": "", "snippet": ""} for i in range(10)],
        "report": report,
        "_prev_evidence_coverage": 0.0,
        "retry_count": 1,
    }
    result = _route_evidence_issue(state)
    assert result == "end"


def test_first_round_with_prev_coverage_should_not_return_end():
    """BUG 重现：第一轮（retry_count=0）inspector 刚写的 _prev_evidence_coverage
    不应触发退出条件，应正常路由到 writer/collector。"""
    report = MagicMock()
    report.model_dump.return_value = {}
    state = {
        "discovered_sources": [{"url": f"https://src{i}.com", "title": "", "snippet": ""} for i in range(10)],
        "report": report,
        "_prev_evidence_coverage": 0.0,  # inspector 刚写的，与当前 coverage 相同
        "retry_count": 0,  # 第一轮
    }
    result = _route_evidence_issue(state)
    # 第一轮不应 end，应该路由到 writer（discovered>=8, coverage<0.5）
    assert result == "writer"
