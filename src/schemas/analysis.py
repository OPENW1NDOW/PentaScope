from pydantic import BaseModel, Field
from typing import Literal


class PositioningEntry(BaseModel):
    """单个竞品的定位分析"""
    name: str
    target_users: str = ""
    core_scenario: str = ""
    pain_points: str = ""
    value_proposition: str = ""


class Positioning(BaseModel):
    """维度一：产品定位与目标用户"""
    per_competitor: list[PositioningEntry] = Field(default_factory=list)
    source_urls: list[str] = Field(default_factory=list)


class FeatureMatrixEntry(BaseModel):
    """功能矩阵中的单条记录"""
    feature: str
    our_product: Literal["有", "无", "计划中", "不适用"] = "无"
    competitors: dict[str, Literal["有", "无", "部分支持"]] = Field(default_factory=dict)
    gap_level: Literal["领先", "持平", "落后", "差异化"] = "持平"
    evidence: str = ""
    source_urls: list[str] = Field(default_factory=list)


class BusinessModelEntry(BaseModel):
    """单个竞品的商业模式"""
    name: str
    revenue_model: str = ""
    pricing_details: str = ""
    free_vs_paid: str = ""


class BusinessModel(BaseModel):
    """维度三：商业模式"""
    per_competitor: list[BusinessModelEntry] = Field(default_factory=list)
    source_urls: list[str] = Field(default_factory=list)


class OperationsEntry(BaseModel):
    """单个竞品的运营策略"""
    name: str
    growth_strategy: str = ""
    marketing_channels: str = ""
    content_strategy: str = ""


class Operations(BaseModel):
    """维度四：运营与增长"""
    per_competitor: list[OperationsEntry] = Field(default_factory=list)
    source_urls: list[str] = Field(default_factory=list)


class UserSentiment(BaseModel):
    """用户情感对比"""
    summary: str = ""
    per_competitor: dict[str, str] = Field(default_factory=dict)
    source_urls: list[str] = Field(default_factory=list)


class SwotEntry(BaseModel):
    """SWOT 单条"""
    point: str
    evidence: str = ""
    dimension: Literal["positioning", "feature", "business", "operations"] = "feature"
    source_urls: list[str] = Field(default_factory=list)


class Swot(BaseModel):
    """SWOT 分析"""
    strengths: list[SwotEntry] = Field(default_factory=list)
    weaknesses: list[SwotEntry] = Field(default_factory=list)
    opportunities: list[SwotEntry] = Field(default_factory=list)
    threats: list[SwotEntry] = Field(default_factory=list)


class RadarDimensions(BaseModel):
    """雷达图五维评分"""
    feature_breadth: float = Field(ge=0, le=5)
    usability: float = Field(ge=0, le=5)
    cost_effectiveness: float = Field(ge=0, le=5)
    stability: float = Field(ge=0, le=5)
    design_quality: float = Field(ge=0, le=5)


class RadarScore(BaseModel):
    """单个竞品的雷达评分"""
    competitor: str
    dimensions: RadarDimensions


class CompetitiveAnalysis(BaseModel):
    """分析 Agent 输出：四维竞品分析"""
    positioning: Positioning = Field(default_factory=Positioning)
    feature_matrix: list[FeatureMatrixEntry] = Field(default_factory=list)
    business_model: BusinessModel = Field(default_factory=BusinessModel)
    operations: Operations = Field(default_factory=Operations)
    user_sentiment: UserSentiment = Field(default_factory=UserSentiment)
    swot: Swot = Field(default_factory=Swot)
    radar_scores: list[RadarScore] = Field(default_factory=list)
