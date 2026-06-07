"""5 套场景规整器单测：枚举模糊匹配 + 清除 LLM 误填的 computed_field"""
import pytest

from src.agents.normalizers import normalize_for_scenario


# ============ 通用入口 ============

def test_normalize_for_scenario_unknown_raises():
    with pytest.raises(KeyError):
        normalize_for_scenario("S99", {})


def test_normalize_does_not_mutate_input_inplace():
    """规整器返回新 dict，不修改输入（避免上游意外副作用）"""
    raw = {"vendor_profiles": [{"wave_position": "leader"}]}
    snapshot = {"vendor_profiles": [{"wave_position": "leader"}]}
    normalize_for_scenario("S1", raw)
    assert raw == snapshot


# ============ S1 ============

def test_s1_wave_position_english_alias_to_wave_leader():
    raw = {"vendor_profiles": [{"wave_position": "leader"}]}
    cleaned = normalize_for_scenario("S1", raw)
    assert cleaned["vendor_profiles"][0]["wave_position"] == "wave_leader"


def test_s1_wave_position_chinese_to_wave_strong_performer():
    raw = {"vendor_profiles": [{"wave_position": "强势表现者"}]}
    cleaned = normalize_for_scenario("S1", raw)
    assert cleaned["vendor_profiles"][0]["wave_position"] == "wave_strong_performer"


def test_s1_wave_position_unknown_falls_to_contender():
    raw = {"vendor_profiles": [{"wave_position": "外星人"}]}
    cleaned = normalize_for_scenario("S1", raw)
    assert cleaned["vendor_profiles"][0]["wave_position"] == "wave_contender"


def test_s1_wave_position_already_valid_keeps():
    raw = {"vendor_profiles": [{"wave_position": "wave_leader"}]}
    cleaned = normalize_for_scenario("S1", raw)
    assert cleaned["vendor_profiles"][0]["wave_position"] == "wave_leader"


def test_s1_drops_feature_matrix_weighted_scores():
    """weighted_scores 是 computed_field，LLM 填了要删"""
    raw = {
        "feature_matrix": {
            "weighted_scores": {"A": 88.8},
            "categories": [{"name": "X", "tier": 1, "weight": 999, "features": []}],
        }
    }
    cleaned = normalize_for_scenario("S1", raw)
    assert "weighted_scores" not in cleaned["feature_matrix"]
    assert "weight" not in cleaned["feature_matrix"]["categories"][0]


def test_s1_recommendation_falls_back_to_build():
    raw = {
        "feature_gaps": [
            {"recommendation": "马上做"},
            {"recommendation": "build"},
            {"recommendation": "differentiate"},
        ]
    }
    cleaned = normalize_for_scenario("S1", raw)
    assert cleaned["feature_gaps"][0]["recommendation"] == "build"
    assert cleaned["feature_gaps"][1]["recommendation"] == "build"
    assert cleaned["feature_gaps"][2]["recommendation"] == "differentiate"


def test_s1_estimated_effort_impact_chinese_to_enum():
    raw = {"feature_gaps": [{"estimated_effort": "高", "estimated_impact": "中"}]}
    cleaned = normalize_for_scenario("S1", raw)
    assert cleaned["feature_gaps"][0]["estimated_effort"] == "high"
    assert cleaned["feature_gaps"][0]["estimated_impact"] == "medium"


# ============ S2 ============

def test_s2_force_intensity_chinese_to_english():
    raw = {"five_forces": {"new_entrants": {"intensity": "高"}}}
    cleaned = normalize_for_scenario("S2", raw)
    assert cleaned["five_forces"]["new_entrants"]["intensity"] == "high"


def test_s2_market_role_alias():
    raw = {"players": [
        {"market_role": "leader"},
        {"market_role": "在位者"},
        {"market_role": "新兴"},
    ]}
    cleaned = normalize_for_scenario("S2", raw)
    assert cleaned["players"][0]["market_role"] == "incumbent"
    assert cleaned["players"][1]["market_role"] == "incumbent"
    assert cleaned["players"][2]["market_role"] == "emerging"


def test_s2_market_concentration_chinese():
    raw = {"market_concentration": "分散"}
    cleaned = normalize_for_scenario("S2", raw)
    assert cleaned["market_concentration"] == "fragmented"


def test_s2_trend_direction_arrow():
    raw = {"key_trends": [
        {"direction": "↑"},
        {"direction": "上升"},
        {"direction": "→"},
    ]}
    cleaned = normalize_for_scenario("S2", raw)
    assert cleaned["key_trends"][0]["direction"] == "up"
    assert cleaned["key_trends"][1]["direction"] == "up"
    assert cleaned["key_trends"][2]["direction"] == "flat"


# ============ S3 ============

