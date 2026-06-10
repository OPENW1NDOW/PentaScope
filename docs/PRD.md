# PRD: PentaScope — AI 驱动的竞品分析 Agent 协作系统

> **文档版本**：V4.0
> **最后更新**：2026-06-10
> **作者**：OPENW1NDOW
> **项目类型**：面向产品经理 / 市场分析师的多 Agent 竞品分析系统

---

## V4.0 变更日志（相对 V3.0 的核心调整）

V3.0 是项目立项之初的产品设想，V4.0 是反映 06-10 实际产品形态的对齐版本。8 项核心调整：

1. **输入入口升级**：`CompetitorInput`（4 字段）→ `ScenarioInput`（5 场景分支校验，S2 输入行业不输入竞品）
2. **报告 schema 重构**：`FinalReport`（4 段执行摘要）→ `BaseReport` + `scenario_payload` discriminated union（5 段执行摘要 + 5 场景独立 Payload）
3. **Agent 数量与编排**：4 Agent 单一流水线 → 5 Agent（增加 S2 场景前置 `recommender`） + Writer 内部 4 阶段编排
4. **数据源整合**：8 个独立数据源（App Store / 36氪 / 微博 等）→ Tavily 单源（一次调用直返带正文）+ 占位降级
5. **新增产品能力**：「AI 帮我选场景」按钮、Markdown / HTML 报告导出、全链路 trace_id 追溯、Plotly 5 场景可视化
6. **质量评分细化**：单一评分 → 三项加权（source_coverage / confidence_avg / inspector_pass_rate） + placeholder warnings 强制 cap 0.5 + raw_quality_score 保留 cap 前真实分
7. **反馈闭环精化**：抽象「打回上游」 → `feedback.issues[].agent` 字段精确路由 + `retry_count` 计数 + `WriterRouteToCollector / Writer / End` 三类自定义异常
8. **S4 增量监控落地**：从 V3.0 「不包含」清单移出，通过 `prior_trace_id` 读取上次基线 + 路径穿越白名单防护实现

---

## 1. 需求背景与目标

### 1.1 背景

企业产品团队在进行竞品分析时，需经历"信息搜集 → 功能对比 → 用户评价整理 → SWOT 分析 → 结构化报告输出"多个环节。该流程存在三个核心问题：

- **效率低**：单次完整竞品分析耗时 2-3 个工作日，其中 70% 时间用于信息搜集和整理
- **质量不稳定**：分析结果高度依赖分析师个人经验和行业认知，同一竞品不同人分析结论差异大
- **场景不匹配**：不同分析目的（功能对标 / 市场进入 / 定价决策 / 持续监控 / 战略定位）需要不同的报告形态，通用模板难以兼顾

### 1.2 目标

构建一个多 Agent 协作的自动化竞品分析系统，按场景产出咨询级竞品报告：

| 目标 | 量化指标 |
|------|----------|
| 效率提升 | 端到端分析时间从 2-3 天缩短至 10 分钟以内 |
| 场景适配 | 5 个分析场景按业界标杆框架组织，每场景独立 Schema 与可视化 |
| 输出一致性 | Schema 驱动 + Pydantic 强约束，消除人为差异 |
| 可追溯性 | 每条分析结论绑定原始数据来源 URL，全链路 trace_id 串联 |
| 报告交付 | 支持 Markdown / HTML 双格式导出，HTML 全内嵌资源支持断网使用 |

### 1.3 设计取向

本项目的核心设计维度：

| 维度 | 关键要求 |
|------|----------|
| 多 Agent 协作与输出可信度 | 角色清晰、结构化消息、反馈闭环、信息溯源 |
| 技术深度与工程完整度 | 端到端链路、可观测性（全链路 trace_id）、错误恢复 |
| 业务价值与产品体验 | 5 场景能力、AI 辅助选型、报告导出、Plotly 可视化 |
| 代码质量与文档 | 模块化、文档齐全、Git 规范 |
| 合规与安全 | 数据采集合规、隐私安全、HTML 导出 XSS 防护、prior_trace_id 路径穿越白名单 |

### 1.4 5 场景能力详述

| 场景 | 适用情境 | 核心问题 | 输入特点 |
|------|---------|---------|---------|
| **S1 功能迭代** | 已有产品看竞品功能差距 | 「我们功能落后在哪 / 下一版迭代补什么」 | 必填我方产品 + 2-10 个竞品 |
| **S2 市场进入** | 还没产品看赛道格局 | 「该不该进 / 怎么进 / 跟谁竞争」 | 必填行业 / 赛道，竞品可选（recommender 自动推荐 Top 3-5 玩家） |
| **S3 定价策略** | 调价 / 重新打包 | 「该卖多少钱 / 怎么打包 / 套餐怎么切」 | 必填我方产品 + 2-10 个竞品 |
| **S4 持续监控** | 季度跟踪 / 战卡更新 | 「这段时间竞品有什么变化 / 哪些威胁要响应」 | 必填竞品；可选 `prior_trace_id` 启动增量模式 |
| **S5 战略定位** | 重新定位 / 品牌升级 | 「我该往哪定位 / 怎么差异化」 | 必填我方产品 + 2-10 个竞品 |

每个场景产出 BaseReport 通用骨架（13 元素）+ 场景专属 Payload，详见 § 4 Schema 与 § 7.5 产品亮点矩阵。

---

## 2. 用户痛点分析

### 2.1 使用角色

| 角色 | 描述 | 使用频率 | 技术水平 |
|------|------|----------|----------|
| **产品经理**（主要） | 负责产品规划，需要功能对标、定价决策、定位评估 | 每周 1-2 次 | 非技术，熟悉业务 |
| **市场分析师**（次要） | 负责行业研究 / 市场进入评估 | 每月 2-3 次 | 非技术，熟悉数据 |
| **战略分析师**（次要） | 负责战略定位、竞争监控、季度战卡 | 每月 1 次 | 非技术，熟悉战略框架 |
| **投资分析师**（次要） | 投资标的赛道格局调研 | 不定期 | 非技术，熟悉财务 |

### 2.2 痛点矩阵（按场景维度）

| 场景 | 用户角色 | 问题场景 | 期望结果 |
|------|---------|---------|---------|
| S1 | 产品经理 | 看竞品功能 8+ 个网站逐一搜，不同分析师维度还不一致 | 输入竞品名称，10 分钟内获得统一矩阵 + 雷达图 + 功能差距清单 |
| S2 | 市场 / 投资分析师 | 准备进新赛道但不知道谁是 Top 玩家、市场空间多大 | 输入行业关键词，自动推荐 Top 3-5 玩家 + TAM/SAM/SOM + Porter 五力 |
| S3 | 产品经理 | 调价无参照系，竞品定价页要逐个翻 | 自动汇总竞品 GBB 套餐 + 价值驱动分析 + ARR 提升预测 |
| S4 | 战略分析师 | 季度战卡每次手动更新，没有上次基线无法做增量对比 | 填上次 trace_id 自动 diff 5 类变更（功能 / 定价 / 营销 / 新闻 / 组织） |
| S5 | 战略分析师 | 定位评估靠主观判断，没有 Magic Quadrant 这类视觉抓手 | 自动产出 MQ + Perceptual Map + Strategy Canvas + 6 位定位陈述模板 |

### 2.3 关键解法

针对上述痛点，本系统的解法策略：

