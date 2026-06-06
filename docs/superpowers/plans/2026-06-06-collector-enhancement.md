# 采集能力增强 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 提升采集层「有没有料」——调长选页超时、抓取失败递补、新增可切换的 Tavily 高质量源，把末端有效正文数从 ~1 提升。

**Architecture:** 三项改动全部落在采集层。P1 调 config 默认值；P2 在 `http_client.get` 加故障分类重试 + 在 `collection_pipeline.collect` 把「抓固定 top3」改为「凑够 N 个有效正文」的候选池递补；P3 新增 `TavilySource`（复用 `get_json`、不引 SDK），由 `build_graph` 按 `SEARCH_PROVIDER` 二选一注入，`collect` 内按 source 能力分叉。下游消费方（`_add`/`sources`/`labeled_text`/schema/graph 编排/前端）零改动。

**Tech Stack:** Python 3.14, httpx (async), pytest + pytest-asyncio (auto mode), unittest.mock。

**Spec:** `docs/superpowers/specs/2026-06-06-collector-enhancement-design.md`

---

## File Structure

- `src/utils/config.py` — 改默认值（PICK_LLM_TIMEOUT 20→45, SEARCH_TOP_N 3→5）+ 新增 SEARCH_PROVIDER / TAVILY_API_KEY
- `tests/unit/test_config.py` — 同步默认值断言 + 新配置项断言
- `src/tools/http_client.py` — `get()` 加故障分类重试
- `tests/unit/test_http_client.py` — 重试/不重试用例
- `src/tools/sources.py` — 新增 `TavilySource`
- `tests/unit/test_sources.py` — TavilySource 解析/无 key/脱敏
- `src/agents/collection_pipeline.py` — `collect()` 搜索主线段改递补 + 按 source 能力分叉 tavily
- `tests/unit/test_collection_pipeline.py` — 递补凑数/降级/Tavily 主线
- `src/graph/builder.py` — 按 SEARCH_PROVIDER 注入分叉

---

## Task 1: 配置项（P1 + 新增开关）

**Files:**
- Modify: `src/utils/config.py:25-28`
- Test: `tests/unit/test_config.py:12-14`

- [ ] **Step 1: 改 test_config 断言（让它先红）**

把 `tests/unit/test_config.py:12-13` 改为新默认值，并补两个新配置项断言。`test_search_config_defaults_when_absent` 改成：

```python
def test_search_config_defaults_when_absent(monkeypatch):
    for k in ("SEARCH_API_KEY", "SEARCH_TOP_N", "PICK_LLM_TIMEOUT",
              "MAX_FETCH_CONCURRENCY", "SEARCH_PROVIDER", "TAVILY_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: False)
    import src.utils.config as cfg
    importlib.reload(cfg)
    assert cfg.settings.SEARCH_API_KEY == ""
    assert cfg.settings.SEARCH_TOP_N == 5
    assert cfg.settings.PICK_LLM_TIMEOUT == 45
    assert cfg.settings.MAX_FETCH_CONCURRENCY == 5
    assert cfg.settings.SEARCH_PROVIDER == "serpapi"
    assert cfg.settings.TAVILY_API_KEY == ""
```

新增一个非法 provider 回落用例（追加到文件末尾）：

```python
def test_invalid_search_provider_falls_back_to_serpapi(monkeypatch):
    monkeypatch.setenv("SEARCH_PROVIDER", "FooBar")
    import src.utils.config as cfg
    importlib.reload(cfg)
    assert cfg.settings.SEARCH_PROVIDER == "serpapi"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `./venv/Scripts/python.exe -m pytest tests/unit/test_config.py -v`
Expected: FAIL（默认值断言不符 + AttributeError: SEARCH_PROVIDER）

- [ ] **Step 3: 改 config.py**

`src/utils/config.py:25-28` 区块改为（新增一个 `_provider_env` 规整函数 + 两个配置项）：

```python
def _provider_env(name: str, default: str, allowed: tuple[str, ...]) -> str:
    """读取字符串枚举环境变量，非法/空值回落默认（小写规整）"""
    val = (os.getenv(name) or "").strip().lower()
    return val if val in allowed else default
