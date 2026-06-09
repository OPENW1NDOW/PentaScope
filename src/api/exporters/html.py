"""BaseReport → HTML 导出器（PD-4 全内嵌：字体 + Plotly + CSS）。

C5 修入：narrative 走 markdown→html→nh3 sanitize 三步保 XSS 安全。
PD-4 修入：字体 base64 内嵌 + Plotly include_plotlyjs=True 内嵌 plotly.min.js。
"""
from __future__ import annotations

import base64
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jinja2
import markdown as md_lib
import nh3

from src.api.exporters import check_fonts

logger = logging.getLogger(__name__)

_BEIJING = timezone(timedelta(hours=8))
_FONTS_DIR = Path(__file__).parent / "fonts"
_TEMPLATES_DIR = Path(__file__).parent / "templates"

_SCENARIO_LABELS = {
    "S1": "功能迭代", "S2": "市场进入", "S3": "定价策略",
    "S4": "持续监控", "S5": "战略定位",
}

_FONT_BASE64_CACHE: dict[str, str] = {}


def _font_base64(name: str) -> str:
    """读字体文件并返回 base64 字符串（缓存到模块级 dict 避免重复读盘）。"""
    if name not in _FONT_BASE64_CACHE:
        path = _FONTS_DIR / name
        _FONT_BASE64_CACHE[name] = base64.b64encode(path.read_bytes()).decode()
    return _FONT_BASE64_CACHE[name]


# nh3 sanitizer config（C5 修入）
_NH3_ALLOWED_TAGS = {
    "p", "br", "strong", "em", "ul", "ol", "li",
    "h1", "h2", "h3", "h4", "h5", "h6",
    "blockquote", "code", "pre", "a",
    "table", "thead", "tbody", "tr", "th", "td",
    "hr", "div", "span",
}
_NH3_ALLOWED_ATTRS = {"a": {"href", "title"}}


def _safe_markdown(text: str) -> str:
    """C5 修入：narrative 等 LLM 文本走 markdown→html→nh3 sanitize 三步。

    nh3 strips:
    - <script> tags
    - inline event handlers (onclick=...)
    - javascript: URIs
    - 任何不在 _NH3_ALLOWED_TAGS 内的标签
    """
    if not text or not isinstance(text, str):
        return ""
    raw_html = md_lib.markdown(text, extensions=["extra", "nl2br"])
    return nh3.clean(
        raw_html,
        tags=_NH3_ALLOWED_TAGS,
        attributes=_NH3_ALLOWED_ATTRS,
    )


# Jinja2 environment（autoescape 强开 = C5 双层防护）
_jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(_TEMPLATES_DIR)),
    autoescape=jinja2.select_autoescape(["html", "j2"]),
)
_jinja_env.filters["safe_md"] = _safe_markdown


def _confidence_color(level: str) -> str:
    return {
        "high": "#16A34A",
        "medium": "#D97706",
        "low": "#DC2626",
    }.get(level or "", "#475569")


def _competitors_sub(report: dict) -> str:
    """KPI 竞品数量副信息。S2 时显示「含 N 推荐」。"""
    payload = report.get("scenario_payload") or {}
    if payload.get("scenario_type") == "S2":
        rec = payload.get("competitor_recommendations") or {}
        rec_list = rec.get("recommended_competitors") or []
        if rec_list:
            return f"含 {len(rec_list)} 推荐"
    return ""


def _sources_sub(meta: dict) -> str:
    sources = meta.get("data_sources") or []
    if not sources:
        return ""
    high = sum(1 for s in sources if (s.get("confidence") or "") == "high")
    mid = sum(1 for s in sources if (s.get("confidence") or "") == "medium")
    low = sum(1 for s in sources if (s.get("confidence") or "") == "low")
    return f"高 {high} 中 {mid} 低 {low}"


def _build_scenario_charts(report: dict) -> tuple[str, list[str]]:
    """生成 5 场景的 Plotly 图表 HTML 字符串列表。

    返回 (scenario_type, charts_list)。第一张 include_plotlyjs=True
    内嵌 plotly.min.js；后续图 include_plotlyjs=False 共享。
    """
    payload = report.get("scenario_payload") or {}
    scenario_type = (
        payload.get("scenario_type")
        or (report.get("metadata") or {}).get("scenario")
        or ""
    )

    charts: list[str] = []
    figs = []

    if scenario_type == "S1":
        from src.frontend.render import _radar_chart_s1
        fig = _radar_chart_s1(payload.get("radar_scores") or [])
        if fig is not None:
            figs.append(fig)
    elif scenario_type == "S2":
        from src.frontend.render import _radar_chart_five_forces
        fig = _radar_chart_five_forces(payload.get("five_forces") or {})
        if fig is not None:
            figs.append(fig)
    elif scenario_type == "S5":
        from src.frontend.render import (
            _line_strategy_canvas,
            _scatter_magic_quadrant,
            _scatter_perceptual_map,
        )
        for builder, arg in [
            (_scatter_perceptual_map, payload.get("perceptual_map") or {}),
            (_scatter_magic_quadrant, payload.get("vendor_profiles") or []),
            (_line_strategy_canvas, payload.get("strategy_canvas") or {}),
        ]:
            fig = builder(arg)
            if fig is not None:
                figs.append(fig)

    for i, fig in enumerate(figs):
        try:
            charts.append(fig.to_html(
                include_plotlyjs=(i == 0),  # 第一张内嵌完整 plotly.min.js
                full_html=False,
            ))
        except Exception as e:  # noqa: BLE001
            logger.warning("[html_export] Plotly to_html failed: %s", e)

    return scenario_type, charts


def render_html(report: dict, *, trace_id: str) -> str:
    """渲染 BaseReport dict 为完整 HTML 字符串。

    所有资源（字体 / Plotly / CSS）全部内嵌，单 HTML 文件离线 100% 可用。
    """
    check_fonts()  # 启动校验，缺字体 raise FileNotFoundError

    template = _jinja_env.get_template("report.html.j2")

    scenario_type, scenario_charts = _build_scenario_charts(report)
    meta = report.get("metadata") or {}

    return template.render(
        report=report,
        trace_id=trace_id,
        generated_at=datetime.now(_BEIJING).strftime("%Y-%m-%d %H:%M"),
        font_jakarta_regular=_font_base64("PlusJakartaSans-Regular.woff2"),
        font_fira=_font_base64("FiraCode-Regular.woff2"),
        scenario_label=_SCENARIO_LABELS.get(meta.get("scenario") or "", ""),
        competitors_sub=_competitors_sub(report),
        sources_sub=_sources_sub(meta),
        confidence_color=_confidence_color(meta.get("confidence_level") or ""),
        scenario_type=scenario_type,
        scenario_charts=scenario_charts,
    )
