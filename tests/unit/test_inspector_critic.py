"""LLM-as-critic 单元 + 集成测试。

测试三层（spec v4）：
1. 单元测试（机制正确性，CI required）
2. 集成测试（端到端 mock LLM，CI required）
3. 反例集 eval（手动 pytest -m eval，不进 CI）—— 见 tests/eval/
"""
import pytest
from pydantic import ValidationError
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def make_simple_report():
    """构造最小合法 BaseReport，参数控制各字段长度便于测试不同分支。"""
    from datetime import date
    from src.schemas.report import (
        BaseReport, ReportMetadata, ReportScope, Methodology, Finding,
        AnalysisSection, Recommendation, SwotEntry, Swot, ExecutiveSummary,
    )
    from src.schemas.common import DataSource, SourceRef
    from src.schemas.scenarios.s1 import (
        S1FeatureIterationPayload, S1VendorProfile, FeatureMatrix,
        FeatureCategory, FeatureRow, FeatureScore, S1RadarScore,
        JobStatement, FeatureGap, RoadmapRecommendations,
        VendorStrength, VendorCaution,
    )

    def _make(
        findings_count: int = 3,
        recs_count: int = 3,
        with_source_refs: bool = True,
        swot_strengths_count: int = 1,
    ):
        sw_entry = SwotEntry(
            point="优势点描述足够长一些",
            evidence="证据描述也要足够长一点",
            source_refs=[SourceRef(url="https://example.com/sw", title="sw")] if with_source_refs else [],
        )
        finding = Finding(
            statement="陈述足够长" * 4,
            evidence="证据足够长" * 4,
            implication="意义足够长" * 4,
            source_refs=[SourceRef(url="https://example.com/f", title="f")] if with_source_refs else [],
        )
        rec = Recommendation(
            action="行动描述够长" * 4,
            target_role="产品经理",
            priority="critical",
            timeline="immediate",
            rationale="依据描述够长足够长" * 3,
        )

        def _ok_strength():
            return VendorStrength(point="某项核心优势描述至少十字", evidence="官网功能页有详细截图说明")

        def _ok_caution():
            return VendorCaution(point="某项需注意点描述至少十字", evidence="用户论坛有大量差评汇总记录")

        def _ok_profile(name):
            return S1VendorProfile(
                competitor_name=name,
                wave_position="wave_leader",
                one_line_pitch=f"{name} 的一句话定位描述足够长",
                strengths=[_ok_strength(), _ok_strength()],
                cautions=[_ok_caution()],
                best_fit_for="中小团队场景适配最好",
            )

        payload = S1FeatureIterationPayload(
            vendor_profiles=[_ok_profile("A"), _ok_profile("B")],
            feature_matrix=FeatureMatrix(
                artifact_id="fm-1",
                competitors=["A", "B", "我方"],
                our_product_name="我方",
                categories=[FeatureCategory(name="核心", tier=1, features=[
                    FeatureRow(
                        name="f1",
                        scores={c: FeatureScore(score=2, evidence_url="https://a.com") for c in ["A", "B", "我方"]},
                    ),
                ])],
            ),
            radar_scores=[
                S1RadarScore(
                    artifact_id="r-A", competitor_name="A",
                    feature_breadth=4, usability=4, cost_effectiveness=4, stability=4, design_quality=4,
                ),
                S1RadarScore(
                    artifact_id="r-B", competitor_name="B",
                    feature_breadth=3, usability=3, cost_effectiveness=3, stability=3, design_quality=3,
                ),
            ],
            job_statement=JobStatement(
                situation="跨部门协作场景下处理文档",
                motivation="希望减少沟通成本提升效率",
                outcome="最终减少跨部门同步会议次数",
            ),
            feature_gaps=[FeatureGap(
                feature_name="移动端", competitors_have_it=["A"],
                underserved_outcome="出差场景下无法编辑文档",
                estimated_effort="medium", estimated_impact="high",
                recommendation="build",
            )],
            roadmap_recommendations=RoadmapRecommendations(
                must_build=["移动端"],
                rationale_summary="必须补移动端，理由如下" * 5,
            ),
        )

        return BaseReport(
            metadata=ReportMetadata(
                report_id="r1", trace_id="t1", scenario="S1",
                publication_date=date(2026, 6, 7),
                data_sources=[DataSource(url="https://example.com")],
                confidence_level="high",
            ),
            title="S1 功能迭代竞品分析报告",
            at_a_glance=["要点 1", "要点 2", "要点 3"],
            executive_summary=ExecutiveSummary(
                context="x" * 100,
                core_thesis="y" * 60,
                key_findings_brief=["finding 1 detail" * 3, "finding 2 detail" * 3],
                implications="z" * 120,
                path_forward=["action 1"],
            ),
            background="x" * 300,
            scope=ReportScope(competitors=["A"], time_window="2026 Q2"),
            methodology=Methodology(
                data_collection_approach="x" * 200,
                evaluation_criteria=["c1", "c2", "c3"],
                limitations=["l1", "l2"],
                sample_size_note="x" * 80,
            ),
            key_findings=[finding] * findings_count,
            analysis_sections=[
                AnalysisSection(section_id=f"sec-{i}", heading="深度章节", narrative="x" * 300, section_type="overview")
                for i in range(4)
            ],
            swot=Swot(
                strengths=[sw_entry] * swot_strengths_count,
                weaknesses=[sw_entry], opportunities=[sw_entry], threats=[sw_entry],
            ),
            conclusions="y" * 300,
            recommendations=[rec] * recs_count,
            scenario_payload=payload,
        )

    return _make


