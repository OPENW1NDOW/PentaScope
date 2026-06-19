"""critic v1.2.0 修复验证测试：场景 pair 字段名 + scenario_payload 不裁 + 全量传递。

三问题回归锁定：
1. scenario_payload 不裁剪 → report_brief 含 scenario_payload
2. 全量传递 → all_findings/all_narratives/all_recommendations 长度等于报告原始数量
3. 场景 pair 构造 → S2/S3/S4/S5 各自场景 pair 出现在返回列表，data_a/data_b 非空
"""
import json
from datetime import date


# ============ Fixtures ============

def _minimal_metadata(scenario="S1"):
    from src.schemas.report import ReportMetadata
    from src.schemas.common import DataSource
    return ReportMetadata(
        report_id="test", trace_id="test", scenario=scenario,
        publication_date=date(2026, 6, 19),
        data_sources=[DataSource(url="https://example.com")],
        confidence_level="medium",
    )


def _minimal_base_report(scenario, payload):
    """构造最小合法 BaseReport（用 model_construct 绕过 min_length）。"""
    from src.schemas.report import (
        BaseReport, ReportScope, Methodology, Finding,
        AnalysisSection, Recommendation, SwotEntry, Swot, ExecutiveSummary,
    )

    finding = Finding.model_construct(
        statement="statement " * 5, evidence="evidence " * 5,
        implication="implication " * 5, source_refs=[],
    )
    rec = Recommendation.model_construct(
        action="action " * 5, target_role="PM",
        priority="critical", timeline="immediate", rationale="rationale " * 5,
        source_refs=[],
    )
    section = AnalysisSection.model_construct(
        section_id="sec-1", heading="heading", narrative="narrative " * 50,
        section_type="overview", artifact_refs=[], source_refs=[],
    )
    sw = SwotEntry.model_construct(point="point " * 3, evidence="ev " * 5, source_refs=[])
    exec_summary = ExecutiveSummary.model_construct(
        context="ctx" * 40, core_thesis="thesis" * 20,
        key_findings_brief=["f1", "f2"], implications="imp" * 50,
        path_forward=["p1"],
    )

    return BaseReport.model_construct(
        metadata=_minimal_metadata(scenario),
        title="Test Report",
        at_a_glance=["point 1", "point 2", "point 3"],
        executive_summary=exec_summary,
        background="bg" * 100,
        scope=ReportScope.model_construct(competitors=["A", "B"], time_window="2026", regions=[], exclusions=[]),
        methodology=Methodology.model_construct(
            data_collection_approach="x" * 200,
            evaluation_criteria=["c1"], limitations=["l1"], sample_size_note="note",
        ),
        key_findings=[finding] * 8,
        analysis_sections=[section] * 6,
        swot=Swot.model_construct(
            strengths=[sw], weaknesses=[sw], opportunities=[sw], threats=[sw],
        ),
        conclusions="conclusions " * 30,
        recommendations=[rec] * 7,
        scenario_payload=payload,
    )


