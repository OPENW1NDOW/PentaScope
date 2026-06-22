# Evidence 反馈闭环 v2 + 截断阈值调整 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修正 writer URL 引用张冠李戴问题（按竞品分组传 URL + 打回时传精确 reason）+ 删除 v1 错误代码 + 截断阈值 30→50 万。

**Architecture:** writer phase 2/3 prompt 注入按竞品分组的 URL 字典 + 引用规则；打回时传 inspector 原始 issues 原文；删除 `_route_evidence_issue` 及其相关代码；`_ISSUE_TYPE_TO_AGENT` 映射修正 `source_mismatch → writer`；collector 截断阈值放宽。

**Tech Stack:** Python / Pydantic v2 / LangGraph StateGraph / pytest-asyncio

**Spec:** `docs/superpowers/specs/2026-06-22-evidence-v2-and-threshold-design.md`

---

## File Map

| Action | Path | Responsibility |
|--------|------|---------------|
| Modify | `src/agents/writer_orchestrator.py` | 构造 grouped_urls + 注入 phase 2/3 + 接收 feedback_issues |
| Modify | `src/agents/prompts/writer/payload/_common.py` | SOURCE_REFS_PROTOCOL 改为分组格式 |
| Modify | `src/agents/prompts/writer/narrative/_common.py` | NARRATIVE_TEMPLATE 追加引用规则占位符 |
| Modify | `src/graph/builder.py` | 删除 v1 代码 + writer_node 传 feedback_issues |
| Modify | `src/graph/state.py` | 删除 `_prev_evidence_coverage` |
| Modify | `src/schemas/feedback.py` | 删除 EvidenceFeedback |
| Modify | `src/agents/inspector.py` | 修正 `_ISSUE_TYPE_TO_AGENT` |
| Modify | `src/agents/collector.py` | 删除 supplement_collect + 阈值调整 |
| Delete | `tests/unit/test_evidence_routing.py` | 路由函数已删 |
| Delete | `tests/unit/test_supplement_collect.py` | 补采已删 |
| Modify | `tests/unit/test_writer_orchestrator.py` | 删除旧 evidence_feedback 测试 + 新增分组 URL / feedback_issues 测试 |
| Modify | `tests/unit/test_inspector_critic.py` | 删除 EvidenceFeedback 测试 |

---

### Task 1: 删除 v1 错误代码（清理）

**Files:**
- Modify: `src/graph/builder.py`
- Modify: `src/graph/state.py`
- Modify: `src/schemas/feedback.py`
- Modify: `src/agents/collector.py`
- Modify: `src/agents/writer_orchestrator.py`
- Delete: `tests/unit/test_evidence_routing.py`
- Delete: `tests/unit/test_supplement_collect.py`
- Modify: `tests/unit/test_writer_orchestrator.py`
- Modify: `tests/unit/test_inspector_critic.py`

- [ ] **Step 1: 删除 `src/graph/builder.py` 中的 v1 代码**

删除以下内容：
1. 第 35 行 `from src.utils.url_normalize import normalize_url as _normalize_url`
2. 第 36 行 `from src.agents.writer_orchestrator import _collect_source_refs_recursive`
3. `_EVIDENCE_ISSUE_TYPES` 常量（第 128 行）
4. `_extract_used_urls` 函数（第 131-139 行）
5. `_route_evidence_issue` 函数（第 142-169 行）
6. `should_continue` 中的 evidence 优先扫描分支（"evidence issues 优先扫描"注释开始到 `break` 结束的 7 行）
7. `inspector_node` 中 "写入 evidence coverage" 注释开始到 `result["_prev_evidence_coverage"] = ...` 的整个 if 块
8. `writer_node` 中 "检测 evidence 反馈" 注释开始到 `evidence_feedback=evidence_feedback,` 的整个块
9. `collector_node` 中 "检测是否为 evidence 反馈打回的增量补采模式" 注释开始到 `return {"current_node": "collector"}` 的整个 if 块

`writer.write()` 调用中删除 `evidence_feedback=evidence_feedback,` 参数。

- [ ] **Step 2: 删除 `src/graph/state.py` 中的 `_prev_evidence_coverage` 字段**

