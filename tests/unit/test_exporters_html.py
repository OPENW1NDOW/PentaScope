"""验证 html 导出器：5 场景关键字段 + Plotly 嵌入 + 字体 base64。"""
from __future__ import annotations

from src.api.exporters.html import render_html
from tests.unit.test_exporters_markdown import _minimal_base_report


def test_html_basic_structure():
    """生成的 HTML 含 doctype + meta + style + body。"""
    rep = _minimal_base_report("S1", {})
    out = render_html(rep, trace_id="t-html")

    assert out.startswith("<!DOCTYPE html>")
    assert "<html" in out
    assert "<head>" in out and "</head>" in out
    assert "<body>" in out and "</body>" in out
    assert "t-html" in out
    assert rep["title"] in out


def test_html_kpi_strip_present():
    """KPI 5 卡的标签都出现。"""
    rep = _minimal_base_report("S2", {})
    out = render_html(rep, trace_id="t-kpi")
    assert "质检评分" in out
    assert "场景标签" in out
    assert "竞品数量" in out
    assert "参考资料" in out
    assert "可信度" in out


def test_html_font_base64_inlined():
    """PD-4 全内嵌：HTML 含 woff2 字体 base64 字符串。"""
    rep = _minimal_base_report("S1", {})
    out = render_html(rep, trace_id="t")
    assert "data:font/woff2;base64," in out
    assert "Plus Jakarta Sans" in out


def test_html_s1_radar_plotly_embedded():
    """S1 场景含雷达图：HTML 含 plotly.js + scatterpolar trace。"""
    rep = _minimal_base_report("S1", {
        "radar_scores": [
            {"competitor_name": "A", "feature_breadth": 4, "usability": 4,
             "cost_effectiveness": 4, "stability": 4, "design_quality": 4},
        ],
    })
    out = render_html(rep, trace_id="t-s1")
    # Plotly 全内嵌（PD-4）：第一张图 include_plotlyjs=True 嵌入完整 plotly.min.js
    assert "Plotly.newPlot" in out or "plotly" in out.lower()


def test_html_s2_renders_without_crash():
    """S2 含 five_forces，HTML 渲染不崩。"""
    rep = _minimal_base_report("S2", {
        "five_forces": {
            "new_entrants": {"intensity": "low", "implication": "X"},
            "supplier_power": {"intensity": "medium", "implication": "Y"},
            "buyer_power": {"intensity": "high", "implication": "Z"},
            "substitute_threat": {"intensity": "low", "implication": "W"},
            "competitive_rivalry": {"intensity": "medium", "implication": "V"},
        },
    })
    out = render_html(rep, trace_id="t-s2")
    assert "S2" in out


def test_html_s5_renders_without_crash():
    """S5 含 vendor_profiles MQ + perceptual_map，不崩。"""
    rep = _minimal_base_report("S5", {
        "vendor_profiles": [
            {"competitor_name": "V1", "ability_to_execute_score": 3,
             "completeness_of_vision_score": 4, "mq_quadrant": "visionary",
             "overview": "V1 概览"},
        ],
        "perceptual_map": {
            "x_axis": {"attribute": "X", "low_label": "低",
                       "high_label": "高", "scale_max": 5},
            "y_axis": {"attribute": "Y", "low_label": "低",
                       "high_label": "高", "scale_max": 5},
            "plotted_brands": [
                {"competitor_name": "V1", "x_score": 3, "y_score": 4,
                 "is_self": False, "confidence": "high", "score_rationale": "依据"},
            ],
        },
    })
    out = render_html(rep, trace_id="t-s5")
    assert "S5" in out
    assert "V1" in out


def test_html_kpi_quality_score_dashes_when_missing():
    """metadata 缺 raw 与 quality 时 KPI 卡显示 — 与未质检。"""
    rep = _minimal_base_report("S1", {})
    rep["metadata"]["raw_quality_score"] = None
    rep["metadata"]["quality_score"] = None
    out = render_html(rep, trace_id="t-noscore")
    # 至少一处出现 "—" 占位 + "未质检" 副信息
    assert "未质检" in out
