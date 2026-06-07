import pytest
from pydantic import ValidationError
from src.schemas.scenarios.s1 import (
    S1FeatureIterationPayload, S1VendorProfile, FeatureMatrix, FeatureCategory,
    FeatureRow, FeatureScore, S1RadarScore, JobStatement,
    FeatureGap, RoadmapRecommendations, VendorStrength, VendorCaution,
)


def _ok_strength():
    return VendorStrength(
        point="某项核心优势描述至少十字",
        evidence="官网功能页有详细的截图说明",
    )


def _ok_caution():
    return VendorCaution(
        point="某项需注意点描述至少十字",
        evidence="用户论坛有大量差评汇总记录",
    )


def _ok_profile(name: str, wave="wave_leader"):
    return S1VendorProfile(
        competitor_name=name,
        wave_position=wave,
        one_line_pitch=f"{name} 的一句话定位描述足够长",
        strengths=[_ok_strength(), _ok_strength()],
        cautions=[_ok_caution()],
        best_fit_for="中小团队场景适配最好",
    )


def _ok_radar(name: str):
    return S1RadarScore(
        artifact_id=f"r-{name}",
        competitor_name=name,
        feature_breadth=4, usability=4, cost_effectiveness=4, stability=4, design_quality=4,
    )


def _ok_matrix(competitors=("A", "B", "我方")):
    return FeatureMatrix(
        artifact_id="s1-fm",
        competitors=list(competitors),
        our_product_name="我方",
        categories=[FeatureCategory(name="核心", tier=1, features=[
            FeatureRow(
                name="f1",
                scores={c: FeatureScore(score=2, evidence_url="https://a.com") for c in competitors},
            )
        ])],
    )


def _ok_job_statement():
    return JobStatement(
        situation="跨部门协作场景下处理文档",
        motivation="希望减少沟通成本提升效率",
        outcome="最终减少跨部门同步会议次数",
    )


def _ok_gap():
    return FeatureGap(
        feature_name="移动端",
        competitors_have_it=["A"],
        underserved_outcome="出差场景下无法编辑文档",
        estimated_effort="medium",
        estimated_impact="high",
        recommendation="build",
    )


def _ok_roadmap():
    return RoadmapRecommendations(
        must_build=["移动端"],
        rationale_summary="必须补移动端，理由如下" * 5,
    )


def test_feature_score_score_2_requires_evidence_url():
    """score=2 必须有 evidence_url"""
    with pytest.raises(ValidationError):
        FeatureScore(score=2)
    fs = FeatureScore(score=2, evidence_url="https://example.com")
    assert fs.score == 2


def test_feature_score_score_0_requires_url_or_reason():
    with pytest.raises(ValidationError):
        FeatureScore(score=0)
    fs = FeatureScore(score=0, source_missing_reason="未在公开页发现")
    assert fs.score == 0


def test_feature_category_weight_computed():
    """weight 由 tier 自动派生（tier 1=3, 2=2, 3=1）"""
    fc = FeatureCategory(
        name="协作",
        tier=1,
        features=[FeatureRow(name="实时协作", scores={"A": FeatureScore(score=2, evidence_url="https://a.com")})],
    )
    assert fc.weight == 3
    fc2 = FeatureCategory(
        name="次要",
        tier=3,
        features=[FeatureRow(name="ff", scores={"A": FeatureScore(score=1)})],
    )
    assert fc2.weight == 1


def test_feature_matrix_weighted_scores_computed():
    """weighted_scores 由代码计算"""
    fm = FeatureMatrix(
        artifact_id="s1-fm",
        competitors=["A", "我方"],
        our_product_name="我方",
        categories=[
            FeatureCategory(
                name="核心",
                tier=1,
                features=[
                    FeatureRow(
                        name="F1",
                        scores={
                            "A": FeatureScore(score=2, evidence_url="https://a.com"),
                            "我方": FeatureScore(score=1, source_missing_reason="部分支持"),
                        },
                    ),
                ],
            ),
        ],
    )
    assert fm.weighted_scores["A"] == 100.0
    assert fm.weighted_scores["我方"] == 50.0


def test_s1_payload_constructs_normally():
    """正常构造 S1 payload，所有竞品名一致"""
    payload = S1FeatureIterationPayload(
        vendor_profiles=[_ok_profile("A"), _ok_profile("B", wave="wave_contender")],
        feature_matrix=_ok_matrix(),
        radar_scores=[_ok_radar("A"), _ok_radar("B")],
        job_statement=_ok_job_statement(),
        feature_gaps=[_ok_gap()],
        roadmap_recommendations=_ok_roadmap(),
    )
    assert payload.scenario_type == "S1"
    assert len(payload.vendor_profiles) == 2


def test_s1_competitor_consistency_validator_rejects_mismatch():
    """vendor_profiles 中竞品名不在 feature_matrix.competitors 时应拒"""
    fm = _ok_matrix(competitors=("A", "B", "我方"))
    bad_profile = _ok_profile("X", wave="wave_contender")  # X 不在 matrix
    with pytest.raises(ValidationError, match="不在 feature_matrix"):
        S1FeatureIterationPayload(
            vendor_profiles=[_ok_profile("A"), bad_profile],
            feature_matrix=fm,
            radar_scores=[_ok_radar("A"), _ok_radar("B")],
            job_statement=_ok_job_statement(),
            feature_gaps=[_ok_gap()],
            roadmap_recommendations=_ok_roadmap(),
        )
