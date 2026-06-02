# 数据源拓展 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 collector 的硬编码三源采集，重构为「搜索 API→LLM 选页→正文页→质量闸门」主线 + 按 category 路由的可插拔结构化专源，采集逻辑下沉到独立的 CollectionPipeline tool。

**Architecture:** 三层分层 `CollectorAgent(agent) → CollectionPipeline(tool) → sources(插件)`。主线用 SerpAPI 搜索拿候选 URL、LLM 选页、抓正文、质量闸门过滤；专源（iTunes 等）按 category 并行路由。无 SerpAPI key 时跳过搜索主线只走专源（不退 SERP）。全空时产 completeness=0.0 占位 profile。顶层 collect 改为部分降级（单竞品失败不拖垮全局）。

**Tech Stack:** Python 3.14, asyncio, httpx, Pydantic v2, pytest（asyncio auto 模式），BeautifulSoup4。

**设计来源:** `docs/superpowers/specs/2026-06-03-datasource-expansion-design.md`（经 brainstorming + 三轮 doubt-driven 跨模型审查）。

---

## 文件结构

| 文件 | 职责 | 动作 |
|---|---|---|
| `src/tools/quality_gate.py` | 纯函数：判断正文是否为软404/验证页/过短，决定丢弃 | Create |
| `src/tools/sources.py` | DataSource 极简基类 + iTunes 专源 + SerpAPI 搜索源 + 按 category 取专源的函数 | Create |
| `src/agents/collection_pipeline.py` | 编排 search→选页→fetch→闸门 + 专源并行 + 去重 + 全空占位；产 (merged_text, sources, pipeline_trace) | Create |
| `src/schemas/profile.py` | `ProfileMetadata` 加 `pipeline_trace` 字段 | Modify |
| `src/utils/config.py` | 加 4 个可选配置 | Modify |
| `src/tools/http_client.py` | 加 `get_json(url, headers)`；现有 `get` 不动 | Modify |
| `src/agents/collector.py` | 删 URL_TEMPLATES/_fetch_and_parse/_parse_itunes；构造器改 (llm, pipeline)；加 detect_category（零 LLM）；加 _build_placeholder_profile；_collect_single 调 pipeline；顶层 collect 改 return_exceptions | Modify |
| `src/graph/builder.py` | `build_graph` 内组装 pipeline 并注入 collector（签名不变） | Modify |
| `tests/unit/test_quality_gate.py` | 闸门纯函数测试 | Create |
| `tests/unit/test_sources.py` | iTunes + SerpAPI 源测试 | Create |
| `tests/unit/test_collection_pipeline.py` | 管线编排/降级/去重测试 | Create |
| `tests/unit/test_config.py` | 配置容错测试 | Create |
| `tests/unit/test_collector.py` | 改构造器引用 + detect_category 测试 | Modify |
| `tests/integration/test_graph.py` 等 | 适配新接线（mock pipeline 或 mock http.get_json） | Modify |

**实现顺序**：底层无依赖的纯函数/schema/config 先行（Task 1-4），再 sources（Task 5-7），再 pipeline（Task 8-10），再 collector 接线（Task 11-13），最后 builder + 集成测试（Task 14-15）。

---

### Task 1: ProfileMetadata 增加 pipeline_trace 字段

**Files:**
- Modify: `src/schemas/profile.py:73-77`
- Test: `tests/unit/test_profile_schema.py`（Create）

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_profile_schema.py
from src.schemas.profile import ProfileMetadata


def test_metadata_accepts_pipeline_trace():
    meta = ProfileMetadata(
        collected_at="2026-06-03T10:00:00",
        pipeline_trace=[{"step": "search", "provider": "serpapi", "candidates": 5}],
    )
    assert meta.pipeline_trace == [{"step": "search", "provider": "serpapi", "candidates": 5}]


def test_metadata_pipeline_trace_defaults_empty():
    meta = ProfileMetadata(collected_at="2026-06-03T10:00:00")
    assert meta.pipeline_trace == []
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/unit/test_profile_schema.py -v`
Expected: FAIL — `ProfileMetadata` 无 `pipeline_trace`，传入额外字段被忽略 → 第一个断言 `assert meta.pipeline_trace` AttributeError。

- [ ] **Step 3: 加字段**

`src/schemas/profile.py` 的 `ProfileMetadata` 改为：

```python
class ProfileMetadata(BaseModel):
    """采集元数据"""
    collected_at: str
    data_sources: list[str] = Field(default_factory=list)
    completeness_score: float = Field(ge=0, le=1, default=0)
    pipeline_trace: list[dict] = Field(default_factory=list)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/unit/test_profile_schema.py -v`
Expected: PASS（2 passed）

- [ ] **Step 5: 跑全量回归确认没破坏现有**

Run: `pytest -q`
Expected: 现有 51+ 全绿（新增字段有默认值，向后兼容）

- [ ] **Step 6: Commit**

```bash
git add src/schemas/profile.py tests/unit/test_profile_schema.py
git commit -m "feat: ProfileMetadata 增加 pipeline_trace 字段承载采集决策追溯"
```

---

### Task 2: config 增加 4 个可选配置（import 不抛）

**Files:**
- Modify: `src/utils/config.py:7-15`
- Test: `tests/unit/test_config.py`（Create）

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_config.py
import importlib
import os


def test_search_config_defaults_when_absent(monkeypatch):
    for k in ("SEARCH_API_KEY", "SEARCH_TOP_N", "PICK_LLM_TIMEOUT", "MAX_FETCH_CONCURRENCY"):
        monkeypatch.delenv(k, raising=False)
    import src.utils.config as cfg
    importlib.reload(cfg)
    assert cfg.settings.SEARCH_API_KEY == ""
    assert cfg.settings.SEARCH_TOP_N == 3
    assert cfg.settings.PICK_LLM_TIMEOUT == 20
    assert cfg.settings.MAX_FETCH_CONCURRENCY == 5


def test_invalid_int_env_does_not_crash_import(monkeypatch):
    monkeypatch.setenv("SEARCH_TOP_N", "not-a-number")
    import src.utils.config as cfg
    importlib.reload(cfg)
    # 非法值回落默认，不抛
    assert cfg.settings.SEARCH_TOP_N == 3
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/unit/test_config.py -v`
Expected: FAIL — `AttributeError: SEARCH_API_KEY`

- [ ] **Step 3: 加配置 + 容错 int 辅助**

`src/utils/config.py` 在 `import os` 后加辅助函数，并在 `Settings` 内加字段：

```python
import os
from dotenv import load_dotenv

load_dotenv()


def _int_env(name: str, default: int) -> int:
    """读取整数环境变量，非法值回落默认，绝不在 import 时抛错"""
    try:
        return int(os.getenv(name) or default)
    except (TypeError, ValueError):
        return default


class Settings:
    DOUBAO_API_KEY: str = os.getenv("DOUBAO_API_KEY", "")
    DOUBAO_BASE_URL: str = os.getenv("DOUBAO_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
    DOUBAO_MODEL_EP: str = os.getenv("DOUBAO_MODEL_EP", "ep-20260514111325-xjmj7")
    LLM_TIMEOUT: int = 120
    LLM_MAX_RETRIES: int = 2
    HTTP_TIMEOUT: int = 30
    COLLECT_INTERVAL: float = 2.0  # 同域名请求间隔（秒）
    MAX_RETRIES_INSPECTOR: int = 2
    # 数据源拓展
    SEARCH_API_KEY: str = os.getenv("SEARCH_API_KEY", "")
    SEARCH_TOP_N: int = _int_env("SEARCH_TOP_N", 3)
    PICK_LLM_TIMEOUT: int = _int_env("PICK_LLM_TIMEOUT", 20)
    MAX_FETCH_CONCURRENCY: int = _int_env("MAX_FETCH_CONCURRENCY", 5)


settings = Settings()
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/unit/test_config.py -v`
Expected: PASS（2 passed）

- [ ] **Step 5: Commit**

