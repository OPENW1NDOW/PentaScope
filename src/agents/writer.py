"""WriterAgent 桩：D 阶段（worktree-scenario-schemas-graph）暂保留文件壳，
E 大类（worktree-scenario-writer-frontend）会整文件重写为 WriterOrchestrator 4 阶段编排实现。
"""

from src.schemas.analysis import CompetitiveAnalysis
from src.schemas.report import BaseReport


class WriterAgent:
    def __init__(self, llm):
        self.llm = llm

    async def write(self, analysis: CompetitiveAnalysis, competitors: list[str]) -> BaseReport:
        raise NotImplementedError(
            "WriterAgent 已废除，等 E 大类（writer_orchestrator）实现后替换。"
        )
