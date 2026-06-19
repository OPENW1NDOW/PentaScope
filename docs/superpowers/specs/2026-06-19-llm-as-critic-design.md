# LLM-as-Critic 评分系统设计 v3

> **v3 状态**：v1 → v2 已合 33 条审查反馈中的 26 条 actionable；v2 经 cycle 2
> Codex 审查再发现 22 条问题（4 critical / 12 major / 6 minor），其中 20 条
> actionable 在本 v3 版本中合入。修订日志见文末。

> 落实 OPEN_QUESTIONS Q-2026-06-17-字数约束的代理失效 的核心修法。
> 不再用字数 schema 代理"内容质量"，改用语义级 LLM critic 给报告打分。
> Brainstorming 8 个问题已逐一拍板（决策映射见决策表的 Q# 列）。

## 背景

PentaScope 当前 inspector 的 quality_score 三项加权（source_coverage / confidence_avg / inspector_pass_rate）实证存在三类问题：

1. **confidence_avg 是假动态** — `writer_orchestrator.py:1375` 全部 DataSource.confidence 写死为 "medium"，导致历史所有 trace 的 confidence_avg ≡ 0.6
2. **source_coverage 只测有无 source，不测相关性** — 引用错位的报告（如 `runs/20260617-181916-91bc54` 中 PostHog finding 引 OpenAI 事故公告）coverage 仍然高
3. **inspector_pass_rate 是 issue 数倒推** — 跟 critic 维度分会重复计算

更上游的根因（OPEN_QUESTIONS Q-2026-06-17-字数约束）：schema 字段大量 ≥N 字符约束作为"反空话"代理，LLM 字符层面执行差，已经造成多次重试浪费和"长但空"的报告产出。

本设计用 **LLM-as-critic 语义评分**替换三项加权，作为"字数约束分阶段退役"路径的前置基础设施。

## 核心决策（已固化）

| # | 决策项 | 选择 | brainstorming Q# | 理由摘要 |
|---|--------|------|------------------|---------|
| 1 | 架构 | 路线 A — critic 是 inspector 内部子模块 | Q-架构 | 不新增 graph 节点，反馈闭环复用 |
| 2 | 维度 | evidence + specificity + coherence + actionability（4 维） | Q-维度 | Cooper 痛感排序 C/A/D + 决策时加回 actionability（详见"维度选择实证基础"）|
| 3 | 权重 | 0.30 / 0.30 / 0.20 / 0.20 | Q-维度（派生）| 重证据 + 具体；coherence/actionability 同权 |
| 4 | quality_score 计算 | critic_score 完全替换 coverage + confidence + pass_rate | Q-维度（派生）| 三项有 bug 或冗余 |
| 5 | 集成顺序 | C — critic 内嵌一次 LLM 调用同时输出 rubric + issues | Q2-集成顺序 | 省一次 LLM 调用 |
| 6 | Coherence 范围 | 限定 pair 比对（3 个固定 pair + deterministic builder） | Q6-评分粒度（派生）| 全文级 LLM 注意力不擅长 |
| 7 | 失败降级 | B+C — retry 1 次（length 错除外），仍失败 critic_score=0.5 + 强制生成 critic_failed major issue | Q3-失败降级 | 救偶发抖动，不让 critic 失败 = 报告 0 分 |
| 8 | 阈值规则 | D' — dim ≤1 强制 critical / dim ≤2 至少 major / 否则均值映射 | Q4-阈值（v2 升级）| 防"3 维优秀掩盖 1 维灾难" + 防维度信号被聚合分抹平 |
| 9 | CoT 策略 | B — 全维度带 CoT，但 reasoning 改结构化短 bullet（非自由长文）| Q5-CoT | 工程经验：CoT 提升 LLM-judge 一致性，但长 reasoning 跟 JSON 解析冲突 |
| 10 | 评分粒度 | A — 整报告级单次评分 | Q6-评分粒度 | 章节级会爆 quota 上限 |
| 11 | 测试策略 | Y' — 三层：单元（fake stub）+ 集成（fake critic）+ prompt snapshot eval（手动）| Q7-测试 | record/replay 测不到 critic 真实判断力，拆双层 |
| 12 | v3-R17 cap 0.5 | 完全删除 | Q8-cap | critic 已天然惩罚 placeholder |
| 13 | max_tokens | critic 调用 8192 | Q5-CoT（派生）| CoT 输出长，4096 不够 |

**Q# 命名**：Q-架构 / Q-维度 / Q2-集成顺序 / Q3-失败降级 / Q4-阈值 / Q5-CoT / Q6-评分粒度 / Q7-测试 / Q8-cap。其中 Q1（rubric 维度选择）和 Q-架构是 brainstorming 早期问题，后续 Q2-Q8 是按顺序拍板的 7 个问题，加上 Q-架构共 8 个。13 项决策中 5 项标 "(派生)" 是其他决策的连带影响。

### 维度选择实证基础

Cooper 选择 C/A/D（evidence/specificity/coherence）+ actionability 的依据来自历史 trace 暴露的失败模式：

| 失败模式 | 实证 trace | 对应 critic 维度 |
|---------|-----------|-----------------|
| 引用错位（finding 引第三方聚合站）| `runs/20260617-181916-91bc54` PostHog finding 引 OpenAI 事故公告 | evidence |
| 长但空（rationale ≥50 字符过 schema 但全套话）| 多次 trace 实证（OPEN_QUESTIONS Q-2026-06-17-字数约束）| specificity |
| SWOT 跟 vendor cautions 矛盾 | trace `20260618-095358-c5ab5c` 多次 | coherence |
| recommendation "加强 AI 能力"无具体动作 | 多次 trace | actionability |

## 架构设计

### Inspector v4 流程

```
inspect(report):
  Step 1: _programmatic_checks()
    - _check_common(report)       # schema 之外的硬查
    - _dispatch_scenario_check    # _check_s1..s5
    （删除 _check_warnings_prefix——v3-R17 cap 一并删）

  Step 2: _critic_check(report, discovered_urls)
    - 外层 broad except 兜底（任何非 LLM 异常也降级）
    - 调用 LLM（system=CRITIC_PROMPT, max_tokens=8192）
    - 失败 retry 1 次（length 错除外）
    - 仍失败/length 错 → critic_score=0.5, critic_scores=None,
                          warnings.append("critic_failed:<code>"),
                          critic_issues=[强制生成的 critic_failed major issue]
    - 成功 → 返回 (CriticScores, list[FeedbackIssue])

  Step 3: 合并 issues
    - prog_issues + critic_issues
    - 按 (agent, field, dimension) 三元组去重，保留最严重
    - dimension 字段是 critic 维度名（"evidence"/"specificity"/...），
      prog_issues 该字段填 "programmatic"

  Step 4: quality_score 计算
    - weighted_raw_score = 0.30*ev + 0.30*sp + 0.20*co + 0.20*ac  # 1-4 区间
    - quality_score = clamp((weighted_raw_score - 1) / 3, 0.0, 1.0)  # 归一化到 [0, 1]
    - 写入 metadata.quality_score（永远非空，clamp 保证 ∈ [0,1]）
    - 写入 metadata.score_source = "critic" 或 "fallback"
    - 写入 metadata.critic_scores = CriticScores（fallback 时 None）
    - 写入 metadata.quality_score_calculation_note（已有字段，复用）

  Step 5: passed 判定
    # v3 修订（cycle2/M2）：改成显式判定，避免 all([]) == True 隐式语义
    - passed = not any(issue.severity in {"critical", "major"} for issue in issues)
    - critic_failed major issue 强制让 passed=False，触发反馈闭环
    - 现有判定逻辑等价但更显式（empty issue list 仍为 passed=True，符合预期）
```

