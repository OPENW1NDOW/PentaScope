"""前端渲染单测：容错性 + 调用次数核对。

streamlit 函数本身不能在测试中真实调用，用 monkeypatch 替换为 spy（记录调用），
重点验证：① 渲染函数遇到缺字段/空值/None 不崩；② 关键内容被传给 streamlit。
"""
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def st_spy(monkeypatch):
    """把 streamlit 替换成 MagicMock，记录所有调用"""
    from src.frontend.render import _hc
    _hc.reset()
    spy = MagicMock()
    # 共用一个上下文 mock，便于断言 cm.metric / cm.markdown 调用
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=cm)
    cm.__exit__ = MagicMock(return_value=False)
    # st.columns(n) 按传入数字返回 [cm] * n，兼容任意列数（3 / 4 / len(tiers)）
    spy.columns.side_effect = lambda n=2: [cm] * (n if isinstance(n, int) else len(n))
    spy.expander.return_value = cm
    spy._cm = cm  # 测试可访问 spy._cm 取共享 cm
    monkeypatch.setattr("src.frontend.render.st", spy)
    return spy


# ============ 入口函数容错 ============

def test_render_empty_report_does_not_crash(st_spy):
    from src.frontend.render import render_base_report
    render_base_report({})
    st_spy.warning.assert_called_with("报告为空")


def test_render_minimal_report_does_not_crash(st_spy):
    from src.frontend.render import render_base_report
    render_base_report({
        "title": "测试报告",
        "executive_summary": {},
        "scope": {},
        "methodology": {},
        "key_findings": [],
        "analysis_sections": [],
        "swot": {},
        "recommendations": [],
        "appendix": {},
        "metadata": {},
        "scenario_payload": None,
    })
    st_spy.title.assert_called_once_with("测试报告")


def test_render_none_report_does_not_crash(st_spy):
    from src.frontend.render import render_base_report
    render_base_report(None)
    st_spy.warning.assert_called()


# ============ executive_summary 5 段 ============

def test_render_executive_summary_5_sections(st_spy):
    from src.frontend.render import _render_executive_summary
    _render_executive_summary({
        "context": "上下文" * 20,
        "core_thesis": "核心论断",
        "key_findings_brief": ["发现一", "发现二"],
        "implications": "启示" * 30,
        "path_forward": ["行动一"],
    })
    # 至少调用了 header 包含"执行摘要"
    header_calls = [str(c) for c in st_spy.header.call_args_list]
    assert any("执行摘要" in c for c in header_calls)
    # subheader 对 5 个段都触发（其中 3 个 直接段 + 2 个 list 段共 5 次以内）
    assert st_spy.subheader.call_count >= 4


def test_render_executive_summary_skips_empty_fields(st_spy):
    from src.frontend.render import _render_executive_summary
    _render_executive_summary({"context": "x" * 100})
    header_calls = [str(c) for c in st_spy.header.call_args_list]
    assert any("执行摘要" in c for c in header_calls)
    # 只 context 有值时不应渲染 implications 等
    subheader_calls = [str(c) for c in st_spy.subheader.call_args_list]
    assert not any("现实启示 Implications" in c for c in subheader_calls)


# ============ key_findings ============

def test_render_key_findings_with_source_refs(st_spy):
    from src.frontend.render import _render_key_findings
    _render_key_findings([
        {
            "statement": "竞品 A 增长率 30%",
            "evidence": "Q3 财报显示",
            "implication": "需关注其新功能",
            "source_refs": [{"url": "https://x.com", "title": "财报"}],
        },
    ])
    header_calls = [str(c) for c in st_spy.header.call_args_list]
    assert any("关键发现" in c for c in header_calls)
    st_spy.markdown.assert_any_call("**发现 1**：竞品 A 增长率 30%")


def test_render_key_findings_empty_skipped(st_spy):
    from src.frontend.render import _render_key_findings
    _render_key_findings([])
    st_spy.header.assert_not_called()


# ============ swot ============

