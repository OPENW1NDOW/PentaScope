# 反馈闭环路由改进设计 v2

> v2 修订：合并单模型 + 跨模型（codex/GPT-5.5）两轮 doubt-driven 审查共 9 条 actionable findings。

## 背景

S4 实测暴露：evidence=2 → critic issues 打回 collector → collector 重搜相同结果 → evidence 仍为 2 → 闭环有害。
根因：evidence 低分大部分是"writer 有 URL 可用但没写进 source_refs"，不是"搜不到信息"。

## 设计目标

1. 路由正确性：区分"有源不用"（打回 writer）vs"真缺源"（打回 collector 补采）
2. 打回有效性：被打回的 agent 收到具体可执行的反馈指令（含哪些段落引用不够）
3. 补采有效性：collector 打回时做定向补充搜索（含正文），不盲跑
4. 防御性：discovered_sources 为空 / report 为 None / 补采失败 均有安全 fallback

## 方案：代码路由 + 双路径反馈注入

### Part 1：路由决策逻辑

#### 1.1 独立函数 `_route_evidence_issue`

位置：`builder.py` 模块级函数（不嵌在 `build_graph` 内），便于单测。

```python
def _route_evidence_issue(state: AnalysisState) -> str | None:
    """evidence 类 issue 的智能路由。返回 "writer"/"collector"/"end"/None。
    None 表示走原有 _ISSUE_TYPE_TO_AGENT 映射。"""
    
    # 防御：无数据时不做判断
    discovered = state.get("discovered_sources", [])
    if not discovered:
        return None
    
    discovered_urls = {_normalize_url(d["url"]) for d in discovered 
                       if isinstance(d, dict) and d.get("url")}
    if not discovered_urls:
        return None
    
    report = state.get("report")
    if report is None:
        return None
    
    used_urls = {_normalize_url(u) for u in _extract_used_urls(report)}
    coverage = len(used_urls & discovered_urls) / len(discovered_urls)
    
    # 退出条件：第二次 evidence 打回且 coverage 未提升
    prev_coverage = state.get("_prev_evidence_coverage")
    if prev_coverage is not None and coverage >= prev_coverage - 0.05:
        return "end"
    
    # 路由判断
    if len(discovered_urls) >= 8 and coverage < 0.5:
        return "writer"
    elif len(discovered_urls) < 5:
        return "collector"
    else:
        return "writer"
```

**关键修订**：
- 函数提取为模块级（审查 #4：减轻 should_continue 职责）
- URL 比较用 `_normalize_url` 归一化（审查 I1：去尾 slash / fragment / http→https）

#### 1.2 URL 归一化函数

```python
def _normalize_url(url: str) -> str:
    """归一化 URL 用于比较：去尾 slash / fragment / 统一 https。"""
    from urllib.parse import urlparse, urlunparse
    parsed = urlparse(url)
    scheme = "https"  # 统一为 https
    path = parsed.path.rstrip("/")
    # 去 fragment，保留 query（可能含有意义的参数）
    return urlunparse((scheme, parsed.netloc, path, parsed.params, parsed.query, ""))
```

#### 1.3 should_continue 集成

```python
def should_continue(state):
    # ... 现有 passed/critic_failed/max_retries 检查 ...
    
    # 优先扫描 evidence issues（审查 C3：不被非 evidence issue 挡住）
    evidence_types = {"url_not_discovered", "source_mismatch", "source_irrelevant"}
    for issue in feedback.issues:
        if issue.severity in ("critical", "major") and issue.issue_type in evidence_types:
            evidence_route = _route_evidence_issue(state)
            if evidence_route is not None:
                # 写入当前 coverage 供下轮退出判断（审查 C1）
                # 注：通过 inspector_node 返回的 state dict 更新
                return evidence_route
            break  # fallback to original mapping
    
    # 原有逻辑：取第一条 critical/major issue.agent
    for issue in feedback.issues:
        if issue.severity in ("critical", "major"):
            return issue.agent
    return "end"
```

**关键修订**：
- 优先扫描 evidence issues（审查 C3）
- `_prev_evidence_coverage` 由 `_route_evidence_issue` 计算后通过 state 返回写入（审查 C1）

#### 1.4 `_prev_evidence_coverage` state 更新

在 `inspector_node` 返回 state 时，如果 evidence 评分 ≤ 2，顺带计算并写入 `_prev_evidence_coverage`：

