# LLM-as-Critic 评分系统设计

> 落实 OPEN_QUESTIONS Q-2026-06-17-字数约束的代理失效 的核心修法。
> 不再用字数 schema 代理"内容质量"，改用语义级 LLM critic 给报告打分。
> Brainstorming 8 个问题已逐一拍板（见各章节 ✅ 标记）。

## 背景

PentaScope 当前 inspector 的 quality_score 三项加权（source_coverage / confidence_avg / inspector_pass_rate）实证存在三类问题：

1. **confidence_avg 是假动态** — `writer_orchestrator.py:1375` 全部 DataSource.confidence 写死为 "medium"，导致历史所有 trace 的 confidence_avg ≡ 0.6
2. **source_coverage 只测有无 source，不测相关性** — 引用错位的报告（如 `runs/20260617-181916-91bc54` 中 PostHog finding 引 OpenAI 事故公告）coverage 仍然高
3. **inspector_pass_rate 是 issue 数倒推** — 跟 critic 维度分会重复计算

更上游的根因（OPEN_QUESTIONS Q-2026-06-17-字数约束）：schema 字段大量 ≥N 字符约束作为"反空话"代理，LLM 字符层面执行差，已经造成多次重试浪费和"长但空"的报告产出。

本设计用 **LLM-as-critic 语义评分**替换三项加权，作为"字数约束分阶段退役"路径的前置基础设施。

## 核心决策（已固化）

| # | 决策项 | 选择 | 理由摘要 |
|---|--------|------|---------|
| 1 | 架构 | 路线 A — critic 是 inspector 内部子模块 | 不新增 graph 节点，反馈闭环复用现有 |
| 2 | 维度 | evidence + specificity + coherence + actionability（4 维） | Cooper 痛感排序 C/A/D 三维 + 决策时加回 actionability |
| 3 | 权重 | 0.30 / 0.30 / 0.20 / 0.20 | 重证据 + 具体；coherence/actionability 同权 |
| 4 | quality_score 计算 | critic_score 完全替换 coverage + confidence + pass_rate | 三项有 bug 或冗余，纯净化信号 |
| 5 | 集成顺序 | C — critic 内嵌一次 LLM 调用同时输出 rubric + issues | 省一次 LLM 调用，quota 友好 |
| 6 | Coherence 范围 | 限定 pair 比对（3 个固定 pair） | 全文级 LLM 注意力不擅长 |
| 7 | 失败降级 | B+C — retry 1 次，仍失败 critic_score=0.5 + warnings | 救偶发抖动，不让 critic 失败 = 报告 0 分 |
| 8 | 阈值规则 | D — 均值映射 severity + 单维度 ≤1 强制 critical | 防"3 维优秀掩盖 1 维灾难" |
| 9 | CoT 策略 | B — 全维度带 CoT | 学界数据 +20% 一致性 |
| 10 | 评分粒度 | A — 整报告级单次评分 | 章节级会爆 quota 上限 |
| 11 | 测试策略 | Y — 单元 + 集成 + 反例集（record/replay） | 反例集守住底线，不依赖人工标注 |
| 12 | v3-R17 cap 0.5 | 完全删除 | critic 已天然惩罚 placeholder |
| 13 | max_tokens | critic 调用 8192 | CoT 输出长，4096 不够 |

## 架构设计

### Inspector v4 流程

```
inspect(report):
  Step 1: _programmatic_checks()
    - _check_common(report)       # schema 之外的硬查
    - _dispatch_scenario_check    # _check_s1..s5
    （删除 _check_warnings_prefix——v3-R17 cap 一并删）

  Step 2: _critic_check(report, discovered_urls)
    - 调用 LLM 一次（system=CRITIC_PROMPT, max_tokens=8192）
    - LLM 失败时 retry 1 次
    - 仍失败 → critic_score=0.5 + warnings.append("critic_failed")
    - 成功 → 返回 (CriticScores, list[FeedbackIssue])

  Step 3: 合并 issues
    - prog_issues + critic_issues
    - 按 (agent, field) 去重保留最严重

  Step 4: quality_score 计算
    - quality_score = critic_score
    - 不再走 calc_quality_score 三项加权

  Step 5: passed 判定
    - passed = all(issue.severity == "minor")
    - 现有判定逻辑不变
```

