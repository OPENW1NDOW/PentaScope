"""BaseReport 通用骨架 + 5 场景 discriminated union"""
from __future__ import annotations
from datetime import date
from typing import Annotated, Literal, Optional, Union
from pydantic import BaseModel, Field, computed_field, model_validator

from src.schemas.common import DataSource, Exhibit, Revision, SourceRef
from src.schemas.scenarios.s1 import S1FeatureIterationPayload
from src.schemas.scenarios.s2 import S2MarketEntryPayload
from src.schemas.scenarios.s3 import S3PricingStrategyPayload
from src.schemas.scenarios.s4 import S4MonitoringPayload
from src.schemas.scenarios.s5 import S5PositioningPayload


# ============ 通用骨架子模型 ============

class ExecutiveSummary(BaseModel):
    """执行摘要 5 段式（替代旧 4 段）"""
    context: str = Field(min_length=80, max_length=200)
    core_thesis: str = Field(min_length=50, max_length=120)
    key_findings_brief: list[str] = Field(min_length=2, max_length=4)
    implications: str = Field(min_length=100, max_length=250)
    path_forward: list[str] = Field(min_length=1, max_length=3)


class ReportScope(BaseModel):
    competitors: list[str] = Field(min_length=1)
    time_window: str
    regions: list[str] = Field(default_factory=list)
    exclusions: list[str] = Field(default_factory=list)


class Methodology(BaseModel):
    """方法论章节，字数预算 1000+ 字"""
    data_collection_approach: str = Field(min_length=200)
    evaluation_criteria: list[str] = Field(min_length=3)
    limitations: list[str] = Field(min_length=2)
    sample_size_note: str = Field(min_length=80)
    analyst_disclosure: str = Field(
        default="本报告由 AI 多 Agent 协作系统生成，分析模型 Doubao-Seed-2.0-lite"
    )


class Finding(BaseModel):
    statement: str = Field(min_length=20)
    evidence: str = Field(min_length=20)
    implication: str = Field(min_length=20)
    source_refs: list[SourceRef] = Field(default_factory=list)


class AnalysisSection(BaseModel):
    section_id: str = Field(min_length=3, max_length=40)
    heading: str = Field(min_length=4)
    narrative: str = Field(min_length=300)
    section_type: Literal[
        "overview", "executive_overview", "background", "conclusions_summary",
        "feature_matrix_analysis", "vendor_profile_analysis", "jtbd_analysis", "roadmap_analysis",
        "market_sizing_analysis", "five_forces_analysis", "competitive_landscape_analysis",
        "consumer_segments_analysis", "trends_analysis", "entry_strategy_analysis",
        "pricing_baseline_analysis", "value_drivers_analysis", "packaging_design_analysis",
        "competitive_pricing_analysis", "pricing_recommendations_analysis",
        "monitoring_overview", "competitive_moves_analysis", "threat_assessment_analysis",
        "opportunity_identification_analysis", "battlecard_analysis",
        "vendor_positioning_analysis", "perceptual_map_analysis", "strategy_canvas_analysis",
        "errc_analysis", "positioning_statement_analysis",
    ]
    artifact_refs: list[str] = Field(default_factory=list)
    source_refs: list[SourceRef] = Field(default_factory=list)


class Recommendation(BaseModel):
    action: str = Field(min_length=20)
    target_role: str
    priority: Literal["critical", "important", "consider"]
    timeline: Literal["immediate", "short_term", "long_term"]
    rationale: str = Field(min_length=20)
    source_refs: list[SourceRef] = Field(default_factory=list)


class SwotEntry(BaseModel):
    point: str = Field(min_length=10)
    evidence: str = Field(min_length=10)
    dimension: str = Field(default="overall")
    source_refs: list[SourceRef] = Field(default_factory=list)


class Swot(BaseModel):
    strengths: list[SwotEntry] = Field(min_length=1)
    weaknesses: list[SwotEntry] = Field(min_length=1)
    opportunities: list[SwotEntry] = Field(min_length=1)
    threats: list[SwotEntry] = Field(min_length=1)


class Appendix(BaseModel):
    glossary: dict[str, str] = Field(default_factory=dict)
    additional_exhibits: list[Exhibit] = Field(default_factory=list)
    data_sources_full: list[DataSource] = Field(default_factory=list)


# ============ ReportMetadata（Task 3） ============

class ReportMetadata(BaseModel):
    # 基础识别
    report_id: str
    trace_id: str
    scenario: Literal["S1", "S2", "S3", "S4", "S5"]
    schema_version: str = "2.0"

    # 时间与版本
    publication_date: date
    version: str = "1.0"
    revision_history: list[Revision] = Field(default_factory=list)

    # 作者与出品方
    organization: str = "AI 竞品分析 Agent 协作系统"
    contributing_agents: list[str] = Field(default_factory=list)

    # 可信度与溯源
    data_sources: list[DataSource] = Field(min_length=1)
    confidence_level: Literal["high", "medium", "low"]
    quality_score: Optional[float] = Field(default=None, ge=0, le=1)
    raw_quality_score: Optional[float] = Field(
        default=None,
        ge=0,
        le=1,
        description=(
            "cap 前的初始加权分（含 placeholder pass_rate 影响）。"
            "用于 KPI 卡显示模型实际算分。命名 raw 仅指 cap 前，"
            "不代表完全无任何惩罚——v3-R17 cap 仅是惩罚之一。"
        ),
    )
    quality_score_calculation_note: str = Field(default="")
    warnings: list[str] = Field(default_factory=list)

    # 合规
    disclaimer: str = Field(
        default="本报告基于公开渠道采集数据生成，不构成投资建议。生成时间晚于数据采集时间可能存在滞后。"
    )
    citation_format: Optional[str] = None


# ============ BaseReport（接通 5 场景 discriminated union） ============


class BaseReport(BaseModel):
    """所有 5 场景共用的报告通用骨架"""
    metadata: ReportMetadata
    title: str = Field(min_length=10, max_length=80)
    subtitle: Optional[str] = Field(default=None, max_length=120)
    at_a_glance: list[str] = Field(min_length=3, max_length=6)
    executive_summary: ExecutiveSummary
    background: str = Field(min_length=200, max_length=1500)
    scope: ReportScope
    methodology: Methodology
    key_findings: list[Finding] = Field(min_length=3, max_length=6)
    analysis_sections: list[AnalysisSection] = Field(min_length=4, max_length=8)
    swot: Swot
    conclusions: str = Field(min_length=200, max_length=1500)
    recommendations: list[Recommendation] = Field(min_length=3)
    appendix: Appendix = Field(default_factory=lambda: Appendix())

    scenario_payload: Annotated[
        Union[
            S1FeatureIterationPayload,
            S2MarketEntryPayload,
            S3PricingStrategyPayload,
            S4MonitoringPayload,
            S5PositioningPayload,
        ],
        Field(discriminator='scenario_type')
    ]

    @computed_field
    @property
    def scenario(self) -> Literal["S1", "S2", "S3", "S4", "S5"]:
        return self.scenario_payload.scenario_type

    @model_validator(mode='after')
    def _check_scenario_consistency(self) -> 'BaseReport':
        if self.metadata.scenario != self.scenario_payload.scenario_type:
            raise ValueError(
                f"metadata.scenario={self.metadata.scenario} but "
                f"scenario_payload.scenario_type={self.scenario_payload.scenario_type}"
            )
        return self
