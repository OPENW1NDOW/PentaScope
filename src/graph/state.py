from typing import TypedDict, Optional
from src.schemas.input import ScenarioInput, AnalysisGoal
from src.schemas.profile import CompetitorProfile
from src.schemas.analysis import CompetitiveAnalysis
from src.schemas.report import BaseReport
from src.schemas.feedback import RejectionFeedback
from src.schemas.scenarios.s2 import CompetitorRecommendations


class AnalysisState(TypedDict, total=False):
    """LangGraph 状态：所有 Agent 共享的数据结构"""
    user_input: ScenarioInput

    # S2 专用：recommender 节点产出
    competitor_recommendations: Optional[CompetitorRecommendations]

    # S4 专用：从 prior_trace_id 读到的旧 BaseReport（dict 形式）
    prior_report_data: Optional[dict]

    # 采集层
    profiles: list[CompetitorProfile]
    analysis_goal: AnalysisGoal

    # 分析层
    analysis: CompetitiveAnalysis

    # 撰写层
    report: BaseReport

    # 质检
    feedback: RejectionFeedback

    # 控制流
    retry_count: int
    max_retries: int
    trace_id: str
    current_node: str
