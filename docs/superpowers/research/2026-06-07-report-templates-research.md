# 咨询级竞品分析报告模板研究

> 调研日期：2026-06-07
> 调研目的：为 5 套场景化报告 schema 设计（R2: BaseReport + 场景 payload）提供模板依据
> 调研范围：5 个竞品分析场景（S1 功能迭代 / S2 市场进入 / S3 定价策略 / S4 持续监控 / S5 战略定位）+ 通用咨询报告骨架
> 调研机构：McKinsey、BCG、Bain、Gartner、Forrester、Simon-Kucher、CB Insights、Klue、IndustryLens 等

---

## 调研结论速览

### 1. 通用骨架 13 元素（5/5 咨询机构共识）

| # | 元素 | 共识度 | 字段名建议 |
|---|---|---|---|
| 1 | Title | 5/5 | `title: str` |
| 2 | Subtitle | 部分 | `subtitle: Optional[str]` |
| 3 | At a Glance | 5/5 | `at_a_glance: list[str]` |
| 4 | Executive Summary | 5/5 | `executive_summary: ExecutiveSummary` |
| 5 | Background | 5/5 | `background: str` |
| 6 | Scope & Coverage | 5/5 | `scope: ReportScope` |
| 7 | Methodology | 5/5 | `methodology: Methodology` |
| 8 | Key Findings | 5/5 | `key_findings: list[Finding]` |
| 9 | Main Analysis (场景化) | 5/5 | `analysis_sections: list[AnalysisSection]` |
| 10 | Conclusions | 5/5 | `conclusions: str / list[str]` |
| 11 | Recommendations | 5/5 | `recommendations: list[Recommendation]` |
| 12 | Appendix | 5/5 | `appendix: Appendix` |
| 13 | Metadata & Disclaimer | 5/5 | `metadata: ReportMetadata` |

### 2. 场景专属元素（不进通用骨架）

| 场景 | 专属元素 |
|---|---|
| S1 功能迭代 | Feature Matrix（加权评分）、Capability Gap Analysis、Roadmap Comparison、Feature Parity Score |
| S2 市场进入 | Market Sizing（TAM/SAM/SOM）、Five Forces、Top N Players、Entry Mode Comparison |
| S3 定价策略 | Pricing Tier Comparison、Willingness-to-Pay Analysis、GBB Packaging、Pricing Page Audit |
| S4 持续监控 | Recent Updates Timeline、Change Log、Period-over-Period Delta、Living Battlecard |
| S5 战略定位 | Perceptual Map、Strategic Group Map、Strategy Canvas / ERRC、Positioning Statement |

### 3. 执行摘要 5 段式标准结构

| 段落 | 内容 | 字数（按 600 字总量） |
|---|---|---|
| Context / Why now | 为什么这件事重要 | 80–120 |
| Core thesis / "So what" | 一句压舱判断 | 50–80 |
| Key findings (2–4 条) | 摘要级核心发现 | 200–280 |
| Implications | 这些发现意味着什么 | 100–150 |
| Path forward | 1–3 条最关键建议 | 80–120 |

---

## 第 1 部分：通用骨架研究（McKinsey / BCG / Bain / Gartner / Forrester）

### 调研样本对照表

| 报告 | 章节序列（节选） |
|---|---|
| **McKinsey – The Energy Transition (2022)** | Cover / About authors / Contents / In Brief / Executive Summary / Ch1–5 / Acknowledgments |
| **McKinsey – Smart Cities (MGI, 2018)** | Cover / About MGI / In Brief / Executive Summary / 5 Chapters / Acknowledgments / Bibliography |
| **BCG – Where's the Value in AI (2024)** | Contents / Who's Getting Results / Surprising Sources of Value / Playbook / Definitions and Methodology / Authors |
| **BCG – Widening AI Value Gap (2025)** | At a Glance / Future-Built Strategies / How to Accelerate / Appendix: Definitions, Methodology / Authors |
| **Bain – 2026 CEO Agenda** | At a Glance（4–5 条要点）/ 主体多个 H2 / The Path Forward / 作者署名 |
| **Gartner – Market Guide / Magic Quadrant** | Overview / Key Findings / Recommendations / SPA / Market Definition / Direction / Analysis / Evidence / Revision History / Disclaimer |
| **Forrester Wave – AI/ML Platforms Q3 2022** | Summary / Evaluation Summary / Vendor Offerings / Vendor Profiles / Evaluation Overview / Inclusion Criteria / Supplemental Material / Wave Methodology / Endnotes & Citation Policy |

