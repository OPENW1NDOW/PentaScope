# 给模型的统一 Prompt

> 以下是执行测评时，粘贴给每个模型 agent 的完整 prompt。一字不改。

---

请实现以下功能：将 analyzer 从串行分析改为并行分析，提速 ~50%。

详细需求请阅读 `benchmark/TASK.md`。

核心要点：
1. 修改 `src/agents/analyzer.py`：竞品 ≥3 时拆 2 组并发，<3 时保持原逻辑
2. 修改 `src/utils/config.py`：新增 `ANALYZER_CONCURRENCY` 配置
3. 新增 7 个测试到 `tests/unit/test_analyzer.py`

完成实现后，运行以下验收命令确认通过：
- `pytest tests/unit/test_analyzer.py`
- `pytest`（全量无回归）
- `ruff check src tests`

如果测试或 lint 不通过，自行修复直到全部通过。最后 git commit 你的改动。