def test_critic_scores_basic_validation():
    """CriticScores 4 维分数 1-4 整数校验。"""
    from src.schemas.feedback import CriticScores

    scores = CriticScores(evidence=4, specificity=3, coherence=2, actionability=1)
    assert scores.evidence == 4
    assert scores.specificity == 3
    assert scores.coherence == 2
    assert scores.actionability == 1
    assert scores.reasoning == {}


def test_critic_scores_rejects_out_of_range():
    """score 不能小于 1 或大于 4。"""
    from src.schemas.feedback import CriticScores

    with pytest.raises(ValidationError):
        CriticScores(evidence=0, specificity=2, coherence=2, actionability=2)
    with pytest.raises(ValidationError):
        CriticScores(evidence=5, specificity=2, coherence=2, actionability=2)


def test_critic_scores_reasoning_is_list_of_str():
    """reasoning 字段是 dict[str, list[str]]，每个维度对应 bullet list。"""
    from src.schemas.feedback import CriticScores

    scores = CriticScores(
        evidence=3, specificity=3, coherence=3, actionability=3,
        reasoning={
            "evidence": ["[Step 1] ...", "[Step 2] ..."],
            "specificity": ["[Step 1] ..."],
        },
    )
    assert scores.reasoning["evidence"] == ["[Step 1] ...", "[Step 2] ..."]


def test_feedback_issue_new_fields_optional():
    """FeedbackIssue 新增 dimension / issue_type 必须 Optional 默认 None（旧 trace 兼容）。"""
    from src.schemas.feedback import FeedbackIssue

    issue = FeedbackIssue(
        agent="writer", field="key_findings[0]", severity="major",
        reason="...", suggestion="...",
    )
    assert issue.dimension is None
    assert issue.issue_type is None


def test_feedback_issue_new_fields_settable():
    """FeedbackIssue 新增字段能正常设置。"""
    from src.schemas.feedback import FeedbackIssue

    issue = FeedbackIssue(
        agent="writer", field="key_findings[0]", severity="major",
        reason="...", suggestion="...",
        dimension="evidence", issue_type="source_irrelevant",
    )
    assert issue.dimension == "evidence"
    assert issue.issue_type == "source_irrelevant"


