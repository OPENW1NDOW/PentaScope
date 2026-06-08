"""28 项 section_type 元信息：标签、关注点、上下文取值路径。

[v3-R20] 必须覆盖 src/schemas/report.py AnalysisSection.section_type Literal 全部 28 项。
"""

# section_type → 章节中文标签（建议默认 heading）
SECTION_LABELS: dict[str, str] = {
    # 通用骨架
    "overview": "总览",
    "executive_overview": "执行总览",
    "background": "研究背景",
    "conclusions_summary": "结论小结",
    # S1 功能迭代
    "feature_matrix_analysis": "功能矩阵分析",
    "vendor_profile_analysis": "竞品档案分析",
    "jtbd_analysis": "JTBD 用户任务分析",
    "roadmap_analysis": "Roadmap 优先级分析",
    # S2 市场进入
    "market_sizing_analysis": "市场规模分析",
    "five_forces_analysis": "五力模型分析",
    "competitive_landscape_analysis": "竞争格局分析",
    "consumer_segments_analysis": "用户细分分析",
    "trends_analysis": "市场趋势分析",
    "entry_strategy_analysis": "进入策略分析",
    # S3 定价策略
    "pricing_baseline_analysis": "定价基线分析",
    "value_drivers_analysis": "价值驱动因素分析",
    "packaging_design_analysis": "Packaging 设计分析",
    "competitive_pricing_analysis": "竞品定价对比分析",
    "pricing_recommendations_analysis": "定价建议分析",
    # S4 持续监控
    "monitoring_overview": "监控周期总览",
    "competitive_moves_analysis": "竞品动作分析",
    "threat_assessment_analysis": "威胁评估分析",
    "opportunity_identification_analysis": "机会识别分析",
    "battlecard_analysis": "Battlecard 分析",
    # S5 战略定位
    "vendor_positioning_analysis": "竞品定位分析",
    "perceptual_map_analysis": "感知地图分析",
    "strategy_canvas_analysis": "战略画布分析",
    "errc_analysis": "ERRC 行动分析",
    "positioning_statement_analysis": "定位陈述分析",
}

# section_type → 关注点提示（写 narrative 时要交付的"所以呢"）
SECTION_FOCUS_HINTS: dict[str, str] = {
    "overview": "对全报告做一段总览，让读者 3 分钟掌握全貌：扫描场景、核心结论、关键数字。",
    "executive_overview": "提炼执行摘要的 5 段为一段连贯叙事，让 C 级读者快速形成判断。",
    "background": "讲清楚行业背景与项目动因，回答 'why now'。",
    "conclusions_summary": "把全报告的关键结论收束到本节，为后续 recommendations 做铺垫。",
    "feature_matrix_analysis": "横向对比加权得分、Tier 1 高重要性差距、我方与竞品的功能身位差异。",
    "vendor_profile_analysis": "逐一描绘每个竞品的 Wave 位置、卖点、注意事项，给出对比的'人格画像'。",
    "jtbd_analysis": "用 JTBD 三段式（Situation-Motivation-Outcome）解读用户为什么选竞品而非我方。",
    "roadmap_analysis": "把 must_build / should_skip / should_differentiate 的清单变成一段决策叙事。",
    "market_sizing_analysis": "讲清楚 TAM/SAM/SOM 的数值依据，标明置信度，给出市场规模判断。",
    "five_forces_analysis": "5 力强度对比 + 综合评估行业吸引力（1-5 分），给出影响进入决策的论点。",
    "competitive_landscape_analysis": "现有玩家的角色（incumbent/challenger/emerging/niche）+ 市场集中度判断。",
    "consumer_segments_analysis": "细分用户群的需求差异 + 哪些 segment 被 underserved。",
    "trends_analysis": "本期最重要的 2-3 个趋势，方向（up/flat/down）、时间窗口、对进入的影响。",
    "entry_strategy_analysis": "推荐进入模式（head_on/niche_focus/etc）的理由 + 关键成功因素 + 风险与节奏。",
    "pricing_baseline_analysis": "我方现状定价模型的优劣 + 竞品定价模型对比。",
    "value_drivers_analysis": "Kano 模型分类 + 哪些 driver 是高重要性 + 它们对定价决策的支撑。",
    "packaging_design_analysis": "推荐 GBB 档位结构 + 锚定 tier + 各档位的价值差异 + 推荐档位为什么选它。",
    "competitive_pricing_analysis": "竞品定价矩阵的横向对比 + pricing_page_audit 8 法则的得分高低。",
    "pricing_recommendations_analysis": "推荐定价的预期 ARR 影响 + rollout 节奏 + 主要风险与缓解。",
    "monitoring_overview": "本期监控周期标签 + 监控竞品名单 + 趋势变化总览。",
    "competitive_moves_analysis": "本期 5 类 changes（feature/pricing/messaging/news/org）的高严重度事件展开。",
    "threat_assessment_analysis": "高 severity × likelihood 的威胁逐一展开，给出 act_now/contingency 分类。",
    "opportunity_identification_analysis": "本期识别的机会 + 推荐 first_step。",
    "battlecard_analysis": "对每个监控竞品的 battlecard 关键 sections 内容展开。",
    "vendor_positioning_analysis": "MQ 二轴评分高的竞品在哪里、低的在哪里、我方位置如何。",
    "perceptual_map_analysis": "二维感知图轴选择理由 + 各品牌位置 + 白空间机会区。",
    "strategy_canvas_analysis": "竞争画布关键因子的水平差异 + 蓝海机会指向。",
    "errc_analysis": "Eliminate / Reduce / Raise / Create 4 类动作各 1-2 条核心建议。",
    "positioning_statement_analysis": "推荐的 positioning statement 一句话拆解 + 与竞品差异点。",
}

