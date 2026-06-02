# 数据源拓展设计

> 日期：2026-06-03
> 状态：设计待评审
> 方法论：brainstorming → doubt-driven（三节各一轮单模型 + Codex 跨模型对抗审查）

## 1. 背景与问题

当前采集（`src/agents/collector.py:12-20`）只有 3 个硬编码、对所有竞品一刀切的数据源：

| 源 | URL 模板 | 问题 |
|---|---|---|
| `itunes_api` | iTunes Search API | 场景错配：硬件竞品搜到同名 App；仅适合 SaaS/App |
| `bing_search` | Bing 搜索页 | **抓 SERP 摘要而非正文**，信噪比低 |
| `sogou_search` | 搜狗搜索页 | 同上，反爬更激进 |

**质量低的首要根因**：Bing/搜狗抓的是搜索结果页（SERP）HTML，不是竞品官网/文档正文。最权威的一手信息（官网功能页、定价页、帮助文档）根本没抓。

## 2. 目标与约束

**目标**：兼顾 SaaS + 硬件两类竞品，提升采集质量与覆盖。

**关键决策**（与 Cooper 对齐）：
- 两步走：**搜索 → 正文页**（质量提升主线）
- 搜索用**专业搜索 API**（带 key），默认实现 **SerpAPI**
- 正文页用 **LLM 选页**（带规则兜底 + 独立短超时）
- 结构化专源**按 category 路由、可插拔**
- 抓后加**轻量启发式质量闸门**
- 无 key 时降级走**专源 + 官网近似**，**绝不退回 SERP 抓取**

**契约（不可破）**：
- 不破坏现有 51+ 测试，尤其 4 个集成测试硬编码的 **6 步 `call_json` 序列**（parse_goal→classify→extract→analyzer→writer→inspector）
- `build_graph(llm, http, parser, trace_writer)` 签名不变；`routes.py` 创建/关闭 `HttpClient` 的方式不变
- 新配置全部可选，import 时绝不抛错
- 降级绝不阻塞核心分析、绝不让单竞品失败拖垮全局
- 可观测性辅助、不阻塞主流程
- YAGNI；手写透明逻辑优先于框架魔法

## 3. 架构

### 3.1 分层

```
CollectorAgent (agent)  →  CollectionPipeline (tool)  →  sources (插件)
```

`CollectionPipeline` 是 collector 的 tool 依赖，与 `LLMClient`/`HttpClient` 同级。装配在 `builder.py`：

```python
# builder.py（http/parser 下沉给 pipeline，build_graph 签名不变）
pipeline  = CollectionPipeline(llm=llm, http=http, parser=parser, registry=...)
collector = CollectorAgent(llm=llm, pipeline=pipeline)
```

`routes.py` 创建 `http`/`llm`/`parser` 的方式不动；`build_graph` 仍收 `http`/`parser`，在内部转交 pipeline。

### 3.2 单竞品采集流程

```
parse_goal (已有)
   │ 每竞品并行（pipeline 实例级 Semaphore 限并发；非 global）
classify_competitor (已有，6步序列之一，保留)
detect_category (新，零 LLM：规则匹配 category/name/company，缺失→default)
   │
CollectionPipeline.collect(name, category, goal):
   ├─ 有 key（search_provider.available()）:
   │    ① SerpAPI search(query)  （URL 编码；key 走 header 不走 query）
   │    ② LLM 选页 asyncio.wait_for(llm.call_json(...), PICK_LLM_TIMEOUT)
   │         超时/错 → 规则打分（域名+路径关键词，零 LLM）
   │    ③ 并行抓正文（每页 wait_for 超时；per-domain 锁；http.get None 容错）
   │    ④ 质量闸门 quality_gate（逐页过滤软404/验证页/过短）
   ├─ 无 key: 跳过搜索主线（不退 SERP），仅走专源
   └─ 并行: 按 category 路由的可插拔专源（每源 wait_for 超时 + gather return_exceptions）
   │
   合并: 过闸门内容页 + 专源结果 → URL 去重
        → sources[] 仅含真正喂 LLM 的内容页 URL
          （搜索 endpoint / 被丢候选 / 含 key URL 一律排除）
   │
   全空? → _build_placeholder_profile()（不调 LLM；completeness 显式 0.0；data_sources=[]）
   否则  → _extract_profile (已有)
   │
   pipeline_trace 写入 profile.metadata.pipeline_trace（不碰 builder 的 node_trace）
```

