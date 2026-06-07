"""通用 schema 子模型：跨场景共享（SourceRef/ArtifactBase/DataSource 等）"""
from datetime import date
from typing import Literal, Optional
from pydantic import BaseModel, Field


class SourceRef(BaseModel):
    """统一溯源对象（跨场景统一命名，禁止再用 source_urls/sources/evidence_url）"""
    url: str = Field(min_length=8)
    title: str = ""
    accessed_at: Optional[date] = None
    source_type: Literal[
        "official_website", "third_party_review", "industry_report",
        "news", "user_review", "regulatory", "other"
    ] = "other"


class DataSource(BaseModel):
    """报告级数据源汇总"""
    url: str = Field(min_length=8)
    title: str = ""
    accessed_at: Optional[date] = None
    source_type: Literal[
        "official_website", "third_party_review", "industry_report",
        "news", "user_review", "regulatory", "other"
    ] = "other"
    confidence: Literal["high", "medium", "low"] = "medium"


class ArtifactBase(BaseModel):
    """所有可被 AnalysisSection.artifact_refs 引用的产物基类"""
    artifact_id: str = Field(min_length=3, max_length=40)
    artifact_type: str
    title: str = Field(default="")


class Revision(BaseModel):
    """报告版本修订记录"""
    revision_date: date
    change_summary: str
    triggered_by: Literal["initial", "inspector_feedback", "user_request"]


class Author(BaseModel):
    name: str
    role: str = ""
    bio: str = ""


class Exhibit(ArtifactBase):
    """通用附录展示（图表/数据/截图）"""
    artifact_type: Literal["exhibit"] = "exhibit"
    description: str = ""
    payload: dict = Field(default_factory=dict)
