"""ai_pick_scenario 工具函数单测。"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from src.tools.scenario_picker import ai_pick_scenario


@pytest.mark.asyncio
async def test_ai_pick_returns_valid_scenario():
    """正常路径：LLM 返回合法 scenario + confidence + rationale"""
    mock_llm = MagicMock()
    mock_llm.call_json = AsyncMock(return_value={
        "scenario": "S1",
        "confidence": "high",
        "rationale": "用户描述含「已有产品」和「想看竞品功能差距」关键词，明确指向 S1 功能迭代",
    })
    result = await ai_pick_scenario(
        "我们准备做协作文档产品，想看竞品有什么功能我们没有的",
        llm=mock_llm,
    )
    assert result["scenario"] == "S1"
    assert result["confidence"] == "high"
    assert "S1" in result["rationale"] or "功能迭代" in result["rationale"]


@pytest.mark.asyncio
async def test_ai_pick_falls_back_on_invalid_scenario():
    """LLM 返回非法 scenario → 兜底 S1 + confidence=low"""
    mock_llm = MagicMock()
    mock_llm.call_json = AsyncMock(return_value={
        "scenario": "S99",  # 非法
        "confidence": "high",
        "rationale": "...",
    })
    result = await ai_pick_scenario("...", llm=mock_llm)
    assert result["scenario"] == "S1"  # 兜底
    # confidence=high 仍透传（仅 scenario 兜底为 S1）


@pytest.mark.asyncio
async def test_ai_pick_falls_back_on_invalid_confidence():
    """LLM 返回非法 confidence → 兜底 low"""
    mock_llm = MagicMock()
    mock_llm.call_json = AsyncMock(return_value={
        "scenario": "S2",
        "confidence": "very_high",  # 非法
        "rationale": "x" * 30,
    })
    result = await ai_pick_scenario("...", llm=mock_llm)
    assert result["scenario"] == "S2"
    assert result["confidence"] == "low"


@pytest.mark.asyncio
async def test_ai_pick_handles_missing_fields():
    """LLM 返回空 dict → 全部兜底"""
    mock_llm = MagicMock()
    mock_llm.call_json = AsyncMock(return_value={})
    result = await ai_pick_scenario("...", llm=mock_llm)
    assert result["scenario"] == "S1"
    assert result["confidence"] == "low"
    assert "兜底" in result["rationale"]
