# 反馈闭环路由改进设计

## 背景

S4 实测暴露：evidence=2 → critic issues 打回 collector → collector 重搜相同结果 → evidence 仍为 2 → 闭环有害。
根因：evidence 低分大部分是"writer 有 URL 可用但没写进 source_refs"，不是"搜不到信息"。

## 设计目标

1. 路由正确性：区分"有源不用"（打回 writer）vs"真缺源"（打回 collector 补采）
2. 打回有效性：被打回的 agent 收到具体可执行的反馈指令
3. 补采有效性：collector 打回时做定向补充搜索，不盲跑

## 方案：代码路由 + 双路径反馈注入

### Part 1：路由决策逻辑

位置：`builder.py` 的 `should_continue` 函数。

当第一条 critical/major issue 的 `issue_type` 属于 evidence 类（`url_not_discovered` / `source_mismatch` / `source_irrelevant`）时，不直接用 `_ISSUE_TYPE_TO_AGENT` 映射，而是用代码层判断：

```python
evidence_types = {"url_not_discovered", "source_mismatch", "source_irrelevant"}

if issue.issue_type in evidence_types:
    discovered = state.get("discovered_sources", [])
    discovered_urls = {d["url"] for d in discovered if isinstance(d, dict)}
    report = state.get("report")
    used_urls = _extract_used_urls(report)  # 从报告递归收集所有 source_refs url
    
    coverage = len(used_urls & discovered_urls) / max(len(discovered_urls), 1)
    
    if coverage < 0.5 and len(discovered_urls) >= 8:
        # 有充足源但引用率低 → writer 问题
        return "writer"
    elif len(discovered_urls) < 5:
        # 源本身就少 → collector 补采
        return "collector"
    else:
        # 模糊地带：默认打回 writer
        return "writer"
```

`_extract_used_urls(report)` 复用 `writer_orchestrator.py` 已有的 `_collect_source_refs_recursive` 逻辑。

### Part 2：Writer 收到 evidence 反馈后的行为

触发条件：`writer_node` 检测到 feedback 有 evidence 类 issues。

注入位置：**phase 3 narrative** 的每个 section prompt 尾部追加：

```
【质检反馈：溯源引用不足】
上一轮报告 evidence 评分不及格（source_refs 覆盖率低）。本次重写请确保：
1. 每个 analysis_section 的 narrative 中至少引用 1 个 source_ref URL
2. key_findings 的每条 statement 必须关联至少 1 个 source_ref
3. 可用的溯源 URL 列表如下（从 discovered_sources 中选取）：
   - {url_1}
   - {url_2}
   ...
请优先使用上述 URL，在 source_refs 数组中以 {"url": "...", "title": "..."} 格式引用。
```

实现方式：
- `WriterOrchestrator.write()` 新增 `evidence_feedback: dict | None` 参数
- `writer_node` 在调用 `orch.write()` 前从 state["feedback"] 提取 evidence issues → 构造 evidence_feedback（含 discovered_urls 列表）
- `_phase3_one_section` 里判断 evidence_feedback 非空时追加上述指令到 system_prompt

不改 phase 1/2（骨架和 payload 不涉及 source_refs）。

### Part 3：Collector 定向补采

触发条件：`should_continue` 判定 `len(discovered_urls) < 5` → 打回 collector。

Collector 行为变化：

1. **检测 feedback**：`_collect_single` 开始前检查 `state["feedback"]` 是否有 evidence issues
2. **LLM 生成补充 query**：用 fast 模型一次调用，输入 = feedback issues（evidence 类）+ 竞品名列表 + 场景，输出 2-3 条针对性 query
3. **增量搜索**：只跑补充 query × Tavily，不重跑原有 3 条 scenario query
4. **结果追加**：新 URL + 正文 append 到已有 profiles 的 data_sources（不重新 extract profile）
5. **更新 discovered_sources**：新 URL 追加到 state

如果补充搜索仍搜不到有效结果：日志记录，不再打回，让流程继续。

### 数据流变化

```
inspector 出分 → should_continue:
  ├─ evidence issue + discovered_urls ≥ 8 + coverage < 0.5
  │   → 打回 writer（带 evidence_feedback：URL 列表 + 强制引用指令）
  │   → writer phase 3 注入反馈 → 重写 narrative 多引用 source_refs
  │
  ├─ evidence issue + discovered_urls < 5
  │   → 打回 collector（带 feedback issues）
  │   → collector LLM 生成补充 query → 增量搜索 → 追加数据
  │   → 继续走 analyzer → writer → inspector
  │
  └─ 非 evidence issue（vague_description / cross_field_contradiction 等）
      → 沿用原有 _ISSUE_TYPE_TO_AGENT 映射
```

### 不改动的部分

- `_ISSUE_TYPE_TO_AGENT` 映射表保持原样（非 evidence issues 不受影响）
- phase 4 URL 双通道聚合 + 幻觉过滤逻辑不变
- critic prompt 不改
- `max_retries=2` 强制结束兜底不变

### 测试策略

1. 单测：`should_continue` 在不同 discovered_sources 数量 + coverage 比例下的路由结果
2. 单测：writer phase 3 注入 evidence_feedback 后 prompt 包含 URL 列表
3. 单测：collector 定向补采模式生成 query + 增量搜索 + 追加结果
4. 集成测试：mock 一个 evidence=2 的 feedback → 验证路由到 writer → writer 产出 source_refs 数增加

## 实证依据

- S4 trace `20260620-153459-f19d5f`：两轮 evidence=2，discovered_sources 充足但 writer 只引用了 5/12
- S5 trace `20260619-203923-9f5681`：同样 12 条 URL 只引用 5 条
- S1 trace `20260620-124502`：打回 collector 后搜索结果与首次完全相同
