"""S4 持续监控场景载荷"""
from datetime import date
from typing import Literal, Optional
from pydantic import BaseModel, Field, computed_field, model_validator

from src.schemas.common import ArtifactBase, SourceRef


class ReviewPeriod(BaseModel):
    """监控时间窗"""
    last_review_date: Optional[date] = None
    current_review_date: date
    review_period_label: str = ""
    monitored_competitors: list[str] = Field(min_length=1)
    prior_trace_id: Optional[str] = None  # 缺失则走"首次监控"模式

    newly_added_competitors: list[str] = Field(default_factory=list)
    dropped_competitors: list[str] = Field(default_factory=list)


class FIATuple(BaseModel):
    """Klue FIA 三元组（fact 必填，impact + act Optional）"""
    fact: str = ""
    impact: Optional[str] = None
    act: Optional[str] = None


class _BaseChange(BaseModel):
    """所有变更条目共享的基础字段"""
    competitor_name: str = ""
    detected_date: Optional[date] = None
    fia: FIATuple
    severity: Literal["low", "medium", "high"]
    source_refs: list[SourceRef] = Field(min_length=1)
    is_baseline: bool = False  # 首次监控模式时填 True


class FeatureChange(_BaseChange, ArtifactBase):
    artifact_type: Literal["feature_change"] = "feature_change"
    change_type: Literal["new_feature", "removed_feature", "feature_updated"]
    feature_name: str = ""


class PricingChange(_BaseChange, ArtifactBase):
    artifact_type: Literal["pricing_change"] = "pricing_change"
    change_type: Literal[
        "tier_added", "tier_removed", "price_increased", "price_decreased",
        "packaging_restructured", "discount_changed",
    ]
    before: str = Field(default="")
    after: str = Field(default="")


class MessagingChange(_BaseChange, ArtifactBase):
    artifact_type: Literal["messaging_change"] = "messaging_change"
    change_type: Literal[
        "headline_changed", "positioning_shift", "brand_update", "campaign_launch",
    ]
    before_text: str = Field(default="")
    after_text: str = Field(default="")


class NewsEvent(_BaseChange, ArtifactBase):
    artifact_type: Literal["news_event"] = "news_event"
    category: Literal[
        "funding", "partnership", "leadership", "legal", "product_launch",
        "acquisition", "ipo", "layoff", "other",
    ]
    headline: str = ""


class OrgChange(_BaseChange, ArtifactBase):
    artifact_type: Literal["org_change"] = "org_change"
    role: str = ""
    person_name: Optional[str] = None
    action: Literal[
        "hired", "departed", "promoted", "demoted",
        "joined_board", "title_changed", "founder_exit",
    ]


class MonitoringThreat(ArtifactBase):
    """威胁评估（quadrant 由 severity×likelihood 自动派生）"""
    artifact_type: Literal["monitoring_threat"] = "monitoring_threat"
    title: str = ""
    severity: Literal["low", "medium", "high"]
    likelihood: Literal["low", "medium", "high"]
    description: str = ""
    recommended_response: str = ""
    source_refs: list[SourceRef] = Field(default_factory=list)

    @computed_field
    @property
    def quadrant(self) -> Literal["act_now", "contingency", "monitor", "deprioritize"]:
        s_high = self.severity == "high"
        l_high = self.likelihood == "high"
        if s_high and l_high:
            return "act_now"
        if s_high and not l_high:
            return "contingency"
        if not s_high and l_high:
            return "monitor"
        return "deprioritize"


class MonitoringOpportunity(ArtifactBase):
    """机会识别（OSCOM 4 类）"""
    artifact_type: Literal["monitoring_opportunity"] = "monitoring_opportunity"
    opportunity_type: Literal[
        "abandoned_segment", "product_gap", "messaging_white_space", "operational_weakness",
    ]
    description: str = ""
    estimated_effort: Literal["low", "medium", "high"]
    expected_impact: Literal["low", "medium", "high"]
    first_step: str = ""
    source_refs: list[SourceRef] = Field(default_factory=list)


class MonitoringTrends(BaseModel):
    """趋势方向（统一 up/flat/down）"""
    sentiment_trend: Optional[Literal["up", "flat", "down"]] = None
    pricing_trend: Optional[Literal["up", "flat", "down"]] = None
    release_velocity_trend: Optional[Literal["up", "flat", "down"]] = None
    threat_level_trend: Optional[Literal["up", "flat", "down"]] = None
    rationale: str = Field(default="")


