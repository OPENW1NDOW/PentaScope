from pydantic import BaseModel, Field
from typing import Literal


class CompetitorBasic(BaseModel):
    """竞品基础信息（用户输入）"""
    name: str = Field(..., min_length=2, max_length=50, description="竞品名称")
    company: str = Field(default="", description="所属公司（选填，系统可推断）")
    category: str = Field(default="", description="行业分类（选填，系统可推断）")


class AnalysisGoal(BaseModel):
    """解析后的分析目标"""
    goal_type: Literal[
        "feature_iteration", "pricing_strategy",
        "market_entry", "competitive_monitoring"
    ] = "competitive_monitoring"
    product_stage: Literal["entering", "growing", "mature"] = "growing"
    focus_area: str = Field(default="", description="用户关注的具体领域")
    output_expectation: Literal["info", "knowledge", "action"] = "action"


class CompetitorInput(BaseModel):
    """完整的用户输入"""
    competitors: list[CompetitorBasic] = Field(..., min_length=1, max_length=10, description="竞品列表")
    analysis_context: str = Field(..., min_length=1, description="自然语言描述分析意图")
