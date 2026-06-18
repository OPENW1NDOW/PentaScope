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

## Q-2026-06-17-字数约束的代理失效

**状态**：未决

### 问题描述

PentaScope schema 大量字段带 `≥N 字符` 长度约束（`rationale ≥50` / `point ≥10` / `overview 20-200` / `why_this_category ≥30` / `feature.description ≤200` 等），用来反 LLM「写空话糊弄」。但这是个有缺陷的代理：

1. **执行困难**：LLM 在字符层面控制力差是机制问题（token≠字符 / 自回归无全局规划 / 训练分布缺「严格字数」任务 / 知行差距）。换更强模型也救不了——MiMo 0/3、Doubao 1/3 PASS 靠 fix20 兜底
2. **失败模式错位**：字数约束能拦「懒得写」但拦不住「写很多废话」，废话恰是 LLM 舒适区。能让"内容长"，做不到"内容真"
3. **代理叠加无效**：第一反应是换另一个字符级代理（"每段必须有数字 / 专名"），但真实咨询报告大量纯洞察论断本身就没数字（"建议优先攻防而非主动进攻" / "进入门槛主要在生态而非技术"），强制加会逼出比废话更糟的假数据幻觉

### 发现路径

2026-06-17 跑 S5 payload 拆分时，写测试 fixture 反复触发字数 ValidationError（`overview` 17 字差 3、`rationale` 41 字差 9 等），Claude 自己估字数都频繁出错 → Cooper 反问 "为什么 LLM 字数控制差" → 引出 token-counting 机制讨论 → Cooper 进一步反问 "实际竞品分析报告真的能达到 ≥1 数字 / 专名要求吗"，Claude 撤回方案 A，承认是 "看到代理失效就想换代理" 的思维 bias

### 当前理解

提质方向应**跳出代理思路**，转向 LLM-as-critic 语义评分（G-Eval / Prometheus 范式）：
- 独立 critic prompt 按结构化 rubric 打分（specificity / actionability / evidence / coherence）
- writer 据此重写
- 字数约束**渐进退役**——critic 跑通后逐字段评估"实际拦住的是什么"，拦"水且违规"才保留，拦"真但不合规"或"水但合规"则删
- collector 增厚后再考虑 embedding 溯源校验（rationale vs source 内容相似度），现在 Tavily 单源不够支撑

### 实证素材

- `runs/20260617-181916-91bc54`（S4 Mixpanel/Amplitude/PostHog 首次基线）—— 三类失败（max_tokens 截断 / phase 3 ValidationError / collector 抽取超长）全是字数约束 + LLM 长输出弱可控的同一根因变种
- `feedback_proxy_metric_bias.md`（记忆）—— Claude 思维 bias 记录
- `project_length_constraint_proxy_problem.md`（记忆）—— 项目当前字数约束本质问题 + 提质方向

### 不动手的原因

需要走完整 brainstorming → doubt-driven → spec → plan 流程：
- critic prompt 设计本身需要好几轮调优
- rubric 维度选择影响评分稳定性
- 跟现有 inspector 反馈闭环架构兼容需要设计
- 多 1 次 LLM 调用，quota 18 上限可能不够，需要预算重算
- 字数约束渐进退役需要 A/B 测试，不能一次删完

### 关联问题

- Q-2026-06-17-llm-长输出鲁棒性（同根因不同表现）
- Q-2026-06-17-phase3-不重试占位（同根因不同表现）
- Q-2026-06-17-collector-抽取全或无（同根因不同表现）

---

## Q-2026-06-17-llm-长输出鲁棒性

**状态**：未决（症状已知，对策未定）

### 问题描述

LLM 生成长 JSON（writer phase 1 outline / phase 2 payload）时，字符串值在写到一半时 token 计数撞 `max_tokens=4096/8192` 上限被硬截断，输出半截字符串没闭合引号 → JSON 解析 `Unterminated string` → 全 3 次重试都失败 → ValueError。

`llm_client.py:_BARE_BACKSLASH_PATTERN` 兜底只能修反斜杠转义，对"字符串本身被截断"和"property name 处缺引号"两类错无效。