### 组件清单

#### 删除的组件

| 文件 | 组件 | 理由 |
|------|------|------|
| `src/agents/quality_score.py` | `calc_source_coverage` | 跟 critic.evidence 重叠，细粒度替粗粒度 |
| `src/agents/quality_score.py` | `calc_confidence_avg` | 假动态恒等于 0.6 |
| `src/agents/quality_score.py` | `calc_inspector_pass_rate` | 跟 critic.threshold 映射重叠 |
| `src/agents/quality_score.py` | 旧 `calc_quality_score` 三项加权 | 整体替换为新 critic_score 函数 |
| `src/agents/inspector.py` | `_QUALITY_SCORE_CAP_ON_PLACEHOLDER` | v3-R17 废弃 |
| `src/agents/inspector.py` | `_detect_placeholder_warnings` | cap 删了它就没用 |
| `src/agents/inspector.py` | `_check_warnings_prefix` | 同上 |
| `src/agents/inspector.py` | `_llm_check` | 重写为 `_critic_check`，输出格式从 issue list 改为 rubric + issues |
| `src/agents/prompts/__init__.py` | `INSPECTOR_SYSTEM` | critic prompt 移到独立文件 `prompts/inspector/critic.py` |

#### 新增的组件

| 文件 | 组件 | 职责 |
|------|------|------|
| `src/agents/inspector.py` | `_critic_check(report, discovered_urls)` | 调 critic LLM，4 维 CoT 评分，含 retry + 降级 |
| `src/agents/inspector.py` | `_score_to_severity(score, dim, agg_score)` | D 阈值规则：score → minor/major/critical 映射 |
| `src/agents/quality_score.py` | `calc_critic_score(critic_scores)` | 4 维加权 0.30/0.30/0.20/0.20 |
| `src/agents/prompts/inspector/__init__.py` | 模块包 | 新建 inspector prompts 包 |
| `src/agents/prompts/inspector/critic.py` | `CRITIC_SYSTEM` | critic 4 维 CoT rubric prompt |
| `src/schemas/feedback.py` | `CriticScores`（新 BaseModel） | 持久化 4 维分到 metadata |
| `src/schemas/report.py` | `ReportMetadata.critic_scores: Optional[CriticScores]` | metadata 字段扩展供前端展示 |

## Critic Prompt 详细设计

### 整体结构

```
[ROLE]               资深咨询审计师（反 self-preference）
[TASK]               4 维 rubric 评分
[INPUTS]             report dict + discovered_urls + limited_pairs
[RUBRIC]             每维 1-4 分锚点 + 正反例
[REASONING_STEPS]    每维 CoT 推理步骤
[OUTPUT_CONTRACT]    JSON 输出格式
[CONSTRAINTS]        硬约束
```

### [ROLE]

```
你是一位资深的咨询报告审计师，专业是质量稽核而非内容创作。你的职责
是按 4 个维度对一份竞品分析报告做 rubric 评分，并指出具体问题。

你不是作者。你不为报告辩护，也不脑补缺失内容。你只评判呈现给你的
内容。
```

**设计意图**：用"审计师"角色压制 LLM 的 self-preference bias（学界发现 LLM 当 author 时倾向给自己的输出打高分；当 auditor 时打分更客观）。

### [RUBRIC]

#### evidence（证据可溯，权重 0.30）

```
4 分 优秀：≥90% 论断有合规 source_refs，URL 在 discovered_urls 内，
        引用内容跟论断主题相关
3 分 良好：≥70% 论断有合规 source_refs，少数轻微 mismatch
2 分 不及格：≥40% 论断有 source_refs，但出现明显 mismatch
        （如 "PostHog 月活高" 引用 "OpenAI 事故公告"）
1 分 严重：≥30% 论断无任何 source 支撑，或大量第三方聚合站当主要证据
        （upmarket.co / spyingbee.com 这类）

例（4 分）："PostHog 在 2024-Q4 推出 launch week"，引用
         posthog.com/blog/launch-week-2024 ✓
例（2 分）："PostHog 开源策略形成壁垒"，引用 PostHog 通用更新博客
         （不直接支撑"开源壁垒"论点）
例（1 分）："Mixpanel 月活 200 万"，无任何 source_ref
```

#### specificity（内容具体，权重 0.30）