1. **5 Agent 协作**：S2 场景前置 `recommender` 推荐头部玩家，其余 4 场景共用 `collector → analyzer → writer → inspector` 流水线
2. **场景化 Schema**：BaseReport 通用骨架 + 5 套场景 Payload（discriminated union），各场景按业界框架组织（Forrester Wave / Gartner MQ / Porter 五力 / GBB / Blue Ocean）
3. **反馈闭环**：质检 Agent 按 `issue.agent` 字段路由打回上游修正，`retry_count + 1` 直至 `max_retries` 强制结束
4. **全链路溯源**：`SourceRef` 跨场景统一命名，每条结论绑定 URL；trace_id 串联日志 + 中间产物 + 报告 metadata
5. **辅助产品能力**：「AI 帮我选场景」LLM 推断 + Markdown / HTML 双格式导出 + Plotly 5 场景图表 + 执行追溯面板

---

## 3. 名词解释

| 术语 | 定义 |
|------|------|
| **Agent** | 基于 LLM 的自主任务执行单元，具有独立的角色定义、输入输出格式和工具调用能力 |
| **Schema** | 预定义的 Pydantic 数据结构规范，约束 Agent 的输出格式和字段完整性 |
| **ScenarioInput** | 5 场景统一输入 schema，按 `scenario` 字段分支校验必填字段 |
| **BaseReport** | 5 场景共用的报告通用骨架（13 通用元素：title/subtitle/at_a_glance/executive_summary/...） |
| **scenario_payload** | discriminated union 字段，按 `scenario_type` 自动派发到 5 套场景 Payload |
| **Payload** | 场景专属数据载荷（S1FeatureIterationPayload / S2MarketEntryPayload / ...） |
| **Artifact** | 报告中可被 `AnalysisSection.artifact_refs` 引用的产物（feature_matrix / perceptual_map 等） |
| **SourceRef** | 跨场景统一溯源对象（url + title + accessed_at + source_type） |
| **DataSource** | 报告级数据源汇总（含 confidence 字段，appendix.data_sources_full / metadata.data_sources 使用） |
| **trace_id** | 北京时间格式 `YYYYMMDD-HHMMSS-<6hex>`，串联一次分析的全链路日志与中间产物 |
| **反馈闭环** | 质检 Agent 按 `issue.agent` 字段决定打回 collector / analyzer / writer，`retry_count + 1` |
| **Writer 4 阶段** | outline（LLM）→ payload（LLM）→ narrative（LLM 并行）→ assemble（0 LLM 代码合成） |
| **quality_score** | 报告质量评分，三项加权（source_coverage + confidence_avg + inspector_pass_rate） |
| **placeholder warnings** | writer 占位降级触发的标记，会强制 cap quality_score 到 0.5 |
| **raw_quality_score** | cap 前的初始加权分，KPI 卡显示供对比 |
| **DAG** | 有向无环图，描述 Agent 间任务流转（含质检→上游的环路） |
| **SWOT** | Strengths / Weaknesses / Opportunities / Threats 战略分析框架 |
| **Forrester Wave** | Forrester 公司的供应商评估框架（leader / strong_performer / contender 三档） |
| **Gartner MQ（Magic Quadrant）** | Gartner 二维评估（Ability to Execute × Completeness of Vision，4 象限） |
| **Porter 五力** | 新进入者 / 供应商议价权 / 买家议价权 / 替代品威胁 / 现有竞争（low/medium/high） |
| **TAM / SAM / SOM** | Total / Serviceable / Serviceable Obtainable Market 三层市场规模 |
| **PESTEL** | Political / Economic / Social / Technology / Environmental / Legal 宏观环境 |
| **GBB（Good-Better-Best）** | 三层套餐定价法（强制 1 个 is_recommended） |
| **WTP（Willingness to Pay）** | 支付意愿研究（含 conjoint / van_westendorp / proxy 等方法） |
| **JTBD（Jobs To Be Done）** | 用户任务驱动的需求分析框架 |
| **Battlecard** | 销售战卡，含 FIA 三元组 / proof points / objection handling 等 |
| **FIA（Fact-Impact-Act）** | Klue 战卡情报三元组（fact 必填，impact + act Optional） |
| **Perceptual Map** | 二维感知地图（X/Y 轴各 attribute + low/high 标签 + 品牌散点） |
| **Strategy Canvas** | Blue Ocean 战略画布（多个 competitive_factor × 各品牌评分折线） |
| **ERRC（Eliminate-Reduce-Raise-Create）** | Blue Ocean 4 行动框架 |
| **Blue Ocean Move** | 蓝海战略动作（compelling_tagline + focus / divergence assessment） |

---

## 4. 数据契约（Schema）

### 4.1 输入 Schema：ScenarioInput

`ScenarioInput` 是 5 场景统一入口（`src/schemas/input.py`），按 `scenario` 字段分支校验：

```yaml
ScenarioInput:
  scenario: Literal["S1", "S2", "S3", "S4", "S5"]
  competitors: list[CompetitorBasic]            # 最多 10 个，S2 可空
  industry: Optional[str]                       # S2 必填
  analysis_context: str                         # 自然语言描述分析意图，min_length=1
  our_product_name: Optional[str]               # 除 S2 外必填
  our_product_brief: Optional[str]              # 选填
  prior_trace_id: Optional[str]                 # S4 增量模式，路径白名单 ^[a-f0-9-]+$ 长度 ≤64

CompetitorBasic:
  name: str                                     # min_length=2, max_length=50
  company: str                                  # 默认 ""
  category: str                                 # 默认 ""
  official_url: Optional[str]                   # 用户可提供官网
```

**分支校验规则**（`src/schemas/input.py:26-36`）：
- `S2`：必填 `industry`；`competitors` 可空（recommender 会自动推荐）
- `S1 / S3 / S4 / S5`：必填 `our_product_name` + 至少 1 个 `competitors`

> **注**：旧 V3.0 中的 `AnalysisGoal`（goal_type / product_stage / focus_area / output_expectation）已降级为 `collector` 内部解析中间态，不再对外暴露。详见 § 5.2 Collector Agent 职责。

### 4.2 采集 Agent 输出 Schema：CompetitorProfile

`CompetitorProfile`（`src/schemas/profile.py`）是 collector 对每个竞品的结构化产出：

```yaml
CompetitorProfile:
  classification:
    competitor_type: Literal["核心竞品", "标杆竞品", "间接竞品", "潜力竞品",
                              "替代竞品", "翘楚竞品", "避坑竞品"]
    reason: str                                 # 分类理由

  basic_info:
    name: str
    company: str
    version: str = "unknown"
    release_date: str                           # ISO 8601
    platform: list[str]                         # iOS / Android / Web / Desktop

  feature_tree: list[FeatureTree]               # 模块 → 子功能两级
  pricing:
    model: str                                  # freemium / subscription / per_seat 等
    tiers: list[PricingTier]
    source_url: str
  user_reviews:
    rating: float (0-5)
    total_reviews: int
    positive_summary, negative_summary: str
    sample_reviews: list[SampleReview]          # 每条含 source_url
  recent_updates: list[RecentUpdate]            # 近 90 天更新

  metadata:
    collected_at: str                           # ISO 8601
    data_sources: list[str]
    completeness_score: float (0-1)
    pipeline_trace: list[dict]                  # 采集管线决策记录
```

**完整度评分**（pipeline 计算）：
- `basic_info` 每缺失一字段扣 0.05
- `feature_tree` 为空扣 0.3 / `pricing` 空扣 0.15 / `user_reviews` 空扣 0.15 / `recent_updates` 空扣 0.1
- 缺 key / Tavily 失败 / 全空 → 输出 `completeness=0.0` 占位 profile，不调 LLM 编造画像

