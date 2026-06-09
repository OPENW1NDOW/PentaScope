"""验证 HTML 导出器的 XSS 防护（C5 critical / 跨模型独占发现）。

narrative / executive_summary / 章节文本可能含 LLM 生成或网页爬来的 HTML，
必须经 nh3 sanitize + Jinja2 autoescape 双层防护。
"""
from __future__ import annotations

from src.api.exporters.html import _safe_markdown, render_html
from tests.unit.test_exporters_markdown import _minimal_base_report


def test_safe_markdown_strips_script():
    """直接测试 _safe_markdown 函数：<script> 应被 strip。"""
    text = "正常文本 <script>alert('XSS')</script> 后面"
    out = _safe_markdown(text)
    assert "<script>" not in out
    assert "alert" not in out
    assert "正常文本" in out
    assert "后面" in out


def test_safe_markdown_strips_inline_event_handler():
    """inline event handler (onclick) 应被 strip。"""
    text = '<a href="https://example.com" onclick="alert(1)">link</a>'
    out = _safe_markdown(text)
    assert "onclick" not in out
    assert "link" in out


def test_safe_markdown_strips_javascript_uri():
    """javascript: 协议 URL 应被 strip。"""
    text = '<a href="javascript:alert(1)">click</a>'
    out = _safe_markdown(text)
    assert "javascript:" not in out


def test_safe_markdown_strips_iframe():
    """<iframe> 应被 strip。"""
    text = '<iframe src="https://evil.com"></iframe>'
    out = _safe_markdown(text)
    assert "<iframe" not in out


def test_safe_markdown_preserves_safe_html():
    """安全的 HTML（strong/em/a 等）应保留。"""
    text = "**bold** *italic* and a [link](https://example.com)"
    out = _safe_markdown(text)
    assert "<strong>" in out
    assert "<em>" in out
    assert "<a " in out and "https://example.com" in out


def test_html_export_strips_script_in_narrative():
    """端到端：恶意 narrative 通过 render_html 后 HTML 不含 <script>。"""
    rep = _minimal_base_report("S1", {})
    rep["analysis_sections"][0]["narrative"] = (
        "正常分析。<script>alert('XSS')</script> 文末。"
    )
    out = render_html(rep, trace_id="t-xss")
    # 注意：autoescape 会把字面 < > 转义；nh3 strip 真实标签
    # 最终 HTML 不应含可执行的 <script> 标签
    assert "<script>alert" not in out
    assert "正常分析" in out


def test_html_export_strips_iframe_in_executive_summary():
    """executive_summary 含 iframe 攻击向量也应被 strip。"""
    rep = _minimal_base_report("S2", {})
    rep["executive_summary"]["context"] = (
        "市场背景。<iframe src='https://evil.com'></iframe>"
    )
    out = render_html(rep, trace_id="t-xss2")
    # safe_md 会 strip iframe；如果未走 safe_md 而走 autoescape，则被转义
    assert "<iframe" not in out
    assert "市场背景" in out


def test_html_export_jinja_autoescape_for_metadata():
    """非 markdown 字段（如 title）走 Jinja autoescape，含 <script> 标签应被转义。"""
    rep = _minimal_base_report("S1", {})
    rep["title"] = "<script>alert(1)</script>"  # 不会过 markdown
    out = render_html(rep, trace_id="t-title")
    # 标题里的 <script> 应被 autoescape 转义为 &lt;script&gt;
    # 不应作为可执行 HTML 标签出现
    assert "<script>alert(1)</script>" not in out
    # 应包含转义后形态
    assert "&lt;script&gt;" in out or "&lt;script" in out