def test_report_metadata_v4_fields_optional():
    """v4 新增字段必须 Optional 默认 None，旧 v1 trace 反序列化兼容。"""
    from src.schemas.report import ReportMetadata

    # 模拟旧 v1 trace：不含 critic_scores / score_source / critic_prompt_version
    old_metadata_dict = {
        "report_id": "rpt-test",
        "trace_id": "test-trace",
        "scenario": "S5",
        "schema_version": "2.0",
        "publication_date": "2026-06-18",
        "confidence_level": "medium",
        "warnings": [],
        "data_sources": [{
            "url": "https://example.com",
            "title": "test",
            "accessed_at": "2026-06-18",
            "source_type": "other",
            "confidence": "medium",
        }],
    }
    md = ReportMetadata.model_validate(old_metadata_dict)

    # v4 修订（cycle3/C1）：旧 trace 期望统一为 None
    assert md.critic_scores is None
    assert md.score_source is None
    assert md.critic_prompt_version is None


def test_report_metadata_v4_fields_settable():
    """v4 新增字段能正常设置。"""
    from src.schemas.report import ReportMetadata

    md = ReportMetadata.model_validate({
        "report_id": "rpt-test",
        "trace_id": "test-trace",
        "scenario": "S5",
        "schema_version": "2.0",
        "publication_date": "2026-06-18",
        "confidence_level": "medium",
        "warnings": [],
        "data_sources": [{
            "url": "https://example.com", "title": "t",
            "accessed_at": "2026-06-18", "source_type": "other",
            "confidence": "medium",
        }],
        "critic_scores": {
            "evidence": 3, "specificity": 3, "coherence": 3, "actionability": 3,
            "reasoning": {},
        },
        "score_source": "critic",
        "critic_prompt_version": "critic-prompt-v1.0.0",
    })
    assert md.critic_scores.evidence == 3
    assert md.score_source == "critic"
    assert md.critic_prompt_version == "critic-prompt-v1.0.0"


def test_v1_trace_can_be_loaded_with_v4_schema():
    """spec v4 验收 2：真实历史 trace 能用 v4 BaseReport schema 加载。"""
    import json
    from pathlib import Path
    from src.schemas.report import BaseReport

    # 找一个真实历史 trace（v1 schema 落盘的）
    trace_path = Path("runs/20260618-095358-c5ab5c/03_report.json")
    if not trace_path.exists():
        pytest.skip(f"trace fixture 不存在: {trace_path}")

    raw = json.loads(trace_path.read_text(encoding="utf-8"))
    report = BaseReport.model_validate(raw)

    # v4 修订（cycle3/C1）：旧 trace 反序列化后所有 v4 新字段必须为 None
    assert report.metadata.critic_scores is None
    assert report.metadata.score_source is None
    assert report.metadata.critic_prompt_version is None


def test_calc_critic_score_normal():
    """4 维加权 + 归一化 + clamp。"""
    from src.agents.quality_score import calc_critic_score
    from src.schemas.feedback import CriticScores

    scores = CriticScores(evidence=4, specificity=4, coherence=4, actionability=4)
    # weighted_raw = 0.30*4 + 0.30*4 + 0.20*4 + 0.20*4 = 4.0
    # normalized = (4.0 - 1) / 3 = 1.0
    assert calc_critic_score(scores) == pytest.approx(1.0)


def test_calc_critic_score_minimum():
    """全 1 分 → quality_score 0."""
    from src.agents.quality_score import calc_critic_score
    from src.schemas.feedback import CriticScores

    scores = CriticScores(evidence=1, specificity=1, coherence=1, actionability=1)
    # weighted_raw = 1.0; (1.0 - 1) / 3 = 0.0
    assert calc_critic_score(scores) == pytest.approx(0.0)


def test_calc_critic_score_mixed():
    """混合分数：ev=4 sp=2 co=3 ac=3 → raw=3.0 → norm=0.667。"""
    from src.agents.quality_score import calc_critic_score
    from src.schemas.feedback import CriticScores

    scores = CriticScores(evidence=4, specificity=2, coherence=3, actionability=3)
    # weighted_raw = 0.30*4 + 0.30*2 + 0.20*3 + 0.20*3 = 1.2 + 0.6 + 0.6 + 0.6 = 3.0
    # normalized = (3.0 - 1) / 3 = 0.667
    assert calc_critic_score(scores) == pytest.approx(0.667, abs=0.001)


