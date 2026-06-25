import pytest
from pydantic import ValidationError
from src.schemas.input import ScenarioInput, CompetitorBasic


def test_s2_requires_industry_competitors_optional():
    si = ScenarioInput(
        scenario="S2",
        industry="知识管理 SaaS",
        analysis_context="找头部玩家",
    )
    assert si.competitors == []


def test_s1_requires_competitors_and_our_product():
    with pytest.raises(ValidationError, match="our_product_name"):
        ScenarioInput(
            scenario="S1",
            competitors=[CompetitorBasic(name="飞书")],
            analysis_context="x",
        )

    si = ScenarioInput(
        scenario="S1",
        competitors=[CompetitorBasic(name="飞书")],
        our_product_name="MyProduct",
        analysis_context="x",
    )
    assert si.our_product_name == "MyProduct"


def test_competitor_name_allows_single_char():
    """[#min_length 放宽] CompetitorBasic.name min_length=1，允许单字符/短竞品名（如 'Go'、'V'）。"""
    cb = CompetitorBasic(name="V")
    assert cb.name == "V"


def test_s2_no_industry_fails():
    with pytest.raises(ValidationError, match="industry"):
        ScenarioInput(
            scenario="S2",
            analysis_context="x",
        )


def test_s4_can_carry_prior_trace_id():
    si = ScenarioInput(
        scenario="S4",
        competitors=[CompetitorBasic(name="飞书")],
        our_product_name="MyProduct",
        analysis_context="例行监控",
        prior_trace_id="abc-123-uuid",
    )
    assert si.prior_trace_id == "abc-123-uuid"


def test_s3_no_competitors_fails():
    with pytest.raises(ValidationError, match="必须提供至少一个 competitor"):
        ScenarioInput(
            scenario="S3",
            our_product_name="MyProduct",
            analysis_context="定价",
        )


def test_competitor_input_alias_still_works():
    """旧 import CompetitorInput 不应破坏（兼容性占位）"""
    from src.schemas.input import CompetitorInput
    assert CompetitorInput is ScenarioInput
