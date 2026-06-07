import pytest
from unittest.mock import AsyncMock

from src.tools.scenario_picker import ai_pick_scenario, SCENARIO_PICKER_SYSTEM


@pytest.mark.asyncio
async def test_ai_pick_returns_valid_scenario():
    """LLM 返回的 scenario 必须在 5 个枚举内"""
    mock_llm = AsyncMock()
    mock_llm.call_json.return_value = {
        "scenario": "S1",
        "confidence": "high",
        "rationale": "用户已有产品并准备做新功能，对比竞品功能差距",
    }
    result = await ai_pick_scenario("我们准备做协作文档产品，想看竞品", llm=mock_llm)

    assert result["scenario"] in {"S1", "S2", "S3", "S4", "S5"}
    assert result["confidence"] in {"high", "medium", "low"}
    assert "rationale" in result


@pytest.mark.asyncio
async def test_ai_pick_passes_system_prompt():
    """ai_pick_scenario 调用 LLM 时必须传入 SCENARIO_PICKER_SYSTEM"""
    mock_llm = AsyncMock()
    mock_llm.call_json.return_value = {"scenario": "S2", "confidence": "medium", "rationale": "用户在做行业调研"}
    await ai_pick_scenario("我想了解 SaaS 行业", llm=mock_llm)

    mock_llm.call_json.assert_called_once()
    call_args = mock_llm.call_json.call_args
    assert call_args[0][0] == SCENARIO_PICKER_SYSTEM
    assert "我想了解 SaaS 行业" in call_args[0][1]
