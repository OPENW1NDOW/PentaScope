/**
 * PentaScope TypeScript type definitions
 * Converted from Pydantic schemas (src/schemas/)
 *
 * @module types
 */

// ============================================================
// Common Types
// ============================================================

/** 统一溯源对象 */
export interface SourceRef {
  url: string;
  title?: string;
  accessed_at?: string; // ISO date string
  source_type?: SourceType;
}

export type SourceType =
  | "official_website"
  | "third_party_review"
  | "industry_report"
  | "news"
  | "user_review"
  | "regulatory"
  | "other";

/** 报告级数据源汇总 */
export interface DataSource extends SourceRef {
  confidence?: ConfidenceLevel;
}

export type ConfidenceLevel = "high" | "medium" | "low";

/** 可被 AnalysisSection.artifact_refs 引用的产物基类 */
export interface ArtifactBase {
  artifact_id: string;
  artifact_type: string;
  title?: string;
}

/** 报告版本修订记录 */
export interface Revision {
  revision_date: string; // ISO date string
  change_summary: string;
  triggered_by: "initial" | "inspector_feedback" | "user_request";
}

/** 附录展示 */
export interface Exhibit extends ArtifactBase {
  artifact_type: "exhibit";
  description?: string;
  payload?: Record<string, unknown>;
}

// ============================================================
// Feedback Types
// ============================================================

/** 质检发现的单个问题 */
export interface FeedbackIssue {
  agent: "collector" | "analyzer" | "writer" | "end";
  field: string;
  severity: "critical" | "major" | "minor";
  reason: string;
  suggestion?: string;
  dimension?: FeedbackDimension;
  issue_type?: IssueType;
}

export type FeedbackDimension =
  | "evidence"
  | "specificity"
  | "coherence"
  | "actionability"
  | "programmatic"
  | "critic_failed"
  | "overall";

export type IssueType =
  | "url_not_discovered"
  | "source_mismatch"
  | "source_irrelevant"
  | "vague_description"
  | "cross_field_contradiction"
  | "vague_recommendation"
  | "critic_failed";

/** critic 4 维评分 */
export interface CriticScores {
  evidence: number; // 1-4
  specificity: number; // 1-4
  coherence: number; // 1-4
  actionability: number; // 1-4
  reasoning?: Record<string, string[]>;
}

/** 质检 Agent 输出 */
export interface RejectionFeedback {
  passed: boolean;
  issues?: FeedbackIssue[];
  retry_count?: number;
  max_retries?: number;
}

// ============================================================
// Report Types
// ============================================================

/** 执行摘要 */
export interface ExecutiveSummary {
  context: string;
  core_thesis: string;
  key_findings_brief: string[]; // 2-4 items
  implications: string;
  path_forward: string[]; // 1-3 items
}

/** 报告范围 */
export interface ReportScope {
  competitors: string[];
  time_window: string;
  regions?: string[];
  exclusions?: string[];
}

/** 方法论 */
export interface Methodology {
  data_collection_approach?: string;
  evaluation_criteria: string[]; // 2+
  limitations: string[]; // 1+
  sample_size_note?: string;
  analyst_disclosure?: string;
}

/** 关键发现 */
export interface Finding {
  statement: string;
  evidence: string;
  implication: string;
  source_refs?: SourceRef[];
}

/** 分析章节 */
export interface AnalysisSection {
  section_id: string;
  heading: string;
  narrative: string;
  section_type: SectionType;
  artifact_refs?: string[];
  source_refs?: SourceRef[];
}

