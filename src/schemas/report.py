from pydantic import BaseModel, Field
from typing import Literal
from src.schemas.input import AnalysisGoal


class ExecutiveSummary(BaseModel):
    """四段式执行摘要"""
    what_competitors_did_right: str = ""
    what_competitors_did_wrong: str = ""
    our_opportunities: str = ""
    next_steps_summary: str = ""


class ReportSection(BaseModel):
    """报告章节"""
    title: str
    content: str = ""
    source_refs: list[str] = Field(default_factory=list)


class ActionItem(BaseModel):
    """单条行动建议"""
    priority: Literal["高", "中", "低"]
    description: str
    rationale: str = ""
    source_urls: list[str] = Field(default_factory=list)


class ActionItems(BaseModel):
    """时间分层行动建议"""
    immediate: list[ActionItem] = Field(default_factory=list, description="1个月内")
    short_term: list[ActionItem] = Field(default_factory=list, description="3个月内")
    long_term: list[ActionItem] = Field(default_factory=list, description="6个月内")


class ReportMetadata(BaseModel):
    """报告元数据"""
    competitors_analyzed: list[str] = Field(default_factory=list)
    analysis_goal: AnalysisGoal = Field(default_factory=AnalysisGoal)
    generated_at: str = ""
    data_sources: list[str] = Field(default_factory=list)
    quality_score: float = Field(ge=0, le=1, default=0)
    warnings: list[str] = Field(default_factory=list)


class FinalReport(BaseModel):
    """撰写 Agent 输出：最终竞品分析报告"""
    title: str
    executive_summary: ExecutiveSummary = Field(default_factory=ExecutiveSummary)
    sections: list[ReportSection] = Field(default_factory=list)
    action_items: ActionItems = Field(default_factory=ActionItems)
    metadata: ReportMetadata = Field(default_factory=ReportMetadata)