### 3.3 文件结构（3 模块，不过度拆分）

```
src/tools/sources.py          # iTunes 专源 + SerpAPI 搜索源 + 极简 DataSource 基类 + 按 category 取源函数
                              #   - 只实现 SerpAPI（不做 provider 抽象；换 provider 是未来扩展）
                              #   - SerpAPI key 走 header；无 key → available()=False
src/agents/collection_pipeline.py  # 编排 search→选页→fetch→闸门 + 专源并行 + 去重 + 全空占位
src/tools/quality_gate.py     # 纯函数闸门
```

### 3.4 collector.py 变化

- 删 `URL_TEMPLATES`/`_fetch_and_parse`/`_parse_itunes`（迁入 `sources.py`）
- 构造器 `(llm, http, parser)` → `(llm, pipeline)`
- 新增 `detect_category`（**零 LLM**：规则匹配，缺失归 default）
- `_collect_single` 改调 `pipeline.collect(...)`
- 新增 `_build_placeholder_profile`（全空时用，completeness=0.0）
- 顶层 `collect()` 改 `asyncio.gather(..., return_exceptions=True)`：**单竞品失败产占位、其他继续**（语义变更，见 §5）

### 3.5 配套改动

| 改动 | 文件 |
|---|---|
| `ProfileMetadata` 显式加 `pipeline_trace: list = Field(default_factory=list)` | `schemas/profile.py` |
| `HttpClient` 加 `get_json(url, headers)`：headers 局部传参不碰共享字典；复用 `_rate_limit`；UA 也用局部 header 或加锁；现有 `get(url)` 不动 | `tools/http_client.py` |
| http 日志对 URL 做 key 脱敏 | `tools/http_client.py` |
| 选页超时用外层 `asyncio.wait_for`，**不改 `call_json` 签名** | `collection_pipeline.py` |

### 3.6 配置项（全可选，import 不抛）

```python
SEARCH_API_KEY = os.getenv("SEARCH_API_KEY", "")            # 空 → available()=False → 降级
SEARCH_TOP_N = int(os.getenv("SEARCH_TOP_N") or "3")        # 选页上界
PICK_LLM_TIMEOUT = int(os.getenv("PICK_LLM_TIMEOUT") or "20")
MAX_FETCH_CONCURRENCY = int(os.getenv("MAX_FETCH_CONCURRENCY") or "5")  # pipeline 实例内惰性创建 Semaphore
```
不引入 `SEARCH_PROVIDER`——只实现 SerpAPI，换 provider 各家响应格式不同必须写新 parser，列入未来扩展。

## 4. 降级路径（每竞品独立，绝不阻塞）

```
搜索主线（SerpAPI）:
  available()==False（key 空） → 跳过主线，仅专源（不退 SERP）
  search() 抛错/429/超时       → warning，跳过主线
  候选为空                     → 跳过
  LLM 选页超时/错              → 退回规则打分（零 LLM）
  抓正文每页独立容错 + 质量闸门逐页过滤

专源: detect_category（零 LLM）→ 按 category 取源 → 每源 wait_for 超时 + gather(return_exceptions)

合并全空 → _build_placeholder_profile（不调 LLM，completeness=0.0，data_sources=[]）

顶层 collect(): return_exceptions=True，单竞品失败 → 占位 profile，其他竞品继续
```

**关键自洽点**：LLM 选页**仅在有 key 且走搜索主线时发生**。集成测试环境无 key → 走专源降级 → collector 内仍只有 classify + extract 两次调用 → **6 步序列天然保持不破**。

