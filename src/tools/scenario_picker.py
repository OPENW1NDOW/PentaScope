"""AI 帮用户选场景（前端不确定时调用）。

输入：用户自由文本描述（如"我们做了协作文档想看竞品"）
输出：{scenario: S1/S2/S3/S4/S5, confidence, rationale}
"""
import logging

from src.agents.prompts import SCENARIO_PICKER_SYSTEM

logger = logging.getLogger(__name__)


async def ai_pick_scenario(user_text: str, llm) -> dict:
    """调用 LLM 推断场景。

    返回 dict 含 scenario / confidence / rationale 三字段。
    LLM 漏字段时会从 raw 中补默认值（兜底为 confidence=low + scenario=S1）。
    """
    logger.info("[scenario_picker] 推断场景, user_text 前 50 字: %s", user_text[:50])
    raw = await llm.call_json(SCENARIO_PICKER_SYSTEM, f"用户描述：{user_text}")

    scenario = raw.get("scenario", "")
    if scenario not in {"S1", "S2", "S3", "S4", "S5"}:
        logger.warning("[scenario_picker] LLM 返回非法 scenario=%s，兜底 S1", scenario)
        scenario = "S1"

    confidence = raw.get("confidence", "low")
    if confidence not in {"high", "medium", "low"}:
        confidence = "low"

    rationale = raw.get("rationale", "AI 自动推断（无理由说明，兜底）")

    return {"scenario": scenario, "confidence": confidence, "rationale": rationale}