删除：
```python
    # evidence 路由：上轮 coverage（用于判断是否改善）
    _prev_evidence_coverage: Optional[float]
```

- [ ] **Step 3: 删除 `src/schemas/feedback.py` 中的 `EvidenceFeedback` class**

删除：
```python
class EvidenceFeedback(BaseModel):
    """evidence 维度打回 writer 时携带的反馈信息。"""
    available_urls: list[str] = Field(default_factory=list)
    weak_fields: list[str] = Field(default_factory=list)
    coverage_pct: float = 0.0
```

- [ ] **Step 4: 删除 `src/agents/collector.py` 中的 `supplement_collect` 方法和 `_SUPPLEMENT_QUERY_SYSTEM`**

删除 `_SUPPLEMENT_QUERY_SYSTEM` 字符串和整个 `async def supplement_collect(...)` 方法。同时删除顶部的 `import json`（如果只有 supplement_collect 用到的话——检查是否 `_serialize_validation_error` 也用了 json，如果用了则保留）。

- [ ] **Step 5: 删除 `src/agents/writer_orchestrator.py` 中的 `evidence_feedback` 参数和注入逻辑**

1. `write()` 签名删除 `evidence_feedback: Any = None,`
2. `_phase3_narratives()` 签名删除 `evidence_feedback: Any = None,`，调用处删除 `evidence_feedback=evidence_feedback,`
3. `_phase3_one_section()` 签名删除 `evidence_feedback: Any = None,`，删除 `if evidence_feedback and getattr(...)` 整个注入块
4. `_phase3_narratives` 中 gather 和 retry 调用处删除 `evidence_feedback=evidence_feedback,`

- [ ] **Step 6: 删除测试文件和旧测试**

1. 删除 `tests/unit/test_evidence_routing.py`
2. 删除 `tests/unit/test_supplement_collect.py`
3. 从 `tests/unit/test_writer_orchestrator.py` 删除 `test_phase3_evidence_feedback_injects_urls` 函数
4. 从 `tests/unit/test_writer_orchestrator.py` 删除 `test_phase3_retry_includes_error_hint_in_prompt` 函数（将在 Task 4 中重写）
5. 从 `tests/unit/test_inspector_critic.py` 删除 `test_evidence_feedback_model` 和 `test_evidence_feedback_defaults`

- [ ] **Step 7: 运行测试确认无 import 错误和回归**

Run: `pytest tests/unit/ tests/integration/ -q --tb=short`
Expected: all pass（测试数减少但无 failure）

- [ ] **Step 8: Ruff**

Run: `ruff check src tests`
Expected: All checks passed

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "refactor: 删除 evidence 闭环 v1 错误代码（route_evidence_issue + EvidenceFeedback + supplement_collect）"
```

---

### Task 2: 修正路由映射 + 截断阈值

**Files:**
- Modify: `src/agents/inspector.py`
- Modify: `src/agents/collector.py`

- [ ] **Step 1: 写测试验证 source_mismatch 路由到 writer**

在 `tests/unit/test_inspector_critic.py` 末尾追加：

```python
def test_source_mismatch_routes_to_writer():
    from src.agents.inspector import _map_issue_type_to_agent
    assert _map_issue_type_to_agent("source_mismatch") == "writer"
    assert _map_issue_type_to_agent("source_irrelevant") == "writer"
    assert _map_issue_type_to_agent("url_not_discovered") == "collector"