def test_render_swot_renders_all_4_quadrants(st_spy):
    from src.frontend.render import _render_swot
    _render_swot({
        "strengths": [{"point": "技术领先"}],
        "weaknesses": [{"point": "成本高"}],
        "opportunities": [{"point": "市场扩张"}],
        "threats": [{"point": "新对手"}],
    })
    subheader_calls = [str(c) for c in st_spy.subheader.call_args_list]
    assert any("优势 S" in c for c in subheader_calls)
    assert any("劣势 W" in c for c in subheader_calls)
    assert any("机会 O" in c for c in subheader_calls)
    assert any("威胁 T" in c for c in subheader_calls)


def test_render_swot_empty_skipped(st_spy):
    from src.frontend.render import _render_swot
    _render_swot({})
    st_spy.header.assert_not_called()


def test_render_swot_partial_renders(st_spy):
    """仅 strengths 有内容也渲染"""
    from src.frontend.render import _render_swot
    _render_swot({"strengths": [{"point": "x"}]})
    header_calls = [str(c) for c in st_spy.header.call_args_list]
    assert any("SWOT 分析" in c for c in header_calls)


# ============ recommendations ============

def test_render_recommendations_groups_by_timeline(st_spy):
    from src.frontend.render import _render_recommendations
    _render_recommendations([
        {"action": "改 A", "priority": "critical", "timeline": "immediate", "target_role": "PM",
         "rationale": "市场窗口"},
        {"action": "改 B", "priority": "important", "timeline": "short_term", "target_role": "Dev",
         "rationale": "技术债"},
    ])
    subheader_calls = [str(c) for c in st_spy.subheader.call_args_list]
    assert any("即时（1 个月内）" in c for c in subheader_calls)
    assert any("短期（3 个月内）" in c for c in subheader_calls)


def test_render_recommendations_with_priority_emoji(st_spy):
    from src.frontend.render import _render_recommendations
    _render_recommendations([
        {"action": "x", "priority": "critical", "timeline": "immediate", "target_role": "", "rationale": ""},
    ])
    md_calls = [c.args[0] for c in st_spy.markdown.call_args_list]
    assert any("紧急 (critical)" in m for m in md_calls)


# ============ scope + methodology ============

def test_render_scope_displays_competitors(st_spy):
    from src.frontend.render import _render_scope_and_methodology
    _render_scope_and_methodology(
        {"competitors": ["A", "B"], "time_window": "2026 Q1", "regions": ["CN"]},
        {},
    )
    md_calls = [c.args[0] for c in st_spy.markdown.call_args_list]
    assert any("A, B" in m for m in md_calls)


# ============ source_refs 容错 ============

def test_render_source_refs_handles_missing_fields(st_spy):
    from src.frontend.render import _render_source_refs
    # 既有 url 又无 title / 既无 url 又无 title / 干净 ref 三种形态
    _render_source_refs([
        {"url": "https://a.com"},
        {},
        {"url": "https://b.com", "title": "B 站"},
    ])
    # 不崩即过


def test_render_source_refs_none_skipped(st_spy):
    from src.frontend.render import _render_source_refs
    _render_source_refs(None)
    st_spy.caption.assert_not_called()


# ============ metadata ============

def test_render_metadata_quality_score_displays(st_spy):
    from src.frontend.render import _render_metadata_panel
    _render_metadata_panel({
        "scenario": "S1",
        "confidence_level": "high",
        "quality_score": 0.85,
        "quality_score_calculation_note": "coverage=0.9 ...",
        "warnings": ["placeholder_section:x"],
    })
    # metric 由 cols[i] 上下文调用：所有列共享 fixture 的 cm mock
    cm = st_spy._cm
    assert cm.metric.call_count >= 3


def test_render_metadata_quality_score_none_shows_unscored(st_spy):
    from src.frontend.render import _render_metadata_panel
    _render_metadata_panel({"scenario": "S2", "confidence_level": "low"})
    cm = st_spy._cm
    metric_calls = [c.args for c in cm.metric.call_args_list]
    # 第三个 metric 应为"未质检"
    assert any(args[1] == "未质检" for args in metric_calls)


# ============ F2 scenario_payload 分发器 ============