```

放在 `_int_env` 之后。然后 `Settings` 类的数据源拓展区块改为：

```python
    # 数据源拓展
    SEARCH_API_KEY: str = os.getenv("SEARCH_API_KEY", "")
    SEARCH_TOP_N: int = _int_env("SEARCH_TOP_N", 5)
    PICK_LLM_TIMEOUT: int = _int_env("PICK_LLM_TIMEOUT", 45)
    MAX_FETCH_CONCURRENCY: int = _int_env("MAX_FETCH_CONCURRENCY", 5)
    SEARCH_PROVIDER: str = _provider_env("SEARCH_PROVIDER", "serpapi", ("serpapi", "tavily"))
    TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")
```

- [ ] **Step 4: 运行测试确认通过**

Run: `./venv/Scripts/python.exe -m pytest tests/unit/test_config.py -v`
Expected: PASS（3 个用例）

- [ ] **Step 5: Commit**

```bash
git add src/utils/config.py tests/unit/test_config.py
git commit -m "feat: 采集配置 P1 超时 45s + SEARCH_TOP_N 5 + SEARCH_PROVIDER/TAVILY_API_KEY"
```

---

## Task 2: 抓取层故障分类重试（P2-a）

**Files:**
- Modify: `src/tools/http_client.py:63-78`
- Test: `tests/unit/test_http_client.py`

逻辑：超时 / `httpx.ConnectError` / 5xx → 重试 1 次（共 2 次尝试，重试自然换 UA）；403/404 等 4xx → 不重试返回 None。

- [ ] **Step 1: 写失败测试**

追加到 `tests/unit/test_http_client.py` 的 `TestHttpClient` 类内：

```python
    @pytest.mark.asyncio
    async def test_get_retries_once_on_timeout_then_succeeds(self):
        client = HttpClient()
        ok = httpx.Response(200, text="<html>ok</html>")
        with patch.object(
            client.client, "get", new_callable=AsyncMock,
            side_effect=[httpx.TimeoutException("t"), ok],
        ) as m:
            result = await client.get("https://example.com")
            assert result == "<html>ok</html>"
            assert m.call_count == 2
        await client.close()

    @pytest.mark.asyncio
    async def test_get_retries_once_on_5xx_then_gives_up(self):
        client = HttpClient()
        resp500 = httpx.Response(500)
        with patch.object(
            client.client, "get", new_callable=AsyncMock,
            side_effect=[resp500, resp500],
        ) as m:
            result = await client.get("https://example.com")
            assert result is None
            assert m.call_count == 2
        await client.close()

    @pytest.mark.asyncio
    async def test_get_does_not_retry_on_403(self):
        client = HttpClient()
        resp403 = httpx.Response(403)
        with patch.object(
            client.client, "get", new_callable=AsyncMock, return_value=resp403,
        ) as m:
            result = await client.get("https://example.com")
            assert result is None
            assert m.call_count == 1
        await client.close()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `./venv/Scripts/python.exe -m pytest tests/unit/test_http_client.py -k "retries or not_retry or 403" -v`
Expected: FAIL（现无重试，timeout 用例 call_count==1，5xx 用例 call_count==1）

- [ ] **Step 3: 改 http_client.py 的 get()**

`src/tools/http_client.py:63-78` 的 `get` 方法整体替换为：

```python
    async def get(self, url: str) -> str | None:
        """GET 请求，失败返回 None。超时/连接错误/5xx 重试 1 次；4xx 不重试。"""
        for attempt in range(2):  # 共 2 次尝试
            try:
                await self._rate_limit(url)
                await self._rotate_ua()
                response = await self.client.get(url)
                if response.status_code == 200:
                    return response.text
                logger.warning("[http] %s 返回状态码 %d", _redact_key(url), response.status_code)
                if response.status_code >= 500 and attempt == 0:
                    continue  # 5xx 重试
                return None  # 4xx 或重试后仍 5xx
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                logger.warning("[http] %s 请求超时/连接失败: %s", _redact_key(url), _redact_key(str(e)))
                if attempt == 0:
                    continue
                return None
            except httpx.RequestError as e:
                logger.warning("[http] %s 请求失败: %s", _redact_key(url), _redact_key(str(e)))
                return None
        return None
```

- [ ] **Step 4: 运行测试确认通过**

Run: `./venv/Scripts/python.exe -m pytest tests/unit/test_http_client.py -v`
Expected: PASS（含原有 + 3 个新用例）

- [ ] **Step 5: Commit**

