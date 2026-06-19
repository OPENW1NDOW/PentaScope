"""S1 功能迭代场景载荷"""
from datetime import date
from typing import Literal, Optional
from pydantic import BaseModel, Field, computed_field, model_validator

from src.schemas.common import ArtifactBase, SourceRef


class VendorStrength(BaseModel):
    point: str
    evidence: str = ""
    source_refs: list[SourceRef] = Field(default_factory=list)


class VendorCaution(BaseModel):
    point: str
    evidence: str = ""
    source_refs: list[SourceRef] = Field(default_factory=list)


class S1VendorProfile(BaseModel):
    competitor_name: str = Field(min_length=1)
    wave_position: Literal["wave_leader", "wave_strong_performer", "wave_contender"]
    one_line_pitch: str = Field(max_length=150)
    strengths: list[VendorStrength] = Field(min_length=1, max_length=5)
    cautions: list[VendorCaution] = Field(min_length=1, max_length=4)
    best_fit_for: str = ""
    reference_customer_feedback: str = Field(default="")
    source_refs: list[SourceRef] = Field(default_factory=list)


class FeatureScore(BaseModel):
    """0-2 评分制单元格 + evidence_url 强制"""
    score: Literal[0, 1, 2]
    note: str = ""
    evidence_url: Optional[str] = Field(default=None, min_length=8)
    source_missing_reason: Optional[str] = None
    last_verified: Optional[date] = None

    @model_validator(mode='after')
    def _check_evidence(self) -> 'FeatureScore':
        if self.score == 2 and not self.evidence_url:
            raise ValueError("score=2 必须提供 evidence_url（'完整支持'必有来源）")
        if self.score == 0 and not self.evidence_url and not self.source_missing_reason:
            raise ValueError("score=0 必须提供 evidence_url 或 source_missing_reason")
        return self


class FeatureRow(BaseModel):
    name: str
    description: str = ""
    scores: dict[str, FeatureScore]


class FeatureCategory(BaseModel):
    name: str
    tier: Literal[1, 2, 3]
    features: list[FeatureRow] = Field(min_length=1)

    @computed_field
    @property
    def weight(self) -> int:
        return {1: 3, 2: 2, 3: 1}[self.tier]


class FeatureMatrix(ArtifactBase):
    """加权评分功能矩阵"""
    artifact_type: Literal["feature_matrix"] = "feature_matrix"
    competitors: list[str] = Field(min_length=2)
    our_product_name: str = Field(min_length=1)
    categories: list[FeatureCategory] = Field(min_length=1)

    @computed_field
    @property
    def weighted_scores(self) -> dict[str, float]:
        scores: dict[str, float] = {}
        for c in self.competitors:
            total = 0
            max_total = 0
            for cat in self.categories:
                w = cat.weight
                for f in cat.features:
                    if c in f.scores:
                        total += f.scores[c].score * w
                    max_total += 2 * w
            scores[c] = round(total / max_total * 100, 1) if max_total > 0 else 0.0
        return scores


class Tier1Disqualifier(BaseModel):
    feature: str
    competitors_failing: list[str] = Field(min_length=1)
    implication: str = ""


class WhiteSpaceFeature(BaseModel):
    feature: str
    why_no_one_supports: str = ""
    opportunity_estimate: Literal["high", "medium", "low"]


class S1RadarScore(ArtifactBase):
    """S1 雷达图（5 维多边形，区别于 S5 perceptual map 二维散点）"""
    artifact_type: Literal["s1_radar_score"] = "s1_radar_score"
    competitor_name: str = Field(min_length=1)
    feature_breadth: float = Field(ge=0, le=5)
    usability: float = Field(ge=0, le=5)
    cost_effectiveness: float = Field(ge=0, le=5)
    stability: float = Field(ge=0, le=5)
    design_quality: float = Field(ge=0, le=5)


class JobStatement(BaseModel):
    """When [situation], I want to [motivation], so I can [outcome]"""
    situation: str
    motivation: str
    outcome: str
    layer: Literal["functional", "emotional", "social"] = "functional"


class FeatureGap(BaseModel):
    feature_name: str
    competitors_have_it: list[str] = Field(min_length=1)
    underserved_outcome: str = ""
    estimated_effort: Literal["low", "medium", "high"]
    estimated_impact: Literal["low", "medium", "high"]
    recommendation: Literal["build", "skip", "differentiate"]
    source_refs: list[SourceRef] = Field(default_factory=list)


class RoadmapRecommendations(BaseModel):
    must_build: list[str] = Field(min_length=1)
    should_skip: list[str] = Field(default_factory=list)
    should_differentiate: list[str] = Field(default_factory=list)
    rationale_summary: str = ""


class S1FeatureIterationPayload(BaseModel):
    """S1 功能迭代场景载荷"""
    scenario_type: Literal["S1"] = "S1"

    vendor_profiles: list[S1VendorProfile] = Field(min_length=2)

    feature_matrix: FeatureMatrix
    tier1_disqualifiers: list[Tier1Disqualifier] = Field(default_factory=list)
    white_space_features: list[WhiteSpaceFeature] = Field(default_factory=list)

    radar_scores: list[S1RadarScore] = Field(min_length=2)

    job_statement: JobStatement

    feature_gaps: list[FeatureGap] = Field(min_length=1)
    roadmap_recommendations: RoadmapRecommendations

    @model_validator(mode='after')
    def _check_competitor_consistency(self) -> 'S1FeatureIterationPayload':
        matrix_competitors = set(self.feature_matrix.competitors)
        vendor_names = {vp.competitor_name for vp in self.vendor_profiles}
        radar_names = {rs.competitor_name for rs in self.radar_scores}
        if not vendor_names.issubset(matrix_competitors):
            raise ValueError(
                f"vendor_profiles 竞品名 {vendor_names} 不在 feature_matrix.competitors {matrix_competitors} 中"
            )
        if not radar_names.issubset(matrix_competitors):
            raise ValueError(
                f"radar_scores 竞品名 {radar_names} 不在 feature_matrix.competitors {matrix_competitors} 中"
            )
        return self
