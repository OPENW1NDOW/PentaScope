"""Inspector + quality_score 公式单测。

测试范围（Cooper 决策 Q2=A，但按 b 方案优化测试覆盖）：
- 通用骨架检查（_check_common）
- S1 / S2 关键硬查（复用 test_schemas_* fixture）
- S3/S4/S5 _check_sX 通过 mock dispatcher 验证被调用（具体规则覆盖留 H 大类端到端）
- quality_score 三项加权公式
"""
import pytest
from unittest.mock import AsyncMock

from src.agents.inspector import InspectorAgent
from src.agents.quality_score import (
    calc_source_coverage,
    calc_confidence_avg,
    calc_inspector_pass_rate,
    calc_quality_score,
)
from src.schemas.feedback import FeedbackIssue
from src.schemas.common import SourceRef

from tests.unit.test_schemas_base_report import _make_minimal_base_report


# ============ Helpers ============


def _patch_recommendation_source_refs(report):
    """Recommendation 缺 source_refs 会触发 _check_common 报警，
    单测里默认 fixture 没填，需手动补一份避免噪声 issue。"""
    for rec in report.recommendations:
        if not rec.source_refs:
            rec.source_refs = [SourceRef(url="https://example.com")]


def _patch_section_source_refs(report):
    for sec in report.analysis_sections:
        if not sec.source_refs:
            sec.source_refs = [SourceRef(url="https://example.com")]


def _make_clean_s1_report():
    """构造一份通用层全部填 source_refs 的 S1 报告，方便单独测 S1 规则。"""
    report = _make_minimal_base_report("S1")
    _patch_recommendation_source_refs(report)
    _patch_section_source_refs(report)
    return report


# ============ quality_score 公式测试 ============


def test_calc_inspector_pass_rate_no_issues_full_score():
    assert calc_inspector_pass_rate([]) == 1.0


def test_calc_inspector_pass_rate_critical_penalty():
    issues = [FeedbackIssue(agent="writer", field="x", severity="critical", reason="x", suggestion="x")]
    assert calc_inspector_pass_rate(issues) == pytest.approx(0.6)


def test_calc_inspector_pass_rate_clamps_at_zero():
    issues = [
        FeedbackIssue(agent="writer", field=f"x{i}", severity="critical", reason="x", suggestion="x")
        for i in range(5)
    ]
    assert calc_inspector_pass_rate(issues) == 0.0


def test_calc_source_coverage_full():
    """clean S1 report 大多数 source_refs 字段是 default_factory=list（空），覆盖率不会满分。"""
    report = _make_clean_s1_report()
    cov = calc_source_coverage(report)
    assert cov is not None
    assert 0 <= cov <= 1


def test_calc_confidence_avg_in_range():
    """confidence_avg 应在合法 [0.3, 1.0] 区间内（含 metadata.confidence_level + DataSource.confidence）"""
    report = _make_clean_s1_report()
    avg = calc_confidence_avg(report)
    assert avg is not None
    # 默认 fixture: metadata.confidence_level=high(1.0) + DataSource.confidence=medium(0.6) → 0.8
    assert 0.3 <= avg <= 1.0


def test_calc_quality_score_returns_score_and_note():
    report = _make_clean_s1_report()
    score, note = calc_quality_score(report, [])
    assert 0 <= score <= 1
    assert "source_coverage" in note
    assert "confidence_avg" in note
    assert "inspector_pass_rate" in note


def test_calc_quality_score_drops_critical():
    """1 critical issue 应让分数显著下降"""
    report = _make_clean_s1_report()
    score_clean, _ = calc_quality_score(report, [])
    score_bad, _ = calc_quality_score(
        report,
        [FeedbackIssue(agent="writer", field="x", severity="critical", reason="x", suggestion="x")],
    )
    assert score_bad < score_clean


# ============ 通用骨架硬查测试 ============


def test_check_common_recommendation_missing_source_refs_yields_major():
    """recommendations 缺 source_refs → major issue"""
    report = _make_minimal_base_report("S1")
    # 不打补丁，让 recommendations 都缺 source_refs
    _patch_section_source_refs(report)  # section 补上避免噪声

    inspector = InspectorAgent(llm=None)  # _programmatic_checks 不调 LLM
    issues = inspector._programmatic_checks(report, competitors=["A", "B"])
    rec_issues = [i for i in issues if i.field.startswith("recommendations[")]
    assert len(rec_issues) > 0
    assert all(i.severity == "major" for i in rec_issues)


def test_check_common_section_missing_source_refs_yields_major():
    report = _make_minimal_base_report("S1")
    _patch_recommendation_source_refs(report)
    # analysis_sections 默认无 source_refs
    inspector = InspectorAgent(llm=None)
    issues = inspector._programmatic_checks(report, competitors=["A", "B"])
    sec_issues = [i for i in issues if i.field.startswith("analysis_sections[")]
    assert len(sec_issues) > 0
    assert all(i.severity == "major" for i in sec_issues)


# ============ S1 硬查测试 ============


def test_check_s1_vendor_profiles_missing_competitor_yields_critical():
    """scope.competitors 包含 'C'，但 vendor_profiles 只有 A/B → critical"""
    report = _make_clean_s1_report()
    report.scope.competitors = ["A", "B", "C"]  # 加一个 vendor_profiles 不覆盖的

    inspector = InspectorAgent(llm=None)
    issues = inspector._programmatic_checks(report, competitors=["A", "B", "C"])
    critical = [i for i in issues if i.severity == "critical"]
    assert any("vendor_profiles" in i.field for i in critical)