```
4 分 优秀：每段平均 ≥2 个具体事实点（数字/日期/产品名/案例）
3 分 良好：每段平均 1 个具体事实点，部分段落偏抽象但可接受
2 分 不及格：≥50% 段落是空泛描述，缺乏具体支撑
1 分 严重：通篇套话（"具有较强竞争力" / "市场空间巨大"），无可验证事实

具体例（算 specificity）：
  "Mixpanel 在 2023-07 集成 GPT-3.5 Turbo，是该品类首个支持
   自然语言查询的产品"
  含：日期 2023-07 + 模型名 GPT-3.5 + 排名性事实

抽象例（不算）：
  "Mixpanel 持续创新，市场表现良好"
  "用户对 PostHog 的开源策略普遍认可"

⚠️ 反 self-preference 提醒：常识陈述（如 "PostHog 是开源工具"）
   不算具体事实——具体事实需带数字 / 日期 / 排名 / 案例引用之一。
```

#### coherence（内部一致，权重 0.20）

```
仅检查 limited_pairs 中给出的固定 3 个 pair：
1. swot.strengths 中提及 X 公司 vs vendor_profiles[X].cautions
   （同一竞品的强弱说法是否对接）
2. key_findings vs recommendations
   （发现 → 行动是否对接）
3. metadata.quality_score vs warnings 数量
   （自洽性：高分但多 warning 是矛盾）

4 分 优秀：3 个 pair 均无矛盾
3 分 良好：1 个 pair 有轻微矛盾（用词差异 / 维度切换）
2 分 不及格：2-3 个 pair 有明显矛盾
1 分 严重：核心结论之间冲突（如 SWOT.strengths 说 X 强 + cautions
       说 X 弱，针对同一竞品同一维度）

⚠️ 不要做 limited_pairs 之外的全文级矛盾检查，那超出本 critic 范围。
```

#### actionability（可行动性，权重 0.20）

```
4 分 优秀：每条 recommendation 含动词 + 时限 + 具体对象 / 模型 / 工具
3 分 良好：≥70% recommendation 含动词 + 时限 / 对象之一
2 分 不及格：≥50% recommendation 仅含动词无具体细节
1 分 严重：通篇 "加强 / 提升 / 优化" 这类无具体动作的建议

可行动例（4 分）：
  "在 2026Q3 前接入 Mixpanel-style 自然语言查询，用 GPT-3.5 Turbo
   替代规则引擎"
  含：时限 2026Q3 + 替代对象 GPT-3.5 + 现状参照"规则引擎"

不可行动例（1 分）：
  "建议加强 AI 能力" — 无动作 / 无时限 / 无对象
  "需要持续关注市场动态" — 关注不是动作

⚠️ 反"假可行动"：建议写得很具体但实际不可行（"建议收购 Notion"）
   也算 1 分——可行动 ≠ 仅含具体词，还要可执行。
```

### [REASONING_STEPS]

每维都按这个模板推理，再给分。

```
evidence_reasoning_steps:
  Step 1: 列出报告中需要 source_refs 的条目类型与数量
          （key_findings + analysis_sections + recommendations + swot 4 类）
  Step 2: 统计每类有 source_refs 的占比
  Step 3: 抽查 5 条带 source_refs 的论断，判断 URL 是否在 discovered_urls 内
  Step 4: 抽查 5 条 source_refs 内容是否跟论断相关
  Step 5: 综合给 1-4 分

specificity_reasoning_steps:
  Step 1: 列出报告中所有 narrative 段落（analysis_sections + executive_summary）
  Step 2: 抽 5 段，逐段标记"具体事实数 / 总句数"
  Step 3: 计算平均具体度
  Step 4: 判断是否含通用套话标志词（"持续创新" / "市场空间巨大" / "用户认可度高"）
  Step 5: 综合给 1-4 分

coherence_reasoning_steps:
  Step 1: 取 limited_pairs[0]，找出双方对应数据，判断有无矛盾
  Step 2: 取 limited_pairs[1]，同上
  Step 3: 取 limited_pairs[2]，同上
  Step 4: 综合 3 个 pair 的矛盾数 → 1-4 分

actionability_reasoning_steps:
  Step 1: 列出所有 recommendation 条目
  Step 2: 逐条标记"含动词? 含时限? 含具体对象?"
  Step 3: 计算"3 要素齐全"的占比
  Step 4: 检查是否含"假可行动"陷阱（具体词但不可执行）
  Step 5: 综合给 1-4 分
```