```bash
git add src/utils/config.py tests/unit/test_config.py
git commit -m "feat: 新增数据源拓展配置（SEARCH_API_KEY/TOP_N/PICK_LLM_TIMEOUT/并发上限），import 容错"
```

---

### Task 3: quality_gate 纯函数闸门

**Files:**
- Create: `src/tools/quality_gate.py`
- Test: `tests/unit/test_quality_gate.py`（Create）

**说明**：闸门判断一段已抽取的正文是否应被丢弃。判据：①过短（< MIN_CONTENT_LEN 字符）；②含验证/拦截特征词（captcha、人机验证、访问异常、安全验证、verify you are human）；③软404（含「页面不存在」「404」「not found」「页面已删除」且正文很短）。结构化专源（iTunes）结果不过此闸门——闸门只作用于网页抓取正文，避免误杀短但有效的 API 结果。

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_quality_gate.py
from src.tools.quality_gate import is_low_quality, MIN_CONTENT_LEN


def test_too_short_is_low_quality():
    assert is_low_quality("支付宝") is True


def test_captcha_page_is_low_quality():
    text = "请完成安全验证 " + "x" * 200
    assert is_low_quality(text) is True


def test_soft_404_is_low_quality():
    text = "404 页面不存在 请返回首页"
    assert is_low_quality(text) is True


def test_normal_content_kept():
    text = "支付宝是蚂蚁集团旗下的移动支付平台，提供扫码支付、转账、理财等功能。" * 5
    assert is_low_quality(text) is False


def test_empty_is_low_quality():
    assert is_low_quality("") is True
    assert is_low_quality(None) is True


def test_min_content_len_is_positive():
    assert MIN_CONTENT_LEN > 0
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/unit/test_quality_gate.py -v`
Expected: FAIL — `ModuleNotFoundError: src.tools.quality_gate`

- [ ] **Step 3: 实现闸门**

```python
# src/tools/quality_gate.py
"""正文质量闸门：纯函数，判断抓取正文是否应丢弃（软404/验证页/过短）。

只作用于网页抓取正文；结构化专源（iTunes 等）结果不经过此闸门，
避免误杀短但有效的 API 结果。
"""

MIN_CONTENT_LEN = 80  # 中文正文低于此长度视为无效

_BLOCK_MARKERS = (
    "captcha", "verify you are human", "人机验证", "安全验证",
    "访问异常", "请完成验证", "滑动验证",
)
_NOT_FOUND_MARKERS = ("页面不存在", "页面已删除", "not found", "404")


def is_low_quality(text: str | None) -> bool:
    """正文是否低质应丢弃。"""
    if not text:
        return True
    stripped = text.strip()
    if len(stripped) < MIN_CONTENT_LEN:
        return True
    lowered = stripped.lower()
    if any(m in lowered for m in _BLOCK_MARKERS):
        return True
    # 软 404：含 not-found 标记且正文较短（长正文里偶含 "404" 不算）
    if len(stripped) < MIN_CONTENT_LEN * 4 and any(m in lowered for m in _NOT_FOUND_MARKERS):
        return True
    return False
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/unit/test_quality_gate.py -v`
Expected: PASS（6 passed）

- [ ] **Step 5: Commit**

```bash
git add src/tools/quality_gate.py tests/unit/test_quality_gate.py
git commit -m "feat: 新增正文质量闸门纯函数（软404/验证页/过短过滤）"
```

---

### Task 4: HttpClient 增加 get_json（局部 header、复用限速、UA 加锁、key 脱敏日志）

**Files:**
- Modify: `src/tools/http_client.py`
- Test: `tests/unit/test_http_client.py`（追加用例）

**说明**：搜索 API 需要带 `Authorization` header 且解析 JSON。`get_json` 复用 `_rate_limit`，但 header 用**局部传参**（`self.client.get(url, headers=...)`），不污染共享 `self.client.headers`。同时给 UA 轮换加锁，避免并发下共享 header 竞态（doubt-driven #7/#12）。日志对 URL 的 key 做脱敏。

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_http_client.py 追加（文件已 import httpx, AsyncMock, patch）
import httpx
import pytest
from unittest.mock import AsyncMock, patch
from src.tools.http_client import HttpClient, _redact_key


class TestGetJson:
    @pytest.mark.asyncio
    async def test_get_json_parses_and_passes_local_headers(self):
        client = HttpClient()
        payload = {"organic_results": [{"link": "https://x.com"}]}
        mock_resp = httpx.Response(200, json=payload)
        captured = {}

        async def fake_get(url, headers=None):
            captured["headers"] = headers
            return mock_resp

        with patch.object(client.client, "get", side_effect=fake_get):
            result = await client.get_json("https://serpapi.com/search", headers={"Authorization": "Bearer K"})
        assert result == payload
        # 局部 header 传入，且未污染共享客户端 header
        assert captured["headers"] == {"Authorization": "Bearer K"}
        assert "Authorization" not in client.client.headers
        await client.close()

    @pytest.mark.asyncio
    async def test_get_json_returns_none_on_non_200(self):
        client = HttpClient()
        with patch.object(client.client, "get", new_callable=AsyncMock, return_value=httpx.Response(429)):
            result = await client.get_json("https://serpapi.com/search", headers={})
        assert result is None
        await client.close()

    @pytest.mark.asyncio
    async def test_get_json_returns_none_on_timeout(self):
        client = HttpClient()
        with patch.object(client.client, "get", new_callable=AsyncMock,
                          side_effect=httpx.TimeoutException("t")):
            result = await client.get_json("https://serpapi.com/search", headers={})
        assert result is None
        await client.close()


def test_redact_key_masks_query_param():
    out = _redact_key("https://serpapi.com/search?q=x&api_key=SECRET123")
    assert "SECRET123" not in out
    assert "api_key=" in out
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/unit/test_http_client.py::TestGetJson -v`
Expected: FAIL — `HttpClient` 无 `get_json`、模块无 `_redact_key`

- [ ] **Step 3: 实现 get_json + 脱敏 + UA 锁**

`src/tools/http_client.py` 顶部加 `import re`；在类外加脱敏函数；在 `__init__` 加锁；改 `_rotate_ua`/`get` 用锁；新增 `get_json`。完整改动：

```python
import asyncio
import logging
import re
import time
from urllib.parse import urlparse

import httpx

from src.utils.config import settings

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
]

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Upgrade-Insecure-Requests": "1",
}

_KEY_QUERY_RE = re.compile(r"(api_key|apikey|key|token)=([^&\s]+)", re.IGNORECASE)


def _redact_key(url: str) -> str:
    """脱敏 URL 中的 key/token query 参数，用于安全日志。"""
    return _KEY_QUERY_RE.sub(r"\1=***", url)


class HttpClient:
    """异步 HTTP 客户端，带超时、User-Agent 轮换和同域名频率控制"""

    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=settings.HTTP_TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENTS[0], **DEFAULT_HEADERS},
        )
        self._ua_index = 0
        self._last_request: dict[str, float] = {}
        self._ua_lock = asyncio.Lock()

    async def _rotate_ua(self):
        async with self._ua_lock:
            self._ua_index = (self._ua_index + 1) % len(USER_AGENTS)
            self.client.headers["User-Agent"] = USER_AGENTS[self._ua_index]

    async def _rate_limit(self, url: str):
        """同域名频率控制"""
        domain = urlparse(url).netloc
        if domain in self._last_request:
            elapsed = time.time() - self._last_request[domain]
            if elapsed < settings.COLLECT_INTERVAL:
                await asyncio.sleep(settings.COLLECT_INTERVAL - elapsed)
        self._last_request[domain] = time.time()

    async def get(self, url: str) -> str | None:
        """GET 请求，失败返回 None"""
        try:
            await self._rate_limit(url)
            await self._rotate_ua()
            response = await self.client.get(url)
            if response.status_code == 200:
                return response.text
            logger.warning("[http] %s 返回状态码 %d", _redact_key(url), response.status_code)
            return None
        except httpx.TimeoutException:
            logger.warning("[http] %s 请求超时", _redact_key(url))
            return None
        except httpx.RequestError as e:
            logger.warning("[http] %s 请求失败: %s", _redact_key(url), e)
            return None

    async def get_json(self, url: str, headers: dict | None = None) -> dict | list | None:
        """GET 请求并解析 JSON；header 局部传参不污染共享客户端；失败返回 None"""
        try:
            await self._rate_limit(url)
            response = await self.client.get(url, headers=headers)
            if response.status_code == 200:
                return response.json()
            logger.warning("[http] %s 返回状态码 %d", _redact_key(url), response.status_code)
            return None
        except httpx.TimeoutException:
            logger.warning("[http] %s 请求超时", _redact_key(url))
            return None
        except (httpx.RequestError, ValueError) as e:
            logger.warning("[http] %s 请求/解析失败: %s", _redact_key(url), e)
            return None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def close(self):
        await self.client.aclose()
```

