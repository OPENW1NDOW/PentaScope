import pytest
from pydantic import ValidationError
from src.schemas.scenarios.s3 import (
    WTPResearch, RecommendedPriceTier, ObservedCompetitorTier,
    Packaging, PricingPageAudit, PricingPageAuditScore,
)
from src.schemas.common import SourceRef


def test_observed_tier_requires_source_refs():
    """ObservedCompetitorTier 必须 source_refs（防幻觉）"""
    with pytest.raises(ValidationError):
        ObservedCompetitorTier(
            name="Pro", monthly_price=10, currency="CNY",
            billing_unit="per_seat", observed_features=["f1"],
        )
    t = ObservedCompetitorTier(
        name="Pro", monthly_price=10, currency="CNY",
        billing_unit="per_seat", observed_features=["f1"],
        source_refs=[SourceRef(url="https://example.com/pricing")],
    )
    assert t.name == "Pro"


def test_packaging_must_have_exactly_one_recommended():
    """有且仅有一个 is_recommended"""
    t1 = RecommendedPriceTier(
        name="Free", position="free", billing_unit="flat_rate",
        target_persona="个人用户描述十字以上",
        included_features=["基础"],
    )
    t2 = RecommendedPriceTier(
        name="Pro", position="better", billing_unit="per_seat",
        target_persona="团队用户描述十字以上",
        included_features=["进阶"], is_recommended=True,
    )
    p = Packaging(
        artifact_id="pkg1", tiers=[t1, t2],
        rationale="设计理由长描述足够多字数补满五十字以上的内容描述详细" * 2,
    )
    assert p.tiers[1].is_recommended

    # 0 个 recommended 应失败
    with pytest.raises(ValidationError):
        Packaging(
            artifact_id="pkg1",
            tiers=[t1, RecommendedPriceTier(
                name="Pro", position="better", billing_unit="per_seat",
                target_persona="x" * 10, included_features=["a"],
            )],
            rationale="x" * 60,
        )


def test_pricing_page_audit_overall_score_computed():
    pa = PricingPageAudit(
        artifact_id="pa1",
        competitor_name="A",
        audit_scores=[
            PricingPageAuditScore(rule_name="tier_naming_buyer_centric", passed=True),
            PricingPageAuditScore(rule_name="anchor_pricing_middle_tier", passed=False),
        ],
        pricing_page_url="https://example.com/pricing",
    )
    assert pa.overall_score_pct == 50.0


def test_wtp_proxy_requires_low_confidence():
    """proxy_from_competitor_pricing 必须 confidence=low"""
    with pytest.raises(ValidationError):
        WTPResearch(
            method="proxy_from_competitor_pricing",
            confidence="medium",
            rationale="基于竞品价格估算的支付意愿",
        )


def test_recommended_tier_annual_le_monthly_x12():
    """年付不能超过月付 x12"""
    with pytest.raises(ValidationError):
        RecommendedPriceTier(
            name="Pro", position="better", billing_unit="per_seat",
            monthly_price=10, annual_price=200,
            target_persona="x" * 10, included_features=["a"],
        )


def test_no_url_no_audit_validator():
    """无 pricing_page_url 时不允许填 audit_scores"""
    with pytest.raises(ValidationError):
        PricingPageAudit(
            artifact_id="pa1", competitor_name="A",
            audit_scores=[
                PricingPageAuditScore(rule_name="tier_naming_buyer_centric", passed=True),
            ],
        )
