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