注意：`_rotate_ua` 由同步改为 `async`，`get` 内改为 `await self._rotate_ua()`。

- [ ] **Step 4: 跑测试确认通过 + 现有 http 测试不破**

Run: `pytest tests/unit/test_http_client.py -v`
Expected: PASS（原有 3 个 get 测试 + 新增 4 个）。原 get 测试不传 header、行为不变。

- [ ] **Step 5: Commit**

```bash
git add src/tools/http_client.py tests/unit/test_http_client.py
git commit -m "feat: HttpClient 增加 get_json（局部 header/复用限速/UA 加锁）+ URL key 脱敏"
```

---

### Task 5: sources.py — DataSource 基类 + iTunes 专源

**Files:**
- Create: `src/tools/sources.py`
- Test: `tests/unit/test_sources.py`（Create）

**说明**：`DataSource` 是极简协议——专源暴露 `name` 和 `async collect(competitor_name) -> list[SourceResult]`。`SourceResult` 是 `(url, text)` 的轻量 dataclass。iTunes 源迁移自 collector 现有 `_parse_itunes`，修掉 null description 的潜在 bug（`description` 值为 None 时 `[:1000]` 会 TypeError）。

- [ ] **Step 1: 写失败测试（iTunes 部分）**

```python
# tests/unit/test_sources.py
import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from src.tools.sources import ItunesSource, SourceResult


@pytest.mark.asyncio
async def test_itunes_parses_results():
    raw = {"results": [{"trackName": "支付宝", "formattedPrice": "免费",
                        "averageUserRating": 4.7, "userRatingCount": 20000,
                        "sellerName": "Ant", "description": "移动支付平台" * 10,
                        "trackViewUrl": "https://apps.apple.com/app/id1"}]}
    http = MagicMock()
    http.get_json = AsyncMock(return_value=raw)
    results = await ItunesSource(http).collect("支付宝")
    assert len(results) == 1
    assert isinstance(results[0], SourceResult)
    assert "支付宝" in results[0].text
    assert results[0].url == "https://apps.apple.com/app/id1"


@pytest.mark.asyncio
async def test_itunes_handles_null_description():
    raw = {"results": [{"trackName": "X", "description": None,
                       "trackViewUrl": "https://apps.apple.com/app/id2"}]}
    http = MagicMock()
    http.get_json = AsyncMock(return_value=raw)
    results = await ItunesSource(http).collect("X")  # 不应抛 TypeError
    assert len(results) == 1


@pytest.mark.asyncio
async def test_itunes_empty_results():
    http = MagicMock()
    http.get_json = AsyncMock(return_value={"results": []})
    results = await ItunesSource(http).collect("无此应用")
    assert results == []


@pytest.mark.asyncio
async def test_itunes_none_response():
    http = MagicMock()
    http.get_json = AsyncMock(return_value=None)  # 请求失败
    results = await ItunesSource(http).collect("X")
    assert results == []
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/unit/test_sources.py -v`
Expected: FAIL — `ModuleNotFoundError: src.tools.sources`

- [ ] **Step 3: 实现基类 + iTunes**

```python
# src/tools/sources.py
"""数据源插件：DataSource 基类 + iTunes 专源 + SerpAPI 搜索源 + 按 category 路由。

只实现 SerpAPI 一个搜索 provider（换 provider 各家响应格式不同需各写 parser，列入未来扩展）。
结构化专源（iTunes）结果不经过 quality_gate。
"""
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

ITUNES_API_URL = "https://itunes.apple.com/search?term={name}&country=cn&entity=software&limit=3"


@dataclass
class SourceResult:
    """单条数据源结果：内容页 URL + 已抽取正文。"""
    url: str
    text: str


class ItunesSource:
    """iTunes Search API 专源（结构化，不过质量闸门）。"""

    name = "itunes"

    def __init__(self, http):
        self.http = http

    async def collect(self, competitor_name: str) -> list[SourceResult]:
        from urllib.parse import quote
        url = ITUNES_API_URL.format(name=quote(competitor_name))
        data = await self.http.get_json(url)
        if not data or not isinstance(data, dict):
            return []
        results = []
        for app in data.get("results", []):
            desc = app.get("description") or ""
            text = (
                f"应用：{app.get('trackName', '')}\n"
                f"价格：{app.get('formattedPrice', '')}\n"
                f"评分：{app.get('averageUserRating', '')}（{app.get('userRatingCount', 0)} 条评价）\n"
                f"开发商：{app.get('sellerName', '')}\n"
                f"描述：{desc[:1000]}"
            )
            results.append(SourceResult(url=app.get("trackViewUrl", ""), text=text))
        return results
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/unit/test_sources.py -v`
Expected: PASS（4 passed）

- [ ] **Step 5: Commit**

```bash
git add src/tools/sources.py tests/unit/test_sources.py
git commit -m "feat: sources.py 基类 + iTunes 专源（迁移并修复 null description bug）"
```

---

### Task 6: sources.py — SerpAPI 搜索源（key 走 header、无 key→available()=False）

**Files:**
- Modify: `src/tools/sources.py`
- Test: `tests/unit/test_sources.py`（追加）

**说明**：`SerpApiSource` 提供 `available()`（key 非空才 True）和 `async search(query) -> list[dict{url,title,snippet}]`。key 走 `Authorization` header（不进 query），避免泄漏。429/超时由 `http.get_json` 吞成 None → search 返回 `[]`。

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_sources.py 追加
from src.tools.sources import SerpApiSource


@pytest.mark.asyncio
async def test_serpapi_unavailable_without_key():
    src = SerpApiSource(http=MagicMock(), api_key="")
    assert src.available() is False


@pytest.mark.asyncio
async def test_serpapi_available_with_key():
    src = SerpApiSource(http=MagicMock(), api_key="K")
    assert src.available() is True


@pytest.mark.asyncio
async def test_serpapi_search_parses_candidates_and_uses_header():
    payload = {"organic_results": [
        {"link": "https://a.com", "title": "A", "snippet": "sa"},
        {"link": "https://b.com", "title": "B", "snippet": "sb"},
    ]}
    http = MagicMock()
    captured = {}

    async def fake_get_json(url, headers=None):
        captured["url"] = url
        captured["headers"] = headers
        return payload

    http.get_json = AsyncMock(side_effect=fake_get_json)
    src = SerpApiSource(http=http, api_key="SECRET")
    cands = await src.search("支付宝 定价")
    assert [c["url"] for c in cands] == ["https://a.com", "https://b.com"]
    # key 走 header，不进 url
    assert "SECRET" not in captured["url"]
    assert captured["headers"]["Authorization"] == "Bearer SECRET"


@pytest.mark.asyncio
async def test_serpapi_search_empty_on_none():
    http = MagicMock()
    http.get_json = AsyncMock(return_value=None)  # 429/超时被吞
    src = SerpApiSource(http=http, api_key="K")
    assert await src.search("x") == []
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/unit/test_sources.py::test_serpapi_search_parses_candidates_and_uses_header -v`
Expected: FAIL — 无 `SerpApiSource`

- [ ] **Step 3: 实现 SerpApiSource**

`src/tools/sources.py` 追加（顶部已 import logging/dataclass，补 quote 在用处 import）：

```python
SERPAPI_URL = "https://serpapi.com/search?engine=google&q={query}&num=10"


