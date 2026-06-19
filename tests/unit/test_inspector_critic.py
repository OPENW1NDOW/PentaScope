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