### [OUTPUT_CONTRACT]

```json
{
  "evidence": {
    "reasoning": "<推理过程，~200-400 字>",
    "score": 3,
    "issues": [
      {
        "field": "key_findings[2].source_refs[1]",
        "reason": "<问题描述>",
        "suggestion": "<修改建议>"
      }
    ]
  },
  "specificity": {
    "reasoning": "<同上>",
    "score": 2,
    "issues": [...]
  },
  "coherence": {
    "reasoning": "<同上，重点说 3 个 pair 各自情况>",
    "score": 4,
    "issues": []
  },
  "actionability": {
    "reasoning": "<同上>",
    "score": 3,
    "issues": [...]
  }
}
```

注意：
- `score` 字段必须是 1/2/3/4 整数，不接受 2.5 这种小数
- `issues[].severity` 由代码层根据 score + D 阈值规则**自动映射**，LLM 不直接打 severity（避免它瞎标）
- `issues[].field / reason / suggestion` 复用现有 FeedbackIssue schema（agent 字段由代码统一标 "writer"）

### [CONSTRAINTS]

```
1. 严格按 [OUTPUT_CONTRACT] JSON 输出，不要 markdown，不要解释开头
2. score 必须是 1/2/3/4 整数（不接受 2.5）
3. reasoning 字段必填，不能为空
4. issues 列表可空（如果该维度无问题）
5. 你是审计师，不要为报告写不足之处辩护
6. 不要做 limited_pairs 之外的全文级一致性检查
```

## 数据流与时序

### 正常路径（critic 一次成功）

```
inspector.inspect(report)
  ↓
_programmatic_checks()  →  prog_issues
  ↓
_critic_check(report, discovered_urls)
  ├─ 1. 拼装 user_prompt（report dict + discovered_urls + limited_pairs）
  ├─ 2. _llm_call_with_quota(CRITIC_SYSTEM, user_prompt, max_tokens=8192)
  ├─ 3. 解析返回 dict，校验 4 维 score 都是 1-4 整数
  ├─ 4. CriticScores(evidence=N, specificity=N, coherence=N, actionability=N)
  ├─ 5. 4 维 issues → FeedbackIssue list（severity 由 _score_to_severity 计算）
  └─ 返回 (critic_scores, critic_issues)
  ↓
合并 prog_issues + critic_issues，去重
  ↓
critic_score = calc_critic_score(critic_scores)
            = 0.30*evidence + 0.30*specificity + 0.20*coherence + 0.20*actionability
            归一化到 [0, 1]：score = (sum - 1) / 3
            （单维度 1-4 → critic_score 0-1）
  ↓
report.metadata.quality_score = critic_score
report.metadata.critic_scores = critic_scores  ← 新字段，供前端展示
report.metadata.quality_score_calculation_note = "critic: ev=3 sp=2 co=4 ac=3 → 0.583"
  ↓
RejectionFeedback(passed, issues, ...)
```

### 失败路径（critic LLM 出错）

```
_critic_check(report, discovered_urls)
  ↓
attempt 0: _llm_call_with_quota(max_tokens=8192) → 失败
  ├─ JSON 解析失败 / score 字段缺失 / score 越界 / retry
  └─ 落 logger.warning("[critic] LLM 第 1 次失败：%s")
  ↓
attempt 1（retry 1 次，max_tokens=8192 不变）:
  ├─ 成功 → 走正常路径
  └─ 失败 → 进入降级
  ↓
降级路径：
  ├─ critic_score = 0.5（中位数标记"质检失败"）
  ├─ critic_scores = None（metadata 写 None）
  ├─ report.metadata.warnings.append("critic_failed:<error_summary_short>")
  ├─ 不生成 critic_issues（issue 列表跳过 critic 那部分）
  └─ logger.error("[critic] LLM 失败重试后仍失败，降级为 score=0.5")
```

**注意**：retry 时 max_tokens 维持 8192 不调整。如果 attempt 0 因 max_tokens
不够撞 finish_reason=length，attempt 1 也会同样撞——但相同输入下重试有时能改善 LLM 输出
鲁棒性问题（OPEN_QUESTIONS Q-2026-06-18-llm-反馈修一退一 同类机制），所以保留 retry。
本 spec 不解 max_tokens 调参问题（不在范围）。