export type SectionType =
  | "overview"
  | "executive_overview"
  | "background"
  | "conclusions_summary"
  | "feature_matrix_analysis"
  | "vendor_profile_analysis"
  | "jtbd_analysis"
  | "roadmap_analysis"
  | "market_sizing_analysis"
  | "five_forces_analysis"
  | "competitive_landscape_analysis"
  | "consumer_segments_analysis"
  | "trends_analysis"
  | "entry_strategy_analysis"
  | "pricing_baseline_analysis"
  | "value_drivers_analysis"
  | "packaging_design_analysis"
  | "competitive_pricing_analysis"
  | "pricing_recommendations_analysis"
  | "monitoring_overview"
  | "competitive_moves_analysis"
  | "threat_assessment_analysis"
  | "opportunity_identification_analysis"
  | "battlecard_analysis"
  | "vendor_positioning_analysis"
  | "perceptual_map_analysis"
  | "strategy_canvas_analysis"
  | "errc_analysis"
  | "positioning_statement_analysis";

/** 建议 */
export interface Recommendation {
  action: string;
  target_role: string;
  priority: "critical" | "important" | "consider";
  timeline: "immediate" | "short_term" | "long_term";
  rationale?: string;
  source_refs?: SourceRef[];
}

/** SWOT 条目 */
export interface SwotEntry {
  point: string;
  evidence?: string;
  dimension?: string;
  source_refs?: SourceRef[];
}

/** SWOT 分析 */
export interface Swot {
  strengths: SwotEntry[];
  weaknesses: SwotEntry[];
  opportunities: SwotEntry[];
  threats: SwotEntry[];
}

/** 附录 */
export interface Appendix {
  glossary?: Record<string, string>;
  additional_exhibits?: Exhibit[];
  data_sources_full?: DataSource[];
}

/** 报告元数据 */
export interface ReportMetadata {
  report_id: string;
  trace_id: string;
  scenario: Scenario;
  schema_version?: string;
  publication_date: string; // ISO date string
  version?: string;
  revision_history?: Revision[];
  organization?: string;
  contributing_agents?: string[];
  data_sources: DataSource[];
  confidence_level: ConfidenceLevel;
  quality_score?: number | null;
  raw_quality_score?: number | null;
  quality_score_calculation_note?: string;
  warnings?: string[];
  disclaimer?: string;
  citation_format?: string | null;
  critic_scores?: CriticScores | null;
  score_source?: "critic" | "fallback" | null;
  critic_prompt_version?: string | null;
}

export type Scenario = "S1" | "S2" | "S3" | "S4" | "S5";

/** BaseReport — 所有场景共用的报告骨架 */
export interface BaseReport {
  metadata: ReportMetadata;
  title: string;
  subtitle?: string | null;
  at_a_glance: string[]; // 3-6 items
  executive_summary: ExecutiveSummary;
  background: string;
  scope: ReportScope;
  methodology: Methodology;
  key_findings: Finding[]; // 3-6 items
  analysis_sections: AnalysisSection[]; // 4-8 items
  swot: Swot;
  conclusions: string;
  recommendations: Recommendation[]; // 3+ items
  appendix?: Appendix;
  scenario_payload: ScenarioPayload;
}

export type ScenarioPayload =
  | S1FeatureIterationPayload
  | S2MarketEntryPayload
  | S3PricingStrategyPayload
  | S4MonitoringPayload
  | S5PositioningPayload;

// ============================================================
// S1 — Feature Iteration
// ============================================================

export interface VendorStrength {
  point: string;
  evidence?: string;
  source_refs?: SourceRef[];
}

export interface VendorCaution {
  point: string;
  evidence?: string;
  source_refs?: SourceRef[];
}

export interface S1VendorProfile {
  competitor_name: string;
  wave_position: "wave_leader" | "wave_strong_performer" | "wave_contender";
  one_line_pitch: string;
  strengths: VendorStrength[];
  cautions: VendorCaution[];
  best_fit_for?: string;
  reference_customer_feedback?: string;
  source_refs?: SourceRef[];
}

export interface FeatureScore {
  score: 0 | 1 | 2;
  note?: string;
  evidence_url?: string | null;
  source_missing_reason?: string | null;
  last_verified?: string | null; // ISO date string
}

export interface FeatureRow {
  name: string;
  description?: string;
  scores: Record<string, FeatureScore>;
}

