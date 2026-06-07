import pytest
from pydantic import ValidationError
from src.schemas.report import (
    ExecutiveSummary, ReportScope, Methodology, Finding, AnalysisSection,
    Recommendation, Appendix, Swot, SwotEntry,
)


def test_executive_summary_5_fields_with_length():
    """ExecutiveSummary 5 段，每段有字数硬约束"""
    es = ExecutiveSummary(
        context="x" * 100,
        core_thesis="y" * 60,
        key_findings_brief=["finding 1 detail" * 3, "finding 2 detail" * 3],
        implications="z" * 120,
        path_forward=["action 1"],
    )
    assert len(es.key_findings_brief) == 2

    # context 太短应失败
    with pytest.raises(ValidationError):
        ExecutiveSummary(
            context="short", core_thesis="y" * 60,
            key_findings_brief=["a" * 30, "b" * 30],
            implications="z" * 120, path_forward=["a"]
        )


def test_report_scope_competitors_min_1():
    rs = ReportScope(competitors=["A"], time_window="2026 Q1")
    assert rs.regions == []
    with pytest.raises(ValidationError):
        ReportScope(competitors=[], time_window="2026 Q1")


def test_methodology_1000_word_budget():
    """Methodology data_collection_approach min_length=200"""
    m = Methodology(
        data_collection_approach="x" * 200,
        evaluation_criteria=["c1", "c2", "c3"],
        limitations=["l1", "l2"],
        sample_size_note="x" * 80,
    )
    assert m.analyst_disclosure.startswith("本报告")
    with pytest.raises(ValidationError):
        Methodology(
            data_collection_approach="too short",
            evaluation_criteria=["a", "b", "c"],
            limitations=["l1", "l2"],
            sample_size_note="x" * 80,
        )


def test_finding_required_fields():
    f = Finding(
        statement="陈述足够长" * 4,
        evidence="证据足够长" * 4,
        implication="意义足够长" * 4,
    )
    assert f.source_refs == []


def test_analysis_section_section_id_constraints():
    sec = AnalysisSection(
        section_id="s1-feature-deep",
        heading="深度章节",
        narrative="x" * 300,
        section_type="feature_matrix_analysis",
    )
    assert sec.artifact_refs == []
    with pytest.raises(ValidationError):
        AnalysisSection(
            section_id="ab",
            heading="x", narrative="x" * 300, section_type="overview",
        )


def test_recommendation_priority_timeline():
    r = Recommendation(
        action="行动描述够长" * 4,
        target_role="产品经理",
        priority="critical",
        timeline="immediate",
        rationale="依据描述够长足够长" * 3,
    )
    assert r.source_refs == []


def test_swot_min_1_per_quadrant():
    """Swot 4 象限各至少 1 条"""
    e = SwotEntry(point="优势点描述足够长一些", evidence="证据描述也要足够长一点")
    sw = Swot(strengths=[e], weaknesses=[e], opportunities=[e], threats=[e])
    assert len(sw.strengths) == 1
    with pytest.raises(ValidationError):
        Swot(strengths=[], weaknesses=[e], opportunities=[e], threats=[e])


def test_appendix_default_empty():
    a = Appendix()
    assert a.glossary == {}
    assert a.additional_exhibits == []


# ============ Task 3: ReportMetadata 测试 ============

def test_report_metadata_required_fields():
    from datetime import date
    from src.schemas.report import ReportMetadata
    from src.schemas.common import DataSource

    m = ReportMetadata(
        report_id="r1", trace_id="t1", scenario="S1",
        publication_date=date(2026, 6, 7),
        data_sources=[DataSource(url="https://example.com")],
        confidence_level="high",
    )
    assert m.schema_version == "2.0"
    assert m.quality_score is None  # 未质检


def test_report_metadata_quality_score_default_none():
    """quality_score 默认 None（区分'未质检'与'质检 0 分'）"""
    from datetime import date
    from src.schemas.report import ReportMetadata
    from src.schemas.common import DataSource

    m = ReportMetadata(
        report_id="r1", trace_id="t1", scenario="S1",
        publication_date=date(2026, 6, 7),
        data_sources=[DataSource(url="https://example.com")],
        confidence_level="medium",
    )
    assert m.quality_score is None
