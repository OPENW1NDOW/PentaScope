import pytest
from unittest.mock import AsyncMock, MagicMock
from src.schemas.report import FinalReport
from src.agents.writer import WriterAgent


class TestWriterAgent:
    @pytest.mark.asyncio
    async def test_write_returns_final_report(self, sample_competitive_analysis, sample_final_report):
        mock_llm = MagicMock()
        mock_llm.call_json = AsyncMock(return_value=sample_final_report)

        agent = WriterAgent(llm=mock_llm)
        from src.schemas.analysis import CompetitiveAnalysis
        analysis = CompetitiveAnalysis(**sample_competitive_analysis)

        result = await agent.write(analysis, ["支付宝"])
        assert isinstance(result, FinalReport)
        assert result.executive_summary.what_competitors_did_right != ""
        assert len(result.action_items.immediate) >= 1


@pytest.mark.asyncio
async def test_writer_mechanically_transfers_structured_fields():
    from src.agents.writer import WriterAgent
    from src.schemas.analysis import (
        CompetitiveAnalysis, Swot, SwotEntry, RadarScore, RadarDimensions,
        FeatureMatrixEntry,
    )
    analysis = CompetitiveAnalysis(
        swot=Swot(strengths=[SwotEntry(point="强")]),
        radar_scores=[RadarScore(competitor="X", dimensions=RadarDimensions(
            feature_breadth=4, usability=4, cost_effectiveness=3, stability=4, design_quality=5))],
        feature_matrix=[FeatureMatrixEntry(feature="f")],
    )

    class _LLM:
        async def call_json(self, system, user):
            return {
                "title": "报告",
                "executive_summary": {
                    "what_competitors_did_right": "x" * 20,
                    "what_competitors_did_wrong": "x" * 20,
                    "our_opportunities": "x" * 20,
                    "next_steps_summary": "x" * 20,
                },
                "sections": [{"title": "概览", "content": "c"}],
                "action_items": {"immediate": [{"priority": "高", "description": "d"}],
                                 "short_term": [{"priority": "中", "description": "d"}],
                                 "long_term": [{"priority": "低", "description": "d"}]},
            }

    report = await WriterAgent(llm=_LLM()).write(analysis, ["X"])
    assert report.swot.strengths[0].point == "强"
    assert report.radar_scores[0].competitor == "X"
    assert report.feature_matrix[0].feature == "f"


def test_downpour_maps_dimension_to_source_refs():
    from src.agents.writer import WriterAgent
    from src.schemas.analysis import CompetitiveAnalysis, Positioning, BusinessModel
    from src.schemas.report import FinalReport, ReportSection
    analysis = CompetitiveAnalysis(
        positioning=Positioning(source_urls=["https://pos.com"]),
        business_model=BusinessModel(source_urls=["https://biz.com"]),
    )
    report = FinalReport(title="t", sections=[
        ReportSection(title="定位", dimension="positioning"),
        ReportSection(title="商业", dimension="business_model"),
        ReportSection(title="综述", dimension="overview"),
    ])
    WriterAgent._fill_section_source_refs(report, analysis)
    assert report.sections[0].source_refs == ["https://pos.com"]
    assert report.sections[1].source_refs == ["https://biz.com"]
    assert set(report.sections[2].source_refs) == {"https://pos.com", "https://biz.com"}


def test_filter_hallucinated_action_item_urls():
    from src.agents.writer import WriterAgent
    from src.schemas.analysis import CompetitiveAnalysis, Positioning
    from src.schemas.report import FinalReport, ActionItems, ActionItem
    analysis = CompetitiveAnalysis(positioning=Positioning(source_urls=["https://real.com"]))
    report = FinalReport(title="t", action_items=ActionItems(
        immediate=[ActionItem(priority="高", description="d",
                              source_urls=["https://real.com", "https://fake.com"])]))
    WriterAgent._fill_section_source_refs(report, analysis)
    assert report.action_items.immediate[0].source_urls == ["https://real.com"]


def test_fill_skips_overwrites_existing_valid_refs():
    """section 已填且 URL 有效时，保留 LLM 填的（仍是它）。"""
    from src.agents.writer import WriterAgent
    from src.schemas.analysis import CompetitiveAnalysis, Positioning
    from src.schemas.report import FinalReport, ReportSection
    analysis = CompetitiveAnalysis(positioning=Positioning(source_urls=["https://pos.com", "https://extra.com"]))
    report = FinalReport(title="t", sections=[
        ReportSection(title="定位", dimension="positioning", source_refs=["https://pos.com"]),
    ])
    WriterAgent._fill_section_source_refs(report, analysis)
    assert report.sections[0].source_refs == ["https://pos.com"]  # 有效，保留 LLM 填的


def test_fill_filters_hallucinated_section_refs():
    """section 已填但全是幻觉 URL 时，回退到机械下沉。"""
    from src.agents.writer import WriterAgent
    from src.schemas.analysis import CompetitiveAnalysis, Positioning
    from src.schemas.report import FinalReport, ReportSection
    analysis = CompetitiveAnalysis(positioning=Positioning(source_urls=["https://real.com"]))
    report = FinalReport(title="t", sections=[
        ReportSection(title="定位", dimension="positioning", source_refs=["https://fake.com"]),
    ])
    WriterAgent._fill_section_source_refs(report, analysis)
    assert report.sections[0].source_refs == ["https://real.com"]  # 幻觉过滤后回退机械下沉


def test_fill_maps_swot_and_feature_matrix_dimensions():
    """swot 和 feature_matrix 维度的 URL 聚合下沉正确。"""
    from src.agents.writer import WriterAgent
    from src.schemas.analysis import (
        CompetitiveAnalysis, Swot, SwotEntry, FeatureMatrixEntry,
    )
    analysis = CompetitiveAnalysis(
        swot=Swot(strengths=[SwotEntry(point="p", source_urls=["https://swot.com"])]),
        feature_matrix=[FeatureMatrixEntry(feature="f", source_urls=["https://fm.com"])],
    )
    from src.schemas.report import FinalReport, ReportSection
    report = FinalReport(title="t", sections=[
        ReportSection(title="SWOT", dimension="swot"),
        ReportSection(title="功能", dimension="feature_matrix"),
    ])
    WriterAgent._fill_section_source_refs(report, analysis)
    assert report.sections[0].source_refs == ["https://swot.com"]
    assert report.sections[1].source_refs == ["https://fm.com"]
