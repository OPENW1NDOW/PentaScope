"""5 场景共用的 outline 约束块。每场景 prompt 的尾部固定附加该块。"""

OUTLINE_FIELDS_HARD_CONSTRAINT = """
【返回 JSON 字段约束（必须严格满足，否则将被拒绝）】

返回单个 JSON 对象，含以下 19 个字段，绝对禁止出现其他顶层字段：

- title (str, 12-100 字)：报告标题。要求：(1) 如涉及时间范围必须与当前实际时间一致，不得编造未来/过去不存在的时间 (2) 不得出现内部场景代号如 S1/S2/S3/S4/S5 (3) 应包含核心分析对象（竞品名或行业）(4) 风格多样化，不要总是"XX竞品功能迭代分析报告"这种死板格式
- subtitle (str, 0-118 字)：副标题，可空字符串
- at_a_glance (list[str], 3-6 条)：一眼看懂的最关键 3-6 条结论，每条 20-60 字
- executive_summary (object)：
  - context (str, 200-500 字)：why now，行业/竞争背景
  - core_thesis (str, 100-350 字)：核心判断（清晰的总论，可多维度展开）
  - key_findings_brief (list[str], 2-4 条)：3 段式之外的关键发现摘要，每条 ≥30 字
  - implications (str, 250-700 字)：对我方的影响与意义
  - path_forward (list[str], 1-3 条)：下一步行动方向（高度概括）
- background (str, 220-1480 字)：研究背景（市场/技术/竞争脉络）
- scope (object)：
  - time_window (str, 必填)：研究时间窗口，如 "2025 Q3 - 2026 Q2"
  - regions (list[str])：覆盖地区，可空数组
  - exclusions (list[str])：明确不在研究范围的事项，可空数组
- methodology (object)：
  - data_collection_approach (str)：**该字段会被 Phase 4 代码合成覆盖，请填一个占位字符串如 "由代码合成" 即可，不要花精力写**
  - evaluation_criteria (list[str], ≥3 条)：评估口径
  - limitations (list[str], ≥2 条)：研究局限
  - sample_size_note (str, ≥85 字)：样本量与代表性说明
- key_findings (list[Finding], 3-6 条)：每条 {statement, evidence, implication} 三段式，每段 ≥25 字
- recommendations (list[Recommendation], ≥3 条)：每条 {action, target_role, priority, timeline, rationale}
  - action (str, ≥25 字)
  - target_role (str)：执行角色
  - priority (str): "critical" | "important" | "consider"
  - timeline (str): "immediate" | "short_term" | "long_term"
  - rationale (str, ≥25 字)
- conclusions (str, 220-1480 字)：研究结论

绝对不要返回以下字段（由后续阶段或代码处理）：
- scenario_payload（Phase 2 LLM 单独产出）
- analysis_sections（Phase 3 LLM 单独产出）
- swot（Phase 4 代码透传 analysis.swot）
- metadata（Phase 4 代码构造）
- appendix（保留默认值）
- scope.competitors（Phase 4 代码代填）

只返回上述 19 个字段的 JSON，绝不要 Markdown、绝不要解释文本、绝不要额外字段。
"""