def test_dispatch_unknown_scenario_falls_back_to_json(st_spy):
    from src.frontend.render import render_scenario_payload
    render_scenario_payload({"scenario_type": "S99"})
    st_spy.json.assert_called()
    cap_args = [c.args[0] for c in st_spy.caption.call_args_list]
    assert any("未知场景" in c for c in cap_args)


def test_dispatch_empty_payload_skipped(st_spy):
    from src.frontend.render import render_scenario_payload
    render_scenario_payload(None)
    st_spy.header.assert_not_called()


@pytest.mark.parametrize("scenario_type", ["S1", "S2", "S3", "S4", "S5"])
def test_dispatch_routes_to_each_scenario(st_spy, scenario_type, monkeypatch):
    """分发器按 scenario_type 路由到对应 _render_sX_payload"""
    from src.frontend import render
    called = []
    monkeypatch.setattr(
        f"src.frontend.render._render_{scenario_type.lower()}_payload",
        lambda p: called.append(scenario_type),
    )
    render.render_scenario_payload({"scenario_type": scenario_type})
    assert called == [scenario_type]


# ============ S1 ============

def test_render_s1_minimal_payload_does_not_crash(st_spy):
    from src.frontend.render import _render_s1_payload
    _render_s1_payload({"scenario_type": "S1"})


def test_render_s1_with_vendor_profiles(st_spy):
    from src.frontend.render import _render_s1_payload
    _render_s1_payload({
        "scenario_type": "S1",
        "vendor_profiles": [
            {"competitor_name": "A", "wave_position": "wave_leader",
             "one_line_pitch": "技术领先", "best_fit_for": "大型企业",
             "strengths": [{"point": "x"}], "cautions": [{"point": "y"}]},
        ],
        "feature_matrix": {
            "our_product_name": "Us", "competitors": ["A"],
            "categories": [{"name": "核心", "weight": 3, "features": [
                {"name": "f1", "scores": {"A": {"score": 2}}},
            ]}],
            "weighted_scores": {"A": 95.0},
        },
        "feature_gaps": [{"feature_name": "g1", "competitors_have_it": ["A"],
                          "underserved_outcome": "x", "estimated_effort": "high",
                          "estimated_impact": "high", "recommendation": "build"}],
        "roadmap_recommendations": {"must_build": ["x"], "rationale_summary": "xx"},
    })
    headers = [str(c) for c in st_spy.subheader.call_args_list]
    assert any("竞品画像（Forrester Wave 风格）" in h for h in headers)
    assert any("功能矩阵" in h for h in headers)


# ============ S2 ============

def test_render_s2_minimal_payload_does_not_crash(st_spy):
    from src.frontend.render import _render_s2_payload
    _render_s2_payload({"scenario_type": "S2"})


def test_render_s2_with_market_sizing_and_players(st_spy):
    from src.frontend.render import _render_s2_payload
    _render_s2_payload({
        "scenario_type": "S2",
        "market_sizing": {
            "tam": {"amount": 10, "unit": "billion", "currency": "USD", "value_basis": "measured"},
            "sam": {"amount": 3, "unit": "billion", "currency": "USD", "value_basis": "estimated"},
            "som": {"amount": 0.5, "unit": "billion", "currency": "USD", "value_basis": "inferred"},
            "cagr_pct": 12.5,
        },
        "five_forces": {"new_entrants": {"intensity": "high", "implication": "x"}},
        "players": [{"name": "A", "market_role": "incumbent", "one_line_summary": "x"}],
        "market_concentration": "moderate",
        "key_trends": [{"trend_name": "AI 化", "direction": "up", "time_horizon": "mid_term",
                        "impact_on_entry": "positive"}],
        "entry_strategy": {"recommended_mode": "niche_focus", "target_segments": ["A"],
                           "initial_positioning": "x" * 30, "key_success_factors": ["a", "b"],
                           "main_risks": [{"description": "x", "likelihood": "low", "impact": "low",
                                           "mitigation": "y"}]},
    })
    headers = [str(c) for c in st_spy.subheader.call_args_list]
    assert any("市场规模 TAM/SAM/SOM" in h for h in headers)
    assert any("市场玩家" in h for h in headers)


# ============ S3 ============