**5 家共性**：5 家在不同名字下都具备这 7 类骨架元素：
- 标题/封面
- 摘要（At a Glance / Key Findings / In Brief / Executive Summary）
- 背景或市场定义
- 方法论（必有，且必须独立成节）
- 主体分析
- 结论与建议
- 附录（Evidence / Endnotes / Disclaimer / Author bio）

### 通用骨架元素详表

| # | 元素（中/英） | 一句话定义 | 是否必填 | 字数级别 | 形态 | 字段名 |
|---|---|---|---|---|---|---|
| 1 | 报告标题 Title | 一句话点明竞品对象 + 报告类型 + 时点 | 必填 | 10–25 字 | 纯文本 | `title: str` |
| 2 | 副标题 Subtitle | 标题的"so what"补充 | 可选 | 15–40 字 | 纯文本 | `subtitle: Optional[str]` |
| 3 | At a Glance / 关键要点 | 4–5 条 bullet，每条独立成立 | 必填 | 80–150 字 | 列表 | `at_a_glance: list[str]` |
| 4 | 执行摘要 Executive Summary | 整份报告的"独立可读版" | 必填 | 占报告 5–10% | 段落+小列表 | 见第 1 部分专章 |
| 5 | 研究背景 Background | 为什么这件事现在重要、市场现状 | 必填 | 300–600 字 | 段落 | `background: str` |
| 6 | 研究范围 Scope & Coverage | 涵盖了哪些竞品/时间窗/地区 | 必填 | 100–200 字 | 列表/键值 | `scope: ReportScope` |
| 7 | 方法论 Methodology | 数据来源、采集方式、评估口径、局限性 | 必填 | 200–400 字 | 段落+列表 | `methodology: Methodology` |
| 8 | 核心发现 Key Findings | 3–6 条带证据的发现 | 必填 | 400–800 字 | 编号列表 | `key_findings: list[Finding]` |
| 9 | 主体分析 Main Analysis | 场景特有的分析章节集合 | 必填 | 占报告 60–70% | 多个 H2 章节 | `analysis_sections: list[AnalysisSection]` |
| 10 | 结论 Conclusions | 综合判断（不是建议） | 必填 | 200–400 字 | 段落 | `conclusions: str / list[str]` |
| 11 | 行动建议 Recommendations | 给读者下一步该做什么 | 必填 | 300–600 字 | 编号列表 | `recommendations: list[Recommendation]` |
| 12 | 附录 Appendix | 数据来源、术语表、附加图表 | 必填 | 不计字数 | 列表/表格 | `appendix: Appendix` |
| 13 | 元数据/免责声明 | 作者、日期、版本、引用、声明 | 必填 | 100–200 字 | 键值 | `metadata: ReportMetadata` |

### 执行摘要结构（5 段范式）

跨 5 家机构对照后的共性：

| # | 段落 | 内容 | 大致字数（按 600 字总量） |
|---|---|---|---|
| 1 | Context / Why now | 为什么这件事重要、市场处于什么节点 | 80–120 |
| 2 | Core thesis / "So what" | 一句压舱判断 | 50–80 |
| 3 | Key findings (2–4 条) | 摘要级的核心发现 | 200–280 |
| 4 | Implications / Strategic moves | 这些发现意味着什么 | 100–150 |
| 5 | Recommended actions / Path forward | 1–3 条最关键建议 | 80–120 |

**Pydantic 落地建议（混合制）**：

```python
class ExecutiveSummary(BaseModel):
    context: str           # ~100 字
    core_thesis: str       # ~70 字，一句话压舱判断
    key_findings_brief: list[str]   # 2–4 条，每条 ≤80 字
    implications: str      # ~120 字
    path_forward: list[str]         # 1–3 条 top-level 建议
```

### 真实例子节选

**Bain – 2026 CEO Agenda（At a Glance 风格）**：
> "The best performers run two tracks simultaneously: delivering today while building tomorrow's growth engine. Yet fewer than half of CEOs believe that their organizations can adapt and execute at the speed the market now requires. AI should help. But most CEOs use it for productivity gains alone, and more than 80% aren't satisfied with the results. The path forward: Build adaptability and resilience, strengthen execution, and scale AI beyond pilots."

**BCG – Drive Sustainable Cost Advantage with AI**：
> "Amid a complex economic landscape and rapidly evolving tariff dynamics, cost reduction continues to be a top priority for executives. However, executives report that only 48% of cost-saving targets are achieved … Over 90% of executives are planning to invest in AI … Already, 25% of executives report significant gains, strengthening their competitive advantage."