class MonitoringAction(BaseModel):
    """推荐行动（supporting_intel_refs 用 artifact_id）"""
    description: str = ""
    owner_team: Literal["product", "marketing", "sales", "exec", "engineering", "support"]
    priority_tier: Literal["critical", "important", "consider"]
    due_date_estimate: Optional[date] = None
    supporting_intel_refs: list[str] = Field(default_factory=list)


class BattlecardSection(BaseModel):
    """Battlecard 单节（completeness 表数据完整度而非可信度）"""
    section_name: Literal[
        "quick_summary", "primary_threat", "messaging_positioning",
        "pricing_packaging", "product_strategy",
        "customer_sentiment", "win_loss_themes", "monitoring_priorities",
    ]
    content: str = Field(default="")
    completeness: Literal["full", "partial", "empty"] = "empty"
    source_refs: list[SourceRef] = Field(default_factory=list)


class Battlecard(ArtifactBase):
    """单竞品活体 Battlecard"""
    artifact_type: Literal["battlecard"] = "battlecard"
    competitor_name: str = ""
    sections: list[BattlecardSection] = Field(min_length=4)
    overall_completeness: Literal["full", "partial", "empty"] = "partial"

    @computed_field
    @property
    def last_updated_at(self) -> Optional[date]:
        all_dates: list[date] = []
        for s in self.sections:
            for ref in s.source_refs:
                if ref.accessed_at:
                    all_dates.append(ref.accessed_at)
        return max(all_dates) if all_dates else None


class S4MonitoringPayload(BaseModel):
    """S4 持续监控场景载荷"""
    scenario_type: Literal["S4"] = "S4"

    review_period: ReviewPeriod

    feature_changes: list[FeatureChange] = Field(default_factory=list)
    pricing_changes: list[PricingChange] = Field(default_factory=list)
    messaging_changes: list[MessagingChange] = Field(default_factory=list)
    news_events: list[NewsEvent] = Field(default_factory=list)
    org_changes: list[OrgChange] = Field(default_factory=list)

    threats: list[MonitoringThreat] = Field(default_factory=list, max_length=5)
    opportunities: list[MonitoringOpportunity] = Field(default_factory=list, max_length=8)

    trends: MonitoringTrends

    monitoring_actions: list[MonitoringAction] = Field(default_factory=list, max_length=12)

    battlecards: list[Battlecard] = Field(min_length=1)

    @model_validator(mode='after')
    def _check_monitored_competitor_consistency(self) -> 'S4MonitoringPayload':
        monitored = set(self.review_period.monitored_competitors)
        for collection_name, items in [
            ("feature_changes", self.feature_changes),
            ("pricing_changes", self.pricing_changes),
            ("messaging_changes", self.messaging_changes),
            ("news_events", self.news_events),
            ("org_changes", self.org_changes),
        ]:
            for item in items:
                if item.competitor_name not in monitored:
                    raise ValueError(
                        f"{collection_name} 中竞品 '{item.competitor_name}' 不在 monitored_competitors {monitored}"
                    )
        for bc in self.battlecards:
            if bc.competitor_name not in monitored:
                raise ValueError(
                    f"battlecards 中竞品 '{bc.competitor_name}' 不在 monitored_competitors {monitored}"
                )
        return self

    @model_validator(mode='after')
    def _check_first_review_baseline(self) -> 'S4MonitoringPayload':
        """首次监控模式（prior_trace_id=None）下，所有 change 必须 is_baseline=True，trends 全 None"""
        if self.review_period.prior_trace_id is None:
            for items in [
                self.feature_changes, self.pricing_changes, self.messaging_changes,
                self.news_events, self.org_changes,
            ]:
                for item in items:
                    if not item.is_baseline:
                        raise ValueError(
                            "首次监控模式（prior_trace_id=None）下，所有 change 条目必须 is_baseline=True"
                        )
            t = self.trends
            if any([t.sentiment_trend, t.pricing_trend, t.release_velocity_trend, t.threat_level_trend]):
                raise ValueError("首次监控模式下 trends 必须全部为 None")
        return self
