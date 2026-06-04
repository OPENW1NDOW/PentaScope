import pytest
from pydantic import ValidationError
from src.schemas.input import CompetitorBasic, AnalysisGoal, CompetitorInput
from src.schemas.profile import CompetitorProfile
from src.schemas.analysis import CompetitiveAnalysis
from src.schemas.report import FinalReport
from src.schemas.feedback import RejectionFeedback, FeedbackIssue, AgentMessage


class TestCompetitorBasic:
    def test_valid_minimal(self):
        c = CompetitorBasic(name="支付宝")
        assert c.name == "支付宝"
        assert c.company == ""
        assert c.category == ""

    def test_valid_full(self):
        c = CompetitorBasic(name="支付宝", company="蚂蚁集团", category="金融科技")
        assert c.company == "蚂蚁集团"

    def test_name_too_short(self):
        with pytest.raises(ValidationError):
            CompetitorBasic(name="支")

    def test_name_too_long(self):
        with pytest.raises(ValidationError):
            CompetitorBasic(name="a" * 51)

    def test_name_empty(self):
        with pytest.raises(ValidationError):
            CompetitorBasic(name="")


class TestAnalysisGoal:
    def test_defaults(self):
        g = AnalysisGoal()
        assert g.goal_type == "competitive_monitoring"
        assert g.product_stage == "growing"
        assert g.output_expectation == "action"

    def test_valid_types(self):
        g = AnalysisGoal(goal_type="feature_iteration", product_stage="entering", output_expectation="info")
        assert g.goal_type == "feature_iteration"

    def test_invalid_goal_type(self):
        with pytest.raises(ValidationError):
            AnalysisGoal(goal_type="invalid_type")


class TestCompetitorInput:
    def test_valid(self):
        ci = CompetitorInput(
            competitors=[CompetitorBasic(name="支付宝"), CompetitorBasic(name="微信支付")],
            analysis_context="分析移动支付竞品"
        )
        assert len(ci.competitors) == 2

    def test_empty_competitors(self):
        with pytest.raises(ValidationError):
            CompetitorInput(competitors=[], analysis_context="test")

    def test_too_many_competitors(self):
        with pytest.raises(ValidationError):
            CompetitorInput(
                competitors=[CompetitorBasic(name=f"竞品{i}") for i in range(11)],
                analysis_context="test"
            )


class TestCompetitorProfile:
    def test_valid_full(self, sample_competitor_profile):
        p = CompetitorProfile(**sample_competitor_profile)
        assert p.classification.competitor_type == "核心竞品"
        assert p.basic_info.name == "支付宝"
        assert len(p.feature_tree) == 1
        assert p.metadata.completeness_score == 0.85

    def test_completeness_score_range(self, sample_competitor_profile):
        sample_competitor_profile["metadata"]["completeness_score"] = 1.5
        with pytest.raises(ValidationError):
            CompetitorProfile(**sample_competitor_profile)

    def test_empty_feature_tree(self, sample_competitor_profile):
        sample_competitor_profile["feature_tree"] = []
        p = CompetitorProfile(**sample_competitor_profile)
        assert p.feature_tree == []


class TestCompetitiveAnalysis:
    def test_valid_full(self, sample_competitive_analysis):
        a = CompetitiveAnalysis(**sample_competitive_analysis)
        assert len(a.positioning.per_competitor) == 1
        assert len(a.feature_matrix) == 1
        assert a.feature_matrix[0].gap_level == "落后"
        assert len(a.radar_scores) == 1
        assert a.radar_scores[0].dimensions.feature_breadth == 4.5

    def test_swot_has_dimension(self, sample_competitive_analysis):
        a = CompetitiveAnalysis(**sample_competitive_analysis)
        assert a.swot.strengths[0].dimension == "positioning"

    def test_radar_score_range(self, sample_competitive_analysis):
        sample_competitive_analysis["radar_scores"][0]["dimensions"]["feature_breadth"] = 6.0
        with pytest.raises(ValidationError):
            CompetitiveAnalysis(**sample_competitive_analysis)


class TestFinalReport:
    def test_valid_full(self, sample_final_report):
        r = FinalReport(**sample_final_report)
        assert r.title == "支付宝竞品分析报告"
        assert len(r.action_items.immediate) == 1
        assert r.metadata.quality_score == 0.85

    def test_action_items_time_layers(self, sample_final_report):
        r = FinalReport(**sample_final_report)
        assert r.action_items.immediate[0].priority == "高"
        assert r.action_items.short_term[0].priority == "中"
        assert r.action_items.long_term[0].priority == "低"


class TestRejectionFeedback:
    def test_valid(self):
        f = RejectionFeedback(
            passed=False,
            issues=[FeedbackIssue(agent="collector", field="feature_tree", severity="critical", reason="为空", suggestion="补充功能数据")],
            retry_count=0, max_retries=2
        )
        assert f.passed is False
        assert f.issues[0].agent == "collector"

    def test_passed_no_issues(self):
        f = RejectionFeedback(passed=True, issues=[], retry_count=0, max_retries=2)
        assert f.passed is True


class TestAgentMessage:
    def test_valid(self):
        m = AgentMessage(
            from_agent="collector", to_agent="analyzer",
            message_type="result", payload={"profiles": []},
            timestamp="2026-05-31T10:00:00", trace_id="abc-123"
        )
        assert m.from_agent == "collector"


def test_final_report_has_structured_fields_with_defaults():
    from src.schemas.report import FinalReport
    report = FinalReport(title="t")
    assert report.swot.strengths == []
    assert report.radar_scores == []
    assert report.feature_matrix == []


def test_report_section_dimension_defaults_overview():
    from src.schemas.report import ReportSection
    sec = ReportSection(title="概览")
    assert sec.dimension == "overview"


def test_report_section_dimension_accepts_analysis_keys():
    from src.schemas.report import ReportSection
    for d in ["positioning", "feature_matrix", "business_model",
              "operations", "user_sentiment", "swot", "overview"]:
        assert ReportSection(title="x", dimension=d).dimension == d