### 组件清单

#### 删除的组件

| 文件 | 组件 | 理由 |
|------|------|------|
| `src/agents/quality_score.py` | `calc_source_coverage` | 跟 critic.evidence 重叠，细粒度替粗粒度 |
| `src/agents/quality_score.py` | `calc_confidence_avg` | 假动态恒等于 0.6 |
| `src/agents/quality_score.py` | `calc_inspector_pass_rate` | 跟 critic.threshold 映射重叠 |
| `src/agents/quality_score.py` | 旧 `calc_quality_score` 三项加权 | 整体替换为新 `calc_critic_score` |
| `src/agents/inspector.py` | `_QUALITY_SCORE_CAP_ON_PLACEHOLDER` | v3-R17 废弃 |
| `src/agents/inspector.py` | `_detect_placeholder_warnings` | cap 删了它就没用 |
| `src/agents/inspector.py` | `_check_warnings_prefix` | 同上 |
| `src/agents/inspector.py` | `_llm_check` | 重写为 `_critic_check`（外部调用方搜索结果：仅 inspector.inspect 一处，无 graph/api/前端调用，无兼容包袱）|
| `src/agents/prompts/__init__.py` | `INSPECTOR_SYSTEM` | critic prompt 移到独立文件 |

#### 新增的组件

| 文件 | 组件 | 职责 |
|------|------|------|
| `src/agents/inspector.py` | `_critic_check(report, discovered_urls)` | 调 critic LLM，4 维 CoT 评分，含 retry + 降级；外层 broad except |
| `src/agents/inspector.py` | `_score_to_severity(dim_score, all_scores)` | D' 阈值规则（v2 升级）|
| `src/agents/inspector.py` | `_build_limited_pairs(report)` | deterministic 构造 3 个 coherence pair |
| `src/agents/inspector.py` | `_sample_items_deterministic(items, n=5, seed_field='id')` | deterministic 抽样（hash by id 排序后取前 N）|
| `src/agents/inspector.py` | `_build_critic_inputs(report, discovered_urls)` | 拼装 critic LLM 的 user_prompt（含 source title + snippet）|
| `src/agents/quality_score.py` | `calc_critic_score(scores: CriticScores \| Mapping[str, Any]) -> float` | 4 维加权 + 归一化 + clamp；签名兼容 model 和 dict；**仅读 evidence/specificity/coherence/actionability 4 个 key 当 int 处理，其他 key（如 reasoning）一律忽略**（v3 修订 cycle2/m4） |
| `src/agents/prompts/inspector/__init__.py` | 模块包 | 新建 |
| `src/agents/prompts/inspector/critic.py` | `CRITIC_SYSTEM`, `CRITIC_VERSION` | critic 4 维 CoT rubric prompt + 版本标识 |
| `src/schemas/feedback.py` | `CriticScores`（新 BaseModel） | 持久化 4 维分到 metadata |
| `src/schemas/feedback.py` | `FeedbackIssue.dimension`（新字段，Optional[str]） | 区分 critic 维度 vs programmatic |
| `src/schemas/report.py` | `ReportMetadata.critic_scores: Optional[CriticScores]` | metadata 字段扩展 |
| `src/schemas/report.py` | `ReportMetadata.score_source: Literal["critic", "fallback"]` | 区分 critic 真实分 vs 失败降级分 |
| `src/schemas/report.py` | `ReportMetadata.critic_version: Optional[str]` | 持久化 prompt 版本供历史追溯 |

### Schema 兼容（v2 修订 - C1）

**关键**：所有新增 metadata 字段必须 `Optional` 且默认 `None`，旧 trace 反序列化必须可行。

**Import 方向**（避免循环依赖）：
```
src/schemas/feedback.py     ← 定义 CriticScores（不 import report）
src/schemas/report.py       ← import CriticScores from feedback
src/agents/quality_score.py ← import CriticScores from feedback
```

`feedback.py` 不应 import `report.py`，避免循环。

**FeedbackIssue 兼容**：新增的 `dimension: Optional[str] = None` 字段确保旧 issue 反序列化不破坏（旧 dump 没有该字段时默认 None）。

**旧 trace 反序列化测试**：用 `runs/20260618-095358-c5ab5c/03_report.json`（v1 schema）作为 fixture，验证 v2 BaseReport schema 能加载。

## Critic Prompt 详细设计

### 整体结构

```
[ROLE]               资深咨询审计师（反 self-preference）
[TASK]               4 维 rubric 评分
[INPUTS]             report dict + discovered_urls（含 title/snippet）+ limited_pairs + sampled_items
[RUBRIC]             每维 1-4 分锚点（互斥区间）+ 正反例
[REASONING_STEPS]    每维 CoT 推理步骤
[OUTPUT_CONTRACT]    JSON 输出格式（reasoning 是结构化 bullet 数组）
[CONSTRAINTS]        硬约束
```

### [ROLE]

```
你是一位资深的咨询报告审计师，专业是质量稽核而非内容创作。你的职责
是按 4 个维度对一份竞品分析报告做 rubric 评分，并指出具体问题。

你不是作者。你不为报告辩护，也不脑补缺失内容。你只评判呈现给你的
内容。
```

### 上游数据流改动（v3 新增 - cycle2/M4）

**关键发现**：v2 假设 inspector 能拿到 source title/snippet 用于 evidence rubric 判断
URL 相关性，但当前架构不支持：
- `inspector.inspect()` 现有签名：`(report, competitors=None, retry_count=0, max_retries=2)`，**不传 discovered_urls**
- `AnalysisState` 没有 discovered URLs 字段
- collector 落盘的 `01_profiles.json` 含 source URL + title 但**不含 snippet**（只是搜索结果标题，没正文片段）

**v3 上游改动清单**（plan 阶段必须含）：

1. `src/graph/state.py::AnalysisState` 新增字段：
   ```python
   discovered_sources: list[dict] | None  # [{"url": str, "title": str, "snippet": str}]
   ```