export interface FeatureCategory {
  name: string;
  tier: 1 | 2 | 3;
  features: FeatureRow[];
}

export interface FeatureMatrix extends ArtifactBase {
  artifact_type: "feature_matrix";
  competitors: string[];
  our_product_name: string;
  categories: FeatureCategory[];
}

export interface S1RadarScore extends ArtifactBase {
  artifact_type: "s1_radar_score";
  competitor_name: string;
  feature_breadth: number; // 0-5
  usability: number; // 0-5
  cost_effectiveness: number; // 0-5
  stability: number; // 0-5
  design_quality: number; // 0-5
}

export interface JobStatement {
  situation: string;
  motivation: string;
  outcome: string;
  layer?: "functional" | "emotional" | "social";
}

export interface FeatureGap {
  feature_name: string;
  competitors_have_it: string[];
  underserved_outcome?: string;
  estimated_effort: "low" | "medium" | "high";
  estimated_impact: "low" | "medium" | "high";
  recommendation: "build" | "skip" | "differentiate";
  source_refs?: SourceRef[];
}

export interface RoadmapRecommendations {
  must_build: string[];
  should_skip?: string[];
  should_differentiate?: string[];
  rationale_summary?: string;
}

export interface Tier1Disqualifier {
  feature: string;
  competitors_failing: string[];
  implication?: string;
}

export interface WhiteSpaceFeature {
  feature: string;
  why_no_one_supports?: string;
  opportunity_estimate: "high" | "medium" | "low";
}

export interface S1FeatureIterationPayload {
  scenario_type: "S1";
  vendor_profiles: S1VendorProfile[];
  feature_matrix: FeatureMatrix;
  tier1_disqualifiers?: Tier1Disqualifier[];
  white_space_features?: WhiteSpaceFeature[];
  radar_scores: S1RadarScore[];
  job_statement: JobStatement;
  feature_gaps: FeatureGap[];
  roadmap_recommendations: RoadmapRecommendations;
}

// ============================================================
// S2 — Market Entry
// ============================================================

export interface MarketValue {
  amount?: number | null;
  currency?: "USD" | "CNY" | "EUR" | "JPY" | "unknown";
  unit?: "billion" | "million" | "thousand" | "raw";
  year?: number | null;
  geography?: string;
  value_basis?: "measured" | "estimated" | "inferred" | "unknown";
  methodology_note?: string;
  source_refs?: SourceRef[];
}

export interface ForecastScenarios {
  low_growth_pct: number;
  base_growth_pct: number;
  high_growth_pct: number;
  rationale?: string;
}

export interface MarketSizing extends ArtifactBase {
  artifact_type: "market_sizing";
  tam: MarketValue;
  sam: MarketValue;
  som: MarketValue;
  cagr_pct?: number | null;
  forecast_years?: number | null;
  forecast_scenarios?: ForecastScenarios | null;
  triangulation_gap_pct?: number | null;
}

export interface Force {
  intensity: "low" | "medium" | "high";
  drivers: string[];
  evidence: string[];
  implication?: string;
  source_refs?: SourceRef[];
}

export interface FiveForces extends ArtifactBase {
  artifact_type: "five_forces";
  new_entrants: Force;
  supplier_power: Force;
  buyer_power: Force;
  substitute_threat: Force;
  competitive_rivalry: Force;
}

export interface MarketPlayer {
  name?: string;
  company?: string;
  market_role: "incumbent" | "challenger" | "emerging" | "niche" | "substitute";
  market_share_pct?: number | null;
  yoy_growth_pct?: number | null;
  one_line_summary?: string;
  key_differentiator?: string;
  is_recommended?: boolean;
  is_collected?: boolean;
  source_refs?: SourceRef[];
}

export interface ConsumerSegment {
  name?: string;
  size_estimate?: string;
  share_pct?: number | null;
  key_needs: string[];
  underserved_indicators?: string[];
  addressability: "easy" | "moderate" | "hard";
  source_refs?: SourceRef[];
}

