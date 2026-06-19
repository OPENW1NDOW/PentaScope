"""S3 定价策略场景载荷"""
from typing import Literal, Optional
from pydantic import BaseModel, Field, computed_field, model_validator

from src.schemas.common import ArtifactBase, SourceRef
from src.schemas.scenarios.s2 import Risk


class PricingBaseline(BaseModel):
    current_pricing_model: Literal[
        "per_seat", "flat_rate", "usage_based", "hybrid", "freemium", "platform_fee", "unknown"
    ]
    current_tier_count: int = Field(ge=0, le=10)
    current_arpu_note: str = Field(default="")
    pain_points: list[str] = Field(min_length=1)
    source_refs: list[SourceRef] = Field(default_factory=list)


class ValueDriver(BaseModel):
    driver_name: str = ""
    importance: Literal["low", "medium", "high"]
    evidence: str = ""
    source_refs: list[SourceRef] = Field(default_factory=list)


class FeatureClassification(BaseModel):
    """功能分类（hygiene / preference / premium driver）"""
    hygiene_factors: list[str] = Field(min_length=1)
    preference_drivers: list[str] = Field(default_factory=list)
    premium_drivers: list[str] = Field(min_length=1)


class WTPResearch(BaseModel):
    """支付意愿研究（首版 Optional）"""
    method: Literal[
        "conjoint_analysis", "van_westendorp", "gabor_granger",
        "interviews", "ab_testing", "proxy_from_competitor_pricing"
    ]
    sample_size: Optional[int] = None
    optimal_price_point: Optional[str] = None
    confidence: Literal["low", "medium", "high"] = "low"
    rationale: str = ""
    limitations: str = Field(default="")

    @model_validator(mode='after')
    def _enforce_proxy_low_confidence(self) -> 'WTPResearch':
        if self.method == "proxy_from_competitor_pricing":
            if self.confidence != "low":
                raise ValueError("WTPResearch.method=proxy_from_competitor_pricing 时 confidence 必须为 low")
            if not self.limitations:
                raise ValueError("WTPResearch.method=proxy_from_competitor_pricing 时 limitations 必填")
        return self


class RecommendedPriceTier(BaseModel):
    """我方推荐套餐的单层（用于 Packaging）"""
    name: str = ""
    position: Literal["good", "better", "best", "enterprise", "free"]
    monthly_price: Optional[float] = Field(default=None, ge=0)
    annual_price: Optional[float] = Field(default=None, ge=0)
    currency: Literal["CNY", "USD", "EUR", "JPY", "unknown"] = "CNY"
    billing_unit: Literal["per_seat", "flat_rate", "usage_based", "tier_subscription"]
    is_recommended: bool = False
    target_persona: str = ""
    included_features: list[str] = Field(min_length=1)
    gated_features: list[str] = Field(default_factory=list)
    cta_copy: str = Field(default="")
    upgrade_trigger: str = Field(default="")

    @model_validator(mode='after')
    def _check_annual_le_monthly_x12(self) -> 'RecommendedPriceTier':
        if self.monthly_price is not None and self.annual_price is not None:
            if self.annual_price > self.monthly_price * 12:
                raise ValueError(
                    f"annual_price {self.annual_price} > monthly_price x12 {self.monthly_price * 12}"
                )
        return self


class ObservedCompetitorTier(BaseModel):
    """竞品现有套餐的单层（每条价格强制 source_refs）"""
    name: str = ""
    monthly_price: Optional[float] = Field(default=None, ge=0)
    annual_price: Optional[float] = Field(default=None, ge=0)
    currency: Literal["CNY", "USD", "EUR", "JPY", "unknown"] = "CNY"
    billing_unit: Literal["per_seat", "flat_rate", "usage_based", "tier_subscription"]
    observed_is_most_popular: bool = False
    observed_target_persona: str = Field(default="")
    observed_features: list[str] = Field(min_length=1)
    observed_cta_copy: str = Field(default="")
    source_refs: list[SourceRef] = Field(min_length=1)


class Packaging(ArtifactBase):
    """推荐套餐设计（GBB 三层套餐法）"""
    artifact_type: Literal["packaging"] = "packaging"
    tiers: list[RecommendedPriceTier] = Field(min_length=2, max_length=5)
    annual_discount_pct: Optional[float] = Field(default=None, ge=0, le=50)
    default_billing_cycle: Literal["monthly", "annual"] = "annual"
    rationale: str = ""

    @model_validator(mode='after')
    def _check_recommended_tier(self) -> 'Packaging':
        recommended = [t for t in self.tiers if t.is_recommended]
        if len(recommended) != 1:
            raise ValueError(
                f"Packaging 应有且仅有一个 is_recommended tier，发现 {len(recommended)} 个"
            )
        return self

    @model_validator(mode='after')
    def _check_position_uniqueness(self) -> 'Packaging':
        positions = [t.position for t in self.tiers]
        for p in ["good", "better", "best"]:
            if positions.count(p) > 1:
                raise ValueError(f"position={p} 在 tiers 中重复 {positions.count(p)} 次")
        return self