2. `src/agents/collector.py` 在搜索阶段把 Tavily 返回的 `content` 字段（snippet）也保存
3. `src/graph/builder.py::collector_node` 把 discovered_sources 写入 state
4. `src/graph/builder.py::inspector_node` 调 `inspector.inspect(report, discovered_sources=state['discovered_sources'])`
5. `inspector.inspect()` 签名扩展含 `discovered_sources` 参数（保持 Optional 默认 None 向后兼容）

**降级策略**（cycle2/M4）：
- 如果 collector 没成功抓到 snippet（旧 trace / Tavily 失败），`discovered_sources[i]["snippet"]` 设 `""` 空字符串
- prompt 里 `_build_critic_inputs` 检查若 ≥80% sources 都是 `snippet=""`，加 prompt warning：
  `"⚠️ 大部分 source 缺少 snippet，evidence 维度仅能基于 URL/title 判断"`
- 这种情况下 critic 给 evidence 评分时降级标准：仅判定 URL 是否在 list 内 + title 主题匹配，不能要求严格相关性
- inspector 不因此降级 critic 整体评分（因为是上游数据问题，不是报告问题）

### [INPUTS] 输入构造（v2 修订 - M5/M6/M7；v3 调整 - cycle2/M4/M5）

由 `_build_critic_inputs(report, discovered_sources)` 代码生成，传给 LLM 的 user_prompt：

```python
{
  "report_brief": <report.model_dump() 但 narrative 截断到 2000 字符/章>,
  "discovered_sources": [
    # discovered_urls 不再是裸 URL 列表，加 title + snippet
    {"url": "...", "title": "...", "snippet": "<前 200 字符>"}
  ],
  "limited_pairs": [
    # _build_limited_pairs(report) deterministic 构造，固定 3 个：
    {
      "id": "swot_vs_vendor_cautions",
      "data_a": {"swot.strengths": [...涉及 vendor 名的条目]},
      "data_b": {"vendor_profiles[*].cautions": [...所有 vendor 的 cautions]}
    },
    {
      "id": "findings_vs_recommendations",
      "data_a": {"key_findings": [...]},
      "data_b": {"recommendations": [...]}
    },
    # v3 修订（cycle2/M5）：替换 score_vs_warnings 伪 pair
    # 原 pair 用 quality_score_hint="TBD（critic 计算中）"，critic 评分时此值还不存在，
    # 等于让 LLM 对未知字段做无意义推断。改用真实字段对照：
    {
      "id": "exec_summary_vs_recommendations",
      "data_a": {"executive_summary.implications": "..."},
      "data_b": {"recommendations": [...]}
    }
  ],
  "sampled_findings": [<deterministic 抽 5 条 key_findings + analysis_sections>],
  "sampled_narratives": [<deterministic 抽 5 段 narrative>],
  "sampled_recommendations": [<deterministic 抽 5 条>]
}
```

**limited_pairs 缺字段协议**（v2 - M5）：
- 任何 pair 的 `data_a` 或 `data_b` 缺失 → 该 pair 进 inputs 时显式标 `"data_a": null, "data_b": null, "skip_reason": "missing"`
- LLM 看到 `null` pair 不评分，coherence 自动按"剩余 pair 数"计算

**deterministic 抽样规则**（v2 - M7；v3 修订 - cycle2/M7）：
- `_sample_items_deterministic(items, n=5, seed_field='id')`
- 优先按 item.id（如果存在）排序，取前 N
- 没有 id 时用 `hashlib.sha256(json.dumps(item, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()` 排序
- **禁止使用 Python 内建 `hash()`**——受 PYTHONHASHSEED 影响跨进程不稳定
- **必须 `sort_keys=True`**——避免 dict key 顺序影响 json.dumps 输出
- 不用随机数 / 不让 LLM 自选
- N=5 个为上限，items 数 <5 时全取

### [RUBRIC]

#### evidence（证据可溯，权重 0.30）

**v2 修订 - M15**：阈值改为互斥区间 `<40% / 40-69% / 70-89% / ≥90%` source support rate。
**v3 修订 - cycle2/m6**：明确 support rate 与 mismatch rate 的优先级和分母。

```
评分依据（按优先级，从严到松）：

第 1 优先：support rate（有 source_refs 的论断 / 总论断数）
  4 分 优秀：≥90%
  3 分 良好：70-89%
  2 分 不及格：40-69%
  1 分 严重：<40%

第 2 优先（升级降级）：mismatch rate（mismatch 论断 / 有 source_refs 的论断）
  ≥30% mismatch → 强制降到 ≤2 分
  ≥50% mismatch → 强制降到 1 分

mismatch 包括：
  - URL 不在 discovered_sources（issue_type=url_not_discovered）
  - URL 在 list 内但 title/snippet 跟论断主题不符（issue_type=source_mismatch）
  - URL/snippet 都对但论断本身引错源（issue_type=source_irrelevant）

第三方源策略（v3 修订 - cycle2/M12）：
  按 claim 类型判断 source 合规性，不再硬编码黑名单：
  - 产品/定价/功能 claim：优先官方 URL；引用第三方时 mismatch 升级
  - 流量/排名/估算 claim：第三方数据（similarweb.com 等）合理；
    仅当未标注估算性质 / 来源时才扣分
  - 新闻 claim：权威媒体 OK；纯 SEO 聚合站（upmarket.co / spyingbee.com）扣分

⚠️ 不要硬记"哪些域名是聚合站"——按 claim 类型 + 来源权威性综合判断。
```

#### specificity（内容具体，权重 0.30）

```
4 分 优秀：每段平均 ≥2 个具体事实点（数字/日期/产品名/案例）
3 分 良好：每段平均 1 个具体事实点，部分段落偏抽象但可接受
2 分 不及格：≥50% 段落是空泛描述，缺乏具体支撑
1 分 严重：通篇套话（"具有较强竞争力" / "市场空间巨大"），无可验证事实

具体例（算 specificity）：
  "Mixpanel 在 2023-07 集成 OpenAI GPT 系列模型，是该品类首个支持
   自然语言查询的产品"
  含：日期 2023-07 + 模型类别 + 排名性事实

抽象例（不算）：
  "Mixpanel 持续创新，市场表现良好"
  "用户对 PostHog 的开源策略普遍认可"

⚠️ 反 self-preference 提醒：常识陈述（如 "PostHog 是开源工具"）
   不算具体事实——具体事实需带数字 / 日期 / 排名 / 案例引用之一。
```

#### coherence（内部一致，权重 0.20）

仅检查 limited_pairs 中给出的 3 个固定 pair（见 [INPUTS] 章节构造规则）。

