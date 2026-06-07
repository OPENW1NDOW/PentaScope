# 弃用 SerpAPI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 删除 SerpAPI 搜索源、SEARCH_API_KEY/SEARCH_PROVIDER 配置开关、collection_pipeline 的 _llm_pick/_rule_pick/_fetch_clean/_fetch_with_backfill 四方法，让 Tavily 成为唯一搜索源。

**Architecture:** 单 provider 收敛。删除"搜索→选页→抓取"两步走机制；Tavily 一次调用直返带正文 SourceResult。CollectionPipeline 构造器塌缩为只接受 search_source 参数。

**Tech Stack:** Python + LangGraph + FastAPI + Pydantic v2 + httpx + pytest（无新依赖）。

**Spec:** `docs/superpowers/specs/2026-06-07-drop-serpapi-design.md`

---

## 执行原则

1. **Commit 拓扑**：测试先改适应 Tavily（T1）→ 删生产代码（T2-T4）→ 删 SerpAPI 测试 + 改 fixture（T5）→ 文档同步（T6-T7）。每个 commit 跑 `pytest -q && ruff check src tests`，全过才推下一个。
2. **TDD 反向使用**：本次是 refactor 删代码而非新增功能，TDD 顺序反过来：T1 先**改测试断言新行为**（保持 pytest 全过的前提下），再 T2-T4 删生产代码（生产代码删完测试自然全过）。
3. **遇错即停**：任何一步 pytest 不全过、ruff 不全清、import 失败，**停下来排查根因**，不强行往下推。
4. **每个 task 独立 commit**：commit message 格式 `<type>: <desc>`（refactor/test/docs/chore）。

---

## Task 1：集成测试改造适应 Tavily 路径

**Why first:** 集成测试现在依赖 SerpAPI 主线（`SEARCH_API_KEY="K"` + `_llm_pick` mock 步 + `mock_http.get_json`）。如果先删生产代码，3 个集成测试全炸；先改这些测试让它们适应"Tavily 一步直返"，删生产代码时它们仍能通过。

**Files:**
- Modify: `tests/integration/test_graph.py`
- Modify: `tests/integration/test_api.py`
- Modify: `tests/integration/test_trace_api.py`

**Risk:** 这是本计划最大头的 task。3 个文件 LLM mock 序列各不相同（happy path / 反馈闭环重试路径），每条序列都要核对调用次数 + 删 `_llm_pick` 那一步。**做之前必须先读完三个测试文件**理解每条 side_effect 序列对应哪个调用流程。

### 前置阅读

- [ ] **Step 1.0a：阅读 `tests/integration/test_graph.py` 全文**

  Run: `cat tests/integration/test_graph.py`
  Goal: 理解 `mock_llm.call_json.side_effect = [...]` 序列的每一条对应哪个 LLM 调用（parse_goal / classify / _llm_pick / extract / analyze / write / inspect / 重试 collector / 重试 analyzer / 重试 writer）。**画出调用顺序表**。

- [ ] **Step 1.0b：阅读 `tests/integration/test_api.py` 和 `test_trace_api.py`**

  Run: `cat tests/integration/test_api.py tests/integration/test_trace_api.py`
  Goal: 同上。注意 `test_api.py:18` 和 `test_trace_api.py:41` 用 `monkeypatch.setattr("src.graph.builder.settings.SEARCH_API_KEY", "K", raising=False)`，是 SerpAPI 时代的 fixture。

### test_graph.py 改造

- [ ] **Step 1.1：fixture 加 TAVILY_API_KEY="K"**

  Modify `tests/integration/test_graph.py` 的相关 fixture/setup（搜 `SEARCH_API_KEY` 找位置）：

  ```python
  # 旧
  monkeypatch.setattr("src.graph.builder.settings.SEARCH_API_KEY", "K", raising=False)

  # 新
  monkeypatch.setattr("src.graph.builder.settings.TAVILY_API_KEY", "K", raising=False)
  ```

- [ ] **Step 1.2：mock_http 加 post_json**

  在 mock_http 配置 `get_json` 的同一处加 `post_json` 配置：

  ```python
  # 加（在原 mock_http.get_json 配置之后）
  mock_http.post_json = AsyncMock(return_value={
      "results": [
          {"url": "https://alipay.com/pricing",
           "raw_content": "支付宝定价" * 60,
           "content": ""},
          {"url": "https://alipay.com/features",
           "raw_content": "支付宝功能" * 60,
           "content": ""},
          {"url": "https://alipay.com/help",
           "raw_content": "支付宝帮助" * 60,
           "content": ""},
      ]
  })
  ```

  注意 `raw_content` 长度要 ≥ `is_low_quality` 阈值（看 `src/tools/quality_gate.py` 中的最低字数，目测约 50-100 字）。"X" * 60 = 60 字符的"X"，足够通过质量闸门。