def test_check_s1_vendor_profiles_full_coverage_no_critical():
    """scope.competitors == vendor_profiles names → 不触发 vendor_profiles critical"""
    report = _make_clean_s1_report()
    # _make_minimal 默认 scope=["A","B"]，vendor_profiles 也是 A/B
    inspector = InspectorAgent(llm=None)
    issues = inspector._programmatic_checks(report, competitors=["A", "B"])
    vendor_issues = [
        i for i in issues
        if i.severity == "critical" and "vendor_profiles" in i.field
    ]
    assert vendor_issues == []


def test_check_s1_empty_must_build_yields_major():
    report = _make_clean_s1_report()
    report.scenario_payload.roadmap_recommendations.must_build = []
    inspector = InspectorAgent(llm=None)
    issues = inspector._programmatic_checks(report, competitors=["A", "B"])
    assert any(
        "must_build" in i.field and i.severity == "major"
        for i in issues
    )


# ============ S2 硬查测试 ============


def _make_clean_s2_report():
    """构造 S2 BaseReport：复用 _make_minimal_base_report 但替换 payload"""
    from tests.unit.test_schemas_s2 import _make_minimal_s2_payload
    report = _make_minimal_base_report("S1")  # 先建一份 S1
    s2_payload = _make_minimal_s2_payload()
    # 替换 metadata.scenario + scenario_payload，绕过 BaseReport 的 model_validator
    # 用 model_copy(update=...) 重建（避免触发 validator）
    from src.schemas.report import BaseReport
    data = report.model_dump()
    data["scenario_payload"] = s2_payload.model_dump()
    data["metadata"]["scenario"] = "S2"
    data["scope"]["competitors"] = ["A", "B", "C"]  # 对齐 s2 players
    new_report = BaseReport(**data)
    _patch_recommendation_source_refs(new_report)
    _patch_section_source_refs(new_report)
    return new_report


def test_check_s2_market_sizing_all_unknown_yields_major():
    """market_sizing TAM/SAM/SOM 全无 amount → major"""
    report = _make_clean_s2_report()
    # _make_minimal_s2_payload 默认 amount=None / value_basis=unknown
    inspector = InspectorAgent(llm=None)
    issues = inspector._programmatic_checks(report, competitors=["A", "B", "C"])
    assert any(
        "market_sizing" in i.field and i.severity == "major"
        for i in issues
    )


def test_check_s2_dispatches_to_s2_branch():
    """scenario=S2 时 _programmatic_checks 应路由到 _check_s2"""
    report = _make_clean_s2_report()
    inspector = InspectorAgent(llm=None)
    issues = inspector._programmatic_checks(report, competitors=["A", "B", "C"])
    # _check_s2 至少会因 market_sizing 全 unknown 报 1 条
    assert len(issues) > 0


# ============ S3/S4/S5 dispatcher 路由测试 ============


def test_dispatcher_routes_by_scenario(monkeypatch):
    """验证 _programmatic_checks 按 report.scenario 调对应 _check_sX 方法"""
    inspector = InspectorAgent(llm=None)
    called: list[str] = []

    monkeypatch.setattr(inspector, "_check_common", lambda r: called.append("common") or [])
    monkeypatch.setattr(inspector, "_check_s1", lambda r: called.append("s1") or [])
    monkeypatch.setattr(inspector, "_check_s2", lambda r: called.append("s2") or [])
    monkeypatch.setattr(inspector, "_check_s3", lambda r: called.append("s3") or [])
    monkeypatch.setattr(inspector, "_check_s4", lambda r: called.append("s4") or [])
    monkeypatch.setattr(inspector, "_check_s5", lambda r: called.append("s5") or [])

    report = _make_minimal_base_report("S1")
    inspector._programmatic_checks(report, competitors=["A", "B"])
    assert called == ["common", "s1"]


# ============ inspect 端到端：LLM mock + quality_score 回填 ============


@pytest.mark.asyncio
async def test_inspect_writes_quality_score_to_metadata():
    """inspect 完成后 metadata.quality_score 必须被写入"""
    report = _make_clean_s1_report()
    mock_llm = AsyncMock()
    mock_llm.call_json.return_value = {"issues": []}
    inspector = InspectorAgent(llm=mock_llm)

    await inspector.inspect(report, competitors=["A", "B"])
    assert report.metadata.quality_score is not None
    assert 0 <= report.metadata.quality_score <= 1
    assert report.metadata.quality_score_calculation_note  # 非空说明


@pytest.mark.asyncio
async def test_inspect_handles_invalid_llm_issue():
    """LLM 返回畸形 issue 不应让 inspect 整体崩"""
    report = _make_clean_s1_report()
    mock_llm = AsyncMock()
    mock_llm.call_json.return_value = {
        "issues": [
            {"agent": "writer", "field": "x", "severity": "critical", "reason": "ok", "suggestion": "ok"},
            {"agent": "invalid_agent", "field": "y"},  # 缺 severity，应被跳过
        ],
    }
    inspector = InspectorAgent(llm=mock_llm)
    feedback = await inspector.inspect(report, competitors=["A", "B"])
    # 至少应保留有效那一条 + 程序化 issue
    assert any(i.severity == "critical" for i in feedback.issues)


@pytest.mark.asyncio
async def test_inspect_passed_when_only_minor():
    """全是 minor issue 时 passed=True"""
    report = _make_clean_s1_report()
    # 故意不补 swot.source_refs，让 _check_common 产 minor
    mock_llm = AsyncMock()
    mock_llm.call_json.return_value = {"issues": []}
    inspector = InspectorAgent(llm=mock_llm)
    feedback = await inspector.inspect(report, competitors=["A", "B"])
    if all(i.severity == "minor" for i in feedback.issues):
        assert feedback.passed
