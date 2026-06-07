"""S5 战略定位场景载荷"""
from typing import Literal, Optional
from pydantic import BaseModel, Field, computed_field, model_validator

from src.schemas.common import ArtifactBase, SourceRef
from src.schemas.scenarios.s1 import VendorStrength, VendorCaution


class S5VendorProfile(BaseModel):
    """仿 Gartner MQ Vendor Strengths & Cautions 卡（mq_quadrant 由代码派生）"""
    competitor_name: str = Field(min_length=1)

    ability_to_execute_score: float = Field(ge=0, le=5)
    ability_to_execute_rationale: str = Field(min_length=50)
    completeness_of_vision_score: float = Field(ge=0, le=5)
    completeness_of_vision_rationale: str = Field(min_length=50)

    overview: str = Field(min_length=20, max_length=200)
    strengths: list[VendorStrength] = Field(min_length=2, max_length=5)
    cautions: list[VendorCaution] = Field(min_length=1, max_length=4)
    source_refs: list[SourceRef] = Field(min_length=1)

    @computed_field
    @property
    def mq_quadrant(self) -> Literal["mq_leader", "mq_challenger", "mq_visionary", "mq_niche_player"]:
        e_high = self.ability_to_execute_score >= 2.5
        v_high = self.completeness_of_vision_score >= 2.5
        if e_high and v_high:
            return "mq_leader"
        if e_high and not v_high:
            return "mq_challenger"
        if not e_high and v_high:
            return "mq_visionary"
        return "mq_niche_player"


class PerceptualAxis(BaseModel):
    """Perceptual Map 的一个轴"""
    attribute: str = Field(min_length=4)
    low_label: str = Field(min_length=2)
    high_label: str = Field(min_length=2)
    scale_max: int = Field(default=5, ge=3, le=10)
    rationale: str = Field(min_length=20)


class PlottedBrand(BaseModel):
    """Perceptual Map 上的单个品牌位置"""
    competitor_name: str = Field(min_length=1)
    is_self: bool = False
    x_score: float = Field(ge=0)
    y_score: float = Field(ge=0)
    bubble_size_metric: Optional[float] = None

    confidence: Literal["high", "medium", "low"]
    score_rationale: str = Field(min_length=20)
    source_refs: list[SourceRef] = Field(default_factory=list)


class WhiteSpaceZone(BaseModel):
    quadrant: Literal["top_right", "top_left", "bottom_right", "bottom_left", "center"]
    opportunity_description: str = Field(min_length=20)
    interpretation: str = Field(default="")


class ClusterZone(BaseModel):
    brands_in_cluster: list[str] = Field(min_length=2)
    implication: str = Field(min_length=20)


class PerceptualMap(ArtifactBase):
    """二维感知地图"""
    artifact_type: Literal["perceptual_map"] = "perceptual_map"
    x_axis: PerceptualAxis
    y_axis: PerceptualAxis
    plotted_brands: list[PlottedBrand] = Field(min_length=3)
    white_space: list[WhiteSpaceZone] = Field(default_factory=list)
    cluster_zones: list[ClusterZone] = Field(default_factory=list)

    display_watermark: str = Field(default="基于公开信息 AI 推断，非客户调研真实分数")

    @model_validator(mode='after')
    def _check_axes_and_scores(self) -> 'PerceptualMap':
        if self.x_axis.attribute == self.y_axis.attribute:
            raise ValueError(
                f"x_axis 和 y_axis 不能是同一 attribute（'{self.x_axis.attribute}'）"
            )
        for b in self.plotted_brands:
            if b.x_score > self.x_axis.scale_max:
                raise ValueError(
                    f"plotted_brands['{b.competitor_name}'].x_score={b.x_score} "
                    f"超过 x_axis.scale_max={self.x_axis.scale_max}"
                )
            if b.y_score > self.y_axis.scale_max:
                raise ValueError(
                    f"plotted_brands['{b.competitor_name}'].y_score={b.y_score} "
                    f"超过 y_axis.scale_max={self.y_axis.scale_max}"
                )
        return self


class CompetitiveFactor(BaseModel):
    name: str = Field(min_length=4)
    industry_avg_level: float = Field(ge=0, le=10)


class ValueCurve(BaseModel):
    """单品牌的 value curve"""
    competitor_name: str = Field(min_length=1)
    is_self: bool = False
    factor_levels: dict[str, float]
    source_refs: list[SourceRef] = Field(default_factory=list)

    @model_validator(mode='after')
    def _check_factor_levels_range(self) -> 'ValueCurve':
        for name, level in self.factor_levels.items():
            if not (0 <= level <= 10):
                raise ValueError(f"factor_levels['{name}']={level} 不在 0-10 范围内")
        return self


