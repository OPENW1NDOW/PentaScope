"""Phase 3 narrative 共用模板与 28 项 section 元信息。"""
from src.agents.prompts.writer.narrative._common import NARRATIVE_TEMPLATE
from src.agents.prompts.writer.narrative.sections import (
    SECTION_LABELS,
    SECTION_FOCUS_HINTS,
    SECTION_CONTEXT_MAP,
)

__all__ = [
    "NARRATIVE_TEMPLATE",
    "SECTION_LABELS",
    "SECTION_FOCUS_HINTS",
    "SECTION_CONTEXT_MAP",
]