def _make_s2_payload():
    """构造 S2 payload 含 market_sizing + entry_strategy（model_construct 绕验证）。"""
    from src.schemas.scenarios.s2 import (
        S2MarketEntryPayload, MarketSizing, MarketValue,
        EntryStrategy, MarketPlayer, Trend, FiveForces, Force,
        CompetitorRecommendations, RecommendedCompetitor, Risk, Phase,
    )

    mv = MarketValue.model_construct(amount=10.0, currency="USD", unit="billion", year=2025, geography="global", value_basis="estimated", methodology_note="", source_refs=[])
    ms = MarketSizing.model_construct(artifact_id="ms-1", artifact_type="market_sizing", tam=mv, sam=mv, som=mv, cagr_pct=15.0, forecast_years=5, forecast_scenarios=None, triangulation_gap_pct=None)

    force = Force.model_construct(intensity="medium", drivers=["d1", "d2"], evidence=["e1"], implication="implication " * 3, source_refs=[])
    ff = FiveForces.model_construct(artifact_id="ff-1", artifact_type="five_forces", new_entrants=force, supplier_power=force, buyer_power=force, substitute_threat=force, competitive_rivalry=force)

    es = EntryStrategy.model_construct(
        artifact_id="es-1", artifact_type="entry_strategy",
        recommended_mode="niche_focus",
        target_segments=["SMB", "mid-market"],
        initial_positioning="差异化定位描述" * 3,
        key_success_factors=["f1", "f2"],
        main_risks=[Risk.model_construct(description="risk desc " * 3, likelihood="medium", impact="high", mitigation="mitigate " * 3)],
        timeline_phases=[
            Phase.model_construct(phase_name="phase1", duration="3m", key_milestones=["m1"], resource_requirements=""),
            Phase.model_construct(phase_name="phase2", duration="6m", key_milestones=["m2"], resource_requirements=""),
        ],
    )

    player = MarketPlayer.model_construct(name="Player A", company="Co A", market_role="incumbent", market_share_pct=30.0, yoy_growth_pct=5.0, one_line_summary="summary " * 3, key_differentiator="diff", is_recommended=True, is_collected=True, source_refs=[])
    trend = Trend.model_construct(trend_name="trend1", description="desc " * 5, supporting_data="", direction="up", time_horizon="mid_term", impact_on_entry="positive", source_refs=[])

    cr = CompetitorRecommendations.model_construct(
        user_provided_industry="SaaS", user_provided_competitors=[],
        recommended_competitors=[
            RecommendedCompetitor.model_construct(name="A", company="", why_recommended="why " * 5, confidence="high", source_refs=[]),
            RecommendedCompetitor.model_construct(name="B", company="", why_recommended="why " * 5, confidence="medium", source_refs=[]),
            RecommendedCompetitor.model_construct(name="C", company="", why_recommended="why " * 5, confidence="medium", source_refs=[]),
        ],
        selection_method="hybrid", selection_rationale="rationale " * 10,
    )

    return S2MarketEntryPayload.model_construct(
        scenario_type="S2", market_sizing=ms, five_forces=ff,
        industry_attractiveness_1_5=3, players=[player, player, player],
        market_concentration="moderate", consumer_segments=None,
        key_trends=[trend, trend], entry_strategy=es, pestel=None,
        competitor_recommendations=cr,
    )


def _make_s3_payload():
    """构造 S3 payload 含 packaging + recommendations_summary（model_construct 绕验证）。"""
    from src.schemas.scenarios.s3 import (
        S3PricingStrategyPayload, PricingBaseline, ValueDriver,
        FeatureClassification, Packaging, RecommendedPriceTier,
        CompetitorPricing, ObservedCompetitorTier, PricingRecommendationsSummary,
        RolloutStep,
    )
    from src.schemas.scenarios.s2 import Risk
    from src.schemas.common import SourceRef

    baseline = PricingBaseline.model_construct(current_pricing_model="per_seat", current_tier_count=3, current_arpu_note="", pain_points=["p1"], source_refs=[])
    vd = ValueDriver.model_construct(driver_name="driver1", importance="high", evidence="evidence " * 5, source_refs=[])
    fc = FeatureClassification.model_construct(hygiene_factors=["h1"], preference_drivers=["p1"], premium_drivers=["pm1"])

    tier = RecommendedPriceTier.model_construct(
        name="Pro", position="better", monthly_price=99.0, annual_price=999.0,
        currency="USD", billing_unit="per_seat", is_recommended=True,
        target_persona="中型团队产品经理负责人",
        included_features=["f1", "f2"], gated_features=[], cta_copy="", upgrade_trigger="",
    )
    packaging = Packaging.model_construct(
        artifact_id="pkg-1", artifact_type="packaging",
        tiers=[tier, tier, tier],
        annual_discount_pct=20.0, default_billing_cycle="annual",
        rationale="rationale " * 15,
    )

    obs_tier = ObservedCompetitorTier.model_construct(
        name="Basic", monthly_price=49.0, annual_price=490.0, currency="USD",
        billing_unit="per_seat", observed_is_most_popular=False,
        observed_target_persona="", observed_features=["f1"], observed_cta_copy="",
        source_refs=[SourceRef.model_construct(url="https://competitor.com/pricing", title="pricing")],
    )
    cp = CompetitorPricing.model_construct(
        artifact_id="cp-1", artifact_type="competitor_pricing",
        competitor_name="Competitor X", pricing_model="per_seat",
        tiers=[obs_tier], free_plan_strategy="freemium", discount_strategy="", notes="",
        source_refs=[SourceRef.model_construct(url="https://competitor.com/pricing", title="pricing")],
    )

    rec_summary = PricingRecommendationsSummary.model_construct(
        recommended_packaging_summary="推荐采用三层 GBB 套餐结构，预计提升 ARR 30%" * 2,
        expected_arr_uplift_pct=30.0,
        expected_arr_uplift_basis="competitor_benchmark",
        expected_arr_uplift_methodology="基于竞品对标分析" * 3,
        expected_uplift_rationale="uplift rationale " * 5,
        main_risks=[Risk.model_construct(description="risk " * 5, likelihood="medium", impact="medium", mitigation="mit " * 5)],
    )

    rollout = RolloutStep.model_construct(artifact_id="rs-1", artifact_type="rollout_step", step_name="step1", description="desc " * 5, duration="2w", owner_team="", success_metric="")

    return S3PricingStrategyPayload.model_construct(
        scenario_type="S3", pricing_baseline=baseline,
        value_drivers=[vd, vd, vd], feature_classification=fc,
        wtp_research=None, packaging=packaging,
        competitive_pricing_matrix=[cp, cp],
        pricing_page_audit=[], recommendations_summary=rec_summary,
        rollout_plan=[rollout, rollout, rollout],
    )


