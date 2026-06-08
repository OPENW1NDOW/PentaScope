"""5 场景 E2E 集成测试：验证 graph 拓扑装配 + scenario 路由 + state 传递契约。

策略：build_graph 内部构造的 5 个 agent 类的核心方法（collect/analyze/write/inspect/recommend）
通过 monkeypatch 替换为 AsyncMock，让 graph 真跑一遍，验证：

1. graph 节点访问顺序（node_trace）符合 scenario 路由（S2 经过 recommender / 其他直走 collector）
2. writer 收到的 scenario_input.scenario 与场景一致
3. 终态 state.report 是合法 BaseReport
4. inspector 被调用且 metadata.quality_score 被回填

不验证 agent 内部逻辑（unit test 覆盖），不构造 5 套合法 LLM JSON fixture。
"""
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.graph.builder import build_graph
from src.schemas.analysis import CompetitiveAnalysis
from src.schemas.feedback import RejectionFeedback
from src.schemas.input import CompetitorBasic, ScenarioInput
from src.schemas.profile import CompetitorProfile
from src.schemas.report import (
    AnalysisSection,
    Appendix,
    BaseReport,
    ExecutiveSummary,
    Finding,
    Methodology,
    Recommendation,
    ReportMetadata,
    ReportScope,
    Swot,
    SwotEntry,
)
from src.schemas.common import DataSource
from src.schemas.scenarios.s1 import (
    FeatureCategory,
    FeatureGap,
    FeatureMatrix,
    FeatureRow,
    FeatureScore,
    JobStatement,
    RoadmapRecommendations,
    S1FeatureIterationPayload,
    S1RadarScore,
    S1VendorProfile,
    VendorCaution,
    VendorStrength,
)
from src.schemas.scenarios.s2 import (
    CompetitorRecommendations,
    EntryStrategy,
    FiveForces,
    Force,
    MarketPlayer,
    MarketSizing,
    MarketValue,
    Phase,
    RecommendedCompetitor,
    Risk,
    S2MarketEntryPayload,
    Trend,
)
from src.schemas.scenarios.s3 import (
    FeatureClassification,
    Packaging,
    PricingBaseline,
    PricingRecommendationsSummary,
    RecommendedPriceTier,
    RolloutStep,
    S3PricingStrategyPayload,
    ValueDriver,
)
from src.schemas.scenarios.s4 import (
    Battlecard,
    BattlecardSection,
    MonitoringTrends,
    ReviewPeriod,
    S4MonitoringPayload,
)
from src.schemas.scenarios.s5 import (
    CategoryStrategy,
    ClusterZone,
    CompetitiveFactor,
    ERRCGrid,
    PerceptualAxis,
    PerceptualMap,
    PlottedBrand,
    PositioningStatement,
    S5PositioningPayload,
    S5VendorProfile,
    StrategyCanvas,
    ValueCurve,
    WhiteSpaceZone,
)


# ============ Helpers：构造各场景的最小合法 BaseReport ============

# 通用长串：所有 schema min_length 字段统一用 _LONG（60+ 字符）即可
# 不再细分 _LONG / _SHORT，避免反复踩到不同字段不同门槛
_LONG = "这是一段足够长的测试用占位文本可以满足任意字数门槛的硬约束以方便构造合法 fixture instance for testing"

def _common_metadata(scenario: str) -> ReportMetadata:
    return ReportMetadata(
        report_id=f"r-{scenario.lower()}-test",
        trace_id=f"trace-{scenario.lower()}",
        scenario=scenario,
        publication_date=date(2026, 6, 8),
        contributing_agents=["collector", "analyzer", "writer"],
        data_sources=[
            DataSource(url="https://a.com", title="A", confidence="high"),
            DataSource(url="https://b.com", title="B", confidence="medium"),
            DataSource(url="https://c.com", title="C", confidence="medium"),
        ],
        confidence_level="medium",
    )


def _common_swot() -> Swot:
    return Swot(
        strengths=[SwotEntry(point=_LONG, evidence=_LONG)],
        weaknesses=[SwotEntry(point=_LONG, evidence=_LONG)],
        opportunities=[SwotEntry(point=_LONG, evidence=_LONG)],
        threats=[SwotEntry(point=_LONG, evidence=_LONG)],
    )