```
基于"可用 pair 矛盾比例"评分（v3 修订 - cycle2/M6）：
  4 分 优秀：可用 pair 中 0% 有矛盾
  3 分 良好：可用 pair 中 ≤33% 有矛盾（如 3 中 1）
  2 分 不及格：可用 pair 中 34-66% 有矛盾（如 3 中 2）
  1 分 严重：可用 pair 中 >66% 有矛盾（如 3 中 3，或核心结论冲突）

⚠️ 不要做 limited_pairs 之外的全文级矛盾检查，那超出本 critic 范围。
⚠️ pair 标 skip_reason="missing" 时不参与评分，仅按剩余可用 pair 数计算比例。
⚠️ 如果可用 pair 数为 0（极端情况，所有 pair 都缺失）→ 跳过 coherence 维度，
   coherence_score=4 兜底（不作为约束信号），但 critic_failed 不触发。
```

#### actionability（可行动性，权重 0.20）

**v2 修订 - M16**：示例去掉具体过时模型名，改成模型无关。

```
4 分 优秀：每条 recommendation 含动词 + 时限 + 具体对象（产品/技术/工具）
3 分 良好：≥70% recommendation 含动词 + 时限 / 对象之一
2 分 不及格：≥50% recommendation 仅含动词无具体细节
1 分 严重：通篇 "加强 / 提升 / 优化" 这类无具体动作的建议

可行动例（4 分）：
  "在 2026Q3 前完成 X 模块的某能力升级，对标 Y 竞品的某产品功能，
   作为现有规则引擎的替代方案"
  含：时限 2026Q3 + 替代对象 + 现状参照 + 具体目标
   （注：示例避免引用具体模型名/版本号——critic 应判"是否可执行"
    而非"是否引用了某具体技术"）

不可行动例（1 分）：
  "建议加强 AI 能力" — 无动作 / 无时限 / 无对象
  "需要持续关注市场动态" — 关注不是动作

⚠️ 反"假可行动"：建议写得很具体但实际不可行（"建议收购 Notion"）
   也算 1 分——可行动 ≠ 仅含具体词，还要可执行（成本/合规/能力约束内）。
```

### [REASONING_STEPS]（v2 修订 - M9）

**关键**：reasoning 改成**结构化 bullet 数组**而非自由长 CoT，每条 bullet ≤80 字。
这平衡了"CoT 提升判断力"与"长 reasoning 跟 JSON 输出冲突"两个需求。

```
evidence_reasoning（list[str]，每条 ≤80 字）:
  "[Step 1] 列出需 source_refs 的条目类型与数量"
  "[Step 2] 统计有 source_refs 的占比 X%"
  "[Step 3] 抽查 sampled_findings 5 条，检查 URL 在 discovered_sources 内"
  "[Step 4] 判断 source title/snippet 跟论断主题相关性"
  "[Step 5] 综合给 1-4 分"

specificity_reasoning（list[str]，同上）:
  "[Step 1] 抽 sampled_narratives 5 段"
  "[Step 2] 逐段标记具体事实数 / 总句数"
  "[Step 3] 计算平均具体度"
  "[Step 4] 检查通用套话标志词（持续创新/市场空间巨大/用户认可度高）"
  "[Step 5] 综合给 1-4 分"

coherence_reasoning（list[str]，同上）:
  "[Step 1] 取 limited_pairs[0]，对照 data_a / data_b，是否矛盾"
  "[Step 2] 取 limited_pairs[1]，同上"
  "[Step 3] 取 limited_pairs[2]，同上"
  "[Step 4] skip 跳过 null pair"
  "[Step 5] 综合给 1-4 分"

actionability_reasoning（list[str]，同上）:
  "[Step 1] 抽 sampled_recommendations 5 条"
  "[Step 2] 逐条标记动词/时限/对象 3 要素"
  "[Step 3] 计算 3 要素齐全占比"
  "[Step 4] 检查假可行动陷阱"
  "[Step 5] 综合给 1-4 分"
```

### [OUTPUT_CONTRACT]

```json
{
  "evidence": {
    "reasoning": ["[Step 1] ...", "[Step 2] ...", ...],
    "score": 3,
    "issues": [
      {
        "field": "key_findings[2].source_refs[1]",
        "issue_type": "url_not_discovered",
        "reason": "<问题描述，≤200 字>",
        "suggestion": "<修改建议，≤200 字>"
      }
    ]
  },
  "specificity": { "reasoning": [...], "score": 2, "issues": [...] },
  "coherence":   { "reasoning": [...], "score": 4, "issues": [] },
  "actionability": { "reasoning": [...], "score": 3, "issues": [...] }
}
```

**v2 修订 - M4 / m5 / m6 / C8**：

`issue.issue_type` 枚举（v2 新增；v3 修订 - cycle2/M3 + cycle2/M11）：
- `url_not_discovered`：source_ref URL 不在 discovered_sources（agent → **collector**——因为是采集层缺失）
- `source_mismatch`：URL 在 list 内但 title/snippet 跟论断主题不符（agent → **collector**——因为采集 snippet 错或没抓全）
- `source_irrelevant`：URL 在 list 内、snippet 真实，但论断本身就引错了源（agent → **writer**——writer 选错引用）
- `vague_description`：内容空泛（agent → writer）
- `cross_field_contradiction`：跨字段矛盾（agent → writer）
- `vague_recommendation`：建议无具体动作（agent → writer）
- `critic_failed`：v3 新增 - critic 自身失败（agent → writer，让 writer 重写一次）

**v3 修订（cycle2/M11）**：v2 把 `source_mismatch` 全归 writer 太粗——mismatch 可能是 collector
错抓 snippet（应给 collector）也可能是 writer 引错源（应给 writer）。拆成 source_mismatch
（collector）+ source_irrelevant（writer）两类，让 LLM 在 prompt 里判断后输出正确类型。

代码层用 `_map_issue_type_to_agent` 字典做自动映射（不再依赖 LLM 直接打 agent）。

**reasoning 字段格式**：
- `list[str]` 而非单一长字符串
- 每条 bullet ≤80 字符
- 整 list ≤10 条
- 持久化时仅保留 list 不展开（防 metadata 体积爆炸）

**FeedbackIssue 完整映射表**（v2 修订 - M4）：

```python
FeedbackIssue(
    agent=<由 issue_type 映射，见上>,
    field=<LLM 输出>,
    severity=<由 _score_to_severity 计算，LLM 不直接打>,
    reason=<LLM 输出，≤200 字>,
    suggestion=<LLM 输出，≤200 字>,
    dimension=<critic 维度名，如 "evidence">,  # v2 新增字段
)
```

### [CONSTRAINTS]

```
1. 严格按 [OUTPUT_CONTRACT] JSON 输出，不要 markdown，不要解释开头
2. score 必须是 1/2/3/4 整数（不接受 2.5）
3. reasoning 应为 list[str]，每条建议 ≤80 个 Python `len()` 字符
   （v3 修订 cycle2/m5：明确按 Python `len()` 计数；prompt 层是 soft constraint）
4. issues 列表可空（如果该维度无问题）
5. 你是审计师，不要为报告写不足之处辩护
6. 不要做 limited_pairs 之外的全文级一致性检查
7. issue_type 必须从枚举中选（url_not_discovered / source_mismatch /
   source_irrelevant / vague_description / cross_field_contradiction /
   vague_recommendation）；critic_failed 仅由代码层在 fallback 时使用，LLM 不得输出
```