def _make_s4_payload():
    """构造 S4 payload 含 threats + monitoring_actions（model_construct 绕验证）。"""
    from src.schemas.scenarios.s4 import (
        S4MonitoringPayload, ReviewPeriod, MonitoringThreat,
        MonitoringAction, MonitoringTrends, Battlecard, BattlecardSection,
    )

    rp = ReviewPeriod.model_construct(
        last_review_date=date(2026, 5, 1), current_review_date=date(2026, 6, 1),
        review_period_label="2026-05 to 2026-06", monitored_competitors=["A", "B"],
        prior_trace_id="prior-123", newly_added_competitors=[], dropped_competitors=[],
    )
    threat = MonitoringThreat.model_construct(
        artifact_id="th-1", artifact_type="monitoring_threat",
        title="竞品 A 发布 AI 功能大版本升级",
        severity="high", likelihood="high",
        description="竞品 A 在 6 月发布全新 AI 辅助功能，直接对标我方核心能力" * 2,
        recommended_response="加速我方 AI 路线图，提前发布 beta 版本" * 2,
        source_refs=[],
    )
    action = MonitoringAction.model_construct(
        description="紧急启动 AI 功能开发 sprint，抢在竞品 A 正式推广前发布 MVP 版本" * 2,
        owner_team="product", priority_tier="critical",
        due_date_estimate=date(2026, 7, 1), supporting_intel_refs=["th-1"],
    )
    trends = MonitoringTrends.model_construct(
        sentiment_trend="down", pricing_trend="up",
        release_velocity_trend="up", threat_level_trend="up", rationale="rationale",
    )
    bc_section = BattlecardSection.model_construct(section_name="quick_summary", content="content " * 5, completeness="partial", source_refs=[])
    bc = Battlecard.model_construct(
        artifact_id="bc-1", artifact_type="battlecard",
        competitor_name="A", sections=[bc_section] * 4, overall_completeness="partial",
    )

    return S4MonitoringPayload.model_construct(
        scenario_type="S4", review_period=rp,
        feature_changes=[], pricing_changes=[], messaging_changes=[],
        news_events=[], org_changes=[],
        threats=[threat], opportunities=[],
        trends=trends, monitoring_actions=[action],
        battlecards=[bc],
    )


