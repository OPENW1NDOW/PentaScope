import pytest
from unittest.mock import AsyncMock, MagicMock
from src.tools.sources import SourceResult


@pytest.mark.asyncio
async def test_tavily_parses_results_with_body():
    from src.tools.sources import TavilySource
    raw = {"results": [
        {"url": "https://feishu.cn/docs", "raw_content": "飞书功能介绍" * 30, "content": "短摘要"},
        {"url": "https://feishu.cn/pricing", "raw_content": "", "content": "飞书定价说明" * 30},
    ]}
    http = MagicMock()
    http.post_json_with_status = AsyncMock(return_value=(raw, 200))
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
    """[#13] post_json_with_status 返回 (None, None)（网络失败/超时，无状态码）→ 真无结果，返回 []。"""
    from src.tools.sources import TavilySource
    http = MagicMock()
    http.post_json_with_status = AsyncMock(return_value=(None, None))
    results = await TavilySource(http, api_key="k").search("x")
    assert results == []


@pytest.mark.asyncio
async def test_tavily_returns_empty_on_200_no_results():
    """[#13] 200 但 results 为空 → 合法的无结果，返回 []（不抛异常）。"""
    from src.tools.sources import TavilySource
    http = MagicMock()
    http.post_json_with_status = AsyncMock(return_value=({"results": []}, 200))
    results = await TavilySource(http, api_key="k").search("x")
    assert results == []


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [401, 403])
async def test_tavily_raises_auth_error_on_401_403(status):
    """[#13] 401/403（key 错误/失效）→ 抛 TavilyAuthError，而非静默返回 []。
    让 pipeline/collector 感知 key 异常，避免「配错 key 却产全占位报告无信号」。
    """
    from src.tools.sources import TavilySource, TavilyAuthError
    http = MagicMock()
    http.post_json_with_status = AsyncMock(return_value=(None, status))
    with pytest.raises(TavilyAuthError):
        await TavilySource(http, api_key="bad-key").search("x")


@pytest.mark.asyncio
async def test_tavily_uses_post_bearer_and_search_top_n(monkeypatch):
    # Tavily 官方契约：POST + JSON body，key 走 Authorization: Bearer header
    from src.tools.sources import TavilySource
    monkeypatch.setattr("src.tools.sources.settings.SEARCH_TOP_N", 7)
    captured = {}

    async def fake_post_json_with_status(url, json_body, headers=None):
        captured["url"] = url
        captured["body"] = json_body
        captured["headers"] = headers
        return ({"results": []}, 200)

    http = MagicMock()
    http.post_json_with_status = fake_post_json_with_status
    await TavilySource(http, api_key="SECRET").search("飞书")
    assert captured["url"] == "https://api.tavily.com/search"
    assert captured["body"]["query"] == "飞书"
    assert captured["body"]["max_results"] == 7
    assert captured["body"]["include_raw_content"] is True
    assert captured["headers"]["Authorization"] == "Bearer SECRET"