### 4.3 分析 Agent 输出 Schema：CompetitiveAnalysis

`CompetitiveAnalysis`（`src/schemas/analysis.py`）基于四维框架对比：

```yaml
CompetitiveAnalysis:
  positioning: Positioning                      # 维度一：产品定位与目标用户
  feature_matrix: list[dict]                    # 维度二占位透传（详见说明）
  business_model: BusinessModel                 # 维度三：商业模式
  operations: Operations                        # 维度四：运营与增长
  user_sentiment: UserSentiment                 # 用户情感对比
  swot: Optional[Swot]                          # SWOT 4 类，每条绑 source_refs
  radar_scores: list[dict]                      # 占位透传（详见说明）
```

**关于 `feature_matrix` / `radar_scores`**：
当前实现把这两个字段定义为 `list[dict]` 占位透传——具体结构化数据承载在场景 Payload 中（S1.FeatureMatrix / S1.RadarScores / S5.PerceptualMap 等），analyzer 阶段仅做扁平传递，writer phase 4 assemble 时按场景规则重新组装。这是设计上的过渡方案，未来场景 Payload schema 完全稳定后会从 analysis schema 中移除。

### 4.4 BaseReport 通用骨架

`BaseReport`（`src/schemas/report.py:145-185`）是 5 场景共用的报告骨架 + scenario_payload union：

```yaml
BaseReport:
  metadata: ReportMetadata                      # § 4.7
  title: str                                    # min=10, max=80
  subtitle: Optional[str]                       # max=120
  at_a_glance: list[str]                        # 3-6 条
  executive_summary: ExecutiveSummary           # 5 段式（替代旧 4 段）
  background: str                               # min=200, max=1500
  scope: ReportScope                            # competitors / time_window / regions / exclusions
  methodology: Methodology                      # 方法论 1000+ 字
  key_findings: list[Finding]                   # 3-6 条
  analysis_sections: list[AnalysisSection]      # 4-8 章
  swot: Swot                                    # 4 类各 ≥1 条，每条绑 source_refs
  conclusions: str                              # min=200, max=1500
  recommendations: list[Recommendation]         # ≥3 条，含 priority + timeline
  appendix: Appendix                            # glossary + exhibits + data_sources_full

  scenario_payload: Annotated[Union[
      S1FeatureIterationPayload, S2MarketEntryPayload, S3PricingStrategyPayload,
      S4MonitoringPayload, S5PositioningPayload,
  ], Field(discriminator='scenario_type')]

  # computed_field：从 payload 派生，与 metadata.scenario 强一致校验
  scenario: Literal["S1", "S2", "S3", "S4", "S5"]  (computed)
```

**关键设计**：
- `executive_summary` 5 段式（`context` 80-200 / `core_thesis` 50-120 / `key_findings_brief` 2-4 条 / `implications` 100-250 / `path_forward` 1-3 条）
- `scenario` computed_field 从 `scenario_payload.scenario_type` 派生，避免顶层 / metadata / payload 三处独立的命名漂移
- `model_validator` 强制 `metadata.scenario == scenario_payload.scenario_type`，不一致直接报错

### 4.5 5 场景 Payload 概览

每个场景一节，列「核心 Artifact + 5-10 个关键字段 + 1-2 个强约束亮点」。完整字段定义见 `src/schemas/scenarios/s1.py` ~ `s5.py`。

#### 4.5.1 S1：FeatureIterationPayload（功能迭代）

**核心 Artifact**：`vendor_profiles` / `feature_matrix` / `radar_scores` / `jtbd` / `roadmap`

| 字段 | 类型 / 约束 | 说明 |
|---|---|---|
| `vendor_profiles` | `list[S1VendorProfile]` | 每竞品一条，含 `wave_position`（wave_leader / wave_strong_performer / wave_contender）+ strengths 2-5 条 + cautions 1-4 条 |
| `feature_matrix` | `FeatureMatrix` | 加权评分（tier1=3 / tier2=2 / tier3=1），computed_field `weighted_scores` 自动计算每竞品总分 |
| `radar_scores` | 5 维评分 | 功能广度 / 易用性 / 性价比 / 稳定性 / 设计质量（0-5） |
| `feature_gap_analysis` | 差距清单 | 每条含 `gap_level`（leading / parity / lagging / differentiated）+ 行动建议 |
| `jtbd` | `JTBDAnalysis` | 用户任务清单，每条含 job_statement + outcome_metric |
| `roadmap` | 三档建议 | must_build / should_skip / should_differentiate |

**强约束亮点**：
- `FeatureScore.score=2`（完整支持）必须提供 `evidence_url`，否则 ValidationError（防 LLM 编造高分）
- `FeatureScore.score=0`（不支持）必须提供 `evidence_url` 或 `source_missing_reason`

#### 4.5.2 S2：MarketEntryPayload（市场进入）

**核心 Artifact**：`market_sizing` / `five_forces` / `players` / `entry_strategy` / `competitor_recommendations` / `pestel`

| 字段 | 类型 / 约束 | 说明 |
|---|---|---|
| `market_sizing` | `MarketSizing` | TAM / SAM / SOM 三层，每层 `MarketValue` 含 `value_basis`（measured / estimated / inferred / unknown）防幻觉 |
| `five_forces` | `FiveForces` | Porter 5 力，每力 `intensity`（low/medium/high）+ drivers 2+ 条 + evidence + implication |
| `players` | `list[MarketPlayer]` | 含 `market_role`（incumbent/challenger/emerging/niche/substitute）+ `is_recommended` + `is_collected` |
| `competitor_recommendations` | recommender 产物 | Top 3-5 推荐竞品 + confidence + selection_method（hybrid / search_only / llm_only） |
| `entry_strategy` | `EntryStrategy` | `recommended_mode`（niche_focus / differentiation / cost_leadership / fast_follower）+ phases + risks |
| `pestel` | Optional 6 因子 | 政治 / 经济 / 社会 / 技术 / 环境 / 法律，每因子含 impact + outlook |

**强约束亮点**：
- `MarketValue.amount` Optional + `value_basis` 必填——LLM 不知道就填 unknown，严禁编造数字
- `scope.competitors` 由 phase 4 union（用户输入 + recommender 推荐）唯一构造，去重 by name 用户在前

#### 4.5.3 S3：PricingStrategyPayload（定价策略）

**核心 Artifact**：`pricing_baseline` / `value_drivers` / `feature_classification` / `wtp_research` / `packaging` / `competitive_pricing` / `pricing_page_audit` / `rollout_plan`

| 字段 | 类型 / 约束 | 说明 |
|---|---|---|
| `pricing_baseline` | `PricingBaseline` | 当前定价模型（per_seat / flat_rate / usage_based / hybrid / freemium / platform_fee）+ tier 数 + 痛点 |
| `value_drivers` | `list[ValueDriver]` | 每条 `importance`（low/medium/high）+ evidence min=20 |
| `feature_classification` | hygiene / preference / premium 三档 | premium 对应可加价功能 |
| `wtp_research` | Optional `WTPResearch` | 方法（conjoint_analysis / van_westendorp / gabor_granger / interviews / ab_testing / proxy_from_competitor_pricing），proxy 方法时 confidence 强制 low |
| `packaging` | `RecommendedPriceTier[]` | GBB 三层套餐，**强制有且只有 1 个 `is_recommended=True`**；`annual_price ≤ monthly_price × 12` validator 强制 |
| `competitive_pricing` | 竞品定价矩阵 | 每条 `ObservedCompetitorTier` 必填 source_refs（防价格幻觉） |
| `pricing_page_audit` | 8 法则审计 | 每法则 pass / partial / fail + 改进建议 |
| `rollout_plan` | 上线步骤 + 预期 ARR 提升 | `expected_arr_uplift_basis` 不能是 `llm_inferred` 否则 inspector 标 minor |

