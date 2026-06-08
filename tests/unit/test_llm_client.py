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

    @pytest.mark.asyncio
    async def test_call_json_max_tokens_default_not_passed(self):
        """[v3-R03] 不传 max_tokens 时不应进 OpenAI SDK kwargs（保持向后兼容）"""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({"k": "v"})

        client = LLMClient(api_key="t", base_url="https://t.com", model_ep="ep-t")
        mock_create = AsyncMock(return_value=mock_response)
        with patch.object(client.client.chat.completions, "create", mock_create):
            await client.call_json("sys", "usr")
        call_kwargs = mock_create.call_args.kwargs
        assert "max_tokens" not in call_kwargs

    @pytest.mark.asyncio
    async def test_call_json_max_tokens_passed_when_specified(self):
        """[v3-R03] 传 max_tokens=4096 时应进 OpenAI SDK kwargs"""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({"k": "v"})

        client = LLMClient(api_key="t", base_url="https://t.com", model_ep="ep-t")
        mock_create = AsyncMock(return_value=mock_response)
        with patch.object(client.client.chat.completions, "create", mock_create):
            await client.call_json("sys", "usr", max_tokens=4096)
        call_kwargs = mock_create.call_args.kwargs
        assert call_kwargs.get("max_tokens") == 4096