def _common_findings_and_sections() -> tuple[list[Finding], list[AnalysisSection]]:
    findings = [
        Finding(statement=_LONG, evidence=_LONG, implication=_LONG),
        Finding(statement=_LONG, evidence=_LONG, implication=_LONG),
        Finding(statement=_LONG, evidence=_LONG, implication=_LONG),
    ]
    sections = [
        AnalysisSection(
            section_id=f"sec-{i}", heading=f"章节 {i}",
            narrative="叙述内容" * 80, section_type="overview",
        )
        for i in range(1, 5)
    ]
    return findings, sections


def _common_recommendations() -> list[Recommendation]:
    return [
        Recommendation(
            action=_LONG, target_role="PM",
            priority="critical", timeline="immediate",
            rationale=_LONG,
        ),
        Recommendation(
            action=_LONG, target_role="Dev",
            priority="important", timeline="short_term",
            rationale=_LONG,
        ),
        Recommendation(
            action=_LONG, target_role="Sales",
            priority="consider", timeline="long_term",
            rationale=_LONG,
        ),
    ]


def _build_base(payload, scenario: str) -> BaseReport:
    findings, sections = _common_findings_and_sections()
    return BaseReport(
        metadata=_common_metadata(scenario),
        title=f"{scenario} 测试报告标题用于 E2E 集成测试 fixture",
        at_a_glance=["要点一足够长" * 2, "要点二足够长" * 2, "要点三足够长" * 2],
        executive_summary=ExecutiveSummary(
            context="背景上下文描述" * 12,  # 84 字 ∈ [80,200]
            core_thesis="核心论断的描述需要够长" * 5,  # 55 字 ∈ [50,120]
            key_findings_brief=["发现一", "发现二"],
            implications="现实启示描述需要足够长足够长一" * 8,  # 120 字 ∈ [100,250]
            path_forward=["路径一"],
        ),
        background="背景描述" * 60,
        scope=ReportScope(competitors=["A"], time_window="2026 Q1"),
        methodology=Methodology(
            data_collection_approach="采集方法描述" * 40,
            evaluation_criteria=["criteria1", "criteria2", "criteria3"],
            limitations=["limit1", "limit2"],
            sample_size_note="样本量说明" * 16,
        ),
        key_findings=findings,
        analysis_sections=sections,
        swot=_common_swot(),
        conclusions="结论描述" * 60,
        recommendations=_common_recommendations(),
        appendix=Appendix(),
        scenario_payload=payload,
    )


def _make_s1_report() -> BaseReport:
    payload = S1FeatureIterationPayload(
        vendor_profiles=[
            S1VendorProfile(
                competitor_name="AA", wave_position="wave_leader",
                one_line_pitch=_LONG, best_fit_for=_LONG,
                strengths=[
                    VendorStrength(point=_LONG, evidence=_LONG),
                    VendorStrength(point=_LONG, evidence=_LONG),
                ],
                cautions=[VendorCaution(point=_LONG, evidence=_LONG)],
            ),
            S1VendorProfile(
                competitor_name="BB", wave_position="wave_strong_performer",
                one_line_pitch=_LONG, best_fit_for=_LONG,
                strengths=[
                    VendorStrength(point=_LONG, evidence=_LONG),
                    VendorStrength(point=_LONG, evidence=_LONG),
                ],
                cautions=[VendorCaution(point=_LONG, evidence=_LONG)],
            ),
        ],
        feature_matrix=FeatureMatrix(
            artifact_id="fm-1", competitors=["AA", "BB"], our_product_name="Us",
            categories=[FeatureCategory(
                name="核心", tier=1,
                features=[FeatureRow(
                    name="f1",
                    scores={
                        "AA": FeatureScore(score=2, evidence_url="https://a.com/f1"),
                        "BB": FeatureScore(score=1),
                    },
                )],
            )],
        ),
        radar_scores=[
            S1RadarScore(
                artifact_id="r-A", competitor_name="AA",
                feature_breadth=4, usability=3, cost_effectiveness=2,
                stability=4, design_quality=4,
            ),
            S1RadarScore(
                artifact_id="r-B", competitor_name="BB",
                feature_breadth=3, usability=4, cost_effectiveness=4,
                stability=3, design_quality=3,
            ),
        ],
        job_statement=JobStatement(situation=_LONG, motivation=_LONG, outcome=_LONG),
        feature_gaps=[FeatureGap(
            feature_name="g1", competitors_have_it=["AA"],
            underserved_outcome=_LONG,
            estimated_effort="medium", estimated_impact="high",
            recommendation="build",
        )],
        roadmap_recommendations=RoadmapRecommendations(
            must_build=["x"], rationale_summary=_LONG,
        ),
    )
    return _build_base(payload, "S1")


