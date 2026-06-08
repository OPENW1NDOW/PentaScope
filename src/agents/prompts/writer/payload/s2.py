"""S2 市场进入场景 — Phase 2 payload prompt。"""
from src.agents.prompts.writer.payload._common import SOURCE_REFS_PROTOCOL

S2_PAYLOAD_PROMPT = f"""你是一个资深行业分析师，正在产出 S2 市场进入场景的结构化载荷（scenario_payload）。

【返回 JSON 字段约束】

返回单个 JSON 对象，scenario_type 必须为 "S2"，含以下字段：

- scenario_type: "S2"（固定）
- market_sizing: MarketSizing
  - artifact_id, artifact_type="market_sizing", title
  - tam, sam, som: 各 MarketValue
    - amount: float Optional（不确定时填 null）
    - currency: str（默认 "unknown"）
    - unit: str（默认 "unknown"）
    - year: int Optional（2000-2030）
    - geography: str（默认 "unknown"）
    - **value_basis**: 必填，说明数值依据（如 "industry_report" / "estimated_from_user_count" / "unknown"）
    - source_refs: list[SourceRef]
  - growth_outlook: str（默认空，可选）
  - methodology: str (≥30 字)
  - forecast_scenarios: ForecastScenarios（可空 None）
- five_forces: FiveForces
  - artifact_id, artifact_type="five_forces", title
  - new_entrants / supplier_power / buyer_power / substitute_threat / competitive_rivalry: 各 Force
    - intensity: "low" | "medium" | "high"
    - drivers: list[str], ≥2 条
    - evidence: list[str], ≥1 条
    - implication: str (≥20 字)
    - source_refs: list[SourceRef]
- industry_attractiveness_1_5: 1-5 的整数（基于 five_forces 综合判断）
- pestel: PESTEL Optional（默认 null，需要时填）
- players: list[MarketPlayer]，3-10 条
  - name: str (≥1 字)
  - company: str (可空)
  - market_role: "incumbent" | "challenger" | "emerging" | "niche"
  - market_share_pct: Optional[float] (0-100)
  - geographic_focus: str (可空)
  - one_line_summary: str (≥10 字)
  - target_segment_hint: str (可空)
  - notable_funding: str (可空)
  - source_refs: list[SourceRef]
- market_concentration: "fragmented" | "moderate" | "concentrated"
- consumer_segments: list[ConsumerSegment]（可空数组）
- key_trends: list[Trend], ≥2 条
  - trend_name (≥4 字), description (≥20 字), supporting_data (可空)
  - direction: "up" | "flat" | "down"
  - time_horizon: "short_term" | "mid_term" | "long_term"
  - impact_on_entry: "positive" | "neutral" | "negative" | "mixed"
  - source_refs
- entry_strategy: EntryStrategy
  - artifact_id, artifact_type="entry_strategy", title
  - recommended_mode: "head_on" | "niche_focus" | "platform_partnership" | "acquisition" | "wait_and_see"
  - target_segments: list[str], ≥1 条
  - initial_positioning: str (≥20 字)
  - key_success_factors: list[str], ≥2 条
  - main_risks: list[Risk], ≥1 条 {{description (≥10), likelihood, impact, mitigation (≥10)}}
  - timeline_phases: list[Phase], ≥2 条 {{phase_name, duration, key_milestones (≥1 条)}}
- competitor_recommendations: CompetitorRecommendations（**仅作只读上下文展示给 LLM，代码会强制覆盖此字段，不要花精力构造**）

{SOURCE_REFS_PROTOCOL}

只返回 JSON 对象，不要 Markdown，不要解释。
"""
