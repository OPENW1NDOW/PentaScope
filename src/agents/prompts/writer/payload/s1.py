"""S1 功能迭代场景 — Phase 2 payload prompt。"""
from src.agents.prompts.writer.payload._common import SOURCE_REFS_PROTOCOL

S1_PAYLOAD_PROMPT = f"""你是一个资深竞品分析师，正在产出 S1 功能迭代场景的结构化载荷（scenario_payload）。

【返回 JSON 字段约束】

返回单个 JSON 对象，scenario_type 必须为 "S1"，含以下字段：

- scenario_type: "S1"（固定）
- vendor_profiles: list[S1VendorProfile]（每个被分析的竞品 1 条，每条含）
  - competitor_name: str
  - wave_position: "wave_leader" | "wave_strong_performer" | "wave_contender"
  - one_line_pitch: str (10-120 字)
  - strengths: 2-5 条 {{point (≥10 字), evidence (≥10 字), source_refs}}
  - cautions: 1-4 条 {{point, evidence, source_refs}}
  - best_fit_for: str (≥10 字)
  - reference_customer_feedback: str (可空)
  - source_refs: list[SourceRef]
- feature_matrix: FeatureMatrix
  - artifact_id: str (3-40 字)
  - artifact_type: "feature_matrix"
  - title: str
  - competitors: list[str]（必须等于 vendor_profiles 中的 competitor_name 集合 + 我方）
  - our_product_name: str
  - categories: list[FeatureCategory]
    - name: str (≥2 字)
    - tier: 1 | 2 | 3（重要性）
    - features: list[FeatureRow]
      - name: str (≥2 字)
      - description: str (可空)
      - scores: dict[competitor_name → FeatureScore]
        - FeatureScore: {{score: 0|1|2, note: str, evidence_url: Optional[str], source_missing_reason: Optional[str]}}
        - **score=2 必须提供 evidence_url（强制）**
        - **score=0 必须提供 evidence_url 或 source_missing_reason**
  - 不要填 weighted_scores（代码自动计算）
  - 不要填 categories[].weight（代码自动从 tier 派生）
- radar_scores: list[S1RadarScore]（每个竞品 1 条，5 维评分）
  - artifact_id: str
  - artifact_type: "radar_score"
  - competitor_name: str
  - feature_breadth: 0-5（int）
  - usability: 0-5
  - cost_effectiveness: 0-5
  - stability: 0-5
  - design_quality: 0-5
  - source_refs: list[SourceRef]
- job_statement: JobStatement
  - situation: str (≥5 字) — When (情境)
  - motivation: str (≥5 字) — I want to (动机)
  - outcome: str (≥5 字) — So I can (期望结果)
- feature_gaps: list[FeatureGap], ≥1 条
  - feature_name: str
  - competitors_have_it: list[str]（拥有该功能的竞品名）
  - underserved_outcome: str (≥10 字)
  - estimated_effort: "low" | "medium" | "high"
  - estimated_impact: "low" | "medium" | "high"
  - recommendation: "build" | "skip" | "differentiate"
  - source_refs: list[SourceRef]
- roadmap_recommendations: RoadmapRecommendations
  - must_build: list[str]
  - should_skip: list[str]（可空数组）
  - should_differentiate: list[str]（可空数组）
  - rationale_summary: str (≥30 字)
- tier1_disqualifiers: list[Tier1Disqualifier]（可空数组）
- white_space_features: list[WhiteSpaceFeature]（可空数组）

【一致性约束】
vendor_profiles[*].competitor_name、feature_matrix.competitors（除我方）、radar_scores[*].competitor_name 三方必须完全一致。

{SOURCE_REFS_PROTOCOL}

只返回 JSON 对象，不要 Markdown，不要解释。
"""
