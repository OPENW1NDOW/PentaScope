"""WriterAgent 桩 — 旧版基于 FinalReport 的实现已废除（A 大类删除 FinalReport）。

新版 WriterOrchestrator（4 阶段编排）由 Task 21.1 实现。
本桩仅保留 import 兼容性，调用 write 直接 raise NotImplementedError。
"""


class WriterAgent:
    """旧 WriterAgent 桩。E 阶段 Task 21.1 后由 WriterOrchestrator 接管。"""

    def __init__(self, llm):
        self.llm = llm

    async def write(self, *args, **kwargs):
        raise NotImplementedError(
            "WriterAgent 已废除。请使用 src.agents.writer_orchestrator.WriterOrchestrator"
        )
