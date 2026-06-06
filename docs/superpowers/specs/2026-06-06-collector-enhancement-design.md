# 采集能力增强设计（P1 超时 + P2 递补/抓取加固 + TavilySource 可切换）

> 日期：2026-06-06
> 状态：设计已确认，待 writing-plans 拆实现计划
> 背景文档：`docs/数据采集问题诊断与改进方向-临时.md`（诊断 + 方案评估）

## 一、目标与范围

提升采集层「有没有料」——当前末端转化率 ≈ 5%（20 候选 → 1 个有效正文），是报告质量的绝对天花板。本 session 做三项，全部落在采集管线内。

**范围内（三项）：**
- P1：选页 LLM 超时调长
- P2：递补机制 + 抓取层加固
- TavilySource：可切换的高质量搜索源

**明确排除：**
- P7 候选完整落盘（开发者诊断用，对最终报告无直接贡献；Cooper 只关心结果好坏，不做搜/选归因）
- 第二档：P4 detect_category 修正、P5 规则选页减分、P6 质量闸门语义判断
- 第三档：追问式输入、竞品发现、市场分析层 Schema

**不变的契约：**
- `CollectionPipeline.collect()` 返回签名 `(merged_text, sources, trace, labeled_text)` 不变
- `CompetitorProfile` schema 不变
- graph 编排逻辑不变（节点、边、`should_continue` 路由不动）
- 前端不动

**需要触及但属本设计范围内的改动（doubt-driven 修正）：**
- `build_graph`（`builder.py:15-22`）的 **source 装配处**要按 `SEARCH_PROVIDER` 选注入 `SerpApiSource` 还是 `TavilySource`——这是函数体内的依赖装配，不是 graph 编排，编排逻辑仍不动。原 spec「graph 不动」表述过宽，此处修正。
- `tests/unit/test_config.py` 现硬断言默认值（`SEARCH_TOP_N==3`、`PICK_LLM_TIMEOUT==20`）；改默认值必须同步更新这些断言（见第八节）。原 spec「139 测试不破」需理解为「同步更新受影响断言后全绿」，而非「零测试改动」。

## 二、P1 选页超时调长

**问题**：`PICK_LLM_TIMEOUT=20s`（`config.py:27`）< Doubao 选页实际耗时（实测飞书 68s）。超时即退化成只看 URL 的规则选页，选中法务页（`feishu.cn/legal/pricing-adjustment` 含 "pricing"）。

**改动**：`PICK_LLM_TIMEOUT` 默认值 `20 → 45`。

**取舍说明**：只调长数值，不动选页逻辑。45s 是权衡——调太长（70s）会让每个竞品都被慢页拖住；45s 接住大部分中等延迟的返回，仍超时的退规则选页（行为不变）。

**诚实边界（doubt-driven 修正）**：实测飞书选页要 68s，45s 救不了这种极端慢的 case——它仍会超时退规则选页。45s 只改善「中等延迟」场景；极端慢 case 的真正解法是切 `SEARCH_PROVIDER=tavily`（Tavily 直接返回正文、根本不走选页这一跳）。规则选页减分兜底（P5）属第二档，本 session 不做。手写管线选页慢可接受（它退居「答辩讲工程深度 + 兜底」角色，极端 case 由 Tavily 兜）。

## 三、P2 递补机制 + 抓取层加固

### (a) 抓取层加固（`http_client.py::get`）

**问题**：现在非 200 直接返回 None（`http_client.py:71`），知乎 403、瞬时超时都一发即弃。

**改动**：区分故障类型重试。
- 超时 / `httpx.ConnectError` / 5xx → 重试 1 次（共 2 次尝试）
- 403/404 等 4xx → 直接返回 None，不重试（明确拒绝/不存在，重试无意义）

改动局部在 `get()` 方法内。`get_json()`（API 端点）不动。

**UA 与并发共享状态（doubt-driven 修正）**：`get()` 每次调用已 `_rotate_ua()`（`http_client.py:67`），重试**复用现有轮换**即可（重试也是一次 `get` 逻辑，自然换 UA），不新增重复轮换逻辑（守 CLAUDE.md 手术式修改）。注：`_rotate_ua` 改的是共享 `AsyncClient.headers`，并发 `_fetch_clean` 下本就存在 UA 互相覆盖——这是**既有行为**，现有测试通过、非本次新增风险，本 session 不动（要彻底解决需 per-request headers，属另一课题）。