export interface Trend {
  trend_name?: string;
  description?: string;
  supporting_data?: string;
  direction: "up" | "flat" | "down";
  time_horizon: "short_term" | "mid_term" | "long_term";
  impact_on_entry: "positive" | "negative" | "mixed";
  source_refs?: SourceRef[];
}

export interface Risk {
  description?: string;
  likelihood: "low" | "medium" | "high";
  impact: "low" | "medium" | "high";
  mitigation?: string;
}

export interface Phase {
  phase_name?: string;
  duration: string;
  key_milestones: string[];
  resource_requirements?: string;
}

export interface EntryStrategy extends ArtifactBase {
  artifact_type: "entry_strategy";
  recommended_mode:
    | "direct_competition"
    | "niche_focus"
    | "differentiation"
    | "partnership"
    | "acquisition"
    | "wait_and_see";
  target_segments: string[];
  initial_positioning?: string;
  key_success_factors: string[];
  main_risks: Risk[];
  timeline_phases: Phase[];
}

export interface PESTELFactor {
  name?: string;
  impact: "opportunity" | "threat" | "neutral";
  severity: "low" | "medium" | "high";
  description?: string;
  source_refs?: SourceRef[];
}

export interface PESTEL extends ArtifactBase {
  artifact_type: "pestel";
  political?: PESTELFactor[];
  economic?: PESTELFactor[];
  social?: PESTELFactor[];
  technological?: PESTELFactor[];
  environmental?: PESTELFactor[];
  legal?: PESTELFactor[];
}

export interface RecommendedCompetitor {
  name?: string;
  company?: string;
  why_recommended?: string;
  confidence: ConfidenceLevel;
  source_refs?: SourceRef[];
}

export interface CompetitorRecommendations {
  user_provided_industry?: string;
  user_provided_competitors?: string[];
  recommended_competitors: RecommendedCompetitor[];
  selection_method: "search_api_top_n" | "llm_inference" | "hybrid";
  selection_rationale?: string;
}

export interface S2MarketEntryPayload {
  scenario_type: "S2";
  market_sizing: MarketSizing;
  five_forces: FiveForces;
  industry_attractiveness_1_5: number; // 1-5
  players: MarketPlayer[];
  market_concentration: "fragmented" | "moderate" | "concentrated";
  consumer_segments?: ConsumerSegment[] | null;
  key_trends: Trend[];
  entry_strategy: EntryStrategy;
  pestel?: PESTEL | null;
  competitor_recommendations: CompetitorRecommendations;
}

// ============================================================
// S3 — Pricing Strategy
// ============================================================

export type PricingModel =
  | "per_seat"
  | "flat_rate"
  | "usage_based"
  | "hybrid"
  | "freemium"
  | "platform_fee"
  | "unknown";

export type BillingUnit =
  | "per_seat"
  | "flat_rate"
  | "usage_based"
  | "tier_subscription";

export type Currency = "CNY" | "USD" | "EUR" | "JPY" | "unknown";

export interface PricingBaseline {
  current_pricing_model: PricingModel;
  current_tier_count: number;
  current_arpu_note?: string;
  pain_points: string[];
  source_refs?: SourceRef[];
}

export interface ValueDriver {
  driver_name?: string;
  importance: "low" | "medium" | "high";
  evidence?: string;
  source_refs?: SourceRef[];
}

export interface FeatureClassification {
  hygiene_factors: string[];
  preference_drivers?: string[];
  premium_drivers: string[];
}

export interface WTPResearch {
  method:
    | "conjoint_analysis"
    | "van_westendorp"
    | "gabor_granger"
    | "interviews"
    | "ab_testing"
    | "proxy_from_competitor_pricing";
  sample_size?: number | null;
  optimal_price_point?: string | null;
  confidence: "low" | "medium" | "high";
  rationale?: string;
  limitations?: string;
}