**Gartner – Market Guide 标准模板**：
> "**Key Findings:** Sourcing leaders who research all viable maintenance options are well-positioned to recommend cost optimization …
> **Recommendations:** Use the five evaluation steps … Compare TPSS offerings with the maintenance and support policies …"

### Metadata 字段建议

| 字段（中/英） | McKinsey | BCG | Bain | Gartner | Forrester |
|---|---|---|---|---|---|
| Title | ✓ | ✓ | ✓ | ✓ | ✓ |
| Publication date | ✓ | ✓ | ✓ | ✓ | ✓ |
| Authors（带 partner level） | ✓ | ✓ | ✓ | ✓ | ✓ |
| 机构 / 出品方 | ✓ | ✓ | ✓ | ✓ | ✓ |
| 版本号 / 修订历史 | ✗ | ✗ | ✗ | ✓ | ✓ |
| Citation 格式 | 隐式 | 隐式 | 隐式 | ✓ | ✓ |
| 数据来源声明 | ✓ | ✓ | ✓ | ✓ | ✓ |
| Disclaimer | 短 | 短 | 短 | 长（~200 字） | 长 |
| Acknowledgments | ✓ | ✓ | 可选 | ✗ | ✗ |

```python
class ReportMetadata(BaseModel):
    report_id: str
    title: str
    subtitle: Optional[str]
    scenario: Literal["S1","S2","S3","S4","S5"]

    publication_date: date
    version: str
    revision_history: list[Revision]

    authors: list[Author]
    organization: str
    contributing_agents: list[str]

    data_sources: list[DataSource]
    confidence_level: Literal["high","medium","low"]

    disclaimer: str
    citation_format: Optional[str]
    license: Optional[str]

    trace_id: str  # 对接 runs/<trace_id>/
```

---

## 第 2 部分：S1 功能迭代（Feature Roadmap）

### 标杆样本：Forrester Wave™ Customer Data Platforms For B2C, Q3 2024

- **覆盖**：12 家厂商（ActionIQ, Adobe, Amperity, BlueConic, Microsoft, mParticle, Redpoint, Salesforce, Tealium, Treasure Data, Twilio, Zeta Global）
- **链接**：
  - 主页：https://www.forrester.com/report/the-forrester-wave-tm-customer-data-platforms-for-b2c-q3-2024/
  - 厂商免费版：https://business.adobe.com/resources/reports/forrester-wave-b2c-customer-data-platforms-2024.html
  - 方法论：https://www.forrester.com/policies/forrester-wave-methodology/

### 章节结构（Forrester Wave 经典版式）

1. **Summary**（执行摘要）
2. **The [Market] Landscape**（市场格局）
3. **Evaluation Overview / Summary**（评估概要，含 Wave 四象限图）
4. **Evaluated Vendors and Inclusion Criteria**
5. **Vendor Profiles**（Leaders / Strong Performers / Contenders）
6. **Evaluation Overview / Scoring Details**（评分明细）
7. **Supplemental Material**（方法论、互动工具说明）
8. **Endnotes / Related Research**

### 评分维度（三大轴 × 子项）

**Current Offering**（Y 轴，当前能力）—— 30-100 条子项（product capabilities / ease of implementation / service & support / training）
**Strategy**（X 轴，未来策略）—— product roadmap / partner ecosystem / vision articulation
**Customer Feedback**（点的大小/halo，2024 起替代 Market Presence）—— reference response rate / breadth of functionality used / overall satisfaction

**评分结构**：
- 0-5 分制（0 = not offered；5 = best）
- 每条 criterion 配 weighting 权重（百分比）
- 每条 criterion 配 scale explanation

**四象限图**：
- X 轴 = Strategy
- Y 轴 = Current Offering
- 点大小 = Customer Feedback halo
- 三档命名（2024 起）：**Leaders / Strong Performers / Contenders**

### Vendor Profile 卡内部字段

```
position: Leader / Strong Performer / Contender
one_line_pitch: 一句话定位
strengths: 3-5 条优势 bullets（含证据）
weaknesses / cautions: 2-4 条短板 bullets
best_fit_for: 最适合的客户画像
reference_customer_feedback: 参考客户反馈摘要
```

### 业界框架补充

#### 框架 1：Battle Card（销售战卡）

11 个核心要素：
1. Competitor snapshot（创立时间 / HQ / 融资 / 员工数 / 关键管理层）
2. Target market & ICP
3. Pricing model & typical deal size（真实成交价，不是 list price）
4. Strengths & weaknesses
5. Feature comparison matrix（5-7 条决定性能力）
6. Win themes（3-4 条具体差异点）
7. Objection library（按 deal stage 组织）
8. Landmine questions（让对手弱点自然暴露的引导问句）
9. They'll say → We say（话术对子）
10. Proof points（客户引述、案例数字、第三方背书）
11. Last updated / Source

