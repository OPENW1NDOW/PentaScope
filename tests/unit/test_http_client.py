import pytest
import httpx
from unittest.mock import AsyncMock, patch
from src.tools.http_client import HttpClient, _redact_key


class TestHttpClient:
    @pytest.mark.asyncio
    async def test_get_returns_text(self):
        mock_response = httpx.Response(200, text="<html>ok</html>")
        client = HttpClient()
        with patch.object(
            client.client, "get", new_callable=AsyncMock, return_value=mock_response
        ):
            result = await client.get("https://example.com")
            assert result == "<html>ok</html>"
        await client.close()

    @pytest.mark.asyncio
    async def test_get_returns_none_on_timeout(self):
        client = HttpClient()
        with patch.object(
            client.client,
            "get",
            new_callable=AsyncMock,
            side_effect=httpx.TimeoutException("timeout"),
        ):
            result = await client.get("https://example.com")
            assert result is None
        await client.close()

    @pytest.mark.asyncio
    async def test_get_returns_none_on_404(self):
        mock_response = httpx.Response(404)
        client = HttpClient()
        with patch.object(
            client.client, "get", new_callable=AsyncMock, return_value=mock_response
        ):
            result = await client.get("https://example.com")
            assert result is None
        await client.close()

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
        with patch.object(client.client, "get", new_callable=AsyncMock, side_effect=httpx.TimeoutException("t")):
            result = await client.get_json("https://serpapi.com/search", headers={})
        assert result is None
        await client.close()

    @pytest.mark.asyncio
    async def test_get_json_returns_none_on_invalid_json(self):
        client = HttpClient()
        bad = httpx.Response(200, text="<html>not json</html>")
        with patch.object(client.client, "get", new_callable=AsyncMock, return_value=bad):
            result = await client.get_json("https://serpapi.com/search", headers={})
        assert result is None
        await client.close()


class TestPostJson:
    @pytest.mark.asyncio
    async def test_post_json_sends_body_and_headers(self):
        client = HttpClient()
        payload = {"results": [{"url": "https://x.com", "raw_content": "正文"}]}
        mock_resp = httpx.Response(200, json=payload)
        captured = {}

        async def fake_post(url, json=None, headers=None):
            captured["url"] = url
            captured["json"] = json
            captured["headers"] = headers
            return mock_resp

        with patch.object(client.client, "post", side_effect=fake_post):
            result = await client.post_json(
                "https://api.tavily.com/search",
                {"query": "x"},
                headers={"Authorization": "Bearer K"},
            )
        assert result == payload
        assert captured["json"] == {"query": "x"}
        assert captured["headers"] == {"Authorization": "Bearer K"}
        assert "Authorization" not in client.client.headers
        await client.close()

    @pytest.mark.asyncio
    async def test_post_json_returns_none_on_non_200(self):
        client = HttpClient()
        with patch.object(client.client, "post", new_callable=AsyncMock, return_value=httpx.Response(401)):
            result = await client.post_json("https://api.tavily.com/search", {"query": "x"}, headers={})
        assert result is None
        await client.close()

    @pytest.mark.asyncio
    async def test_post_json_returns_none_on_timeout(self):
        client = HttpClient()
        with patch.object(client.client, "post", new_callable=AsyncMock, side_effect=httpx.TimeoutException("t")):
            result = await client.post_json("https://api.tavily.com/search", {"query": "x"}, headers={})
        assert result is None
        await client.close()


def test_redact_key_masks_query_param():
    out = _redact_key("https://serpapi.com/search?q=x&api_key=SECRET123")
    assert "SECRET123" not in out
    assert "api_key=" in out