export interface RecommendedPriceTier {
  name?: string;
  position: "good" | "better" | "best" | "enterprise" | "free";
  monthly_price?: number | null;
  annual_price?: number | null;
  currency?: Currency;
  billing_unit: BillingUnit;
  is_recommended?: boolean;
  target_persona?: string;
  included_features: string[];
  gated_features?: string[];
  cta_copy?: string;
  upgrade_trigger?: string;
}

export interface Packaging extends ArtifactBase {
  artifact_type: "packaging";
  tiers: RecommendedPriceTier[];
  annual_discount_pct?: number | null;
  default_billing_cycle?: "monthly" | "annual";
  rationale?: string;
}

export interface ObservedCompetitorTier {
  name?: string;
  monthly_price?: number | null;
  annual_price?: number | null;
  currency?: Currency;
  billing_unit: BillingUnit;
  observed_is_most_popular?: boolean;
  observed_target_persona?: string;
  observed_features: string[];
  observed_cta_copy?: string;
  source_refs: SourceRef[];
}

export interface CompetitorPricing extends ArtifactBase {
  artifact_type: "competitor_pricing";
  competitor_name?: string;
  pricing_model: PricingModel;
  tiers: ObservedCompetitorTier[];
  free_plan_strategy?: "freemium" | "free_trial" | "no_free_plan" | null;
  discount_strategy?: string;
  notes?: string;
  source_refs: SourceRef[];
}

export interface PricingPageAuditScore {
  rule_name:
    | "tier_naming_buyer_centric"
    | "anchor_pricing_middle_tier"
    | "annual_billing_default"
    | "feature_gating_clear"
    | "cta_copy_aligned"
    | "social_proof_at_decision"
    | "transparent_feature_comparison"
    | "psychological_pricing";
  passed: boolean;
  note?: string;
}

export interface PricingPageAudit extends ArtifactBase {
  artifact_type: "pricing_page_audit";
  competitor_name?: string;
  audit_scores?: PricingPageAuditScore[];
  pricing_page_url?: string | null;
  source_refs?: SourceRef[];
}

export interface PricingRecommendationsSummary {
  recommended_packaging_summary?: string;
  expected_arr_uplift_pct?: number | null;
  expected_arr_uplift_basis?:
    | "measured_pilot"
    | "competitor_benchmark"
    | "industry_estimate"
    | "llm_inferred";
  expected_arr_uplift_methodology?: string;
  expected_uplift_rationale?: string;
  main_risks: Risk[];
}

export interface RolloutStep extends ArtifactBase {
  artifact_type: "rollout_step";
  step_name?: string;
  description?: string;
  duration: string;
  owner_team?: string;
  success_metric?: string;
}

export interface S3PricingStrategyPayload {
  scenario_type: "S3";
  pricing_baseline: PricingBaseline;
  value_drivers: ValueDriver[];
  feature_classification: FeatureClassification;
  wtp_research?: WTPResearch | null;
  packaging: Packaging;
  competitive_pricing_matrix: CompetitorPricing[];
  pricing_page_audit?: PricingPageAudit[];
  recommendations_summary: PricingRecommendationsSummary;
  rollout_plan: RolloutStep[];
}

// ============================================================
// S4 — Competitive Monitoring
// ============================================================

/** 监控时间窗 */
export interface ReviewPeriod {
  last_review_date?: string | null;
  current_review_date: string;
  review_period_label?: string;
  monitored_competitors: string[];
  prior_trace_id?: string | null; // 缺失则为「首次监控」模式
  newly_added_competitors?: string[];
  dropped_competitors?: string[];
}

/** Klue FIA 三元组（fact 必填，impact + act Optional） */
export interface FIATuple {
  fact: string;
  impact?: string | null;
  act?: string | null;
}

export type ChangeSeverity = "low" | "medium" | "high";

/** 所有变更条目共享的基础字段 */
export interface BaseChange extends ArtifactBase {
  competitor_name: string;
  detected_date?: string | null;
  fia: FIATuple;
  severity: ChangeSeverity;
  source_refs: SourceRef[];
  is_baseline: boolean; // 首次监控模式时为 true
}