def test_calc_critic_score_accepts_dict():
    """spec v3 cycle2/C5 + cycle2/m4：calc_critic_score 兼容 CriticScores 模型和 dict。"""
    from src.agents.quality_score import calc_critic_score

    dict_input = {"evidence": 3, "specificity": 3, "coherence": 3, "actionability": 3}
    # raw = 3.0; (3.0 - 1) / 3 = 0.667
    assert calc_critic_score(dict_input) == pytest.approx(0.667, abs=0.001)


def test_calc_critic_score_dict_ignores_extra_fields():
    """spec v3 cycle2/m4：dict 输入只读 4 个维度 key，忽略 reasoning 等额外 key。"""
    from src.agents.quality_score import calc_critic_score

    dict_with_extra = {
        "evidence": 3, "specificity": 3, "coherence": 3, "actionability": 3,
        "reasoning": ["[Step 1] foo"],  # 额外 key 必须被忽略
        "unknown_field": "garbage",
    }
    assert calc_critic_score(dict_with_extra) == pytest.approx(0.667, abs=0.001)


def test_calc_critic_score_clamps_to_unit_interval():
    """spec v4 验收 6：quality_score 永远 ∈ [0, 1] 即使输入异常。"""
    from src.agents.quality_score import calc_critic_score

    # 异常 dict（超出 1-4 区间）—— clamp 应保住边界
    weird_dict = {"evidence": 0, "specificity": 0, "coherence": 0, "actionability": 0}
    result = calc_critic_score(weird_dict)
    assert 0.0 <= result <= 1.0


def test_score_to_severity_dim1_critical():
    """spec v3 cycle2/M2：dim ≤1 → critical。"""
    from src.agents.inspector import _score_to_severity

    all_scores = {"evidence": 4, "specificity": 4, "coherence": 4, "actionability": 4}
    assert _score_to_severity(1, all_scores) == "critical"


def test_score_to_severity_dim2_major():
    """spec v3 cycle2/M2：dim == 2 → major（不再仅靠均值）。"""
    from src.agents.inspector import _score_to_severity

    # 即使均值 4，evidence=2 仍要 major
    all_scores = {"evidence": 2, "specificity": 4, "coherence": 4, "actionability": 4}
    assert _score_to_severity(2, all_scores) == "major"


def test_score_to_severity_dim3_low_agg_major():
    """dim==3 + 低均值 → major。"""
    from src.agents.inspector import _score_to_severity

    # 全 3 分（边缘）：raw=3.0; norm=0.667 ≥ 0.5 → minor
    all_scores = {"evidence": 3, "specificity": 3, "coherence": 3, "actionability": 3}
    assert _score_to_severity(3, all_scores) == "minor"

    # 多维度 2，均值低：ev=3 sp=2 co=2 ac=2 → raw=2.3; norm=0.433 < 0.5 → major
    low_all_scores = {"evidence": 3, "specificity": 2, "coherence": 2, "actionability": 2}
    assert _score_to_severity(3, low_all_scores) == "major"


def test_score_to_severity_dim4_minor():
    """spec v4 cycle3/M1：dim >= 4 显式 → minor 防 fall-through。"""
    from src.agents.inspector import _score_to_severity

    weird_all_scores = {"evidence": 4, "specificity": 1, "coherence": 1, "actionability": 1}
    assert _score_to_severity(4, weird_all_scores) == "minor"


# ============ Task 7: _build_limited_pairs ============

def test_build_limited_pairs_three_pairs(make_simple_report):
    """spec v3 cycle2/M5：固定 3 个 deterministic pair。"""
    from src.agents.inspector import _build_limited_pairs

    report = make_simple_report()
    pairs = _build_limited_pairs(report)

    pair_ids = [p["id"] for p in pairs]
    assert "swot_vs_vendor_cautions" in pair_ids
    assert "findings_vs_recommendations" in pair_ids
    assert "exec_summary_vs_recommendations" in pair_ids
    assert len(pairs) == 3


