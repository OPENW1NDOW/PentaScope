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
    """没有 prior_trace_id 时所有 change 自动加 is_baseline=True（首次监控模式）。

    [v3-R14] 修订后：必须给 changes 提供有效 source_refs，否则会被 normalizer 删除。
    """
    valid_ref = [{"url": "https://example.com/a"}]
    raw = {
        "review_period": {"prior_trace_id": None},
        "feature_changes": [{"competitor_name": "A", "source_refs": valid_ref}],
        "pricing_changes": [{"competitor_name": "A", "source_refs": valid_ref}],
    }
    cleaned = normalize_for_scenario("S4", raw)
    assert cleaned["feature_changes"][0]["is_baseline"] is True
    assert cleaned["pricing_changes"][0]["is_baseline"] is True


def test_s4_drops_changes_without_source_refs():
    """[v3-R14] 无 source_refs 的 changes 被 normalizer 删除"""
    valid_ref = [{"url": "https://example.com/a"}]
    raw = {
        "review_period": {"prior_trace_id": None},
        "feature_changes": [
            {"competitor_name": "A", "source_refs": valid_ref},  # 保留
            {"competitor_name": "B", "source_refs": []},  # 删
            {"competitor_name": "C"},  # 删（缺字段）
        ],
        "pricing_changes": [{"competitor_name": "A", "source_refs": [{"url": ""}]}],  # 删（url 空）
    }
    warnings = []
    cleaned = normalize_for_scenario("S4", raw, warnings=warnings)
    assert len(cleaned["feature_changes"]) == 1
    assert cleaned["feature_changes"][0]["competitor_name"] == "A"
    assert len(cleaned["pricing_changes"]) == 0
    assert any("dropped_unverified_entries:s4.feature_changes:2" in w for w in warnings)
    assert any("dropped_unverified_entries:s4.pricing_changes:1" in w for w in warnings)


def test_s3_drops_observed_tier_without_source_refs():
    """[v3-R14] 无 source_refs 的 ObservedCompetitorTier 被删；连带 CompetitorPricing 也清"""
    valid_ref = [{"url": "https://x.com/p"}]
    raw = {
        "competitive_pricing_matrix": [
            {
                "competitor_name": "A",
                "source_refs": valid_ref,
                "tiers": [
                    {"name": "pro", "source_refs": valid_ref},  # 保
                    {"name": "free", "source_refs": []},  # 删
                ],
            },
            {
                "competitor_name": "B",
                "source_refs": [],  # 整条删（自身无 source_refs）
                "tiers": [{"name": "free", "source_refs": valid_ref}],
            },
        ],
    }
    warnings = []
    cleaned = normalize_for_scenario("S3", raw, warnings=warnings)
    assert len(cleaned["competitive_pricing_matrix"]) == 1
    assert cleaned["competitive_pricing_matrix"][0]["competitor_name"] == "A"
    assert len(cleaned["competitive_pricing_matrix"][0]["tiers"]) == 1
    assert any("dropped_unverified_entries:s3" in w for w in warnings)


def test_s3_wtp_proxy_forces_low_confidence():
    """[v3-R15] WTP method=proxy_from_competitor_pricing 时 normalizer 强制 confidence=low"""
    raw = {
        "wtp_research": {
            "method": "proxy_from_competitor_pricing",
            "confidence": "high",  # LLM 错误填 high
            "rationale": "x" * 30,
            "limitations": "",
        }
    }
    cleaned = normalize_for_scenario("S3", raw)
    assert cleaned["wtp_research"]["confidence"] == "low"
    # limitations 兜底自动补
    assert cleaned["wtp_research"]["limitations"]


def test_s1_score_2_with_invalid_evidence_url_demoted():
    """[v3-R14] FeatureScore.score=2 但 evidence_url 不在 discovered_urls 时降为 score=1"""
    discovered = {"https://valid.com/a", "https://valid.com/b"}
    raw = {
        "feature_matrix": {
            "categories": [
                {
                    "name": "core",
                    "tier": 1,
                    "features": [
                        {
                            "name": "f1",
                            "scores": {
                                "compA": {"score": 2, "evidence_url": "https://valid.com/a"},  # 保留 score=2
                                "compB": {"score": 2, "evidence_url": "https://hallucinated.com/x"},  # 降 score=1
                                "compC": {"score": 0, "evidence_url": "https://hallucinated.com/y", "source_missing_reason": "未找到"},  # 清非法 url，保 score=0
                            },
                        }
                    ],
                }
            ]
        }
    }
    cleaned = normalize_for_scenario("S1", raw, discovered_urls=discovered)
    scores = cleaned["feature_matrix"]["categories"][0]["features"][0]["scores"]
    assert scores["compA"]["score"] == 2
    assert scores["compA"]["evidence_url"] == "https://valid.com/a"
    assert scores["compB"]["score"] == 1
    assert scores["compB"]["evidence_url"] is None
    assert scores["compB"]["source_missing_reason"]  # 已自动补
    assert scores["compC"]["score"] == 0
    assert scores["compC"]["evidence_url"] is None
    assert scores["compC"]["source_missing_reason"] == "未找到"  # 保留原始 reason


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


