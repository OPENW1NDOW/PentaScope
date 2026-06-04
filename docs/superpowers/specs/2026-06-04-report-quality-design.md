# 报告质量提升设计（方案 C：溯源为脉）

> 日期：2026-06-04
> 状态：已通过 brainstorming + 两轮 doubt-driven（单模型 + Codex gpt-5.5 跨模型），Cooper 已认可
> 关联课题评分项：多 Agent 协作与可信度（35%）、技术深度（25%）、业务价值（20%）

## 1. 问题

工作流能跑通，但产出报告**简陋、深度不足、溯源断链**。质检（inspector）反复暴露三类硬伤：

1. **溯源断链**：report 各 section 的 `source_refs`、各 action_item 的 `source_urls` 恒空。
2. **SWOT 丢失**：analyzer 算出 SWOT，但 report schema 无 SWOT 字段，writer 丢弃。
3. **focus_area 空**：collector 解析目标时未填 `analysis_goal.focus_area`。

## 2. 根因（两轮对抗审查核对源码后定论）

最初设想「只改 writer 做机械下沉」是错的。两轮 doubt-driven 一致揭示：**溯源断链与简陋的真正根因在采集层就埋下**。

- **事实与 URL 从未绑定**：`COLLECTOR_EXTRACT_SYSTEM`（prompts.py:39）只给 `sample_reviews` 留了 `source_url`，feature_tree/pricing/recent_updates 抽取模板无此字段；`_normalize_raw`（collector.py:78-80）只把 URL 写进 `metadata.data_sources`（扁平列表），不写进每个 fact。
- **正文 merge 成无锚点 blob**：`collection_pipeline.collect`（collection_pipeline.py:147）把多源正文拼成一个 blob，sources 是另一个扁平 list，二者无「哪段文字来自哪个 URL」的边界——LLM 抽取时无 URL 锚点，任何后续溯源都是猜。
- **analysis 无 source_urls 输出槽**：`ANALYZER_SYSTEM`（prompts.py:49-61）JSON 模板无 source_urls 字段，故 analysis 各维度 source_urls 恒空。
- **prompt 填空式 + 主动限长**：writer 每段「50-150 字」，压制深度。
- **三层串联截断**：analyzer 12000、writer 8000、inspector 15000 字符截断，逐级丢信息。
- **假闭环**：`inspector.py:82` `passed = len(issues)==0` 不分 severity；`should_continue`（builder.py:102-104）路由只认 collector/writer，analyzer 缺陷静默转 writer，writer 改不了上游 → 必耗尽 max_retries 强制结束、defects 仍在。

## 3. 设计主线：事实-URL 绑定链（贯穿全链路）

```
collection_pipeline: 保留 per-source 的 (text, url) 分段，不再 merge 成无锚点 blob
   ↓ 带 URL 边界的分段文本
collector: 抽取时给每个 fact（feature/pricing/review/update）填 source_url
   ↓ profile 各 fact 带 source_url
analyzer: prompt 补 source_urls 输出槽 + 代码兜底从 profile 聚合
   ↓ analysis 各维度 source_urls 真实有值
writer: 代码机械下沉到 section.source_refs / 透传 SWOT/radar/feature_matrix
   ↓ report 结构完整 + 溯源挂载
inspector: 程序化硬查溯源/SWOT/radar/feature_matrix；修反馈路由
```

核心原则（贯穿）：**能用代码保证的结构与溯源，不赌 LLM**；LLM 只负责它擅长的——写得深、写解读散文。

## 4. 分节设计

### 4.1 采集层——事实与 URL 绑定（链路起点，地基）

- `collection_pipeline.collect` 返回**带 URL 标记的分段文本**（非 merged blob）。最小改法：每段正文前加可见来源标记，例如 `【来源: https://...】\n<正文>\n\n【来源: ...】\n<正文>`。
- `collector._extract_profile` 把带标记文本喂给 LLM；`COLLECTOR_EXTRACT_SYSTEM` 新增要求：每个 feature/pricing tier/review/update 都填它来自的【来源】URL 到既有 `source_url` 字段。
- **不动 profile.py 的 schema 结构**（feature_tree/pricing/user_reviews 是课题指定知识契约，source_url 字段已存在，仅填充）。

### 4.2 analyzer——source_urls 透传 + 代码兜底

- **prompt 出**：`ANALYZER_SYSTEM` JSON 模板给每个维度（positioning/business_model/operations/user_sentiment/feature_matrix/swot）补 `source_urls` 字段，要求 LLM 填引用 fact 对应的 source_url。
- **代码兜底（关键）**：`analyzer.py::_normalize` 加一步——从传入 profiles 按竞品聚合所有 fact 的 source_url，若 LLM 输出某维度 source_urls 为空，则用该竞品 profile 的 URL 集合兜底回填。消除「默认空静默掩盖遗漏」。
- **溯源粒度 trade-off**：做到**维度级 + 竞品级**溯源（「该维度对 X 竞品的分析来自这些 URL」），不追 per-entry（每条结论独立 source 需改 analysis schema 结构 + 大改 prompt，留作未来增强）。已远好于现状（全空），可支撑前端溯源跳转。

### 4.3 writer——机械下沉 + 透传

- **report schema 加字段**（FinalReport，**全部带默认值** `default_factory`，避免 LLM 漏填致 `FinalReport(**result)` 先 ValidationError）：
  - `swot: Swot`、`radar_scores: list[RadarScore]`、`feature_matrix: list[FeatureMatrixEntry]`——全部**复用 analysis 的类型**。
  - `ReportSection` 加 `dimension` 字段，**默认值 `"overview"`**，枚举对齐 analysis 真实字段名：`positioning/feature_matrix/business_model/operations/user_sentiment/swot/overview`。