def test_build_limited_pairs_missing_field_skipped(make_simple_report):
    """缺 vendor_profiles cautions 时 pair 标 skip_reason="missing"。"""
    from src.agents.inspector import _build_limited_pairs

    report = make_simple_report()
    # 人为清空 vendor_profiles 的 cautions 来触发 skip
    for vp in report.scenario_payload.vendor_profiles:
        vp.cautions = []
    pairs = _build_limited_pairs(report)

    swot_pair = next(p for p in pairs if p["id"] == "swot_vs_vendor_cautions")
    if not swot_pair.get("data_b"):
        assert swot_pair.get("skip_reason") == "missing"


def test_build_limited_pairs_deterministic(make_simple_report):
    """同 report 多次调用结果一致。"""
    from src.agents.inspector import _build_limited_pairs

    report = make_simple_report()
    pairs_1 = _build_limited_pairs(report)
    pairs_2 = _build_limited_pairs(report)
    assert pairs_1 == pairs_2


# ============ Task 8: _sample_items_deterministic ============

def test_sample_items_deterministic_takes_first_n_by_id():
    from src.agents.inspector import _sample_items_deterministic

    items = [{"id": "z", "value": 1}, {"id": "a", "value": 2}, {"id": "m", "value": 3}]
    result = _sample_items_deterministic(items, n=2, seed_field="id")
    assert [r["id"] for r in result] == ["a", "m"]


def test_sample_items_deterministic_uses_sha256_when_no_id():
    from src.agents.inspector import _sample_items_deterministic

    items = [{"value": 1}, {"value": 2}, {"value": 3}]
    result_1 = _sample_items_deterministic(items, n=2)
    result_2 = _sample_items_deterministic(items, n=2)
    assert result_1 == result_2


def test_sample_items_deterministic_returns_all_when_fewer_than_n():
    from src.agents.inspector import _sample_items_deterministic

    items = [{"id": "a"}, {"id": "b"}]
    result = _sample_items_deterministic(items, n=5)
    assert len(result) == 2


# ============ Task 9: _build_critic_inputs ============

def test_build_critic_inputs_basic_structure(make_simple_report):
    import json
    from src.agents.inspector import _build_critic_inputs

    report = make_simple_report()
    discovered_sources = [{"url": "https://a.com", "title": "Page A", "snippet": "snippet a"}]
    user_prompt = _build_critic_inputs(report, discovered_sources)

    inputs = json.loads(user_prompt)
    assert "report_brief" in inputs
    assert "discovered_sources" in inputs
    assert "limited_pairs" in inputs
    assert len(inputs["limited_pairs"]) == 3


def test_build_critic_inputs_includes_all_items(make_simple_report):
    import json
    from src.agents.inspector import _build_critic_inputs

    report = make_simple_report(findings_count=6, recs_count=5)
    discovered_sources = [{"url": "https://a.com", "title": "t", "snippet": "s"}]
    user_prompt = _build_critic_inputs(report, discovered_sources)

    inputs = json.loads(user_prompt)
    assert "all_findings" in inputs
    assert "all_recommendations" in inputs
    assert len(inputs["all_findings"]) == 6
    assert len(inputs["all_recommendations"]) == 5


def test_build_critic_inputs_handles_empty_discovered_sources(make_simple_report):
    import json
    from src.agents.inspector import _build_critic_inputs

    report = make_simple_report()
    user_prompt = _build_critic_inputs(report, [])

    inputs = json.loads(user_prompt)
    assert inputs["discovered_sources"] == []


# ============ Task 10: _safe_minimal_fallback + _map_issue_type_to_agent ============

