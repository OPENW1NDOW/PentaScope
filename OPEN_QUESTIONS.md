# Open Questions

PentaScope 项目里**已发现但未决定如何应对**的深层问题。与 PROGRESS / DECISIONS 边界：

| 文档 | 内容 | 时间尺度 |
|------|------|---------|
| `PROGRESS.md` | 每次 session 干了什么 / 接下来 1-2 session 做什么 | 短（天 / 周） |
| `DECISIONS.md` | 已**做出**的技术决策及其理由 | 永久 |
| `OPEN_QUESTIONS.md` | 已**发现**但**未决定如何应对**的深层问题（跨 session 反复回访） | 中（周 / 月） |

判别规则：
- 已经决定怎么修 → DECISIONS（写决策）+ PROGRESS（排期实施）
- 还没决定怎么修，但讨论过 → 进 OPEN_QUESTIONS
- 一两天就能消化 → 留在 PROGRESS 不要分
- 跨 session 反复回访 / 跨场景跨模块 / 修复路径不明 / 可能引发架构级改动 → 移到 OPEN_QUESTIONS

每条问题用 `Q-YYYY-MM-DD-关键词` 作为 ID，PROGRESS 引用时写 `详见 OPEN_QUESTIONS.md#Q-...`。

状态分四档：
- **未决** — 已发现 / 已讨论方向 / 未启动修复
- **设计中** — 走 brainstorming / spec / plan 流程
- **实施中** — 进 PROGRESS 跟踪
- **已并入** — 解法落到 DECISIONS，原问题归档

---

## 等 critic 落地的 6 条（2026-06-19 统一处置）

2026-06-19 Cooper 决断：
- **字数约束代理失效**（原 Q-2026-06-17-字数约束）→ 已决断采用 LLM-as-critic + 字数约束渐进退役，spec v2 已落 `docs/superpowers/specs/2026-06-19-llm-as-critic-design.md`，进开发阶段，本条移出 OPEN_QUESTIONS
- **narrative 偶发抖动**（原 Q-2026-06-18-narrative-偶发抖动）→ 已决断方案 (a) phase 3 加 1 次轻重试，已记入 PROGRESS 06-18 待办，本条移出 OPEN_QUESTIONS

剩下 6 条都挂在「LLM 输出鲁棒性差 + 字数约束副作用」这条根因上，**等 critic 落地后回头看可能消解一半**，所以现在统一冻结观察、不深入决策：

---

## Q-2026-06-17-llm-长输出鲁棒性

**状态**：未决（等 critic）

LLM 生成长 JSON 时字符串值在写到一半被 `max_tokens` 硬截断 → `Unterminated string` → 3 次重试都失败。`llm_client.py:_BARE_BACKSLASH_PATTERN` 兜底无效。

候选：(a) 拆 phase / (b) 容错 JSON 解析 / (c) structured outputs

**等 critic 决策原因**：critic + 字数退役后 writer 单次输出复杂度自然降，本问题可能消解一半。**不要单独修**。

实证：`runs/20260617-181916-91bc54/04_writer_error.json` —— `Unterminated string starting at: line 199 column 26 (char 8274)`

---

## Q-2026-06-17-phase3-不重试占位

**状态**：未决（部分已并入 narrative 抖动决策）

writer phase 3 narrative 单次失败直接占位 → `placeholder_section` warning → quality_score cap 0.5 → passed=False。

**重叠提示**：本问题与已决断的 Q-2026-06-18-narrative-偶发抖动 重叠——加 1 次轻重试（已排进 PROGRESS）能消解大半。剩下「输入大 section 是否要拆」「占位是否触发 cap」等 critic 落地后再评估。

实证：`runs/20260617-181916-91bc54/run.log:63` —— `phase 3 section competitive_moves_analysis 失败 → 占位降级`

---

## Q-2026-06-17-collector-抽取全或无

**状态**：未决（等 critic，可叠加 normalizer 应急）

Collector 抽取 LLM 把网页正文转 dict 时 Pydantic 整体校验：1 个字段违反 schema（如 `feature_tree[i].features[j].description` >200 字符）→ 整个 profile 被丢弃。LLM 干了 99% 正确的活，1 个 description 多写 20 字 → 100% 作废。

候选：(a) 抽取后接 normalizer 自动截断 / (b) 字段级回填 / (c) prompt 加显式硬约束 / (d) 字数约束渐进退役

**等 critic 决策原因**：(d) 跟 critic 同方向；(a) 是应急止血方案、可以不等 critic 单独排期，但优先级 Cooper 后续决定。

实证：`runs/20260617-181916-91bc54/run.log:23-27` —— Mixpanel `feature_tree.4.features.1.description: String should have at most 200 characters` → completeness=0.0

---

## Q-2026-06-18-json-extra-data

**状态**：未决（等 critic）

LLM 输出 JSON 时偶尔在合法 JSON 之后追加纯文本说明段 → `Extra data: line N column M` → 解析失败。`_strip_json_fence` 只处理 ```` ``` ```` 围栏，不处理 JSON 后的纯文本尾巴。

候选：(a) `_strip_json_fence` 改用 `json.JSONDecoder().raw_decode()` 找第一个完整 JSON / (b) prompt 加显式提醒 / (c) structured outputs

**等 critic 决策原因**：(c) 跟 critic 同方向；(a) 工程量极小、可独立做，优先级 Cooper 后续决定。

实证：`runs/20260618-095358-c5ab5c/run.log` —— writer phase 2b `Extra data: line 74 column 4 (char 2655)`

---

## Q-2026-06-18-llm-反馈修一退一

**状态**：未决（等 critic）

writer / outline ValidationError 重试时 LLM 没有"上次这条对了别动它"的记忆 → 常见"修一退一"：attempt 0 错 A → attempt 1 修 A 但反退 B → attempt 2 修 B 但反退 C，max_retries=2 预算紧。

候选：(a) 增量编辑 patch / (b) prompt 提醒"上次合规字段保留" / (c) 字段级独立校验 + 重试 / (d) critic 替代字数 schema 约束

**等 critic 决策原因**：错误大半是字数约束触发的，critic + 字数退役后"修一退一"频率会自然下降。(a)/(b)/(c) 都是工程上很重的方案，先看 critic 后还剩多少。

实证：`runs/20260618-095358-c5ab5c/run.log` —— phase 2a / phase 2b 的"修一退一"完整时序

---

## Q-2026-06-18-inspector-llm-issue-丢失

**状态**：未决（等 critic）

inspector LLM 返回的 issue list 部分条目自身违反 `FeedbackIssue` schema（severity 缺失等）→ `_parse_llm_issues` 直接丢弃 → 反馈信号容量被自身鲁棒性问题压低（trace 实证 8 条 LLM 给的 issue 丢了 2 条）。

候选：(a) inspector LLM issue 也做错误反馈重试 / (b) FeedbackIssue 字段宽容化 / (c) inspector 改用 LLM-as-critic rubric 输出

**等 critic 决策原因**：critic 落地后 inspector 角色可能整体重构，(c) 跟 critic 整体设计同方向。先观察 inspector LLM issue 丢失率，critic 落地后再看是否还需要单独修。

实证：`runs/20260618-095358-c5ab5c/run.log` —— inspector LLM issue 解析失败 2 次

---