# ============ [fix20 prove-it] S5 vendor_profiles / perceptual_map / category_strategy 兜底 ============

def test_s5_vendor_strengths_padded_when_under_two():
    """[fix20] vendor_profiles[*].strengths 少于 2 条时，复制最后一条凑齐 2 条（schema 要求 ≥2）"""
    raw = {
        "vendor_profiles": [
            {"competitor_name": "A", "strengths": [
                {"point": "唯一一条优势内容", "evidence": "证据内容至少十字符", "source_refs": []}
            ]},
        ]
    }
    cleaned = normalize_for_scenario("S5", raw)
    assert len(cleaned["vendor_profiles"][0]["strengths"]) >= 2


def test_s5_vendor_strengths_kept_when_already_two_or_more():
    """[fix20] strengths 已经 ≥2 条时不应改动"""
    raw = {
        "vendor_profiles": [
            {"competitor_name": "A", "strengths": [
                {"point": "第一条优势内容", "evidence": "证据 1 内容十字符", "source_refs": []},
                {"point": "第二条优势内容", "evidence": "证据 2 内容十字符", "source_refs": []},
                {"point": "第三条优势内容", "evidence": "证据 3 内容十字符", "source_refs": []},
            ]},
        ]
    }
    cleaned = normalize_for_scenario("S5", raw)
    assert len(cleaned["vendor_profiles"][0]["strengths"]) == 3


def test_s5_perceptual_axis_short_label_padded():
    """[fix20] perceptual_map.x_axis/y_axis 的 low_label/high_label 单字时自动补字（schema ≥2 字符）"""
    raw = {
        "perceptual_map": {
            "x_axis": {"low_label": "低", "high_label": "高"},
            "y_axis": {"low_label": "弱", "high_label": "强"},
        }
    }
    cleaned = normalize_for_scenario("S5", raw)
    pm = cleaned["perceptual_map"]
    assert len(pm["x_axis"]["low_label"]) >= 2
    assert len(pm["x_axis"]["high_label"]) >= 2
    assert len(pm["y_axis"]["low_label"]) >= 2
    assert len(pm["y_axis"]["high_label"]) >= 2


def test_s5_perceptual_axis_two_char_label_kept():
    """[fix20] 已经 ≥2 字的 label 不应被改"""
    raw = {
        "perceptual_map": {
            "x_axis": {"low_label": "低端", "high_label": "高端"},
        }
    }
    cleaned = normalize_for_scenario("S5", raw)
    assert cleaned["perceptual_map"]["x_axis"]["low_label"] == "低端"
    assert cleaned["perceptual_map"]["x_axis"]["high_label"] == "高端"


def test_s5_category_strategy_empty_dict_filled_with_placeholders():
    """[fix20] category_strategy 是空 dict / 缺子字段时，自动用占位填齐（让 schema 通过）"""
    raw = {"category_strategy": {}}
    cleaned = normalize_for_scenario("S5", raw)
    cs = cleaned["category_strategy"]
    assert cs.get("chosen_category") and len(cs["chosen_category"]) >= 4
    assert cs.get("why_this_category") and len(cs["why_this_category"]) >= 30
    assert isinstance(cs.get("competitors_implied"), list) and len(cs["competitors_implied"]) >= 1


def test_s5_category_strategy_existing_fields_kept():
    """[fix20] category_strategy 已填的字段不应被覆盖"""
    raw = {
        "category_strategy": {
            "chosen_category": "AI 设计协作工具",
            "why_this_category": "我方原因长度足够超过三十字符的真实理由说明真",
            "competitors_implied": ["Sketch", "Adobe XD"],
        }
    }
    cleaned = normalize_for_scenario("S5", raw)
    assert cleaned["category_strategy"]["chosen_category"] == "AI 设计协作工具"
    assert cleaned["category_strategy"]["competitors_implied"] == ["Sketch", "Adobe XD"]