### 发现路径

2026-06-17 trace 复盘：5 次 JSON 解析失败的 char 位置（6089 / 13900 / 22429 / 8274 / 5765 / 9009）全在字符串值中间，看上下文片段都是输出在 `conclusions / value_basis / recommended_response` 等长 narrative 字段中途被切。

### 当前理解（候选对策三选）

| 方案 | 思路 | 代价 |
|------|------|------|
| (a) 降单次输出长度 | phase 2 拆分（参考 S5 phase2a/2b 模式扩展到其他场景） | 工程量中，多 1 次 LLM 调用 |
| (b) 流式 / 容错 JSON 解析 | 引入 `json5` 或自实现"截断后补 `"]}` 闭合"逻辑 | 工程量小，但本质是事后补救，可能引入数据错误 |
| (c) 接 structured outputs | OpenAI / Doubao 端点的 JSON Schema constrained decoding，token 采样阶段直接掐死非法 token | 取决于 MiMo 是否支持，需调研 |

### 实证素材

- `runs/20260617-181916-91bc54/run.log` 行 37-46 + 52-57 —— 5 次失败完整时序
- `runs/20260617-181916-91bc54/04_writer_error.json` —— `Unterminated string starting at: line 199 column 26 (char 8274)`

### 不动手的原因

跟字数约束代理失效（Q-2026-06-17-字数约束）同根：LLM 长输出弱可控。如果先做 LLM-as-critic + 字数约束渐进退役，writer 单次输出复杂度自然降低，本问题可能消解一半。**不要单独修，等上游决策**。

### 关联问题

- Q-2026-06-17-字数约束的代理失效（根因）
- S5 phase 2 拆分（已实施，可作为其他场景拆分的参考）

---

## Q-2026-06-17-phase3-不重试占位

**状态**：未决

### 问题描述

Writer phase 3 narrative 是 6 个 section 用 `asyncio.gather(return_exceptions=True)` 并发调 LLM。设计上**单次调用、不重试**——失败直接 `_build_placeholder_section` 占位降级。

副作用：
1. 偶发 LLM 输出 ValidationError（缺字段 / 类型错） → 直接占位，无补救机会
2. 占位会触发 `placeholder_section:{section_type}` warning → quality_score 强制 cap 0.5（v3-R17）→ 整份报告 passed=False
3. 占位章节内容为兜底模板（~400 字），没有任何业务价值
4. 输入 context 大的 section（如 S4 `competitive_moves_analysis` 吃 5 字段：feature/pricing/messaging/news/org changes）失败率显著高于其他 section

### 发现路径

2026-06-17 trace `20260617-181916-91bc54` 第二次 writer 跑：phase 3 6 个 section 中 5 成功 1 失败（`competitive_moves_analysis`），ValidationError → 占位 → quality_score=0.493（cap 0.5 触发）→ passed=False → reject 到 max_retries=2 强制结束。31 分钟跑出半残报告。

### 当前理解（候选对策）

| 方案 | 思路 | 代价 |
|------|------|------|
| (a) phase 3 加 1 次重试 | 简单：失败重跑一次，仍失败才占位 | 增加 ~30s × 失败 section 数；需要警惕 LLM 卡死场景 |
| (b) 大输入 section 拆分 | 5 字段 section 拆 2 次 narrative（feature+pricing 一节、messaging+news+org 一节） | 工程量中；改 SECTION_CONTEXT_MAP + 增加 section 数 |
| (c) 占位章节不触发 cap | 单 section 失败不算"placeholder warning"，全报告失败才 cap | 改 inspector / quality_score 计算；可能放宽过头 |

设计权衡：原 v3 选不重试是为了避免 6 section × 3 retry × 高 max_tokens = 长尾耗时不可控。但实际跑出来"快 30 分钟"也没好到哪去。

### 实证素材

- `runs/20260617-181916-91bc54/run.log:63` —— `phase 3 section competitive_moves_analysis 失败 → 占位降级: ValidationError`
- `runs/20260617-181916-91bc54/03_report.json` —— 占位章节 narrative=414 字符（兜底模板），其他 5 章 1700-2300 字

### 关联问题

- Q-2026-06-17-字数约束的代理失效（根因之一）
- Q-2026-06-17-llm-长输出鲁棒性（根因之一）

---

## Q-2026-06-17-collector-抽取全或无

**状态**：未决

### 问题描述

Collector 抽取 LLM 把网页正文转成 `CompetitorProfile` 结构化 dict 时，**Pydantic 整体校验**：1 个字段违反 schema（如 `feature_tree[i].features[j].description` >200 字符）→ **整个 profile 被丢弃** → 06-14 fix 兜底：保留 pipeline 抓到的 URL，构造**占位 profile**（feature_tree=[]、recent_updates=[]、completeness=0.0）。

副作用：LLM 干了 99% 正确的活（合规结构 + 真实内容 + 几十个有效字段），1 个 description 多写 20 字 → 100% 被作废，下游 analyzer / writer 拿到的只有 URL 列表，无结构化字段，事实溯源能力大幅退化。

### 发现路径

2026-06-17 trace `20260617-181916-91bc54` collector 阶段：Mixpanel LLM 抽取返回完整 dict（5 module / 12+ feature / 4 review / 3 update / 5 source URL），但 `feature_tree[4].features[1].description`（Mixpanel MCP 那条）写了 220 字符 → string_too_long → 整个 profile 被丢弃 → completeness=0.0。

下游报告里 Mixpanel 章节信息严重缺位（key_findings 引用第三方聚合站 `upmarket.co` / `spyingbee.com` 而非官网，inspector 提了 major issue）。

### 当前理解（候选对策三选 + 1）

| 方案 | 思路 | 代价 |
|------|------|------|
| (a) 抽取后接 normalizer | 自动截断超长字符串到 schema 上限（取最长 200 字符 + "..."） | 工程量小；可能截在不合理位置 |
| (b) 部分接受 + 字段级回填 | Pydantic ValidationError 时按字段 path 定位违规字段，只丢违规字段，保留其他 | 工程量中；改 `_extract_profile` 兜底逻辑 |
| (c) 抽取 prompt 加显式硬约束 | "description ≤200 字符（含中英文）" 写进 prompt | 工程量极小；但 LLM 字数控制差不可靠（见 Q-2026-06-17-字数约束） |
| (d) 字数约束渐进退役 | 跟随 LLM-as-critic 决策，删 description 字数限 | 工程量大；依赖 critic 落地 |

(a) + (c) 可叠加；(d) 需要等上游 critic 决策。

### 实证素材

- `runs/20260617-181916-91bc54/run.log:23-27` —— Mixpanel 失败精确字段：`feature_tree.4.features.1.description: String should have at most 200 characters`
- `runs/20260617-181916-91bc54/01_profiles.json` —— Mixpanel: `completeness=0.0` / `feature_tree modules=0` / `recent_updates=0` / `data_sources=5`（与 Amplitude/PostHog 完整 profile 对比鲜明）

### 关联问题

- Q-2026-06-17-字数约束的代理失效（根因）
- PROGRESS 06-14 已识别但未修："completeness 评分机制问题：硬编码 4 项扣分，占位 profile 硬编码 0.0 而非走公式"

---

## Q-2026-06-18-json-extra-data

**状态**：未决（症状已知，对策未定）

### 问题描述

LLM 输出 JSON 时偶尔在合法 JSON 之后**追加纯文本说明段**——这是 `Extra data: line N column M` 类 JSON 解析错误，与已知的 `Unterminated string` / `Expecting value` / `Expecting property name` 不是同一类。

例：
```
{
  "errc_grid": {...},
  "positioning_statement": {...}
}
↓ char 2655 (line 74) ↓
注：以上 JSON 已严格按 schema 输出。
```

`_strip_json_fence` 只处理 ```` ``` ```` 围栏，不处理 JSON 后的纯文本尾巴 → JSON 解析失败。