def test_render_s3_minimal_payload_does_not_crash(st_spy):
    from src.frontend.render import _render_s3_payload
    _render_s3_payload({"scenario_type": "S3"})


def test_render_s3_with_packaging(st_spy):
    from src.frontend.render import _render_s3_payload
    _render_s3_payload({
        "scenario_type": "S3",
        "pricing_baseline": {"current_pricing_model": "per_seat", "current_tier_count": 3,
                             "pain_points": ["p1"]},
        "value_drivers": [{"driver_name": "速度", "importance": "high", "evidence": "x"}],
        "packaging": {
            "tiers": [
                {"name": "Basic", "position": "good", "monthly_price": 9, "currency": "USD",
                 "billing_unit": "per_seat", "is_recommended": False, "target_persona": "x",
                 "included_features": ["f1"]},
                {"name": "Pro", "position": "better", "monthly_price": 29, "currency": "USD",
                 "billing_unit": "per_seat", "is_recommended": True, "target_persona": "x",
                 "included_features": ["f1", "f2"]},
            ],
            "default_billing_cycle": "annual", "rationale": "x" * 60,
        },
    })
    headers = [str(c) for c in st_spy.subheader.call_args_list]
    assert any("推荐套餐设计 GBB" in h for h in headers)


# ============ S4 ============

def test_render_s4_minimal_payload_does_not_crash(st_spy):
    from src.frontend.render import _render_s4_payload
    _render_s4_payload({"scenario_type": "S4"})


def test_render_s4_with_changes_and_battlecards(st_spy):
    from src.frontend.render import _render_s4_payload
    _render_s4_payload({
        "scenario_type": "S4",
        "review_period": {"review_period_label": "2026-Q1",
                          "monitored_competitors": ["A"], "current_review_date": "2026-03-31"},
        "feature_changes": [{"competitor_name": "A", "change_type": "new_feature",
                             "feature_name": "x", "fia": {"fact": "x" * 20},
                             "severity": "medium", "is_baseline": False}],
        "threats": [{"title": "竞品大降价", "severity": "high", "likelihood": "high",
                     "quadrant": "act_now", "recommended_response": "x" * 25}],
        "trends": {"sentiment_trend": "up", "rationale": "x"},
        "battlecards": [{"competitor_name": "A", "overall_completeness": "partial",
                         "sections": [{"section_name": "quick_summary", "completeness": "full",
                                       "content": "x"}]}],
    })
    headers = [str(c) for c in st_spy.subheader.call_args_list]
    assert any("监控周期" in h for h in headers)
    assert any("活体战卡" in h for h in headers)


# ============ S5 ============

def test_render_s5_minimal_payload_does_not_crash(st_spy):
    from src.frontend.render import _render_s5_payload
    _render_s5_payload({"scenario_type": "S5"})


# ============ F3 Plotly 图表 ============

def test_radar_chart_s1_returns_figure_with_n_traces():
    from src.frontend.render import _radar_chart_s1
    fig = _radar_chart_s1([
        {"competitor_name": "A", "feature_breadth": 4, "usability": 3,
         "cost_effectiveness": 2, "stability": 5, "design_quality": 4},
        {"competitor_name": "B", "feature_breadth": 3, "usability": 4,
         "cost_effectiveness": 4, "stability": 3, "design_quality": 3},
    ])
    assert fig is not None
    assert len(fig.data) == 2  # 两个竞品 = 两条 trace


def test_radar_chart_s1_empty_returns_none():
    from src.frontend.render import _radar_chart_s1
    assert _radar_chart_s1([]) is None


def test_radar_chart_five_forces_intensity_to_num():
    from src.frontend.render import _radar_chart_five_forces
    fig = _radar_chart_five_forces({
        "new_entrants": {"intensity": "high"},
        "supplier_power": {"intensity": "low"},
        "buyer_power": {"intensity": "medium"},
        "substitute_threat": {"intensity": "high"},
        "competitive_rivalry": {"intensity": "medium"},
    })
    assert fig is not None
    # 第一个 trace 的 r 数据应已数值化（high=5/medium=3/low=1）
    r = fig.data[0].r
    assert 5 in r and 3 in r and 1 in r


