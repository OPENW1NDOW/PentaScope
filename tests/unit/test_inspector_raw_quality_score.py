"""验证 inspector 在 cap 前后均正确写入 raw_quality_score 与 quality_score。

PD-3 KPI 显示用：raw_quality_score 保留 cap 前真实加权分；
quality_score 在 placeholder warnings 触发时被 cap 到 0.5。

复用 test_inspector_v3.py 的 SimpleNamespace mock 模式（避免造完整 BaseReport）。
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.inspector import InspectorAgent


def _ds_list(n=3):
    return [SimpleNamespace(confidence="high") for _ in range(n)]


def _section(sid="sec-1"):
    return SimpleNamespace(section_id=sid)


def _rec(priority="important"):
    return SimpleNamespace(priority=priority, action="test recommendation action")


def _make_clean_report(*, with_placeholder: bool):
    """构造满足 inspector 调用的最小 mock；可选附 placeholder warning。"""
    metadata = SimpleNamespace(
        data_sources=_ds_list(3),
        quality_score=None,
        raw_quality_score=None,
        quality_score_calculation_note="",
        warnings=["placeholder_section:feature_matrix_analysis"] if with_placeholder else [],
    )
    swot = SimpleNamespace(strengths=[], weaknesses=[], opportunities=[], threats=[])
    report = SimpleNamespace(
        scenario="S1",
        scenario_payload=SimpleNamespace(
            feature_matrix=SimpleNamespace(
                our_product_name="Us",
                competitors=["Us", "A"],
                categories=[
                    SimpleNamespace(
                        features=[SimpleNamespace(scores={"A": SimpleNamespace(score=2)})]
                    )
                ],
            ),
            vendor_profiles=[SimpleNamespace(competitor_name="A")],
            white_space_features=["x"],
            feature_gaps=["x"],
        ),
        analysis_sections=[_section()],
        at_a_glance=["足够长的洞察文本一" * 2, "足够长的洞察文本二" * 2, "足够长的洞察文本三" * 2],
        recommendations=[_rec("important")],
        key_findings=[SimpleNamespace(source_refs=["x"], statement="test finding statement")],
        executive_summary=SimpleNamespace(implications="test implications text"),
        swot=swot,
        metadata=metadata,
    )
    report.model_dump_json = MagicMock(return_value="{}")
    report.model_dump = MagicMock(return_value={
        "analysis_sections": [{"section_id": "s1", "narrative": "x" * 100}],
        "key_findings": [{"statement": "s", "evidence": "e", "implication": "i"}],
        "recommendations": [{"action": "a"}],
    })
    return report, metadata


@pytest.mark.asyncio
async def test_quality_score_set_by_critic():
    """v4：quality_score 由 critic 评分计算。"""
    report, metadata = _make_clean_report(with_placeholder=False)
    mock_llm = MagicMock()
    mock_llm.call_json = AsyncMock(return_value={
        "evidence": {"reasoning": [], "score": 3, "issues": []},
        "specificity": {"reasoning": [], "score": 3, "issues": []},
        "coherence": {"reasoning": [], "score": 3, "issues": []},
        "actionability": {"reasoning": [], "score": 3, "issues": []},
    })

    insp = InspectorAgent(llm=mock_llm)
    await insp.inspect(report)

    assert metadata.quality_score is not None
    assert 0.0 <= metadata.quality_score <= 1.0
    assert metadata.score_source == "critic"
    assert "capped" not in (metadata.quality_score_calculation_note or "")


@pytest.mark.asyncio
async def test_placeholder_warnings_no_longer_cap_quality_score():
    """v4：placeholder warnings 不再 cap quality_score。"""
    report, metadata = _make_clean_report(with_placeholder=True)
    mock_llm = MagicMock()
    mock_llm.call_json = AsyncMock(return_value={
        "evidence": {"reasoning": [], "score": 4, "issues": []},
        "specificity": {"reasoning": [], "score": 4, "issues": []},
        "coherence": {"reasoning": [], "score": 4, "issues": []},
        "actionability": {"reasoning": [], "score": 4, "issues": []},
    })

    insp = InspectorAgent(llm=mock_llm)
    await insp.inspect(report)

    # v4：全 4 分 → quality_score = 1.0，不被 cap
    assert metadata.quality_score == 1.0
    assert "capped" not in (metadata.quality_score_calculation_note or "")
