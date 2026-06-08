"""API 请求/响应 schema（承载 ScenarioInput 字段）"""
from typing import Literal, Optional
from pydantic import BaseModel, Field

from src.schemas.input import CompetitorBasic, ScenarioInput


class AnalysisRequest(BaseModel):
    """API 请求（包装 ScenarioInput 字段）"""
    scenario: Literal["S1", "S2", "S3", "S4", "S5"]
    competitors: list[CompetitorBasic] = Field(default_factory=list, max_length=10)
    industry: Optional[str] = None
    analysis_context: str = Field(min_length=1)
    our_product_name: Optional[str] = None
    our_product_brief: Optional[str] = None
    prior_trace_id: Optional[str] = None

    def to_scenario_input(self) -> ScenarioInput:
        return ScenarioInput(**self.model_dump())


class AnalysisResponse(BaseModel):
    """API 响应"""
    trace_id: str
    status: str  # "completed" | "failed"
    report: dict | None = None
    error: str | None = None


class TraceResponse(BaseModel):
    """追溯 API 响应"""
    trace_id: str
    meta: dict | None = None
    stages: dict = Field(default_factory=dict)
    snapshots: list[str] = Field(default_factory=list)
    log: str = ""


class PickScenarioRequest(BaseModel):
    """AI 选场景请求（用户描述自由文本）"""
    user_text: str = Field(min_length=1, max_length=2000)


class PickScenarioResponse(BaseModel):
    """AI 选场景响应"""
    scenario: Literal["S1", "S2", "S3", "S4", "S5"]
    confidence: Literal["high", "medium", "low"]
    rationale: str
