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
- graph / 前端 不动

## 二、P1 选页超时调长

**问题**：`PICK_LLM_TIMEOUT=20s`（`config.py:27`）< Doubao 选页实际耗时（实测飞书 68s）。超时即退化成只看 URL 的规则选页，选中法务页（`feishu.cn/legal/pricing-adjustment` 含 "pricing"）。

**改动**：`PICK_LLM_TIMEOUT` 默认值 `20 → 45`。

**取舍说明**：只调长数值，不动选页逻辑。45s 是权衡——调太长（70s）会让每个竞品都被慢页拖住；45s 接住大部分正常返回，仍超时的退规则选页（行为不变）。规则选页减分兜底（P5）属第二档，本 session 不做。既然 Tavily 做主力出片，手写管线选页慢可接受（它退居「答辩讲工程深度 + 兜底」角色）。

## 三、P2 递补机制 + 抓取层加固

### (a) 抓取层加固（`http_client.py::get`）

**问题**：现在非 200 直接返回 None（`http_client.py:71`），知乎 403、瞬时超时都一发即弃。

**改动**：区分故障类型重试。
- 超时 / `httpx.ConnectError` / 5xx → 换 UA 重试 1 次（共 2 次尝试）
- 403/404 等 4xx → 直接返回 None，不重试（明确拒绝/不存在，重试无意义）

改动局部在 `get()` 方法内。`get_json()`（API 端点）不动。

### (b) 递补机制（`collection_pipeline.py::collect` 搜索主线段，`:124-141`）

**问题**：选页选出 top3，并发抓这 3 个；挂了/低质不补。SerpAPI 返回的 10 条候选里第 4+ 条可能是好页，根本没抓。

**改动**：从「抓固定 top3」改为「凑够 N 个有效正文就停」。
- N 取 `SEARCH_TOP_N`，默认值 `3 → 5`
- 候选池 = 选页排序后的候选列表（不止 top N，用上 SerpAPI 返回的全部 ~10 条）
- **并发批次**策略：
  1. 从候选池取一批（N + 2 条）并发 `_fetch_clean`
  2. 过质量闸门的计入有效正文
  3. 有效正文 ≥ N → 取前 N 个，停
  4. 不够且候选池还有 → 再并发抓下一批
  5. 候选池耗尽 → 用现有的（可能 < N）
- 零额外 SerpAPI 成本（都在已返回的候选里挑）

**取舍说明**：并发批次 vs 串行。抓网页是慢操作，并发对总耗时影响大。并发批次保住并发速度，代价是「够了之后这批里多抓的几条白抓」——但候选就 10 条、零 API 成本，浪费可忽略。串行虽零浪费但丢了并发、慢，不选。

## 四、TavilySource 可切换

### 接口与关键区别

Tavily = 为 LLM 设计的搜索 API，一次调用返回「结果 + 每条清洗后正文」，吃掉「搜索→选页→抓取→清洗」整条主线。

- `SerpApiSource.search()` 只返回候选 `[{url,title,snippet}]`，正文靠后续选页+抓取
- `TavilySource` 直接返回带正文的结果，**不需要选页和抓取**

所以 Tavily 不是简单替换 `search_source`，它替代的是整条搜索主线。

### 切换语义（配置开关二选一）

- `config.py` 加 `SEARCH_PROVIDER`（`serpapi` / `tavily`），默认 `serpapi`（保持现状）
- `collect()` 搜索主线段按开关分叉：
  - `serpapi` → 现有「搜索→选页→递补抓取」（含本次 P1/P2 改进）
  - `tavily` → 调 `TavilySource`，直接拿带正文的结果，跳过选页和抓取
- 两条路结果都汇进同一套 `_add(text, url)` / `sources` / `labeled_text`，**下游零改动**
- iTunes 专源在两条路下都照常并行（不受开关影响）
- 加 `TAVILY_API_KEY` 配置项；选 tavily 但无 key 时降级（参照现有 SerpAPI 无 key 逻辑：跳过搜索主线、仅走专源）

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
- Tavily 鉴权方式按其官方文档实现；若走 query 参数，复用 `HttpClient._redact_key` 脱敏
- 沿用既有取向：密钥日志脱敏、httpx 日志压 WARNING

## 八、测试要点

- P1：配置项默认值 + 可被环境变量覆盖
- 抓取加固：超时/5xx 触发重试、403/404 不重试（mock 响应）
- 递补：批次凑数逻辑（部分抓挂时从候选池补足、候选耗尽时降级）
- TavilySource：search 返回带正文结果的解析；无 key 降级
- `collect()` 按 `SEARCH_PROVIDER` 正确分叉（两条路各一条集成路径）
- 全量回归：现有 139 测试不破