**v3 修订（cycle2/M8）**：reasoning 缺失策略
- 如果 LLM 返回的 dict 缺 reasoning 字段：代码层填空 list `[]` 而非 retry/fallback——
  reasoning 是辅助分析的 nice-to-have，缺它不算 critic 失败
- 如果 LLM 返回的 dict 缺 score 字段：retry 1 次仍缺则 fallback
- 这平衡了"reasoning 不持久化全文"目标 vs "缺 reasoning 不应炸"

## 数据流与时序

### 正常路径（critic 一次成功）

```
inspector.inspect(report)
  ↓
_programmatic_checks()  →  prog_issues
  ↓
_critic_check(report, discovered_urls)  ← 外层 broad try/except
  ├─ 1. _build_critic_inputs(report, discovered_urls) → user_prompt
  │     （拼装 report_brief + discovered_sources 含 title/snippet
  │       + limited_pairs + sampled_items）
  ├─ 2. _llm_call_with_quota(CRITIC_SYSTEM, user_prompt, max_tokens=8192)
  ├─ 3. 解析返回 dict，校验 4 维 score 都是 1-4 整数
  ├─ 4. CriticScores(evidence=N, specificity=N, coherence=N, actionability=N,
  │                  reasoning={dim: list[str]})
  ├─ 5. 4 维 issues → FeedbackIssue list（severity 由 _score_to_severity 算，
  │                                       agent 由 _map_issue_type_to_agent 算）
  └─ 返回 (critic_scores, critic_issues)
  ↓
合并 prog_issues + critic_issues，按 (agent, field, dimension) 三元组去重
  ↓
weighted_raw_score = 0.30*ev + 0.30*sp + 0.20*co + 0.20*ac        # 1-4 区间
quality_score = clamp((weighted_raw_score - 1) / 3, 0.0, 1.0)     # 归一化 [0, 1]
  ↓
report.metadata.quality_score = quality_score                     # ∈ [0, 1] 永远非空
report.metadata.score_source = "critic"
report.metadata.critic_scores = critic_scores
report.metadata.critic_prompt_version = CRITIC_PROMPT_VERSION     # 如 "critic-prompt-v1.0.0"
# v3 修订（cycle2/m2）：消除 "critic v{CRITIC_VERSION}" 的双 v 笔误
report.metadata.quality_score_calculation_note =
    f"{CRITIC_PROMPT_VERSION} | ev={ev} sp={sp} co={co} ac={ac} → raw={raw:.2f} → norm={quality_score:.3f}"
  ↓
RejectionFeedback(passed, issues, ...)
```

### 失败路径（critic LLM 出错）

**v3 修订 - cycle2/C3 + cycle2/M8**：fallback 路径自身做"无异常构造"，并在最外层
broad except 兜底——避免 fallback 内部还能抛错。

```
_critic_check(report, discovered_urls)
  ↓
[外层 broad try/except，覆盖所有非 LLM 异常 + fallback 自身可能的异常]
  ↓
正常调用：
 - _build_critic_inputs 失败（report 缺字段、limited_pairs 构造异常等）
 - report.model_dump() 异常
 - JSON 解析失败 / score 字段缺失 / score 越界
 - FeedbackIssue 构造失败
 - 任何 unexpected exception
  ↓
attempt 0: _llm_call_with_quota(max_tokens=8192) → 失败
  ├─ 检查 finish_reason
  ├─ 如果 finish_reason == "length" → 直接进入降级（不 retry，避免确定性失败重复）
  └─ 否则记 logger.warning("[critic] LLM 第 1 次失败：%s")
  ↓
attempt 1（仅当 finish_reason != "length" 时执行）:
  ├─ 成功 → 走正常路径
  └─ 失败 → 进入降级
  ↓
降级路径（v3 修订：内部做"无异常构造"——任何字段操作都先做 None safe）：
  ├─ critic_score (raw) = 2.5（中位数对应 1-4 区间）
  ├─ quality_score = clamp((2.5 - 1) / 3, 0.0, 1.0) = 0.5（中位数）
  ├─ critic_scores = None
  ├─ score_source = "fallback"
  ├─ critic_prompt_version = None
  ├─ # v3 修订（cycle2/C3）：先做 None safe 转换，避免 metadata.warnings is None 时 .append 崩
  ├─ existing_warnings = list(report.metadata.warnings or [])
  ├─ existing_warnings.append(f"critic_failed:{error_code}")
  ├─ report.metadata.warnings = existing_warnings
  │     # error_code 枚举: llm_timeout / json_parse_error / score_out_of_range /
  │     #                  field_missing / max_tokens_length / build_inputs_error /
  │     #                  unexpected_error
  ├─ 强制生成 1 条 FeedbackIssue（v3 修订 - cycle2/C1）：
  │     # builder.py:436 用 issue.agent 直接路由 graph 节点
  │     # graph 节点只有 recommender/collector/analyzer/writer/inspector
  │     # 用 agent="inspector" 会形成循环 → 必须用现有合法 retry target
  │     FeedbackIssue(
  │         agent="writer",  # critic 失败语义上是"质量未确认"，让 writer 重写一次
  │         field="critic_check",
  │         severity="major",  # 强制 major，让 passed=False 触发反馈
  │         reason=f"critic 评分失败：{error_code}",
  │         suggestion="人工 review 或重跑分析；如重试仍 critic 失败则 max_retries 终止",
  │         dimension="critic_failed",
  │         issue_type="critic_failed",  # cycle2/M3：枚举里加这条
  │     )
  └─ logger.error("[critic] LLM 失败重试后仍失败，降级 score_source=fallback")
```

### Severity 映射规则（D' 阈值，v2 修订 - M2）

```python
def _score_to_severity(dim_score: int, all_scores: dict[str, int]) -> str:
    """D' 阈值规则：维度分主导 + 聚合分升级。

    输入：
      dim_score: 当前维度分（1-4 整数）
      all_scores: 4 维全分数 dict（{evidence: N, specificity: N, ...}）
    返回：
      "critical" / "major" / "minor"

    规则（按优先级）：
      1. dim_score == 1 → critical（单维度灾难）
      2. dim_score == 2 → major（维度不及格）
      3. dim_score == 3 → 看聚合分：
         - 聚合分（quality_score）< 0.50 → major
         - 否则 → minor
      4. dim_score == 4 → minor（理论上不该生成 issue，但兼容）
    """
    if dim_score <= 1:
        return "critical"
    if dim_score == 2:
        return "major"
    # v3 修订（cycle2/M1）：显式处理 dim_score >= 4 case，避免 fall-through 误升级 major
    if dim_score >= 4:
        return "minor"
    # dim_score == 3
    raw = sum(W[k] * v for k, v in all_scores.items())  # weighted raw 1-4
    quality_score = max(0.0, min(1.0, (raw - 1) / 3))
    if quality_score < 0.50:
        return "major"
    return "minor"
```

