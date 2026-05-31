import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from src.tools.llm_client import LLMClient


class TestLLMClient:
    @pytest.mark.asyncio
    async def test_call_json_returns_parsed_dict(self):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({"key": "value"})

        client = LLMClient(api_key="test", base_url="https://test.com", model_ep="ep-test")
        with patch.object(client.client.chat.completions, "create", new_callable=AsyncMock, return_value=mock_response):
            result = await client.call_json("system prompt", "user prompt")
            assert result == {"key": "value"}

    @pytest.mark.asyncio
    async def test_call_json_retries_on_invalid_json(self):
        mock_bad = MagicMock()
        mock_bad.choices = [MagicMock()]
        mock_bad.choices[0].message.content = "not json"

        mock_good = MagicMock()
        mock_good.choices = [MagicMock()]
        mock_good.choices[0].message.content = json.dumps({"ok": True})

        client = LLMClient(api_key="test", base_url="https://test.com", model_ep="ep-test")
        with patch.object(client.client.chat.completions, "create", new_callable=AsyncMock, side_effect=[mock_bad, mock_good]):
            result = await client.call_json("sys", "usr")
            assert result == {"ok": True}

    @pytest.mark.asyncio
    async def test_call_json_raises_after_max_retries(self):
        mock_bad = MagicMock()
        mock_bad.choices = [MagicMock()]
        mock_bad.choices[0].message.content = "not json"

        client = LLMClient(api_key="test", base_url="https://test.com", model_ep="ep-test")
        with patch.object(client.client.chat.completions, "create", new_callable=AsyncMock, return_value=mock_bad):
            with pytest.raises(ValueError, match="Failed to parse"):
                await client.call_json("sys", "usr")
