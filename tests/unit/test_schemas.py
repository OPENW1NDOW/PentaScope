"""A 大类过渡：旧 FinalReport / ReportSection / ActionItems 已废除。

新 schema 测试见 tests/unit/test_schemas_common.py 与 test_schemas_base_report.py。
B 大类完成 BaseReport 接通后，可按需补充端到端 schema 测试。
旧测试用例可在 git history 中查阅。
"""
import pytest

pytest.skip(
    "A 大类过渡：旧 schema 整体测试将由 B 大类完成 BaseReport 接通后重写",
    allow_module_level=True,
)
