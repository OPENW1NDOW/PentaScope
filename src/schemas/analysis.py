from pydantic import BaseModel, Field

# Swot 已迁移至 src.schemas.report（Task 4 / plan Part 0 废除清单）
from src.schemas.report import Swot


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


class CompetitiveAnalysis(BaseModel):
    """分析 Agent 输出：四维竞品分析

    Task 4 阶段过渡：
    - SwotEntry / Swot / RadarScore / FeatureMatrixEntry 已迁移
    - Swot 从 src.schemas.report import 复用通用骨架
    - feature_matrix / radar_scores 暂用 list[dict] 占位，B 大类各场景 payload 接入后由 writer/analyzer 透传
    """
    positioning: Positioning = Field(default_factory=Positioning)
    feature_matrix: list[dict] = Field(default_factory=list)
    business_model: BusinessModel = Field(default_factory=BusinessModel)
    operations: Operations = Field(default_factory=Operations)
    user_sentiment: UserSentiment = Field(default_factory=UserSentiment)
    swot: Swot | None = None
    radar_scores: list[dict] = Field(default_factory=list)
