import pytest
from unittest.mock import AsyncMock, MagicMock
from src.tools.sources import ItunesSource, SourceResult
from src.tools.sources import SerpApiSource
from src.tools.sources import build_pro_sources, normalize_category


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
    results = await ItunesSource(http).collect("X")  # must NOT raise TypeError
    assert len(results) == 1


@pytest.mark.asyncio
async def test_itunes_skips_empty_shell_record():
    raw = {"results": [
        {"trackName": "", "description": None, "trackViewUrl": "https://x/1"},  # empty shell → skip
        {"trackName": "支付宝", "description": "有效描述" * 10, "trackViewUrl": "https://x/2"},
    ]}
    http = MagicMock()
    http.get_json = AsyncMock(return_value=raw)
    results = await ItunesSource(http).collect("支付宝")
    assert len(results) == 1
    assert results[0].url == "https://x/2"


@pytest.mark.asyncio
async def test_itunes_empty_results():
    http = MagicMock()
    http.get_json = AsyncMock(return_value={"results": []})
    results = await ItunesSource(http).collect("无此应用")
    assert results == []


@pytest.mark.asyncio
async def test_itunes_none_response():
    http = MagicMock()
    http.get_json = AsyncMock(return_value=None)  # request failed
    results = await ItunesSource(http).collect("X")
    assert results == []


@pytest.mark.asyncio
async def test_serpapi_unavailable_without_key():
    src = SerpApiSource(http=MagicMock(), api_key="")
    assert src.available() is False


@pytest.mark.asyncio
async def test_serpapi_available_with_key():
    src = SerpApiSource(http=MagicMock(), api_key="K")
    assert src.available() is True


@pytest.mark.asyncio
async def test_serpapi_search_parses_candidates_and_uses_query_key():
    # SerpAPI 用 api_key query 参数鉴权（Bearer header 遇非 ASCII query 会 401）
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
    # key 走 query 参数，不走 Authorization header
    assert "api_key=SECRET" in captured["url"]
    assert captured["headers"] is None or "Authorization" not in captured["headers"]


@pytest.mark.asyncio
async def test_serpapi_search_chinese_query_encoded():
    # 回归：中文 query 必须 URL 编码（裸非 ASCII 会触发 SerpAPI 401）
    http = MagicMock()
    captured = {}

    async def fake_get_json(url, headers=None):
        captured["url"] = url
        return {"organic_results": []}

    http.get_json = AsyncMock(side_effect=fake_get_json)
    src = SerpApiSource(http=http, api_key="K")
    await src.search("语雀 定价")
    # query 经过编码，不含裸中文字符
    assert "语雀" not in captured["url"]
    assert "%E8%AF%AD%E9%9B%80" in captured["url"]


@pytest.mark.asyncio
async def test_serpapi_search_empty_on_none():
    http = MagicMock()
    http.get_json = AsyncMock(return_value=None)
    src = SerpApiSource(http=http, api_key="K")
    assert await src.search("x") == []


@pytest.mark.asyncio
async def test_serpapi_search_empty_when_unavailable():
    http = MagicMock()
    http.get_json = AsyncMock(return_value={"organic_results": [{"link": "https://a.com"}]})
    src = SerpApiSource(http=http, api_key="")  # no key
    assert await src.search("x") == []
    src.http.get_json.assert_not_called()


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


def test_build_pro_sources_freetext_category_routed():
    # build_pro_sources 接收的是原始 category，内部应规范化
    sources = build_pro_sources("协作软件", http=MagicMock())
    assert any(isinstance(s, ItunesSource) for s in sources)
    assert build_pro_sources("金融科技", http=MagicMock()) == []


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
    assert "飞书功能介绍" in results[0].text
    assert "飞书定价说明" in results[1].text
    assert results[0].url == "https://feishu.cn/docs"


@pytest.mark.asyncio
async def test_tavily_unavailable_without_key():
    from src.tools.sources import TavilySource
    src = TavilySource(MagicMock(), api_key="")
    assert src.available() is False
    results = await src.search("x")
    assert results == []


@pytest.mark.asyncio
async def test_tavily_returns_empty_on_request_failure():
    from src.tools.sources import TavilySource
    http = MagicMock()
    http.get_json = AsyncMock(return_value=None)
    results = await TavilySource(http, api_key="k").search("x")
    assert results == []
