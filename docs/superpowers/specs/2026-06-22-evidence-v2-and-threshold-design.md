# Evidence 反馈闭环 v2 + 截断阈值调整 设计

## 背景

S4 端到端验证暴露两个独立问题：

1. **URL 引用张冠李戴**：writer 在多竞品场景下把 A 竞品的 URL 引到 B 竞品的论断中（历史 36 条 evidence issues 中 78% 是 source_mismatch）。根因：writer 只看到扁平 URL 列表，不知道哪个 URL 属于哪个竞品。
2. **labeled_text 截断导致 profile 不完整**：30 万字符上限导致大厂竞品（金山办公等）的后半段文本被截断，pricing/user_reviews 提取不到（completeness 卡在 0.70）。

此外，当前 evidence 反馈闭环 v1 基于错误假设（以为问题是"引用不足"），代码需要清理。

## 目标

- Writer 引用 URL 时不再张冠李戴（准确性）
- Prompt 鼓励 writer 为事实性论断附上 source_ref（覆盖率，软约束）
- Inspector 打回 writer 时传递精确的错误信息而非泛化的覆盖率模板
- 删除 v1 中基于错误假设写的代码，简化路由逻辑
- 截断阈值放宽到 50 万，让更多文本进入 LLM 提取

## 非目标

- 不要求每段 narrative 都必须有 source_refs（不加硬约束）
- 不做代码层自动补引用（phase 4 assemble 不改）
- 不新增 source_insufficient issue 类型（当前只修准确性）
- 不改 inspector critic prompt（评分逻辑不变）

---

## 设计

### Part 1: 按竞品分组传 URL（预防层）

**数据构造**：在 `WriterOrchestrator.write()` 内部，从 `profiles` 参数构建按竞品分组的 URL 字典：

```python
# {竞品名: [URL1, URL2, ...]}
grouped_urls = {}
for p in profiles:
    name = p.basic_info.name
    urls = sorted(collect_profile_urls(p))
    grouped_urls[name] = urls
```

**Phase 2 注入**：当前 `payload/_common.py` 的 `discovered_urls_json` 是扁平列表。改为按竞品分组的 JSON：

```
profiles_source_urls（按竞品归属）：
{
  "GrowingIO": ["https://growingio.com/...", "https://growingio.github.io/..."],
  "友盟": ["https://devs.umeng.com/...", "https://info.umeng.com/..."],
  "金山办公数据分析": ["https://volcengine.com/...", "https://developer.volcengine.com/..."]
}

引用规则：source_refs 中的 URL 必须属于你正在论述的竞品。论述 GrowingIO 时只能用 GrowingIO 的 URL。
```

**Phase 3 注入**：在 `_phase3_one_section` 的 system_prompt 末尾追加按竞品分组的 URL 列表 + 引用规则 + 鼓励引用的软约束：

```
【溯源引用规则】
可用 URL（按竞品归属）：
- GrowingIO: https://growingio.com/..., https://growingio.github.io/...
- 友盟: https://devs.umeng.com/..., https://info.umeng.com/...
- 金山办公: https://volcengine.com/..., https://developer.volcengine.com/...

规则：
1. 论述哪个竞品时，source_refs 只能从该竞品对应的 URL 中选取
2. 尽量为每个事实性论断（产品功能、市场数据、用户反馈等）附上至少 1 个 source_ref
3. 找不到对应 URL 时 source_refs 留空 []，绝不编造、绝不跨竞品引用
```

### Part 2: 打回时传精确反馈（纠正层）

**writer_node 修改**：检测 feedback 中的 evidence issues 时，直接把 `issue.field + issue.reason + issue.suggestion` 拼成纠正指令注入 phase 3 prompt：

```
【质检打回：以下引用存在问题，请修正】
- key_findings[0].source_refs[1]: 用火山引擎(volcengine)文档的 URL 证明 GrowingIO 的 XBA 模型，源与论断完全无关。建议：移除或替换该 source_ref，使用属于 GrowingIO 的官方文档链接。
- key_findings[1].source_refs[0]: 用友盟(umeng)的 URL 证明金山办公的"智能分析 Agent"，源与论断完全无关。建议：替换为金山办公相关文档链接。
```

**不再传**：覆盖率数字、URL 列表、weak_fields 等泛化信息。

**传递机制**：`WriterOrchestrator.write()` 新增参数 `feedback_issues: list[FeedbackIssue] | None = None`（复用已有的 FeedbackIssue schema），传到 `_phase3_one_section` 注入 prompt。不需要 EvidenceFeedback schema。

### Part 3: 路由简化 + 代码清理

