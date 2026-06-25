"""验证 markdown 导出器：5 场景关键字段断言 + 不崩。"""
from __future__ import annotations

from src.api.exporters.markdown import render_markdown


def _minimal_base_report(scenario: str, payload: dict) -> dict:
    """构造满足 markdown 渲染需要的最小 BaseReport dict。"""
    return {
        "title": f"{scenario} 测试报告",
        "subtitle": "单元测试用",
        "at_a_glance": ["要点 1", "要点 2"],
        "executive_summary": {
            "context": "背景上下文",
            "core_thesis": "核心论断",
            "key_findings_brief": ["finding A"],
            "implications": "现实启示",
            "path_forward": ["路径 1"],
        },
        "scope": {"competitors": ["A", "B"], "time_window": "2026"},
        "methodology": {"data_collection_approach": "搜 X 渠道"},
        "key_findings": [
            {"statement": "F1", "evidence": "E1", "implication": "I1", "source_refs": []},
        ],
        "analysis_sections": [
            {"heading": "分析章节 A", "section_type": "vendor_profiles",
             "narrative": "正文。", "source_refs": []},
        ],
        "swot": {
            "strengths": [{"point": "S1", "evidence": "E1", "source_refs": []}],
            "weaknesses": [],
            "opportunities": [],
            "threats": [],
        },
        "recommendations": [
            {"priority": "critical", "timeline": "immediate", "action": "做 X",
             "target_role": "产品", "rationale": "理由", "source_refs": []},
        ],
        "appendix": {"glossary": {}, "data_sources_full": []},
        "metadata": {
            "scenario": scenario,
            "raw_quality_score": 0.85,
            "quality_score": 0.85,
            "confidence_level": "high",
            "data_sources": [{"url": "https://example.com", "confidence": "high"}],
        },
        "scenario_payload": {**payload, "scenario_type": scenario},
    }


def test_markdown_s1_basic():
    rep = _minimal_base_report("S1", {
        "vendor_profiles": [
            {"competitor_name": "竞品A", "wave_position": "wave_leader",
             "one_line_pitch": "A 的卖点", "best_fit_for": "中型企业",
             "strengths": ["强 1", "强 2"], "cautions": ["注意 1"]},
        ],
        "radar_scores": [
            {"competitor_name": "竞品A", "feature_breadth": 4, "usability": 5,
             "cost_effectiveness": 3, "stability": 4, "design_quality": 4},
        ],
    })
    out = render_markdown(rep, trace_id="test-trace-001")
    assert "# S1 测试报告" in out
    assert "test-trace-001" in out
    assert "要点 1" in out
    assert "核心论断" in out
    assert "S1" in out
    assert "做 X" in out
    assert "竞品A" in out
    assert "wave_leader" in out
    assert "feature_breadth" in out or "功能广度" in out


def test_markdown_s2_basic():
    rep = _minimal_base_report("S2", {
        "market_sizing": {
            "tam": {"amount": 100, "unit": "亿", "currency": "USD",
                    "value_basis": "industry_report"},
            "sam": {"amount": 30, "unit": "亿", "currency": "USD",
                    "value_basis": "estimated"},
            "som": {"amount": 5, "unit": "亿", "currency": "USD",
                    "value_basis": "inferred"},
        },
        "players": [
            {"name": "P1", "company": "公司 1", "market_role": "market_leader",
             "market_share_pct": 40, "key_differentiator": "差异化"},
        ],
    })
    out = render_markdown(rep, trace_id="t2")
    assert "TAM" in out and "SAM" in out and "SOM" in out
    assert "P1" in out
    assert "market_leader" in out


def test_markdown_s3_basic():
    rep = _minimal_base_report("S3", {
        "packaging": {
            "tiers": [
                {"name": "Basic", "position": "good", "monthly_price": 10,
                 "annual_price": 100, "currency": "USD", "is_recommended": False,
                 "target_persona": "个人", "included_features": ["F1"]},
                {"name": "Pro", "position": "better", "monthly_price": 30,
                 "annual_price": 300, "currency": "USD", "is_recommended": True,
                 "target_persona": "团队", "included_features": ["F1", "F2"]},
            ],
        },
    })
    out = render_markdown(rep, trace_id="t3")
    assert "Basic" in out and "Pro" in out
    assert "10" in out and "30" in out


def test_markdown_s4_basic():
    rep = _minimal_base_report("S4", {
        "review_period": {"review_period_label": "2026-Q1", "monitored_competitors": ["C1"]},
        "feature_changes": [
            {"competitor_name": "C1", "change_type": "new_feature",
             "fia": {"fact": "C1 上了新功能 X", "impact": "影响 Y", "act": "我们应该 Z"},
             "severity": "high"},
        ],
    })
    out = render_markdown(rep, trace_id="t4")
    assert "C1" in out
    assert "new_feature" in out or "功能变更" in out