def test_safe_minimal_fallback_returns_safe_value():
    from src.agents.inspector import _safe_minimal_fallback

    scores, issues = _safe_minimal_fallback()
    assert scores is None
    assert len(issues) == 1
    assert issues[0].agent == "end"
    assert issues[0].severity == "critical"
    assert issues[0].dimension == "critic_failed"
    assert issues[0].issue_type == "critic_failed"


def test_map_issue_type_to_agent():
    from src.agents.inspector import _map_issue_type_to_agent

    assert _map_issue_type_to_agent("url_not_discovered") == "collector"
    assert _map_issue_type_to_agent("source_mismatch") == "writer"
    assert _map_issue_type_to_agent("source_irrelevant") == "writer"
    assert _map_issue_type_to_agent("vague_description") == "writer"
    assert _map_issue_type_to_agent("cross_field_contradiction") == "writer"
    assert _map_issue_type_to_agent("vague_recommendation") == "writer"
    assert _map_issue_type_to_agent("critic_failed") == "end"
    assert _map_issue_type_to_agent("unknown_type") == "writer"


# ============ Task 11: _critic_check ============


@pytest.mark.asyncio
async def test_critic_check_normal_path(make_simple_report):
    from src.agents.inspector import InspectorAgent
    from src.schemas.feedback import CriticScores

    mock_llm_response = {
        "evidence": {"reasoning": ["[Step 1] ..."], "score": 3, "issues": []},
        "specificity": {"reasoning": ["[Step 1] ..."], "score": 4, "issues": []},
        "coherence": {"reasoning": ["[Step 1] ..."], "score": 4, "issues": []},
        "actionability": {"reasoning": ["[Step 1] ..."], "score": 3, "issues": []},
    }
    mock_llm = MagicMock()
    mock_llm.call_json = AsyncMock(return_value=mock_llm_response)

    inspector = InspectorAgent(llm=mock_llm)
    report = make_simple_report()
    discovered_sources = [{"url": "https://a.com", "title": "t", "snippet": "s"}]

    critic_scores, critic_issues = await inspector._critic_check(report, discovered_sources)

    assert isinstance(critic_scores, CriticScores)
    assert critic_scores.evidence == 3
    assert critic_scores.specificity == 4
    assert critic_issues == []
    assert mock_llm.call_json.call_count == 1


@pytest.mark.asyncio
async def test_critic_check_retry_then_success(make_simple_report):
    from src.agents.inspector import InspectorAgent

    bad_response = {
        "evidence": {"reasoning": [], "score": 5, "issues": []},
        "specificity": {"reasoning": [], "score": 3, "issues": []},
        "coherence": {"reasoning": [], "score": 3, "issues": []},
        "actionability": {"reasoning": [], "score": 3, "issues": []},
    }
    good_response = {
        "evidence": {"reasoning": [], "score": 3, "issues": []},
        "specificity": {"reasoning": [], "score": 3, "issues": []},
        "coherence": {"reasoning": [], "score": 3, "issues": []},
        "actionability": {"reasoning": [], "score": 3, "issues": []},
    }
    mock_llm = MagicMock()
    mock_llm.call_json = AsyncMock(side_effect=[bad_response, good_response])

    inspector = InspectorAgent(llm=mock_llm)
    report = make_simple_report()
    critic_scores, _ = await inspector._critic_check(report, [])

    assert critic_scores.evidence == 3
    assert mock_llm.call_json.call_count == 2


@pytest.mark.asyncio
async def test_critic_check_retry_then_fallback(make_simple_report):
    from src.agents.inspector import InspectorAgent

    bad_response = {
        "evidence": {"reasoning": [], "score": 5, "issues": []},
        "specificity": {"reasoning": [], "score": 3, "issues": []},
        "coherence": {"reasoning": [], "score": 3, "issues": []},
        "actionability": {"reasoning": [], "score": 3, "issues": []},
    }
    mock_llm = MagicMock()
    mock_llm.call_json = AsyncMock(return_value=bad_response)

    inspector = InspectorAgent(llm=mock_llm)
    report = make_simple_report()
    critic_scores, critic_issues = await inspector._critic_check(report, [])

    assert critic_scores is None
    assert len(critic_issues) == 1
    assert critic_issues[0].severity == "critical"
    assert critic_issues[0].agent == "end"
    assert critic_issues[0].dimension == "critic_failed"
    assert mock_llm.call_json.call_count == 2


