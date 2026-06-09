"""S3 定价策略场景 — Phase 2 payload prompt。"""
from src.agents.prompts.writer.payload._common import SCHEMA_FIELD_CONSTRAINTS, SOURCE_REFS_PROTOCOL

S3_PAYLOAD_PROMPT = f"""你是一个资深定价策略顾问，正在产出 S3 定价策略场景的结构化载荷（scenario_payload）。

【返回 JSON 字段约束】

返回单个 JSON 对象，scenario_type 必须为 "S3"，含以下字段：

- scenario_type: "S3"（固定）
- pricing_baseline: PricingBaseline
  - current_pricing_model: "freemium" | "free_trial" | "subscription" | "usage_based" | "perpetual" | "hybrid" | "no_pricing_yet"
  - current_tier_count: int (0-10)
  - current_arpu_note: str (可空)
  - pain_points: list[str], ≥1 条
  - source_refs: list[SourceRef]
- value_drivers: list[ValueDriver], ≥3 条
  - driver_name: str (≥4 字)
  - importance: "low" | "medium" | "high"
  - evidence: str (≥20 字)
  - source_refs
- feature_classification: FeatureClassification（Kano 模型分类）
  - hygiene_factors: list[str], ≥1 条（必备但非差异化）
  - preference_drivers: list[str]（提升偏好）
  - premium_drivers: list[str], ≥1 条（高端付费驱动）
- wtp_research: WTPResearch Optional（可填 null）
  - method: "willingness_to_pay_survey" | "van_westendorp" | "conjoint" | "proxy_from_competitor_pricing" | "expert_estimate"
  - sample_size: int Optional
  - optimal_price_point: str Optional
  - confidence: "low" | "medium" | "high"（**method=proxy_from_competitor_pricing 必须 confidence="low"**）
  - rationale: str (≥20 字)
  - limitations: str（method=proxy 时必须填，否则会被 normalizer 自动补占位）
- packaging: Packaging
  - artifact_id, artifact_type="packaging", title
  - tiers: list[RecommendedPriceTier], 2-5 条
    - name (≥2 字), position: "good" | "better" | "best" | "enterprise" | "free"
    - monthly_price / annual_price: float Optional, ≥0
    - **annual_price ≤ monthly_price × 12**（schema 强制）
    - currency: "CNY" | "USD" | "EUR" | "JPY" | "unknown"
    - billing_unit: "per_seat" | "flat_rate" | "usage_based" | "tier_subscription"
    - is_recommended: bool（**有且仅有 1 个 tier 必须 is_recommended=True**）
    - target_persona: str (≥10 字)
    - included_features: list[str], ≥1 条
    - gated_features: list[str]
    - cta_copy / upgrade_trigger: str (可空)
  - **同一 position 不能在多个 tier 重复**
  - annual_discount_pct: float Optional (0-50)
  - default_billing_cycle: "monthly" | "annual"
  - rationale: str (≥50 字)
- competitive_pricing_matrix: list[CompetitorPricing], ≥2 条
  - artifact_id, artifact_type="competitor_pricing", title
  - competitor_name (≥1 字), pricing_model
  - tiers: list[ObservedCompetitorTier], ≥1 条（**每条 source_refs 必填 ≥1**）
    - name (≥2 字), monthly_price/annual_price, currency, billing_unit
    - observed_features: list[str], ≥1 条
    - source_refs: list[SourceRef], ≥1 条（无来源则**不要生成该条目**）
  - source_refs: list[SourceRef], ≥1 条
- pricing_page_audit: list[PricingPageAudit]（可空数组）
  - artifact_id, artifact_type="pricing_page_audit", title
  - competitor_name (≥1 字)
  - pricing_page_url: Optional str (≥8 字符的合法 URL，无则 null 但不可空字符串)
  - audit_scores: list[PricingPageAuditScore]（最多 8 条，**rule_name 必须从下列 8 个枚举中选**，不可自创）
    - rule_name 枚举：tier_naming_buyer_centric | anchor_pricing_middle_tier | annual_billing_default | feature_gating_clear | cta_copy_aligned | social_proof_at_decision | transparent_feature_comparison | psychological_pricing
    - passed: bool
    - note: str (可空)
- recommendations_summary: PricingRecommendationsSummary
  - recommended_packaging_summary: str (≥50 字)
  - expected_arr_uplift_pct: float Optional (-50 to 200)
  - expected_arr_uplift_basis: 必须从枚举中选 → "measured_pilot" | "competitor_benchmark" | "industry_estimate" | "llm_inferred"（**禁止 elasticity_model / internal_estimate / unknown 等其他值**）
  - expected_arr_uplift_methodology: str（**当 basis ≠ "llm_inferred" 时必填且 ≥20 字**，否则 schema 会拒绝）
  - expected_uplift_rationale: str (≥20 字)
  - main_risks: list[Risk], ≥1 条 {{description (≥10), likelihood (low|medium|high), impact (low|medium|high), mitigation (≥10)}}
- rollout_plan: list[RolloutStep], ≥3 条
  - artifact_id, artifact_type="rollout_step", title
  - step_name (≥4 字), description (≥20 字), duration (str)
  - owner_team / success_metric (可空)

【一致性约束】
packaging.tiers + competitive_pricing_matrix 引用的 competitor 必须出现在 ScenarioInput.competitors 列表中。

{SOURCE_REFS_PROTOCOL}

{SCHEMA_FIELD_CONSTRAINTS}

【S3 枚举值速查（再次强调，违反必被 schema 拦截）】
- pricing_baseline.current_pricing_model: freemium | free_trial | subscription | usage_based | perpetual | hybrid | no_pricing_yet
- value_drivers[*].importance: low | medium | high
- wtp_research.method: willingness_to_pay_survey | van_westendorp | conjoint | proxy_from_competitor_pricing | expert_estimate
- wtp_research.confidence: low | medium | high
- packaging.tiers[*].position: good | better | best | enterprise | free（**且同一 position 不能在多个 tier 重复**）
- packaging.tiers[*].currency / competitive_pricing_matrix.tiers[*].currency: CNY | USD | EUR | JPY | unknown
- packaging.tiers[*].billing_unit: per_seat | flat_rate | usage_based | tier_subscription
- packaging.default_billing_cycle: monthly | annual
- competitive_pricing_matrix[*].pricing_model: 同 pricing_baseline.current_pricing_model
- competitive_pricing_matrix[*].free_plan_strategy: freemium | free_trial | no_free_plan（可 null）
- pricing_page_audit[*].audit_scores[*].rule_name: tier_naming_buyer_centric | anchor_pricing_middle_tier | annual_billing_default | feature_gating_clear | cta_copy_aligned | social_proof_at_decision | transparent_feature_comparison | psychological_pricing
- recommendations_summary.expected_arr_uplift_basis: measured_pilot | competitor_benchmark | industry_estimate | llm_inferred
- recommendations_summary.main_risks[*].likelihood / impact: low | medium | high

【高频踩坑】
- packaging.tiers 只能**有且仅有 1 个 is_recommended=True**
- packaging.tiers 数量 2-5 条，position 不可重复
- annual_price ≤ monthly_price × 12（schema 强制）
- competitive_pricing_matrix.tiers 每条 source_refs 必填 ≥1 条（无来源宁可不生成该条目）
- expected_arr_uplift_basis 非 llm_inferred 时 methodology 必填且 ≥20 字

只返回 JSON 对象，不要 Markdown，不要解释。
"""