class StrategyCanvas(ArtifactBase):
    """战略画布"""
    artifact_type: Literal["strategy_canvas"] = "strategy_canvas"
    competitive_factors: list[CompetitiveFactor] = Field(min_length=5, max_length=15)
    value_curves: list[ValueCurve] = Field(min_length=2)

    @model_validator(mode='after')
    def _check_factor_key_completeness(self) -> 'StrategyCanvas':
        factor_names = {f.name for f in self.competitive_factors}
        for vc in self.value_curves:
            curve_keys = set(vc.factor_levels.keys())
            if curve_keys != factor_names:
                missing = factor_names - curve_keys
                extra = curve_keys - factor_names
                raise ValueError(
                    f"value_curve['{vc.competitor_name}'].factor_levels 与 competitive_factors 不一致："
                    f"missing={missing}, extra={extra}"
                )
        return self


class ERRCAction(BaseModel):
    factor: str = Field(min_length=4)
    rationale: str = Field(min_length=20)
    proposed_level: Optional[float] = Field(default=None, ge=0, le=10)
    buyer_value: str = Field(default="")


class ERRCGrid(ArtifactBase):
    """ERRC 4 宫格"""
    artifact_type: Literal["errc_grid"] = "errc_grid"
    eliminate: list[ERRCAction] = Field(default_factory=list)
    reduce: list[ERRCAction] = Field(default_factory=list)
    raise_level: list[ERRCAction] = Field(default_factory=list)
    create: list[ERRCAction] = Field(default_factory=list)


class BlueOceanMove(ArtifactBase):
    """基于 ERRC 的新价值曲线"""
    artifact_type: Literal["blue_ocean_move"] = "blue_ocean_move"
    new_value_curve_summary: str = Field(min_length=50)

    focus_assessment: Literal["focused", "scattered", "uncertain"]
    focus_rationale: str = Field(min_length=20)
    divergence_assessment: Literal["divergent", "overlapping", "uncertain"]
    divergence_rationale: str = Field(min_length=20)

    compelling_tagline: str = Field(min_length=10, max_length=40)
    target_noncustomers: list[str] = Field(min_length=1)


class PositioningStatement(BaseModel):
    """Geoffrey Moore 6 位模板"""
    target_customer: str = Field(min_length=10)
    need_or_opportunity: str = Field(min_length=10)
    product_name: str = Field(min_length=2)
    product_category: str = Field(min_length=4)
    key_benefit: str = Field(min_length=10)
    primary_alternative: str = Field(min_length=4)
    primary_differentiation: str = Field(min_length=10)

    confidence: Literal["from_user_brief", "llm_inferred", "low_confidence"]

    @computed_field
    @property
    def full_statement_text(self) -> str:
        prefix = ""
        if self.confidence != "from_user_brief":
            prefix = "[AI 推断版本，请人工校对] "
        return (
            f"{prefix}For {self.target_customer} who {self.need_or_opportunity}, "
            f"{self.product_name} is a {self.product_category} that {self.key_benefit}. "
            f"Unlike {self.primary_alternative}, our product {self.primary_differentiation}."
        )


class CategoryStrategy(BaseModel):
    """品类战略（competitors_implied 由 S5 顶层 validator 校验子集关系）"""
    chosen_category: str = Field(min_length=4)
    why_this_category: str = Field(min_length=30)
    competitors_implied: list[str] = Field(min_length=1)
    risk_of_category_choice: str = Field(default="")


class S5PositioningPayload(BaseModel):
    """S5 战略定位场景载荷"""
    scenario_type: Literal["S5"] = "S5"

    vendor_profiles: list[S5VendorProfile] = Field(min_length=2)

    perceptual_map: PerceptualMap

    strategy_canvas: StrategyCanvas
    errc_grid: ERRCGrid

    blue_ocean_move: Optional[BlueOceanMove] = None

    positioning_statement: PositioningStatement

    category_strategy: CategoryStrategy

    @model_validator(mode='after')
    def _check_competitor_consistency(self) -> 'S5PositioningPayload':
        vendor_names = {vp.competitor_name for vp in self.vendor_profiles}
        map_names = {b.competitor_name for b in self.perceptual_map.plotted_brands}
        canvas_names = {vc.competitor_name for vc in self.strategy_canvas.value_curves}

        missing_in_map = vendor_names - map_names
        if missing_in_map:
            raise ValueError(
                f"vendor_profiles 中的 {missing_in_map} 不在 perceptual_map.plotted_brands 中"
            )

        missing_in_canvas = vendor_names - canvas_names
        if missing_in_canvas:
            raise ValueError(
                f"vendor_profiles 中的 {missing_in_canvas} 不在 strategy_canvas.value_curves 中"
            )

        selves_in_map = [b for b in self.perceptual_map.plotted_brands if b.is_self]
        if len(selves_in_map) > 1:
            raise ValueError(
                f"perceptual_map 中 is_self=True 的品牌应有且仅有一个，发现 {len(selves_in_map)} 个"
            )
        selves_in_canvas = [c for c in self.strategy_canvas.value_curves if c.is_self]
        if len(selves_in_canvas) > 1:
            raise ValueError(
                f"strategy_canvas.value_curves 中 is_self=True 的品牌应有且仅有一个，发现 {len(selves_in_canvas)} 个"
            )

        return self