**修正路由映射**（`src/agents/inspector.py`）：

```python
_ISSUE_TYPE_TO_AGENT = {
    "url_not_discovered": "collector",
    "source_mismatch": "writer",      # 之前错误映射到 collector
    "source_irrelevant": "writer",
    "vague_description": "writer",
    "cross_field_contradiction": "writer",
    "vague_recommendation": "writer",
    "critic_failed": "end",
}
```

**删除的代码**：

| 文件 | 删除内容 |
|------|----------|
| `src/graph/builder.py` | `_route_evidence_issue` 函数、`_extract_used_urls` 函数、`_EVIDENCE_ISSUE_TYPES` 常量、`should_continue` 中的 evidence 优先扫描逻辑、`inspector_node` 中写 `_prev_evidence_coverage` 的逻辑、`writer_node` 中构造 EvidenceFeedback 的逻辑、`collector_node` 中增量补采模式逻辑 |
| `src/graph/state.py` | `_prev_evidence_coverage` 字段 |
| `src/schemas/feedback.py` | `EvidenceFeedback` class |
| `src/agents/collector.py` | `supplement_collect` 方法、`_SUPPLEMENT_QUERY_SYSTEM` |
| `src/agents/writer_orchestrator.py` | `evidence_feedback` 参数及相关注入逻辑 |
| `src/utils/url_normalize.py` | 保留（phase 2/3 可能复用） |
| `tests/unit/test_evidence_routing.py` | 删除整个文件（路由函数已删） |
| `tests/unit/test_supplement_collect.py` | 删除整个文件 |
| 相关测试中的 evidence_feedback 测试 | 删除 |

**`should_continue` 回归原始逻辑**：删除 evidence 优先扫描分支，恢复为直接按第一条 critical/major issue 的 `agent` 字段路由。

### Part 4: 截断阈值调整

`src/agents/collector.py` 第 12 行：

```python
_EXTRACT_TEXT_MAX_CHARS = 500_000  # 从 300_000 调整
```

---

## 数据流变化

### 改前

```
collector → profiles (flat data_sources)
         → discovered_sources [{url, title, snippet}]

writer phase 2: discovered_urls_json = 扁平 URL 列表
writer phase 3: 无 URL 列表注入（只有规则文字）
writer_node 打回时: EvidenceFeedback(available_urls, weak_fields, coverage_pct)

should_continue: _route_evidence_issue(coverage 判断) → writer/collector/end
```

### 改后

```
collector → profiles (同上，不变)
         → discovered_sources (同上，不变)

writer phase 2: grouped_urls_json = {竞品名: [URLs]} 分组格式
writer phase 3: system_prompt 末尾注入分组 URL + 引用规则
writer_node 打回时: feedback_issues = [{field, reason, suggestion}] 原文

should_continue: issue.agent 字段直接路由（_ISSUE_TYPE_TO_AGENT 映射）
```

---

## 验证

1. **单元测试**：
   - 新增：`test_grouped_urls_in_phase2_prompt` — 验证 phase 2 prompt 包含分组 URL
   - 新增：`test_grouped_urls_in_phase3_prompt` — 验证 phase 3 prompt 包含分组 URL + 引用规则
   - 新增：`test_feedback_issues_injected_on_retry` — 验证打回时 prompt 包含 reason/suggestion
   - 新增：`test_source_mismatch_routes_to_writer` — 验证路由映射修正
   - 删除：`test_evidence_routing.py` 整个文件
   - 删除：`test_supplement_collect.py` 整个文件
   - 删除：`test_phase3_evidence_feedback_injects_urls`
   - 修改：确认现有测试无回归（删代码后 import 是否干净）

2. **端到端验证**：
   - 跑 S4 场景，观察 writer 引用的 URL 是否与论述的竞品匹配
   - 观察 inspector evidence 评分是否提升（目标 ≥2 → ≥3）
   - 如果打回，观察 writer 第二轮是否修正了 source_mismatch

3. **阈值验证**：
   - 跑包含金山办公的场景，确认 labeled_text 不再被截断（或截断频率大幅下降）
   - 确认 completeness_score 从 0.70 提升（pricing/user_reviews 不再为空）

---

## 风险

- Phase 3 prompt 增加 42 条分组 URL 会增加约 2000-3000 token 输入，在 12288 max_tokens 的 context 下影响可控
- 路由简化后 `url_not_discovered` 仍打回 collector，但该类型只占 3%，collector 全量重跑（非增量）是可接受的
- 阈值放宽到 50 万后 LLM 提取质量是否下降需要验证（超长文本注意力稀释）