```bash
git add src/tools/http_client.py tests/unit/test_http_client.py
git commit -m "feat: http get 故障分类重试（超时/5xx 重试 1 次，4xx 直接弃）"
```

---

## Task 3: 候选池递补（P2-b）

**Files:**
- Modify: `src/agents/collection_pipeline.py:124-141`（搜索主线段）
- Test: `tests/unit/test_collection_pipeline.py`

逻辑：候选池 = 选中的在前 + 其余候选按原序兜底；并发批次（批大小 `min(差额+2, max_concurrency)`）抓取，过 `_fetch_clean` 且不在 `seen_urls` 的计入有效正文，凑够 N 取前 N 停，候选耗尽降级。

- [ ] **Step 1: 写失败测试（递补凑数 + 403 降级）**

追加到 `tests/unit/test_collection_pipeline.py` 末尾。第一个测前 2 个候选抓挂、靠后续候选补足凑够 N=2：

```python
@pytest.mark.asyncio
async def test_replenish_fills_from_pool_when_picked_fail(monkeypatch):
    monkeypatch.setattr("src.agents.collection_pipeline.build_pro_sources",
                        lambda category, http: [])
    search = MagicMock()
    search.available.return_value = True
    search.name = "serpapi"
    # 5 个候选，前 2 个抓返回 None（挂），后 3 个成功
    cands = [{"url": f"https://s/{i}", "title": "", "snippet": ""} for i in range(5)]
    search.search = AsyncMock(return_value=cands)

    pipe = CollectionPipeline(llm=MagicMock(), http=MagicMock(), parser=MagicMock(),
                              search_source=search, max_top_n=2, pick_timeout=20, max_concurrency=5)
    # LLM 选页只选前 2 个（会抓挂）
    pipe._llm_pick = AsyncMock(return_value=[cands[0], cands[1]])

    async def fake_fetch(url):
        idx = int(url.rsplit("/", 1)[1])
        return None if idx < 2 else f"正文{idx}" * 30
    pipe._fetch_clean = AsyncMock(side_effect=fake_fetch)

    text, sources, trace, labeled = await pipe.collect("X", "default")
    # 凑够 N=2：应来自后 3 个成功候选，前 2 个挂的不计
    assert len(sources) == 2
    assert all("https://s/" in s for s in sources)


@pytest.mark.asyncio
async def test_replenish_degrades_below_n_when_pool_exhausted(monkeypatch):
    monkeypatch.setattr("src.agents.collection_pipeline.build_pro_sources",
                        lambda category, http: [])
    search = MagicMock()
    search.available.return_value = True
    search.name = "serpapi"
    cands = [{"url": f"https://s/{i}", "title": "", "snippet": ""} for i in range(3)]
    search.search = AsyncMock(return_value=cands)
    pipe = CollectionPipeline(llm=MagicMock(), http=MagicMock(), parser=MagicMock(),
                              search_source=search, max_top_n=5, pick_timeout=20, max_concurrency=5)
    pipe._llm_pick = AsyncMock(return_value=cands)
    # 全部抓挂（模拟 403 站点）
    pipe._fetch_clean = AsyncMock(return_value=None)
    text, sources, trace, labeled = await pipe.collect("X", "default")
    assert sources == []  # 凑不够，合理降级
```

- [ ] **Step 2: 运行测试确认失败**

Run: `./venv/Scripts/python.exe -m pytest tests/unit/test_collection_pipeline.py -k "replenish" -v`
Expected: FAIL（现逻辑只抓 picked，不递补；第一个用例 sources 会 < 2）

- [ ] **Step 3: 实现递补**

在 `CollectionPipeline` 内新增一个辅助方法（放在 `_fetch_clean` 之后）：

```python
    def _build_pool(self, picked: list[dict], candidates: list[dict]) -> list[dict]:
        """候选池 = 选中的在前 + 其余候选按原序兜底（去重 URL）。"""
        seen = set()
        pool = []
        for c in list(picked) + list(candidates):
            u = c.get("url")
            if u and u not in seen:
                pool.append(c)
                seen.add(u)
        return pool

    async def _replenish_fetch(self, pool: list[dict], need: int, seen_urls: set):
        """从候选池并发批次抓取，凑够 need 个有效正文（过闸门 + 去重）就停。
        返回 [(url, text), ...]，最多 need 个。"""
        collected: list[tuple[str, str]] = []
        i = 0
        while len(collected) < need and i < len(pool):
            remaining = need - len(collected)
            batch_size = min(remaining + 2, self.max_concurrency)
            batch = pool[i:i + batch_size]
            i += len(batch)
            fetched = await asyncio.gather(
                *[self._fetch_clean(c["url"]) for c in batch], return_exceptions=True
            )
            for c, t in zip(batch, fetched):
                if isinstance(t, str) and t and c["url"] not in seen_urls:
                    collected.append((c["url"], t))
                    seen_urls.add(c["url"])
                    if len(collected) >= need:
                        break
        return collected[:need]
```

