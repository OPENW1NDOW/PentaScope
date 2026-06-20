from typing import TypedDict, Optional
from src.schemas.input import ScenarioInput, AnalysisGoal
from src.schemas.profile import CompetitorProfile
from src.schemas.analysis import CompetitiveAnalysis
from src.schemas.report import BaseReport
from src.schemas.feedback import RejectionFeedback
from src.schemas.scenarios.s2 import CompetitorRecommendations


class AnalysisState(TypedDict, total=False):
    """LangGraph 状态定义：所有 Agent 共享的数据结构"""
    # 输入（v3：ScenarioInput 替代 CompetitorInput）
    user_input: ScenarioInput

    # S2 专用：recommender 节点产出
    competitor_recommendations: Optional[CompetitorRecommendations]

    # S4 专用：从 prior_trace_id 读到的旧 BaseReport（dict 形式）
    prior_report_data: Optional[dict]

    # 采集 Agent 输出
    profiles: list[CompetitorProfile]
    # 采集阶段解析的分析目标（供 focus_area 回填报告）
    analysis_goal: AnalysisGoal

    # 分析 Agent 输出
    analysis: CompetitiveAnalysis

    # 撰写 Agent 输出（v3：BaseReport 替代 FinalReport）
    report: BaseReport

    # 质检 Agent 输出
    feedback: RejectionFeedback

    # 控制流
    retry_count: int
    max_retries: int
    trace_id: str
    current_node: str  # 当前执行到的节点名称

    # v4 critic：采集阶段产出的搜索源信息（供 inspector evidence rubric 使用）
    discovered_sources: list[dict]  # [{"url", "title", "snippet"}]

    # evidence 路由：上轮 coverage（用于判断是否改善）
    _prev_evidence_coverage: Optional[float]