**对照 v1 D 规则的差异**：v1 是"单维度 ≤1 critical / 否则全看聚合"，v2 升级为"单维度 ≤2 至少 major"——防 evidence=2 + 其他=4 时 evidence issue 被错标 minor。

## Schema 改动

### 新增 CriticScores

```python
# src/schemas/feedback.py 末尾追加
# 注意：feedback.py 不 import report.py，避免循环依赖

class CriticScores(BaseModel):
    """critic 4 维评分（持久化到 ReportMetadata.critic_scores）

    每维 1-4 整数分；reasoning 是结构化 bullet list（v2-M9 修订）。
    """
    evidence: int = Field(ge=1, le=4)
    specificity: int = Field(ge=1, le=4)
    coherence: int = Field(ge=1, le=4)
    actionability: int = Field(ge=1, le=4)
    reasoning: dict[str, list[str]] = Field(default_factory=dict)
    """{dim: [bullet1, bullet2, ...]}，CoT 推理过程（短 bullet，每条 ≤80 字）"""
```

### FeedbackIssue 扩展（v2 - M3 + m5）

```python
# src/schemas/feedback.py 修改 FeedbackIssue

class FeedbackIssue(BaseModel):
    agent: str  # "writer" / "collector" / "inspector"，由 issue_type 映射
    field: str
    severity: Literal["critical", "major", "minor"]
    reason: str
    suggestion: str
    # v2 新增字段（所有 Optional 兼容旧 issue 反序列化）
    dimension: Optional[str] = None
    """critic 维度名（"evidence"/"specificity"/...）或 "programmatic" / "critic_failed"
    用于去重 + 反馈路由"""
    issue_type: Optional[str] = None
    """枚举: url_not_discovered / source_mismatch / vague_description /
    cross_field_contradiction / vague_recommendation / programmatic_*"""
```

### ReportMetadata 扩展

```python
# src/schemas/report.py ReportMetadata 类追加（所有字段 Optional 兼容旧 trace）

class ReportMetadata(BaseModel):
    # ...现有字段...
    critic_scores: Optional[CriticScores] = None
    """critic 4 维评分；critic 失败降级时为 None"""
    # v3 修订（cycle2/C2）：必须 Optional 默认 None，否则旧 trace 反序列化时
    # 会被错填 "critic"，污染 provenance 语义
    score_source: Optional[Literal["critic", "fallback"]] = None
    """quality_score 的来源；"critic"=critic 真分；"fallback"=critic 失败降级 0.5；
    None=旧 v1 trace（来自旧 coverage/confidence/pass_rate 三项加权）"""
    critic_prompt_version: Optional[str] = None
    """critic prompt 版本（如 "critic-prompt-v1.0.0"），用于历史分数可比；
    v3 修订（cycle2/m1）：字段名改 critic_prompt_version 跟 spec 版本号区分"""
```

### Schema 兼容验收（v2 - C1 + M11）

**两条独立验收**（不混淆）：

1. **旧 trace 反序列化测试**：
   - fixture：`runs/20260618-095358-c5ab5c/03_report.json`（v1 schema 落盘的报告）
   - 测试：`BaseReport.model_validate_json(<fixture content>)` 不抛异常
   - 期望：所有 v2 新增字段填默认值（critic_scores=None, score_source="critic", critic_version=None）

2. **critic 失败降级测试**（独立的 v2 行为验证）：
   - fixture：v2 schema 的 BaseReport
   - mock critic LLM 抛异常
   - 期望：inspect() 不抛异常 / metadata.score_source="fallback" / critic_failed major issue 生成

## 测试设计（v2 修订 - C6 + M12）

### 第 1 层：单元测试（机制正确性，CI required）

`tests/unit/test_inspector_critic.py` —— 全部用 mock LLM，CI 必跑。

| 测试 | 场景 |
|------|------|
| `test_critic_check_normal_path` | mock LLM 返回合规 dict → 校验 critic_scores + issues 生成 |
| `test_critic_check_score_to_severity_d_prime_dim_le1_critical` | dim=1 → critical |
| `test_critic_check_score_to_severity_d_prime_dim_eq2_major` | dim=2 → major（v2 升级关键测试）|
| `test_critic_check_score_to_severity_d_prime_dim_eq3_low_agg_major` | dim=3 + quality_score<0.5 → major |
| `test_critic_check_score_to_severity_d_prime_dim_eq3_high_agg_minor` | dim=3 + quality_score≥0.5 → minor |
| `test_critic_check_score_out_of_range_retries` | LLM 返回 score=5 → retry 1 次 |
| `test_critic_check_missing_dimension_retries` | LLM 返回缺 `evidence.score` 或缺 `evidence` 整对象 → retry 1 次（v3 修订 cycle2/m3：字段名跟 OUTPUT_CONTRACT 对齐） |
| `test_critic_check_finish_reason_length_no_retry` | finish_reason=length → 不 retry，直接 fallback |
| `test_critic_check_retry_then_fallback` | retry 仍失败 → critic_score=0.5 + critic_failed major issue |
| `test_critic_check_build_inputs_failure_falls_back` | _build_critic_inputs 抛异常 → fallback |
| `test_critic_check_calc_critic_score_accepts_model_or_dict` | calc_critic_score(CriticScores 实例) 和 calc_critic_score(dict) 都通（C5 修复）|
| `test_critic_check_quality_score_clamped` | weighted_raw_score 异常时 quality_score 仍 ∈ [0, 1] |
| `test_limited_pairs_builder_deterministic` | `_build_limited_pairs(report)` 同 report 多次调用结果一致 |
| `test_limited_pairs_missing_field_skipped` | report 缺 swot 时对应 pair 标 skip_reason="missing" |
| `test_sample_items_deterministic` | `_sample_items_deterministic` 同 items 多次调用结果一致 |

### 第 2 层：集成测试（端到端，CI required）

`tests/unit/test_inspector_critic.py` 末尾追加，全部 mock LLM。

| 测试 | 场景 |
|------|------|
| `test_inspect_with_critic_replaces_quality_score` | 完整 BaseReport fixture → 跑 inspect → quality_score = critic_score 归一化值 |
| `test_inspect_v3_r17_cap_removed` | placeholder warnings 存在但 critic_score=0.6 → quality_score 仍是 0.6 |
| `test_inspect_critic_failure_warnings` | mock critic 失败 → metadata.warnings 含 "critic_failed:<code>" + score_source="fallback" |
| `test_inspect_v1_trace_backward_compat` | 旧 trace fixture（runs/20260618-095358-c5ab5c/03_report.json）能反序列化 |
| `test_inspect_v1_trace_inspect_runs` | 旧 trace fixture 能跑 inspect 不崩（critic 给打分）|
| `test_inspect_passed_blocks_on_critic_failure` | critic 失败 → critic_failed major issue → passed=False（C3 关键回归保护）|
| `test_dedup_keeps_cross_dimension_issues` | 同 field 不同 dimension 的 issue 不被去重（M3）|