class SerpApiSource:
    """SerpAPI 搜索源：search(query) -> 候选 [{url,title,snippet}]。key 走 header。"""

    name = "serpapi"

    def __init__(self, http, api_key: str):
        self.http = http
        self.api_key = api_key

    def available(self) -> bool:
        return bool(self.api_key)

    async def search(self, query: str) -> list[dict]:
        if not self.available():
            return []
        from urllib.parse import quote
        url = SERPAPI_URL.format(query=quote(query))
        headers = {"Authorization": f"Bearer {self.api_key}"}
        data = await self.http.get_json(url, headers=headers)
        if not data or not isinstance(data, dict):
            return []
        candidates = []
        for item in data.get("organic_results", []):
            link = item.get("link")
            if link:
                candidates.append({
                    "url": link,
                    "title": item.get("title", ""),
                    "snippet": item.get("snippet", ""),
                })
        return candidates
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/unit/test_sources.py -v`
Expected: PASS（8 passed：iTunes 4 + SerpAPI 4）

- [ ] **Step 5: Commit**

```bash
git add src/tools/sources.py tests/unit/test_sources.py
git commit -m "feat: SerpAPI 搜索源（key 走 header 防泄漏，无 key 优雅降级）"
```

---

### Task 7: sources.py — 按 category 路由专源

**Files:**
- Modify: `src/tools/sources.py`
- Test: `tests/unit/test_sources.py`（追加）

**说明**：`build_pro_sources(category, http)` 按规范化后的 category 返回结构化专源列表。`saas` → [iTunes]；其余（含 `hardware`、`default`、未识别）→ []（硬件电商源列入未来扩展，本轮不实现）。category 规范化：含「软件/saas/app/应用/工具/平台」→ saas；其余 → default。

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_sources.py 追加
from src.tools.sources import build_pro_sources, normalize_category, ItunesSource


def test_normalize_category_saas():
    assert normalize_category("SaaS 工具") == "saas"
    assert normalize_category("协作软件") == "saas"


def test_normalize_category_default_for_unknown():
    assert normalize_category("金融科技") == "default"
    assert normalize_category("") == "default"


def test_build_pro_sources_saas_has_itunes():
    sources = build_pro_sources("saas", http=MagicMock())
    assert any(isinstance(s, ItunesSource) for s in sources)


def test_build_pro_sources_default_empty():
    assert build_pro_sources("default", http=MagicMock()) == []
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/unit/test_sources.py::test_build_pro_sources_saas_has_itunes -v`
Expected: FAIL — 无 `build_pro_sources`

- [ ] **Step 3: 实现路由**

`src/tools/sources.py` 追加：

```python
_SAAS_KEYWORDS = ("软件", "saas", "app", "应用", "工具", "平台", "service")


def normalize_category(category: str) -> str:
    """自由文本 category 规范化到路由键：saas / default。"""
    if not category:
        return "default"
    lowered = category.lower()
    if any(k in lowered for k in _SAAS_KEYWORDS):
        return "saas"
    return "default"


def build_pro_sources(category: str, http) -> list:
    """按规范化 category 返回结构化专源列表。硬件电商源列入未来扩展。"""
    key = normalize_category(category)
    if key == "saas":
        return [ItunesSource(http)]
    return []
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/unit/test_sources.py -v`
Expected: PASS（12 passed）

- [ ] **Step 5: Commit**

```bash
git add src/tools/sources.py tests/unit/test_sources.py
git commit -m "feat: 按 category 路由结构化专源（saas→iTunes，其余→空）"
```

---

### Task 8: CollectionPipeline — 骨架 + 规则选页 + 无 key 降级

**Files:**
- Create: `src/agents/collection_pipeline.py`
- Test: `tests/unit/test_collection_pipeline.py`（Create）

**说明**：`CollectionPipeline.collect(name, category) -> (merged_text, sources, pipeline_trace)`。本任务先实现：无 key 路径（跳过搜索主线、只走专源）+ 规则选页 `_rule_pick`（域名/路径关键词打分，零 LLM）。LLM 选页在 Task 9 加。Semaphore 实例级惰性创建（首次 async 上下文）。

接口契约：
- `merged_text: str`、`sources: list[str]`（仅真正喂 LLM 的内容页 URL）、`pipeline_trace: list[dict]`。
- `__init__(self, llm, http, parser, search_source, max_top_n, pick_timeout, max_concurrency)`。

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_collection_pipeline.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from src.agents.collection_pipeline import CollectionPipeline


def _pipeline(search_available=False, **kw):
    search = MagicMock()
    search.available.return_value = search_available
    search.search = AsyncMock(return_value=[])
    return CollectionPipeline(
        llm=MagicMock(), http=MagicMock(), parser=MagicMock(),
        search_source=search, max_top_n=3, pick_timeout=20, max_concurrency=5, **kw,
    )


@pytest.mark.asyncio
async def test_no_key_skips_search_uses_pro_sources(monkeypatch):
    # 无 key：search.available()=False，只走专源
    from src.tools.sources import SourceResult
    fake_source = MagicMock()
    fake_source.name = "itunes"
    fake_source.collect = AsyncMock(return_value=[SourceResult(url="https://x.com/app", text="支付宝介绍" * 30)])
    monkeypatch.setattr("src.agents.collection_pipeline.build_pro_sources",
                        lambda category, http: [fake_source])

    pipe = _pipeline(search_available=False)
    text, sources, trace = await pipe.collect("支付宝", "saas")
    assert "支付宝介绍" in text
    assert "https://x.com/app" in sources
    # search 未被调用
    assert any(t.get("step") == "search_skipped" for t in trace)


def test_rule_pick_prefers_official_and_pricing_paths():
    pipe = _pipeline()
    cands = [
        {"url": "https://random-blog.com/post", "title": "blog", "snippet": ""},
        {"url": "https://alipay.com/pricing", "title": "定价", "snippet": ""},
        {"url": "https://alipay.com/features", "title": "功能", "snippet": ""},
    ]
    picked = pipe._rule_pick(cands, "支付宝", top_n=2)
    urls = [c["url"] for c in picked]
    assert "https://alipay.com/pricing" in urls
    assert "https://alipay.com/features" in urls
    assert "https://random-blog.com/post" not in urls
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/unit/test_collection_pipeline.py -v`
Expected: FAIL — `ModuleNotFoundError: src.agents.collection_pipeline`

- [ ] **Step 3: 实现骨架 + 规则选页 + 无 key 路径**

```python
# src/agents/collection_pipeline.py
"""采集管线：搜索→选页→抓正文→质量闸门 + 专源并行 + 去重 + 全空兜底。

collector 的 tool 依赖。collect() 返回 (merged_text, sources, pipeline_trace)。
LLM 选页仅在有 key 且走搜索主线时发生——无 key 路径零新增 LLM 调用。
"""
import asyncio
import logging
from urllib.parse import urlparse

from src.tools.quality_gate import is_low_quality
from src.tools.sources import build_pro_sources

logger = logging.getLogger(__name__)

# 规则选页加分关键词（域名/路径）
_PATH_KEYWORDS = ("pricing", "price", "feature", "product", "docs", "help", "定价", "功能", "产品")


