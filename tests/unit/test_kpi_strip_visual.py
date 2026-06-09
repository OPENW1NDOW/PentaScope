"""验证 KPI 卡等高 CSS 规则 + 导出按钮无 'download' 字样。

Cooper 2026-06-10 手工验收发现 2 个视觉 bug：
1. 导出按钮显示 "download 导出 Markdown" —— Material Symbols 字体 ligature
   未替换为图标 glyph，字面 "download" 字母透出来
2. KPI 5 张卡片高度不一 —— sub 字段长短不一导致 div 自然高度差异

修复策略：
1. 删按钮 <span class="material-symbols-outlined">download</span>
2. theme CSS .kpi-card 加 flex 布局 + min-height 强制等高
"""
from __future__ import annotations

from src.frontend import render, theme


# ============ 问题 1: 导出按钮 ============

def test_export_buttons_no_download_icon_text():
    """导出按钮的 HTML 不应含 'material-symbols-outlined download' 字样。

    Material Symbols 字体未必加载（streamlit iframe sandbox 等环境因素），
    ligature 失效时字面 'download' 字母会透出来；删图标更稳妥。
    """
    # 抓 _render_export_buttons 渲染的 HTML 字符串
    captured = []

    def fake_markdown(content, **_kwargs):
        captured.append(content)

    import streamlit as st
    real_markdown = st.markdown
    st.markdown = fake_markdown
    try:
        render._render_export_buttons("test-trace-id-001")
    finally:
        st.markdown = real_markdown

    assert captured, "_render_export_buttons 未调用 st.markdown"
    html = captured[0]

    # 不应有 material-symbols-outlined（字体 ligature 不稳）
    assert "material-symbols-outlined" not in html, (
        "按钮 HTML 不应含 Material Symbols span（字体未加载时字面 'download' 透出）"
    )
    # 但仍应有按钮文字
    assert "导出 Markdown" in html
    assert "导出 HTML" in html
    # 应仍是 <a download> 触发浏览器原生下载
    assert "download" in html  # download 属性仍在（不是 span 文字）
    assert "<a " in html


# ============ 问题 2: KPI 卡等高 ============

def test_theme_css_kpi_card_has_flex_equal_height():
    """.kpi-card CSS 必须有 flex 布局 + min-height 保证 5 张卡等高。

    问题：默认 div 高度跟随内容，sub 字段长短不一（'高 18 中 6 低 0' vs ''）
    导致卡片高度不齐，视觉散乱。

    修复：
    - display: flex + flex-direction: column → 内部 label/main/sub 垂直堆叠
    - min-height: 固定下限 → 即使内容短也保持卡高
    - justify-content: space-between → label 顶 / sub 底，main 居中拉开
    """
    css = theme._THEME_CSS
    # 提取 .kpi-card { ... } 规则块
    import re
    match = re.search(r"\.kpi-card\s*\{([^}]+)\}", css)
    assert match, ".kpi-card CSS 规则块缺失"
    rule = match.group(1)

    # 等高三件套
    assert "display: flex" in rule or "display:flex" in rule, (
        ".kpi-card 必须 display: flex 才能保证内部元素均匀分布"
    )
    assert "flex-direction: column" in rule or "flex-direction:column" in rule, (
        ".kpi-card 必须 flex-direction: column"
    )
    assert "min-height" in rule, ".kpi-card 必须有 min-height 强制最小高度"


def test_theme_css_kpi_card_sub_has_fallback_height():
    """.kpi-card-sub 即使内容为空也应保留行高占位（保持 5 卡视觉对齐）。"""
    css = theme._THEME_CSS
    import re
    match = re.search(r"\.kpi-card-sub\s*\{([^}]+)\}", css)
    assert match, ".kpi-card-sub CSS 规则块缺失"
    rule = match.group(1)

    # min-height 保证空 sub 仍占位
    assert "min-height" in rule, (
        ".kpi-card-sub 必须有 min-height 防空内容时塌缩"
    )
