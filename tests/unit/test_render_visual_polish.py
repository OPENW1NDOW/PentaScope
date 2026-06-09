"""验证 Cooper 2026-06-10 第 4 批视觉打磨：

1. 导出按钮 CSS 必须 text-decoration: none !important（覆盖 Streamlit 默认）
2. _render_at_a_glance 标题改用「核心要点」（不是误译的「一图看懂」）
3. _render_executive_summary 子标题纯中文（去掉 'Context' / 'Core Thesis' / 'Implications' / 'Path Forward'）
4. _render_appendix 新增「参考资料」小节，扫描全报告 source_refs 收集所有链接
"""
from __future__ import annotations

from src.frontend import render, theme


# ============ 1. 按钮下划线修 ============

def test_btn_export_css_no_underline_with_important():
    """.btn-export 必须 text-decoration: none !important（覆盖 Streamlit 默认 a 下划线）。"""
    css = theme._THEME_CSS
    import re
    # 抓 .btn-export 主规则块（不含 :hover 子选择器）
    match = re.search(r"\.btn-export\s*\{([^}]+)\}", css)
    assert match, ".btn-export CSS 规则块缺失"
    rule = match.group(1)
    assert "text-decoration: none !important" in rule or "text-decoration:none !important" in rule, (
        ".btn-export 必须 text-decoration: none !important（Streamlit 默认 a 选择器优先级高）"
    )


# ============ 2. 「一图看懂」改名 ============

def test_at_a_glance_renders_with_correct_label():
    """_render_at_a_glance 应渲染「核心要点」标题（不是误译的「一图看懂」）。"""
    captured_calls = []

    def fake_subheader(text):
        captured_calls.append(("subheader", text))

    def fake_markdown(text, **_):
        captured_calls.append(("markdown", text))

    import streamlit as st
    real_subheader, real_markdown = st.subheader, st.markdown
    st.subheader = fake_subheader
    st.markdown = fake_markdown
    try:
        render._render_at_a_glance(["要点1", "要点2", "要点3"])
    finally:
        st.subheader, st.markdown = real_subheader, real_markdown

    subheaders = [t for kind, t in captured_calls if kind == "subheader"]
    assert "核心要点" in subheaders, (
        f"_render_at_a_glance 应渲染「核心要点」标题，实际 subheader: {subheaders}"
    )
    assert "一图看懂" not in subheaders, (
        "「一图看懂」是误译（at_a_glance 内容不是图，是要点速览），应改为「核心要点」"
    )


# ============ 3. 执行摘要子标题纯中文 ============

def test_executive_summary_subheaders_chinese_only():
    """_render_executive_summary 子标题应纯中文，不带英文。"""
    captured = []

    def fake_subheader(text):
        captured.append(text)

    def fake_header(_text):
        pass

    def fake_write(_text):
        pass

    def fake_markdown(_text, **_):
        pass

    import streamlit as st
    saved = (st.subheader, st.header, st.write, st.markdown)
    st.subheader, st.header, st.write, st.markdown = (
        fake_subheader, fake_header, fake_write, fake_markdown
    )
    try:
        render._render_executive_summary({
            "context": "x" * 80,
            "core_thesis": "y" * 50,
            "key_findings_brief": ["a"],
            "implications": "z" * 100,
            "path_forward": ["b"],
        })
    finally:
        st.subheader, st.header, st.write, st.markdown = saved

    # 不应出现英文（CommonMark 翻译过来的术语）
    for sub in captured:
        for forbidden_en in ("Context", "Core Thesis", "Implications", "Path Forward"):
            assert forbidden_en not in sub, (
                f"执行摘要子标题应纯中文，不应含 '{forbidden_en}'：实际 subheader '{sub}'"
            )
    # 确实出现了中文标题（不能因为我把所有标题都删了导致测试假绿）
    assert "背景定位" in " ".join(captured) or "核心论断" in " ".join(captured)


# ============ 4. 附录加参考资料小节 ============

def test_appendix_renders_references_section_from_full_report():
    """_render_appendix 新增「参考资料」小节，扫全报告 source_refs 收集去重链接。

    覆盖范围：BaseReport 通用 5 处 + 5 场景 payload 任意嵌套深度的 source_refs。
    """
    # 构造一个含多处 source_refs（含 S4 深嵌套）的最小 report
    report = {
        "appendix": {
            "glossary": {"JTBD": "Jobs to be done"},
        },
        "metadata": {
            "data_sources": [
                {"url": "https://a.com", "title": "A 来源", "confidence": "high"},
            ],
        },
        "key_findings": [
            {"source_refs": [{"url": "https://b.com", "title": "B 报告"}]},
        ],
        "analysis_sections": [
            {"source_refs": [
                {"url": "https://a.com", "title": "A 来源"},  # 重复，应去重
                {"url": "https://c.com", "title": "C 文档"},
            ]},
        ],
        "swot": {
            "strengths": [{"source_refs": [{"url": "https://d.com", "title": "D"}]}],
            "weaknesses": [],
            "opportunities": [],
            "threats": [],
        },
        "recommendations": [
            {"source_refs": [{"url": "https://e.com", "title": "E 行业"}]},
        ],
        # S4 scenario_payload 深嵌套 source_refs（不应漏扫）
        "scenario_payload": {
            "scenario_type": "S4",
            "feature_changes": [
                {"source_refs": [{"url": "https://f.com", "title": "F 公告"}]},
            ],
            "threats": [
                {"source_refs": [{"url": "https://g.com", "title": "G 监测"}]},
            ],
            "battlecards": [
                {"sections": [
                    # 再深一层（虚构）source_refs，验证递归
                    {"source_refs": [{"url": "https://h.com", "title": "H 战卡"}]},
                ]},
            ],
        },
    }

    captured_md = []

    def fake_markdown(text, **_):
        captured_md.append(text)

    def fake_subheader(text):
        captured_md.append(f"[H3] {text}")

    class _FakeExpander:
        def __enter__(self): return self
        def __exit__(self, *_): pass

    def fake_expander(_label, **_):
        return _FakeExpander()

    import streamlit as st
    saved = (st.markdown, st.subheader, st.expander)
    st.markdown, st.subheader, st.expander = (
        fake_markdown, fake_subheader, fake_expander
    )
    try:
        render._render_appendix(report.get("appendix") or {}, report=report)
    finally:
        st.markdown, st.subheader, st.expander = saved

    full_text = "\n".join(captured_md)
    # 1. 「参考资料」小节标题出现
    assert "参考资料" in full_text, "附录必须含「参考资料」subheader"
    # 2. BaseReport 通用 5 处链接（A/B/C/D/E）+ S4 scenario_payload 深嵌套（F/G/H）全部出现
    for url in ("https://a.com", "https://b.com", "https://c.com",
                "https://d.com", "https://e.com",
                "https://f.com", "https://g.com", "https://h.com"):
        assert url in full_text, f"参考资料应含 {url}（含 5 场景 payload 深嵌套）"