class CollectionPipeline:
    def __init__(self, llm, http, parser, search_source,
                 max_top_n: int = 3, pick_timeout: int = 20, max_concurrency: int = 5):
        self.llm = llm
        self.http = http
        self.parser = parser
        self.search_source = search_source
        self.max_top_n = max_top_n
        self.pick_timeout = pick_timeout
        self.max_concurrency = max_concurrency
        self._sem: asyncio.Semaphore | None = None

    def _semaphore(self) -> asyncio.Semaphore:
        # 实例级惰性创建，绑定首次使用时的事件循环；非 module-global
        if self._sem is None:
            self._sem = asyncio.Semaphore(self.max_concurrency)
        return self._sem

    def _rule_pick(self, candidates: list[dict], name: str, top_n: int) -> list[dict]:
        """零 LLM 规则打分选页：路径关键词 + 名称命中域名加分。"""
        def score(c: dict) -> int:
            url = (c.get("url") or "").lower()
            s = 0
            if any(k in url for k in _PATH_KEYWORDS):
                s += 2
            if name.lower() in url:
                s += 1
            return s
        ranked = sorted(candidates, key=score, reverse=True)
        return [c for c in ranked if score(c) > 0][:top_n]

    async def _fetch_clean(self, url: str) -> str | None:
        """抓取并抽取正文，过质量闸门；低质/失败返回 None。"""
        async with self._semaphore():
            raw = await self.http.get(url)
        if raw is None:
            return None
        text = self.parser.extract_text(raw)
        if is_low_quality(text):
            return None
        return text

    async def collect(self, competitor_name: str, category: str):
        """返回 (merged_text, sources, pipeline_trace)。"""
        trace: list[dict] = []
        texts: list[str] = []
        sources: list[str] = []
        seen_urls: set[str] = set()

        # 专源（与主线并行起步前先构建）
        pro_sources = build_pro_sources(category, self.http)
        trace.append({"step": "route", "category": category, "pro_sources": [s.name for s in pro_sources]})

        # 搜索主线：仅在 available 时
        if self.search_source.available():
            trace.append({"step": "search", "provider": self.search_source.name})
            # 选页在 Task 9 接 LLM；本任务先用规则选页占位
            candidates = await self.search_source.search(f"{competitor_name} 产品 功能 定价")
            picked = self._rule_pick(candidates, competitor_name, self.max_top_n)
            trace.append({"step": "pick", "method": "rule", "picked": [c["url"] for c in picked]})
            fetched = await asyncio.gather(
                *[self._fetch_clean(c["url"]) for c in picked], return_exceptions=True
            )
            for c, t in zip(picked, fetched):
                if isinstance(t, str) and t and c["url"] not in seen_urls:
                    texts.append(t)
                    sources.append(c["url"])
                    seen_urls.add(c["url"])
        else:
            trace.append({"step": "search_skipped", "reason": "no_api_key"})

        # 专源并行（每源独立超时容错）
        async def _run_source(src):
            try:
                return await asyncio.wait_for(src.collect(competitor_name), timeout=self.http_timeout())
            except Exception as e:  # noqa: BLE001
                logger.warning("[pipeline] 专源 %s 失败: %s", getattr(src, "name", "?"), e)
                return []
        results_per_source = await asyncio.gather(*[_run_source(s) for s in pro_sources])
        for src, results in zip(pro_sources, results_per_source):
            for r in results:
                if r.url not in seen_urls:
                    texts.append(r.text)
                    if r.url:
                        sources.append(r.url)
                        seen_urls.add(r.url)
            trace.append({"step": "pro_source", "name": src.name, "results": len(results)})

        merged_text = "\n\n".join(texts)
        return merged_text, sources, trace

    def http_timeout(self) -> int:
        from src.utils.config import settings
        return settings.HTTP_TIMEOUT
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/unit/test_collection_pipeline.py -v`
Expected: PASS（2 passed）

- [ ] **Step 5: Commit**

```bash
git add src/agents/collection_pipeline.py tests/unit/test_collection_pipeline.py
git commit -m "feat: CollectionPipeline 骨架（规则选页 + 无 key 降级 + 专源并行容错）"
```

---

### Task 9: CollectionPipeline — LLM 选页（独立短超时，失败退规则）

**Files:**
- Modify: `src/agents/collection_pipeline.py`
- Test: `tests/unit/test_collection_pipeline.py`（追加）

**说明**：有 key 时，候选页用 LLM 选最相关 Top N，外层 `asyncio.wait_for(self.llm.call_json(...), self.pick_timeout)` 包裹——**不改 call_json 签名**。超时/异常/解析失败 → 退回 `_rule_pick`。LLM 选页发生在搜索主线内，因此**无 key 时绝不触发**（保 6 步序列）。

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_collection_pipeline.py 追加
import asyncio


@pytest.mark.asyncio
async def test_llm_pick_used_when_key_present(monkeypatch):
    monkeypatch.setattr("src.agents.collection_pipeline.build_pro_sources", lambda category, http: [])
    search = MagicMock()
    search.available.return_value = True
    search.name = "serpapi"
    search.search = AsyncMock(return_value=[
        {"url": "https://a.com/x", "title": "A", "snippet": ""},
        {"url": "https://b.com/y", "title": "B", "snippet": ""},
    ])
    llm = MagicMock()
    llm.call_json = AsyncMock(return_value={"urls": ["https://b.com/y"]})
    parser = MagicMock()
    parser.extract_text.return_value = "有效正文" * 40
    http = MagicMock()
    http.get = AsyncMock(return_value="<html>x</html>")
    pipe = CollectionPipeline(llm=llm, http=http, parser=parser, search_source=search,
                              max_top_n=3, pick_timeout=20, max_concurrency=5)
    text, sources, trace = await pipe.collect("X", "default")
    assert sources == ["https://b.com/y"]  # LLM 只选了 b
    assert any(t.get("step") == "pick" and t.get("method") == "llm" for t in trace)


@pytest.mark.asyncio
async def test_llm_pick_timeout_falls_back_to_rule(monkeypatch):
    monkeypatch.setattr("src.agents.collection_pipeline.build_pro_sources", lambda category, http: [])
    search = MagicMock()
    search.available.return_value = True
    search.name = "serpapi"
    search.search = AsyncMock(return_value=[{"url": "https://a.com/pricing", "title": "", "snippet": ""}])

    async def hang(*a, **k):
        await asyncio.sleep(10)

    llm = MagicMock()
    llm.call_json = AsyncMock(side_effect=hang)
    parser = MagicMock()
    parser.extract_text.return_value = "有效正文" * 40
    http = MagicMock()
    http.get = AsyncMock(return_value="<html>x</html>")
    pipe = CollectionPipeline(llm=llm, http=http, parser=parser, search_source=search,
                              max_top_n=3, pick_timeout=0.05, max_concurrency=5)
    text, sources, trace = await pipe.collect("X", "default")
    assert sources == ["https://a.com/pricing"]  # 退回规则选页
    assert any(t.get("step") == "pick" and t.get("method") == "rule_fallback" for t in trace)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/unit/test_collection_pipeline.py::test_llm_pick_used_when_key_present -v`
Expected: FAIL — 当前固定走 `_rule_pick`，trace method 是 "rule" 不是 "llm"

- [ ] **Step 3: 加 LLM 选页 + 超时回退**

在 `collection_pipeline.py` 顶部加 prompt 常量；加 `_llm_pick` 方法；改 `collect` 内选页段。

顶部加：

```python
PICK_SYSTEM = (
    "你是竞品资料筛选助手。给定候选网页列表（url/title/snippet），"
    "选出最可能含目标竞品官方产品/功能/定价信息的页面。"
    '只返回 JSON：{"urls": ["选中的url", ...]}，最多选 N 个，按相关度排序。'
)
```

加方法：

```python
    async def _llm_pick(self, candidates: list[dict], name: str, top_n: int) -> list[dict] | None:
        """LLM 选页，外层超时；超时/异常/解析失败返回 None（调用方退回规则）。"""
        import json
        listing = "\n".join(
            f"{i}. {c.get('url')} | {c.get('title', '')} | {c.get('snippet', '')}"
            for i, c in enumerate(candidates)
        )
        user = f"竞品：{name}\n最多选 {top_n} 个。候选：\n{listing}"
        try:
            result = await asyncio.wait_for(
                self.llm.call_json(PICK_SYSTEM, user), timeout=self.pick_timeout
            )
        except Exception as e:  # noqa: BLE001 — 含 TimeoutError；任何失败都退回规则选页
            logger.warning("[pipeline] LLM 选页失败/超时, 退回规则: %s", e)
            return None
        urls = result.get("urls") if isinstance(result, dict) else None
        if not isinstance(urls, list):
            return None
        by_url = {c.get("url"): c for c in candidates}
        picked = [by_url[u] for u in urls if u in by_url][:top_n]
        return picked or None
```