```

- [ ] **Step 2: 运行测试验证红**

Run: `pytest tests/unit/test_inspector_critic.py::test_source_mismatch_routes_to_writer -v`
Expected: FAIL（source_mismatch 当前映射到 collector）

- [ ] **Step 3: 修正 `_ISSUE_TYPE_TO_AGENT`**

`src/agents/inspector.py` 第 49 行：

```python
_ISSUE_TYPE_TO_AGENT = {
    "url_not_discovered": "collector",
    "source_mismatch": "writer",
    "source_irrelevant": "writer",
    "vague_description": "writer",
    "cross_field_contradiction": "writer",
    "vague_recommendation": "writer",
    "critic_failed": "end",
}
```

- [ ] **Step 4: 运行测试验证绿**

Run: `pytest tests/unit/test_inspector_critic.py::test_source_mismatch_routes_to_writer -v`
Expected: PASS

- [ ] **Step 5: 修改截断阈值**

`src/agents/collector.py` 第 12 行：

```python
_EXTRACT_TEXT_MAX_CHARS = 500_000
```

- [ ] **Step 6: 运行全量测试**

Run: `pytest tests/unit/ tests/integration/ -q --tb=short`
Expected: all pass

- [ ] **Step 7: Commit**

```bash
git add src/agents/inspector.py src/agents/collector.py tests/unit/test_inspector_critic.py
git commit -m "fix: source_mismatch 路由修正为 writer + 截断阈值 30→50 万"
```

---

### Task 3: 按竞品分组传 URL（Phase 2 + Phase 3）

**Files:**
- Modify: `src/agents/writer_orchestrator.py`
- Modify: `src/agents/prompts/writer/payload/_common.py`
- Modify: `src/agents/prompts/writer/narrative/_common.py`
- Modify: `tests/unit/test_writer_orchestrator.py`

- [ ] **Step 1: 写测试验证 phase 2 prompt 包含分组 URL**

在 `tests/unit/test_writer_orchestrator.py` 末尾追加：

```python
@pytest.mark.asyncio
async def test_phase2_prompt_contains_grouped_urls():
    """phase 2 user prompt 应包含按竞品分组的 URL（而非扁平列表）。"""
    scenario_input, analysis, profiles = _make_phase3_full_run_inputs()

    phase1_outline = _make_valid_outline_dict("测试")
    phase2_payload = _s1_payload_dict_with_weighted_scores()
    s1_types = ["overview", "vendor_profile_analysis", "feature_matrix_analysis", "jtbd_analysis", "roadmap_analysis"]
    side_effects = [phase1_outline, phase2_payload] + [_make_valid_narrative_json(t) for t in s1_types]

    mock_llm = MagicMock(spec=LLMClient)
    mock_llm.call_json = AsyncMock(side_effect=side_effects)
    orch = WriterOrchestrator(llm=mock_llm)

    try:
        await orch.write(scenario_input=scenario_input, analysis=analysis, profiles=profiles)
    except Exception:
        pass

    # phase 2 是第 2 次 LLM 调用
    phase2_call = mock_llm.call_json.call_args_list[1]
    user_prompt = phase2_call[0][1]
    # 应包含按竞品分组的格式（竞品名作为 key）
    assert "AA" in user_prompt  # 竞品名 AA
    assert "BB" in user_prompt  # 竞品名 BB
    assert "按竞品归属" in user_prompt or "竞品归属" in user_prompt
```

- [ ] **Step 2: 运行测试验证红**

Run: `pytest tests/unit/test_writer_orchestrator.py::test_phase2_prompt_contains_grouped_urls -v`
Expected: FAIL

- [ ] **Step 3: 在 `WriterOrchestrator.write()` 中构造 `grouped_urls`**

在 `discovered_urls` 构造之后添加：

```python
        # 按竞品分组的 URL 字典（用于 phase 2/3 prompt 注入）
        grouped_urls: dict[str, list[str]] = {}
        for p in profiles:
            name = p.basic_info.name
            urls = sorted(collect_profile_urls(p))
            if urls:
                grouped_urls[name] = urls