- [ ] **Step 1.3：删 LLM mock 序列里的 _llm_pick 步**

  找到 `mock_llm.call_json.side_effect = [...]`，删除每段序列里 `{"urls": ["https://..."]}` 这条（_llm_pick 的响应）：

  ```python
  # 旧（典型 happy path 7 步）
  mock_llm.call_json.side_effect = [
      {"goal_type": ...},                          # 1. parse_goal
      {"competitor_type": ...},                    # 2. classify
      {"urls": ["https://alipay.com/pricing"]},    # 3. _llm_pick ← 删
      {"basic_info": ...},                         # 4. extract（变成 step 3）
      {"positioning": ...},                        # 5. analyze
      {"title": ...},                              # 6. write
      {"issues": []},                              # 7. inspect
  ]

  # 新（6 步）
  mock_llm.call_json.side_effect = [
      {"goal_type": ...},                          # 1. parse_goal
      {"competitor_type": ...},                    # 2. classify
      {"basic_info": ...},                         # 3. extract
      {"positioning": ...},                        # 4. analyze
      {"title": ...},                              # 5. write
      {"issues": []},                              # 6. inspect
  ]
  ```

  **关键**：如果有反馈闭环重试路径（重试 collector → 再 classify + extract，重试 analyzer → 再 analyze），每段重试序列里**也要删** `_llm_pick` 步。仔细对照 Step 1.0a 的调用顺序表。

- [ ] **Step 1.4：call_index 断言改值**

  搜 `call_index[0] ==` 或 `call_count ==`，每条断言把数值减 N（N = 该流程被删了几次 `_llm_pick`）：

  ```python
  # 旧
  assert call_index[0] == 7

  # 新
  assert call_index[0] == 6
  ```

  **如有反馈闭环重试路径**，重试也调一次 `_llm_pick`，要相应递减。例如 `== 13`（重试 1 次）改为 `== 11`。

- [ ] **Step 1.5：跑该文件测试验证全过**

  Run: `pytest tests/integration/test_graph.py -v`
  Expected: PASS（之前 N 个测试，删 _llm_pick mock 步后仍 N 个测试全过）

  **如失败**：根因可能是
  1. mock 序列删错（少删一条→后面 LLM 调用拿到错的 mock 响应）
  2. mock 序列没补全反馈闭环重试路径
  3. mock_http.post_json 返回的 results 内容长度不够 → is_low_quality 挡掉 → 走占位降级 → analysis 字段为空
  停下来排查，不要硬塞。

### test_api.py 改造

- [ ] **Step 1.6：照样改 test_api.py**

  重复 Step 1.1~1.4 的逻辑，针对 test_api.py 的 fixture 和 mock 序列。

- [ ] **Step 1.7：跑 test_api.py 验证**

  Run: `pytest tests/integration/test_api.py -v`
  Expected: PASS

### test_trace_api.py 改造

- [ ] **Step 1.8：照样改 test_trace_api.py**

  重复 Step 1.1~1.4 的逻辑，针对 test_trace_api.py:41。

- [ ] **Step 1.9：跑 test_trace_api.py 验证**

  Run: `pytest tests/integration/test_trace_api.py -v`
  Expected: PASS

### Task 1 收尾

- [ ] **Step 1.10：跑全集成测试套件**

  Run: `pytest tests/integration/ -v`
  Expected: PASS

- [ ] **Step 1.11：跑全测试 + ruff（防止误改其他文件）**

  Run: `pytest -q`
  Expected: 139 passed（注意：此时**生产代码尚未改**，所以测试数仍是 139）

  Run: `ruff check src tests`
  Expected: All clean

- [ ] **Step 1.12：Commit**

  ```bash
  git add tests/integration/test_graph.py tests/integration/test_api.py tests/integration/test_trace_api.py
  git commit -m "test: 集成测试改造适应 Tavily 单 provider（删 _llm_pick mock 步、加 post_json mock、改 SEARCH_API_KEY 为 TAVILY_API_KEY）"
  ```

---

## Task 2：collection_pipeline 删 4 方法 + 构造器塌缩 + collect 主流程化简

**Files:**
- Modify: `src/agents/collection_pipeline.py`

### 验证 grep 假设（执行前必做）

