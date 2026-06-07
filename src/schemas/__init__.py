"""schema 包：BaseReport 通用骨架 + 5 场景 payload union（Task 11 接通）

旧 FinalReport / ReportSection / ActionItem / ActionItems 已废除（plan Part 0）。
其他依赖这些类的代码（writer/inspector/api/frontend）将在 D/E/F/G 大类重写。
"""
from src.schemas.input import CompetitorBasic, AnalysisGoal, CompetitorInput
from src.schemas.profile import CompetitorProfile
from src.schemas.analysis import CompetitiveAnalysis
from src.schemas.common import (
    Author, ArtifactBase, DataSource, Exhibit, Revision, SourceRef,
)
from src.schemas.report import (
    ExecutiveSummary, ReportScope, Methodology, Finding, AnalysisSection,
    Recommendation, Appendix, Swot, SwotEntry,
)
from src.schemas.feedback import RejectionFeedback, FeedbackIssue, AgentMessage

__all__ = [
    "CompetitorBasic", "AnalysisGoal", "CompetitorInput",
    "CompetitorProfile", "CompetitiveAnalysis",
    "Author", "ArtifactBase", "DataSource", "Exhibit", "Revision", "SourceRef",
    "ExecutiveSummary", "ReportScope", "Methodology", "Finding", "AnalysisSection",
    "Recommendation", "Appendix", "Swot", "SwotEntry",
    "RejectionFeedback", "FeedbackIssue", "AgentMessage",
]
