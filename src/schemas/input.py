"""ScenarioInput 与 AnalysisGoal（CompetitorInput 已迁移为 ScenarioInput 别名）"""
from typing import Literal, Optional
from pydantic import BaseModel, Field, model_validator


class CompetitorBasic(BaseModel):
    name: str = Field(min_length=2, max_length=50)
    company: str = ""
    category: str = ""
    official_url: Optional[str] = None  # 可选用户提供官网


class ScenarioInput(BaseModel):
    """统一输入 schema，按 scenario 分支校验"""
    scenario: Literal["S1", "S2", "S3", "S4", "S5"]
    competitors: list[CompetitorBasic] = Field(default_factory=list, max_length=10)
    industry: Optional[str] = None
    analysis_context: str = Field(min_length=1)

    our_product_name: Optional[str] = None
    our_product_brief: Optional[str] = None

    # S4 专用：上次监控的 trace_id（用于 delta）
    prior_trace_id: Optional[str] = None

    @model_validator(mode='after')
    def _check_scenario_inputs(self) -> 'ScenarioInput':
        if self.scenario == "S2":
            if not self.industry:
                raise ValueError("S2 市场进入场景必须提供 industry")
        else:
            if not self.competitors:
                raise ValueError(f"{self.scenario} 场景必须提供至少一个 competitor")
            if not self.our_product_name:
                raise ValueError(f"{self.scenario} 场景必须提供 our_product_name")
        return self


class AnalysisGoal(BaseModel):
    """解析后的分析目标（collector 内部仍使用）"""
    goal_type: Literal[
        "feature_iteration", "pricing_strategy",
        "market_entry", "competitive_monitoring"
    ] = "competitive_monitoring"
    product_stage: Literal["entering", "growing", "mature"] = "growing"
    focus_area: str = ""
    output_expectation: Literal["info", "knowledge", "action"] = "action"


# 兼容性占位：旧代码 import CompetitorInput 不崩
CompetitorInput = ScenarioInput
