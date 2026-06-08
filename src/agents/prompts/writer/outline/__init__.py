"""5 场景 Phase 1 outline prompts。

每个 OUTLINE_PROMPT 强制 LLM 一次性产出 BaseReport 全部非 payload/sections/swot 字段
（共 19 个必填字段，[v3-R21]）。
"""
from src.agents.prompts.writer.outline.s1 import S1_OUTLINE_PROMPT
from src.agents.prompts.writer.outline.s2 import S2_OUTLINE_PROMPT
from src.agents.prompts.writer.outline.s3 import S3_OUTLINE_PROMPT
from src.agents.prompts.writer.outline.s4 import S4_OUTLINE_PROMPT
from src.agents.prompts.writer.outline.s5 import S5_OUTLINE_PROMPT

WRITER_OUTLINE_PROMPTS: dict[str, str] = {
    "S1": S1_OUTLINE_PROMPT,
    "S2": S2_OUTLINE_PROMPT,
    "S3": S3_OUTLINE_PROMPT,
    "S4": S4_OUTLINE_PROMPT,
    "S5": S5_OUTLINE_PROMPT,
}

__all__ = ["WRITER_OUTLINE_PROMPTS"]