- [ ] **Step 2.0a：验证 _fetch_clean 仅被 _fetch_with_backfill 调用**

  Run: `grep -rn "_fetch_clean" src/`
  Expected: 仅 `src/agents/collection_pipeline.py` 内 2 处（定义 + 在 _fetch_with_backfill 内调用）

- [ ] **Step 2.0b：验证 _llm_pick / _rule_pick / _fetch_with_backfill 不被生产代码外部调用**

  Run: `grep -rn "_llm_pick\|_rule_pick\|_fetch_with_backfill" src/`
  Expected: 仅 collection_pipeline.py 内自调用，无外部调用

  **如失败**：外部有调用方，stop 整个 task，回 spec 修订。

### 修改

- [ ] **Step 2.1：替换整个 CollectionPipeline 类**

  Replace `src/agents/collection_pipeline.py` 整个文件。**最终文件**应是这样（约 50-60 行，从原 ~180 行降到 ~50 行）：

  ```python
  """采集管线：Tavily 搜索 → 质量闸门 → 全空兜底。

  collector 的 tool 依赖。collect() 返回 (merged_text, sources, pipeline_trace, labeled_text)。
  Tavily 一次调用直返带正文 SourceResult，跳过传统选页/抓取步骤。
  """
  import logging

  from src.tools.quality_gate import is_low_quality

  logger = logging.getLogger(__name__)


  class CollectionPipeline:
      def __init__(self, search_source):
          self.search_source = search_source

      async def collect(self, competitor_name: str, category: str | None = None):
          """采集一个竞品的正文 + 来源 + 管线追踪。

          Returns:
              (merged_text, sources, trace, labeled_text)
          """
          texts: list[str] = []
          labeled_parts: list[str] = []
          sources: list[str] = []
          seen_urls: set[str] = set()
          trace: list[dict] = []

          def _add(text: str, url: str) -> None:
              texts.append(text)
              labeled_parts.append(f"【来源: {url}】\n{text}")

          # 搜索主线：仅在搜索源可用时
          if self.search_source.available():
              trace.append({"step": "search", "provider": self.search_source.name})
              tav_results = await self.search_source.search(
                  f"{competitor_name} 产品 功能 定价")
              valid = 0
              for r in tav_results:
                  if r.url and r.url not in seen_urls and not is_low_quality(r.text):
                      _add(r.text, r.url)
                      sources.append(r.url)
                      seen_urls.add(r.url)
                      valid += 1
              trace.append({"step": "tavily", "results": valid})
          else:
              trace.append({"step": "search_skipped", "reason": "no_api_key"})

          merged_text = "\n\n".join(texts)
          labeled_text = "\n\n".join(labeled_parts)
          return merged_text, sources, trace, labeled_text
  ```

  **被删除的内容（verify 这些都没了）**：
  - `import asyncio`
  - `_PATH_KEYWORDS` / `PICK_SYSTEM` 常量
  - 构造器中的 `llm`, `http`, `parser`, `max_top_n`, `pick_timeout`, `max_concurrency`, `_sem`
  - `_semaphore` 方法
  - `_rule_pick` 方法
  - `_llm_pick` 方法
  - `_fetch_clean` 方法
  - `_fetch_with_backfill` 方法
  - collect 内部 `getattr(self.search_source, "returns_bodies", False)` 检查 + if/else 分叉

### 验证

- [ ] **Step 2.2：跑 collection_pipeline 单测**

  Run: `pytest tests/unit/test_collection_pipeline.py -v`
  Expected: 失败（依赖 _llm_pick / _rule_pick / _fetch_clean 的测试 import 失败或 AttributeError）。**这是预期的**——T5 会清理这些测试。

  **本步不阻塞**：记下哪些测试挂了（截图 / 复制 console），T5 用得上。

- [ ] **Step 2.3：跑集成测试 + 全测试看哪些通过**

  Run: `pytest tests/integration/ -v`
  Expected: 集成测试**全过**（T1 已让它们适应 Tavily 路径）

  Run: `pytest tests/unit/test_sources.py tests/unit/test_quality_gate.py tests/unit/test_http_client.py tests/unit/test_config.py -v`
  Expected: 这些测试不依赖被删方法、应全过（test_sources.py 里的 test_serpapi_* 此时仍引用 SerpApiSource → import 失败、T3 后才删）。**也是预期的**。

  本 task 阶段允许 test_sources.py / test_collection_pipeline.py / test_config.py 局部失败，整体不阻塞。