def test_scatter_perceptual_map_separates_self_and_others():
    from src.frontend.render import _scatter_perceptual_map
    fig = _scatter_perceptual_map({
        "x_axis": {"attribute": "Price", "low_label": "L", "high_label": "H", "scale_max": 5},
        "y_axis": {"attribute": "Quality", "low_label": "L", "high_label": "H", "scale_max": 5},
        "plotted_brands": [
            {"competitor_name": "A", "is_self": False, "x_score": 2, "y_score": 3,
             "confidence": "high", "score_rationale": "x"},
            {"competitor_name": "Us", "is_self": True, "x_score": 4, "y_score": 4,
             "confidence": "high", "score_rationale": "x"},
        ],
    })
    assert fig is not None
    # 应有两条 trace：竞品 + 我方
    assert len(fig.data) == 2


def test_scatter_perceptual_map_empty_returns_none():
    from src.frontend.render import _scatter_perceptual_map
    assert _scatter_perceptual_map({"plotted_brands": []}) is None


def test_scatter_magic_quadrant_has_quadrant_lines():
    from src.frontend.render import _scatter_magic_quadrant
    fig = _scatter_magic_quadrant([
        {"competitor_name": "A", "ability_to_execute_score": 4, "completeness_of_vision_score": 4},
        {"competitor_name": "B", "ability_to_execute_score": 1, "completeness_of_vision_score": 2},
    ])
    assert fig is not None
    # 至少有 2 条分隔线 + 4 个象限标签 annotation
    assert len(fig.layout.shapes) >= 2
    assert len(fig.layout.annotations) >= 4


def test_line_strategy_canvas_returns_curve_per_brand():
    from src.frontend.render import _line_strategy_canvas
    fig = _line_strategy_canvas({
        "competitive_factors": [{"name": "速度"}, {"name": "易用性"}],
        "value_curves": [
            {"competitor_name": "A", "is_self": False, "factor_levels": {"速度": 7, "易用性": 5}},
            {"competitor_name": "Us", "is_self": True, "factor_levels": {"速度": 5, "易用性": 8}},
        ],
    })
    assert fig is not None
    assert len(fig.data) == 2


def test_line_strategy_canvas_no_factors_returns_none():
    from src.frontend.render import _line_strategy_canvas
    assert _line_strategy_canvas({"competitive_factors": [], "value_curves": []}) is None


def test_render_s5_with_perceptual_map_and_canvas(st_spy):
    from src.frontend.render import _render_s5_payload
    _render_s5_payload({
        "scenario_type": "S5",
        "vendor_profiles": [{"competitor_name": "A", "ability_to_execute_score": 4,
                             "completeness_of_vision_score": 3, "mq_quadrant": "mq_leader",
                             "overview": "x" * 30}],
        "perceptual_map": {
            "x_axis": {"attribute": "Price", "low_label": "low", "high_label": "high"},
            "y_axis": {"attribute": "Quality", "low_label": "low", "high_label": "high"},
            "plotted_brands": [{"competitor_name": "A", "is_self": False, "x_score": 3,
                                "y_score": 4, "confidence": "high", "score_rationale": "x"}],
        },
        "strategy_canvas": {
            "competitive_factors": [{"name": "速度"}, {"name": "易用性"}],
            "value_curves": [{"competitor_name": "A", "is_self": False,
                              "factor_levels": {"速度": 7, "易用性": 5}}],
        },
        "errc_grid": {"eliminate": [{"factor": "x", "rationale": "y"}]},
        "positioning_statement": {"target_customer": "x", "need_or_opportunity": "y",
                                  "product_name": "P", "product_category": "x",
                                  "key_benefit": "x", "primary_alternative": "x",
                                  "primary_differentiation": "x", "confidence": "from_user_brief",
                                  "full_statement_text": "For X who Y..."},
        "category_strategy": {"chosen_category": "AI 工具", "why_this_category": "x" * 30,
                              "competitors_implied": ["A"]},
    })
    headers = [str(c) for c in st_spy.subheader.call_args_list]
    assert any("竞品画像 Gartner MQ" in h for h in headers)
    assert any("感知地图 Perceptual Map" in h for h in headers)
    assert any("战略画布" in h for h in headers)
    assert any("ERRC 4 宫格" in h for h in headers)


