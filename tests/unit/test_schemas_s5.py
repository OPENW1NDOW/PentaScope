import pytest
from pydantic import ValidationError
from src.schemas.scenarios.s5 import (
    S5VendorProfile, PerceptualMap, PerceptualAxis,
    PlottedBrand, ValueCurve, CompetitiveFactor, StrategyCanvas,
    PositioningStatement,
)
from src.schemas.common import SourceRef
from src.schemas.scenarios.s1 import VendorStrength, VendorCaution


def _ok_strength():
    return VendorStrength(point="某项核心优势描述至少十字", evidence="官网功能页有详细的截图说明")


def _ok_caution():
    return VendorCaution(point="某项需注意点描述至少十字", evidence="用户论坛有大量差评汇总记录")


def test_mq_quadrant_computed():
    """mq_quadrant 由两轴总分代码派生（>= 2.5 算高）"""
    long_rationale = "x" * 60
    long_v_rationale = "y" * 60
    profile = S5VendorProfile(
        competitor_name="A",
        ability_to_execute_score=4.0,
        ability_to_execute_rationale=long_rationale,
        completeness_of_vision_score=4.0,
        completeness_of_vision_rationale=long_v_rationale,
        overview="A 的产品简介足够长一些字数补满二十字以上的内容",
        strengths=[_ok_strength(), _ok_strength()],
        cautions=[_ok_caution()],
        source_refs=[SourceRef(url="https://example.com")],
    )
    assert profile.mq_quadrant == "mq_leader"

    profile_low = S5VendorProfile(
        competitor_name="B",
        ability_to_execute_score=1.0,
        ability_to_execute_rationale=long_rationale,
        completeness_of_vision_score=1.0,
        completeness_of_vision_rationale=long_v_rationale,
        overview="B 的产品简介足够长一些字数补满二十字以上的内容",
        strengths=[_ok_strength(), _ok_strength()],
        cautions=[_ok_caution()],
        source_refs=[SourceRef(url="https://example.com")],
    )
    assert profile_low.mq_quadrant == "mq_niche_player"


def test_perceptual_axis_x_y_must_differ():
    """x_axis 和 y_axis 不能同 attribute"""
    axis_a = PerceptualAxis(
        attribute="易用性能", low_label="复杂", high_label="简单",
        rationale="选这条轴的理由长度补够二十字字数足以满足约束",
    )
    with pytest.raises(ValidationError, match="不能是同一 attribute"):
        PerceptualMap(
            artifact_id="pm-x1", x_axis=axis_a, y_axis=axis_a,
            plotted_brands=[
                PlottedBrand(
                    competitor_name="A", x_score=2, y_score=3,
                    confidence="medium", score_rationale="x" * 30,
                ),
                PlottedBrand(
                    competitor_name="B", x_score=4, y_score=4,
                    confidence="medium", score_rationale="x" * 30,
                ),
                PlottedBrand(
                    competitor_name="C", x_score=1, y_score=1,
                    confidence="low", score_rationale="x" * 30,
                ),
            ],
        )


def test_plotted_brand_score_le_scale_max():
    """坐标 ≤ scale_max"""
    axis_x = PerceptualAxis(
        attribute="价格水平", low_label="便宜", high_label="昂贵",
        rationale="选这条轴的理由长度补够二十字字数足以满足约束", scale_max=5,
    )
    axis_y = PerceptualAxis(
        attribute="易用程度", low_label="难用", high_label="简易",
        rationale="选这条轴的理由长度补够二十字字数足以满足约束", scale_max=5,
    )
    with pytest.raises(ValidationError, match="超过 x_axis.scale_max"):
        PerceptualMap(
            artifact_id="pm-y1", x_axis=axis_x, y_axis=axis_y,
            plotted_brands=[
                PlottedBrand(
                    competitor_name="A", x_score=8, y_score=2,
                    confidence="medium", score_rationale="x" * 30,
                ),
                PlottedBrand(
                    competitor_name="B", x_score=2, y_score=2,
                    confidence="low", score_rationale="x" * 30,
                ),
                PlottedBrand(
                    competitor_name="C", x_score=3, y_score=3,
                    confidence="low", score_rationale="x" * 30,
                ),
            ],
        )


def test_strategy_canvas_factor_key_completeness():
    """每个 value_curve.factor_levels 必须等于 competitive_factors 的 name 集合"""
    factors = [
        CompetitiveFactor(name="价格水平", industry_avg_level=5),
        CompetitiveFactor(name="功能丰富度", industry_avg_level=5),
        CompetitiveFactor(name="易用性程度", industry_avg_level=5),
        CompetitiveFactor(name="服务质量", industry_avg_level=5),
        CompetitiveFactor(name="品牌力度", industry_avg_level=5),
    ]
    with pytest.raises(ValidationError, match="不一致"):
        StrategyCanvas(
            artifact_id="sc-x", competitive_factors=factors,
            value_curves=[
                ValueCurve(competitor_name="A", factor_levels={"价格水平": 5}),
                ValueCurve(competitor_name="B", factor_levels={
                    "价格水平": 4, "功能丰富度": 4, "易用性程度": 4,
                    "服务质量": 4, "品牌力度": 4,
                }),
            ],
        )


def _ok_positioning_statement(confidence):
    return PositioningStatement(
        target_customer="目标客户描述至少十字以上",
        need_or_opportunity="痛点描述足够长一些字数",
        product_name="MyX",
        product_category="智能 SaaS",
        key_benefit="核心价值描述至少十字内容",
        primary_alternative="主要替代品",
        primary_differentiation="差异化描述至少十字字数",
        confidence=confidence,
    )


def test_positioning_statement_full_text_with_watermark():
    """非 from_user_brief 时添加水印"""
    ps = _ok_positioning_statement("llm_inferred")
    assert "[AI 推断版本" in ps.full_statement_text


def test_positioning_statement_no_watermark_for_user_brief():
    ps = _ok_positioning_statement("from_user_brief")
    assert "[AI 推断版本" not in ps.full_statement_text