然后把 `collect()` 搜索主线段（`:124-141`，即 `if self.search_source.available():` 到专源之前）的抓取部分改为用递补。原 `:128-141` 替换为：

```python
        if self.search_source.available():
            trace.append({"step": "search", "provider": self.search_source.name})
            candidates = await self.search_source.search(f"{competitor_name} 产品 功能 定价")
            picked = await self._llm_pick(candidates, competitor_name, self.max_top_n)
            if picked is not None:
                trace.append({"step": "pick", "method": "llm", "picked": [c["url"] for c in picked]})
            else:
                picked = self._rule_pick(candidates, competitor_name, self.max_top_n)
                trace.append({"step": "pick", "method": "rule_fallback", "picked": [c["url"] for c in picked]})
            pool = self._build_pool(picked, candidates)
            replenished = await self._replenish_fetch(pool, self.max_top_n, seen_urls)
            for url, t in replenished:
                _add(t, url)
                sources.append(url)
            trace.append({"step": "fetch", "valid": len(replenished), "target": self.max_top_n})
        else:
            trace.append({"step": "search_skipped", "reason": "no_api_key"})
```

注意：`_replenish_fetch` 内已把成功 url 加进 `seen_urls`，循环里不再重复加。

- [ ] **Step 4: 运行测试确认通过**

Run: `./venv/Scripts/python.exe -m pytest tests/unit/test_collection_pipeline.py -v`
Expected: PASS（含原有 + 2 个递补用例）

- [ ] **Step 5: Commit**

```bash
git add src/agents/collection_pipeline.py tests/unit/test_collection_pipeline.py
git commit -m "feat: 采集递补——凑够 N 个有效正文（并发批次，抓挂从候选池补足）"
```

---

## Task 4: TavilySource（P3 数据源）

**Files:**
- Modify: `src/tools/sources.py`（新增 `TavilySource` 类）
- Test: `tests/unit/test_sources.py`

接口：`available() -> bool`、`async search(query) -> list[SourceResult]`（注意：直接返回带正文的 `SourceResult`，与 `SerpApiSource.search` 返回候选 dict 不同——这是分叉的依据）。用 `http.get_json` 调 REST，api_key 走 query。

> Tavily REST 端点与参数实现时按官方文档核对（source-driven）。本计划用 `https://api.tavily.com/search?query=...&api_key=...&include_raw_content=true` 形式，响应取 `results[].raw_content`（无则退 `content`）+ `results[].url`。若官方文档与此不符，以文档为准并相应调整解析与测试 mock。

- [ ] **Step 1: 写失败测试**

追加到 `tests/unit/test_sources.py` 末尾：

```python
@pytest.mark.asyncio
async def test_tavily_parses_results_with_body():
    from src.tools.sources import TavilySource
    raw = {"results": [
        {"url": "https://feishu.cn/docs", "raw_content": "飞书功能介绍" * 30, "content": "短摘要"},
        {"url": "https://feishu.cn/pricing", "raw_content": "", "content": "飞书定价说明" * 30},
    ]}
    http = MagicMock()
    http.get_json = AsyncMock(return_value=raw)
    results = await TavilySource(http, api_key="k").search("飞书 产品 功能 定价")
    assert len(results) == 2
    assert isinstance(results[0], SourceResult)
    assert "飞书功能介绍" in results[0].text       # 优先 raw_content
    assert "飞书定价说明" in results[1].text       # raw_content 空时退 content
    assert results[0].url == "https://feishu.cn/docs"


@pytest.mark.asyncio
async def test_tavily_unavailable_without_key():
    from src.tools.sources import TavilySource
    src = TavilySource(MagicMock(), api_key="")
    assert src.available() is False
    results = await src.search("x")
    assert results == []


@pytest.mark.asyncio
async def test_tavily_key_in_query_not_crashing_on_empty():
    from src.tools.sources import TavilySource
    http = MagicMock()
    http.get_json = AsyncMock(return_value=None)  # 模拟请求失败
    results = await TavilySource(http, api_key="k").search("x")
    assert results == []
```