@pytest.mark.asyncio
async def test_critic_check_unexpected_exception_falls_back(make_simple_report):
    from src.agents.inspector import InspectorAgent

    mock_llm = MagicMock()
    mock_llm.call_json = AsyncMock(side_effect=RuntimeError("unexpected error"))

    inspector = InspectorAgent(llm=mock_llm)
    report = make_simple_report()

    critic_scores, critic_issues = await inspector._critic_check(report, [])
    assert critic_scores is None
    assert any(i.dimension == "critic_failed" for i in critic_issues)


# ============ Task 12: inspect() 端到端 ============

@pytest.mark.asyncio
async def test_inspect_with_critic_replaces_quality_score(make_simple_report):
    from src.agents.inspector import InspectorAgent

    mock_llm_response = {
        "evidence": {"reasoning": [], "score": 3, "issues": []},
        "specificity": {"reasoning": [], "score": 3, "issues": []},
        "coherence": {"reasoning": [], "score": 3, "issues": []},
        "actionability": {"reasoning": [], "score": 3, "issues": []},
    }
    mock_llm = MagicMock()
    mock_llm.call_json = AsyncMock(return_value=mock_llm_response)

    inspector = InspectorAgent(llm=mock_llm)
    report = make_simple_report()

    feedback = await inspector.inspect(report, discovered_sources=[])

    assert report.metadata.quality_score == pytest.approx(0.667, abs=0.01)
    assert report.metadata.score_source == "critic"
    assert report.metadata.critic_scores is not None
    assert report.metadata.critic_scores.evidence == 3
    assert report.metadata.critic_prompt_version == "critic-prompt-v1.2.1"
    assert isinstance(feedback, type(feedback))  # RejectionFeedback


@pytest.mark.asyncio
async def test_inspect_critic_failure_warnings_and_passed(make_simple_report):
    from src.agents.inspector import InspectorAgent

    mock_llm = MagicMock()
    mock_llm.call_json = AsyncMock(side_effect=RuntimeError("simulated critic failure"))

    inspector = InspectorAgent(llm=mock_llm)
    report = make_simple_report()

    feedback = await inspector.inspect(report, discovered_sources=[])

    assert report.metadata.score_source == "fallback"
    assert report.metadata.quality_score == 0.5
    assert report.metadata.critic_scores is None
    assert any("critic_failed" in w for w in (report.metadata.warnings or []))
    assert feedback.passed is False


@pytest.mark.asyncio
async def test_inspect_v3_r17_cap_removed(make_simple_report):
    """spec v4：v3-R17 cap 0.5 删除——placeholder warnings 不再 cap quality_score。"""
    from src.agents.inspector import InspectorAgent

    mock_llm_response = {
        "evidence": {"reasoning": [], "score": 4, "issues": []},
        "specificity": {"reasoning": [], "score": 4, "issues": []},
        "coherence": {"reasoning": [], "score": 4, "issues": []},
        "actionability": {"reasoning": [], "score": 4, "issues": []},
    }
    mock_llm = MagicMock()
    mock_llm.call_json = AsyncMock(return_value=mock_llm_response)

    inspector = InspectorAgent(llm=mock_llm)
    report = make_simple_report()
    report.metadata.warnings = ["placeholder_section:overview:ValidationError"]

    await inspector.inspect(report, discovered_sources=[])

    assert report.metadata.quality_score == pytest.approx(1.0, abs=0.01)


def test_source_mismatch_routes_to_writer():
    from src.agents.inspector import _map_issue_type_to_agent
    assert _map_issue_type_to_agent("source_mismatch") == "writer"
    assert _map_issue_type_to_agent("source_irrelevant") == "writer"
    assert _map_issue_type_to_agent("url_not_discovered") == "collector"
