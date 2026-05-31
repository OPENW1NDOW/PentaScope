import pytest
from pydantic import ValidationError
from src.schemas.input import CompetitorBasic, AnalysisGoal, CompetitorInput


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
                competitors=[CompetitorBasic(name=f"竞品{i}") for i in range(6)],
                analysis_context="test"
            )