- **代码机械透传**（writer.py，在 `FinalReport(**result)` 之后、return 之前）：`report.swot = analysis.swot`、`report.radar_scores = analysis.radar_scores`、`report.feature_matrix = analysis.feature_matrix`。结构化产物由代码直接搬，100% 不丢；LLM 只写 sections 散文和 executive_summary。
- **机械下沉 source_refs**：writer.py 按 `section.dimension` 经固定映射字典取 analysis 对应维度 `source_urls`，填进 `section.source_refs`；`overview` 段聚合全部 URL。不靠 LLM 猜标题。
- **action_item.source_urls（诚实边界）**：无法机械保证（action_item 是 LLM 推理建议，对应证据只有 LLM 知）。处理：prompt 要求 LLM 从「已有 analysis source_urls 池」挑引用，**代码过滤**剔除不在池里的 URL（防幻觉 URL）。能过滤幻觉、不能保证非空 → inspector 对它只软查。
- **prompt 思考式 + 删截断**：`WRITER_SYSTEM` 去「50-150 字」，改要求展开论证/交叉对比/量化；删 writer.py:41-42 的 8000 截断。

### 4.4 inspector——程序化硬查 + 反馈路由修复

- **补程序化硬查**（`_programmatic_checks`，确定性）：
  - SWOT 存在性：四象限至少各 1 条（补 prompts.py:91 声称查实际没查的缺口）。
  - 雷达存在性：每个竞品有一条 radar_score（需 inspect 额外接收竞品名单做 cardinality 检查）。
  - feature_matrix 存在性：非空。
  - 维度级溯源：每个有内容的 section，其 `source_refs` 非空（第 4.1~4.3 打通后可稳定满足）。
  - action_item source_urls：**软查**，缺失记 `minor`，不强制（机械上保证不了，硬查会逼成假闭环）。
- **修反馈路由假闭环**：
  - 方案 C 让溯源/SWOT/雷达/feature_matrix 由代码在 analyzer/writer 阶段机械保证，inspector 硬查正常流程下直接通过，几乎不触发打回 analyzer。
  - 保险起见仍修路由：`should_continue` 增加对 `analyzer` 识别，analyzer 类问题打回 analyzer 节点（graph 加 analyzer 回边）。即使触发也回到能修的节点，非假闭环。
  - **pass/fail 改 severity 分级**：只有 critical/major 阻断，minor（如 action_item 溯源）不阻断 pass（改 inspector.py:82 判定逻辑，谨慎不让真缺陷漏过）。

### 4.5 focus_area 打通 + 前端呈现 + 已知 trade-off

- **focus_area 打通**：collector 把 `goal` 写进 graph state（state.py 加 `analysis_goal`）→ writer_node 回填 `report.metadata.analysis_goal`（与现有 data_sources 回填同处，builder.py:56-62）。`COLLECTOR_GOAL_SYSTEM` 默认值补 focus_area 提炼要求；用户确实没提时合法为空，inspector 只软查（inspector 拿不到原始 input，不能硬判该不该空）。
- **前端呈现**：前端当前只渲染 sections/action_items/metadata（app.py:70/89-95），需加：SWOT 四象限、雷达图、功能矩阵表、section 的 source_refs 可点击溯源链接。这是结构完整度（35%）+ 业务价值（20%）的演示落点。

## 5. 已知 trade-off（显式记录，不在本轮解决）

- **删截断的 token/超时风险**：`llm_client` 无 max_tokens、超长输入「迷失在中间」可能损害引用准确率。Cooper 已拍板全传（256K context），记为已知风险，验证阶段实测观察，必要时回调。
- **溯源粒度**：维度+竞品级，不追 per-entry。课题「每条结论可溯源」打折扣，但远好于现状。
- **per-entry 溯源、action_item 强制溯源**：留作未来增强。

## 6. 验收标准（Cooper 确认的四项）

| 验收项 | 由哪节保证 | 可量化指标 |
|---|---|---|
| 质检硬伤归零 | 4.4 硬查 + 真闭环 | quality_score 稳定 ≥ 0.7、不耗尽重试 |
| 报告可读丰满度 | 4.3 prompt 思考式 + 删截断 | 人读 + inspector 软评 |
| 结构完整度 | 4.3 透传 SWOT/雷达/矩阵 + 4.5 前端 | 最终报告含 SWOT/雷达/功能矩阵，前端可见 |
| 溯源可信度 | 4.1~4.3 贯穿绑定链 | section source_refs 覆盖率（有内容 section 100% 有源） |

## 7. 范围边界

- **不改** profile.py 的知识 Schema 结构（课题指定契约）。
- **改** collection_pipeline.py（原「Phase 2」约束作废——溯源根因在此，Cooper 已同意「溯源为脉」重排）。
- 一轮实现，不再分阶段。

## 8. 对抗审查留痕

- 第一轮（单模型 general-purpose）：揭示「analysis source_urls 恒空、断点在 analyzer 不在 writer」「section 无匹配锚点」「反馈路由不含 analyzer」。
- 第二轮（Codex gpt-5.5 跨模型，20 条命中）：进一步揭示「事实-URL 在 collector 即未绑定、正文 merge 成无锚点 blob」「维度级 source 不满足每条结论溯源（#4）」「FinalReport 必填字段先于 transfer 校验（#7）」「severity 不影响 pass/fail（#11）」「feature_matrix 缺结构化承接（#17）」「前端未渲染新字段（#20）」等。方案 C 的分节设计逐条吸收。
