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

剩下的条目（2026-06-19 晚 session 重新评估后）：

- Q-2026-06-17-llm-长输出鲁棒性 → **已并入 DECISIONS**：max_tokens 实证调参（phase1=6144/phase2=12288/phase3=8192），S5 实测零截断
- Q-2026-06-17-phase3-不重试占位 → **已并入 DECISIONS**：narrative 轻重试实现（commit eae4e44），S5 实战验证救回 1 section
- Q-2026-06-18-llm-反馈修一退一 → **已消解**：字符 min_length 全部退役（commit 0ad443c），触发"修一退一"的根因不存在了
- Q-2026-06-17-collector-抽取全或无 → **已修复**：Feature.description max_length 200→500（commit 本次），不再因 20 字超限丢整个 profile

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

## Q-2026-06-19-scenario-query-低相关

**状态**：未决（归入 collector 搜索优化课题）

S5 query `"{name} 品牌定位 战略差异化 核心竞争力"` 搜到大量无关内容（MBA 百科、社科院论文、金融研报），12 条 Tavily 结果中仅 5 条与竞品真实相关（42% 有效率）。其他场景也存在类似问题但程度不同。

根因：query 用学术/抽象术语而非产品实操语言，Tavily 把 query 理解为"搜品牌定位这个概念"而非"搜这个产品的竞争信息"。

候选改进方向：
- (a) 每场景 2-3 条 query（当前仅 1 条），覆盖不同角度（产品对比 / 市场份额 / 用户评价）
- (b) query 模板改用产品实操语言（如 `"{name} vs 竞品 对比 2024"` / `"{name} 用户评价 优缺点"`）
- (c) 动态 query 生成：LLM 根据 scenario + competitor_name 生成 2-3 条针对性 query

关联待办：PROGRESS 里多次出现的"collector 信息收集优化：多次搜索 + 不同关键词"

实证：`runs/20260619-203923-9f5681` S5 场景——Sketch 搜到 wiki.mbalib.com 品牌百科 / bdrc.sass.org.cn 社科院论文 / pdf.dfcfw.com 东财研报；Adobe XD 搜到 Adobe Campaign 品牌指南（同名污染）

---