```python
# inspector_node 末尾：
result = {"feedback": feedback, "current_node": "inspector", "retry_count": next_retry}
if critic_scores and critic_scores.evidence <= 2:
    # 预计算 coverage 供下轮 _route_evidence_issue 判断退出条件
    discovered_urls = {_normalize_url(d["url"]) for d in (state.get("discovered_sources") or [])
                       if isinstance(d, dict) and d.get("url")}
    used_urls = {_normalize_url(u) for u in _extract_used_urls(report)} if report else set()
    result["_prev_evidence_coverage"] = len(used_urls & discovered_urls) / max(len(discovered_urls), 1)
return result
```

### Part 2：Writer 收到 evidence 反馈后的行为

#### 2.1 state flag 传递

`should_continue` 返回 "writer" 时，同时写入 state flag：
```python
result["_evidence_rerouted"] = True
result["_evidence_feedback_urls"] = sorted(discovered_urls)[:10]
result["_evidence_weak_fields"] = [i.field for i in feedback.issues 
                                    if i.issue_type in evidence_types]
```

**关键修订**：
- state flag `_evidence_rerouted` 让 writer_node 知道自己被 evidence 路由过来（审查 I2）
- `_evidence_weak_fields` 告诉 writer 哪些段落引用不够（审查 I4 / Cooper 产品决策）
- URL 列表最多 10 条（审查 #5：防 token 爆）

#### 2.2 EvidenceFeedback Pydantic 模型

位置：`src/schemas/feedback.py`（与现有 FeedbackIssue 同文件）

```python
class EvidenceFeedback(BaseModel):
    available_urls: list[str] = Field(default_factory=list)  # 最多 10 条
    weak_fields: list[str] = Field(default_factory=list)  # critic issues 指出的具体字段
    coverage_pct: float = 0.0
```

#### 2.3 writer_node 检测 + 注入

```python
# writer_node 中：
evidence_rerouted = state.get("_evidence_rerouted", False)
evidence_feedback = None
if evidence_rerouted:
    evidence_feedback = EvidenceFeedback(
        available_urls=state.get("_evidence_feedback_urls", []),
        weak_fields=state.get("_evidence_weak_fields", []),
        coverage_pct=state.get("_prev_evidence_coverage", 0.0),
    )
    # 清除 flag 防止下次 writer 重入时误触发
    # （通过返回 state dict 中 _evidence_rerouted=False 清除）
```

#### 2.4 phase 3 prompt 注入

修改 `_phase3_one_section`：

1. **去掉 `_ = discovered_urls`**（审查 C4：不再丢弃 URL 列表）
2. 当 `evidence_feedback` 非空时，在 system_prompt 尾部追加：

```
【质检反馈：溯源引用不足】
上一轮 evidence 覆盖率 {coverage_pct:.0%}，以下字段被标记为引用不足：
{weak_fields 逐行列出}

本次重写请确保：
1. 上述字段对应的 narrative 段落中必须引用至少 1 个 source_ref URL
2. 可用的溯源 URL 列表（优先使用）：
   - {url_1}
   - {url_2}
   ...（最多 10 条）
在 source_refs 数组中以 {"url": "...", "title": "相关描述"} 格式引用。
如果某段内容确实无法关联上述 URL，source_refs 留空数组 [] 即可。
```

**关键修订**：
- 包含 `weak_fields`（审查 I4）：告诉 LLM 具体哪些段落要改
- 保留"无法关联则留空"（审查 C4 独占发现：避免强制引用导致 `source_irrelevant`）
- URL 最多 10 条（审查 #5）

### Part 3：Collector 定向补采

#### 3.1 新增 `CollectorAgent.supplement_collect()` 方法

（审查 I3：现有 `collect()` 是全量重跑，需要独立增量入口）

```python
async def supplement_collect(
    self,
    competitors: list[CompetitorBasic],
    feedback_issues: list[FeedbackIssue],
    scenario: str,
    existing_profiles: list[CompetitorProfile],
) -> tuple[list[CompetitorProfile], list[dict]]:
    """定向补采：从 feedback issues 生成补充 query → 增量搜索 → 追加正文+URL 到已有 profiles。"""
```

#### 3.2 补采流程

1. **LLM 生成补充 query**（fast 模型）：输入 = evidence issues 的 field + reason + 竞品名 + 场景，输出 2-3 条 query
2. **增量搜索**：补充 query × Tavily，结果过 `is_low_quality` 质量闸门（审查 #6）
3. **正文追加**（审查 C2）：新搜到的**正文 + URL** 追加到对应竞品的 profile（通过构造新 profile 副本返回，不 mutate 原对象）
4. **更新 discovered_sources**：新 URL 以 `{"url": ..., "title": ..., "snippet": ...}` 格式追加（通过节点返回增量 dict）
5. **去重**：补充 URL 经 `_normalize_url` 归一化后与已有 `discovered_sources` 去重

