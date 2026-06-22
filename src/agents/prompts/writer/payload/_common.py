"""5 场景 payload 共用的溯源约束块 + schema 字段约束块。"""

SOURCE_REFS_PROTOCOL = """
【溯源 URL 强约束（编造 URL 视为严重违规）】

1. 任何 evidence_url / SourceRef.url / source_url 字段，**只能填**输入的 profiles_source_urls 列表中实际存在的 URL。
2. profiles_source_urls 按竞品分组，论述哪个竞品时只能引用该竞品名下的 URL，绝不跨竞品引用。
3. SourceRef 对象格式（source_refs 字段下的每条）：
   {{
     "url": "必须来自 profiles_source_urls，至少 8 字符",
     "title": "未知时填空字符串",
     "source_type": "official_website | third_party_review | industry_report | news | user_review | regulatory | other（不确定填 other）",
     "accessed_at": "未知时省略"
   }}
4. 如果某条目（如 ObservedCompetitorTier、FeatureChange、ConsumerSegment 等 source_refs 必填的）找不到 ≥1 个合法 URL，**不要生成该条目**。宁缺勿滥。
"""


SCHEMA_FIELD_CONSTRAINTS = """
【字段长度与数量硬约束（违反将被 schema 拦截，重试浪费 LLM quota）】

通用约束（适用于所有 scenario payload）：
- 所有 `artifact_id` 字段：3-40 字符（**严禁超长**），用 ASCII + 短横线/下划线，例：`s1-vendor-飞书`、`s4-change-001`
- 所有 SourceRef/DataSource 的 `url`：≥8 字符的合法 URL（来自 profiles_source_urls）
- 所有 `point` / `evidence` 字段：≥10 字符
- 所有 `narrative` / `data_collection_approach`：≥80-300 字符（不同字段不同，遇到 schema 错误请按报错调整）
- 所有 `*_brief` 含 list 的 (`key_findings_brief` / `implications` / `core_thesis`)：注意 max 上限（120-250 字符），不要写小作文

S1 专属（vendor profile + feature matrix 高频踩坑）：
- `vendor_profiles[*].strengths`: list 长度 **2-5 条**（少于 2 / 多于 5 都拒绝）
- `vendor_profiles[*].cautions`: list 长度 **1-4 条**
- `vendor_profiles[*].one_line_pitch`: 字符串 10-120 字符
- `vendor_profiles[*].best_fit_for`: 字符串 ≥10 字符
- `feature_matrix.competitors`: list 长度 ≥2
- `feature_matrix.categories[*].features`: list 长度 ≥1
- 雷达 5 维度：feature_breadth / usability / cost_effectiveness / stability / design_quality 取值 0-5（浮点）

宁可少给条目（在 list min 之内），也不要凑数堆短字符串触发 schema 拒绝。
"""
