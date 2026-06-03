# 数据源拓展真实跑通验证 — 设计文档

日期：2026-06-03
关联：`docs/superpowers/specs/2026-06-03-datasource-expansion-design.md`（被验证对象）

## 背景与定位

上一 session 把采集层从「collector 内 3 个硬编码 URL 源」重构为分层管线
`CollectorAgent(agent) → CollectionPipeline(tool) → sources(插件)`，117 个单元/集成测试全绿。

**本次验证的定位 = 端到端真实环境冒烟，不是补单测。**

- 逻辑分支（无 key 跳过、LLM 选页、超时退规则、畸形 JSON 退规则、软 404 过滤、去重、并发不串名、
  iTunes 解析/空壳跳过、SerpAPI key 走 header、category 路由、占位 profile、rate limit per-domain 锁、
  key 脱敏）**已被 117 个单测确定性覆盖**，本次不重复。
- 本次只验 mock 测不到的东西：真实 LLM + 真实 iTunes/SerpAPI + 真实网页下，
  逻辑是否仍成立、产物是否合理、外部数据源契合度如何。

判定证据来源：**落盘产物 `runs/<trace_id>/01_profiles.json` 的 pipeline_trace + sources**，
辅以 `runs/<trace_id>/run.log` 日志（不看运行内对象，顺带验证 pipeline_trace 序列化不丢字段）。

## doubt-driven 捕获的关键盲点（已并入方案）

经单模型 + Codex(gpt-5.5) 跨模型对抗审查，修正原方案以下盲点：

- **B1 import 固化**：`settings = Settings()` 在 import 时读环境变量。改 `.env` 后**必须重启 uvicorn**，
  否则运行时仍是旧值（无 key）。验证前先确认 key 真的进了运行时。
- **B4 主线成败混淆**：SaaS 场景下 iTunes 专源也产 source URL，「sources 非空」证明不了搜索主线成功。
  必须**按 pipeline_trace 区分哪些 URL 来自 `pick`(主线)、哪些来自 `pro_source`(专源)**。
- **B5 外部 vs 逻辑失败归因**：真实跑失败可能是 429/反爬/quota/空结果，非代码逻辑问题。
  失败时**按 pipeline_trace 的 step 定位失败发生在哪一步**，区分归因。
- **B3 溯源断链隐患**：iTunes 记录可能 `text` 非空但 `trackViewUrl=""`——内容进 merged_text 喂 LLM，
  但空 URL 不进 sources，造成「用了来源却不可溯源」。真实跑时盯一眼此现象（与报告质量课题②同源）。
- **B2 「没发生」的观测**：无 key 路径靠 `run.log` 确认没有 search/pick LLM 日志，而非只看 trace 写了 search_skipped。
- **B6 SerpAPI 配额**：免费约 100 次/月，路径 B 限定跑 1–2 次，确认主线触发即止。
- **B7 iTunes 数据不稳定**：同名 App/空结果/区域差异 → flaky。选语雀/飞书（中国区确有上架）降低风险，
  但接受「跑出来内容可能弱」，不把 iTunes 内容当稳定事实。

## 验证场景

| 场景 | 竞品组 | 路由 | 验证目标 |
|------|--------|------|----------|
| 主组 SaaS | 语雀 vs 飞书文档 | saas→iTunes | A 降级主路径 + B 搜索主线 |
| 补充硬件 | 小米 vs OPPO | default→空 | A' 全空兜底边界 |

## 验证路径与判定标准

### 路径 A：SaaS 无 key（先跑，零成本）

前置：`.env` 不配 `SEARCH_API_KEY`，正常 `uvicorn` 启动。

跑语雀 vs 飞书文档，查 `01_profiles.json` 的 `pipeline_trace` + `sources`：

1. trace 出现 `{step: search_skipped, reason: no_api_key}`（正确跳过主线）。
2. trace `route` step 显示 `pro_sources: [itunes]`（saas 路由正确）。
3. trace `pro_source` step `results > 0`，`sources` 含真实 `trackViewUrl`，profile 非空壳。
4. **盯 B3**：检查是否有 iTunes 内容进了 merged_text 但对应 URL 为空（记录现象，供课题②）。
5. **看 `run.log`（B2）**：无 `[pipeline] search` / LLM 选页日志（确认主线真的没跑）。

### 路径 A'：硬件无 key（验边界）

跑小米 vs OPPO，查 `01_profiles.json`：

6. trace `route` 显示 `pro_sources: []` + `search_skipped`。
7. 产 `completeness_score=0.0` 占位 profile，`data_sources=[]`。
8. **看 `run.log`**：collector 无 extract 调用日志（占位路径不调 extract LLM，防幻觉）。

### 路径 B：SaaS 有 key（配好后跑，省配额）

前置：`.env` 加 `SEARCH_API_KEY`，**重启 uvicorn**（B1），先确认 key 进了运行时（日志/trace 出现 search step）。
**限定跑 1–2 次**（B6）。

跑语雀 vs 飞书文档，查 `01_profiles.json` 的 `pipeline_trace`：

9. trace 出现 `search → pick(method=llm 或 rule_fallback) → pro_source` 序列。
10. **按 trace 区分来源（B4）**：`pick` step 的 `picked` URL = 主线贡献；`pro_source` = 专源贡献。
    主线至少 1 个网页正文过质量闸门进入 sources。
11. **失败归因（B5）**：若主线无产出，按 trace step 定位失败在 search / pick / fetch 哪一步，
    区分是外部环境（429/反爬/空结果）还是逻辑问题。

## 接受不验（已有单测覆盖或成本不划算）

- **timeout fallback**（T1）：真实 LLM 大概率一次成功，打不到超时分支；已有
  `test_llm_pick_timeout_falls_back_to_rule` 确定性覆盖。
- **并发不串名**（B8）：已有 `test_concurrent_collect_no_name_crosstalk` 确定性覆盖；
  真实跑一次证明不了无竞争，仅附带观察。
- **quality gate 过滤 / rate limit per-domain 竞态 / category 归一化变体 / key 多路径脱敏**（T2）：
  均有单测覆盖，本次端到端不重复。
- **部分降级「一成一败」**（T3）：有价值但需构造，列为可选，主验通过后再补。
- **writer/inspector 的 source_refs/SWOT/focus_area/quality_score**：属报告质量课题②，本次明确排除。

## 执行顺序

1. 路径 A（SaaS 无 key）→ 立即跑，拿降级路径真实结果。
2. 路径 A'（硬件无 key）→ 同一无 key 环境顺带验边界。
3. 路径 B（SaaS 有 key）→ Cooper 配好 SerpAPI key 并重启后跑，验主线。

每个场景跑完记录 trace_id，结论写回 `PROGRESS.md`。
