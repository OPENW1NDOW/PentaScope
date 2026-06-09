"""验证 inject_theme 不被 markdown 引擎截断 <style> block。

Bug 现象（Cooper 2026-06-10 手工验收截图）：
  _THEME_CSS 字符串内容（CSS 注释 + 选择器 + 规则块）作为纯文本显示在前端页面，
  CSS 完全不生效（标题颜色仍是黑色 / 背景仍是默认 Streamlit 灰）。

systematic-debugging Phase 1-3 锁定根因：
  st.markdown(unsafe_allow_html=True) 把字符串经 CommonMark/GFM markdown 引擎处理，
  type 6 HTML block (<style>) 遇连续空行（\n\n）被判定为 block 结束，剩余 CSS
  文本回到 markdown 解析模式被当文本输出。

Prove-It pattern 修复：
  改用 st.html() ——Streamlit 1.33+ 官方推荐的 HTML 注入路径，不经 markdown 引擎。

本测试 lock-in 修复后的不变量：
  1. inject_theme() 必须调 st.html，不能调 st.markdown
  2. _THEME_CSS 必须是良构 HTML（含完整 <style>...</style> 闭合 + 至少 1 对 <link>）
"""
from __future__ import annotations

from unittest.mock import patch

from src.frontend import theme


def test_theme_css_has_well_formed_style_block():
    """_THEME_CSS 必须含完整的 <style> ... </style> 闭合。"""
    css = theme._THEME_CSS
    assert css.count("<style>") == 1, "应有且仅有一个 <style> 开标签"
    assert css.count("</style>") == 1, "应有且仅有一个 </style> 关标签"
    style_open = css.index("<style>")
    style_close = css.index("</style>")
    assert style_open < style_close, "<style> 必须在 </style> 之前"


def test_theme_css_includes_required_color_tokens():
    """主题色令牌（PD-3 KPI 卡视觉依赖）必须在 CSS 中定义。"""
    css = theme._THEME_CSS
    for var_name in [
        "--color-primary",
        "--color-bg",
        "--color-accent",
        "--color-surface",
        "--color-danger",
    ]:
        assert var_name in css, f"CSS 必须定义 {var_name}（Data-Dense Dashboard 设计令牌）"


def test_theme_css_includes_kpi_card_class():
    """KPI 卡片样式（render.py::_render_kpi_strip 依赖）必须在 CSS 中存在。"""
    css = theme._THEME_CSS
    assert ".kpi-card" in css, "render.py KPI 卡片渲染依赖 .kpi-card 选择器"
    assert ".section-card" in css, "render.py section 卡片渲染依赖 .section-card 选择器"
    assert ".btn-export" in css, "render.py 导出按钮依赖 .btn-export 选择器"


def test_inject_theme_uses_st_html_not_markdown():
    """根因修复：inject_theme 必须用 st.html 注入，不能用 st.markdown。

    st.markdown(unsafe_allow_html=True) 会经 CommonMark 引擎，
    遇连续空行截断 <style> block，导致 CSS 文本被渲染为可见内容（Cooper 报告 bug）。

    st.html 直接走 sanitized HTML 注入路径，是 Streamlit 1.33+ 注入 <style> 的官方方式。
    """
    with patch.object(theme.st, "html") as mock_html, \
         patch.object(theme.st, "markdown") as mock_markdown:
        theme.inject_theme()

        # 必须调用 st.html，不能调用 st.markdown
        mock_html.assert_called_once()
        mock_markdown.assert_not_called()

        # 传给 st.html 的内容必须是 _THEME_CSS（不被截断）
        called_arg = mock_html.call_args[0][0]
        assert "<style>" in called_arg
        assert "</style>" in called_arg
        assert ".kpi-card" in called_arg
        assert ".btn-export" in called_arg