#### 4.5.4 S4：MonitoringPayload（持续监控）

**核心 Artifact**：`review_period` / `feature_changes` / `pricing_changes` / `messaging_changes` / `news_events` / `org_changes` / `monitoring_threats` / `opportunities` / `battlecards`

| 字段 | 类型 / 约束 | 说明 |
|---|---|---|
| `review_period` | `ReviewPeriod` | 含 `prior_trace_id`，缺失则首次模式（baseline） |
| `feature_changes` | 5 类变更之一 | 每条 FIA 三元组（fact 必填，impact / act Optional），首次模式强制 `is_baseline=True` |
| `pricing_changes` / `messaging_changes` / `news_events` / `org_changes` | 同上模式 | 各自独立 change_type Literal 枚举 |
| `monitoring_threats` | `list[MonitoringThreat]` | computed_field `quadrant`（severity × likelihood = act_now / contingency / monitor / deprioritize） |
| `opportunities` | 机会识别 | 每条 `opportunity_type` + estimated_effort + expected_impact |
| `battlecards` | 活体战卡 | 每竞品至少 4 个 section（min_length=4），多个 section 完整度 |

**强约束亮点**：
- 首次模式（`prior_trace_id` 缺失）：所有 changes 强制 `is_baseline=True` + `MonitoringTrends` 全 None（model_validator 检查）
- `prior_trace_id` 必须匹配白名单 `^[a-f0-9-]+$` 且长度 ≤64，否则 graph 拒绝读盘 + log warning + 降级首次模式

#### 4.5.5 S5：PositioningPayload（战略定位）

**核心 Artifact**：`vendor_profiles` / `perceptual_map` / `magic_quadrant` / `strategy_canvas` / `errc_grid` / `blue_ocean_move` / `positioning_statement` / `category_strategy`

| 字段 | 类型 / 约束 | 说明 |
|---|---|---|
| `vendor_profiles` | `list[S5VendorProfile]` | 仿 Gartner MQ Strengths & Cautions 卡，含 `ability_to_execute_score`（0-5）+ `completeness_of_vision_score`（0-5）+ computed `mq_quadrant`（mq_leader / mq_challenger / mq_visionary / mq_niche_player） |
| `perceptual_map` | `PerceptualMap` | 二维感知地图，每个 PlottedBrand 含 `confidence` + `score_rationale`，**水印**: "基于公开信息 AI 推断，非客户调研真实分数" |
| `strategy_canvas` | Blue Ocean 战略画布 | 多个 competitive_factor × 每品牌评分折线 |
| `errc_grid` | ERRC 4 宫格 | Eliminate / Reduce / Raise / Create |
| `blue_ocean_move` | 蓝海动作 | compelling_tagline + focus_assessment + divergence_assessment |
| `positioning_statement` | Geoffrey Moore 6 位模板 | For X who Y, Product is a Category that Benefit. Unlike Alternative, Differentiation. confidence 必填（from_user_brief / llm_inferred / low_confidence） |
| `category_strategy` | `CategoryStrategy` | chosen_category + competitors_implied（必须是 vendor_profiles 子集） |

**强约束亮点**：
- `PerceptualMap.x_axis.attribute != y_axis.attribute`（不能同维度）+ 所有 plotted_brands 评分必须在 axis.scale_max 范围内
- `competitors_implied` 跨字段一致性校验（必须是 vendor_profiles 中的子集）

### 4.6 质检 Agent 输出 Schema：RejectionFeedback

`RejectionFeedback`（`src/schemas/feedback.py`）是 inspector 的结构化打回反馈：

```yaml
RejectionFeedback:
  passed: bool
  issues: list[FeedbackIssue]
  retry_count: int (≥0, default=0)
  max_retries: int (≥0, default=2)

FeedbackIssue:
  agent: Literal["collector", "analyzer", "writer"]   # 路由依据
  field: str                                          # 字段路径，如 "scenario_payload.market_sizing.tam"
  severity: Literal["critical", "major", "minor"]
  reason: str                                         # 问题描述
  suggestion: str                                     # 修改建议
```

**反馈路由规则**：
- `inspector` 按 `issues[].agent` 字段决定打回 `collector` / `analyzer` / `writer`
- inspector 打回时 `retry_count + 1`（recommender 与 collector 内部失败不计入）
- `retry_count >= max_retries` 强制 end，metadata.warnings 标注 retry_exceeded
- 第 2 次打回仅处理 `severity` 为 `critical` 和 `major` 的问题

### 4.7 ReportMetadata

```yaml
ReportMetadata:
  report_id: str
  trace_id: str
  scenario: Literal["S1", "S2", "S3", "S4", "S5"]
  schema_version: str = "2.0"

  publication_date: date
  version: str = "1.0"
  revision_history: list[Revision]              # 版本修订记录

  organization: str = "AI 竞品分析 Agent 协作系统"
  contributing_agents: list[str]

  data_sources: list[DataSource]                # min_length=1，含 confidence
  confidence_level: Literal["high", "medium", "low"]
  quality_score: Optional[float] (0-1)          # cap 后最终分
  raw_quality_score: Optional[float] (0-1)      # cap 前真实分（KPI 卡显示）
  quality_score_calculation_note: str           # 计算说明
  warnings: list[str]                            # placeholder_section: / placeholder_swot / dropped_unverified_entries:

  disclaimer: str                                # 免责声明（默认值已设）
  citation_format: Optional[str]
```

---

## 5. Agent 角色设计

### 5.1 总体架构

```
                 ┌─(S2)─→ recommender ─┐
   set_entry ───┤                       ├─→ collector → analyzer → writer → inspector ─┬─(passed)─→ END
                 └─(其他)──────────────┘                  ↑          ↑          ↑      │
                                                          │          │          │      ├─(issues→writer)────→ writer
                                                          │          │          │      ├─(issues→analyzer)──→ analyzer
                                                          │          │          │      └─(issues→collector)─→ collector
                                                          └──────────┴──────────┴── 反馈闭环回边
                                                       (retry_count + 1，retry_count ≥ max_retries 强制 end)
```

**场景路由**（`src/graph/builder.py`）：
- LangGraph `set_conditional_entry_point` 按 `ScenarioInput.scenario` 分流
- S2 → `recommender` → `collector`；其他 4 场景 → `collector`
- 共享状态 `AnalysisState`（TypedDict），节点间通过返回 dict 增量更新

### 5.2 各 Agent 职责