改 `collect` 内选页段（替换 Task 8 的 `picked = self._rule_pick(...)` 那段）：

```python
            candidates = await self.search_source.search(f"{competitor_name} 产品 功能 定价")
            picked = await self._llm_pick(candidates, competitor_name, self.max_top_n)
            if picked is not None:
                trace.append({"step": "pick", "method": "llm", "picked": [c["url"] for c in picked]})
            else:
                picked = self._rule_pick(candidates, competitor_name, self.max_top_n)
                trace.append({"step": "pick", "method": "rule_fallback", "picked": [c["url"] for c in picked]})
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/unit/test_collection_pipeline.py -v`
Expected: PASS（4 passed）

- [ ] **Step 5: Commit**

```bash
git add src/agents/collection_pipeline.py tests/unit/test_collection_pipeline.py
git commit -m "feat: 管线 LLM 选页（独立短超时 wait_for，失败退规则，不改 call_json 签名）"
```

---

### Task 10: CollectionPipeline — 闸门集成 + sources 安全 + 去重断言

**Files:**
- Modify: 无（行为已在 Task 8/9 实现）
- Test: `tests/unit/test_collection_pipeline.py`（追加验证性测试）

**说明**：本任务不写新实现，补关键安全/集成断言（doubt-driven 要求的负向测试）：①软404页被闸门挡掉、不进 sources；②含 key 的 URL 不会出现在 sources（因为 sources 只来自选中候选/专源 result.url，搜索 endpoint 不入）；③重复 URL 去重。

- [ ] **Step 1: 写测试**

```python
# tests/unit/test_collection_pipeline.py 追加
@pytest.mark.asyncio
async def test_soft404_page_excluded_from_sources(monkeypatch):
    monkeypatch.setattr("src.agents.collection_pipeline.build_pro_sources", lambda category, http: [])
    search = MagicMock()
    search.available.return_value = True
    search.name = "serpapi"
    search.search = AsyncMock(return_value=[{"url": "https://a.com/404page", "title": "", "snippet": ""}])
    llm = MagicMock()
    llm.call_json = AsyncMock(return_value={"urls": ["https://a.com/404page"]})
    parser = MagicMock()
    parser.extract_text.return_value = "404 页面不存在"  # 软404
    http = MagicMock()
    http.get = AsyncMock(return_value="<html>404</html>")
    pipe = CollectionPipeline(llm=llm, http=http, parser=parser, search_source=search,
                              max_top_n=3, pick_timeout=20, max_concurrency=5)
    text, sources, trace = await pipe.collect("X", "default")
    assert sources == []          # 软404 被闸门挡掉
    assert "页面不存在" not in text


@pytest.mark.asyncio
async def test_sources_dedup(monkeypatch):
    from src.tools.sources import SourceResult
    fake = MagicMock(); fake.name = "itunes"
    fake.collect = AsyncMock(return_value=[
        SourceResult(url="https://dup.com", text="正文一" * 30),
        SourceResult(url="https://dup.com", text="正文二" * 30),  # 同 URL
    ])
    monkeypatch.setattr("src.agents.collection_pipeline.build_pro_sources", lambda category, http: [fake])
    search = MagicMock(); search.available.return_value = False
    pipe = CollectionPipeline(llm=MagicMock(), http=MagicMock(), parser=MagicMock(),
                              search_source=search, max_top_n=3, pick_timeout=20, max_concurrency=5)
    text, sources, trace = await pipe.collect("X", "saas")
    assert sources == ["https://dup.com"]  # 去重
```

- [ ] **Step 2: 跑测试**

Run: `pytest tests/unit/test_collection_pipeline.py -v`
Expected: PASS（6 passed）。若软404 未被挡，回查 Task 3 闸门阈值与 Task 8 `_fetch_clean`。

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_collection_pipeline.py
git commit -m "test: 管线闸门集成 + sources 安全（软404排除/去重）负向断言"
```

---

### Task 11: collector — detect_category（零 LLM）+ 占位 profile builder

**Files:**
- Modify: `src/agents/collector.py`
- Test: `tests/unit/test_collector.py`（追加，暂不改现有用例）

**说明**：本任务只**新增**两个不依赖 pipeline 的方法，不改构造器（构造器迁移留 Task 12，便于隔离回归）。`detect_category` 零 LLM——优先用 `comp.category`，空则规则匹配 name/company，全空归 default。`_build_placeholder_profile` 构造合法 `CompetitorProfile`，completeness 显式 0.0、data_sources=[]、不调 LLM。

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_collector.py 追加
from src.schemas.input import CompetitorBasic
from src.schemas.profile import CompetitorProfile


def test_detect_category_uses_input_category():
    agent = CollectorAgent(llm=MagicMock(), http=MagicMock(), parser=MagicMock())
    comp = CompetitorBasic(name="Notion", category="协作软件")
    assert agent.detect_category(comp) == "saas"  # 零 LLM


def test_detect_category_default_when_unknown():
    agent = CollectorAgent(llm=MagicMock(), http=MagicMock(), parser=MagicMock())
    comp = CompetitorBasic(name="某硬件", category="消费电子")
    assert agent.detect_category(comp) == "default"


def test_detect_category_calls_no_llm():
    mock_llm = MagicMock()
    mock_llm.call_json = AsyncMock()
    agent = CollectorAgent(llm=mock_llm, http=MagicMock(), parser=MagicMock())
    agent.detect_category(CompetitorBasic(name="X", category="工具"))
    mock_llm.call_json.assert_not_called()  # 零 LLM 硬约束


def test_build_placeholder_profile():
    agent = CollectorAgent(llm=MagicMock(), http=MagicMock(), parser=MagicMock())
    comp = CompetitorBasic(name="某竞品", company="某公司")
    classification = {"competitor_type": "核心竞品", "reason": "占位"}
    profile = agent._build_placeholder_profile(comp, classification, trace=[{"step": "all_empty"}])
    assert isinstance(profile, CompetitorProfile)
    assert profile.metadata.completeness_score == 0.0
    assert profile.metadata.data_sources == []
    assert profile.basic_info.name == "某竞品"
    assert profile.metadata.pipeline_trace == [{"step": "all_empty"}]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/unit/test_collector.py -k "detect_category or placeholder" -v`
Expected: FAIL — 无 `detect_category` / `_build_placeholder_profile`

- [ ] **Step 3: 实现两个方法**

`src/agents/collector.py` 顶部 import 加入 `from src.schemas.profile import Classification, BasicInfo, ProfileMetadata`（与现有 `CompetitorProfile` 同 import 行扩展）和 `from src.tools.sources import normalize_category`。在 `CollectorAgent` 内加：

```python
    def detect_category(self, comp: CompetitorBasic) -> str:
        """零 LLM 判断产品形态（saas/default），供专源路由。"""
        signal = comp.category or comp.name or comp.company or ""
        return normalize_category(signal)

    def _build_placeholder_profile(self, comp: CompetitorBasic, classification: dict, trace: list) -> CompetitorProfile:
        """全空时构造占位 profile：不调 LLM，completeness 显式 0.0。"""
        return CompetitorProfile(
            classification=Classification(**classification),
            basic_info=BasicInfo(name=comp.name, company=comp.company or ""),
            metadata=ProfileMetadata(
                collected_at=datetime.now(timezone.utc).isoformat(),
                data_sources=[],
                completeness_score=0.0,
                pipeline_trace=trace,
            ),
        )
```