- [ ] **Step 2.4：ruff 必须全清**

  Run: `ruff check src/agents/collection_pipeline.py`
  Expected: All clean（如果有 unused import 警告，例如 `import asyncio` 没删干净，立即修）

  Run: `ruff check src`
  Expected: All clean（src 目录其他文件不应受影响）

- [ ] **Step 2.5：Commit**

  ```bash
  git add src/agents/collection_pipeline.py
  git commit -m "refactor: collection_pipeline 删 _llm_pick/_rule_pick/_fetch_clean/_fetch_with_backfill 四方法 + 构造器塌缩为单 search_source 参数"
  ```

---

## Task 3：sources.py 删 SerpApiSource + builder 改单 TavilySource 注入

**Files:**
- Modify: `src/tools/sources.py`
- Modify: `src/graph/builder.py`

### sources.py 改造

- [ ] **Step 3.1：先读当前 sources.py 全文**

  Run: `cat src/tools/sources.py`
  Goal: 确认要删 `class SerpApiSource`、`SERPAPI_URL` 常量、`from urllib.parse import quote` 这三处的精确行号。

- [ ] **Step 3.2：删 SerpApiSource 类、SERPAPI_URL 常量、urllib.parse import**

  最终 `src/tools/sources.py` 应只剩：
  - 顶部 docstring（改为"Tavily 搜索源（唯一）"）
  - `from dataclasses import dataclass`
  - `from src.utils.config import settings`
  - `@dataclass class SourceResult`
  - `TAVILY_URL = "https://api.tavily.com/search"`
  - `class TavilySource`（含 `returns_bodies = True` 类属性 + 加注释"占位标记：当前仅 Tavily 走带正文路径"）

  Verify after edit:
  ```bash
  grep -nE "SerpApi|SERPAPI_URL|urllib" src/tools/sources.py
  ```
  Expected: 无输出。

- [ ] **Step 3.3：改 TavilySource 类注释（占位标记说明）**

  在 `class TavilySource` 内的 `returns_bodies = True` 那行后加注释：

  ```python
  class TavilySource:
      """Tavily 搜索源..."""
      name = "tavily"
      returns_bodies = True  # 占位标记：当前仅 Tavily 走带正文路径，未来若有不带正文 provider 需引入条件分支
  ```

### builder.py 改造

- [ ] **Step 3.4：读当前 builder.py**

  Run: `cat src/graph/builder.py | head -40`
  Goal: 找到 import + if/else + CollectionPipeline 构造的精确行号。

- [ ] **Step 3.5：改 import**

  ```python
  # 旧
  from src.tools.sources import SerpApiSource, TavilySource

  # 新
  from src.tools.sources import TavilySource
  ```

- [ ] **Step 3.6：删 if/else，直接构造 TavilySource**

  ```python
  # 旧
  if settings.SEARCH_PROVIDER == "tavily":
      search_source = TavilySource(http=http, api_key=settings.TAVILY_API_KEY)
  else:
      search_source = SerpApiSource(http=http, api_key=settings.SEARCH_API_KEY)

  # 新
  search_source = TavilySource(http=http, api_key=settings.TAVILY_API_KEY)
  ```

- [ ] **Step 3.7：改 CollectionPipeline 构造器调用（构造器塌缩同步）**

  搜 `CollectionPipeline(`：

  ```python
  # 旧（如果传 llm/http/parser/max_top_n 等）
  pipeline = CollectionPipeline(
      llm=llm, http=http, parser=parser, search_source=search_source,
      max_top_n=settings.SEARCH_TOP_N, pick_timeout=settings.PICK_LLM_TIMEOUT,
      max_concurrency=settings.MAX_FETCH_CONCURRENCY,
  )

  # 新
  pipeline = CollectionPipeline(search_source=search_source)
  ```

  **如果 builder 还在某处引用 http/parser 等（仅为传给 pipeline）**，把它们一并删掉（YAGNI——不传 pipeline 后这些局部变量也没用）。

### 验证

- [ ] **Step 3.8：跑集成测试**

  Run: `pytest tests/integration/ -v`
  Expected: 全过（T1 已让集成测试适应 Tavily 路径，T2 简化了 pipeline，T3 让 builder 配套塌缩）

  **如失败**：可能 builder 里还有别处引用了 SerpApiSource / SEARCH_API_KEY，grep 找一下：
  ```bash
  grep -nE "SerpApi|SEARCH_API_KEY|SEARCH_PROVIDER" src/graph/
  ```

- [ ] **Step 3.9：ruff**

  Run: `ruff check src/tools/sources.py src/graph/builder.py`
  Expected: All clean