- [ ] **Step 2: 运行测试确认失败**

Run: `./venv/Scripts/python.exe -m pytest tests/unit/test_sources.py -k tavily -v`
Expected: FAIL（ImportError: TavilySource）

- [ ] **Step 3: 实现 TavilySource**

在 `src/tools/sources.py` 的 `SerpApiSource` 类之后新增（沿用文件顶部已 import 的 `quote`、`logging`、`SourceResult`）：

```python
TAVILY_URL = "https://api.tavily.com/search?query={query}&search_depth=advanced&include_raw_content=true&max_results=5"


class TavilySource:
    """Tavily 搜索源：一次调用返回结果 + 每条清洗正文，吃掉搜索+选页+抓取+清洗。

    与 SerpApiSource 不同：search() 直接返回带正文的 SourceResult（非候选 dict）。
    key 走 api_key query 参数，日志由 HttpClient._redact_key 脱敏。
    """

    name = "tavily"

    def __init__(self, http, api_key: str):
        self.http = http
        self.api_key = api_key

    def available(self) -> bool:
        return bool(self.api_key)

    async def search(self, query: str) -> list[SourceResult]:
        if not self.available():
            return []
        url = TAVILY_URL.format(query=quote(query)) + f"&api_key={quote(self.api_key)}"
        data = await self.http.get_json(url)
        if not data or not isinstance(data, dict):
            return []
        results = []
        for item in data.get("results", []):
            text = item.get("raw_content") or item.get("content") or ""
            link = item.get("url", "")
            if text and link:
                results.append(SourceResult(url=link, text=text))
        return results
```

- [ ] **Step 4: 运行测试确认通过**

Run: `./venv/Scripts/python.exe -m pytest tests/unit/test_sources.py -k tavily -v`
Expected: PASS（3 个用例）

- [ ] **Step 5: Commit**

```bash
git add src/tools/sources.py tests/unit/test_sources.py
git commit -m "feat: 新增 TavilySource（get_json + api_key query，返回带正文结果）"
```

---

## Task 5: collect 按 source 能力分叉 tavily + builder 注入

**Files:**
- Modify: `src/agents/collection_pipeline.py:124-141`（搜索主线段加 tavily 分支）
- Modify: `src/graph/builder.py:17`（按 SEARCH_PROVIDER 注入）
- Test: `tests/unit/test_collection_pipeline.py`

分叉依据：source 是否有 `search` 且返回 `SourceResult`（tavily）vs 返回候选 dict（serpapi）。用一个显式标志最稳——给 TavilySource 加类属性 `returns_bodies = True`，serpapi 无此属性。collect 内 `getattr(self.search_source, "returns_bodies", False)` 判断。

- [ ] **Step 1: 给 TavilySource 加标志 + 写 collect 分叉失败测试**

先在 `src/tools/sources.py` 的 `TavilySource` 类里 `name = "tavily"` 下一行加：

```python
    returns_bodies = True  # search() 直接返回带正文 SourceResult，collect 据此跳过选页+抓取
```

追加测试到 `tests/unit/test_collection_pipeline.py` 末尾（验证 tavily 主线跳过选页/抓取、正文过闸门）：