### (b) 递补机制（`collection_pipeline.py::collect` 搜索主线段，`:124-141`）

**问题**：选页选出 top3，并发抓这 3 个；挂了/低质不补。SerpAPI 返回的 10 条候选里第 4+ 条可能是好页，根本没抓。

**改动**：从「抓固定 top3」改为「凑够 N 个有效正文就停」。
- N 取 `SEARCH_TOP_N`，默认值 `3 → 5`
- **候选池排序（doubt-driven 修正）**：`_llm_pick` 现只返回 ≤ top_n 个 URL（`collection_pipeline.py:71,83`），第 4-10 条无 LLM 排序信息。候选池构造 = LLM 选中的按其顺序在前 + 其余候选按 SerpAPI 原始返回顺序兜底在后。规则选页路径同理（rule_pick 排序在前 + 其余兜底）。这样既不改选页 LLM contract，又能用上全部 ~10 条。
- **并发批次**策略：
  1. 从候选池**按序**取一批并发 `_fetch_clean`。批大小 = `min(还差的数量 + 2, MAX_FETCH_CONCURRENCY)`——`MAX_FETCH_CONCURRENCY=5` 的 semaphore（`collection_pipeline.py:88`）本就限流，批大小只控「取多少候选」，实际并发由 semaphore 兜底
  2. 过质量闸门、且 URL 不在 `seen_urls` 的，计入有效正文（**沿用现有 `seen_urls` 全局去重**，`:115`；凑数按去重后实际入库数算，不是按尝试数）
  3. 有效正文（去重后）≥ N → 按候选池排序取前 N 个，停
  4. 不够且候选池还有 → 再按序取下一批并发抓
  5. 候选池耗尽 → 用现有的（可能 < N，合理降级）
- 零额外 SerpAPI 成本（都在已返回的候选里挑）

**403 快速耗尽是预期降级（doubt-driven 修正）**：若候选多为强反爬站点（知乎类 403），递补会快速耗尽候选却凑不够 N，最终拿到 < N 条——这是合理降级路径，需有测试覆盖。

**取舍说明**：并发批次 vs 串行。抓网页是慢操作，并发对总耗时影响大。并发批次保住并发速度，代价是「够了之后这批里多抓的几条白抓」——但候选就 10 条、零 API 成本，浪费可忽略。串行虽零浪费但丢了并发、慢，不选。

## 四、TavilySource 可切换

### 接口与关键区别

Tavily = 为 LLM 设计的搜索 API，一次调用返回「结果 + 每条清洗后正文」，吃掉「搜索→选页→抓取→清洗」整条主线。

- `SerpApiSource.search()` 只返回候选 `[{url,title,snippet}]`，正文靠后续选页+抓取
- `TavilySource` 直接返回带正文的结果，**不需要选页和抓取**

所以 Tavily 不是简单替换 `search_source`，它替代的是整条搜索主线。

**实现方式锁定（doubt-driven 修正）**：`TavilySource` 用现有 `HttpClient.get_json` 调 Tavily REST API，**不引入 Tavily SDK**（守「三项改动 only」、不动 `requirements.txt`）。鉴权用 `api_key` 走 query 参数（与现 SerpAPI 同模式），日志由 `_redact_key` 脱敏；这样规避「需给 HttpClient 加 POST」和「body 里的 key 脱敏不到」两个问题。Tavily REST 支持 GET + api_key query 的调用形式，具体端点/参数实现时按官方文档核对（走 source-driven）。

### 切换语义（配置开关二选一）

- `config.py` 加 `SEARCH_PROVIDER`（`serpapi` / `tavily`），默认 `serpapi`（保持现状）。**非法/空/大小写混用值一律回落 `serpapi`**（守 config.py 既有「非法值不崩」约定，`config.py:7`）
- **注入分叉在 `build_graph`（`builder.py:15-22`）**：按 `SEARCH_PROVIDER` 决定构造 `SerpApiSource` 还是 `TavilySource` 注入 pipeline。`collect()` 内对 `search_source` 用鸭子类型/能力判断走不同主线，不读全局 config（保持 pipeline 对 config 的现有解耦）
- `collect()` 搜索主线段按 source 类型分叉：
  - serpapi → 现有「搜索→选页→递补抓取」（含本次 P1/P2 改进）
  - tavily → 调 `TavilySource` 直接拿带正文结果，跳过选页和抓取