- [ ] **Step 3.10：Commit**

  ```bash
  git add src/tools/sources.py src/graph/builder.py
  git commit -m "refactor: 删 SerpApiSource 类，builder 改为单 TavilySource 注入 + CollectionPipeline 构造器塌缩"
  ```

---

## Task 4：config 删 5 个字段

**Files:**
- Modify: `src/utils/config.py`

- [ ] **Step 4.1：读当前 config.py 全文**

  Run: `cat src/utils/config.py`
  Goal: 确认 `SEARCH_API_KEY`、`SEARCH_PROVIDER`、`PICK_LLM_TIMEOUT`、`MAX_FETCH_CONCURRENCY`、`_provider_env` 这 5 处的精确位置；同时确认 `TAVILY_API_KEY`、`SEARCH_TOP_N`、`COLLECT_INTERVAL`、`COLLECT_TIMEOUT` 保留。

- [ ] **Step 4.2：删除 5 个字段 / helper**

  - 删 `SEARCH_API_KEY: str = os.getenv("SEARCH_API_KEY", "")`
  - 删 `SEARCH_PROVIDER: str = _provider_env(...)`
  - 删 `PICK_LLM_TIMEOUT: int = _int_env(...)`（如果有）
  - 删 `MAX_FETCH_CONCURRENCY: int = _int_env(...)`（如果有）
  - 删 `def _provider_env(...)` 整个函数

  保留 `_int_env` helper（仍服务 SEARCH_TOP_N 等）。

  Verify:
  ```bash
  grep -nE "SEARCH_API_KEY|SEARCH_PROVIDER|PICK_LLM_TIMEOUT|MAX_FETCH_CONCURRENCY|_provider_env" src/utils/config.py
  ```
  Expected: 无输出。

- [ ] **Step 4.3：跑 config 单测验证**

  Run: `pytest tests/unit/test_config.py -v`
  Expected: 部分失败（test_invalid_search_provider_falls_back_to_serpapi 之类 import 失败 / 断言失败）。**预期的**——T5 会清理。

- [ ] **Step 4.4：跑集成测试 + ruff**

  Run: `pytest tests/integration/ -v`
  Expected: 全过

  Run: `ruff check src/utils/config.py`
  Expected: All clean

- [ ] **Step 4.5：Commit**

  ```bash
  git add src/utils/config.py
  git commit -m "refactor: config 删 SEARCH_API_KEY/SEARCH_PROVIDER/_provider_env/PICK_LLM_TIMEOUT/MAX_FETCH_CONCURRENCY"
  ```

---

## Task 5：清理 SerpAPI 专项测试 + conftest fixture 改名

**Files:**
- Modify: `tests/conftest.py`
- Modify: `tests/unit/test_sources.py`
- Modify: `tests/unit/test_collection_pipeline.py`
- Modify: `tests/unit/test_config.py`
- Modify: `tests/unit/test_http_client.py`

### conftest 改名 + 改职责

- [ ] **Step 5.1：改 conftest fixture**

  ```python
  # 旧
  @pytest.fixture(autouse=True)
  def lock_search_provider(monkeypatch):
      """锁定 SEARCH_PROVIDER=serpapi，使集成测试不受本地 .env 影响。

      集成测试的 LLM mock 序列按 serpapi 路径（含选页调用）编排，
      若本地 .env=tavily 会改变 build_graph 注入的 source 导致调用次数错位。
      tavily 专项测试各自显式构造 TavilySource，不读此配置，不受影响。
      """
      monkeypatch.setattr(settings, "SEARCH_PROVIDER", "serpapi")

  # 新
  @pytest.fixture(autouse=True)
  def shield_local_env(monkeypatch):
      """屏蔽本地 .env 的 TAVILY_API_KEY 污染所有测试。

      集成测试需要明确控制 TavilySource.available() 状态：
      - 走主线测试 → 自行 monkeypatch TAVILY_API_KEY="K"
      - 走占位降级测试 → 不设，本 fixture 已默认置空
      Tavily 专项测试用 MagicMock 构造 source，不读此配置，不受影响。
      """
      monkeypatch.setattr(settings, "TAVILY_API_KEY", "")
  ```

### test_sources.py 删 6 个 SerpAPI 测试

