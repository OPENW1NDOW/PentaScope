from src.schemas.scenarios.s2 import (
    S2MarketEntryPayload, MarketSizing, MarketValue, FiveForces, Force,
    MarketPlayer, Trend, EntryStrategy, Risk, Phase,
    CompetitorRecommendations, RecommendedCompetitor, PESTEL, PESTELFactor,
)


def test_market_value_optional_amount():
    """MarketValue.amount 可空（防幻觉）"""
    mv = MarketValue(value_basis="unknown")
    assert mv.amount is None
    assert mv.currency == "unknown"


def test_market_player_optional_share():
    p = MarketPlayer(
        name="A",
        market_role="incumbent",
        one_line_summary="A 的简介足够长一些",
    )
    assert p.market_share_pct is None


def test_force_intensity_three_levels():
    f = Force(
        intensity="high",
        drivers=["d1", "d2"],
        evidence=["e1"],
        implication="影响描述足够长一些字数补满二十字以上的内容",
    )
    assert f.intensity == "high"


def _make_minimal_s2_payload():
    """构造最小合法 S2 载荷"""
    return S2MarketEntryPayload(
        market_sizing=MarketSizing(
            artifact_id="ms1",
            tam=MarketValue(value_basis="unknown"),
            sam=MarketValue(value_basis="unknown"),
            som=MarketValue(value_basis="unknown"),
        ),
        five_forces=FiveForces(
            artifact_id="ff1",
            new_entrants=Force(intensity="medium", drivers=["d1", "d2"], evidence=["e1"], implication="x" * 30),
            supplier_power=Force(intensity="low", drivers=["d1", "d2"], evidence=["e1"], implication="x" * 30),
            buyer_power=Force(intensity="medium", drivers=["d1", "d2"], evidence=["e1"], implication="x" * 30),
            substitute_threat=Force(intensity="low", drivers=["d1", "d2"], evidence=["e1"], implication="x" * 30),
            competitive_rivalry=Force(intensity="high", drivers=["d1", "d2"], evidence=["e1"], implication="x" * 30),
        ),
        industry_attractiveness_1_5=3,
        players=[
            MarketPlayer(name="A", market_role="incumbent", one_line_summary="x" * 20),
            MarketPlayer(name="B", market_role="challenger", one_line_summary="x" * 20),
            MarketPlayer(name="C", market_role="emerging", one_line_summary="x" * 20),
        ],
        market_concentration="moderate",
        key_trends=[
            Trend(trend_name="趋势 1 描述", description="x" * 30, direction="up", time_horizon="short_term", impact_on_entry="positive"),
            Trend(trend_name="趋势 2 描述", description="x" * 30, direction="flat", time_horizon="mid_term", impact_on_entry="mixed"),
        ],
        entry_strategy=EntryStrategy(
            artifact_id="es1",
            recommended_mode="niche_focus",
            target_segments=["segA"],
            initial_positioning="x" * 30,
            key_success_factors=["f1", "f2"],
            main_risks=[Risk(description="风险描述长度足够多字数补齐", likelihood="medium", impact="medium", mitigation="缓解描述长度足够多字数补齐")],
            timeline_phases=[
                Phase(phase_name="阶段一描述", duration="0-3 月", key_milestones=["m1"]),
                Phase(phase_name="阶段二描述", duration="3-6 月", key_milestones=["m2"]),
            ],
        ),
        competitor_recommendations=CompetitorRecommendations(
            user_provided_industry="知识管理 SaaS",
            recommended_competitors=[
                RecommendedCompetitor(name="A", why_recommended="行业头部领导者代表 leader", confidence="high"),
                RecommendedCompetitor(name="B", why_recommended="行业挑战者中坚力量代表", confidence="medium"),
                RecommendedCompetitor(name="C", why_recommended="新兴玩家潜力代表企业", confidence="low"),
            ],
            selection_method="search_api_top_n",
            selection_rationale="基于行业搜索 Top 5 玩家加 LLM 综合筛选" * 2,
        ),
    )


def test_s2_pestel_optional_default_none():
    """S2.pestel 默认 None"""
    p = _make_minimal_s2_payload()
    assert p.pestel is None


def test_s2_payload_constructs():
    p = _make_minimal_s2_payload()
    assert p.scenario_type == "S2"
    assert len(p.players) == 3
    assert p.industry_attractiveness_1_5 == 3


def test_pestel_factor_severity_three_levels():
    pf = PESTELFactor(
        name="政策法规变化",
        impact="threat",
        severity="high",
        description="数据合规法规收紧导致" + "x" * 20,
    )
    assert pf.severity == "high"


def test_pestel_optional_default_factory():
    p = PESTEL(artifact_id="ps1")
    assert p.political == []
    assert p.economic == []
