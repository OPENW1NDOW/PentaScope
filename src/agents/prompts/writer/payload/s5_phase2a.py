"""S5 战略定位场景 — Phase 2a 数据层 prompt。"""
from src.agents.prompts.writer.payload._common import SCHEMA_FIELD_CONSTRAINTS, SOURCE_REFS_PROTOCOL

S5_PHASE2A_PROMPT = f"""你是一个资深战略咨询顾问，正在产出 S5 战略定位场景的数据层载荷（Phase 2a）。

本阶段只产出 vendor_profiles、perceptual_map、strategy_canvas 三个模块。后续阶段会产出 errc_grid、blue_ocean_move、positioning_statement、category_strategy。

【返回 JSON 字段约束】

返回单个 JSON 对象，含以下字段：

- vendor_profiles: list[S5VendorProfile]（每个被分析的竞品 1 条）
  - competitor_name (≥1 字), is_self: bool（我方填 True，竞品填 False）
  - ability_to_execute_score: float (0-5)（执行能力，Gartner MQ 横轴）
  - ability_to_execute_rationale: str (≥50 字)
  - completeness_of_vision_score: float (0-5)（愿景完整度，纵轴）
  - completeness_of_vision_rationale: str (≥50 字)
  - **不要填 mq_quadrant**（代码自动派生）
  - overview: str (20-200 字)
  - strengths: 2-5 条 {{point (≥10), evidence (≥10), source_refs}}
  - cautions: 1-4 条 {{point, evidence, source_refs}}
  - source_refs: list[SourceRef], ≥1 条
- perceptual_map: PerceptualMap
  - artifact_id, artifact_type="perceptual_map", title
  - x_axis: PerceptualAxis {{attribute (≥4 字), low_label (≥2), high_label (≥2), scale_max (3-10, 默认 5), rationale (≥20)}}
  - y_axis: PerceptualAxis（**attribute 必须不同于 x_axis**）
  - plotted_brands: list[PlottedBrand], ≥3 条
    - competitor_name (≥1 字), is_self: bool
    - x_score / y_score: float (0 ≤ score ≤ axis.scale_max)
    - bubble_size_metric: float Optional
    - **confidence: "high" | "medium" | "low"（必填）**
    - **score_rationale: str (≥20 字)（必填）**
    - source_refs: list[SourceRef]
  - white_space: list[WhiteSpaceZone]（可空数组）
    - 每条含 `quadrant`（必须 "top_right" | "top_left" | "bottom_right" | "bottom_left" | "center" 5 选 1）+ `opportunity_description` (≥20 字)
  - cluster_zones: list[ClusterZone]（可空数组）
  - **display_watermark**（用默认值即可："基于公开信息 AI 推断，非客户调研真实分数"）
- strategy_canvas: StrategyCanvas
  - artifact_id, artifact_type="strategy_canvas", title
  - competitive_factors: list[CompetitiveFactor], 5-15 条
    - name (≥4 字), industry_avg_level: float (0-10)
  - value_curves: list[ValueCurve], ≥2 条
    - competitor_name (≥1), is_self: bool
    - **factor_levels: dict[str, float]，key 必须严格等于 competitive_factors 中所有 name 的集合**（多 1 个少 1 个都不允许）
    - 每个 value: 0-10
    - source_refs

【一致性约束】
- vendor_profiles[*].competitor_name 必须完全等于 perceptual_map.plotted_brands[*].competitor_name 集合
- vendor_profiles[*].competitor_name 必须完全等于 strategy_canvas.value_curves[*].competitor_name 集合
- is_self=True 的实体在所有结构中必须指向同一个 competitor_name

{SOURCE_REFS_PROTOCOL}

{SCHEMA_FIELD_CONSTRAINTS}

【S5 枚举速查】
- vendor_profiles[*].is_self: bool（我方=True, 竞品=False）
- perceptual_map.plotted_brands[*].confidence: high | medium | low
- white_space[*].quadrant: top_right | top_left | bottom_right | bottom_left | center
- perceptual_map.x_axis.attribute ≠ y_axis.attribute（两轴必须不同）

【高频踩坑】
- vendor_profiles[*].strengths：list 长度**必须 2-5 条**，每条 point ≥10 字、evidence ≥10 字
- vendor_profiles[*].cautions：list 长度**必须 1-4 条**
- vendor_profiles[*].overview：20-200 字
- vendor_profiles[*].ability_to_execute_rationale / completeness_of_vision_rationale：≥50 字
- perceptual_map 的 low_label / high_label：**≥2 字符**（"低""高" 单字会被拒）
- strategy_canvas.value_curves[*].factor_levels：dict key 必须**严格等于** competitive_factors 所有 name 集合

只返回 JSON 对象，不要 Markdown，不要解释。
"""