#### 框架 2：JTBD（Jobs To Be Done）+ Four Forces

核心要素：
- **Job Statement**：`When [situation], I want to [motivation], so I can [outcome]`
- **Three Layers**：functional / emotional / social
- **Four Forces of Progress**（Bob Moesta）：
  - Push（旧方案痛点）+ Pull（新方案吸引力）
  - Anxiety（对新方案焦虑）+ Habit/Inertia（旧惯性）
  - 切换条件：Push + Pull > Anxiety + Habit
- **Desired Outcomes**：`[Minimize/Maximize] + [Metric] + [Context]`，1-10 分 importance 与 satisfaction
- **Opportunity Score**：`Importance + (Importance − Satisfaction)`

#### 框架 3：Feature Comparison Matrix（加权特性矩阵）

核心要素：
- **Tier 分层**：
  - Tier 1（table-stakes，weight = 3）：缺则失资格
  - Tier 2（differentiating，weight = 2）：决定胜负
  - Tier 3（nice-to-have，weight = 1）：边缘场景
- **0-2 评分制**：0 = 不支持；1 = 部分支持；2 = 完整支持
- **加权得分公式**：`Σ(score × weight) / Σ(2 × weight) × 100`

### S1 schema 字段建议

```python
class S1FeatureIterationPayload:
    # Vendor Profiles
    vendor_profiles: list[VendorProfile]  # 每家含 position/one_line_pitch/strengths/weaknesses/best_fit_for/reference_customer_feedback

    # Feature Matrix（加权评分）
    feature_matrix: FeatureMatrix         # competitors[] + categories[]（含 tier/weight）+ features[]
    weighted_scores: dict[str, float]      # competitor_name → percentage
    tier1_disqualifiers: list[Disqualifier]  # Tier 1 缺失的竞品
    white_space_features: list[WhiteSpace]  # 没人支持的功能

    # JTBD
    job_statement: JobStatement
    desired_outcomes: list[DesiredOutcome]
    four_forces: FourForces
    competitive_alternatives: list[Alternative]
    feature_gaps: list[FeatureGap]

    # Battle Card
    win_themes: list[WinTheme]
    objections: list[Objection]
    proof_points: list[ProofPoint]
```

---

## 第 3 部分：S2 市场进入（Market Entry）

### 标杆样本

#### 报告 1：McKinsey × WFSGI – Sporting Goods 2025

- **链接**：https://www.mckinsey.com/~/media/mckinsey/industries/retail/our%20insights/sporting%20goods%20industry%20trends/2025/sporting-goods-2025-the-new-balancing-act-turning-uncertainty-into-opportunity-v3.pdf
- **总篇幅**：约 60-80 页 PDF

**章节结构**：
- Foreword / Contributors / Acknowledgements
- Executive Summary
- Chapter 1: Industry outlook — Slowing growth, persistent uncertainty
- Chapter 2: The widening activity gap — Two consumer worlds
- Chapter 3: Competitive shifts — Challengers vs. incumbents
- Chapter 4: The resurgence of in-person fitness
- Chapter 5: Live sports and entertainment convergence
- Chapter 6: The strategic playbook
- Closing perspective / Methodology

#### 报告 2：CB Insights State of AI / State of Venture 2025

- **链接**：https://www.cbinsights.com/research/report/ai-trends-2025/
- **总篇幅**：约 80-150 页 PPT 化（slide-style）

**章节结构**：
1. Headline numbers（一页式开篇 KPI）
2. Funding landscape
3. Deal activity by stage
4. Top sectors / sub-markets
5. Top investors
6. Geographic breakdown
7. Unicorn births / valuations
8. M&A and exits
9. Mosaic / Commercial Maturity scoring
10. Predictions

### 量化产物

- 市场规模：行业总规模 USD + 分区域拆解
- 增长指标：CAGR、YoY %、未来 5 年预测（low/base/high 三种情景）
- 玩家排名：Top N brands by revenue、市场份额 %、增速分级
- 消费者细分：activity gap %、segment size %
- 自有评分：Mosaic Score（0-1000）、Commercial Maturity（1-5）

### 业界框架补充

#### 框架 1：Porter Five Forces