```python
@pytest.mark.asyncio
async def test_tavily_mainline_skips_pick_and_fetch(monkeypatch):
    from src.tools.sources import SourceResult
    monkeypatch.setattr("src.agents.collection_pipeline.build_pro_sources",
                        lambda category, http: [])
    tav = MagicMock()
    tav.available.return_value = True
    tav.name = "tavily"
    tav.returns_bodies = True
    tav.search = AsyncMock(return_value=[
        SourceResult(url="https://feishu.cn/a", text="飞书正文" * 30),
        SourceResult(url="https://feishu.cn/b", text="短"),  # 应被 quality_gate 挡掉
    ])
    pipe = CollectionPipeline(llm=MagicMock(), http=MagicMock(), parser=MagicMock(),
                              search_source=tav, max_top_n=5, pick_timeout=20, max_concurrency=5)
    pipe._llm_pick = AsyncMock(side_effect=AssertionError("不应调用选页"))
    pipe._fetch_clean = AsyncMock(side_effect=AssertionError("不应调用抓取"))
    text, sources, trace, labeled = await pipe.collect("飞书", "saas")
    assert "飞书正文" in text
    assert sources == ["https://feishu.cn/a"]   # 短正文被闸门挡
    assert any(t.get("step") == "tavily" for t in trace)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `./venv/Scripts/python.exe -m pytest tests/unit/test_collection_pipeline.py -k tavily_mainline -v`
Expected: FAIL（现 collect 不认 returns_bodies，会走 serpapi 主线调 _llm_pick → AssertionError）

- [ ] **Step 3: 改 collect 加 tavily 分支**

在 `collect()` 的 `if self.search_source.available():` 块内最前面分叉。把 Task 3 改后的搜索主线段进一步改为：

```python
        if self.search_source.available():
            if getattr(self.search_source, "returns_bodies", False):
                # Tavily 路径：直接拿带正文结果，跳过选页+抓取，仍过质量闸门
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
                trace.append({"step": "search", "provider": self.search_source.name})
                candidates = await self.search_source.search(f"{competitor_name} 产品 功能 定价")
                picked = await self._llm_pick(candidates, competitor_name, self.max_top_n)
                if picked is not None:
                    trace.append({"step": "pick", "method": "llm", "picked": [c["url"] for c in picked]})
                else:
                    picked = self._rule_pick(candidates, competitor_name, self.max_top_n)
                    trace.append({"step": "pick", "method": "rule_fallback", "picked": [c["url"] for c in picked]})
                pool = self._build_pool(picked, candidates)
                replenished = await self._replenish_fetch(pool, self.max_top_n, seen_urls)
                for url, t in replenished:
                    _add(t, url)
                    sources.append(url)
                trace.append({"step": "fetch", "valid": len(replenished), "target": self.max_top_n})
        else:
            trace.append({"step": "search_skipped", "reason": "no_api_key"})
```

确认文件顶部已 `from src.tools.quality_gate import is_low_quality`（现有 `:9` 已 import，无需新增）。

- [ ] **Step 4: 运行测试确认通过**

Run: `./venv/Scripts/python.exe -m pytest tests/unit/test_collection_pipeline.py -v`
Expected: PASS（含全部递补 + tavily 主线用例）

- [ ] **Step 5: 改 builder 注入分叉**

`src/graph/builder.py:9` 的 import 加 `TavilySource`：

```python
from src.tools.sources import SerpApiSource, TavilySource
```

`src/graph/builder.py:17` 的 `search_source = ...` 一行改为按开关注入：

```python
    if settings.SEARCH_PROVIDER == "tavily":
        search_source = TavilySource(http=http, api_key=settings.TAVILY_API_KEY)
    else:
        search_source = SerpApiSource(http=http, api_key=settings.SEARCH_API_KEY)
```

- [ ] **Step 6: 全量回归 + ruff**

Run: `./venv/Scripts/python.exe -m pytest -q && ./venv/Scripts/python.exe -m ruff check src tests`
Expected: 全部通过（原 139 + 新增用例）、ruff All checks passed

- [ ] **Step 7: Commit**

```bash
git add src/agents/collection_pipeline.py src/tools/sources.py src/graph/builder.py tests/unit/test_collection_pipeline.py
git commit -m "feat: collect 按 source 能力分叉 tavily 主线 + builder 按 SEARCH_PROVIDER 注入"
```

---

## 真实验收（实现完成后，需 Cooper 配合）

单测全绿后，按 spec 第八节做真实 Tavily 验收（不进 CI）：
1. Cooper 在本地 `.env` 配 `TAVILY_API_KEY=<真 key>` + `SEARCH_PROVIDER=tavily`
2. 起后端跑一次「语雀 vs 飞书」分析
3. 看 `runs/<trace_id>/01_profiles.json` 的 pipeline_trace 是否含 tavily step、completeness 是否提升、报告是否丰满
4. 切回 `SEARCH_PROVIDER=serpapi`（或留空）验证手写管线递补路径仍正常

## 完成后文档

- 更新 `PROGRESS.md`（本次完成 + 真实验收结果）
- 更新 `DECISIONS.md`（记录对 06-03「只做 SerpAPI」决策的修正：加 Tavily 并列、抽象边界为「要不要自己抓正文」）