export interface FeatureChange extends BaseChange {
  artifact_type: "feature_change";
  change_type: "new_feature" | "removed_feature" | "feature_updated";
  feature_name: string;
}

export interface PricingChange extends BaseChange {
  artifact_type: "pricing_change";
  change_type:
    | "tier_added"
    | "tier_removed"
    | "price_increased"
    | "price_decreased"
    | "packaging_restructured"
    | "discount_changed";
  before: string;
  after: string;
}

export interface MessagingChange extends BaseChange {
  artifact_type: "messaging_change";
  change_type:
    | "headline_changed"
    | "positioning_shift"
    | "brand_update"
    | "campaign_launch";
  before_text: string;
  after_text: string;
}

export interface NewsEvent extends BaseChange {
  artifact_type: "news_event";
  category:
    | "funding"
    | "partnership"
    | "leadership"
    | "legal"
    | "product_launch"
    | "acquisition"
    | "ipo"
    | "layoff"
    | "other";
  headline: string;
}

export interface OrgChange extends BaseChange {
  artifact_type: "org_change";
  role: string;
  person_name?: string | null;
  action:
    | "hired"
    | "departed"
    | "promoted"
    | "demoted"
    | "joined_board"
    | "title_changed"
    | "founder_exit";
}

/** 威胁评估（quadrant 由后端 severity×likelihood 派生，随 JSON 下发） */
export interface MonitoringThreat extends ArtifactBase {
  artifact_type: "monitoring_threat";
  title: string;
  severity: ChangeSeverity;
  likelihood: ChangeSeverity;
  description: string;
  recommended_response: string;
  source_refs?: SourceRef[];
  quadrant: "act_now" | "contingency" | "monitor" | "deprioritize";
}

/** 机会识别（OSCOM 4 类） */
export interface MonitoringOpportunity extends ArtifactBase {
  artifact_type: "monitoring_opportunity";
  opportunity_type:
    | "abandoned_segment"
    | "product_gap"
    | "messaging_white_space"
    | "operational_weakness";
  description: string;
  estimated_effort: ChangeSeverity;
  expected_impact: ChangeSeverity;
  first_step: string;
  source_refs?: SourceRef[];
}

export type TrendDirection = "up" | "flat" | "down";

/** 趋势方向（首次监控模式下全 null） */
export interface MonitoringTrends {
  sentiment_trend?: TrendDirection | null;
  pricing_trend?: TrendDirection | null;
  release_velocity_trend?: TrendDirection | null;
  threat_level_trend?: TrendDirection | null;
  rationale?: string;
}

/** 推荐行动 */
export interface MonitoringAction {
  description: string;
  owner_team: "product" | "marketing" | "sales" | "exec" | "engineering" | "support";
  priority_tier: "critical" | "important" | "consider";
  due_date_estimate?: string | null;
  supporting_intel_refs?: string[];
}

export type BattlecardSectionName =
  | "quick_summary"
  | "primary_threat"
  | "messaging_positioning"
  | "pricing_packaging"
  | "product_strategy"
  | "customer_sentiment"
  | "win_loss_themes"
  | "monitoring_priorities";

export type BattlecardCompleteness = "full" | "partial" | "empty";

export interface BattlecardSection {
  section_name: BattlecardSectionName;
  content: string;
  completeness: BattlecardCompleteness;
  source_refs?: SourceRef[];
}

/** 单竞品活体 Battlecard（last_updated_at 由后端派生） */
export interface Battlecard extends ArtifactBase {
  artifact_type: "battlecard";
  competitor_name: string;
  sections: BattlecardSection[];
  overall_completeness: BattlecardCompleteness;
  last_updated_at?: string | null;
}

export interface S4MonitoringPayload {
  scenario_type: "S4";
  review_period: ReviewPeriod;
  feature_changes: FeatureChange[];
  pricing_changes: PricingChange[];
  messaging_changes: MessagingChange[];
  news_events: NewsEvent[];
  org_changes: OrgChange[];
  threats: MonitoringThreat[];
  opportunities: MonitoringOpportunity[];
  trends: MonitoringTrends;
  monitoring_actions: MonitoringAction[];
  battlecards: Battlecard[];
}