### 第 3 层：Prompt Snapshot Eval（手动，非 CI）

**v2 修订（C6）**：拆出"测 critic 真实判断力"的部分，定位为**手动 eval**，不进 CI。

`tests/eval/test_critic_judgment.py` —— 用 `pytest -m eval` 标记，CI 默认跳过。

| 反例集 fixture（手工构造） | 期望 critic 输出 | 测试方式 |
|---------------------------|------------------|---------|
| `report_all_placeholder` 全章节 placeholder | specificity ≤ 2 | 真 LLM 调用，每次重测（手动跑）|
| `report_no_source_refs` 所有 finding 无 source_refs | evidence ≤ 1 | 同上 |
| `report_third_party_only` 全引用聚合站 | evidence ≤ 2 | 同上 |
| `report_swot_self_contradiction` SWOT 矛盾 | coherence ≤ 2 | 同上 |
| `report_vague_recommendations` 全套话建议 | actionability ≤ 1 | 同上 |

**触发方式**：`pytest tests/eval/ -m eval`（手动）；CI 跑 `pytest -m "not eval"`。

**为什么不进 CI**：
- 真 LLM 调用慢且不稳定
- record/replay 录像锁死了 critic 行为，rubric 升级时录像失效但测试仍绿（C6 痛点）
- 这层测试是**人类对 critic 判断力的抽查**，应该手动跑、手动看 reasoning bullet

**rubric 调整后的流程**：手动跑 eval → 看每条 fixture 的 critic 输出是否合理 → 不合理则调 prompt → 再跑。

## 关键设计权衡

### 权衡 1：reasoning 改结构化短 bullet（v2 修订 - C8 + M9）

v1 是自由长 CoT；v2 改 `list[str]`，每条 ≤80 字、整 list ≤10 条。

理由：
- 长自由 CoT 跟严格 JSON 输出冲突（M9，实证 OPEN_QUESTIONS Q-2026-06-17-llm-长输出鲁棒性）
- 持久化全 CoT 文本到 metadata.critic_scores.reasoning 会让 trace 体积爆炸（C8）
- 短 bullet 仍保留 CoT 的"分步推理"价值，但裁剪到工程可接受范围

### 权衡 2：severity 由代码映射（v2 升级 D'）

LLM 不直接打 severity，由 `_score_to_severity(dim_score, all_scores)` 算。
v2 升级（M2）：dim ≤2 至少 major，不再仅靠聚合分映射，防维度信号被抹平。

### 权衡 3：抽查 5 条（v2 deterministic 化 - M7）

整报告 ~25000 字超过 critic 输入预算。`_sample_items_deterministic` deterministic 抽样：
- 按 item.id 或 hash 排序后取前 N
- 同 report 多次调用结果一致
- 测试可重复

### 权衡 4：v3-R17 cap 完全删除

critic 已天然惩罚 placeholder（specificity 1/4 → 强制 critical），cap 0.5 是冗余。删除让 quality_score 信号更纯净。

### 权衡 5：critic 失败降级 0.5 + 强制 major issue（v2 升级 - C3）

v1 仅设 critic_score=0.5；v2 加：
- critic_failed major issue 强制生成 → passed=False → 反馈闭环触发
- score_source="fallback" 字段标记 → 系统监控可识别"伪 0.5"

防止 critic 长期故障时所有报告伪通过（M10）。

### 权衡 6：reasoning 不持久化全文，仅 bullet list（v2 - C8）

避免：
- metadata 体积爆炸
- 敏感信息泄露
- 模型不返回 CoT 时 schema 失败

bullet list ≤10 条 × 80 字 ≈ 800 字符上限/维 × 4 维 = ≤3.2KB 单报告，可接受。

## 与 OPEN_QUESTIONS 的关联

本 spec 实施后，以下 OPEN_QUESTIONS 状态变化：

| Q | 状态变化 |
|---|---------|
| Q-2026-06-17-字数约束的代理失效 | **设计中**（critic 是退役字数约束的前提）|
| Q-2026-06-18-inspector-llm-issue-丢失 | 部分缓解（critic 内部 retry + 降级 + 强制 major issue）|
| Q-2026-06-17-llm-长输出鲁棒性 | 间接缓解（reasoning 短 bullet 设计 + length 不 retry）|

不解决：
- Q-2026-06-17-phase3-不重试占位 — 跟 critic 无关，writer 阶段问题
- Q-2026-06-17-collector-抽取全或无 — 同上
- Q-2026-06-18-narrative-偶发抖动 — 同上
- Q-2026-06-18-llm-反馈修一退一 — 反而可能加重（critic 多生成一些 issue）
- Q-2026-06-18-json-extra-data — 通用 LLM 输出问题，不在本 spec 范围

## 字数约束渐进退役（后续阶段）

**附录性质**：本 spec **仅落地 critic 本身**，字数约束删除留给后续 spec。**本 PR 严禁修改任何 schema 字段的 min_length / max_length 约束**（m2 修订）。

预定路径（参考，OPEN_QUESTIONS Q-2026-06-17-字数约束 已写）：

```
阶段 1（本 spec）：critic 设计 + 落地
                    ↓
阶段 2：跑 2-3 次端到端，校准 critic 准确度（手动 eval）
                    ↓
阶段 3：分批退役 schema 字数下限约束（先 ≥10 / ≥20 小约束）
                    ↓
阶段 4：退役 ≥50 / ≥100 大约束（字数 ValidationError 高发区）
                    ↓
阶段 5：保留上限约束（≤200）+ 结构约束（必填 / 数量 / 枚举），永久不动
```

阶段 3-5 不在本 spec 实施范围。

## 不在本 spec 范围

- 字数约束实际删除（留给后续 spec，**本 PR 严禁动 schema min_length**）
- 现有 phase 1/2/3 的 max_tokens 调参（等 finish_reason 证据积累）；
  **本 PR 仅新增 critic 调用 max_tokens=8192 这一项**——是新建 LLM 调用，不是调参
  （v3 修订 cycle2/M9：消除"调参"声明跟新调用 max_tokens 的语义冲突）
- inspector LLM 调用之外的其他 critic 应用场景（如 writer phase 内嵌 critic）
- 多 critic 投票 / 跨模型 critic（成本高，单一 LLM 够用阶段不需要）
- critic 自身的训练或 fine-tuning（在线 prompt 工程已经够）
- 前端展示 critic_scores 的 UI 改动（schema 写入即可，render 模块改动留给后续）

## 验收标准

实施完成后必须满足。**v3 修订（cycle2/M10）拆两类**：

#### CI required（PR 合并门禁）