# ============ [fix3 prove-it] render_analysis_response: report=None 时的文案兜底 ============

def test_render_response_with_valid_report_shows_success(st_spy):
    """report 非空 → 显示分析完成 + 渲染报告"""
    from src.frontend.render import render_analysis_response
    data = {"status": "completed", "trace_id": "abc-123",
            "report": {"title": "T", "executive_summary": {}}}
    render_analysis_response(data)
    # success 被调用且文案含 trace_id
    success_calls = [c.args[0] for c in st_spy.success.call_args_list]
    assert any("abc-123" in s for s in success_calls), \
        f"应显示带 trace_id 的成功文案，实际 {success_calls}"
    # warning 不应被调用为"未能产出"
    warning_msgs = [c.args[0] for c in st_spy.warning.call_args_list]
    assert not any("未能产出" in w for w in warning_msgs)


def test_render_response_with_none_report_shows_warning(st_spy):
    """[fix3] report=None → 不该显示"分析完成"，要 warning + 提示去追溯面板"""
    from src.frontend.render import render_analysis_response
    data = {"status": "completed", "trace_id": "abc-123", "report": None}
    render_analysis_response(data)
    # 不应误报"分析完成"
    success_calls = [c.args[0] for c in st_spy.success.call_args_list]
    assert not any("分析完成" in s for s in success_calls), \
        f"report=None 时不该 success，实际 {success_calls}"
    # 应有 warning 提示用户去追溯面板
    warning_msgs = [c.args[0] for c in st_spy.warning.call_args_list]
    assert any("未能产出" in w or "追溯" in w for w in warning_msgs), \
        f"应 warning 提示未产出 + 追溯，实际 {warning_msgs}"
    # 应展示 trace_id 让用户可手动查
    assert any("abc-123" in w for w in warning_msgs), \
        f"warning 应含 trace_id，实际 {warning_msgs}"


def test_render_response_with_empty_report_shows_warning(st_spy):
    """report={}（空 dict）→ 同 None，避免 success 文案误导"""
    from src.frontend.render import render_analysis_response
    data = {"status": "completed", "trace_id": "abc-123", "report": {}}
    render_analysis_response(data)
    success_calls = [c.args[0] for c in st_spy.success.call_args_list]
    assert not any("分析完成" in s for s in success_calls)


def test_render_response_with_failed_status_shows_error(st_spy):
    """status != completed → error，不调 render_base_report"""
    from src.frontend.render import render_analysis_response
    data = {"status": "failed", "error": "graph crashed"}
    render_analysis_response(data)
    error_msgs = [c.args[0] for c in st_spy.error.call_args_list]
    assert any("graph crashed" in m or "失败" in m for m in error_msgs)


# ============ [fix16 prove-it] render_trace_report_tab 渲染历史 trace 的 report ============

def test_render_trace_report_tab_with_valid_report_calls_base_render(st_spy):
    """[fix16] 拿到非空 report dict 时应调 render_base_report 渲染美化版"""
    from src.frontend.render import render_trace_report_tab
    report = {"title": "历史报告", "executive_summary": {}}
    render_trace_report_tab(report)
    # 应有 title 渲染（间接验证 render_base_report 被走过）
    title_calls = [c.args[0] for c in st_spy.title.call_args_list]
    assert any("历史报告" in t for t in title_calls), \
        f"应调 render_base_report 渲染 title，实际 title 调用 {title_calls}"


def test_render_trace_report_tab_with_none_shows_warning(st_spy):
    """[fix16] report=None 时显示 warning，不崩"""
    from src.frontend.render import render_trace_report_tab
    render_trace_report_tab(None)
    warnings = [c.args[0] for c in st_spy.warning.call_args_list]
    assert any("无报告" in w or "未产出" in w or "为空" in w for w in warnings), \
        f"None 应触发 warning 文案，实际 {warnings}"


