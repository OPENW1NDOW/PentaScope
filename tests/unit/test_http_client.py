import pytest
import httpx
from unittest.mock import AsyncMock, patch
from src.tools.http_client import HttpClient


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