5 个力量：
1. **Threat of New Entrants**：进入壁垒、规模经济、品牌、资本需求、转换成本、分销渠道
2. **Bargaining Power of Suppliers**：供应商集中度、替代品、前向整合威胁
3. **Bargaining Power of Buyers**：买家集中度、价格敏感度、转换成本、后向整合威胁
4. **Threat of Substitutes**：替代品价格性能比、转换成本
5. **Competitive Rivalry**：竞争者数量、行业增速、固定成本、退出壁垒

#### 框架 2：TAM / SAM / SOM

- **TAM（Total Addressable Market）**：`Industry Size × Relevant Segment %`
- **SAM（Serviceable Available Market）**：`TAM × Accessibility Filters`
- **SOM（Serviceable Obtainable Market）**：`SAM × Realistic Market Share`（成熟市场 1-5%、利基 5-15%）
- 方法论：top-down（行业报告往下切）+ bottom-up（ICP × ARPU × frequency 往上算），两者差距 < 20% 才算可信

#### 框架 3：PESTEL

6 类宏观因素：
- Political、Economic、Social、Technological、Environmental、Legal

### S2 schema 字段建议

```python
class S2MarketEntryPayload:
    # 市场规模
    market_sizing: MarketSizing  # TAM/SAM/SOM + methodology + sources
    triangulation_gap_pct: float  # top-down 与 bottom-up 误差

    # Five Forces
    five_forces: FiveForces  # 5 个 force 评级（low/medium/high）+ drivers + evidence
    industry_attractiveness_score: int  # 1-5

    # PESTEL
    pestel: PESTEL  # 6 维因素清单 + 影响（opportunity/threat）+ severity 1-5

    # 竞争格局
    top_players: list[Player]  # name + share_pct + yoy_growth + classification(challenger/incumbent)
    consumer_segments: list[Segment]  # 目标人群 + 占比

    # 趋势
    key_trends: list[Trend]  # text + supporting_data

    # 战略建议
    entry_strategy: EntryStrategy  # mode + rationale
    recommended_actions: list[Action]
```

---

## 第 4 部分：S3 定价策略（Pricing Strategy）

### 标杆样本

#### 报告 1：Simon-Kucher SaaS Pricing Case Studies

- **链接示例**：
  - https://www.simon-kucher.com/en/insights/how-tailored-pricing-and-packaging-health-it-company-helped-boost-revenue-growth
  - https://www.simon-kucher.com/en/insights/transforming-pricing-strategies-deliver-better-business-growth
- **篇幅**：每份 800-1500 字（短文案例研究）

**章节结构（4 段式）**：
1. Client situation / Challenge
2. Approach / Solution
3. Outcome / Result
4. Key takeaways

**量化产物**：
- ARR uplift：10-20%
- ARPU 提升：20-35%
- Tier 数量变化：2 → 4 / 3 packages
- 计费模式枚举：`per_seat`、`flat_rate`、`usage_based`、`hybrid`、`platform_fee`、`freemium`

#### 报告 2：CompareTiers SaaS Pricing Page Teardown

- **链接**：https://comparetiers.com/blog/saas-pricing-page-teardown
- **篇幅**：约 4000-5000 字
- **覆盖**：Notion、Slack、Linear、Figma、Basecamp、Intercom 等 10 家

**8 法则**：
1. Tier Naming（buyer-centric）
2. Anchor Pricing（中间锚点）
3. Annual vs Monthly Billing Toggle（年付默认，15-25% 提升）
4. Feature Gating
5. CTA Copy by Tier
6. Social Proof
7. Transparent Feature Comparison
8. Psychological Pricing（$99 而非 $100）

### 业界框架补充

#### 框架 1：Simon-Kucher 4-Step Value-Based Pricing

1. Map key value drivers
2. Calculate monetary benefits（conjoint analysis 等）
3. Adapt revenue models
4. Train team to sell value, not price

#### 框架 2：Good / Better / Best Packaging（三层套餐法）

- **Good (Entry)**：解决 80% 付费用户的核心需求
- **Better (Anchor)**：中间锚点，标 "Most Popular"
- **Best (Premium)**：合规、定制合同、专属支持
- （可选）**Enterprise**：Custom pricing
- 规则：3 paid 是认知最优，4+ 引发决策瘫痪

#### 框架 3：Pricing Page Audit（8 法则）

转化基准：median SaaS pricing page 转化 3-5%、top quartile 8-12%

### S3 schema 字段建议