class CompetitorPricing(ArtifactBase):
    """单个竞品的定价矩阵"""
    artifact_type: Literal["competitor_pricing"] = "competitor_pricing"
    competitor_name: str = ""
    pricing_model: Literal[
        "per_seat", "flat_rate", "usage_based", "hybrid", "freemium", "platform_fee", "unknown"
    ]
    tiers: list[ObservedCompetitorTier] = Field(min_length=1)
    free_plan_strategy: Optional[Literal["freemium", "free_trial", "no_free_plan"]] = None
    discount_strategy: str = Field(default="")
    notes: str = Field(default="")
    source_refs: list[SourceRef] = Field(min_length=1)


class PricingPageAuditScore(BaseModel):
    rule_name: Literal[
        "tier_naming_buyer_centric",
        "anchor_pricing_middle_tier",
        "annual_billing_default",
        "feature_gating_clear",
        "cta_copy_aligned",
        "social_proof_at_decision",
        "transparent_feature_comparison",
        "psychological_pricing",
    ]
    passed: bool
    note: str = Field(default="")


class PricingPageAudit(ArtifactBase):
    """竞品定价页审计（无 URL 时不允许填 audit_scores）"""
    artifact_type: Literal["pricing_page_audit"] = "pricing_page_audit"
    competitor_name: str = ""
    audit_scores: list[PricingPageAuditScore] = Field(default_factory=list, max_length=8)
    pricing_page_url: Optional[str] = Field(default=None, min_length=8)
    source_refs: list[SourceRef] = Field(default_factory=list)

    @computed_field
    @property
    def overall_score_pct(self) -> Optional[float]:
        if not self.audit_scores:
            return None
        passed_count = sum(1 for s in self.audit_scores if s.passed)
        return round(passed_count / len(self.audit_scores) * 100, 1)

    @model_validator(mode='after')
    def _check_no_url_no_audit(self) -> 'PricingPageAudit':
        if self.pricing_page_url is None and self.audit_scores:
            raise ValueError("未采集到 pricing_page_url 时，audit_scores 必须为空")
        return self


class PricingRecommendationsSummary(BaseModel):
    """推荐定价方案总结"""
    recommended_packaging_summary: str = ""
    expected_arr_uplift_pct: Optional[float] = Field(default=None, ge=-50, le=200)
    expected_arr_uplift_basis: Literal[
        "measured_pilot", "competitor_benchmark", "industry_estimate", "llm_inferred"
    ] = "llm_inferred"
    expected_arr_uplift_methodology: str = Field(default="")
    expected_uplift_rationale: str = ""
    main_risks: list[Risk] = Field(min_length=1)

    @model_validator(mode='after')
    def _require_methodology_for_specific_basis(self) -> 'PricingRecommendationsSummary':
        if self.expected_arr_uplift_basis != "llm_inferred":
            if not self.expected_arr_uplift_methodology or len(self.expected_arr_uplift_methodology) < 20:
                raise ValueError(
                    f"expected_arr_uplift_basis={self.expected_arr_uplift_basis} 时 methodology 必填且 ≥20 字"
                )
        return self


class RolloutStep(ArtifactBase):
    """Rollout 步骤"""
    artifact_type: Literal["rollout_step"] = "rollout_step"
    step_name: str = ""
    description: str = ""
    duration: str
    owner_team: str = Field(default="")
    success_metric: str = Field(default="")


class S3PricingStrategyPayload(BaseModel):
    """S3 定价策略场景载荷"""
    scenario_type: Literal["S3"] = "S3"

    pricing_baseline: PricingBaseline

    value_drivers: list[ValueDriver] = Field(min_length=3)
    feature_classification: FeatureClassification

    wtp_research: Optional[WTPResearch] = None

    packaging: Packaging

    competitive_pricing_matrix: list[CompetitorPricing] = Field(min_length=2)

    pricing_page_audit: list[PricingPageAudit] = Field(default_factory=list)

    recommendations_summary: PricingRecommendationsSummary
    rollout_plan: list[RolloutStep] = Field(min_length=3)

    @model_validator(mode='after')
    def _check_competitor_consistency(self) -> 'S3PricingStrategyPayload':
        matrix_competitors = {cp.competitor_name for cp in self.competitive_pricing_matrix}
        audit_competitors = {pa.competitor_name for pa in self.pricing_page_audit}
        if audit_competitors and not audit_competitors.issubset(matrix_competitors):
            raise ValueError(
                f"pricing_page_audit 竞品 {audit_competitors} 不在 competitive_pricing_matrix 中"
            )
        return self
