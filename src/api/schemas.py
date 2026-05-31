from pydantic import BaseModel, Field
from src.schemas.input import CompetitorBasic


class AnalysisRequest(BaseModel):
    """API 请求"""
    competitors: list[CompetitorBasic] = Field(..., min_length=1, max_length=5)
    analysis_context: str = Field(..., min_length=1)


class AnalysisResponse(BaseModel):
    """API 响应"""
    trace_id: str
    status: str  # "completed" | "failed"
    report: dict | None = None
    error: str | None = None