```python
class S3PricingStrategyPayload:
    # 现状基线
    pricing_baseline: PricingBaseline  # 旧 ARPU / 旧套餐 / 旧 churn

    # Value-Based Pricing
    value_drivers: list[ValueDriver]
    feature_classification: dict  # hygiene / preference / value 三分类
    wtp_research: WTPResearch  # method + sample_size + optimal_price_point

    # Packaging（GBB）
    packaging: Packaging  # tiers[]（含 Good/Better/Best 三层 + Enterprise）+ annual_discount + default_billing

    # 竞品定价矩阵
    competitive_pricing_matrix: list[CompetitorPricing]

    # 定价页审计
    pricing_page_audit: PricingPageAudit  # 8 法则评分

    # 推荐方案
    recommendations: PricingRecommendations  # 推荐套餐 + 预期 ARR uplift % + rollout strategy
    rollout_plan: list[RolloutStep]  # 5-step：内部对齐 / 分客户层级 / phased rollout / 沟通 / 监控
```

---

## 第 5 部分：S4 持续监控（Ongoing Monitoring）

### 关键洞察：S4 的核心是 delta 而非 snapshot

S4 区别于其他 4 个场景的核心特征：**增量、时间窗、变化跟踪**。所有内容字段必须双版本（current + prior + diff）。

### 标杆样本

#### 样本 A：OSCOM Quarterly Market Intelligence Report

- **链接**：https://oscom.ai/blog/quarterly-market-intelligence-report
- **价值**：业界公认的"5 页 5 段"季度报告骨架

**5 段结构**：
1. Executive Summary（3 个 highlight + 3-5 actions）
2. Competitive Moves Log（按 competitor 分组、按 impact 排序）
3. Threat Assessment（severity × likelihood 2×2，最多 3-5 条）
4. Opportunity Identification（4 类：abandoned segments / product gaps / messaging white space / operational weaknesses）
5. Recommended Actions（8-12 条，按 team 分组）

#### 样本 B：IndustryLens Living Battlecard Schema

- **链接**：https://industry-lens.com/resources/battlecard-templates
- **价值**：明确给出"由监控引擎喂养的活体 Battlecard"的字段 schema

**10 个 section**：
1. Quick Summary
2. Primary Threat
3. Messaging & Positioning
4. Pricing & Packaging
5. Product Strategy
6. Advertising Activity
7. Customer Sentiment
8. Win/Loss Themes
9. Monitoring Priorities
10. Confidence Composite + Last Updated / Source

**三个 S4 必抄的设计**：
1. 每节单独打 confidence（full/partial/empty）—— 缺信号时直说，不编造
2. 每条 claim 都链回 source —— 重试/反馈闭环时可追溯
3. 存储 prior version 并 diff —— "intelligence is the delta"

#### 样本 C：Klue Sales Battlecards 101

- **链接**：https://klue.com/blog/competitive-battlecards-101
- **FIA 框架**：每条情报必须同时给出 Fact / Impact / Act

### 业界框架补充

#### 框架 1：Klue FIA Framework

- **Fact**：上下文 + 卡片标题 + 竞争洞察本身
- **Impact**：这个洞察为什么重要、什么场景下用得上
- **Act**：可执行的话术、提问、后续动作

#### 框架 2：Tierly Per-Section Update Cadence Table

不同章节按不同频率更新：
- Pricing/Features：月更
- Executive Summary/Profiles/SWOT/Positioning Map/Recommendations：季更

### S4 schema 字段建议

```python
class S4MonitoringPayload:
    # 时间窗
    last_review_date: date
    current_review_date: date
    review_period_label: str  # "2026 Q1"
    monitored_competitors: list[str]

    # 变更日志（按类型分桶）
    new_features: list[FeatureChange]  # date + feature_name + source_url + implication + fact + impact + act
    removed_features: list[FeatureChange]
    pricing_changes: list[PricingChange]  # date + change_type + before + after + source_url
    messaging_changes: list[MessagingChange]
    news_events: list[NewsEvent]  # date + category(funding|partnership|leadership|legal|product_launch) + headline
    org_changes: list[OrgChange]

    # 威胁与机会（结构化）
    threats: list[Threat]  # title + severity + likelihood + quadrant + evidence_ref + recommended_response
    opportunities: list[Opportunity]  # type + evidence_ref + effort + expected_impact + first_step
    actions: list[Action]  # description + owner_team + due_date + priority_tier + status

    # 趋势方向
    sentiment_trend: Literal["up", "flat", "down"]
    pricing_trend: Literal["up", "flat", "down"]
    release_velocity_trend: Literal["accelerating", "steady", "slowing"]
    threat_level_trend: Literal["escalating", "stable", "de_escalating"]

    # 活体 Battlecard
    battlecards: list[Battlecard]  # 每个竞品一张
```