// ============================================================
// S5 — Positioning Strategy
// ============================================================

export type WavePosition = "wave_leader" | "wave_strong_performer" | "wave_contender";

export type MQQuadrant = "mq_leader" | "mq_challenger" | "mq_visionary" | "mq_niche_player";

export interface S5VendorProfile {
  competitor_name?: string;
  ability_to_execute_score: number; // 0-5
  ability_to_execute_rationale?: string;
  completeness_of_vision_score: number; // 0-5
  completeness_of_vision_rationale?: string;
  overview: string;
  strengths: VendorStrength[];
  cautions: VendorCaution[];
  source_refs: SourceRef[];
}

export interface PerceptualAxis {
  attribute?: string;
  low_label?: string;
  high_label?: string;
  scale_max?: number;
  rationale?: string;
}

export interface PlottedBrand {
  competitor_name?: string;
  is_self?: boolean;
  x_score: number;
  y_score: number;
  bubble_size_metric?: number | null;
  confidence: ConfidenceLevel;
  score_rationale?: string;
  source_refs?: SourceRef[];
}

export interface WhiteSpaceZone {
  quadrant: "top_right" | "top_left" | "bottom_right" | "bottom_left" | "center";
  opportunity_description?: string;
  interpretation?: string;
}

export interface ClusterZone {
  brands_in_cluster: string[];
  implication?: string;
}

export interface PerceptualMap extends ArtifactBase {
  artifact_type: "perceptual_map";
  x_axis: PerceptualAxis;
  y_axis: PerceptualAxis;
  plotted_brands: PlottedBrand[];
  white_space?: WhiteSpaceZone[];
  cluster_zones?: ClusterZone[];
  display_watermark?: string;
}

export interface CompetitiveFactor {
  name?: string;
  industry_avg_level: number; // 0-10
}

export interface ValueCurve {
  competitor_name?: string;
  is_self?: boolean;
  factor_levels: Record<string, number>;
  source_refs?: SourceRef[];
}

export interface StrategyCanvas extends ArtifactBase {
  artifact_type: "strategy_canvas";
  competitive_factors: CompetitiveFactor[];
  value_curves: ValueCurve[];
}

export interface ERRCAction {
  factor?: string;
  rationale?: string;
  proposed_level?: number | null;
  buyer_value?: string;
}

export interface ERRCGrid extends ArtifactBase {
  artifact_type: "errc_grid";
  eliminate?: ERRCAction[];
  reduce?: ERRCAction[];
  raise_level?: ERRCAction[];
  create?: ERRCAction[];
}

export interface BlueOceanMove extends ArtifactBase {
  artifact_type: "blue_ocean_move";
  new_value_curve_summary?: string;
  focus_assessment: "focused" | "scattered" | "uncertain";
  focus_rationale?: string;
  divergence_assessment: "divergent" | "overlapping" | "uncertain";
  divergence_rationale?: string;
  compelling_tagline: string;
  target_noncustomers: string[];
}

export interface PositioningStatement {
  target_customer?: string;
  need_or_opportunity?: string;
  product_name?: string;
  product_category?: string;
  key_benefit?: string;
  primary_alternative?: string;
  primary_differentiation?: string;
  confidence: "from_user_brief" | "llm_inferred" | "low_confidence";
}

export interface CategoryStrategy {
  chosen_category?: string;
  why_this_category?: string;
  competitors_implied: string[];
  risk_of_category_choice?: string;
}

export interface S5PositioningPayload {
  scenario_type: "S5";
  vendor_profiles: S5VendorProfile[];
  perceptual_map: PerceptualMap;
  strategy_canvas: StrategyCanvas;
  errc_grid: ERRCGrid;
  blue_ocean_move?: BlueOceanMove | null;
  positioning_statement: PositioningStatement;
  category_strategy: CategoryStrategy;
}