- [ ] **Step 5.2：删 test_sources.py 里的 6 个 test_serpapi_***

  删除：
  - `test_serpapi_unavailable_without_key`
  - `test_serpapi_available_with_key`
  - `test_serpapi_search_parses_candidates_and_uses_query_key`
  - `test_serpapi_search_chinese_query_encoded`
  - `test_serpapi_search_empty_on_none`
  - `test_serpapi_search_empty_when_unavailable`

  以及顶部 `from src.tools.sources import SerpApiSource` 这行 import。

  保留 4 个 `test_tavily_*`。

  Verify:
  ```bash
  grep -nE "SerpApi|test_serpapi" tests/unit/test_sources.py
  ```
  Expected: 无输出。

### test_collection_pipeline.py 删 SerpAPI 路径测试

- [ ] **Step 5.3：删 test_collection_pipeline.py 里依赖被删方法的测试**

  删除：
  - `test_rule_pick_prefers_official_and_pricing_paths`
  - `test_llm_pick_used_when_key_present`
  - `test_llm_pick_timeout_falls_back_to_rule`
  - `test_llm_pick_malformed_result_falls_back_to_rule`
  - `test_soft404_page_excluded_from_sources`（依赖 _fetch_clean）
  - 任何 `test_replenish_*` 系列（依赖 _fetch_with_backfill）
  - `test_backfill_does_not_pad`（同上）
  - 任何 mock `pipe._llm_pick = AsyncMock(...)` 或 `pipe._fetch_clean = AsyncMock(...)` 的测试

  保留：
  - Tavily 主线测试（`test_tavily_mainline_*` 之类）
  - 占位降级测试（`test_no_key_skips_search` 之类）
  - 构造器塌缩后能存活的测试

  **执行方式**：跑 `pytest tests/unit/test_collection_pipeline.py -v` 看 fail 列表，按 fail 决定删除项；不存在的方法引用必删，存在的看是否仍合理。

- [ ] **Step 5.4：跑 test_collection_pipeline.py 验证**

  Run: `pytest tests/unit/test_collection_pipeline.py -v`
  Expected: 剩余测试全过

### test_config.py 改造

- [ ] **Step 5.5：改 test_config.py**

  - 删 `test_invalid_search_provider_falls_back_to_serpapi`（_provider_env 已删）
  - 改 `test_settings_load_from_env`：删 `SEARCH_API_KEY` / `SEARCH_PROVIDER` 断言；保留 `TAVILY_API_KEY` 断言
  - 检查测试顶部的 import：删 `from src.utils.config import _provider_env` 这类（如果有）

  Verify:
  ```bash
  grep -nE "SEARCH_API_KEY|SEARCH_PROVIDER|_provider_env" tests/unit/test_config.py
  ```
  Expected: 无输出（除非是字面量测试数据，那种不动）

### test_http_client.py 数据 URL 改名

- [ ] **Step 5.6：改 test_http_client.py 数据 URL**

  把 5 处 `https://serpapi.com/search` 改为通用 URL（如 `https://api.example.com/search`）。**不要删** `get_json` / `post_json` / `_redact_key` 工具测试本身——这些是 HTTP 工具单测，跟搜索源解耦。

  示例：
  ```python
  # 旧
  result = await client.get_json("https://serpapi.com/search", headers={...})

  # 新
  result = await client.get_json("https://api.example.com/search", headers={...})
  ```

  **Tavily URL（如 `https://api.tavily.com/search`）保留不动**——这是 post_json 测试的真实数据 URL。

### Task 5 收尾

- [ ] **Step 5.7：跑全测试**

  Run: `pytest -q`
  Expected: 全过。预期测试数 ≈ 123-125（从 139 减去删除的 ~14-16）

- [ ] **Step 5.8：跑 ruff**

  Run: `ruff check src tests`
  Expected: All clean

- [ ] **Step 5.9：Commit**

  ```bash
  git add tests/conftest.py tests/unit/test_sources.py tests/unit/test_collection_pipeline.py tests/unit/test_config.py tests/unit/test_http_client.py
  git commit -m "test: 清理 SerpAPI 专项测试 + conftest fixture 改名 shield_local_env"
  ```

---

## Task 6：.env.example + CLAUDE.md 同步

**Files:**
- Modify: `.env.example`
- Modify: `CLAUDE.md`

### .env.example

- [ ] **Step 6.1：补 TAVILY_API_KEY**

  Append 一行到 `.env.example`：
  ```
  TAVILY_API_KEY=your_tavily_api_key_here
  ```

  最终 `.env.example`：
  ```
  DOUBAO_API_KEY=your_api_key_here
  DOUBAO_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
  DOUBAO_MODEL_EP=ep-20260514111325-xjmj7
  TAVILY_API_KEY=your_tavily_api_key_here
  ```

### CLAUDE.md