每个 BattlecardSection 通用基类：
```python
class BattlecardSection:
    content: str
    confidence: Literal["full", "partial", "empty"]
    prior_content: Optional[str]
    diff_summary: Optional[str]
    changed_at: Optional[datetime]
    sources: list[SourceRef]
```

**这套机制天然契合项目里的 `trace_writer` + `_vN` 快照机制**——可以把每个 trace 的 profile 当作"上一版"喂回来 diff。

---

## 第 6 部分：S5 战略定位（Positioning）

### 标杆样本：Gartner Magic Quadrant for Analytics and BI Platforms 2024

- **覆盖**：20 家厂商
- **链接**：
  - 主页：https://www.gartner.com/en/documents/5519595
  - 方法论：https://www.gartner.com/en/research/methodologies/magic-quadrants-research

### 章节结构（Gartner MQ 经典版式）

1. Market Definition / Description
2. Magic Quadrant Figure
3. Vendor Strengths and Cautions
4. Vendors Added / Dropped
5. Inclusion and Exclusion Criteria
6. Honorable Mentions
7. Evaluation Criteria（Ability to Execute + Completeness of Vision）
8. Quadrant Descriptions（Leaders / Challengers / Visionaries / Niche Players）
9. Context
10. Market Overview
11. Evidence
12. Evaluation Criteria Definitions

### 评分维度（两大轴 × 15 子项）

**Ability to Execute**（Y 轴 ↑，"今天做得好不好"）—— 7 子项：
1. Product or Service
2. Overall Viability
3. Sales Execution / Pricing
4. Market Responsiveness / Track Record
5. Marketing Execution
6. Customer Experience
7. Operations

**Completeness of Vision**（X 轴 →，"看得有多远"）—— 8 子项：
1. Market Understanding
2. Marketing Strategy
3. Sales Strategy
4. Offering (Product) Strategy
5. Business Model
6. Vertical / Industry Strategy
7. Innovation
8. Geographic Strategy

**四象限定义**：
- **Leaders**：执行强 + 视野远（右上）
- **Challengers**：执行强 + 视野弱（右下）
- **Visionaries**：执行弱 + 视野远（左上）
- **Niche Players**：执行弱 + 视野弱（左下）

### Vendor Strengths & Cautions 卡

```
vendor_name
quadrant: Leaders / Challengers / Visionaries / Niche Players
overview: 1-2 句产品定位
strengths[]: 3-5 条优势（每条对应一个评估子项）
cautions[]: 3-5 条注意事项 / 短板
```

### 业界框架补充

#### 框架 1：Perceptual Map / Positioning Map

- **定义**：以两条客户价值维度为轴的 2x2 散点图
- **轴选择规则**：
  - 必须是买家做决策的维度（来自 win/loss 访谈，不是内部脑暴）
  - 避免相关维度
  - 好的轴会引发争论
- **数据点**：4-8 个竞品 + 本品（最多 50 个）
- **评分尺度**：1-9 或 1-5 分（基于客户调研，非自评）

#### 框架 2：Strategy Canvas + ERRC Grid（蓝海战略）

- **Competitive Factors**：行业集体投入的维度（5-15 个）
- **Value Curve**：每个厂商在所有因子上的投入水平连成一条折线
- **ERRC Grid**：
  - **Eliminate**：行业长期竞争但应彻底消除的因子
  - **Reduce**：应远低于行业标准的因子
  - **Raise**：应远高于行业标准的因子
  - **Create**：行业从未提供、应全新创造的因子
- **三大判定标准**：focus / divergence / compelling tagline

#### 框架 3：Geoffrey Moore Positioning Statement

```
For (target customer)
who (statement of need or opportunity),
the (product name)
is a (product category)
that (key benefit, compelling reason to buy).
Unlike (primary competitive alternative),
our product (statement of primary differentiation).
```

6 个必填位：
1. Target customer（具体到角色）
2. Need or opportunity
3. Product category（决定客户拿你跟谁比）
4. Key benefit
5. Primary competitive alternative
6. Primary differentiation

### S5 schema 字段建议