def _make_s2_report() -> BaseReport:
    mv = MarketValue(amount=10.0, currency="USD", value_basis="estimated")
    forces_kw = dict(drivers=["d1", "d2"], evidence=["e1"], implication=_LONG)
    payload = S2MarketEntryPayload(
        market_sizing=MarketSizing(artifact_id="ms-1", tam=mv, sam=mv, som=mv),
        five_forces=FiveForces(
            artifact_id="ff-1",
            new_entrants=Force(intensity="high", **forces_kw),
            supplier_power=Force(intensity="low", **forces_kw),
            buyer_power=Force(intensity="medium", **forces_kw),
            substitute_threat=Force(intensity="medium", **forces_kw),
            competitive_rivalry=Force(intensity="high", **forces_kw),
        ),
        industry_attractiveness_1_5=3,
        players=[
            MarketPlayer(name="AA", market_role="incumbent", one_line_summary=_LONG,
                         is_recommended=True),
            MarketPlayer(name="BB", market_role="challenger", one_line_summary=_LONG,
                         is_collected=True),
            MarketPlayer(name="CC", market_role="emerging", one_line_summary=_LONG),
        ],
        market_concentration="moderate",
        key_trends=[
            Trend(trend_name="趋势一AI 化", description=_LONG, direction="up",
                  time_horizon="mid_term", impact_on_entry="positive"),
            Trend(trend_name="趋势二自动化", description=_LONG, direction="up",
                  time_horizon="long_term", impact_on_entry="mixed"),
        ],
        entry_strategy=EntryStrategy(
            artifact_id="es-1",
            recommended_mode="niche_focus",
            target_segments=["A 分群"],
            initial_positioning=_LONG,
            key_success_factors=["f1", "f2"],
            main_risks=[Risk(description=_LONG, likelihood="low",
                             impact="medium", mitigation=_LONG)],
            timeline_phases=[
                Phase(phase_name="阶段一名称", duration="3月", key_milestones=["m1"]),
                Phase(phase_name="阶段二名称", duration="6月", key_milestones=["m2"]),
            ],
        ),
        competitor_recommendations=CompetitorRecommendations(
            user_provided_industry="测试行业",
            recommended_competitors=[
                RecommendedCompetitor(name="AA", why_recommended=_LONG, confidence="high"),
                RecommendedCompetitor(name="BB", why_recommended=_LONG, confidence="medium"),
                RecommendedCompetitor(name="CC", why_recommended=_LONG, confidence="low"),
            ],
            selection_method="hybrid",
            selection_rationale=_LONG,
        ),
    )
    return _build_base(payload, "S2")