### 发现路径

2026-06-18 trace `20260618-095358-c5ab5c` writer phase 2b 第二次跑：`Extra data: line 74 column 4 (char 2655)`，由客户端层 `LLM_MAX_RETRIES` 救回，但消耗 1 次重试预算。

### 当前理解（候选对策）

| 方案 | 思路 | 代价 |
|------|------|------|
| (a) `_strip_json_fence` 改为找第一个完整 JSON 对象 | 用 `json.JSONDecoder().raw_decode()` 找出第一个合法 JSON 终止位置，丢弃尾巴 | 工程量小；可能丢弃合法的多 JSON 输出（项目目前无此场景）|
| (b) prompt 加显式提醒"只输出 JSON，不要任何说明" | 软约束，每个 prompt 加一条 | 工程量极小；但 LLM 不一定听 |
| (c) 接 OpenAI structured outputs | token 采样阶段就掐死 | 等 MiMo 支持调研 |

### 实证素材

- `runs/20260618-095358-c5ab5c/run.log` —— phase 2b attempt 1/3 `Extra data: line 74 column 4 (char 2655)`

### 关联问题

- Q-2026-06-17-llm-长输出鲁棒性（同根：LLM 输出鲁棒性差）

---

## Q-2026-06-18-llm-反馈修一退一

