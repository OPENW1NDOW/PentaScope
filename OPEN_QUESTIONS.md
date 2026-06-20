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

**状态**：已并入（2026-06-19 晚修复）

已采用方案 (a) `raw_decode()`：在所有兜底之前优先用 `json.JSONDecoder(strict=False).raw_decode()` 提取第一个完整 JSON 对象，忽略后续追加文本。

---

## Q-2026-06-18-llm-反馈修一退一

**状态**：已消解（2026-06-20）

字符 min_length 全部退役后触发根因不存在了。S1-S4 实跑未再观察到"修一退一"现象。

---

## Q-2026-06-18-inspector-llm-issue-丢失

**状态**：已消解（2026-06-20）

critic v1.2.1 重写 inspector 后，S1-S5 五次实跑均未观察到 issue 丢失。`_extract_critic_issues` 逐条 try/except 容错已覆盖。

---

## Q-2026-06-19-scenario-query-低相关

**状态**：已并入（2026-06-20 实施方案 A）

已采用方案 (a)+(b)：每场景 3 条产品实操语言 query（commit 9e66079），覆盖产品对比/官网/用户评价等不同角度。待下次端到端跑验证有效率提升。

---

## Q-2026-06-20-内部重试应带纠正反馈

**状态**：未决（等 S1-S4 跑完看新 ValidationError 频率再决定优先级）

collector / analyzer / phase 3 narrative / inspector 内部重试都是纯重跑相同 prompt，不带纠正信息。从实测看部分失败是**系统性**的（LLM 写太长/枚举值错），不是随机抖动——纯重试靠运气，加反馈修复率更高。

但字符约束退役后 ValidationError 频率预期大幅下降，ROI 需要重新评估。

待做（如果频率仍高）：
- collector extract：ValidationError 时告诉 LLM "哪个字段超长/缺失，请精简/补全"
- analyzer：ValidationError 时告诉 LLM "哪个字段违规，请修正"
- phase 3 narrative：ValidationError 时告诉 LLM "section_id/narrative 哪里不合规"

参照：writer phase 1/2 已做（`【上次校验失败，请逐条修复】\n{错误摘要}`），效果验证有效

---

## Q-2026-06-20-evidence-issue-路由错误

**状态**：已解决（2026-06-20 反馈闭环路由改进实施）

S4 实测 evidence=2（source_refs 引用率不足）→ critic issues 类型 `url_not_discovered` → `_map_issue_type_to_agent` 映射到 collector → 打回 collector 重搜 → 搜索结果不变 → evidence 仍为 2。

问题：**evidence 低不是"搜不到信息"而是"writer 没把已有 URL 写进 source_refs"**——应该打回 writer 让它重写时多引用，而非打回 collector 重搜。

实证：S4 trace `20260620-153459-f19d5f` 两轮 evidence 都是 2，第二轮 specificity/actionability 反而退步（4→3），闭环有害。

修复方向：
- (a) 短期：修 `_map_issue_type_to_agent`——`url_not_discovered` 改映射到 writer（让 writer 重写时优先使用 discovered_urls 列表中的 URL）
- (b) 中期：writer narrative prompt 加"每段必须引用至少 1 个 source_ref URL"指令
- (c) 区分"URL 根本不存在"（真的需要 collector 补采）vs"URL 存在但 writer 没用"（应打回 writer）

关联：Q-2026-06-20-collector-打回无效重跑

---

## Q-2026-06-20-collector-打回无效重跑

**状态**：已解决（2026-06-20 反馈闭环路由改进实施）

inspector 打回 collector 时只是用相同 query 重新搜索——结果几乎不变，纯浪费时间。应该把 feedback issues 转化为针对性补充搜索 query。

问题本质：collector 打回 ≠ "再搜一遍"，应该 = "针对缺什么补搜什么"。

候选方向：
- (a) 从 feedback issues 中提取 `field` + `reason`，让 LLM 生成 1-2 条补充 query（如"金山文档 AI 写作功能 评测"）
- (b) collector 收到 feedback_issues 后只补搜缺来源的竞品，不重跑全部
- (c) 如果 issues 全指向 collector 但搜索结果确实无法改善（如竞品本身公开信息少），跳过重跑直接 pass

关联：搜索策略优化课题族（Q-2026-06-19-scenario-query + 本条）

实证：S1 trace `20260620-124505` 第一轮 collector 打回后重跑，搜索结果与首次完全相同

---