- **Tavily 正文仍过 `quality_gate.is_low_quality`（doubt-driven 修正）**：保持「有效正文」语义一致，挡掉空正文/摘要/错误页
- **Tavily 结果沿用 `seen_urls` 去重（doubt-driven 修正）**：与 iTunes 专源撞 URL 时，先到先得（搜索主线先于专源执行，与现有顺序一致）
- 两条路结果都汇进同一套 `_add(text, url)` / `sources` / `labeled_text`，**下游消费方零改动**
- iTunes 专源在两条路下都照常并行（不受开关影响）
- 加 `TAVILY_API_KEY` 配置项；选 tavily 但无 key 时降级（参照现有 SerpAPI 无 key 逻辑：跳过搜索主线、仅走专源）
- **trace（doubt-driven 修正）**：tavily 路径产生新 step（如 `{"step":"tavily","results":N}`）。`trace` 是 `list[dict]`、前端追溯面板按原样展示 dict，新增 step 不破坏渲染、无需改前端

### 答辩底线（来自背景文档第五节）

1. 可切换是真切换：两条源都真能跑、有测试，不是 Demo 摆设
2. 答辩坦诚讲选型：大方讲「自建合规管线 vs AI 搜索 API 外包」的工程判断
3. 手写管线该修还得修：有 Tavily 兜底也要修 P1/P2 硬伤，否则带 bug 讲管线会露馅

## 五、对既有决策的修正

**DECISIONS 06-03「只做 SerpAPI，不做 provider 抽象」**：本次部分修正。当年理由是「各家响应格式不同，配置切换是假承诺」。本次加 Tavily 并列不是零成本，但 Tavily 与 SerpAPI 的差异恰好清晰（要不要自己抓正文），抽象边界比当年清楚，值得做。实现后在 DECISIONS 记录此修正。

## 六、配置项汇总

| 配置项 | 现状 | 改后 | 说明 |
|---|---|---|---|
| `PICK_LLM_TIMEOUT` | 20 | 45 | P1 |
| `SEARCH_TOP_N` | 3 | 5 | P2 目标有效正文数 N |
| `SEARCH_PROVIDER` | 无 | 新增，默认 `serpapi` | Tavily 切换 |
| `TAVILY_API_KEY` | 无 | 新增，默认空 | Tavily 鉴权，走 .env |

## 七、安全

- `TAVILY_API_KEY` 只存本地 `.env`（`.gitignore` 已覆盖），不进对话/代码/git
- Tavily 鉴权走 `api_key` query 参数，复用 `HttpClient._redact_key` 脱敏（已在第四节锁定 GET 实现）
- 沿用既有取向：密钥日志脱敏、httpx 日志压 WARNING

## 八、测试要点

- **同步更新 `test_config.py`（必做）**：现断言 `SEARCH_TOP_N==3`、`PICK_LLM_TIMEOUT==20`（`test_config.py:26-27`），改默认值后这两条断言要同步改为 5 / 45，否则直接红
- P1：新默认值 + 可被环境变量覆盖
- 抓取加固：超时/5xx 触发重试、403/404 不重试（mock 响应）
- 递补：批次凑数逻辑（部分抓挂时从候选池补足、**403 快速耗尽候选时降级到 < N**、候选耗尽降级）；候选池排序（LLM 选中在前 + 其余兜底）；`seen_urls` 去重后凑数
- 非法 `SEARCH_PROVIDER` 回落 `serpapi`
- TavilySource：带正文结果解析 + 过 quality_gate + api_key query 脱敏；无 key 降级
- `collect()` 按注入的 source 类型正确分叉（serpapi / tavily 各一条集成路径）
- **真实可跑验收（CONTRACT #6，doubt-driven 修正）**：单测用 mock 响应；「真能跑通真实 Tavily API」由本地配真 key 跑一次、留 `runs/<trace_id>` trace 为证（与历史 SerpAPI 验收方式一致），不进 CI
- 全量回归：受影响断言同步更新后，全部测试全绿（非「零测试改动」）