| Agent | 输入 | 输出 | 核心职责 | 工具依赖 |
|-------|------|------|----------|----------|
| **recommender**（S2 专属） | `ScenarioInput`（industry + analysis_context） | `CompetitorRecommendations` | 搜索行业头部玩家 + LLM 推理推荐 Top 3-5 玩家，含 selection_method（hybrid / search_only / llm_only） | Tavily 搜索 + LLM |
| **collector** | `ScenarioInput` | `list[CompetitorProfile]` | 持有 `CollectionPipeline`，编排「Tavily 搜索 → 质量闸门 → 全空兜底」主线；内部解析 `AnalysisGoal`（goal_type / product_stage / focus_area / output_expectation）作为采集深度依据 | Tavily / httpx async / per-domain 锁 / LLM 抽取 |
| **analyzer** | `list[CompetitorProfile]` + `ScenarioInput` | `CompetitiveAnalysis` | 跨竞品对比 + 各维度结论绑定 source URL；LLM ValidationError 时由 analyzer_node 兜底注入 feedback 不让 graph 崩溃；按 scenario 上下文调整 SWOT 主体 | LLM |
| **writer** （`WriterOrchestrator`） | `CompetitiveAnalysis` + `ScenarioInput` + `competitor_recommendations`（S2） + `prior_report_data`（S4） | `BaseReport` | 4 阶段编排（详见 § 5.5） | LLM × N 并行 |
| **inspector** | `BaseReport` | `RejectionFeedback` | `_check_common` + 5 场景 dispatcher 程序化硬查 + LLM 质检；写入 `quality_score`（详见 § 5.6） | LLM |

所有 prompt 集中在 `src/agents/prompts/`（含 `writer/` 子目录的 outline / payload / narrative 三套）。

### 5.3 反馈闭环机制

质检 Agent 发现问题时，输出结构化的 `RejectionFeedback`（详见 § 4.6）。

**闭环规则**：
1. **路由**：inspector 按 `issues[].agent` 字段决定打回目标，`builder.py::should_continue` 实现路由逻辑
2. **计数**：inspector 打回时 `retry_count + 1`；recommender / collector / analyzer 内部异常不计入
3. **熔断**：`retry_count >= max_retries`（默认 2）强制 end，`metadata.warnings` 标注
4. **降级**：第 2 次打回仅处理 `critical` 和 `major`，跳过 minor，避免无限重试
5. **快照**：每次打回前，旧产物存为 `_vN` 快照（`runs/<trace_id>/01_profiles_v1.json` 等），便于追溯对比

**Writer 阶段错误路由**（`src/agents/writer_orchestrator.py:55-64`）：

writer 阶段错误用三类自定义异常路由（避免依赖中文措辞子串匹配）：

| 异常 | 触发条件 | builder 处理 |
|---|---|---|
| `WriterRouteToCollector` | profiles 0 个 URL / phase 3 半数闸门触发（≥50% section 失败） / final_urls 空 | 注入 feedback agent=collector，回采集 |
| `WriterRouteToWriter` | phase 2 ValidationError 重试耗尽 / payload 校验失败 | 注入 feedback agent=writer，重写 |
| `WriterRouteToEnd` | LLM quota 熔断（WRITER_MAX_LLM_CALLS=18） / S2 scope 全空 / scope 无法构造 | feedback.passed=True 强制 end |

### 5.4 Agent 间状态传递

V3.0 设想的 `AgentMessage` schema（`from_agent / to_agent / message_type / payload / timestamp / trace_id`）作为概念契约保留（`src/schemas/feedback.py:22-29`），但实际跨节点数据通过 LangGraph 的 `AnalysisState`（TypedDict）增量更新——所有跨 Agent 数据都是 Pydantic 模型而非裸 dict：

```python
class AnalysisState(TypedDict):
    user_input: ScenarioInput
    profiles: list[CompetitorProfile]
    analysis: CompetitiveAnalysis
    report: BaseReport
    feedback: RejectionFeedback
    competitor_recommendations: CompetitorRecommendations
    prior_report_data: Optional[dict]              # S4 专用
    retry_count: int
    max_retries: int
    trace_writer: TraceWriter
```

### 5.5 Writer 4 阶段编排

WriterOrchestrator 替代旧 WriterAgent，分 4 阶段产出 `BaseReport`，突破单次 LLM 4-5K 字上限稳定产 7000-8000 字：

| Phase | 职责 | LLM | 关键约束 |
|---|---|---|---|
| **1. outline** | 产出 BaseReport 通用骨架（title / executive_summary / key_findings / analysis_sections heading 列表 / recommendations / conclusions） | 1 次 | Pydantic 失败重试 1 次；`data_collection_approach` ≥200 字字段由代码模板合成 |
| **2. payload** | 实例化场景 Payload schema（S1-S5 之一），执行 normalizers 规整 + S2 recommender 强制覆盖 + S4 prior diff 前置注入 | 1 次（max_retries=2） | 失败转 `WriterRouteToWriter` |
| **3. narrative** | 逐 section 写 narrative（`asyncio.Semaphore(3)` 并发限速） | N 次（每 section 1 次） | 半数硬闸门：≥50% section 失败回 collector；占位降级触发 placeholder warnings |
| **4. assemble** | 0 LLM 代码合成 BaseReport（SWOT 透传 + URL 双通道收集 + scope.competitors S2 union + ReportMetadata 构造） | 0 次 | 全部代码逻辑，不赌 LLM |

**配置项**：
- `WRITER_MAX_LLM_CALLS=18`：总 LLM 调用熔断阈值（4 阶段累加），超限触发 `WriterRouteToEnd`
- `WRITER_NARRATIVE_CONCURRENCY=3`：Phase 3 narrative 并发上限

### 5.6 quality_score 计算规则

`src/agents/quality_score.py::calc_quality_score` 按三项加权计算（各 1/3 等权，缺值降权重新归一化），最终 round 到 3 位小数：

| 项 | 计算方法 |
|---|---|
| **source_coverage** | 4 类条目（key_findings / analysis_sections / recommendations / swot.entries）中带 source_refs 的占比 |
| **confidence_avg** | metadata.data_sources 各 confidence 数值化平均（high=1.0 / medium=0.6 / low=0.3） |
| **inspector_pass_rate** | `1.0 - sum(severity_penalty)`，clamp[0,1]（critical=0.4 / major=0.2 / minor=0.05） |

**placeholder cap 0.5**：
inspector 检测 `metadata.warnings` 含以下任一前缀即强制 cap quality_score 到 0.5（`src/agents/inspector.py:21-37`）：
- `placeholder_section:`
- `placeholder_swot`
- `dropped_unverified_entries:`

`raw_quality_score` 字段保留 cap 前真实分供 KPI 卡对比展示。

---

## 6. 业务流程

### 6.1 端到端流程

```
[用户] 选场景 + 输入字段（按 scenario 分支）
    │
    ▼
[系统] ScenarioInput 校验（Pydantic model_validator 分支）
    │ 校验通过
    ▼
┌──[set_conditional_entry_point]────────────┐
│   if scenario == "S2":                    │
│       → recommender                       │
│           Tavily 搜索行业 + LLM 推理       │
│           输出 CompetitorRecommendations   │
│           Top 3-5 玩家 + selection_method │
│   else:                                   │
│       → collector                         │
└─────────────────────────────────────────┘
    │
    ▼
[collector] 解析 AnalysisGoal → 按 goal_type 决定采集深度
            CollectionPipeline: Tavily 一次调用直返带正文
            S2 时 union（用户竞品 + recommender 推荐）去重 by name
    │ list[CompetitorProfile]
    ▼
[analyzer] 四维分析（定位 / 功能 / 商业 / 运营）+ SWOT
           LLM ValidationError → analyzer_node 兜底注入 feedback
    │ CompetitiveAnalysis
    ▼
[writer 4 阶段]
    │ Phase 1 outline （LLM）
    │ Phase 2 payload  （LLM；S4 时前置注入 prior_report_data 做 diff）
    │ Phase 3 narrative（LLM × N 并行）
    │ Phase 4 assemble （0 LLM）
    │ BaseReport
    ▼
[inspector] _check_common + 场景 dispatcher 程序化硬查 + LLM 质检
            calc_quality_score + placeholder cap 0.5
            输出 RejectionFeedback
    │
    ├─ passed=True → END，输出报告
    └─ passed=False
       │
       ├─ retry_count < max_retries
       │   │ 按 issues[0].agent 字段路由：
       │   ├─ "collector" → collector（旧产物存 _vN 快照）
       │   ├─ "analyzer"  → analyzer
       │   └─ "writer"    → writer
       │   retry_count + 1，回到对应节点重做
       │
       └─ retry_count ≥ max_retries → 强制 END + warnings 标注
```