def test_s3_pricing_model_alias():
    raw = {"pricing_baseline": {"current_pricing_model": "按席位"}}
    cleaned = normalize_for_scenario("S3", raw)
    assert cleaned["pricing_baseline"]["current_pricing_model"] == "per_seat"


def test_s3_drops_pricing_page_audit_overall_score_pct():
    """overall_score_pct 是 computed_field"""
    raw = {"pricing_page_audit": [{"overall_score_pct": 88.8, "audit_scores": []}]}
    cleaned = normalize_for_scenario("S3", raw)
    assert "overall_score_pct" not in cleaned["pricing_page_audit"][0]


def test_s3_packaging_position_alias():
    raw = {"packaging": {"tiers": [
        {"position": "免费"},
        {"position": "best"},
        {"position": "高级版"},
    ]}}
    cleaned = normalize_for_scenario("S3", raw)
    assert cleaned["packaging"]["tiers"][0]["position"] == "free"
    assert cleaned["packaging"]["tiers"][1]["position"] == "best"
    assert cleaned["packaging"]["tiers"][2]["position"] == "best"


def test_s3_arr_uplift_basis_alias():
    raw = {"recommendations_summary": {"expected_arr_uplift_basis": "推断"}}
    cleaned = normalize_for_scenario("S3", raw)
    assert cleaned["recommendations_summary"]["expected_arr_uplift_basis"] == "llm_inferred"


# ============ S4 ============

def test_s4_drops_threat_quadrant_and_battlecard_last_updated():
    raw = {
        "threats": [{"quadrant": "act_now", "severity": "high", "likelihood": "high"}],
        "battlecards": [{"last_updated_at": "2026-06-07", "competitor_name": "A"}],
    }
    cleaned = normalize_for_scenario("S4", raw)
    assert "quadrant" not in cleaned["threats"][0]
    assert "last_updated_at" not in cleaned["battlecards"][0]


def test_s4_severity_likelihood_chinese():
    raw = {"threats": [{"severity": "高", "likelihood": "中"}]}
    cleaned = normalize_for_scenario("S4", raw)
    assert cleaned["threats"][0]["severity"] == "high"
    assert cleaned["threats"][0]["likelihood"] == "medium"


def test_s4_trends_direction_arrow():
    raw = {"trends": {"sentiment_trend": "↑", "pricing_trend": "下降", "release_velocity_trend": "→"}}
    cleaned = normalize_for_scenario("S4", raw)
    assert cleaned["trends"]["sentiment_trend"] == "up"
    assert cleaned["trends"]["pricing_trend"] == "down"
    assert cleaned["trends"]["release_velocity_trend"] == "flat"


def test_s4_first_review_baseline_inferred_when_no_prior():
    """没有 prior_trace_id 时所有 change 自动加 is_baseline=True（首次监控模式）"""
    raw = {
        "review_period": {"prior_trace_id": None},
        "feature_changes": [{"competitor_name": "A"}],
        "pricing_changes": [{"competitor_name": "A"}],
    }
    cleaned = normalize_for_scenario("S4", raw)
    assert cleaned["feature_changes"][0]["is_baseline"] is True
    assert cleaned["pricing_changes"][0]["is_baseline"] is True


# ============ S5 ============

def test_s5_drops_mq_quadrant_and_full_statement():
    raw = {
        "vendor_profiles": [{"mq_quadrant": "mq_leader", "ability_to_execute_score": 4}],
        "positioning_statement": {"full_statement_text": "已经填好的句子"},
    }
    cleaned = normalize_for_scenario("S5", raw)
    assert "mq_quadrant" not in cleaned["vendor_profiles"][0]
    assert "full_statement_text" not in cleaned["positioning_statement"]


def test_s5_focus_divergence_alias():
    raw = {"blue_ocean_move": {"focus_assessment": "聚焦", "divergence_assessment": "重叠"}}
    cleaned = normalize_for_scenario("S5", raw)
    assert cleaned["blue_ocean_move"]["focus_assessment"] == "focused"
    assert cleaned["blue_ocean_move"]["divergence_assessment"] == "overlapping"


def test_s5_positioning_confidence_alias():
    raw = {"positioning_statement": {"confidence": "用户提供"}}
    cleaned = normalize_for_scenario("S5", raw)
    assert cleaned["positioning_statement"]["confidence"] == "from_user_brief"


def test_s5_rename_errc_raise_to_raise_level():
    """常见 LLM 把 raise_level 写成 raise（Python 关键字陷阱）"""
    raw = {"errc_grid": {"raise": [{"factor": "易用性"}]}}
    cleaned = normalize_for_scenario("S5", raw)
    assert "raise" not in cleaned["errc_grid"]
    assert cleaned["errc_grid"]["raise_level"] == [{"factor": "易用性"}]
