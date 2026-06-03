import pytest
from unittest.mock import AsyncMock, MagicMock
from src.tools.sources import ItunesSource, SourceResult
from src.tools.sources import SerpApiSource


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
    assert "SECRET" not in captured["url"]
    assert captured["headers"]["Authorization"] == "Bearer SECRET"


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