def _make_s5_payload():
    """构造 S5 payload 含 perceptual_map(is_self) + positioning_statement。"""
    from src.schemas.scenarios.s5 import (
        S5PositioningPayload, S5VendorProfile, PerceptualMap, PerceptualAxis,
        PlottedBrand, StrategyCanvas, CompetitiveFactor, ValueCurve,
        ERRCGrid, PositioningStatement, CategoryStrategy,
    )
    from src.schemas.scenarios.s1 import VendorStrength, VendorCaution
    from src.schemas.common import SourceRef

    strength = VendorStrength.model_construct(point="strength " * 3, evidence="ev " * 5)
    caution = VendorCaution.model_construct(point="caution " * 3, evidence="ev " * 5)
    sr = SourceRef.model_construct(url="https://example.com", title="src")

    vp = S5VendorProfile.model_construct(
        competitor_name="Brand A",
        ability_to_execute_score=4.0, ability_to_execute_rationale="rationale " * 10,
        completeness_of_vision_score=3.5, completeness_of_vision_rationale="rationale " * 10,
        overview="overview " * 5, strengths=[strength, strength], cautions=[caution],
        source_refs=[sr],
    )
    vp_self = S5VendorProfile.model_construct(
        competitor_name="我方产品",
        ability_to_execute_score=3.0, ability_to_execute_rationale="rationale " * 10,
        completeness_of_vision_score=4.0, completeness_of_vision_rationale="rationale " * 10,
        overview="overview " * 5, strengths=[strength, strength], cautions=[caution],
        source_refs=[sr],
    )

    axis_x = PerceptualAxis.model_construct(attribute="易用性", low_label="难用", high_label="易用", scale_max=5, rationale="rationale " * 5)
    axis_y = PerceptualAxis.model_construct(attribute="功能深度", low_label="浅", high_label="深", scale_max=5, rationale="rationale " * 5)

    brand_self = PlottedBrand.model_construct(
        competitor_name="我方产品", is_self=True,
        x_score=4.2, y_score=3.8, bubble_size_metric=None,
        confidence="medium", score_rationale="score rationale " * 5, source_refs=[],
    )
    brand_other = PlottedBrand.model_construct(
        competitor_name="Brand A", is_self=False,
        x_score=3.0, y_score=4.5, bubble_size_metric=None,
        confidence="medium", score_rationale="score rationale " * 5, source_refs=[],
    )

    pm = PerceptualMap.model_construct(
        artifact_id="pm-1", artifact_type="perceptual_map",
        x_axis=axis_x, y_axis=axis_y,
        plotted_brands=[brand_self, brand_other, brand_other],
        white_space=[], cluster_zones=[], display_watermark="watermark",
    )

    factor = CompetitiveFactor.model_construct(name="factor1", industry_avg_level=5.0)
    vc = ValueCurve.model_construct(competitor_name="Brand A", is_self=False, factor_levels={"factor1": 4.0}, source_refs=[])
    vc_self = ValueCurve.model_construct(competitor_name="我方产品", is_self=True, factor_levels={"factor1": 3.5}, source_refs=[])
    sc = StrategyCanvas.model_construct(artifact_id="sc-1", artifact_type="strategy_canvas", competitive_factors=[factor], value_curves=[vc, vc_self])

    errc = ERRCGrid.model_construct(artifact_id="errc-1", artifact_type="errc_grid", eliminate=[], reduce=[], raise_level=[], create=[])

    ps = PositioningStatement.model_construct(
        target_customer="中小团队产品经理",
        need_or_opportunity="需要快速做竞品分析",
        product_name="PentaScope",
        product_category="AI 竞品分析工具",
        key_benefit="一键生成结构化竞品报告",
        primary_alternative="人工调研 + Excel",
        primary_differentiation="自动化多 Agent 协作生成专业级报告",
        confidence="from_user_brief",
    )

    cat_strategy = CategoryStrategy.model_construct(
        chosen_category="AI 竞品分析", why_this_category="why " * 10,
        competitors_implied=["Brand A"], risk_of_category_choice="",
    )

    return S5PositioningPayload.model_construct(
        scenario_type="S5", vendor_profiles=[vp_self, vp],
        perceptual_map=pm, strategy_canvas=sc, errc_grid=errc,
        blue_ocean_move=None, positioning_statement=ps, category_strategy=cat_strategy,
    )


# ============ 问题 1：scenario_payload 不裁剪 ============

def test_critic_inputs_contains_scenario_payload():
    """report_brief 必须包含 scenario_payload（不被裁剪）。"""
    from src.agents.inspector import _build_critic_inputs

    payload = _make_s2_payload()
    report = _minimal_base_report("S2", payload)
    user_prompt = _build_critic_inputs(report, [])

    inputs = json.loads(user_prompt)
    assert "scenario_payload" in inputs["report_brief"], (
        "scenario_payload 被裁掉了，critic 看不到场景血肉"
    )
    assert inputs["report_brief"]["scenario_payload"]["scenario_type"] == "S2"


# ============ 问题 3：全量传递 ============

def test_critic_inputs_all_findings_full_count():
    """all_findings 应传递全量（8 条），不抽样。"""
    from src.agents.inspector import _build_critic_inputs

    payload = _make_s2_payload()
    report = _minimal_base_report("S2", payload)
    user_prompt = _build_critic_inputs(report, [])

    inputs = json.loads(user_prompt)
    assert "all_findings" in inputs, "应该用 all_findings 而非 sampled_findings"
    assert len(inputs["all_findings"]) == 8


def test_critic_inputs_all_narratives_full_count():
    """all_narratives 应传递全量（6 段），不抽样。"""
    from src.agents.inspector import _build_critic_inputs

    payload = _make_s2_payload()
    report = _minimal_base_report("S2", payload)
    user_prompt = _build_critic_inputs(report, [])

    inputs = json.loads(user_prompt)
    assert "all_narratives" in inputs, "应该用 all_narratives 而非 sampled_narratives"
    assert len(inputs["all_narratives"]) == 6


