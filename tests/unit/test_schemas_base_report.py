import pytest
from pydantic import ValidationError
from src.schemas.report import (
    ExecutiveSummary, ReportScope, Methodology, Finding, AnalysisSection,
    Recommendation, Appendix, Swot, SwotEntry,
)


def test_executive_summary_5_fields():
    """ExecutiveSummary 5 段结构校验（字数约束已移交 critic）"""
    es = ExecutiveSummary(
        context="短背景",
        core_thesis="短论点",
        key_findings_brief=["finding 1", "finding 2"],
        implications="短启示",
        path_forward=["action 1"],
    )
    assert len(es.key_findings_brief) == 2

    # max_length 仍在（防爆）
    with pytest.raises(ValidationError):
        ExecutiveSummary(
            context="x" * 301, core_thesis="y",
            key_findings_brief=["a", "b"],
            implications="z", path_forward=["a"]
        )


def test_report_scope_competitors_min_1():
    rs = ReportScope(competitors=["A"], time_window="2026 Q1")
    assert rs.regions == []
    with pytest.raises(ValidationError):
        ReportScope(competitors=[], time_window="2026 Q1")


def test_methodology_structure():
    """Methodology 结构校验（字数约束已移交 critic）"""
    m = Methodology(
        data_collection_approach="方法",
        evaluation_criteria=["c1", "c2"],
        limitations=["l1"],
        sample_size_note="样本",
    )
    assert m.analyst_disclosure.startswith("本报告")
    # evaluation_criteria 仍需 ≥2
    with pytest.raises(ValidationError):
        Methodology(
            data_collection_approach="",
            evaluation_criteria=["only_one"],
            limitations=["l1"],
            sample_size_note="",
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


# ============ Task 11: BaseReport union 接通测试 ============


def _make_minimal_s1_payload():
    """复用 test_schemas_s1 思路构造最小合法 S1 payload"""
    from src.schemas.scenarios.s1 import (
        S1FeatureIterationPayload, S1VendorProfile, FeatureMatrix,
        FeatureCategory, FeatureRow, FeatureScore, S1RadarScore,
        JobStatement, FeatureGap, RoadmapRecommendations,
        VendorStrength, VendorCaution,
    )

    def _ok_strength():
        return VendorStrength(
            point="某项核心优势描述至少十字",
            evidence="官网功能页有详细的截图说明",
        )

    def _ok_caution():
        return VendorCaution(
            point="某项需注意点描述至少十字",
            evidence="用户论坛有大量差评汇总记录",
        )

    def _ok_profile(name, wave="wave_leader"):
        return S1VendorProfile(
            competitor_name=name,
            wave_position=wave,
            one_line_pitch=f"{name} 的一句话定位描述足够长",
            strengths=[_ok_strength(), _ok_strength()],
            cautions=[_ok_caution()],
            best_fit_for="中小团队场景适配最好",
        )

    return S1FeatureIterationPayload(
        vendor_profiles=[_ok_profile("A"), _ok_profile("B", wave="wave_contender")],
        feature_matrix=FeatureMatrix(
            artifact_id="fm-1",
            competitors=["A", "B", "我方"],
            our_product_name="我方",
            categories=[FeatureCategory(name="核心", tier=1, features=[
                FeatureRow(
                    name="f1",
                    scores={c: FeatureScore(score=2, evidence_url="https://a.com") for c in ["A", "B", "我方"]},
                ),
            ])],
        ),
        radar_scores=[
            S1RadarScore(artifact_id="r-A", competitor_name="A",
                        feature_breadth=4, usability=4, cost_effectiveness=4, stability=4, design_quality=4),
            S1RadarScore(artifact_id="r-B", competitor_name="B",
                        feature_breadth=3, usability=3, cost_effectiveness=3, stability=3, design_quality=3),
        ],
        job_statement=JobStatement(
            situation="跨部门协作场景下处理文档",
            motivation="希望减少沟通成本提升效率",
            outcome="最终减少跨部门同步会议次数",
        ),
        feature_gaps=[FeatureGap(
            feature_name="移动端", competitors_have_it=["A"],
            underserved_outcome="出差场景下无法编辑文档",
            estimated_effort="medium", estimated_impact="high",
            recommendation="build",
        )],
        roadmap_recommendations=RoadmapRecommendations(
            must_build=["移动端"],
            rationale_summary="必须补移动端，理由如下" * 5,
        ),
    )


def _make_minimal_base_report(scenario="S1"):
    """构造最小合法 BaseReport"""
    from datetime import date
    from src.schemas.report import (
        BaseReport, ReportMetadata, ReportScope, Methodology, Finding,
        AnalysisSection, Recommendation, SwotEntry, Swot,
    )
    from src.schemas.common import DataSource

    sw_entry = SwotEntry(point="优势点描述足够长一些", evidence="证据描述也要足够长一点")

    return BaseReport(
        metadata=ReportMetadata(
            report_id="r1",
            trace_id="t1",
            scenario=scenario,
            publication_date=date(2026, 6, 7),
            data_sources=[DataSource(url="https://example.com")],
            confidence_level="high",
        ),
        title="S1 功能迭代竞品分析报告",
        at_a_glance=["要点 1", "要点 2", "要点 3"],
        executive_summary=ExecutiveSummary(
            context="x" * 100,
            core_thesis="y" * 60,
            key_findings_brief=["finding 1 detail" * 3, "finding 2 detail" * 3],
            implications="z" * 120,
            path_forward=["action 1"],
        ),
        background="x" * 300,
        scope=ReportScope(competitors=["A", "B"], time_window="2026 Q2"),
        methodology=Methodology(
            data_collection_approach="x" * 200,
            evaluation_criteria=["c1", "c2", "c3"],
            limitations=["l1", "l2"],
            sample_size_note="x" * 80,
        ),
        key_findings=[
            Finding(statement="陈述足够长" * 4, evidence="证据足够长" * 4, implication="意义足够长" * 4),
            Finding(statement="陈述足够长" * 4, evidence="证据足够长" * 4, implication="意义足够长" * 4),
            Finding(statement="陈述足够长" * 4, evidence="证据足够长" * 4, implication="意义足够长" * 4),
        ],
        analysis_sections=[
            AnalysisSection(section_id=f"sec-{i}", heading="深度章节", narrative="x" * 300, section_type="overview")
            for i in range(4)
        ],
        swot=Swot(
            strengths=[sw_entry], weaknesses=[sw_entry],
            opportunities=[sw_entry], threats=[sw_entry],
        ),
        conclusions="y" * 300,
        recommendations=[
            Recommendation(
                action="行动描述够长" * 4, target_role="产品经理",
                priority="critical", timeline="immediate",
                rationale="依据描述够长足够长" * 3,
            ),
        ] * 3,
        scenario_payload=_make_minimal_s1_payload(),
    )


def test_base_report_union_constructs_s1():
    """完整 BaseReport 构造（S1 场景），union discriminator 工作"""
    report = _make_minimal_base_report("S1")
    assert report.scenario == "S1"
    assert report.scenario_payload.scenario_type == "S1"


def test_base_report_metadata_scenario_consistency():
    """metadata.scenario 与 scenario_payload.scenario_type 不一致应拒"""
    with pytest.raises(ValidationError, match="but"):
        _make_minimal_base_report("S2")  # metadata="S2"，但 payload 是 S1