1. **CI 测试全绿**：单元 + 集成 `pytest -m "not eval"` 全绿（mock LLM，不依赖外部 API）
2. **lint 通过**：`ruff check src tests` 全清（v3 修订 cycle2/m8：用 `ruff check` 不是 `ruff clean`）
3. **旧 trace 反序列化**：`runs/20260618-095358-c5ab5c/03_report.json` 能用 v3 BaseReport schema 加载，且加载后 `score_source=None / critic_scores=None / critic_prompt_version=None`（独立验收）
4. **critic 失败降级**：mock critic 异常 → inspect 不抛 / score_source="fallback" / critic_failed major issue 生成 / passed=False（独立验收）
5. **新报告产出**：metadata 含 `critic_scores` + `score_source` + `critic_prompt_version` 字段（fallback 路径含 critic_scores=None / score_source="fallback"）
6. **quality_score 永远非空且 ∈ [0, 1]**：所有路径（成功 / fallback / 异常）下 metadata.quality_score 都被写入，clamp 保证范围
7. **本 PR 范围控制**：diff 中无任何 schema `min_length` / `max_length` 字段的修改（手动 git grep 验证）
8. **影响面回归**（v3 新增 cycle2/C4）：`grep -r "calc_source_coverage\|calc_confidence_avg\|calc_inspector_pass_rate\|_QUALITY_SCORE_CAP_ON_PLACEHOLDER\|_detect_placeholder_warnings\|_check_warnings_prefix" src/ tests/` 必须无遗留引用（写入 verify 脚本进 CI）

#### Manual pre-release（不进 CI，记录到 PROGRESS）

9. **手动 critic eval**：跑 `pytest tests/eval/ -m eval` 至少 1 次，确认 5 条反例集 fixture 期望符合
10. **手动 S5 真跑**：至少 1 次端到端，人工对比 critic 4 维评分 + reasoning bullets vs 直觉是否大致符合

## v3 修订日志

v2 经 Codex cycle 2 跨模型审查（2026-06-19）发现 22 条问题，处理如下：

**Critical 4 条（全部消化）**：
- cycle2/C1 → fallback issue agent 改 "writer"（不破坏 builder.py 反馈路由）+ M3 issue_type 加 critic_failed
- cycle2/C2 → score_source 改 Optional[Literal[...]]=None，旧 trace 期望 None 不污染语义
- cycle2/C3 → fallback 路径自身 None safe + 内部失败兜底
- cycle2/C4 → 验收 8 加影响面 grep 检查（旧三项无遗留引用）

**Major 12 条（11 必修 + 1 文档化）**：
- cycle2/M1 → `_score_to_severity` 显式加 `if dim_score >= 4: return "minor"` 防 fall-through
- cycle2/M2 → passed 判定改 `not any(severity in {critical, major})` 显式语义
- cycle2/M3 → issue_type 枚举加 `critic_failed`
- cycle2/M4 → discovered_urls 升级为 discovered_sources（含 title/snippet）+ 上游 collector/state/builder 改动清单
- cycle2/M5 → score_vs_warnings 伪 pair 替换为 exec_summary_vs_recommendations
- cycle2/M6 → coherence 缺 pair 时按比例评分规则 + 0 可用 pair 兜底 score=4
- cycle2/M7 → 抽样改用 sha256 + sort_keys=True，禁用 Python 内建 hash()
- cycle2/M8 → reasoning 缺失 → 代码填空 list 不 fallback；score 缺失才 fallback
- cycle2/M9 → "本 PR 仅新增 critic 调用 max_tokens=8192"声明，消除调参矛盾
- cycle2/M10 → 验收拆 CI required (1-8) vs Manual pre-release (9-10)
- cycle2/M11 → source_mismatch 拆 source_mismatch (collector) + source_irrelevant (writer)
- cycle2/M12 → evidence rubric 第三方源策略改"按 claim 类型"，不再硬编码黑名单

**Minor 6 条（5 必修 + 1 noise）**：
- cycle2/m1 → critic_version 改名 critic_prompt_version 跟 spec 版本号区分
- cycle2/m2 → quality_score_calculation_note 双 v 笔误修
- cycle2/m3 → 测试字段名 evidence.score 跟 OUTPUT_CONTRACT 对齐
- cycle2/m4 → calc_critic_score 签名 Mapping[str, Any] + 仅读 4 个维度 key
- cycle2/m5 → "≤80 字符" 明确按 Python `len()` 计数
- cycle2/m6 → mismatch rate 优先级 + 分母明确（mismatch / 有 source_refs 的论断）

## v2 修订日志

v1 经 Codex 跨模型 doubt-driven 审查（2026-06-19）发现 33 条问题，处理如下：

**Critical 8 条（全部消化）**：
- C1 → Schema 兼容章节（import 方向 + 旧 trace 反序列化测试）
- C2 → 失败路径外层 broad except + 列出非 LLM 失败点
- C3 → critic_failed 强制生成 major issue
- C4 → quality_score 永远非空 clamp 保证 + 旧 trace 反序列化独立验收
- C5 → calc_critic_score 签名统一 `CriticScores | Mapping[str, int]`
- C6 → 反例集拆双层（CI fake stub + 手动 eval）
- C7 → 决策表加 Q# 列 + (派生) 标记
- C8 → reasoning 改 list[str] 短 bullet + 持久化裁剪

**Major 16 条（13 必修 + 3 文档化）**：
- M1 → 拆 weighted_raw_score (1-4) vs quality_score (0-1) + clamp
- M2 → D' 阈值升级（dim ≤2 至少 major）
- M3 → 去重 key 加 dimension
- M4 → FeedbackIssue 完整映射表
- M5 → limited_pairs deterministic builder + 缺字段 skip 协议
- M6 → 输入侧加 source title + snippet
- M7 → deterministic 抽样规则
- M8 → length 错不 retry
- M9 → reasoning 改结构化 bullet
- M10 → score_source 字段
- M11 → 拆两个独立验收
- M12 → 反例集明确手动 eval 不进 CI
- M13 → 删 _llm_check 影响面已搜索（无外部调用）
- M14 → 弱化为"工程经验"措辞，不引用具体论文数据
- M15 → evidence 阈值改互斥区间
- M16 → actionability 示例去具体模型名

**Minor 10 条（6 必修 + 3 文档化 + 1 重复）**：
- m1（与 C7 重复）
- m2 → "本 PR 严禁动 schema" 加进范围控制 + 验收 6
- m3 → warning 格式统一 `critic_failed:<code>`
- m4 → quality_score_calculation_note 字段已确认存在（report.py:132）
- m5 → issue_type 枚举区分 url_not_discovered vs source_mismatch
- m6 → issue.agent 由 issue_type 映射
- m7 → 第三方域名注释为可配置，prompt 中保留示例
- m8 → 修正为 `ruff check`
- m9 → 加失败 trace 到维度的映射表（"维度选择实证基础"章节）
- m10 → 加 `critic_version` 字段