（`datetime`/`timezone` collector.py 顶部已 import。）

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/unit/test_collector.py -k "detect_category or placeholder" -v`
Expected: PASS（4 passed）

- [ ] **Step 5: Commit**

```bash
git add src/agents/collector.py tests/unit/test_collector.py
git commit -m "feat: collector 加 detect_category（零LLM）与占位 profile 构造器"
```

---

### Task 12: collector — 构造器迁移 (llm, pipeline) + _collect_single 调管线 + 顶层部分降级

**Files:**
- Modify: `src/agents/collector.py`
- Test: `tests/unit/test_collector.py`（改 :17/:29/:52 三处构造 + 改 test_collect_returns_profiles）

**说明**：本任务一次性完成构造器迁移、删旧采集代码、_collect_single 调 pipeline、顶层 collect 改 `return_exceptions=True`。删除 `URL_TEMPLATES`/`_fetch_and_parse`/`_parse_itunes`（已迁 sources）。`_collect_single` 流程：classify → detect_category → pipeline.collect → 全空则占位、否则 _extract_profile。

- [ ] **Step 1: 改现有单测构造器引用**

`tests/unit/test_collector.py`：
- :17、:29 的 `CollectorAgent(llm=mock_llm, http=MagicMock(), parser=MagicMock())` → `CollectorAgent(llm=mock_llm, pipeline=MagicMock())`
- Task 11 加的 4 个测试里的 `CollectorAgent(llm=..., http=MagicMock(), parser=MagicMock())` 同样改为 `CollectorAgent(llm=..., pipeline=MagicMock())`
- 重写 `test_collect_returns_profiles`（原 :34-59）为 mock pipeline 版本：

```python
    @pytest.mark.asyncio
    async def test_collect_returns_profiles(self, sample_competitor_profile):
        mock_llm = MagicMock()
        mock_llm.call_json = AsyncMock(side_effect=[
            # parse_goal
            {"goal_type": "competitive_monitoring", "product_stage": "growing", "focus_area": "", "output_expectation": "action"},
            # classify
            {"competitor_type": "核心竞品", "reason": "test"},
            # extract_profile（剔除 classification/metadata 的 raw）
            {k: v for k, v in sample_competitor_profile.items() if k not in ("classification", "metadata")},
        ])
        mock_pipeline = MagicMock()
        mock_pipeline.collect = AsyncMock(return_value=("支付宝 移动支付正文" * 10,
                                                        ["https://www.alipay.com/features"],
                                                        [{"step": "route"}]))
        agent = CollectorAgent(llm=mock_llm, pipeline=mock_pipeline)
        user_input = CompetitorInput(
            competitors=[CompetitorBasic(name="支付宝")],
            analysis_context="分析支付宝",
        )
        profiles = await agent.collect(user_input)
        assert len(profiles) == 1
        assert isinstance(profiles[0], CompetitorProfile)
        assert profiles[0].metadata.pipeline_trace == [{"step": "route"}]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/unit/test_collector.py -v`
Expected: FAIL — 构造器仍是 `(llm, http, parser)`，`pipeline=` kwarg 报 TypeError

- [ ] **Step 3: 改 collector.py**

① 删除 `URL_TEMPLATES` 常量块（:12-20）、`_fetch_and_parse`（:60-67）、`_parse_itunes`（:69-85）。
② 构造器改：

```python
    def __init__(self, llm, pipeline):
        self.llm = llm
        self.pipeline = pipeline
```

③ `_normalize_raw` 增加 `pipeline_trace` 参数并写入 metadata：

```python
    @staticmethod
    def _normalize_raw(raw: dict, classification: dict, sources: list[str], pipeline_trace: list) -> dict:
        reviews = raw.get("user_reviews", {}).get("sample_reviews")
        if isinstance(reviews, list):
            raw["user_reviews"]["sample_reviews"] = [
                {"content": r, "rating": 3} if isinstance(r, str) else r
                for r in reviews
            ]
        raw["classification"] = classification
        raw["metadata"] = {
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "data_sources": sources,
            "completeness_score": CollectorAgent._calc_completeness_static(raw),
            "pipeline_trace": pipeline_trace,
        }
        return raw
```

④ `_extract_profile` 增加 `pipeline_trace` 参数并透传：

```python
    async def _extract_profile(self, name: str, text: str, classification: dict,
                               sources: list[str], pipeline_trace: list) -> CompetitorProfile:
        prompt = f"竞品名称：{name}\n\n网页文本内容：\n{text[:8000]}"
        raw = self._normalize_raw(await self.llm.call_json(COLLECTOR_EXTRACT_SYSTEM, prompt),
                                  classification, sources, pipeline_trace)
        try:
            return CompetitorProfile(**raw)
        except ValidationError as e:
            logger.warning("[collector] _extract_profile 校验失败, 重试: %s", e)
            raw = self._normalize_raw(await self.llm.call_json(COLLECTOR_EXTRACT_SYSTEM, prompt),
                                      classification, sources, pipeline_trace)
            try:
                return CompetitorProfile(**raw)
            except ValidationError as e2:
                logger.error("[collector] _extract_profile 重试后仍然失败: %s, raw=%s", e2, raw)
                raise ValueError(f"Collector _extract_profile validation failed after retry: {e2}") from e2
```

⑤ `_collect_single` 重写为调 pipeline：

```python
    async def _collect_single(self, comp: CompetitorBasic, goal: AnalysisGoal) -> CompetitorProfile:
        """采集单个竞品：分类 → 类别路由 → 管线采集 → 抽取/占位。"""
        classification = await self.classify_competitor(comp.name, goal)
        category = self.detect_category(comp)
        merged_text, sources, trace = await self.pipeline.collect(comp.name, category)
        if not merged_text.strip():
            profile = self._build_placeholder_profile(comp, classification, trace)
            logger.info("[collector] %s 全空, 产占位 profile", comp.name)
            return profile
        profile = await self._extract_profile(comp.name, merged_text, classification, sources, trace)
        logger.info("[collector] %s 采集完成, completeness=%.2f", comp.name, profile.metadata.completeness_score)
        return profile
```

⑥ 顶层 `collect` 改部分降级：

```python
    async def collect(self, user_input: CompetitorInput) -> list[CompetitorProfile]:
        """完整采集流程：目标解析 → 并行采集所有竞品（单竞品失败产占位，不拖垮全局）。"""
        goal = await self.parse_goal(user_input.analysis_context)
        results = await asyncio.gather(
            *[self._collect_single(comp, goal) for comp in user_input.competitors],
            return_exceptions=True,
        )
        profiles: list[CompetitorProfile] = []
        for comp, r in zip(user_input.competitors, results):
            if isinstance(r, CompetitorProfile):
                profiles.append(r)
            else:
                logger.error("[collector] %s 采集彻底失败, 产占位: %s", comp.name, r)
                profiles.append(self._build_placeholder_profile(
                    comp, {"competitor_type": "核心竞品", "reason": "采集失败占位"},
                    trace=[{"step": "collect_failed", "error": str(r)}],
                ))
        return profiles