#### 3.3 collector_node 集成

```python
# collector_node 中：
feedback = state.get("feedback")
if feedback and any(i.issue_type in evidence_types for i in feedback.issues):
    # 增量补采模式
    new_profiles, new_sources = await collector.supplement_collect(
        competitors=state["user_input"].competitors,
        feedback_issues=feedback.issues,
        scenario=state["user_input"].scenario,
        existing_profiles=state["profiles"],
    )
    if new_sources:
        return {"profiles": new_profiles, "discovered_sources": existing + new_sources}
    else:
        # 补采无效（审查 I6）：日志记录，不更新 state，让流程继续
        logger.warning("[graph] collector 补采无新数据，跳过")
        return {"current_node": "collector"}
else:
    # 原有全量采集模式
    ...
```

#### 3.4 补采后走完整链

打回 collector 后，graph 边 `collector → analyzer → writer → inspector` 不变——补采后自然经过 analyzer（用新正文重新分析）→ writer（用新 analysis 重写）→ inspector。**不跳过 analyzer**（审查 C2/codex：analyzer 需要看到新正文才能产出有意义的分析）。

#### 3.5 补采失败降级

- Tavily 不可用 / 无 API key：直接跳过补采，日志记录
- LLM 生成 query 失败：用 fallback 确定性 query `"{name} 最新信息 评测"`
- 全部补充 query 搜索结果为 0 或全被质量闸门过滤：返回空，collector_node 不更新 state

### 不改动的部分

- `_ISSUE_TYPE_TO_AGENT` 映射表保持原样（evidence 路由在 should_continue 层拦截，不改映射表本身）
- phase 4 URL 双通道聚合 + 幻觉过滤逻辑不变
- critic prompt 不改
- `max_retries=2` 强制结束兜底不变
- phase 1/2 不改

### 阈值说明

| 阈值 | 值 | 选择依据 |
|------|---|---------|
| coverage < 0.5 | 50% | 引用了不到一半可用源，writer 有改善空间 |
| discovered_urls >= 8 | 8 | S1-S5 实测正常场景 12-15 条（3 竞品 × 5 URL 去重） |
| discovered_urls < 5 | 5 | 低于此值说明搜索本身失败/降级 |
| URL 注入最多 10 条 | 10 | 单 section prompt ~4K token，10 URL ~1K token 安全 |
| coverage 退出容差 | 0.05 | 允许微小波动不误判为"未改善" |

### 测试策略

1. 单测 `_route_evidence_issue`：不同 discovered 数量 + coverage + prev_coverage 下的返回值
2. 单测 `_normalize_url`：尾 slash / http→https / fragment 去除
3. 单测 writer phase 3 注入：evidence_feedback 非空时 prompt 包含 URL 列表 + weak_fields
4. 单测 `supplement_collect`：LLM 生成 query + 增量搜索 + 质量闸门 + 去重
5. 集成测试：mock evidence=2 feedback → 验证路由到 writer → writer 产出 source_refs 增加
6. 集成测试：mock discovered < 5 → 验证路由到 collector → supplement_collect 被调用

## 已知限制（v2 接受的 trade-off）

- **I5**：discovered_urls 5-7 个的"模糊地带"一律路由 writer，可能有真缺源 case 被误判。max_retries 兜底，影响有限
- **URL 归一化**：初版不处理 UTM 参数和重定向跳转，只做基础归一化（scheme/path/fragment）

## 实证依据

- S4 trace `20260620-153459-f19d5f`：两轮 evidence=2，discovered_sources 充足但 writer 只引用了 5/12
- S5 trace `20260619-203923-9f5681`：同样 12 条 URL 只引用 5 条
- S1 trace `20260620-124502`：打回 collector 后搜索结果与首次完全相同
- S5 URL 变体问题：`hk-bingo.com/news/ui-ux-design-software-comparison` vs `/ui/ux-design-software-comparison`

## doubt-driven 审查记录

- 单模型审查：12 条（4 critical / 4 important / 4 noise）
- 跨模型审查（codex/GPT-5.5）：30+ 条（4 critical / 6 important / 其余 noise 或重复）
- 合并去重 actionable：9 条（全部纳入 v2 修订）
- 产品决策 1 条（I4 weak_fields：Cooper 拍板"告诉 writer 哪些段落不够"）
- 接受的 trade-off：2 条（I5 模糊地带 / URL 归一化范围）