# [v3-R20] section_type → 上下文字段取值路径（28 项全覆盖）
# 每个值是 list[str]，每条为 dot-walk 路径（如 "payload.vendor_profiles" / "analysis.swot"）
SECTION_CONTEXT_MAP: dict[str, list[str]] = {
    # 通用
    "overview": ["analysis"],
    "executive_overview": ["analysis", "outline.executive_summary"],
    "background": ["outline.background", "scenario_input"],
    "conclusions_summary": ["outline.conclusions", "outline.recommendations"],
    # S1
    "vendor_profile_analysis": ["payload.vendor_profiles", "analysis.positioning"],
    "feature_matrix_analysis": ["payload.feature_matrix", "analysis.feature_matrix"],
    "jtbd_analysis": ["payload.job_statement", "analysis.user_sentiment"],
    "roadmap_analysis": ["payload.feature_gaps", "payload.roadmap_recommendations"],
    # S2
    "market_sizing_analysis": ["payload.market_sizing"],
    "five_forces_analysis": ["payload.five_forces", "payload.industry_attractiveness_1_5"],
    "competitive_landscape_analysis": ["payload.players", "payload.market_concentration"],
    "consumer_segments_analysis": ["payload.consumer_segments"],
    "trends_analysis": ["payload.key_trends"],
    "entry_strategy_analysis": ["payload.entry_strategy", "payload.competitor_recommendations"],
    # S3
    "pricing_baseline_analysis": ["payload.pricing_baseline"],
    "value_drivers_analysis": ["payload.value_drivers", "payload.feature_classification"],
    "competitive_pricing_analysis": ["payload.competitive_pricing_matrix", "payload.pricing_page_audit"],
    "packaging_design_analysis": ["payload.packaging"],
    "pricing_recommendations_analysis": ["payload.recommendations_summary", "payload.rollout_plan"],
    # S4
    "monitoring_overview": ["payload.review_period", "payload.trends"],
    "competitive_moves_analysis": [
        "payload.feature_changes", "payload.pricing_changes",
        "payload.messaging_changes", "payload.news_events", "payload.org_changes",
    ],
    "threat_assessment_analysis": ["payload.threats"],
    "opportunity_identification_analysis": ["payload.opportunities", "payload.monitoring_actions"],
    "battlecard_analysis": ["payload.battlecards"],
    # S5
    "vendor_positioning_analysis": ["payload.vendor_profiles"],
    "perceptual_map_analysis": ["payload.perceptual_map"],
    "strategy_canvas_analysis": ["payload.strategy_canvas", "payload.errc_grid", "payload.blue_ocean_move"],
    "errc_analysis": ["payload.errc_grid"],
    "positioning_statement_analysis": ["payload.positioning_statement", "payload.category_strategy"],
}
