"""inspector agent prompts。

LLM-as-critic v4：critic 是 inspector 内部子模块，单次 LLM 调用同时输出
4 维 rubric 评分 + 关联 issues（spec v4 路线 A）。
"""
from src.agents.prompts.inspector.critic import (
    CRITIC_SYSTEM,
    CRITIC_PROMPT_VERSION,
)

__all__ = ["CRITIC_SYSTEM", "CRITIC_PROMPT_VERSION"]