- [ ] **Step 6.2：改 line 95~100「环境变量」段**

  ```diff
   运行需在项目根目录配置 `.env`：
   - `DOUBAO_API_KEY` 必填
  -- 搜索主线按 `SEARCH_PROVIDER` 切换：`serpapi`（需 `SEARCH_API_KEY`）或 `tavily`（需 `TAVILY_API_KEY`）；缺 key 则跳过搜索主线、仅走专源/占位降级
  +- `TAVILY_API_KEY` 选填——搜索主线 Tavily 的鉴权 key；缺 key 则跳过搜索主线、走占位降级（completeness=0.0）
   - 其余配置见 `src/utils/config.py` 默认值
  ```

- [ ] **Step 6.3：改 line ~114「采集层」段**

  Search the line containing "搜索源插件在 `src/tools/sources.py`（SerpAPI / Tavily 双 provider"。Replace:

  ```diff
  - ……搜索源插件在 `src/tools/sources.py`（SerpAPI / Tavily 双 provider，按 `SEARCH_PROVIDER` 切换；iTunes 已于 06-06 因同名污染移除）。analyzer/writer/inspector 仍为 `(llm)` 依赖。
  + ……搜索源插件在 `src/tools/sources.py`（仅 Tavily，06-07 弃用 SerpAPI；iTunes 已于 06-06 因同名污染移除）。Tavily 一次调用直返带正文 SourceResult，跳过传统的"搜索→选页→抓取"三步走（_llm_pick/_rule_pick/_fetch_with_backfill 已于 06-07 删除）。analyzer/writer/inspector 仍为 `(llm)` 依赖。
  ```

- [ ] **Step 6.4：grep 验证 CLAUDE.md 没有遗漏**

  Run: `grep -nE "SEARCH_API_KEY|SEARCH_PROVIDER|SerpAPI" CLAUDE.md`
  Expected: 无输出（如果有，说明 spec 漏了某处，逐条修）

- [ ] **Step 6.5：Commit**

  ```bash
  git add .env.example CLAUDE.md
  git commit -m "docs: CLAUDE.md/env.example 同步弃用 SerpAPI 后的环境变量与架构描述"
  ```

---

## Task 7：PROGRESS.md / DECISIONS.md 决策落档

**Files:**
- Modify: `PROGRESS.md`
- Modify: `DECISIONS.md`

### PROGRESS.md

- [ ] **Step 7.1：在 PROGRESS.md 顶部 append 06-07 弃用 SerpAPI 段**

  在 `## 2026-06-07（分场景输出报告：5 套场景 schema 设计 + 双模型 doubt-driven 审查）` 这段**前面**插入新段（项目惯例：日期倒序）：

  ```markdown
  ## 2026-06-07（弃用 SerpAPI：搜索源单 provider 化）
  - 完成（worktree-drop-serpapi 分支，7 commits）：
    - 删除 SerpApiSource 类、SEARCH_API_KEY/SEARCH_PROVIDER 配置、collection_pipeline 的 _llm_pick/_rule_pick/_fetch_clean/_fetch_with_backfill 四方法（共 ~115 行生产代码）
    - 删除 conftest 锁 provider 的 fixture，改为 shield_local_env（屏蔽本地 .env 的 TAVILY_API_KEY 污染）
    - 三个集成测试 fixture 加 TAVILY_API_KEY="K"、LLM mock 序列删 _llm_pick 步、mock_http 替换 get_json 为 post_json
    - .env.example 补 TAVILY_API_KEY；CLAUDE.md 同步两处描述
    - 最终 N 测试通过、ruff 全清
    - 走 brainstorming → doubt-driven 单模型 17 条 + 跨模型 Codex 20 条审查 → RECONCILE 9 actionable + 3 产品决策 → writing-plans → execute
  - 进行中：worktree-drop-serpapi 合并回 master
  - 下一步：接主战场 30 task 分场景报告（worktree-A scenario-reports）
  - 阻塞：无
  - 安全提醒：无（本次重构仅删代码、不引入新 key）
  ```

  **N 替换为实际测试数**（执行时 pytest 输出）。

### DECISIONS.md