### 6.2 异常场景矩阵

| 阶段 | 异常场景 | 触发条件 | 处理方案 |
|------|----------|----------|----------|
| **输入** | scenario 必填字段缺失 | S2 缺 industry / 其他场景缺 our_product_name | Pydantic model_validator 校验失败，前端返回友好提示 |
| **输入** | prior_trace_id 含非法字符 | 用户输入 `../../etc/passwd` 类路径穿越 | 白名单 `^[a-f0-9-]+$` + 长度 ≤64 拒绝，log warning，graph 仍能跑（降级首次模式） |
| **采集** | Tavily 失败 / 全空 | API 故障 / quota 耗尽 / 关键词无结果 | 输出 `completeness=0.0` 占位 profile，不调 LLM 编造画像 |
| **采集** | 单竞品采集失败 | 某竞品所有源不可达 | 部分降级：单竞品占位，其余正常产出（语义从「快速失败」改为「部分降级」） |
| **分析** | LLM ValidationError | 字段类型错位 / 必填缺失 | analyzer_node 兜底注入 feedback agent=analyzer，不让 graph 崩溃 |
| **撰写** | profiles 0 个有效 URL | 上游采集全空 | `WriterRouteToCollector` 抛出，回 collector 重采 |
| **撰写** | phase 2 ValidationError 耗尽重试 | LLM 反复字段错位 | `WriterRouteToWriter`，重写 |
| **撰写** | phase 3 半数 section 失败 | 并发占位降级 ≥50% | `WriterRouteToCollector`，回 collector |
| **撰写** | LLM 调用超 WRITER_MAX_LLM_CALLS=18 | LLM quota 熔断 | `WriterRouteToEnd`，feedback.passed=True 强制 end |
| **质检** | placeholder warnings 出现 | writer 占位降级残留 | quality_score 强制 cap 至 0.5，原始分保留在 raw_quality_score |
| **闭环** | retry_count ≥ max_retries | 修正不收敛 | 强制 END + metadata.warnings 标注 retry_exceeded |
| **系统** | LLM 服务不可用 | Doubao API 故障 / 超时 | OpenAI client max_retries=0（关闭内部重试），LLMClient 外层 retry 3 次（嵌套放大避免）；最终失败返回错误响应 |

---

## 7. 功能清单与优先级

### 7.1 P0 — 核心功能（全部已交付）

| 编号 | 功能 | 描述 | 验收标准 |
|------|------|------|----------|
| F01 | 场景选择 + 场景化输入 | 5 场景下拉 + 按 scenario 分支表单 | ScenarioInput Pydantic 校验通过 |
| F02 | S2 recommender | 输入行业关键词，自动推荐 Top 3-5 玩家 | 输出 CompetitorRecommendations，含 confidence + selection_method |
| F03 | 竞品分类 | LLM 判断竞品 7 类型并决定采集策略 | 分类结果合理，有分类理由 |
| F04 | 数据采集 | Tavily 单源主线 + 全空兜底 | 输出符合 CompetitorProfile schema |
| F05 | 竞品分析 | 四维框架对比 + SWOT | 输出符合 CompetitiveAnalysis schema |
| F06 | 报告生成 | Writer 4 阶段编排产出 BaseReport | 输出符合 BaseReport + 场景 Payload schema |
| F07 | 质量检查 | inspector 程序化硬查 + LLM 质检 | 可识别 schema 缺失、无来源结论、placeholder 残留 |
| F08 | 反馈闭环 | issue.agent 路由 + retry_count 计数 | 打回后输出有改善（字段补全或来源补充） |
| F09 | 信息溯源 | SourceRef + DataSource 双层 + URL 双通道 | 每条结论可点击溯源链接查看原文 |
| F10 | 可观测性 | trace_id 全链路 + TraceWriter 落盘 | 每个 Agent 输入/输出/耗时可查看 |
| F11 | AI 帮我选场景 | 填分析意图，LLM 推断推荐场景 + 置信度 | 5 段测试文案至少 4 段推荐准确 |
| F12 | 报告导出 | Markdown / HTML 双格式 | HTML 全内嵌字体 + Plotly + CSS 单文件 3-5MB 断网可用 |
| F13 | 执行追溯面板 | 前端加载 trace_id 查看 4 阶段产物 + run.log + _vN 快照 | 4 个 tab 都有 JSON 内容 |
| F14 | Plotly 5 场景图表 | S1 雷达 / S2 五力蜘蛛网 / S5 Perceptual Map / MQ / Strategy Canvas | 图表正确渲染交互 |
| F15 | 报告质量评分 | quality_score 三项加权 + cap 机制 | KPI 卡显示 raw + cap 后 |

### 7.2 P1 — 增强功能（部分已交付）

| 编号 | 功能 | 描述 | 状态 |
|------|------|------|------|
| F16 | S4 增量监控 | 填上次 trace_id 自动 diff 5 类变更 | **已交付** |
| F17 | 采集降级策略 | Tavily 失败 / 全空 → 占位 profile + 部分降级 | 已交付 |
| F18 | 进度展示 | 实时展示分析进度（Streamlit spinner） | 已交付 |
| F19 | 历史报告缓存 | 相同竞品短期内不重复采集 | 未做 |

### 7.3 P2 — 扩展功能（未做）

| 编号 | 功能 | 描述 |
|------|------|------|
| F20 | 自定义分析维度 | 用户添加自定义对比维度 |
| F21 | 历史报告对比（跨场景） | 对比两次分析结果差异（S4 内已支持，跨场景未做） |
| F22 | 多语言支持 | 英文报告产出 |
| F23 | 多用户认证 | 个人项目目前单用户即可 |

### 7.4 评估对比 V3.0「不包含」清单

V3.0 清单中已落地的：
- F12 报告导出（V3.0 标 P2 不做） → **已落地**
- F16 S4 增量监控（V3.0 标 P1 不做） → **已落地**

V3.0 清单中仍未做的：自定义维度 / 跨场景历史对比 / 多语言 / 数据库存储 / 多用户认证。

### 7.5 产品亮点矩阵

| 亮点 | 用户感知 | 技术实现 |
|---|---|---|
| **AI 帮我选场景** | 不用纠结自己该选 S1 还是 S5，让 AI 帮判断 | LLM 推断 + 置信度 emoji + rationale 引用关键词 |
| **报告导出 md+html** | 报告可分享、可离线 | HTML 全内嵌字体 woff2 + Plotly + CSS 单文件 3-5MB；nh3 sanitize + Jinja2 autoescape 三道 XSS 防护 |
| **全链路 trace_id 追溯** | 任何报告都可回溯采集 / 分析 / 撰写 / 质检产物 | 北京时间格式 trace_id + TraceWriter 落 runs/<trace_id>/ + _vN 快照 |
| **Plotly 5 场景图表** | 雷达 / MQ / Perceptual Map / Strategy Canvas 交互式图表 | Plotly 5.20+，前端 render.py 按 scenario_payload.scenario_type 派发 |
| **5 段式执行摘要** | context / core_thesis / key_findings_brief / implications / path_forward 业界标杆结构 | Pydantic min/max_length 强约束，writer phase 1 outline 阶段产出 |