**状态**：未决

### 问题描述

writer / outline 阶段的 ValidationError 重试机制是「错误反馈回灌 → LLM 据此修复」。**但 LLM 没有"上次这条对了别动它"的记忆**——只看到当前 prompt + 错误列表。结果常见：

1. attempt 0：A 字段错（cluster_zones 漏字段）
2. attempt 1：A 字段对了，**但 B 字段错了**（strengths < 2 条 —— 上次合规的字段这次反退）
3. attempt 2：A、B 都对了，**但 C 字段错了**

实际 trace 中 phase 2a 这种"修一退一"占了 max_retries=2 整个预算才勉强通过。增强错误反馈虽然让单次错误更易理解，但解决不了"LLM 全文重写时整体一致性不稳"的天然弱点。

### 发现路径

2026-06-18 trace `20260618-095358-c5ab5c`：
- 第一次 writer phase 2a：attempt 0（cluster_zones 4 字段）→ attempt 1（strengths < 2 条）→ attempt 2 通过
- 第二次 writer phase 2b：attempt 0（artifact_id 缺失）→ attempt 1（artifact_id 还缺）→ attempt 2 通过（这次是同字段反复挂，更糟）

### 当前理解（候选对策）

| 方案 | 思路 | 代价 |
|------|------|------|
| (a) 增量编辑而非全文重写 | 重试时让 LLM 输出"针对错误的 patch"（"只修 cluster_zones 这一段"），代码层 merge 到上次输出 | 工程量大；patch 解析本身可能再踩坑 |
| (b) 在 prompt 里提醒"上次输出的 X/Y/Z 字段已合规，请保留" | 把上次合规字段单独列出叫 LLM 别动 | 工程量小；prompt 复杂度增加 |
| (c) 字段级独立校验 + 字段级独立重试 | 拆 phase 2a 为多个子调用，每个只产一两个模块 | 工程量大；不止是 S5 拆分这种粒度，还要更细 |
| (d) LLM-as-critic 评分替代字数 schema 约束 | 见 Q-2026-06-17-字数约束 | 字数约束删了之后，"修一退一"的可能性降低 |

(d) 路径走通后 (a)/(b)/(c) 都可能不需要。

### 实证素材

- `runs/20260618-095358-c5ab5c/run.log` —— phase 2a / phase 2b 的"修一退一"完整时序

### 关联问题

- Q-2026-06-17-字数约束的代理失效（根因——错误本身大半是字数约束触发的）
- 增强错误反馈（writer_orchestrator.py:_serialize_validation_error_enhanced）—— 改善了错误的可读性，但解决不了"全文重写"问题

---

## Q-2026-06-18-inspector-llm-issue-丢失

**状态**：未决

### 问题描述

Inspector 调 LLM 让其产出质检 issues 时，LLM 返回的 issue list 部分条目自身**违反 `FeedbackIssue` schema**（如 severity 字段缺失、字段类型错），inspector 在 `_parse_llm_issues` 处直接丢弃这些条目（`logger.warning("LLM issue 解析失败")`）。