### Severity 映射规则（D 阈值）

```python
def _score_to_severity(dim_score: int, dim: str, all_scores: dict) -> str:
    """D 阈值规则：均值映射 + 单维度 ≤1 强制 critical。

    输入：
      dim_score: 当前维度分（1-4 整数）
      dim: 当前维度名（"evidence" / "specificity" / ...）
      all_scores: 4 维全分数 dict（用于聚合判定）
    返回：
      "critical" / "major" / "minor"
    """
    # 1. 单维度 ≤1 强制 critical（D 规则核心，防均值掩盖灾难）
    if dim_score <= 1:
        return "critical"

    # 2. 否则按聚合分映射
    agg = calc_critic_score(all_scores)  # 0-1 区间
    if agg < 0.50:
        return "critical"
    elif agg < 0.70:
        return "major"
    else:
        return "minor"
```

## Schema 改动

### 新增 CriticScores

```python
# src/schemas/feedback.py 末尾追加

class CriticScores(BaseModel):
    """critic 4 维评分（持久化到 ReportMetadata.critic_scores）"""
    evidence: int = Field(ge=1, le=4)
    specificity: int = Field(ge=1, le=4)
    coherence: int = Field(ge=1, le=4)
    actionability: int = Field(ge=1, le=4)
    reasoning: dict[str, str] = Field(default_factory=dict)
    """{dim: reasoning_text}，CoT 推理过程供前端展开 / 追溯"""
```

### ReportMetadata 扩展

```python
# src/schemas/report.py ReportMetadata 类追加

class ReportMetadata(BaseModel):
    # ...现有字段...
    critic_scores: Optional[CriticScores] = None
    """critic 4 维评分；critic 失败降级时为 None"""
```

## 测试设计

### 第 1 层：单元测试（机制正确性）

`tests/unit/test_inspector_critic.py`：

| 测试 | 场景 |
|------|------|
| `test_critic_check_normal_path` | mock LLM 返回合规 dict → 校验 critic_scores + issues 生成 |
| `test_critic_check_score_to_severity_mapping` | D 阈值规则各分支：1→critical / agg<0.5→critical / agg<0.7→major / else→minor |
| `test_critic_check_dimension_le1_forces_critical` | 单维度=1 即使 agg=3/4 也强制 critical |
| `test_critic_check_score_out_of_range_retries` | LLM 返回 score=5 → retry 1 次 |
| `test_critic_check_missing_dimension_retries` | LLM 返回缺 evidence_score → retry 1 次 |
| `test_critic_check_retry_then_fallback` | retry 仍失败 → critic_score=0.5 + warnings 加 "critic_failed" |
| `test_critic_check_json_parse_fail_uses_fallback` | LLM 返回非 JSON → fallback |

### 第 2 层：集成测试（端到端）

`tests/unit/test_inspector_critic.py` 末尾追加：

| 测试 | 场景 |
|------|------|
| `test_inspect_with_critic_replaces_quality_score` | 完整 BaseReport fixture → 跑 inspect → 验证 quality_score = critic_score（不是旧三项加权）|
| `test_inspect_v3_r17_cap_removed` | placeholder warnings 存在但 critic_score=0.6 → quality_score 仍是 0.6（不被 cap 0.5）|
| `test_inspect_critic_failure_warnings` | mock critic 失败 → metadata.warnings 含 "critic_failed" |

### 第 3 层：反例集测试（critic 判断力底线）

`tests/integration/test_critic_adversarial.py`（用 record/replay 而非真 LLM 调用）：

| Fixture（手工构造的"明显该低分"报告）| 期望 critic 输出 |
|-----|-----|
| `report_all_placeholder` 全章节 placeholder | specificity ≤ 2 |
| `report_no_source_refs` 所有 finding 无 source_refs | evidence ≤ 1 |
| `report_third_party_only` 全引用 upmarket.co / spyingbee.com 第三方聚合 | evidence ≤ 2 |
| `report_swot_self_contradiction` SWOT.strengths 说 X 强 + vendor.cautions 说 X 弱 | coherence ≤ 2 |
| `report_vague_recommendations` 全是 "加强 AI 能力" / "持续关注" | actionability ≤ 1 |

