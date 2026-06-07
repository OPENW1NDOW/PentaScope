"""S2 市场进入场景载荷"""
from typing import Literal, Optional
from pydantic import BaseModel, Field

from src.schemas.common import ArtifactBase, SourceRef


class MarketValue(BaseModel):
    """市场规模数值含完整口径"""
    amount: Optional[float] = None
    currency: Literal["USD", "CNY", "EUR", "JPY", "unknown"] = "unknown"
    unit: Literal["billion", "million", "thousand", "raw"] = "billion"
    year: Optional[int] = Field(default=None, ge=2000, le=2030)
    geography: str = "global"
    value_basis: Literal["measured", "estimated", "inferred", "unknown"] = "unknown"
    methodology_note: str = ""
    source_refs: list[SourceRef] = Field(default_factory=list)


class ForecastScenarios(BaseModel):
    low_growth_pct: float
    base_growth_pct: float
    high_growth_pct: float
    rationale: str = Field(min_length=20)


class MarketSizing(ArtifactBase):
    """TAM/SAM/SOM 三层"""
    artifact_type: Literal["market_sizing"] = "market_sizing"
    tam: MarketValue
    sam: MarketValue
    som: MarketValue
    cagr_pct: Optional[float] = None
    forecast_years: Optional[int] = None
    forecast_scenarios: Optional[ForecastScenarios] = None
    triangulation_gap_pct: Optional[float] = None


class Force(BaseModel):
    intensity: Literal["low", "medium", "high"]
    drivers: list[str] = Field(min_length=2)
    evidence: list[str] = Field(min_length=1)
    implication: str = Field(min_length=20)
    source_refs: list[SourceRef] = Field(default_factory=list)


class FiveForces(ArtifactBase):
    artifact_type: Literal["five_forces"] = "five_forces"
    new_entrants: Force
    supplier_power: Force
    buyer_power: Force
    substitute_threat: Force
    competitive_rivalry: Force


class MarketPlayer(BaseModel):
    """竞品玩家统一表示（取代多份名单）"""
    name: str = Field(min_length=1)
    company: str = ""
    market_role: Literal["incumbent", "challenger", "emerging", "niche", "substitute"]
    market_share_pct: Optional[float] = Field(default=None, ge=0, le=100)
    yoy_growth_pct: Optional[float] = None
    one_line_summary: str = Field(min_length=10)
    key_differentiator: str = ""
    is_recommended: bool = False
    is_collected: bool = False
    source_refs: list[SourceRef] = Field(default_factory=list)


class ConsumerSegment(BaseModel):
    name: str = Field(min_length=2)
    size_estimate: str = ""
    share_pct: Optional[float] = Field(default=None, ge=0, le=100)
    key_needs: list[str] = Field(min_length=1)
    underserved_indicators: list[str] = Field(default_factory=list)
    addressability: Literal["easy", "moderate", "hard"]
    source_refs: list[SourceRef] = Field(default_factory=list)


class Trend(BaseModel):
    trend_name: str = Field(min_length=4)
    description: str = Field(min_length=20)
    supporting_data: str = Field(default="")
    direction: Literal["up", "flat", "down"]
    time_horizon: Literal["short_term", "mid_term", "long_term"]
    impact_on_entry: Literal["positive", "negative", "mixed"]
    source_refs: list[SourceRef] = Field(default_factory=list)


class Risk(BaseModel):
    description: str = Field(min_length=10)
    likelihood: Literal["low", "medium", "high"]
    impact: Literal["low", "medium", "high"]
    mitigation: str = Field(min_length=10)


class Phase(BaseModel):
    phase_name: str = Field(min_length=4)
    duration: str
    key_milestones: list[str] = Field(min_length=1)
    resource_requirements: str = ""


class EntryStrategy(ArtifactBase):
    artifact_type: Literal["entry_strategy"] = "entry_strategy"
    recommended_mode: Literal[
        "direct_competition", "niche_focus", "differentiation",
        "partnership", "acquisition", "wait_and_see"
    ]
    target_segments: list[str] = Field(min_length=1)
    initial_positioning: str = Field(min_length=20)
    key_success_factors: list[str] = Field(min_length=2)
    main_risks: list[Risk] = Field(min_length=1)
    timeline_phases: list[Phase] = Field(min_length=2)


class PESTELFactor(BaseModel):
    name: str = Field(min_length=4)
    impact: Literal["opportunity", "threat", "neutral"]
    severity: Literal["low", "medium", "high"]
    description: str = Field(min_length=20)
    source_refs: list[SourceRef] = Field(default_factory=list)


class PESTEL(ArtifactBase):
    """PESTEL 6 维宏观因素（首版默认 None，等知识库到位后启用）"""
    artifact_type: Literal["pestel"] = "pestel"
    political: list[PESTELFactor] = Field(default_factory=list)
    economic: list[PESTELFactor] = Field(default_factory=list)
    social: list[PESTELFactor] = Field(default_factory=list)
    technological: list[PESTELFactor] = Field(default_factory=list)
    environmental: list[PESTELFactor] = Field(default_factory=list)
    legal: list[PESTELFactor] = Field(default_factory=list)


class RecommendedCompetitor(BaseModel):
    name: str = Field(min_length=1)
    company: str = ""
    why_recommended: str = Field(min_length=10)
    confidence: Literal["high", "medium", "low"]
    source_refs: list[SourceRef] = Field(default_factory=list)


class CompetitorRecommendations(BaseModel):
    """recommender 节点产出（仅 S2 有）"""
    user_provided_industry: str = Field(min_length=2)
    user_provided_competitors: list[str] = Field(default_factory=list)
    recommended_competitors: list[RecommendedCompetitor] = Field(min_length=3)
    selection_method: Literal["search_api_top_n", "llm_inference", "hybrid"]
    selection_rationale: str = Field(min_length=30)


class S2MarketEntryPayload(BaseModel):
    """S2 市场进入场景载荷"""
    scenario_type: Literal["S2"] = "S2"

    market_sizing: MarketSizing

    five_forces: FiveForces
    industry_attractiveness_1_5: int = Field(ge=1, le=5)

    players: list[MarketPlayer] = Field(min_length=3, max_length=10)
    market_concentration: Literal["fragmented", "moderate", "concentrated"]

    consumer_segments: Optional[list[ConsumerSegment]] = None

    key_trends: list[Trend] = Field(min_length=2)

    entry_strategy: EntryStrategy

    pestel: Optional[PESTEL] = None

    competitor_recommendations: CompetitorRecommendations