```

- [ ] **Step 4: 跑 collector 单测确认通过**

Run: `pytest tests/unit/test_collector.py -v`
Expected: PASS（原有 + Task 11 新增全绿）

- [ ] **Step 5: Commit**

```bash
git add src/agents/collector.py tests/unit/test_collector.py
git commit -m "refactor: collector 构造器改 (llm,pipeline)，采集下沉管线，顶层改部分降级"
```

---

### Task 13: collector — 单竞品部分失败 + 全空占位回归测试

**Files:**
- Test: `tests/unit/test_collector.py`（追加）

**说明**：补 doubt-driven 要求的两个降级回归——①多竞品一成一败：失败竞品出占位、成功竞品正常；②全空（pipeline 返回空 text）→ 占位 profile，且不调 extract LLM。

- [ ] **Step 1: 写测试**

```python
# tests/unit/test_collector.py 追加
    @pytest.mark.asyncio
    async def test_partial_failure_one_competitor_placeholder(self, sample_competitor_profile):
        mock_llm = MagicMock()
        raw_profile = {k: v for k, v in sample_competitor_profile.items() if k not in ("classification", "metadata")}
        # parse_goal, A:classify, A:extract, B:classify(抛)
        mock_llm.call_json = AsyncMock(side_effect=[
            {"goal_type": "competitive_monitoring", "product_stage": "growing", "focus_area": "", "output_expectation": "action"},
            {"competitor_type": "核心竞品", "reason": "ok"},
            raw_profile,
            RuntimeError("B classify 炸了"),
        ])
        mock_pipeline = MagicMock()
        mock_pipeline.collect = AsyncMock(return_value=("有效正文" * 30, ["https://a.com"], []))
        agent = CollectorAgent(llm=mock_llm, pipeline=mock_pipeline)
        user_input = CompetitorInput(
            competitors=[CompetitorBasic(name="甲竞品"), CompetitorBasic(name="乙竞品")],
            analysis_context="对比",
        )
        profiles = await agent.collect(user_input)
        assert len(profiles) == 2  # 一个都不少
        assert profiles[1].metadata.completeness_score == 0.0  # 乙占位

    @pytest.mark.asyncio
    async def test_all_empty_produces_placeholder_no_extract_llm(self):
        mock_llm = MagicMock()
        mock_llm.call_json = AsyncMock(side_effect=[
            {"goal_type": "competitive_monitoring", "product_stage": "growing", "focus_area": "", "output_expectation": "action"},
            {"competitor_type": "核心竞品", "reason": "ok"},
        ])  # 只有 parse_goal + classify，无 extract
        mock_pipeline = MagicMock()
        mock_pipeline.collect = AsyncMock(return_value=("", [], [{"step": "all_empty"}]))  # 全空
        agent = CollectorAgent(llm=mock_llm, pipeline=mock_pipeline)
        user_input = CompetitorInput(
            competitors=[CompetitorBasic(name="空竞品")], analysis_context="x",
        )
        profiles = await agent.collect(user_input)
        assert profiles[0].metadata.completeness_score == 0.0
        assert mock_llm.call_json.call_count == 2  # 没调 extract（否则会 StopIteration）
```

- [ ] **Step 2: 跑测试确认通过**

Run: `pytest tests/unit/test_collector.py -k "partial_failure or all_empty" -v`
Expected: PASS（2 passed）

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_collector.py
git commit -m "test: collector 部分降级回归（单竞品失败占位 + 全空不调extract LLM）"
```

---

### Task 14: builder — 组装 pipeline 注入 collector（build_graph 签名不变）

**Files:**
- Modify: `src/graph/builder.py:14`
- Test: 现有 `tests/integration/test_graph.py`（Task 15 适配）

**说明**：`build_graph` 仍收 `(llm, http, parser, trace_writer)`，内部构造 SerpAPI 源 + pipeline，再注入 collector。无 key 时 `SerpApiSource.available()=False`，pipeline 走专源降级——集成测试环境无 key，因此 collector 内仍只有 classify + extract 两次 LLM 调用，6 步序列保持。

- [ ] **Step 1: 改 builder.py**

`src/graph/builder.py` 顶部 import 加：

```python
from src.agents.collection_pipeline import CollectionPipeline
from src.tools.sources import SerpApiSource
from src.utils.config import settings
```

`build_graph` 内 `collector = CollectorAgent(...)`（:14）替换为：

```python
    search_source = SerpApiSource(http=http, api_key=settings.SEARCH_API_KEY)
    pipeline = CollectionPipeline(
        llm=llm, http=http, parser=parser, search_source=search_source,
        max_top_n=settings.SEARCH_TOP_N, pick_timeout=settings.PICK_LLM_TIMEOUT,
        max_concurrency=settings.MAX_FETCH_CONCURRENCY,
    )
    collector = CollectorAgent(llm=llm, pipeline=pipeline)
```

- [ ] **Step 2: 跑全量，预期集成测试此时可能因 mock 缺 get_json 等而失败**

Run: `pytest tests/integration -v`
Expected: 可能 FAIL（Task 15 修）。先观察失败信息，确认是接线相关而非逻辑错误。

- [ ] **Step 3: Commit（接线本身）**

```bash
git add src/graph/builder.py
git commit -m "feat: build_graph 内组装 CollectionPipeline 注入 collector（签名不变）"
```

---

### Task 15: 集成测试适配 + 全量回归

**Files:**
- Modify: `tests/integration/test_graph.py`、`tests/integration/test_api.py`、`tests/integration/test_trace_api.py`

**说明**：集成测试 mock 的 `mock_http` 默认无 `SEARCH_API_KEY`（测试环境不设），`SerpApiSource.available()=False` → 走专源降级。但 saas 路由会触发 iTunes 专源 → 调 `http.get_json`。现有 mock 只有 `mock_http.get`。两种修法择一：①给 mock_http 补 `get_json` 返回 None（专源无结果 → 全空 → 占位 profile）；②让测试输入 category 为 default（不触发 iTunes）。**推荐 ①**——更贴近真实降级，且保持 profile 由 extract 产出（6 步序列不变）需让 pipeline 返回非空 text。

最稳妥：给 `mock_http` 补 `get`（已有，返回 html）→ 但无 key 时不走搜索主线、不抓网页；专源 iTunes 调 `get_json`。所以让 `mock_http.get_json` 返回一个有效 iTunes 结果，使 pipeline 产出非空 text，extract 被调用，6 步序列保持。

- [ ] **Step 1: 给三个集成测试的 mock_http 补 get_json**

在 `test_graph.py`、`test_api.py`、`test_trace_api.py` 每处构造 `mock_http` 后（`mock_http.get = AsyncMock(...)` 旁）追加：

```python
        mock_http.get_json = AsyncMock(return_value={
            "results": [{
                "trackName": "支付宝", "formattedPrice": "免费",
                "averageUserRating": 4.7, "userRatingCount": 20000,
                "sellerName": "Ant", "description": "移动支付平台介绍" * 10,
                "trackViewUrl": "https://apps.apple.com/app/id1",
            }]
        })
```

并确保测试输入竞品的 category 触发 saas 路由——给输入竞品显式带 category（若用 dict 输入 `{"name": "支付宝", "category": "金融软件"}`，"软件" → saas）。检查每个测试的 `competitors` 输入，补 `"category": "金融软件"`。

- [ ] **Step 2: 确认 6 步序列断言仍成立**

无 key → 不走搜索主线 → 不调 LLM 选页。collector 内 LLM 调用仍为 classify + extract 两次；全链路 6 步 `parse_goal→classify→extract→analyzer→writer→inspector` 不变。`node_trace[:4]==["collector","analyzer","writer","inspector"]` 不变（pipeline_trace 不进 node_trace）。

Run: `pytest tests/integration -v`
Expected: PASS（4 个集成测试全绿）

- [ ] **Step 3: 全量回归**

Run: `pytest -q`
Expected: 现有 51+ 全绿 + 本次新增全绿（test_profile_schema/test_config/test_quality_gate/test_sources/test_collection_pipeline + collector 新增）

- [ ] **Step 4: ruff 清理**

Run: `ruff check src tests`
Expected: 无错误（如有 import 未用等，`ruff check --fix src tests`）

- [ ] **Step 5: Commit**

```bash
git add tests/integration
git commit -m "test: 集成测试适配新采集接线（mock get_json，保 6 步序列），全量回归通过"
```

---

## 实现完成后

- 更新 `PROGRESS.md`、`DECISIONS.md`（记录：采集管线下沉、SerpAPI 接入、顶层部分降级语义变更）
- `CLAUDE.md` 代码架构段补充 CollectionPipeline 分层（collector→pipeline→sources）
- 真实跑通验证（需配 `SEARCH_API_KEY` 才走搜索主线；无 key 验证专源降级路径）
- 合并分支回 master

> 注：本计划仅做数据源采集层。报告质量缺陷（PROGRESS 2026-06-02 记录的溯源下沉断链/SWOT 丢失/focus_area 空）是独立课题，不在本计划范围。
