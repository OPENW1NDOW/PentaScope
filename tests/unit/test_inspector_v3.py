"""inspector v3 单测：通用硬查 + 5 套场景硬查 + dispatcher + LLM 质检整合。

为避免造完整 BaseReport（5 套 scenario_payload schema 各自有复杂 model_validator），
本测试用 SimpleNamespace 拼最小 mock，仅覆盖 inspector 实际访问的字段。
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.inspector import (
    InspectorAgent,
    _check_common,
    _check_s1,
    _check_s2,
    _check_s3,
    _check_s4,
    _check_s5,
    _check_warnings_prefix,
    _dispatch_scenario_check,
)


# ============ helpers ============

def _section(sid="sec-1"):
    return SimpleNamespace(section_id=sid)


def _rec(priority="important"):
    return SimpleNamespace(priority=priority)


def _ds_list(n=3):
    return [SimpleNamespace(confidence="high") for _ in range(n)]


def _common_report(
    *,
    section_ids=None,
    at_a_glance=None,
    rec_priorities=None,
    data_sources_n=3,
):
    """返回适配 _check_common 的最小 mock"""
    section_ids = section_ids or ["s1", "s2", "s3", "s4"]
    at_a_glance = at_a_glance or ["有意义的洞察一" * 2, "有意义的洞察二" * 2, "有意义的洞察三" * 2]
    rec_priorities = rec_priorities or ["critical", "important", "consider"]
    return SimpleNamespace(
        analysis_sections=[_section(sid) for sid in section_ids],
        at_a_glance=at_a_glance,
        recommendations=[_rec(p) for p in rec_priorities],
        metadata=SimpleNamespace(data_sources=_ds_list(data_sources_n)),
    )


# ============ _check_common ============

def test_common_no_issues_for_clean_report():
    issues = _check_common(_common_report())
    assert issues == []


def test_common_detects_duplicate_section_ids():
    issues = _check_common(_common_report(section_ids=["s1", "s1", "s2", "s3"]))
    assert any("section_id" in i.field and "重复" in i.reason for i in issues)


def test_common_detects_placeholder_at_a_glance():
    issues = _check_common(_common_report(at_a_glance=["太短", "也短", "N/A"]))
    assert any(i.field == "at_a_glance" and i.severity == "minor" for i in issues)


def test_common_detects_all_critical_priorities():
    issues = _check_common(_common_report(rec_priorities=["critical", "critical", "critical", "critical"]))
    assert any(i.field == "recommendations.priority" for i in issues)


def test_common_detects_too_few_data_sources():
    issues = _check_common(_common_report(data_sources_n=2))
    assert any(i.field == "metadata.data_sources" and i.severity == "major" for i in issues)


# ============ _check_s1 ============

def test_s1_detects_vendor_undercoverage():
    """vendor_profiles 缺竞品 → 报警（feature_matrix.competitors 含我方需排除）"""
    payload = SimpleNamespace(
        feature_matrix=SimpleNamespace(
            our_product_name="Us",
            competitors=["Us", "A", "B", "C"],  # 含我方
            categories=[SimpleNamespace(features=[SimpleNamespace(scores={"A": SimpleNamespace(score=2)})])],
        ),
        vendor_profiles=[SimpleNamespace(competitor_name="A")],  # 仅 A，缺 B/C
        white_space_features=["any"],
        feature_gaps=["any"],
    )
    issues = _check_s1(payload)
    assert any(i.field == "scenario_payload.vendor_profiles" for i in issues)


def test_s1_no_warning_when_vendor_covers_all_competitors_excl_self():
    """vendor 数 = matrix.competitors - our_product 数 → 不报警（修复 06-09 误报）"""
    payload = SimpleNamespace(
        feature_matrix=SimpleNamespace(
            our_product_name="Notion",
            competitors=["Notion", "飞书", "语雀", "WPS"],  # 4 个含我方
            categories=[SimpleNamespace(features=[SimpleNamespace(scores={"飞书": SimpleNamespace(score=2)})])],
        ),
        vendor_profiles=[
            SimpleNamespace(competitor_name="飞书"),
            SimpleNamespace(competitor_name="语雀"),
            SimpleNamespace(competitor_name="WPS"),
        ],  # 3 个，恰好覆盖所有非我方
        white_space_features=["any"],
        feature_gaps=["any"],
    )
    issues = _check_s1(payload)
    # 不应有 vendor_profiles 报警
    assert not any(i.field == "scenario_payload.vendor_profiles" for i in issues)


def test_s1_detects_all_zero_feature_matrix():
    payload = SimpleNamespace(
        feature_matrix=SimpleNamespace(
            our_product_name="Us",
            competitors=["Us", "A", "B"],
            categories=[SimpleNamespace(features=[
                SimpleNamespace(scores={"A": SimpleNamespace(score=0), "B": SimpleNamespace(score=0)}),
            ])],
        ),
        vendor_profiles=[SimpleNamespace(competitor_name="A"), SimpleNamespace(competitor_name="B")],
        white_space_features=["any"],
        feature_gaps=["any"],
    )
    issues = _check_s1(payload)
    assert any(i.severity == "critical" and "评分均为 0" in i.reason for i in issues)


def test_s1_detects_no_feature_iteration_output():
    payload = SimpleNamespace(
        feature_matrix=SimpleNamespace(
            our_product_name="Us",
            competitors=["Us", "A"],
            categories=[SimpleNamespace(features=[SimpleNamespace(scores={"A": SimpleNamespace(score=2)})])],
        ),
        vendor_profiles=[SimpleNamespace(competitor_name="A")],
        white_space_features=[],
        feature_gaps=[],
    )
    issues = _check_s1(payload)
    assert any(i.field == "scenario_payload.feature_gaps" for i in issues)


# ============ _check_s2 ============

def _ms(value_basis="measured", amount=1.0):
    return SimpleNamespace(value_basis=value_basis, amount=amount)


def test_s2_detects_market_sizing_all_unknown():
    payload = SimpleNamespace(
        market_sizing=SimpleNamespace(tam=_ms("unknown", None), sam=_ms("unknown", None), som=_ms("unknown", None)),
        players=[SimpleNamespace(market_role="incumbent", is_recommended=True, is_collected=False)],
    )
    issues = _check_s2(payload)
    assert any(i.severity == "critical" and "market_sizing" in i.field for i in issues)


def test_s2_detects_single_role_players():
    payload = SimpleNamespace(
        market_sizing=SimpleNamespace(tam=_ms(), sam=_ms(), som=_ms()),
        players=[SimpleNamespace(market_role="incumbent", is_recommended=True, is_collected=False) for _ in range(3)],
    )
    issues = _check_s2(payload)
    assert any("单一 role" in i.reason for i in issues)


def test_s2_detects_no_collected_or_recommended_players():
    payload = SimpleNamespace(
        market_sizing=SimpleNamespace(tam=_ms(), sam=_ms(), som=_ms()),
        players=[
            SimpleNamespace(market_role="incumbent", is_recommended=False, is_collected=False),
            SimpleNamespace(market_role="challenger", is_recommended=False, is_collected=False),
        ],
    )
    issues = _check_s2(payload)
    assert any("scope 来源不明" in i.reason for i in issues)


# ============ _check_s3 ============

def test_s3_detects_too_few_tiers():
    payload = SimpleNamespace(
        packaging=SimpleNamespace(tiers=[SimpleNamespace(), SimpleNamespace()]),
        wtp_research=SimpleNamespace(),
        recommendations_summary=SimpleNamespace(expected_arr_uplift_basis="measured_pilot"),
        competitive_pricing_matrix=[SimpleNamespace(), SimpleNamespace()],
    )
    issues = _check_s3(payload)
    assert any(i.field == "scenario_payload.packaging.tiers" for i in issues)


def test_s3_detects_missing_wtp_research():
    payload = SimpleNamespace(
        packaging=SimpleNamespace(tiers=[SimpleNamespace()] * 3),
        wtp_research=None,
        recommendations_summary=SimpleNamespace(expected_arr_uplift_basis="measured_pilot"),
        competitive_pricing_matrix=[SimpleNamespace(), SimpleNamespace()],
    )
    issues = _check_s3(payload)
    assert any(i.field == "scenario_payload.wtp_research" for i in issues)


def test_s3_detects_llm_inferred_arr_uplift():
    payload = SimpleNamespace(
        packaging=SimpleNamespace(tiers=[SimpleNamespace()] * 3),
        wtp_research=SimpleNamespace(),
        recommendations_summary=SimpleNamespace(expected_arr_uplift_basis="llm_inferred"),
        competitive_pricing_matrix=[SimpleNamespace(), SimpleNamespace()],
    )
    issues = _check_s3(payload)
    assert any("llm_inferred" in i.reason for i in issues)


# ============ _check_s4 ============

def test_s4_detects_no_changes_in_non_first_review():
    payload = SimpleNamespace(
        review_period=SimpleNamespace(prior_trace_id="20260601-120000-abc123"),
        feature_changes=[], pricing_changes=[], messaging_changes=[],
        news_events=[], org_changes=[],
        threats=[SimpleNamespace()], opportunities=[],
        battlecards=[SimpleNamespace(overall_completeness="partial")],
    )
    issues = _check_s4(payload)
    assert any("changes 全部为空" in i.reason for i in issues)


def test_s4_skips_changes_check_in_first_review():
    payload = SimpleNamespace(
        review_period=SimpleNamespace(prior_trace_id=None),
        feature_changes=[], pricing_changes=[], messaging_changes=[],
        news_events=[], org_changes=[],
        threats=[SimpleNamespace()], opportunities=[],
        battlecards=[SimpleNamespace(overall_completeness="partial")],
    )
    issues = _check_s4(payload)
    assert not any("changes 全部为空" in i.reason for i in issues)


def test_s4_detects_empty_threats_and_opportunities():
    payload = SimpleNamespace(
        review_period=SimpleNamespace(prior_trace_id=None),
        feature_changes=[], pricing_changes=[], messaging_changes=[],
        news_events=[], org_changes=[],
        threats=[], opportunities=[],
        battlecards=[SimpleNamespace(overall_completeness="partial")],
    )
    issues = _check_s4(payload)
    assert any("threats 和 opportunities 都为空" in i.reason for i in issues)


def test_s4_detects_all_empty_battlecards():
    payload = SimpleNamespace(
        review_period=SimpleNamespace(prior_trace_id=None),
        feature_changes=[], pricing_changes=[], messaging_changes=[],
        news_events=[], org_changes=[],
        threats=[SimpleNamespace()], opportunities=[],
        battlecards=[
            SimpleNamespace(overall_completeness="empty"),
            SimpleNamespace(overall_completeness="empty"),
        ],
    )
    issues = _check_s4(payload)
    assert any("completeness=empty" in i.reason for i in issues)


# ============ _check_s5 ============

def test_s5_detects_missing_self_in_perceptual_map():
    payload = SimpleNamespace(
        perceptual_map=SimpleNamespace(plotted_brands=[
            SimpleNamespace(is_self=False), SimpleNamespace(is_self=False),
        ]),
        blue_ocean_move=SimpleNamespace(),
        positioning_statement=SimpleNamespace(confidence="from_user_brief"),
    )
    issues = _check_s5(payload)
    assert any("is_self=True 缺失" in i.reason for i in issues)


def test_s5_detects_missing_blue_ocean():
    payload = SimpleNamespace(
        perceptual_map=SimpleNamespace(plotted_brands=[SimpleNamespace(is_self=True)]),
        blue_ocean_move=None,
        positioning_statement=SimpleNamespace(confidence="from_user_brief"),
    )
    issues = _check_s5(payload)
    assert any(i.field == "scenario_payload.blue_ocean_move" for i in issues)


def test_s5_detects_low_confidence_positioning():
    payload = SimpleNamespace(
        perceptual_map=SimpleNamespace(plotted_brands=[SimpleNamespace(is_self=True)]),
        blue_ocean_move=SimpleNamespace(),
        positioning_statement=SimpleNamespace(confidence="low_confidence"),
    )
    issues = _check_s5(payload)
    assert any(i.field == "scenario_payload.positioning_statement" for i in issues)


# ============ Dispatcher ============

@pytest.mark.parametrize("scenario,expected_fn", [
    ("S1", _check_s1), ("S2", _check_s2), ("S3", _check_s3),
    ("S4", _check_s4), ("S5", _check_s5),
])
def test_dispatcher_routes_to_right_function(scenario, expected_fn, monkeypatch):
    """dispatcher 根据 report.scenario 路由到对应 _check_sX"""
    called = []
    monkeypatch.setattr(f"src.agents.inspector.{expected_fn.__name__}",
                        lambda payload: called.append(scenario) or [])
    report = SimpleNamespace(scenario=scenario, scenario_payload=SimpleNamespace())
    _dispatch_scenario_check(report)
    assert called == [scenario]


def test_dispatcher_unknown_scenario_returns_empty():
    report = SimpleNamespace(scenario="S9", scenario_payload=SimpleNamespace())
    assert _dispatch_scenario_check(report) == []


# ============ _check_warnings_prefix（E3 / v3-R17） ============

def test_warnings_prefix_no_placeholder_returns_empty():
    report = SimpleNamespace(metadata=SimpleNamespace(warnings=["info: 普通信息"]))
    assert _check_warnings_prefix(report) == []


def test_warnings_prefix_detects_placeholder_section():
    report = SimpleNamespace(metadata=SimpleNamespace(warnings=[
        "placeholder_section:feature_matrix_analysis",
        "placeholder_section:vendor_profile_analysis",
    ]))
    issues = _check_warnings_prefix(report)
    assert len(issues) == 1
    assert issues[0].severity == "major"
    assert "placeholder" in issues[0].reason


def test_warnings_prefix_detects_dropped_unverified_entries():
    report = SimpleNamespace(metadata=SimpleNamespace(warnings=[
        "dropped_unverified_entries:6 条 SWOT entries 缺 source_refs",
    ]))
    issues = _check_warnings_prefix(report)
    assert len(issues) == 1


def test_warnings_prefix_detects_placeholder_swot():
    report = SimpleNamespace(metadata=SimpleNamespace(warnings=["placeholder_swot 全部填占位"]))
    issues = _check_warnings_prefix(report)
    assert len(issues) == 1


# ============ InspectorAgent.inspect 整合 ============

@pytest.mark.asyncio
async def test_inspect_writes_quality_score_to_metadata():
    """inspect 调用后 metadata.quality_score 被回填"""
    metadata = SimpleNamespace(
        data_sources=_ds_list(3),
        quality_score=None,
        quality_score_calculation_note="",
        warnings=[],
    )
    swot = SimpleNamespace(strengths=[], weaknesses=[], opportunities=[], threats=[])
    report = SimpleNamespace(
        scenario="S1",
        scenario_payload=SimpleNamespace(
            feature_matrix=SimpleNamespace(
                our_product_name="Us",
                competitors=["Us", "A"],
                categories=[SimpleNamespace(features=[SimpleNamespace(scores={"A": SimpleNamespace(score=2)})])],
            ),
            vendor_profiles=[SimpleNamespace(competitor_name="A")],
            white_space_features=["x"], feature_gaps=["x"],
        ),
        analysis_sections=[_section()],
        at_a_glance=["足够长的洞察文本一" * 2, "足够长的洞察文本二" * 2, "足够长的洞察文本三" * 2],
        recommendations=[_rec("important")],
        key_findings=[SimpleNamespace(source_refs=["x"])],
        swot=swot,
        metadata=metadata,
    )
    report.model_dump_json = MagicMock(return_value="{}")  # for LLM check

    mock_llm = MagicMock()
    mock_llm.call_json = AsyncMock(return_value={"issues": []})

    insp = InspectorAgent(llm=mock_llm)
    feedback = await insp.inspect(report)

    assert metadata.quality_score is not None
    assert 0.0 <= metadata.quality_score <= 1.0
    assert "score=" in metadata.quality_score_calculation_note
    assert feedback.passed is True  # 干净报告应过


@pytest.mark.asyncio
async def test_inspect_llm_failure_does_not_block():
    """LLM 调用抛异常时 inspect 仍返回 feedback（非阻断）"""
    metadata = SimpleNamespace(
        data_sources=_ds_list(3),
        quality_score=None,
        quality_score_calculation_note="",
        warnings=[],
    )
    swot = SimpleNamespace(strengths=[], weaknesses=[], opportunities=[], threats=[])
    report = SimpleNamespace(
        scenario="S2",
        scenario_payload=SimpleNamespace(
            market_sizing=SimpleNamespace(tam=_ms(), sam=_ms(), som=_ms()),
            players=[
                SimpleNamespace(market_role="incumbent", is_recommended=True, is_collected=False),
                SimpleNamespace(market_role="challenger", is_recommended=False, is_collected=True),
            ],
        ),
        analysis_sections=[_section()],
        at_a_glance=["足够长一" * 3, "足够长二" * 3, "足够长三" * 3],
        recommendations=[_rec("important")],
        key_findings=[],
        swot=swot,
        metadata=metadata,
    )
    report.model_dump_json = MagicMock(return_value="{}")

    mock_llm = MagicMock()
    mock_llm.call_json = AsyncMock(side_effect=RuntimeError("LLM down"))

    insp = InspectorAgent(llm=mock_llm)
    feedback = await insp.inspect(report)
    assert feedback is not None
    assert metadata.quality_score is not None  # quality_score 仍被回填


@pytest.mark.asyncio
async def test_inspect_caps_quality_score_at_0_5_when_placeholder_warnings_present():
    """v3-R17：metadata.warnings 含 placeholder 前缀 → quality_score cap 到 0.5"""
    metadata = SimpleNamespace(
        data_sources=_ds_list(3),
        quality_score=None,
        quality_score_calculation_note="",
        warnings=["placeholder_section:feature_matrix_analysis"],
    )
    swot = SimpleNamespace(strengths=[], weaknesses=[], opportunities=[], threats=[])
    report = SimpleNamespace(
        scenario="S1",
        scenario_payload=SimpleNamespace(
            feature_matrix=SimpleNamespace(
                our_product_name="Us",
                competitors=["Us", "A"],
                categories=[SimpleNamespace(features=[SimpleNamespace(scores={"A": SimpleNamespace(score=2)})])],
            ),
            vendor_profiles=[SimpleNamespace(competitor_name="A")],
            white_space_features=["x"], feature_gaps=["x"],
        ),
        analysis_sections=[_section()],
        at_a_glance=["足够长一" * 3, "足够长二" * 3, "足够长三" * 3],
        recommendations=[_rec("important")],
        key_findings=[SimpleNamespace(source_refs=["x"])],
        swot=swot,
        metadata=metadata,
    )
    report.model_dump_json = MagicMock(return_value="{}")

    mock_llm = MagicMock()
    mock_llm.call_json = AsyncMock(return_value={"issues": []})

    insp = InspectorAgent(llm=mock_llm)
    await insp.inspect(report)
    assert metadata.quality_score == 0.5
    assert "capped" in metadata.quality_score_calculation_note


@pytest.mark.asyncio
async def test_inspect_dedups_issues_by_agent_field_keep_severest():
    """同 (agent, field) 多条 issue → 仅保留最严重的一条"""
    metadata = SimpleNamespace(
        data_sources=_ds_list(3),
        quality_score=None,
        quality_score_calculation_note="",
        warnings=[],
    )
    swot = SimpleNamespace(strengths=[], weaknesses=[], opportunities=[], threats=[])
    report = SimpleNamespace(
        scenario="S1",
        scenario_payload=SimpleNamespace(
            feature_matrix=SimpleNamespace(
                our_product_name="Us",
                competitors=["Us", "A"],
                categories=[SimpleNamespace(features=[SimpleNamespace(scores={"A": SimpleNamespace(score=2)})])],
            ),
            vendor_profiles=[SimpleNamespace(competitor_name="A")],
            white_space_features=["x"], feature_gaps=["x"],
        ),
        analysis_sections=[_section()],
        at_a_glance=["足够长一" * 3, "足够长二" * 3, "足够长三" * 3],
        recommendations=[_rec("important")],
        key_findings=[],
        swot=swot,
        metadata=metadata,
    )
    report.model_dump_json = MagicMock(return_value="{}")

    # LLM 报同 field 的 minor + major，去重应保留 major
    mock_llm = MagicMock()
    mock_llm.call_json = AsyncMock(return_value={"issues": [
        {"agent": "writer", "field": "x", "severity": "minor", "reason": "minor msg"},
        {"agent": "writer", "field": "x", "severity": "major", "reason": "major msg"},
    ]})

    insp = InspectorAgent(llm=mock_llm)
    feedback = await insp.inspect(report)
    same_field = [i for i in feedback.issues if i.field == "x"]
    assert len(same_field) == 1
    assert same_field[0].severity == "major"
