import pytest
from unittest.mock import AsyncMock, MagicMock
from src.schemas.analysis import CompetitiveAnalysis
from src.agents.analyzer import AnalyzerAgent


class TestAnalyzerAgent:
    @pytest.mark.asyncio
    async def test_analyze_returns_competitive_analysis(self, sample_competitor_profile, sample_competitive_analysis):
        mock_llm = MagicMock()
        mock_llm.call_json = AsyncMock(return_value=sample_competitive_analysis)

        agent = AnalyzerAgent(llm=mock_llm)
        from src.schemas.profile import CompetitorProfile
        profiles = [CompetitorProfile(**sample_competitor_profile)]

        result = await agent.analyze(profiles)
        assert isinstance(result, CompetitiveAnalysis)
        assert len(result.feature_matrix) == 1
        assert len(result.radar_scores) == 1


def test_backfill_dimension_source_urls_from_profiles():
    from src.agents.analyzer import AnalyzerAgent
    from src.schemas.profile import (
        CompetitorProfile, Classification, BasicInfo, ProfileMetadata,
        FeatureTree, Feature, Pricing,
    )
    profile = CompetitorProfile(
        classification=Classification(competitor_type="核心竞品", reason="r"),
        basic_info=BasicInfo(name="X"),
        feature_tree=[FeatureTree(module="M", features=[
            Feature(name="f", source_url="https://a.com")])],
        pricing=Pricing(model="免费", source_url="https://b.com"),
        metadata=ProfileMetadata(collected_at="t", data_sources=["https://a.com", "https://b.com"]),
    )
    result = {
        "positioning": {"per_competitor": [], "source_urls": []},
        "feature_matrix": [],
        "business_model": {"per_competitor": [], "source_urls": []},
        "operations": {"per_competitor": [], "source_urls": []},
        "user_sentiment": {"summary": "", "per_competitor": {}, "source_urls": []},
        "swot": {"strengths": [], "weaknesses": [], "opportunities": [], "threats": []},
        "radar_scores": [],
    }
    out = AnalyzerAgent._backfill_source_urls(result, [profile])
    assert set(out["positioning"]["source_urls"]) == {"https://a.com", "https://b.com"}
    assert set(out["business_model"]["source_urls"]) == {"https://a.com", "https://b.com"}


def test_backfill_does_not_overwrite_nonempty():
    from src.agents.analyzer import AnalyzerAgent
    from src.schemas.profile import CompetitorProfile, Classification, BasicInfo, ProfileMetadata
    profile = CompetitorProfile(
        classification=Classification(competitor_type="核心竞品", reason="r"),
        basic_info=BasicInfo(name="X"),
        metadata=ProfileMetadata(collected_at="t", data_sources=["https://fallback.com"]),
    )
    result = {"positioning": {"per_competitor": [], "source_urls": ["https://llm-picked.com"]}}
    out = AnalyzerAgent._backfill_source_urls(result, [profile])
    assert out["positioning"]["source_urls"] == ["https://llm-picked.com"]


def test_backfill_feature_matrix_entry_source_urls():
    from src.agents.analyzer import AnalyzerAgent
    from src.schemas.profile import CompetitorProfile, Classification, BasicInfo, ProfileMetadata
    result = {
        "feature_matrix": [
            {"feature": "登录", "source_urls": []},
            {"feature": "导出", "source_urls": ["https://already.com"]},
        ]
    }
    profile = CompetitorProfile(
        classification=Classification(competitor_type="核心竞品", reason="r"),
        basic_info=BasicInfo(name="X"),
        metadata=ProfileMetadata(collected_at="t", data_sources=["https://fb.com"]),
    )
    out = AnalyzerAgent._backfill_source_urls(result, [profile])
    assert out["feature_matrix"][0]["source_urls"] == ["https://fb.com"]
    assert out["feature_matrix"][1]["source_urls"] == ["https://already.com"]
