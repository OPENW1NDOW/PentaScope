from typing import TypedDict
from src.schemas.input import CompetitorInput, AnalysisGoal
from src.schemas.profile import CompetitorProfile
from src.schemas.analysis import CompetitiveAnalysis
from src.schemas.report import FinalReport
from src.schemas.feedback import RejectionFeedback


class AnalysisState(TypedDict, total=False):
    """LangGraph 状态定义：所有 Agent 共享的数据结构"""
    # 输入
    user_input: CompetitorInput

    # 采集 Agent 输出
    profiles: list[CompetitorProfile]
    # 采集阶段解析的分析目标（供 focus_area 回填报告）
    analysis_goal: AnalysisGoal

    # 分析 Agent 输出
    analysis: CompetitiveAnalysis

    # 撰写 Agent 输出
    report: FinalReport

    # 质检 Agent 输出
    feedback: RejectionFeedback

    # 控制流
    retry_count: int
    max_retries: int
    trace_id: str
    current_node: str  # 当前执行到的节点名称