- [ ] **Step 7.2：在 DECISIONS.md 顶部 append 06-07 决策条目**

  在 `## 2026-06-07: 报告 schema 按使用场景拆分（5 场景全做，R2 架构）` 这段**前面**插入：

  ```markdown
  ## 2026-06-07: 弃用 SerpAPI，仅保留 Tavily 作为唯一搜索源
  - 选择：删除 SerpApiSource 类、SEARCH_API_KEY/SEARCH_PROVIDER 配置开关、collection_pipeline 的"搜索→选页→抓取"两步走机制（_llm_pick/_rule_pick/_fetch_clean/_fetch_with_backfill 四方法 + 构造器塌缩）。Tavily 一次调用直返带正文，跳过中间所有步骤
  - 理由：06-06 实测证实 Tavily 在中文场景质量明显优于 SerpAPI（语雀 1.0 / 飞书 0.85 completeness）；双 provider 架构带来开关复杂度（SEARCH_PROVIDER）、conftest 防污染 fixture、builder if/else、115 行 SerpAPI 专项代码——与 Cooper 选择的"代码简化、答辩故事单一 AI 搜索"目标矛盾。git 历史保留，未来若需恢复可 revert
  - 反转的旧决策：06-06「双 provider 切换、保留 SerpAPI 作为可选 fallback」（一日决策反转，作为历史保留）
  - 备选 1：保留 SerpAPI 但删 SEARCH_PROVIDER 开关、Tavily 作为默认（排除：仍需双 provider 代码维护、答辩故事不干净）
  - 备选 2：仅删 SerpAPI 类、保留 SEARCH_PROVIDER 字段（排除：废留架构假承诺）
  - 实现路径：方案 B'（doubt-driven 双模型审查后修订），分 7 个细粒度 commit；commit 顺序：测试先改不依赖 → 删生产代码 → 删 SerpAPI 专项测试 → 文档同步
  ```

### Task 7 收尾 + 全局验收

- [ ] **Step 7.3：跑全测试 + ruff 最后一次**

  Run: `pytest -q && ruff check src tests`
  Expected: 全过 + clean

- [ ] **Step 7.4：grep 全代码库验证 SerpAPI 痕迹清干净**

  Run: `grep -rn -i "serpapi\|SerpApi\|SEARCH_API_KEY\|SEARCH_PROVIDER" --include="*.py" src tests`
  Expected: 无输出

  Run: `grep -rn -i "serpapi" --include="*.md" CLAUDE.md .env.example` (only current docs, not historical)
  Expected: 无输出

  **如果 PROGRESS.md / DECISIONS.md 历史段还含 SerpAPI 字眼是正常的**——历史不动。

- [ ] **Step 7.5：Commit**

  ```bash
  git add PROGRESS.md DECISIONS.md
  git commit -m "docs: PROGRESS.md/DECISIONS.md append 06-07 弃用 SerpAPI 决策条目"
  ```

- [ ] **Step 7.6：最终 git log 检查**

  Run: `git log --oneline master..HEAD`
  Expected: 7 个 commit，按 T1~T7 顺序：
  ```
  test:     集成测试改造适应 Tavily 单 provider
  refactor: collection_pipeline 删 4 方法 + 构造器塌缩
  refactor: 删 SerpApiSource 类，builder 改为单 TavilySource 注入
  refactor: config 删 SEARCH_API_KEY/SEARCH_PROVIDER 等
  test:     清理 SerpAPI 专项测试 + conftest fixture 改名
  docs:     CLAUDE.md/env.example 同步
  docs:     PROGRESS.md/DECISIONS.md append
  ```

---

## 完工标准（最终验收）

- [ ] `pytest -q` 全过、测试数从 139 降到 ~123-125
- [ ] `ruff check src tests` 全清
- [ ] `grep -rn -i "serpapi\|SerpApi\|SEARCH_API_KEY\|SEARCH_PROVIDER" --include="*.py" src tests` 无输出
- [ ] git log 7 个 commit、消息格式规范
- [ ] worktree 内**未污染** main 项目目录（不动主目录的 master 分支）

合并回 master 的步骤**不在本计划范围**——见 `superpowers:finishing-a-development-branch` 技能。

---

## Self-Review

- ✅ **Spec coverage**: spec Part 1 (A1-A4) → T2/T3/T4；Part 2 (B1-B8) → T1/T5；Part 3 (C1-C3) → T6/T7。全覆盖。
- ✅ **Placeholder scan**: 无 "TBD"/"TODO"/"implement later"；所有代码块完整。
- ✅ **Type consistency**: 全计划 `CollectionPipeline.__init__(search_source)` 签名一致；`_provider_env` / `lock_search_provider` 等待删名称在不同 task 一致。
- ✅ **Commit topology**: T1-T7 严格按 spec Part 5 拓扑（先改测试 → 删生产 → 删测试 → 文档），保证每个 commit 后 pytest 全过。

**Plan 自审通过，待执行。**
