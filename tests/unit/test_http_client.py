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


def test_redact_key_masks_query_param():
    out = _redact_key("https://serpapi.com/search?q=x&api_key=SECRET123")
    assert "SECRET123" not in out
    assert "api_key=" in out