```

- [ ] **Step 4: 修改 phase 2 prompt 注入格式**

在 `_build_phase2_user_prompt` 中（以及 `_phase1_outline` 中），把 `("=== 可用溯源 URL ===", discovered_urls)` 改为按竞品分组的格式。

需要把 `grouped_urls` 传到这些方法。最简单方式：在 `write()` 中用 `json.dumps(grouped_urls, ensure_ascii=False)` 生成字符串，替换现有的 `discovered_urls` 列表注入。

修改 `_build_phase2_user_prompt` 签名新增 `grouped_urls: dict[str, list[str]]`，将 sections 中的：
```python
("=== 可用溯源 URL ===", discovered_urls),
```
替换为：
```python
("=== 可用溯源 URL（按竞品归属）===", json.dumps(grouped_urls, ensure_ascii=False)),
```

同时修改 `SOURCE_REFS_PROTOCOL`（`payload/_common.py`）中的引用规则文字，在第 1-2 条之后追加：
```
注意：profiles_source_urls 按竞品分组，论述哪个竞品时只能引用该竞品名下的 URL。
```

- [ ] **Step 5: 修改 phase 3 prompt 注入**

在 `_phase3_one_section` 中，删除 `_ = discovered_urls` 行，改为在 system_prompt 末尾追加分组 URL + 引用规则：

```python
        # 按竞品分组的溯源 URL + 引用规则
        if grouped_urls:
            url_section = "\n".join(
                f"- {name}: {', '.join(urls)}"
                for name, urls in grouped_urls.items()
            )
            system_prompt += (
                f"\n\n【溯源引用规则】\n"
                f"可用 URL（按竞品归属）：\n{url_section}\n\n"
                f"规则：\n"
                f"1. 论述哪个竞品时，source_refs 只能从该竞品对应的 URL 中选取\n"
                f"2. 尽量为每个事实性论断（产品功能、市场数据、用户反馈等）附上至少 1 个 source_ref\n"
                f"3. 找不到对应 URL 时 source_refs 留空 []，绝不编造、绝不跨竞品引用"
            )
```

需要把 `grouped_urls` 传到 `_phase3_one_section`（通过 `_phase3_narratives` 中转）。

- [ ] **Step 6: 运行测试验证绿**

Run: `pytest tests/unit/test_writer_orchestrator.py::test_phase2_prompt_contains_grouped_urls -v`
Expected: PASS

- [ ] **Step 7: 写 phase 3 测试**

```python
@pytest.mark.asyncio
async def test_phase3_prompt_contains_grouped_urls_and_rules():
    """phase 3 每个 section 的 system_prompt 应包含按竞品分组的 URL + 引用规则。"""
    scenario_input, analysis, profiles = _make_phase3_full_run_inputs()

    phase1_outline = _make_valid_outline_dict("测试")
    phase2_payload = _s1_payload_dict_with_weighted_scores()
    s1_types = ["overview", "vendor_profile_analysis", "feature_matrix_analysis", "jtbd_analysis", "roadmap_analysis"]
    side_effects = [phase1_outline, phase2_payload] + [_make_valid_narrative_json(t) for t in s1_types]

    mock_llm = MagicMock(spec=LLMClient)
    mock_llm.call_json = AsyncMock(side_effect=side_effects)
    orch = WriterOrchestrator(llm=mock_llm)

    try:
        await orch.write(scenario_input=scenario_input, analysis=analysis, profiles=profiles)
    except Exception:
        pass

    # phase 3 调用从 index=2 开始
    narrative_calls = mock_llm.call_json.call_args_list[2:]
    assert len(narrative_calls) >= 1
    for call in narrative_calls:
        system_prompt = call[0][0]
        assert "溯源引用规则" in system_prompt
        assert "跨竞品引用" in system_prompt
```

- [ ] **Step 8: 运行测试验证绿**

Run: `pytest tests/unit/test_writer_orchestrator.py::test_phase3_prompt_contains_grouped_urls_and_rules -v`
Expected: PASS

- [ ] **Step 9: 全量回归**

Run: `pytest tests/unit/ tests/integration/ -q --tb=short`
Expected: all pass

- [ ] **Step 10: Commit**

```bash
git add src/agents/writer_orchestrator.py src/agents/prompts/writer/payload/_common.py src/agents/prompts/writer/narrative/_common.py tests/unit/test_writer_orchestrator.py
git commit -m "feat: writer phase 2/3 按竞品分组传 URL + 引用规则注入"
```

---

### Task 4: 打回时传 inspector 原始 reason/suggestion

**Files:**
- Modify: `src/agents/writer_orchestrator.py`
- Modify: `src/graph/builder.py`
- Modify: `tests/unit/test_writer_orchestrator.py`

- [ ] **Step 1: 写测试验证打回时 prompt 包含 reason/suggestion**

```python
@pytest.mark.asyncio
async def test_feedback_issues_injected_on_retry():
    """打回 writer 时，phase 3 prompt 应包含 inspector 的 reason 和 suggestion。"""
    from src.schemas.feedback import FeedbackIssue

    scenario_input, analysis, profiles = _make_phase3_full_run_inputs()

    issues = [
        FeedbackIssue(
            agent="writer", field="key_findings[0].source_refs[1]",
            severity="critical", dimension="evidence", issue_type="source_mismatch",
            reason="用火山引擎文档证明 GrowingIO 的 XBA 模型",
            suggestion="替换为 GrowingIO 官方文档链接",
        ),
    ]

    phase1_outline = _make_valid_outline_dict("测试")
    phase2_payload = _s1_payload_dict_with_weighted_scores()
    s1_types = ["overview", "vendor_profile_analysis", "feature_matrix_analysis", "jtbd_analysis", "roadmap_analysis"]
    side_effects = [phase1_outline, phase2_payload] + [_make_valid_narrative_json(t) for t in s1_types]

    mock_llm = MagicMock(spec=LLMClient)
    mock_llm.call_json = AsyncMock(side_effect=side_effects)
    orch = WriterOrchestrator(llm=mock_llm)

    try:
        await orch.write(
            scenario_input=scenario_input, analysis=analysis, profiles=profiles,
            feedback_issues=issues,
        )
    except Exception:
        pass

    narrative_calls = mock_llm.call_json.call_args_list[2:]
    for call in narrative_calls:
        system_prompt = call[0][0]
        assert "火山引擎" in system_prompt
        assert "GrowingIO" in system_prompt
