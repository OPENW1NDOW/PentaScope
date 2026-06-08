"""Writer 4 阶段编排 prompts 包。

组织（v3 spec P3=a）：
- outline/{s1..s5}.py — Phase 1 骨架字段约束
- payload/{s1..s5}.py — Phase 2 场景特有载荷
- narrative/_common.py + sections.py — Phase 3 章节模板 + 28 项 _SECTION_CONTEXT_MAP
"""
from src.agents.prompts.writer.outline import WRITER_OUTLINE_PROMPTS
from src.agents.prompts.writer.payload import WRITER_PAYLOAD_PROMPTS
from src.agents.prompts.writer.narrative import (
    NARRATIVE_TEMPLATE,
    SECTION_LABELS,
    SECTION_FOCUS_HINTS,
    SECTION_CONTEXT_MAP,
)

__all__ = [
    "WRITER_OUTLINE_PROMPTS",
    "WRITER_PAYLOAD_PROMPTS",
    "NARRATIVE_TEMPLATE",
    "SECTION_LABELS",
    "SECTION_FOCUS_HINTS",
    "SECTION_CONTEXT_MAP",
]
