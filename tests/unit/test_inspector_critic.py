"""LLM-as-critic 单元 + 集成测试。

测试三层（spec v4）：
1. 单元测试（机制正确性，CI required）
2. 集成测试（端到端 mock LLM，CI required）
3. 反例集 eval（手动 pytest -m eval，不进 CI）—— 见 tests/eval/
"""
import pytest
from pydantic import ValidationError


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
    from src.schemas.feedback import CriticScores

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