```

- [ ] **Step 2: 运行测试验证红**

Run: `pytest tests/unit/test_writer_orchestrator.py::test_feedback_issues_injected_on_retry -v`
Expected: FAIL（write() 不接受 feedback_issues 参数）

- [ ] **Step 3: 实现**

3a. `WriterOrchestrator.write()` 签名新增：
```python
feedback_issues: list | None = None,
```

3b. 传到 `_phase3_narratives`，再传到 `_phase3_one_section`。

3c. 在 `_phase3_one_section` 中，grouped_urls 注入之后、`user_prompt` 之前，添加：

```python
        if feedback_issues:
            issue_lines = []
            for iss in feedback_issues:
                if getattr(iss, "dimension", None) == "evidence":
                    issue_lines.append(f"- {iss.field}: {iss.reason} 建议：{iss.suggestion}")
            if issue_lines:
                issues_text = "\n".join(issue_lines)
                system_prompt += (
                    f"\n\n【质检打回：以下引用存在问题，请修正】\n{issues_text}"
                )
```

3d. `builder.py:writer_node` 中，把 `state.get("feedback")` 的 issues 传给 `writer.write()`：

```python
        # 打回时传 feedback issues 给 writer
        writer_feedback_issues = None
        feedback = state.get("feedback")
        if feedback and not feedback.passed:
            writer_feedback_issues = [i for i in feedback.issues if i.agent == "writer"]

        try:
            report = await writer.write(
                ...,
                feedback_issues=writer_feedback_issues,
            )
```

- [ ] **Step 4: 运行测试验证绿**

Run: `pytest tests/unit/test_writer_orchestrator.py::test_feedback_issues_injected_on_retry -v`
Expected: PASS

- [ ] **Step 5: 全量回归 + ruff**

Run: `pytest tests/unit/ tests/integration/ -q --tb=short`
Run: `ruff check src tests`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add src/agents/writer_orchestrator.py src/graph/builder.py tests/unit/test_writer_orchestrator.py
git commit -m "feat: 打回 writer 时传 inspector 原始 reason/suggestion（精确纠正）"
```

---

### Task 5: 全量回归 + 文档更新 + push

**Files:**
- All modified files
- `PROGRESS.md`
- `OPEN_QUESTIONS.md`

- [ ] **Step 1: Full regression**

Run: `pytest tests/unit/ tests/integration/ -q --tb=short`
Expected: all pass

- [ ] **Step 2: Ruff**

Run: `ruff check src tests`
Expected: All checks passed

- [ ] **Step 3: Update PROGRESS.md**

添加本次实施记录。

- [ ] **Step 4: Update OPEN_QUESTIONS.md**

将 Q-2026-06-20-evidence-反馈闭环路由需重新设计 标记为"已实施"。

- [ ] **Step 5: Final commit + push**

```bash
git add -A
git commit -m "docs: evidence v2 + 阈值调整完成 — PROGRESS + OPEN_QUESTIONS 更新"
git push origin master
```
