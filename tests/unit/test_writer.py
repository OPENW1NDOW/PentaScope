"""A 大类过渡：旧 FinalReport / WriterAgent 已废除。

待 E 大类 writer_orchestrator 实现后按 BaseReport + scenario_payload 重写本文件。
旧测试用例可在 git history 中查阅（master 分支 fcd21eb 之前）。
"""
import pytest

pytest.skip(
    "A 大类过渡：旧 WriterAgent 测试将由 E 大类 writer_orchestrator 重写",
    allow_module_level=True,
)