// ============================================================
// API Types
// ============================================================

/** 分析请求 */
export interface AnalysisRequest {
  scenario: Scenario;
  competitors?: CompetitorBasic[];
  industry?: string | null;
  analysis_context: string;
  our_product_name?: string | null;
  our_product_brief?: string | null;
  prior_trace_id?: string | null;
}

/** 竞品基本信息 */
export interface CompetitorBasic {
  name: string;
  company?: string;
  category?: string;
  official_url?: string | null;
}

/** 分析响应 */
export interface AnalysisResponse {
  trace_id: string;
  status: string;
  report?: BaseReport | null;
  error?: string | null;
}

/** 场景推荐请求 */
export interface PickScenarioRequest {
  user_text: string;
}

/** 场景推荐响应 */
export interface PickScenarioResponse {
  scenario: string;
  confidence: string;
  rationale: string;
}

/** Trace 摘要 */
export interface TraceSummary {
  trace_id: string;
  scenario?: string | null;
  status?: string | null;
  started_at?: string | null;
  ended_at?: string | null;
  competitors: string[];
}

/** Trace 列表响应 */
export interface TracesResponse {
  traces: TraceSummary[];
  total: number;
  page: number;
  page_size: number;
}

/** Trace meta.json 摘要（后端为自由 dict，仅列前端消费的字段） */
export interface TraceMeta {
  status?: string;
  started_at?: string;
  ended_at?: string;
  error?: string;
  input?: {
    scenario?: string;
    competitors?: { name: string }[];
    our_product_name?: string;
    industry?: string;
    prior_trace_id?: string;
  };
  [key: string]: unknown;
}

/** 追溯 API 响应（GET /trace/{trace_id}） */
export interface TraceResponse {
  trace_id: string;
  meta?: TraceMeta | null;
  stages: {
    profiles?: unknown;
    analysis?: unknown;
    report?: BaseReport | null;
    feedback?: unknown;
    [key: string]: unknown;
  };
  snapshots: string[];
  log: string;
}

// ============================================================
// Agent Message Types
// ============================================================

/** Agent 间消息 */
export interface AgentMessage {
  from_agent: string;
  to_agent: string;
  message_type: "task" | "result" | "feedback" | "retry";
  payload?: Record<string, unknown>;
  timestamp: string;
  trace_id: string;
}

// ============================================================
// Utility Types
// ============================================================

/** Extract scenario payload type from scenario code */
export type ScenarioPayloadByType<T extends Scenario> =
  T extends "S1"
    ? S1FeatureIterationPayload
    : T extends "S2"
      ? S2MarketEntryPayload
      : T extends "S3"
        ? S3PricingStrategyPayload
        : T extends "S4"
          ? S4MonitoringPayload
          : T extends "S5"
            ? S5PositioningPayload
            : never;

/** Scenario display names */
export const SCENARIO_LABELS: Record<Scenario, string> = {
  S1: "功能迭代",
  S2: "市场进入",
  S3: "定价策略",
  S4: "竞争监控",
  S5: "定位策略",
} as const;

/** Confidence level display config */
export const CONFIDENCE_CONFIG: Record<
  ConfidenceLevel,
  { label: string; color: string }
> = {
  high: { label: "高", color: "tag-green" },
  medium: { label: "中", color: "tag-yellow" },
  low: { label: "低", color: "tag-red" },
} as const;

/** Priority display config */
export const PRIORITY_CONFIG: Record<
  Recommendation["priority"],
  { label: string; color: string }
> = {
  critical: { label: "关键", color: "tag-red" },
  important: { label: "重要", color: "tag-orange" },
  consider: { label: "建议", color: "tag-blue" },
} as const;

/** Timeline display config */
export const TIMELINE_CONFIG: Record<
  Recommendation["timeline"],
  { label: string }
> = {
  immediate: { label: "立即" },
  short_term: { label: "短期" },
  long_term: { label: "长期" },
} as const;
