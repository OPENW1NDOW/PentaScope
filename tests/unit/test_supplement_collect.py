import pytest
from unittest.mock import AsyncMock, MagicMock
from src.agents.collector import CollectorAgent
from src.schemas.input import CompetitorBasic
from src.schemas.feedback import FeedbackIssue
from src.schemas.profile import CompetitorProfile, BasicInfo, Classification, ProfileMetadata
from src.tools.sources import SourceResult


def _make_existing_profile(name: str, sources: list[str] | None = None) -> CompetitorProfile:
    return CompetitorProfile(
        classification=Classification(competitor_type="核心竞品", reason="test"),
        basic_info=BasicInfo(name=name, company=""),
        metadata=ProfileMetadata(
            collected_at="2026-06-20T00:00:00",
            data_sources=sources or [],
            completeness_score=0.5,
            pipeline_trace=[],
        ),
    )


@pytest.mark.asyncio
async def test_supplement_collect_generates_query_and_searches():
    """补采模式：LLM 生成 query → Tavily 搜索 → 返回新 profiles + sources。"""
    mock_llm = MagicMock()
    mock_llm.call_json = AsyncMock(return_value={
        "queries": ["GrowingIO 数据分析 产品评测", "友盟 SDK 功能 对比"]
    })

    mock_pipeline = MagicMock()
    mock_pipeline.search_source = MagicMock()
    mock_pipeline.search_source.available = MagicMock(return_value=True)
    mock_pipeline.search_source.search = AsyncMock(return_value=[
        SourceResult(url="https://new-source.com/review", title="New Review", text="新搜到的正文内容" * 20),
    ])

    agent = CollectorAgent(llm=mock_llm, pipeline=mock_pipeline)

    competitors = [CompetitorBasic(name="GrowingIO")]
    issues = [FeedbackIssue(
        agent="collector", field="key_findings[0].source_refs",
        severity="major", reason="缺来源", suggestion="补充",
        issue_type="url_not_discovered",
    )]

    existing_profile = _make_existing_profile("GrowingIO", sources=["https://old.com"])

    new_profiles, new_sources = await agent.supplement_collect(
        competitors=competitors,
        feedback_issues=issues,
        scenario="S4",
        existing_profiles=[existing_profile],
    )

    assert len(new_sources) >= 1
    assert new_sources[0]["url"] == "https://new-source.com/review"
    assert "https://new-source.com/review" in new_profiles[0].metadata.data_sources


@pytest.mark.asyncio
async def test_supplement_collect_no_results_returns_empty():
    """补采搜不到有效结果时返回空。"""
    mock_llm = MagicMock()
    mock_llm.call_json = AsyncMock(return_value={"queries": ["无效query"]})

    mock_pipeline = MagicMock()
    mock_pipeline.search_source = MagicMock()
    mock_pipeline.search_source.available = MagicMock(return_value=True)
    mock_pipeline.search_source.search = AsyncMock(return_value=[])

    agent = CollectorAgent(llm=mock_llm, pipeline=mock_pipeline)

    existing_profile = _make_existing_profile("XX")

    new_profiles, new_sources = await agent.supplement_collect(
        competitors=[CompetitorBasic(name="XX")],
        feedback_issues=[],
        scenario="S4",
        existing_profiles=[existing_profile],
    )

    assert new_sources == []
