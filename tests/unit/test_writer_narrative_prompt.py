"""[fix13 prove-it] narrative prompt 必须要求 LLM 用 markdown 段落 + 子标题 + 列表。

现象（trace 20260609-203430-a4aab7 报告渲染）：
LLM 把 1500-3000 字 narrative 输出为单一长字符串，前端 st.markdown 渲染成一大段文字
不便阅读。修法是 prompt 显式要求段落、列表、二级标题等 markdown 元素。
"""
from src.agents.prompts.writer.narrative import NARRATIVE_TEMPLATE


def test_narrative_prompt_requires_markdown_paragraphs():
    """prompt 必须要求 LLM 在 narrative 字段值内部用 markdown 段落。"""
    assert "markdown" in NARRATIVE_TEMPLATE.lower() or "段落" in NARRATIVE_TEMPLATE, \
        "narrative prompt 应要求段落或 markdown 排版"


def test_narrative_prompt_clarifies_json_container_vs_field_value():
    """prompt 应澄清"不要 Markdown" 仅指 JSON 容器（不要 ```json 包装），
    narrative 字段值内部必须支持 markdown，避免冲突指令让 LLM 全用纯文本。
    """
    # 关键词：澄清 / 字段值内部 markdown 允许
    text = NARRATIVE_TEMPLATE
    # narrative 字段允许内部 markdown
    assert ("内部" in text and "markdown" in text.lower()) or ("字段值" in text and "段落" in text), \
        "prompt 应明确 narrative 字段值内部允许/要求 markdown 段落"


def test_narrative_prompt_lists_specific_markdown_elements():
    """prompt 应列出具体可用的 markdown 元素（段落空行 / 列表 / 二级或三级标题），
    给 LLM 明确指引而非泛泛说 "用 markdown"。
    """
    text = NARRATIVE_TEMPLATE
    # 至少提到段落、列表、子标题中的多个
    hits = sum([
        "段落" in text or "空行" in text,
        "列表" in text or "- " in text,
        "标题" in text or "###" in text or "##" in text,
    ])
    assert hits >= 2, "prompt 应列出 ≥2 种具体 markdown 元素（段落 / 列表 / 子标题）"
