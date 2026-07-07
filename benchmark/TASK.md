# 任务：Analyzer 并行拆分

## 背景

当前 `src/agents/analyzer.py` 的 `AnalyzerAgent.analyze()` 方法将所有竞品 profiles 一次性传给 LLM 分析。当竞品数量为 4-5 个时，单次 LLM 调用耗时 ~240s。

目标：将竞品拆分为 2 组并发调用 LLM，最后合并结果，将总耗时从 ~240s 降到 ~120s。

## 需求

### 核心功能

1. 在 `AnalyzerAgent` 中新增并行分析能力：
   - 当竞品数量 ≥ 3 时，拆分为 2 组并发调用 `self.llm.call_json()`
   - 当竞品数量 < 3 时，保持原有单次调用逻辑不变
   - 每组独立执行 `_normalize()` + `_backfill_source_urls()` + Pydantic 校验
   - 两组结果合并为一个完整的 `CompetitiveAnalysis` 对象

2. 合并逻辑：
   - `positioning.per_competitor`：两组的列表直接拼接
   - `business_model.per_competitor`：两组的列表直接拼接
   - `operations.per_competitor`：两组的列表直接拼接
   - `user_sentiment.per_competitor`：两组的 dict 合并
   - `user_sentiment.summary`：取较长的那个（或拼接）
   - `feature_matrix`：两组的列表直接拼接
   - `radar_scores`：两组的列表直接拼接
   - `swot`：两组的 SWOT 按四个维度（strengths/weaknesses/opportunities/threats）拼接去重
   - `source_urls`：各维度的 source_urls 列表拼接去重

3. 错误处理：
   - 如果一组失败（LLM 超时 / ValidationError 重试后仍失败），另一组结果仍然可用
   - 部分成功时用成功组的结果作为最终输出（降级，不抛异常）
   - 两组都失败时，按现有逻辑 raise ValueError
   - 日志记录每组的耗时和成功/失败状态

4. 配置：
   - 新增 `ANALYZER_CONCURRENCY` 配置项（默认 2），控制并发组数
   - 放在 `src/utils/config.py` 的 Settings 类中

### 约束

- `analyzer_node`（`src/graph/builder.py`）的接口不变：仍然调用 `analyzer.analyze(profiles, scenario_input, feedback_issues)`，对外行为不变
- `AnalysisState` 不需要修改
- 现有的 `_format_feedback()` 和 `_format_scenario_context()` 逻辑保持不变，每组都要注入相同的场景上下文和反馈信息
- SWOT 分析的主体不变（由 scenario_input 决定），两组都基于相同的 SWOT 主体产出

### 测试要求

新增以下测试（在 `tests/unit/test_analyzer.py` 中）：

1. `test_parallel_split_4_competitors` — 4 个竞品正确拆分为 2+2 并发
2. `test_parallel_split_5_competitors` — 5 个竞品正确拆分为 3+2 或 2+3
3. `test_no_split_2_competitors` — 2 个竞品走原有单次调用路径
4. `test_parallel_one_group_fails` — 一组失败另一组成功，降级返回部分结果
5. `test_parallel_both_groups_fail` — 两组都失败，raise ValueError
6. `test_parallel_merge_swot_dedup` — SWOT 合并时去重逻辑正确
7. `test_parallel_merge_source_urls_dedup` — source_urls 合并去重

## 关键文件

需要修改的文件：
- `src/agents/analyzer.py` — 主要改动
- `src/utils/config.py` — 新增 ANALYZER_CONCURRENCY 配置
- `tests/unit/test_analyzer.py` — 新增测试

需要阅读理解但不修改的文件：
- `src/graph/builder.py` — 理解 analyzer_node 如何调用 analyzer
- `src/graph/state.py` — 理解 state 结构
- `src/schemas/analysis.py` — 理解 CompetitiveAnalysis 结构
- `src/schemas/report.py` — 理解 Swot 结构
- `src/tools/llm_client.py` — 理解 LLM 调用接口

## 验收标准

1. `pytest tests/unit/test_analyzer.py` — 全部通过（含新增 7 个测试）
2. `pytest` — 全量测试无回归（536+ tests）
3. `ruff check src tests` — 0 errors
4. 代码风格与项目一致（中文日志、logging 模块、async/await）

完成后请自行运行上述验收命令。如果测试或 lint 不通过，自行修复直到全部通过，然后 commit。

## 技术提示

- 项目使用 `asyncio`，并行调用用 `asyncio.gather(return_exceptions=True)`
- 参考 WriterOrchestrator 的 Phase 3 narrative 并发模式（`asyncio.Semaphore` 限速）
- LLM 调用接口：`await self.llm.call_json(system_prompt, user_prompt, max_tokens=16384)`
- 竞品拆分策略：简单平分即可（前 N//2 个一组，后面的一组）
