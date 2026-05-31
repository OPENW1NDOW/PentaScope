from pydantic import BaseModel, Field
from typing import Literal


class Classification(BaseModel):
    """竞品分类"""
    competitor_type: Literal["核心竞品", "标杆竞品", "间接竞品", "潜力竞品", "替代竞品", "翘楚竞品", "避坑竞品"]
    reason: str = Field(..., description="分类理由")


class BasicInfo(BaseModel):
    """竞品基本信息"""
    name: str
    company: str = ""
    version: str = "unknown"
    release_date: str = ""
    platform: list[str] = Field(default_factory=list)


class Feature(BaseModel):
    """单个功能"""
    name: str
    description: str = Field(default="", max_length=200)
    is_new: bool = False
    source_url: str = ""


class FeatureTree(BaseModel):
    """功能模块"""
    module: str
    features: list[Feature] = Field(default_factory=list)


class PricingTier(BaseModel):
    """价格档位"""
    name: str
    price: str = ""
    features: list[str] = Field(default_factory=list)


class Pricing(BaseModel):
    """定价信息"""
    model: str = "unknown"
    tiers: list[PricingTier] = Field(default_factory=list)
    source_url: str = ""


class SampleReview(BaseModel):
    """代表性评论"""
    content: str
    rating: int = Field(ge=1, le=5)
    source: str = ""
    source_url: str = ""


class UserReviews(BaseModel):
    """用户评价"""
    rating: float = Field(ge=0, le=5, default=0)
    total_reviews: int = Field(ge=0, default=0)
    positive_summary: str = ""
    negative_summary: str = ""
    sample_reviews: list[SampleReview] = Field(default_factory=list)


class RecentUpdate(BaseModel):
    """近期更新"""
    date: str
    title: str
    summary: str = ""
    source_url: str = ""


class ProfileMetadata(BaseModel):
    """采集元数据"""
    collected_at: str
    data_sources: list[str] = Field(default_factory=list)
    completeness_score: float = Field(ge=0, le=1, default=0)


class CompetitorProfile(BaseModel):
    """采集 Agent 输出：单个竞品的完整画像"""
    classification: Classification
    basic_info: BasicInfo
    feature_tree: list[FeatureTree] = Field(default_factory=list)
    pricing: Pricing = Field(default_factory=Pricing)
    user_reviews: UserReviews = Field(default_factory=UserReviews)
    recent_updates: list[RecentUpdate] = Field(default_factory=list)
    metadata: ProfileMetadata