def test_render_trace_report_tab_with_empty_dict_shows_warning(st_spy):
    """[fix16] report={} 同样要 warning，不能裸跑 render_base_report 触发 KeyError"""
    from src.frontend.render import render_trace_report_tab
    render_trace_report_tab({})
    warnings = [c.args[0] for c in st_spy.warning.call_args_list]
    assert len(warnings) >= 1


# ============ [fix21 prove-it] PositioningStatement 6 位模板分行渲染 ============

def test_render_s5_positioning_breaks_six_position_template_into_lines(st_spy):
    """[fix21] 6 位定位陈述按 For/who/is a/that/Unlike/our product 分 6 行渲染，
    而不是 st.info 一坨英文连接词混中文。
    """
    from src.frontend.render import _render_s5_payload
    payload = {
        "scenario_type": "S5",
        "positioning_statement": {
            "target_customer": "中小互联网产品团队",
            "need_or_opportunity": "提升跨角色协作效率",
            "product_name": "Figma",
            "product_category": "实时协作平台",
            "key_benefit": "支持产品/设计/开发实时协同",
            "primary_alternative": "传统设计工具+办公文档组合",
            "primary_differentiation": "原生云端实时协作架构",
            "confidence": "llm_inferred",
            "full_statement_text": "[AI 推断版本，请人工校对] For ... unlike ...",
        },
    }
    _render_s5_payload(payload)
    # st.info 不应被调用为一坨英文长串（fix21 改用分行 markdown）
    info_calls = [c.args[0] for c in st_spy.info.call_args_list]
    assert not any(s.startswith("[AI 推断版本") and "For" in s and "Unlike" in s for s in info_calls), \
        f"PositioningStatement 不应再用 st.info 一坨字符串：{info_calls}"
    # 应有 markdown 调用包含 6 位结构关键词
    md_calls = [c.args[0] for c in st_spy.markdown.call_args_list]
    md_combined = "\n".join(md_calls)
    # 6 位模板的关键标识（中英文连接词）
    for label in ["For", "who", "Unlike"]:
        assert label in md_combined, \
            f"6 位模板缺连接词 {label}，markdown 调用：{md_calls[:5]}"


def test_render_s5_positioning_inferred_shows_warning_separately(st_spy):
    """[fix21] confidence != from_user_brief 时，水印「AI 推断 请人工校对」用独立 warning 醒目展示，
    而不是混进 statement 文本里。
    """
    from src.frontend.render import _render_s5_payload
    payload = {
        "scenario_type": "S5",
        "positioning_statement": {
            "target_customer": "X 用户群体",
            "need_or_opportunity": "Y 需求",
            "product_name": "Z 产品",
            "product_category": "Z 品类",
            "key_benefit": "提供 K 价值",
            "primary_alternative": "现有替代方案",
            "primary_differentiation": "差异化点",
            "confidence": "llm_inferred",
        },
    }
    _render_s5_payload(payload)
    warnings = [c.args[0] for c in st_spy.warning.call_args_list]
    assert any("人工校对" in w or "AI 推断" in w for w in warnings), \
        f"llm_inferred 时应用独立 warning 标注 AI 推断：{warnings}"


def test_render_s5_positioning_from_user_brief_no_warning(st_spy):
    """[fix21] confidence == from_user_brief 时不应显示 AI 推断 warning"""
    from src.frontend.render import _render_s5_payload
    payload = {
        "scenario_type": "S5",
        "positioning_statement": {
            "target_customer": "X 用户群体",
            "need_or_opportunity": "Y 需求",
            "product_name": "Z 产品",
            "product_category": "Z 品类",
            "key_benefit": "提供 K 价值",
            "primary_alternative": "现有替代方案",
            "primary_differentiation": "差异化点",
            "confidence": "from_user_brief",
        },
    }
    _render_s5_payload(payload)
    warnings = [c.args[0] for c in st_spy.warning.call_args_list]
    assert not any("人工校对" in w or "AI 推断" in w for w in warnings), \
        "from_user_brief 不应显示 AI 推断 warning"


# ============ [fix6 prove-it] session_state 持久化报告，避免按钮重跑导致 report 消失 ============

