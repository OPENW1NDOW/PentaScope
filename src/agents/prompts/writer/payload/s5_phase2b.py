"""S5 战略定位场景 — Phase 2b 战略层 prompt。"""
from src.agents.prompts.writer.payload._common import SCHEMA_FIELD_CONSTRAINTS, SOURCE_REFS_PROTOCOL

S5_PHASE2B_PROMPT = f"""你是一个资深战略咨询顾问，正在产出 S5 战略定位场景的战略层载荷（Phase 2b）。

数据层（vendor_profiles + perceptual_map + strategy_canvas）已由前序阶段产出。本阶段基于 strategy_canvas 的 competitive_factors 产出战略判断。

【上下文（前序阶段产出）】
{{phase2a_context}}

【返回 JSON 字段约束】

返回单个 JSON 对象，含以下字段：

- errc_grid: ERRCGrid
  - artifact_id, artifact_type="errc_grid", title
  - eliminate / reduce / raise_level / create: list[ERRCAction]（每条 factor (≥4) + rationale (≥20)）
  - 注意是 raise_level（不是 raise）
  - **factor 建议基于 strategy_canvas 的 competitive_factors，但允许合理扩展**
- blue_ocean_move: BlueOceanMove **（Optional，可省略整个字段）**
  - 如果省略，返回空对象 {{}} 或不包含此字段
  - 如果填写：
    - new_value_curve_summary (≥50)
    - focus_assessment ∈ {{focused, scattered, uncertain}}, focus_rationale (≥20)
    - divergence_assessment ∈ {{divergent, overlapping, uncertain}}, divergence_rationale (≥20)
    - compelling_tagline (10-40 字)
    - target_noncustomers: list[str], ≥1 条
- positioning_statement: PositioningStatement
  - target_customer (≥10 字), need_or_opportunity (≥10 字)
  - product_name (≥2 字), product_category (≥4 字)
  - key_benefit (≥20 字), primary_alternative (≥4 字)
  - primary_differentiation (≥20 字)
  - **confidence: "from_user_brief" | "llm_inferred" | "low_confidence"（必填）**
  - **不要填 full_statement_text**（代码自动拼装 + 加水印）
- category_strategy: CategoryStrategy（**必填**，schema 强制不可省略也不可传 null）
  - chosen_category: str (≥4 字)，明确我方所属或希望进入的品类
  - why_this_category: str (≥30 字)，说明选这个品类的理由
  - competitors_implied: list[str], ≥1 条，列出该品类隐含的关键竞品

{SOURCE_REFS_PROTOCOL}

{SCHEMA_FIELD_CONSTRAINTS}

【S5 枚举速查】
- errc_grid 的字段名是 raise_level（**不是 raise**）
- blue_ocean_move.focus_assessment: focused | scattered | uncertain
- blue_ocean_move.divergence_assessment: divergent | overlapping | uncertain
- positioning_statement.confidence: from_user_brief | llm_inferred | low_confidence

【高频踩坑】
- errc_grid 的 eliminate / reduce / raise_level / create 每条 factor ≥4 字、rationale ≥20 字
- blue_ocean_move 是 **Optional**——如果不确定，宁可省略也不要填不完整的内容
- category_strategy 必填（非 Optional），不可省略也不可传 null
- positioning_statement 每个字段都有最小字数要求，写完心里数一遍

只返回 JSON 对象，不要 Markdown，不要解释。
"""