---

## 8. 数据采集

### 8.1 数据源

**当前实现**：Tavily Search API 单源（`src/tools/sources/tavily.py`）

| 项 | 值 | 说明 |
|---|---|---|
| API | Tavily Search API（topic=general，含 `raw_content`） | 一次调用直返带正文 SourceResult，跳过传统三步走（搜索→选页→抓取） |
| 认证 | POST + Bearer header | api_key 走 header 不进 URL，避免 run.log 泄漏 |
| 配置 | `TAVILY_API_KEY` 选填 | 缺 key 时跳过搜索主线，走占位降级（completeness=0.0） |

**设计取舍**：
- 06-06 实测 Tavily 中文场景质量明显优于 SerpAPI（语雀 1.0 / 飞书 0.85 completeness）
- 06-07 弃用 SerpAPI，移除双 provider 架构（删 SEARCH_PROVIDER 开关 + 115 行 SerpAPI 专项代码）
- 06-06 移除 iTunes 专源（同名污染问题）

### 8.2 采集策略

- **Tavily 直采**：一次调用返回 search results + raw_content，跳过中间所有步骤（搜索→选页→抓取→清洗）
- **HTTP 客户端**：httpx async，同域名限速 `COLLECT_INTERVAL` + per-domain 锁（避免并发击穿限速）
- **多 query 并发**：每个竞品多个 query 并发跑，单 query 失败不影响其他 query
- **超时控制**：单次 LLM 调用 `LLM_TIMEOUT=120`s，单次 HTTP 调用根据网络环境自适应

### 8.3 降级策略

| 降级场景 | 处理方式 |
|----------|----------|
| 单 query 失败 | 跳过，其他 query 兜底 |
| 单竞品所有 query 失败 | 输出 completeness=0.0 占位 profile，不调 LLM 编造画像 |
| writer 阶段 profiles 总 URL=0 | `WriterRouteToCollector` 回采集 |
| writer phase 3 半数 section 占位降级 | `WriterRouteToCollector` |
| placeholder warnings 残留 | inspector 强制 cap quality_score 到 0.5 |

---

## 9. 非功能性需求

### 9.1 性能要求

| 指标 | 要求 | 备注 |
|------|------|------|
| 单竞品分析端到端时间 | ≤ 5 分钟 | S1 / S3 / S5 |
| 3 竞品对比分析端到端时间 | ≤ 8 分钟 | S1 / S3 / S5 |
| 5 竞品对比分析端到端时间 | ≤ 10 分钟 | S1 / S3 / S5 |
| 前端页面加载时间 | ≤ 2 秒 | — |

**注**：不同场景的复杂度差异较大——S2 含 recommender 阶段会略慢；S4 增量模式（已有 prior_report_data）会比首次模式快；writer 4 阶段总 LLM 调用熔断阈值 `WRITER_MAX_LLM_CALLS=18`，phase 3 narrative 并发上限 `WRITER_NARRATIVE_CONCURRENCY=3`，超出会终止避免雪崩。

### 9.2 可靠性要求

| 指标 | 要求 |
|------|------|
| 单次分析成功率 | ≥ 90%（允许部分数据源失败 + 占位降级） |
| LLM 调用成功率 | ≥ 95%（含 LLMClient 外层 3 次重试；OpenAI client 内部 max_retries=0 避免嵌套放大） |
| 报告 Schema 合规率 | 100%（writer 4 阶段重试 + ValidationError 自定义异常路由 + inspector 程序化硬查联保） |

### 9.3 可观测性要求

每次分析任务通过 trace_id 串联完整可观测链路：

| 可观测项 | 落盘位置 | 内容 |
|---|---|---|
| 日志（全局） | `logs/app.log` | 跨 trace 的全局日志 |
| 日志（per-trace） | `runs/<trace_id>/run.log` | 单次分析的所有 INFO / WARNING / ERROR |
| 中间产物 | `runs/<trace_id>/0[1-4]_*.json` | 01_profiles / 02_analysis / 03_report / 04_feedback |
| 反馈闭环快照 | `runs/<trace_id>/0[1-4]_*_v\d+.json` | 每次反馈打回前的旧产物 |
| 元数据 | `runs/<trace_id>/meta.json` | 状态（running/completed/failed）+ node_trace（节点访问序列）+ retry_count |
| 决策过程 | meta.json::node_trace | 每次节点切换 + 每次质检 issues 摘要 + 路由目标 |

**API 接口**（`src/api/routes.py`）：
- `GET /api/v1/trace/{trace_id}` 获取最新 4 阶段产物 + meta + run.log（路径穿越双重防护：fullmatch + resolve）
- `GET /api/v1/trace/{trace_id}?version=N` 获取历史 _vN 快照

---

## 10. 验收标准

### 10.1 功能验收

| 验收项 | 验收标准 | 验证方式 |
|--------|----------|----------|
| 场景路由 | S2 后端日志显示 `[graph] → recommender → collector`，其他场景 `[graph] → collector` | 看 run.log |
| ScenarioInput 校验 | S2 缺 industry / 其他缺 our_product_name 应返回 422 | 演示 |
| recommender 输出 | S2 输出 ≥3 个推荐玩家，含 confidence + selection_method | 检查输出 schema |
| BaseReport schema | 5 场景产报告均通过 Pydantic 校验，含 metadata.scenario == scenario_payload.scenario_type | 检查输出 schema |
| 反馈闭环 | 故意构造缺陷报告，质检可识别并按 issue.agent 路由打回 | 演示 |
| 信息溯源 | 报告中每条结论可点击查看 source_refs URL | 演示 |
| 可观测性 | 任一 trace_id 的 4 阶段产物 + meta + run.log 可查看 | 演示 |
| AI 帮我选场景 | 5 段测试文案至少 4 段推荐准确 | docs/TESTING_GUIDE.md |
| 报告导出 | Markdown 关键字段全覆盖；HTML 全内嵌断网可用 | 演示 |
| Plotly 图表 | S1 雷达 / S2 五力蜘蛛网 / S5 MQ + Perceptual Map + Strategy Canvas 渲染正确 | 演示 |
| quality_score | KPI 卡显示 raw + cap 后；placeholder 出现自动 cap 0.5 | 演示 |
| S4 增量模式 | 填 prior_trace_id 显示「模式：增量」，注入 prior_report_data | 演示 |
| 路径穿越拒绝 | prior_trace_id 含 `..` 应被白名单拒绝（log warning，不崩） | 演示 |

### 10.2 质量验收

| 验收项 | 验收标准 |
|--------|----------|
| ExecutiveSummary 5 段字数 | context 80-200 / core_thesis 50-120 / key_findings_brief 2-4 条 / implications 100-250 / path_forward 1-3 条 |
| BaseReport 字数 | background 200-1500 / conclusions 200-1500 |
| 章节数 | analysis_sections 4-8 章 |
| 关键发现 | key_findings 3-6 条 |
| 行动建议 | recommendations ≥3 条，含 priority + timeline |
| SWOT | 4 类各 ≥1 条，每条含 source_refs |
| 溯源链接有效率 | ≥ 80% 的溯源链接可访问 |
| 端到端成功率 | 单竞品分析成功率 ≥ 90% |

### 10.3 非功能验收