def test_render_response_persists_data_to_session_state(st_spy):
    """[fix6] render_analysis_response 必须把 data 存到 session_state['last_response']

    现象：Streamlit 每次按钮点击全脚本重跑；点击"加载追溯"会让"开始分析"if 块跳过，
    报告区消失。修法是让 render_analysis_response 持久化 data，主入口外层无条件
    检查并重渲染。
    """
    # session_state 用真 dict 模拟，便于断言赋值
    st_spy.session_state = {}
    from src.frontend.render import render_analysis_response
    data = {"status": "completed", "trace_id": "abc-123",
            "report": {"title": "T", "executive_summary": {}}}
    render_analysis_response(data)
    assert st_spy.session_state.get("last_response") == data, (
        "render_analysis_response 应把 data 存到 session_state['last_response']"
    )


def test_render_response_persists_even_when_report_none(st_spy):
    """[fix6] 即使 report=None 也要存 last_response，让用户能看到 warning + trace_id"""
    st_spy.session_state = {}
    from src.frontend.render import render_analysis_response
    data = {"status": "completed", "trace_id": "abc-123", "report": None}
    render_analysis_response(data)
    assert st_spy.session_state.get("last_response") == data


# ============ Round 2: staticPlot / subtitle / typography / table overflow ============


def test_chart_uses_static_plot_config(st_spy, monkeypatch):
    """R2 fix: plotly chart must use staticPlot=True to prevent all interaction"""
    monkeypatch.setattr("src.frontend.render._PLOTLY_OK", True)
    import plotly.graph_objects as go
    fig = go.Figure()
    from src.frontend.render import _render_chart_or_skip
    _render_chart_or_skip(fig)
    st_spy.plotly_chart.assert_called_once()
    call_kwargs = st_spy.plotly_chart.call_args[1]
    assert call_kwargs.get("config") == {"staticPlot": True}


def test_subtitle_uses_report_subtitle_class(st_spy):
    """副标题必须使用 report-subtitle class 且字体够大（不是 st.caption）"""
    from src.frontend.render import render_base_report
    render_base_report({"title": "T", "subtitle": "副标题内容"})
    md_calls = [c.args[0] for c in st_spy.markdown.call_args_list
                if len(c.args) > 0 and isinstance(c.args[0], str)]
    subtitle_calls = [m for m in md_calls if "report-subtitle" in m]
    assert len(subtitle_calls) == 1
    assert "副标题内容" in subtitle_calls[0]


def test_s2_players_table_no_differentiator_column(st_spy):
    """S2 市场玩家表不应包含'差异化'列（长文本拆出为 caption）"""
    from src.frontend.render import _render_s2_payload
    _render_s2_payload({
        "scenario_type": "S2",
        "players": [
            {"name": "A", "company": "Co", "market_role": "challenger",
             "market_share_pct": 10, "yoy_growth_pct": 20,
             "key_differentiator": "很长的差异化描述文本",
             "is_recommended": True, "is_collected": True},
        ],
        "market_concentration": "moderate",
    })
    # dataframe 应被调用，检查传入的 row dict 不含"差异化"key
    df_calls = st_spy.dataframe.call_args_list
    assert len(df_calls) >= 1
    rows = df_calls[0].args[0]
    for row in rows:
        assert "差异化" not in row
    # caption 应包含差异化内容
    cap_calls = [c.args[0] for c in st_spy.caption.call_args_list]
    assert any("很长的差异化描述文本" in c for c in cap_calls)


def test_s2_segments_table_no_key_needs_column(st_spy):
    """S2 消费者分群表不应包含'核心需求'列（长文本拆出为 caption）"""
    from src.frontend.render import _render_s2_payload
    _render_s2_payload({
        "scenario_type": "S2",
        "consumer_segments": [
            {"name": "开发者", "share_pct": 40, "addressability": "easy",
             "key_needs": ["API稳定", "文档清晰", "成本低"]},
        ],
    })
    df_calls = st_spy.dataframe.call_args_list
    assert len(df_calls) >= 1
    rows = df_calls[0].args[0]
    for row in rows:
        assert "核心需求" not in row
    cap_calls = [c.args[0] for c in st_spy.caption.call_args_list]
    assert any("API稳定" in c for c in cap_calls)