```python
class S5PositioningPayload:
    # Vendor Profiles（仿 Gartner MQ）
    vendor_profiles: list[VendorPositioningProfile]  # quadrant + overview + strengths + cautions

    # 二维定位
    perceptual_map: PerceptualMap  # x_axis + y_axis + plotted_brands + white_space + cluster_zones
    axis_choice_rationale: AxisRationale

    # Strategy Canvas + ERRC
    strategy_canvas: StrategyCanvas  # competitive_factors + value_curves + industry_average
    errc_grid: ERRCGrid  # eliminate + reduce + raise + create
    blue_ocean_move: BlueOceanMove  # new_value_curve + tagline + target_noncustomers

    # Positioning Statement
    positioning_statement: PositioningStatement  # 6 个必填位
    category_strategy: CategoryStrategy  # chosen_category + competitors_implied
```

---

## 第 7 部分：综合关键决策建议

### 1. 架构决策（R2: BaseReport + 场景 payload）

```python
class BaseReport(BaseModel):
    # 13 个通用骨架字段
    title: str
    subtitle: Optional[str]
    at_a_glance: list[str]
    executive_summary: ExecutiveSummary
    background: str
    scope: ReportScope
    methodology: Methodology
    key_findings: list[Finding]
    analysis_sections: list[AnalysisSection]  # 场景 payload 注入这里
    conclusions: str
    recommendations: list[Recommendation]
    appendix: Appendix
    metadata: ReportMetadata

    # 场景判别
    scenario: Literal["S1","S2","S3","S4","S5"]
    scenario_payload: Union[
        S1FeatureIterationPayload,
        S2MarketEntryPayload,
        S3PricingStrategyPayload,
        S4MonitoringPayload,
        S5PositioningPayload,
    ] = Field(discriminator='scenario_type')
```

### 2. 设计原则

- **`ExecutiveSummary` 用混合制**（5 个固定子字段，内部自由文本）
- **`Methodology` 必须独立成节**（4 个子字段：data_sources / collection_approach / evaluation_criteria / limitations）
- **`data_sources` 列表是溯源 schema 的本体**——每个 finding / recommendation 应能引用 source_id 形成 footnote 关系
- **专属元素放各场景 payload**（Feature Matrix / Pricing Table / Perceptual Map 等）
- **S4 双版本字段**（current + prior + diff_summary + changed_at）—— 区别于其他 4 场景的核心

### 3. 报告字数预期（按方案乙：关键章节深耕）

整份报告 7000-8000 字：
- 通用骨架部分约 2000-2500 字（Executive Summary 600 + Background 400 + Methodology 300 + Key Findings 500 + Conclusions 300 + Recommendations 400）
- 场景 payload 部分约 4000-5000 字（其中 1-2 个核心 section 各 3000 字深耕，其他 section 简短）

### 4. 工程取舍

- writer 重构为编排者：先生成大纲，再分章节调用
- LLM 调用次数从 4 → 8-12（关键章节单独调）
- 单次分析时间从 5-8 分钟 → 12-18 分钟
- 答辩 demo 演示时长适配（建议直接演示成功 trace 的报告，不现场跑）

---

## 调研机构与样本来源汇总

### 通用骨架研究
- McKinsey & Company（The Energy Transition 2022, Smart Cities MGI 2018, Sporting Goods 2025）
- Boston Consulting Group（Where's the Value in AI 2024, Widening AI Value Gap 2025, Cost Advantage with AI）
- Bain & Company（2026 CEO Agenda, Innovation Rewired, B2B Growth Agenda 2026）
- Gartner（Magic Quadrant Methodology, Market Guide 模板）
- Forrester（Wave Methodology, AI/ML Platforms Q3 2022）

### S1 标杆
- Forrester Wave™: Customer Data Platforms For B2C, Q3 2024
- Forrester Wave™: Core CRM Solutions, Q3 2022

### S2 标杆
- McKinsey × WFSGI Sporting Goods 2025
- CB Insights State of AI 2025 / State of Venture 2025

### S3 标杆
- Simon-Kucher SaaS Pricing Case Studies（7 份）
- CompareTiers SaaS Pricing Page Teardown

### S4 标杆
- OSCOM Quarterly Market Intelligence Report
- IndustryLens Living Battlecard Schema
- Klue Sales Battlecards 101
- Tierly CI Report Template

### S5 标杆
- Gartner Magic Quadrant for Analytics and BI Platforms 2024
- Gartner Magic Quadrant for DevOps Platforms 2024

### 框架理论来源
- Battle Card：Oden, Federico Presicci, Industry-Lens
- JTBD：Tony Ulwick, Bob Moesta
- Porter Five Forces：Michael Porter, HBR 1979
- Strategy Canvas / Blue Ocean：Kim & Mauborgne
- Positioning Statement：Geoffrey Moore, Crossing the Chasm
- Value-Based Pricing：Simon-Kucher 4-Step
- Perceptual Map：Atlassian, perceptualmaps.com