**实施方式**：
- record：先用真 LLM 跑一次，用 [VCR.py 类似工具] 录下 LLM 响应
- replay：CI 跑测试时用录像，不调真 LLM
- 录像失效（rubric 调整后）→ 手动重录

## 关键设计权衡

### 权衡 1：reasoning 字段不加字数约束

CoT reasoning 是推理过程，价值在过程而非长度。**不加字数约束避免 reasoning 也踩字数代理失效**。后续观察 reasoning 字数分布，如果 LLM 偷懒（reasoning 太短），再决定。

### 权衡 2：severity 由代码映射，不让 LLM 打

LLM 容易过度严苛或中庸偏稳，让代码按 score 严格映射保证 severity 跟 score 一致。

### 权衡 3：抽查 5 条而非全查

整报告 ~25000 字超过 critic 输入预算，全查时 LLM 注意力稀释。抽查 5 条 + CoT 让 LLM 在小样本上深思。

### 权衡 4：v3-R17 cap 完全删除

critic 已天然惩罚 placeholder（specificity 1/4 → 强制 critical），cap 0.5 是冗余。删除让 quality_score 信号更纯净。

### 权衡 5：critic 失败降级 0.5 而非 0.0

critic 偶发抖动给整份报告 0 分太严苛。降级 0.5（中位数）+ warnings 标记，让用户能识别"质检失败"信号。

## 与 OPEN_QUESTIONS 的关联

本 spec 实施后，以下 OPEN_QUESTIONS 状态变化：

| Q | 状态变化 |
|---|---------|
| Q-2026-06-17-字数约束的代理失效 | **设计中**（critic 是退役字数约束的前提）|
| Q-2026-06-18-inspector-llm-issue-丢失 | 部分缓解（critic 内部 retry + 降级机制）|
| Q-2026-06-17-llm-长输出鲁棒性 | 间接缓解（critic 输入长 → max_tokens 8192 + retry）|

不解决：
- Q-2026-06-17-phase3-不重试占位 — 这个跟 critic 无关，是 writer 阶段问题
- Q-2026-06-17-collector-抽取全或无 — 同上
- Q-2026-06-18-narrative-偶发抖动 — 同上
- Q-2026-06-18-llm-反馈修一退一 — 反而可能加重（critic 多生成一些 issue）
- Q-2026-06-18-json-extra-data — 通用 LLM 输出问题，不在本 spec 范围

## 字数约束渐进退役（后续阶段）

本 spec **仅落地 critic 本身**，字数约束删除留给后续 spec。预定路径（OPEN_QUESTIONS Q-2026-06-17-字数约束 已写）：

```
阶段 1（本 spec）：critic 设计 + 落地
                    ↓
阶段 2：跑 2-3 次端到端，校准 critic 准确度
                    ↓
阶段 3：分批退役 schema 字数下限约束（先 ≥10 / ≥20 小约束）
                    ↓
阶段 4：退役 ≥50 / ≥100 大约束（字数 ValidationError 高发区）
                    ↓
阶段 5：保留上限约束（≤200）+ 结构约束（必填 / 数量 / 枚举），永久不动
```

阶段 3-5 不在本 spec 实施范围。

## 不在本 spec 范围

- 字数约束实际删除（留给后续 spec）
- max_tokens 调参（等 finish_reason 证据积累）
- inspector LLM 调用之外的其他 critic 应用场景（如 writer phase 内嵌 critic）
- 多 critic 投票 / 跨模型 critic（成本高，单一 LLM 够用阶段不需要）
- critic 自身的训练或 fine-tuning（在线 prompt 工程已经够）

## 验收标准

实施完成后必须满足：

1. **测试**：单元 + 集成 + 反例集全绿 / ruff clean
2. **现有报告兼容**：旧 trace 报告（v1 schema）仍可被 inspector 处理（critic 失败降级生效）
3. **新报告产出**：metadata 含 `critic_scores` 字段，包含 4 维分数 + reasoning
4. **失败降级日志**：critic 真实失败时（手动构造场景），warnings 含 `critic_failed:*` 前缀
5. **真实跑通**：至少跑 1 次 S5 场景端到端，对比 critic 评分 vs 人类直觉评估