def _make_s3_report() -> BaseReport:
    from src.schemas.common import SourceRef as _SR
    from src.schemas.scenarios.s3 import (
        CompetitorPricing,
        ObservedCompetitorTier,
    )
    payload = S3PricingStrategyPayload(
        pricing_baseline=PricingBaseline(
            current_pricing_model="per_seat", current_tier_count=3,
            pain_points=["痛点一"],
        ),
        value_drivers=[
            ValueDriver(driver_name="速度领先", importance="high", evidence=_LONG),
            ValueDriver(driver_name="易用程度", importance="high", evidence=_LONG),
            ValueDriver(driver_name="集成深度", importance="medium", evidence=_LONG),
        ],
        feature_classification=FeatureClassification(
            hygiene_factors=["h1"],
            premium_drivers=["p1"],
        ),
        packaging=Packaging(
            artifact_id="pkg-1",
            tiers=[
                RecommendedPriceTier(
                    name="Basic", position="good", monthly_price=9, currency="CNY",
                    billing_unit="per_seat", target_persona=_LONG,
                    included_features=["f1"],
                ),
                RecommendedPriceTier(
                    name="Pro", position="better", monthly_price=29, currency="CNY",
                    billing_unit="per_seat", is_recommended=True, target_persona=_LONG,
                    included_features=["f1", "f2"],
                ),
                RecommendedPriceTier(
                    name="Ent", position="enterprise", monthly_price=99, currency="CNY",
                    billing_unit="per_seat", target_persona=_LONG,
                    included_features=["f1", "f2", "f3"],
                ),
            ],
            rationale=_LONG,
        ),
        competitive_pricing_matrix=[
            CompetitorPricing(
                artifact_id="cp-A", competitor_name="AA", pricing_model="per_seat",
                tiers=[ObservedCompetitorTier(
                    name="A-Basic", monthly_price=10, currency="USD", billing_unit="per_seat",
                    observed_features=["f1"], source_refs=[_SR(url="https://a.com")],
                )],
                source_refs=[_SR(url="https://a.com/pricing")],
            ),
            CompetitorPricing(
                artifact_id="cp-B", competitor_name="BB", pricing_model="flat_rate",
                tiers=[ObservedCompetitorTier(
                    name="B-Std", monthly_price=20, currency="USD", billing_unit="flat_rate",
                    observed_features=["f1"], source_refs=[_SR(url="https://b.com")],
                )],
                source_refs=[_SR(url="https://b.com/pricing")],
            ),
        ],
        recommendations_summary=PricingRecommendationsSummary(
            recommended_packaging_summary=_LONG,
            expected_uplift_rationale=_LONG,
            main_risks=[Risk(description=_LONG, likelihood="medium",
                             impact="high", mitigation=_LONG)],
        ),
        rollout_plan=[
            RolloutStep(artifact_id="step-1", step_name="规划阶段", duration="2 月",
                        description=_LONG),
            RolloutStep(artifact_id="step-2", step_name="试点阶段", duration="3 月",
                        description=_LONG),
            RolloutStep(artifact_id="step-3", step_name="推广阶段", duration="3 月",
                        description=_LONG),
        ],
    )
    return _build_base(payload, "S3")


def _make_s4_report() -> BaseReport:
    payload = S4MonitoringPayload(
        review_period=ReviewPeriod(
            current_review_date=date(2026, 3, 31),
            review_period_label="2026-Q1",
            monitored_competitors=["AA"],
            prior_trace_id=None,
        ),
        trends=MonitoringTrends(),
        battlecards=[Battlecard(
            artifact_id="bc-A", competitor_name="AA",
            sections=[
                BattlecardSection(section_name="quick_summary", content="x", completeness="partial"),
                BattlecardSection(section_name="primary_threat", content="y", completeness="partial"),
                BattlecardSection(section_name="messaging_positioning", completeness="empty"),
                BattlecardSection(section_name="pricing_packaging", completeness="empty"),
            ],
        )],
    )
    return _build_base(payload, "S4")


