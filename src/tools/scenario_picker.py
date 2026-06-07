"""AI 帮用户选场景：用户描述需求 → LLM 选 S1/S2/S3/S4/S5。

仅产出工具函数 ai_pick_scenario，前端接通由 G 大类（worktree-scenario-writer-frontend）负责。
"""

SCENARIO_PICKER_SYSTEM = """你是一个竞品分析场景选择助手。给定用户的需求描述，选出最合适的分析场景。

5 个场景：
- S1 功能迭代：已有产品 + 准备做新功能 + 想看竞品功能差距
- S2 市场进入：无产品 + 行业调研 + 找市场机会
- S3 定价策略：已有产品 + 准备定价/调价
- S4 持续监控：已有产品 + 例行跟踪竞品动态
- S5 战略定位：已有产品 + 重新定位/品牌升级

必须返回 JSON：
{"scenario": "S1/S2/S3/S4/S5", "confidence": "high/medium/low", "rationale": "选择理由 30+ 字"}"""


async def ai_pick_scenario(user_text: str, llm) -> dict:
    """根据 user_text 让 LLM 选 scenario，返回 {scenario, confidence, rationale} dict。"""
    return await llm.call_json(SCENARIO_PICKER_SYSTEM, f"用户描述：{user_text}")