def test_critic_inputs_all_recommendations_full_count():
    """all_recommendations 应传递全量（7 条），不抽样。"""
    from src.agents.inspector import _build_critic_inputs

    payload = _make_s2_payload()
    report = _minimal_base_report("S2", payload)
    user_prompt = _build_critic_inputs(report, [])

    inputs = json.loads(user_prompt)
    assert "all_recommendations" in inputs, "应该用 all_recommendations 而非 sampled_recommendations"
    assert len(inputs["all_recommendations"]) == 7


# ============ 问题 2：场景 pair 构造 ============

def test_s2_pair_market_sizing_vs_entry_strategy():
    """S2 场景 pair 应包含 market_sizing vs entry_strategy，且 data 非空。"""
    from src.agents.inspector import _build_limited_pairs

    payload = _make_s2_payload()
    report = _minimal_base_report("S2", payload)
    pairs = _build_limited_pairs(report)

    s2_pair = next((p for p in pairs if p["id"] == "s2_market_sizing_vs_entry_strategy"), None)
    assert s2_pair is not None, f"S2 pair 未出现在结果中。pair ids: {[p['id'] for p in pairs]}"
    assert s2_pair.get("data_a") is not None, "S2 pair data_a 为空（字段名可能错了）"
    assert s2_pair.get("data_b") is not None, "S2 pair data_b 为空（字段名可能错了）"
    # 验证包含有意义的数据
    assert "market_sizing" in s2_pair["data_a"]
    assert "entry_strategy" in s2_pair["data_b"]


def test_s3_pair_packaging_vs_recommendations_summary():
    """S3 场景 pair 应包含 packaging vs recommendations_summary，且 data 非空。"""
    from src.agents.inspector import _build_limited_pairs

    payload = _make_s3_payload()
    report = _minimal_base_report("S3", payload)
    pairs = _build_limited_pairs(report)

    s3_pair = next((p for p in pairs if p["id"] == "s3_packaging_vs_recommendations_summary"), None)
    assert s3_pair is not None, f"S3 pair 未出现在结果中。pair ids: {[p['id'] for p in pairs]}"
    assert s3_pair.get("data_a") is not None, "S3 pair data_a 为空"
    assert s3_pair.get("data_b") is not None, "S3 pair data_b 为空"
    assert "packaging" in s3_pair["data_a"]
    assert "recommendations_summary" in s3_pair["data_b"]


def test_s4_pair_threats_vs_monitoring_actions():
    """S4 场景 pair 应包含 threats vs monitoring_actions，且 data 非空。"""
    from src.agents.inspector import _build_limited_pairs

    payload = _make_s4_payload()
    report = _minimal_base_report("S4", payload)
    pairs = _build_limited_pairs(report)

    s4_pair = next((p for p in pairs if p["id"] == "s4_threats_vs_monitoring_actions"), None)
    assert s4_pair is not None, f"S4 pair 未出现在结果中。pair ids: {[p['id'] for p in pairs]}"
    assert s4_pair.get("data_a") is not None, "S4 pair data_a 为空"
    assert s4_pair.get("data_b") is not None, "S4 pair data_b 为空"
    assert "threats" in s4_pair["data_a"]
    assert "monitoring_actions" in s4_pair["data_b"]


def test_s5_pair_perceptual_map_vs_positioning():
    """S5 场景 pair 应包含 perceptual_map(is_self) vs positioning_statement，且 data 非空。"""
    from src.agents.inspector import _build_limited_pairs

    payload = _make_s5_payload()
    report = _minimal_base_report("S5", payload)
    pairs = _build_limited_pairs(report)

    s5_pair = next((p for p in pairs if p["id"] == "s5_perceptual_map_vs_positioning"), None)
    assert s5_pair is not None, f"S5 pair 未出现在结果中。pair ids: {[p['id'] for p in pairs]}"
    assert s5_pair.get("data_a") is not None, "S5 pair data_a 为空（字段名可能错了）"
    assert s5_pair.get("data_b") is not None, "S5 pair data_b 为空（字段名可能错了）"
    # 验证 self 坐标非空
    pm_self = s5_pair["data_a"].get("perceptual_map_self", {})
    assert pm_self.get("axis_x") is not None, "is_self 品牌 x 坐标丢失"
    assert pm_self.get("axis_y") is not None, "is_self 品牌 y 坐标丢失"


def test_s2_pair_count_is_4():
    """S2 报告应有 3 通用 + 1 场景 = 4 个 pair。"""
    from src.agents.inspector import _build_limited_pairs

    payload = _make_s2_payload()
    report = _minimal_base_report("S2", payload)
    pairs = _build_limited_pairs(report)
    assert len(pairs) == 4, f"期望 4 个 pair，实际 {len(pairs)}: {[p['id'] for p in pairs]}"