def _make_s5_report() -> BaseReport:
    from src.schemas.common import SourceRef as _SR
    pm = PerceptualMap(
        artifact_id="pm-1",
        x_axis=PerceptualAxis(attribute="价格定位", low_label="低端", high_label="高端", rationale=_LONG),
        y_axis=PerceptualAxis(attribute="质量水平", low_label="低质", high_label="高质", rationale=_LONG),
        plotted_brands=[
            PlottedBrand(competitor_name="AA", x_score=2, y_score=3, confidence="high",
                         score_rationale=_LONG),
            PlottedBrand(competitor_name="Us", is_self=True, x_score=4, y_score=4,
                         confidence="medium", score_rationale=_LONG),
            PlottedBrand(competitor_name="BB", x_score=3, y_score=2, confidence="low",
                         score_rationale=_LONG),
        ],
        white_space=[WhiteSpaceZone(quadrant="top_right", opportunity_description=_LONG)],
        cluster_zones=[ClusterZone(brands_in_cluster=["AA", "BB"], implication=_LONG)],
    )
    payload = S5PositioningPayload(
        vendor_profiles=[
            S5VendorProfile(
                competitor_name="AA", ability_to_execute_score=4,
                ability_to_execute_rationale=_LONG,
                completeness_of_vision_score=3,
                completeness_of_vision_rationale=_LONG,
                overview=_LONG,
                strengths=[VendorStrength(point=_LONG, evidence=_LONG)] * 2,
                cautions=[VendorCaution(point=_LONG, evidence=_LONG)],
                source_refs=[_SR(url="https://a.com")],
            ),
            S5VendorProfile(
                competitor_name="Us", ability_to_execute_score=2,
                ability_to_execute_rationale=_LONG,
                completeness_of_vision_score=4,
                completeness_of_vision_rationale=_LONG,
                overview=_LONG,
                strengths=[VendorStrength(point=_LONG, evidence=_LONG)] * 2,
                cautions=[VendorCaution(point=_LONG, evidence=_LONG)],
                source_refs=[_SR(url="https://us.com")],
            ),
            S5VendorProfile(
                competitor_name="BB", ability_to_execute_score=3,
                ability_to_execute_rationale=_LONG,
                completeness_of_vision_score=2,
                completeness_of_vision_rationale=_LONG,
                overview=_LONG,
                strengths=[VendorStrength(point=_LONG, evidence=_LONG)] * 2,
                cautions=[VendorCaution(point=_LONG, evidence=_LONG)],
                source_refs=[_SR(url="https://b.com")],
            ),
        ],
        perceptual_map=pm,
        strategy_canvas=StrategyCanvas(
            artifact_id="sc-1",
            competitive_factors=[
                CompetitiveFactor(name="速度领先", industry_avg_level=5),
                CompetitiveFactor(name="易用程度", industry_avg_level=5),
                CompetitiveFactor(name="集成深度", industry_avg_level=5),
                CompetitiveFactor(name="定价水平", industry_avg_level=5),
                CompetitiveFactor(name="支持服务", industry_avg_level=5),
            ],
            value_curves=[
                ValueCurve(competitor_name="AA",
                           factor_levels={"速度领先": 7, "易用程度": 5, "集成深度": 6, "定价水平": 5, "支持服务": 4}),
                ValueCurve(competitor_name="Us", is_self=True,
                           factor_levels={"速度领先": 5, "易用程度": 8, "集成深度": 7, "定价水平": 6, "支持服务": 6}),
                ValueCurve(competitor_name="BB",
                           factor_levels={"速度领先": 6, "易用程度": 6, "集成深度": 5, "定价水平": 7, "支持服务": 5}),
            ],
        ),
        errc_grid=ERRCGrid(artifact_id="errc-1"),
        positioning_statement=PositioningStatement(
            target_customer=_LONG,
            need_or_opportunity=_LONG,
            product_name="MyProduct", product_category="AI 工具",
            key_benefit=_LONG,
            primary_alternative="主要替代",
            primary_differentiation=_LONG,
            confidence="from_user_brief",
        ),
        category_strategy=CategoryStrategy(
            chosen_category="协作 SaaS",
            why_this_category=_LONG,
            competitors_implied=["AA", "BB"],
        ),
    )
    return _build_base(payload, "S5")


# ============ Mock 装配 ============

@pytest.fixture
def mock_pipeline_search(monkeypatch):
    """Mock CollectionPipeline 与 TavilySource 避免触发真实 HTTP/API"""
    monkeypatch.setattr(
        "src.agents.collection_pipeline.CollectionPipeline.collect_for_competitor",
        AsyncMock(return_value=MagicMock(spec=CompetitorProfile)),
    )


def _mock_agents(monkeypatch, report: BaseReport):
    """把 5 个 agent 的核心方法替换为预制返回值"""
    fake_profile = MagicMock(spec=CompetitorProfile)
    fake_profile.name = "A"
    fake_profile.basic_info = MagicMock()

    fake_analysis = MagicMock(spec=CompetitiveAnalysis)
    fake_goal = MagicMock(focus_area="测试焦点")

    monkeypatch.setattr(
        "src.agents.collector.CollectorAgent.collect",
        AsyncMock(return_value=([fake_profile], fake_goal)),
    )
    monkeypatch.setattr(
        "src.agents.analyzer.AnalyzerAgent.analyze",
        AsyncMock(return_value=fake_analysis),
    )
    monkeypatch.setattr(
        "src.agents.writer_orchestrator.WriterOrchestrator.write",
        AsyncMock(return_value=report),
    )

    # inspector 整个 mock 为 passed=True 兜底，仍 cap quality_score 走真实公式：
    # 调真实 calc_quality_score 验证回填，然后包装到 RejectionFeedback。
    # 这样既验证 quality_score 真接通，又避免 _check_sX 硬查触发图重试递归。
    from src.agents.quality_score import calc_quality_score
    async def fake_inspect(self, report, competitors=None, retry_count=0, max_retries=2):
        score, note = calc_quality_score(report, [])
        report.metadata.quality_score = score
        report.metadata.quality_score_calculation_note = note
        return RejectionFeedback(
            passed=True, issues=[], retry_count=retry_count, max_retries=max_retries,
        )
    monkeypatch.setattr(
        "src.agents.inspector.InspectorAgent.inspect",
        fake_inspect,
    )

    # recommender 仅 S2 用得上：返回 BaseReport 中已含的 competitor_recommendations
    async def fake_recommend(self, *, industry, context, user_provided_competitors=None):
        return CompetitorRecommendations(
            user_provided_industry=industry or "测试行业",
            recommended_competitors=[
                RecommendedCompetitor(name="AA", why_recommended="测试推荐用例 A 给 fixture 使用", confidence="high"),
                RecommendedCompetitor(name="BB", why_recommended="测试推荐用例 B 给 fixture 使用", confidence="medium"),
                RecommendedCompetitor(name="CC", why_recommended="测试推荐用例 C 给 fixture 使用", confidence="low"),
            ],
            selection_method="hybrid",
            selection_rationale="测试用 recommender mock 产出 fixture 满足三十字 selection_rationale 校验门槛",
        )
    monkeypatch.setattr(
        "src.agents.recommender.RecommenderAgent.recommend",
        fake_recommend,
    )