副作用：inspector 真正想反馈给 writer 的部分质检建议**丢失**，LLM 反馈的信号容量被自身鲁棒性问题压低。

### 发现路径

2026-06-18 trace `20260618-095358-c5ab5c` 第二次 inspector 跑：log 显示 `LLM issue 解析失败: 1 validation error for FeedbackIssue` 出现 2 次，最终 `issues=8 (prog=2, llm=6)`——说明 LLM 至少给了 8 条 issue 但 2 条被 schema 拒了，只剩 6 条进 feedback。

### 当前理解（候选对策）

| 方案 | 思路 | 代价 |
|------|------|------|
| (a) inspector LLM issue 也做错误反馈重试 | 跟 writer 一样，回灌 ValidationError 给 LLM 重写 | 工程量小；多 1 次 LLM 调用 |
| (b) FeedbackIssue 字段宽容化 | severity 等枚举字段加默认值 / 字段缺失允许 | 工程量小；但稀释了 schema 约束意图 |
| (c) inspector 改用 LLM-as-critic rubric 输出 | 跟 Q-2026-06-17-字数约束 的对策方向一致 | 等 critic 整体设计 |

### 实证素材

- `runs/20260618-095358-c5ab5c/run.log` —— inspector LLM issue 解析失败 2 次

### 关联问题

- Q-2026-06-17-字数约束的代理失效（同根：LLM 输出鲁棒性 + 字数约束副作用）

---

## Q-2026-06-18-narrative-偶发抖动

**状态**：未决（观察阶段）

### 问题描述

Phase 3 narrative 各 section 用 `asyncio.gather(return_exceptions=True)` 并发独立 LLM 调用，单次调用不重试，失败直接占位降级（v3 设计选择，见 OPEN_QUESTIONS Q-2026-06-17-phase3-不重试占位）。

**之前假设**：失败率与输入 ctx 大小相关（输入大 → 输出复杂 → 失败概率高）。
**新观察**：今天 S5 第一次跑 `strategy_canvas_analysis` 失败（输入只 1 字段 `payload.strategy_canvas`，并不大），但仍挂；昨天 S4 `competitive_moves_analysis` 失败（输入 5 字段，输入大）。

**修正假设**：单 section 失败率约 17%（昨天 S4 1/6、今天 S5 第一次 1/6）是 MiMo 在该任务的**底噪失败率**，与 section 输入大小关系不强。

### 发现路径

2026-06-18 trace `20260618-095358-c5ab5c`：
- 第一次 writer phase 3：5/6 成功，`strategy_canvas_analysis` 占位
- 第二次 writer phase 3：6/6 全成功（同 section 重跑就过了）→ **印证是偶发抖动，不是 section 固有问题**

### 当前理解

- 不需要"针对某 section 单独优化"
- 需要的是**容错机制**：phase 3 加 1 次重试（覆盖偶发抖动），而非占位降级

但这跟 v3 设计选择冲突（不重试是为了控制总耗时上限）。需要权衡。

### 候选对策

| 方案 | 思路 | 代价 |
|------|------|------|
| (a) phase 3 加 1 次轻重试 | 单 section 失败重跑 1 次，仍失败才占位 | +30s × 失败 section 数；6 sections × 1 次 = 最坏 +3min |
| (b) phase 3 失败 section 不触发 cap | 单 section 占位不计 placeholder warning，多 section 失败才 cap | 改 inspector quality_score 计算逻辑；可能放宽过头 |
| (c) 提高 narrative LLM 输出鲁棒性 | prompt 优化 / max_tokens 调整 / structured outputs | 工程量中 |

### 实证素材

- 昨天 S4 trace `20260617-181916-91bc54` —— competitive_moves_analysis 占位（5/6）
- 今天 S5 trace `20260618-095358-c5ab5c` —— strategy_canvas_analysis 占位（5/6）→ 第二次重跑 6/6
- **同 section 重跑就过 → 强证偶发抖动**

### 关联问题

- Q-2026-06-17-phase3-不重试占位（同问题不同观察角度——之前以为是"输入大 section 注定失败"，现在修正为"偶发抖动通过重试可救"）