## 5. 语义变更声明

**顶层 `collect()` 由"快速失败"改为"部分降级"**：
- 现状（`collector.py:166`）：`asyncio.gather` 无 `return_exceptions`，单竞品异常 → 整个 run failed。
- 新语义：`return_exceptions=True`，单竞品彻底失败 → 产 completeness=0.0 占位 profile，其余竞品正常产出。
- 理由：多竞品场景下一颗老鼠屎不该坏一锅汤；质检会诚实反映占位 profile 的低质量。
- 影响：需改对应集成测试断言（原本期望全失败的场景，现期望部分成功 + 占位）。

## 6. 测试策略

| 测试 | 内容 |
|---|---|
| `test_quality_gate.py`（新，纯函数） | 软404/验证页/过短→丢弃；正常→保留 |
| `test_sources.py`（新） | **iTunes**：null description/空 results/非法 JSON 三边界；**SerpAPI**：mock 解析、无 key→available()=False、429+超时→优雅空、**key 走 header 不进 query** |
| `test_collection_pipeline.py`（新） | 有 key 全流程 / 无 key 降级 / 全空占位 / 选页超时退规则 / URL 去重 / Semaphore 实例级行为（两 pipeline 并发不互相阻塞）/ **闸门集成**（软404页不进 sources 不进抽取）/ **sources 不含含-key URL 负向断言** / 单源 hang 被超时切断 |
| `test_collector.py`（改） | 构造器 `(llm, pipeline)`（改 :17/:29/:52）；mock pipeline；`detect_category` 零 LLM 验证 |
| `test_config.py`（新，轻量） | 新配置缺失不抛；`int()` 容错 |
| 集成测试（改） | 多竞品部分失败（A 成 B 崩 → B 占位、A 正常到 analyzer/writer）；抽取校验失败降级；6 步序列断言保持 |

**回归底线**：现有 51+ 全绿；6 步 `call_json` 序列在无-key 路径下不变；`node_trace[:4]` 断言不破（pipeline_trace 与 node_trace 完全分离）。

## 7. 未来扩展（backlog，本轮不实现）

- **搜索 provider 可换**：抽象 provider parser，支持 Bing/Brave/Google CSE（各家响应格式不同需各写 parser）
- **专业竞品平台接入**（来自 `docs/竞品分析数据来源.md`）：SimilarWeb/七麦/data.ai（流量榜单）、新榜/西瓜（新媒体）、百度指数/Google Trends（舆情热度）。当前均因反爬/需登录/付费/场景不对口，不具备自动化接入条件，作为专源插件 backlog 体现架构通用性。
- **舆情/热度维度**：Schema 当前偏静态（功能/定价/画像），Google Trends 类"相对热度"是 Schema 层扩展，超出本轮数据源范围。

## 8. doubt-driven 审查记录

三节设计各经一轮 doubt-driven（单模型 + Codex gpt-5.5 跨模型对抗审查），累计捕获并修正的实质问题：

- **架构层（第1节）**：路由原语用错（误用 competitor_type 当 SaaS/硬件类别）、node_trace 闭包拿不到、sources 密钥泄露、无 key 降级退回 SERP 的合规风险、全空幻觉 profile。
- **模块层（第2节）**：detect_category LLM 兜底击穿集成测试、PICK_LLM_TIMEOUT 在现有 call_json 下不可执行、ProfileMetadata 装不下 pipeline_trace、get_json 共享 header 污染、抽象拆太碎 + provider 可配置是假承诺（瘦身为 3 模块 + 只实 SerpAPI）。
- **降级层（第3节）**：全空 stub 自相矛盾 + completeness 实为 0.3、LLM 选页是 happy path 必走的新增调用顶垮 6 步序列（→ 用无 key 路径自洽解决）、顶层快速失败语义被悄悄改写（→ 显式声明改为部分降级）、专源缺独立超时仍阻塞、闸门/安全缺集成与负向测试。

累计三轮零 doubt theater（每轮均有 actionable 修正）。