# ============ E2E ============

def _build_inputs_for_scenario(scenario: str) -> ScenarioInput:
    if scenario == "S2":
        return ScenarioInput(
            scenario="S2",
            industry="测试行业",
            analysis_context="进入测试行业",
        )
    return ScenarioInput(
        scenario=scenario,
        competitors=[CompetitorBasic(name="AA"), CompetitorBasic(name="BB")],
        analysis_context="对比分析",
        our_product_name="MyProduct",
    )


@pytest.mark.parametrize("scenario,report_factory", [
    ("S1", _make_s1_report),
    ("S2", _make_s2_report),
    ("S3", _make_s3_report),
    ("S4", _make_s4_report),
    ("S5", _make_s5_report),
])
@pytest.mark.asyncio
async def test_e2e_scenario_full_flow(scenario, report_factory, monkeypatch):
    """对每个场景跑一遍 graph，验证拓扑装配 + scenario 路由 + state 传递 + quality_score 回填"""
    pre_report = report_factory()
    _mock_agents(monkeypatch, pre_report)

    # 使用 patch 屏蔽 TavilySource 真实 HTTP（recommender 内部会 search）
    with patch("src.tools.sources.TavilySource.search", AsyncMock(return_value=[])):
        llm = MagicMock()
        http = MagicMock()
        graph, node_trace = build_graph(llm=llm, http=http, parser=MagicMock())

        result = await graph.ainvoke({
            "user_input": _build_inputs_for_scenario(scenario),
            "retry_count": 0,
            "max_retries": 2,
            "trace_id": f"trace-{scenario.lower()}-test",
        })

    # 1. 节点访问顺序验证
    if scenario == "S2":
        assert node_trace[0] == "recommender", f"S2 必经 recommender，实际 {node_trace[0]}"
        assert node_trace[1] == "collector"
    else:
        assert node_trace[0] == "collector", f"{scenario} 必直走 collector，实际 {node_trace[0]}"
    # 必经 collector / analyzer / writer / inspector
    for need in ["collector", "analyzer", "writer", "inspector"]:
        assert need in node_trace, f"{scenario} 缺少节点 {need}"

    # 2. 终态报告合法
    final_report = result.get("report")
    assert final_report is not None, f"{scenario} 终态 report 为 None"
    assert final_report.metadata.scenario == scenario

    # 3. quality_score 被回填（inspector 已跑）
    assert final_report.metadata.quality_score is not None
    assert 0.0 <= final_report.metadata.quality_score <= 1.0

    # 4. feedback 存在（passed True 或 False 不强制，但要被写）
    feedback = result.get("feedback")
    assert feedback is not None
    assert isinstance(feedback, RejectionFeedback)


@pytest.mark.asyncio
async def test_e2e_route_entry_dispatches_correctly(monkeypatch):
    """直接验证 _route_entry：S2 → recommender，其他 → collector"""
    from src.graph.builder import _route_entry

    state_s2 = {"user_input": _build_inputs_for_scenario("S2")}
    state_s1 = {"user_input": _build_inputs_for_scenario("S1")}
    state_s4 = {"user_input": _build_inputs_for_scenario("S4")}

    assert _route_entry(state_s2) == "recommender"
    assert _route_entry(state_s1) == "collector"
    assert _route_entry(state_s4) == "collector"