| 验收项 | 验收标准 |
|--------|----------|
| 性能 | 单竞品分析 ≤ 5 分钟；5 竞品 ≤ 10 分钟 |
| 稳定性 | 连续 3 次分析无崩溃 |
| 错误处理 | 输入不存在的竞品 / scenario 必填字段缺失，返回友好提示而非崩溃 |
| 安全 | API key 不在 URL / 日志泄漏；prior_trace_id 路径穿越拒绝；HTML 导出三道 XSS 防护 |
| 测试覆盖 | 445 个单元测试 + 集成测试通过；ruff lint 全清 |

---

## 11. 信息溯源

### 11.1 溯源对象设计（双层）

```yaml
# 内嵌在 finding / section / recommendation / swot 内
SourceRef:
  url: str (min_length=8)
  title: str = ""
  accessed_at: Optional[date]
  source_type: Literal["official_website", "third_party_review",
                       "industry_report", "news", "user_review",
                       "regulatory", "other"]

# 报告级数据源汇总（appendix.data_sources_full / metadata.data_sources）
DataSource:
  url: str (min_length=8)
  title: str = ""
  accessed_at: Optional[date]
  source_type: 同上 Literal
  confidence: Literal["high", "medium", "low"] = "medium"
```

### 11.2 URL 双通道收集

writer phase 4 assemble 阶段：
- **通道 1**：narrative 阶段挂 SourceRef 到 finding / section / recommendation / swot 内嵌
- **通道 2**：assemble 阶段汇成 metadata.data_sources（去重）+ appendix.data_sources_full

两通道独立，确保「报告内每条结论都有引用」+「报告末尾有完整数据源汇总」。

### 11.3 溯源展示规则

- 报告中每条 finding / section / recommendation 旁标注 source_refs
- 用户可点击查看 url / title / accessed_at
- Markdown / HTML 导出附录章节列出全部 data_sources
- 失效链接不阻塞报告展示，可选择标记「来源不可用」

---

## 12. 可观测性

### 12.1 日志结构

每次分析任务生成一份完整的执行日志：

```
runs/
  <trace_id>/                         # 北京时间格式 YYYYMMDD-HHMMSS-<6hex>
    01_profiles.json                  # collector 输出
    02_analysis.json                  # analyzer 输出
    03_report.json                    # writer 输出
    04_feedback.json                  # inspector 输出
    01_profiles_v1.json               # 反馈打回前的旧产物（_vN 快照）
    01_profiles_v2.json               # ...
    meta.json                         # 状态 + node_trace + retry_count + 输入参数
    run.log                           # 单次分析的全部日志
    04_writer_error.json              # writer ValidationError 详情（如发生）
```

### 12.2 可观测界面（Streamlit 前端「执行追溯」面板）

- 输入 trace_id 加载 4 阶段产物
- 4 个 tab 分别展示采集 / 分析 / 报告 / 质检产物
- 每 tab 含原始 JSON 折叠 + 美化展示
- 反馈闭环 _vN 历史快照可对比
- 配套 `?version=N` 切换历史版本

### 12.3 决策过程追溯

`meta.json::node_trace` 记录节点执行序列 + 每次质检 issues 摘要 + 路由目标 agent，例：

```json
{
  "node_trace": [
    {"node": "collector", "ts": "..."},
    {"node": "analyzer", "ts": "..."},
    {"node": "writer", "ts": "..."},
    {"node": "inspector", "ts": "...", "passed": false, "issues_brief": [...]},
    {"node": "writer", "ts": "...", "retry_count": 1},
    {"node": "inspector", "ts": "...", "passed": true},
    {"node": "END"}
  ]
}
```

不存 prompt / LLM 原始响应（范围爆炸，收益边际递减），prompt 留作未来扩展。

---

## 13. 技术方案概要

| 层 | 技术选型 | 选型理由 |
|----|----------|----------|
| LLM | Doubao-Seed-2.0-lite（OpenAI SDK 调火山方舟 Ark 端点） | 项目当前选用模型 |
| Agent 编排 | LangGraph StateGraph | 原生支持 DAG + 条件分支 + 环路，适合反馈闭环 |
| 数据校验 | Pydantic v2 | 全链路 Schema 契约 + min/max_length / Literal / model_validator |
| 后端 | FastAPI + uvicorn | 异步支持好，与 LangGraph 生态一致 |
| 前端 | Streamlit + Plotly | 11 天极限计划最快出活；Plotly 5 场景图表交互 |
| 数据采集 | Tavily API + httpx async + BeautifulSoup4 | 一次调用直返带正文 |
| 报告导出 | markdown + Jinja2 + nh3 | Markdown / HTML 双格式；nh3 + autoescape 三道 XSS 防护 |
| HTML 字体 | Plus Jakarta Sans + Fira Code（latin 子集 woff2 base64 内嵌） | 断网可用 |
| 测试 | pytest + pytest-asyncio + ruff | 445 passed / ruff clean |

---

## 14. 版本边界

### 14.1 V4.0 包含

- 5 场景能力（S1 功能迭代 / S2 市场进入 / S3 定价策略 / S4 持续监控 / S4 增量监控 / S5 战略定位）
- 5 Agent 协作（recommender + collector + analyzer + writer + inspector）
- Writer 4 阶段编排（outline + payload + narrative + assemble）
- BaseReport 通用骨架 + 5 套场景 Payload（discriminated union）
- 反馈闭环（issue.agent 路由 + retry_count + WriterRouteTo* 异常）
- 信息溯源（SourceRef + DataSource 双层 + URL 双通道）
- 全链路 trace_id 可观测性（TraceWriter + _vN 快照 + node_trace + run.log）
- AI 帮我选场景（LLM 推断 + 置信度）
- 报告导出（Markdown / HTML 双格式，HTML 全内嵌）
- Plotly 5 场景图表（S1 雷达 / S2 五力蜘蛛网 / S5 Perceptual Map / MQ / Strategy Canvas）
- 质量评分（三项加权 + placeholder cap 0.5 + raw_quality_score）
- Streamlit 前端（场景化输入表单 + 报告渲染 + 执行追溯面板）

### 14.2 V4.0 不包含

| 排除功能 | 排除原因 |
|----------|----------|
| 历史报告缓存 | 个人项目无重复采集需求，未做 |
| 跨场景历史报告对比（S4 内部 diff 已支持） | P2 优先级 |
| 自定义分析维度 | P2 优先级 |
| 多语言支持（英文报告） | 中文场景即可 |
| 数据库存储 | 使用文件系统 + trace_id 命名空间已足够 |
| 多用户认证 | 个人项目，单用户即可 |
| 付费数据源 | 仅采集公开可访问数据 |
| 竞品图谱关系挖掘 | 超出 MVP 范围 |

### 14.3 假设与约束

| 假设/约束 | 说明 |
|-----------|------|
| LLM 服务稳定 | 假设 Doubao API 可用率 ≥ 99% |
| Tavily 配额 | 假设 TAVILY_API_KEY 配额充足；缺 key 时降级走占位 |
| 网络可达 | 假设运行环境可访问目标数据源网站 + Tavily API |
| 中文场景 | 所有分析对象为中文产品，数据源以中文为主（含英文混合） |
| 单用户使用 | 不考虑并发用户场景；trace_id 命名空间隔离不同分析 |
| 公开数据 | 仅采集公开可访问的数据，不涉及付费数据源 |
| prior_trace_id 同库 | S4 增量模式假设 prior_trace_id 在本机 runs/ 目录下 |
| 演示 / Demo | 不要求现场实时跑，可用成功 trace 现成报告演示 |