def test_markdown_s5_basic():
    rep = _minimal_base_report("S5", {
        "vendor_profiles": [
            {"competitor_name": "V1", "ability_to_execute_score": 4,
             "completeness_of_vision_score": 3, "mq_quadrant": "challenger",
             "overview": "V1 概览"},
        ],
        "perceptual_map": {
            "x_axis": {"attribute": "价格", "low_label": "低端",
                       "high_label": "高端", "scale_max": 5},
            "y_axis": {"attribute": "功能", "low_label": "简单",
                       "high_label": "强大", "scale_max": 5},
            "plotted_brands": [
                {"competitor_name": "V1", "x_score": 4, "y_score": 3,
                 "is_self": False, "confidence": "high", "score_rationale": "依据 X"},
            ],
        },
    })
    out = render_markdown(rep, trace_id="t5")
    assert "V1" in out
    assert "challenger" in out
    assert "感知地图" in out or "Perceptual" in out or "perceptual_map" in out


def test_markdown_unknown_scenario_does_not_crash():
    rep = _minimal_base_report("S99", {})
    out = render_markdown(rep, trace_id="t99")
    assert "# S99 测试报告" in out
    assert "t99" in out


def test_markdown_handles_missing_optional_fields():
    minimal = {"title": "极简", "metadata": {"scenario": "S1"}}
    out = render_markdown(minimal, trace_id="t-min")
    assert "# 极简" in out
    assert "t-min" in out


# ============ Code review fixes ============


def test_markdown_kfb_items_only_render_when_present():
    """Critical fix: key_findings_brief items must NOT render when list is empty.
    Also: when kfb is empty, h3 counter should not increment for it."""
    rep = _minimal_base_report("S1", {})
    rep["executive_summary"]["key_findings_brief"] = []
    rep["executive_summary"]["path_forward"] = ["路径 X"]
    out = render_markdown(rep, trace_id="t-kfb-empty")
    assert "关键发现速览" not in out
    assert "路径 X" in out
    # path_forward should be （四）not （五）when kfb is skipped
    # (context=一, core_thesis=二, implications=三, path_forward=四)
    assert "（四）" in out


def test_markdown_concurrent_safety():
    """Critical fix: concurrent calls should not corrupt heading numbers"""
    import concurrent.futures
    rep = _minimal_base_report("S1", {})
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(render_markdown, rep, trace_id=f"t-{i}") for i in range(4)]
        for f in concurrent.futures.as_completed(futures):
            results.append(f.result())
    for out in results:
        assert "一、核心要点" in out


def test_t_imported_from_utils_not_frontend():
    """Important fix: _t should be importable from utils without streamlit"""
    from src.utils.translations import _t, _TRANSLATIONS
    assert _t("high") == "高 (high)"
    assert len(_TRANSLATIONS) > 50


# ---------- [#8] 表格单元格 / 链接转义 ----------

def test_markdown_table_cell_escapes_pipe_and_newline():
    """[#8] 表格单元格含 | 或换行时必须转义，否则破坏表格列/行结构。"""
    rep = _minimal_base_report("S1", {
        "vendor_profiles": [
            {"competitor_name": "甲|乙", "wave_position": "wave_leader",
             "one_line_pitch": "卖点\n第二行", "best_fit_for": "中型",
             "strengths": [], "cautions": []},
        ],
        "radar_scores": [],
    })
    out = render_markdown(rep, trace_id="t-esc")
    # | 应被转义为 \|，不能裸出现在单元格值里破坏列
    assert "甲\\|乙" in out, f"表格单元格的 | 应转义为 \\|，实际：{out}"
    # 换行应被规整为空格，不能断行破坏表格行
    assert "卖点\n第二行" not in out, "表格单元格的换行应被规整，不能断行"


def test_markdown_link_escapes_title_and_url():
    """[#8] 链接 title 含 ] 或 url 含 ) 时必须转义，否则截断/扭曲链接。"""
    rep = _minimal_base_report("S1", {})
    # data_sources_full 链接 + source_refs 链接
    rep["appendix"]["data_sources_full"] = [
        {"url": "https://example.com/a)b", "title": "标题]危险", "confidence": "high"},
    ]
    rep["key_findings"][0]["source_refs"] = [
        {"url": "https://example.com/c)d", "title": "来源]名"},
    ]
    out = render_markdown(rep, trace_id="t-link")
    # title 中的 ] 应被转义，不能裸出现破坏链接语法
    assert "标题]危险" not in out or "标题\\]危险" in out, (
        f"链接 title 中的 ] 应转义，实际：{out}"
    )
    # url 中的 ) 应被处理（尖括号包裹或转义），不能直接断链接
    # 用 <url> 形式时 url 原样保留在尖括号内是安全的
    assert "https://example.com/a)b" in out, "url 内容不应丢失"
