# PRD: AI 驱动的竞品分析 Agent 协作系统

> **文档版本**：V3.0
> **最后更新**：2026-05-31
> **V3.0 变更**：基于竞品分析 SOP 对齐，新增分析目标输入、竞品分类、四维分析框架、行动建议时间分层
> **作者**：OPENW1NDOW
> **项目类型**：字节跳动 CIS AI 全栈项目挑战赛 — Agent 智能体赛道

---

## 1. 需求背景与目标

### 1.1 背景

企业产品团队在进行竞品分析时，需经历"信息搜集 → 功能对比 → 用户评价整理 → SWOT 分析 → 结构化报告输出"多个环节。该流程存在三个核心问题：

- **效率低**：单次完整竞品分析耗时 2-3 个工作日，其中 70% 时间用于信息搜集和整理
- **质量不稳定**：分析结果高度依赖分析师个人经验和行业认知，同一竞品不同人分析结论差异大
- **信息源分散**：数据散落在应用商店、官网、行业媒体、社交平台等 8+ 个渠道，人工难以全覆盖

### 1.2 目标

构建一个多 Agent 协作的自动化竞品分析系统，实现：

| 目标 | 量化指标 |
|------|----------|
| 效率提升 | 端到端分析时间从 2-3 天缩短至 10 分钟以内 |
| 覆盖率提升 | 信息源覆盖从人工的 3-4 个提升至 8+ 个 |
| 输出一致性 | Schema 驱动的结构化输出，消除人为差异 |
| 可追溯性 | 100% 分析结论绑定数据来源，支持一键溯源 |

### 1.3 考察要点映射

本课题的核心考察维度（来自评分标准）：

| 维度 | 权重 | 关键要求 |
|------|------|----------|
| 多 Agent 协作与输出可信度 | 35% | 角色清晰、结构化消息、反馈闭环、信息溯源 |
| 技术深度与工程完整度 | 25% | 端到端链路、可观测性、错误恢复 |
| 业务价值与产品体验 | 20% | 效率提升可量化、交互流畅、业务闭环 |
| 代码质量与文档 | 10% | 模块化、文档齐全、Git 规范 |
| 合规与答辩 | 10% | 数据采集合规、隐私安全 |

---

## 2. 用户痛点分析

### 2.1 使用角色

| 角色 | 描述 | 使用频率 | 技术水平 |
|------|------|----------|----------|
| **产品经理**（主要） | 负责产品规划，需要定期跟踪竞品动态 | 每周 1-2 次 | 非技术，熟悉业务 |
| **市场分析师**（次要） | 负责行业研究，需要横向对比多个竞品 | 每月 2-3 次 | 非技术，熟悉数据 |
| **战略分析师**（次要） | 负责竞争策略，需要深度 SWOT 分析 | 每月 1 次 | 非技术，熟悉战略框架 |

### 2.2 痛点矩阵

| 角色 | 问题场景 | 问题严重性 | 期望结果 |
|------|----------|-----------|----------|
| 产品经理 | 收到"分析支付宝最近新功能"的任务，需手动打开 App Store、官网、36氪等 8+ 个网站逐一搜集，再手动整理成文档 | 耗时 2-3 天，期间核心产品工作被挤占 | 输入竞品名称，10 分钟内获得结构化报告 |
| 产品经理 | 不同分析师对同一竞品的功能梳理维度不同，导致跨团队对比困难 | 决策依据不一致，需反复对齐 | 统一 Schema 驱动，输出格式一致 |
| 市场分析师 | 搜集到的信息来自不同时间点，版本号、定价等数据存在矛盾 | 结论可信度低，需反复验证 | 每条数据标注采集时间和来源，矛盾数据自动标记 |
| 战略分析师 | SWOT 分析依赖个人判断，缺乏数据支撑 | 结论主观性强，难以说服管理层 | SWOT 每个维度绑定具体数据来源 |

### 2.3 关键解法

针对上述痛点，本系统的解法策略：

1. **Agent 化分工**：将竞品分析拆解为采集、分析、撰写、质检四个专职 Agent，模拟真实调研团队的分工协作
2. **Schema 驱动**：定义竞品知识 Schema（功能树、定价模型、用户画像），强制所有 Agent 产出符合 Schema，消除输出不一致
3. **反馈闭环**：质检 Agent 可识别问题并打回上游 Agent 重做，形成自我校验机制
4. **全链路溯源**：每条分析结论绑定原始数据源 URL 和原文片段，支持一键跳转验证

---

## 3. 名词解释

| 术语 | 定义 |
|------|------|
| **Agent** | 基于 LLM 的自主任务执行单元，具有独立的角色定义、输入输出格式和工具调用能力 |
| **Schema** | 预定义的数据结构规范，约束 Agent 的输出格式和字段完整性 |
| **反馈闭环** | 质检 Agent 发现问题后，将问题打回上游 Agent 修正的机制 |
| **信息溯源** | 为每条分析结论绑定原始数据来源（URL + 原文片段），支持追溯验证 |
| **DAG** | 有向无环图，用于描述 Agent 间的任务流转关系（本系统中含质检→采集的环路） |
| **功能树** | 竞品功能的层级结构，按模块 → 子功能两级组织 |
| **SWOT** | Strengths（优势）、Weaknesses（劣势）、Opportunities（机会）、Threats（威胁）的战略分析框架 |

---

## 4. 竞品知识 Schema

### 4.1 输入 Schema

```yaml
CompetitorInput:
  competitors: list[CompetitorBasic]  # 竞品列表（1-5 个）
  analysis_context: str               # 自然语言描述分析意图

CompetitorBasic:
  name: str                # 竞品名称，如"支付宝"
  company: str             # 所属公司（选填，系统可推断）
  category: str            # 行业分类（选填，系统可推断）
```

**输入校验规则**：
- `competitors` 至少 1 个，最多 5 个
- 每个竞品的 `name` 不能为空，长度 2-50 字符
- `company` 和 `category` 为选填，采集 Agent 可自动推断
- `analysis_context` 为自由文本，描述分析动机和关注点（如"分析支付宝最近的新功能，我们准备做一个类似的功能"）

**分析目标解析**：采集 Agent 内部从 `analysis_context` 中解析出结构化目标：

```yaml
AnalysisGoal:
  goal_type: str             # feature_iteration / pricing_strategy / market_entry / competitive_monitoring
  product_stage: str         # entering / growing / mature
  focus_area: str            # 用户关注的具体领域（如有）
  output_expectation: str    # info（了解动态）/ knowledge（理解规律）/ action（指导决策）
```

解析规则：
- 如果 `analysis_context` 中信息不足以判断，使用默认值：`goal_type=competitive_monitoring`，`product_stage=growing`，`output_expectation=action`
- `goal_type` 决定采集深度：`feature_iteration` 聚焦功能细节，`pricing_strategy` 聚焦定价页面，`market_entry` 全量采集

### 4.2 采集 Agent 输出 Schema

```yaml
CompetitorProfile:
  classification:
    competitor_type: str     # 核心/标杆/间接/潜力/替代/翘楚/避坑
    reason: str              # 分类理由（用于溯源）
  basic_info:
    name: str                # 竞品名称
    company: str             # 所属公司
    version: str             # 当前版本号（无法获取时标记 "unknown"）
    release_date: str        # 最近更新日期（ISO 8601 格式）
    platform: list[str]      # 支持平台：iOS / Android / Web / Desktop
  feature_tree:
    - module: str            # 功能模块名（如"支付"、"理财"、"社交"）
      features:
        - name: str          # 功能名称
          description: str   # 功能描述（50-200 字）
          is_new: bool       # 是否为近 90 天新增
          source_url: str    # 功能信息来源 URL
  pricing:
    model: str               # 免费 / 免费增值 / 订阅 / 一次性付费
    tiers:                   # 价格档位列表
      - name: str            # 档位名称（如"基础版"、"专业版"）
        price: str           # 价格（含货币单位）
        features: list[str]  # 该档位包含的功能
    source_url: str          # 定价信息来源 URL
  user_reviews:
    rating: float            # 综合评分（0-5 分制）
    total_reviews: int       # 评论总数
    positive_summary: str    # 好评关键词总结（50-100 字）
    negative_summary: str    # 差评关键词总结（50-100 字）
    sample_reviews:          # 代表性评论（3-5 条）
      - content: str         # 评论内容
        rating: int          # 评分
        source: str          # 来源平台
        source_url: str      # 评论来源 URL
  recent_updates:            # 近 90 天更新记录
    - date: str              # 更新日期
      title: str             # 更新标题
      summary: str           # 更新摘要（30-100 字）
      source_url: str        # 溯源链接
  metadata:
    collected_at: str        # 采集时间（ISO 8601）
    data_sources: list[str]  # 使用的数据源列表
    completeness_score: float # 数据完整度评分（0-1）
```

**数据完整度计算规则**：
- `basic_info` 每缺失一个字段扣 0.05
- `feature_tree` 为空扣 0.3
- `pricing` 为空扣 0.15
- `user_reviews` 为空扣 0.15
- `recent_updates` 为空扣 0.1
- 完整度低于 0.5 时，采集 Agent 需在 metadata 中标注原因

### 4.3 分析 Agent 输出 Schema

分析 Agent 基于四大维度（定位、功能、商业、运营）进行结构化对比，每个维度的结论必须绑定数据来源。

```yaml
CompetitiveAnalysis:
  # 维度一：产品定位与目标用户
  positioning:
    per_competitor:
      - name: str
        target_users: str        # 目标用户画像
        core_scenario: str       # 核心使用场景
        pain_points: str         # 解决的用户痛点
        value_proposition: str   # 价值主张
    source_urls: list[str]

  # 维度二：功能与体验
  feature_matrix:
    - feature: str               # 功能名称
      our_product: str           # 我方状态：有/无/计划中/不适用
      competitors: dict          # {竞品名: 有/无/部分支持}
      gap_level: str             # 领先 / 持平 / 落后 / 差异化
      evidence: str              # 判断依据（引用采集数据）
      source_urls: list[str]

  # 维度三：商业模式
  business_model:
    per_competitor:
      - name: str
        revenue_model: str       # 盈利模式（会员/广告/佣金/增值服务）
        pricing_details: str     # 定价详情
        free_vs_paid: str        # 免费与付费权益划分
    source_urls: list[str]

  # 维度四：运营与增长
  operations:
    per_competitor:
      - name: str
        growth_strategy: str     # 增长策略
        marketing_channels: str  # 营销渠道
        content_strategy: str    # 内容策略
    source_urls: list[str]

  # 用户情感对比
  user_sentiment:
    summary: str                 # 用户情感对比总结（100-200 字）
    per_competitor: dict         # {竞品名: 情感分析摘要}
    source_urls: list[str]

  # SWOT 分析（每个点绑定维度来源）
  swot:
    strengths:
      - point: str               # 优势描述
        evidence: str            # 数据支撑
        dimension: str           # 来自哪个维度（positioning/feature/business/operations）
        source_urls: list[str]
    weaknesses:
      - point: str
        evidence: str
        dimension: str
        source_urls: list[str]
    opportunities:
      - point: str
        evidence: str
        dimension: str
        source_urls: list[str]
    threats:
      - point: str
        evidence: str
        dimension: str
        source_urls: list[str]

  # 雷达图评分（五维量化）
  radar_scores:
    - competitor: str
      dimensions:
        feature_breadth: float    # 功能丰富度（0-5）
        usability: float          # 易用性（0-5）
        cost_effectiveness: float # 性价比（0-5）
        stability: float          # 稳定性（0-5）
        design_quality: float     # 设计美观度（0-5）
```

### 4.4 最终报告 Schema

```yaml
FinalReport:
  title: str                     # 报告标题
  executive_summary:             # 执行摘要（必须回答四个核心问题）
    what_competitors_did_right: str   # 竞品做对了什么？哪些值得借鉴？
    what_competitors_did_wrong: str   # 竞品的短板在哪里？
    our_opportunities: str            # 我们的差异化机会是什么？
    next_steps_summary: str           # 接下来优先做什么？
  sections:                      # 各章节
    - title: str                 # 章节标题
      content: str               # 章节内容（Markdown 格式）
      source_refs: list[str]     # 引用的数据来源编号
  action_items:                  # 行动建议（按时间分层）
    immediate:                   # 短期（1 个月内）
      - priority: str            # 高 / 中 / 低
        description: str
        rationale: str
        source_urls: list[str]
    short_term:                  # 中期（3 个月内）
      - priority: str
        description: str
        rationale: str
        source_urls: list[str]
    long_term:                   # 长期（6 个月内）
      - priority: str
        description: str
        rationale: str
        source_urls: list[str]
  metadata:
    competitors_analyzed: list[str]
    analysis_goal: AnalysisGoal  # 解析出的分析目标（用于溯源）
    generated_at: str
    data_sources: list[str]      # 所有数据来源 URL（去重）
    quality_score: float         # 报告质量评分（0-1）
    warnings: list[str]          # 质量警告
```

---

## 5. Agent 角色设计

### 5.1 总体架构

```
用户输入竞品列表 + 分析意图描述
       │
       ▼
  ┌─────────────────────────────────┐
  │  采集 Agent                      │
  │  Step 1: 解析分析目标             │
  │  Step 2: 竞品分类（7 类）         │
  │  Step 3: 差异化并行采集           │
  └──────┬──────────────────────────┘
         │ CompetitorProfile[]
         ▼
  ┌─────────────┐
  │  分析 Agent   │  四维框架对比（定位/功能/商业/运营）+ SWOT + 雷达评分
  └──────┬──────┘
         │ CompetitiveAnalysis
         ▼
  ┌─────────────┐
  │  撰写 Agent   │  四段式执行摘要 + 时间分层行动建议
  └──────┬──────┘
         │ FinalReport
         ▼
  ┌─────────────┐
  │  质检 Agent   │  校验数据完整性、结论溯源
  └──────┬──────┘
         │
    ┌────┴────┐
    │         │
  通过      不通过 ──→ 打回至采集/分析 Agent 重做
    │
    ▼
  输出报告
```

### 5.2 各 Agent 职责

| Agent | 输入 | 输出 | 核心职责 | 工具依赖 |
|-------|------|------|----------|----------|
| 采集 Agent | CompetitorInput | CompetitorProfile[] | 内部三步走：①解析分析目标 ②竞品分类（7 类） ③按类型差异化采集。从公开源并行采集数据，结构化存储 | HTTP 客户端、HTML 解析器、LLM（目标解析+竞品分类+信息抽取） |
| 分析 Agent | CompetitorProfile[] | CompetitiveAnalysis | 基于四维框架（定位/功能/商业/运营）进行结构化对比，生成功能矩阵、SWOT、雷达评分 | LLM（推理分析） |
| 撰写 Agent | CompetitiveAnalysis | FinalReport | 组装结构化报告，生成四段式执行摘要和时间分层行动建议 | LLM（文本生成） |
| 质检 Agent | FinalReport | 通过/不通过 + RejectionFeedback | 校验 Schema 完整性、结论有数据支撑、溯源链接有效 | URL 校验器、Schema 校验器、LLM（质量评估） |

### 5.3 反馈闭环机制

质检 Agent 发现问题时，输出结构化的打回消息：

```yaml
RejectionFeedback:
  passed: bool
  issues:
    - agent: str             # 问题归属的 Agent（collector / analyzer / writer）
      field: str             # 问题字段路径（如 "feature_tree[0].features"）
      severity: str          # 严重程度：critical / major / minor
      reason: str            # 具体问题描述
      suggestion: str        # 修改建议
  retry_count: int           # 当前重试次数
  max_retries: int           # 最大重试次数（默认 2）
```

**闭环规则**：
- 质检 Agent 最多打回 **2 次**，超过后强制输出报告并在 `metadata.warnings` 中标注
- 打回时，被打回的 Agent 仅修正 `issues` 中指出的问题，不重新执行全部逻辑
- 第 2 次打回仅处理 `severity` 为 `critical` 和 `major` 的问题
- 每次打回修正后，`retry_count` 递增

### 5.4 Agent 间消息传递协议

所有 Agent 间传递的消息遵循统一格式：

```yaml
AgentMessage:
  from: str                  # 发送方 Agent 名称
  to: str                    # 接收方 Agent 名称
  message_type: str          # task / result / feedback / retry
  payload: dict              # 消息内容（对应各 Agent 的输入/输出 Schema）
  timestamp: str             # 消息时间戳
  trace_id: str              # 追踪 ID（同一次分析任务共享）
```

---

## 6. 业务流程

### 6.1 端到端流程

```
[用户] 输入竞品名称列表 + 分析意图描述
    │
    ▼
[系统] 输入校验（名称合法性、数量上限 1-5）
    │ 校验通过
    ▼
[采集 Agent] 内部三步走
    │
    ├─ Step 1: 目标解析
    │   从 analysis_context 中解析出 goal_type、product_stage、
    │   focus_area、output_expectation
    │
    ├─ Step 2: 竞品分类
    │   LLM 判断每个竞品属于核心/标杆/间接/潜力/替代/翘楚/避坑
    │
    └─ Step 3: 差异化采集
        按竞品分类决定采集深度，并行采集各竞品数据
        核心竞品 → 全量采集（功能+定价+评论+动态）
        翘楚竞品 → 聚焦功能亮点
        避坑竞品 → 聚焦负面反馈
    │
    ▼
[采集 Agent] 输出 CompetitorProfile[]，检查数据完整度
    │
    ├─ 完整度 ≥ 0.5 → 传递给分析 Agent
    └─ 完整度 < 0.5 → 标记警告，仍传递（降级处理）
    │
    ▼
[分析 Agent] 基于四维框架生成 CompetitiveAnalysis
    （定位 / 功能 / 商业 / 运营 + SWOT + 雷达评分）
    │
    ▼
[撰写 Agent] 生成 FinalReport
    （四段式执行摘要 + 时间分层行动建议）
    │
    ▼
[质检 Agent] 执行质量检查
    │
    ├─ 通过 → 输出报告给用户
    │
    └─ 不通过 → 生成 RejectionFeedback
        │
        ├─ retry_count < max_retries → 打回对应 Agent 修正
        │   │
        │   ▼
        │   [被指定 Agent] 根据 feedback 修正
        │   │
        │   └─→ 重新提交质检
        │
        └─ retry_count ≥ max_retries → 强制输出报告 + 质量警告
```

### 6.2 异常场景矩阵

| 阶段 | 异常场景 | 触发条件 | 业务后果 | 处理方案 |
|------|----------|----------|----------|----------|
| **输入** | 竞品名称不存在 | 搜索无结果 | 无法采集数据 | 提示用户确认名称，建议修改 |
| **输入** | 竞品名称过于宽泛 | 如输入"支付"而非"支付宝" | 采集目标不明确 | 提示用户输入具体产品名称 |
| **输入** | 竞品数量超限 | 输入 > 5 个竞品 | 系统负载过高 | 仅处理前 5 个，提示用户 |
| **采集** | 目标网页不可访问 | 403/404/超时 | 该数据源缺失 | 跳过该源，标记为不可用，继续其他源 |
| **采集** | 反爬机制触发 | 验证码/IP 封禁 | 采集中断 | 降低采集频率，切换 User-Agent，失败则跳过 |
| **采集** | 网页结构变化 | HTML 格式不符合预期 | 解析失败 | 使用 LLM 兜底抽取，失败则标记该字段为 "unknown" |
| **采集** | 所有数据源均不可用 | 网络故障或全面封禁 | 无法产出报告 | 返回错误提示，建议稍后重试 |
| **分析** | LLM 输出格式不符 | 返回非 YAML/JSON | 无法解析结果 | 重试 1 次（调整 Prompt），仍失败则使用默认值填充 |
| **分析** | Token 超限 | 输入数据过长 | LLM 调用失败 | 对输入数据进行摘要压缩后重试 |
| **撰写** | 执行摘要过短/过长 | < 100 字或 > 800 字 | 报告质量不达标 | 质检打回，要求调整篇幅 |
| **质检** | 溯源链接失效 | URL 返回非 200 | 结论可信度降低 | 标记为失效链接，不阻塞报告输出 |
| **质检** | 循环打回超限 | retry_count ≥ max_retries | 修正无法收敛 | 强制输出报告，附加质量警告 |
| **系统** | LLM 服务不可用 | Doubao API 故障 | 所有 Agent 停摆 | 返回错误提示，建议稍后重试 |
| **系统** | 单次分析超时 | 端到端超过 10 分钟 | 用户体验差 | 超时后输出当前阶段的中间产物 |

---

## 7. 功能清单与优先级

### P0 — 核心功能（MVP，必须交付）

| 编号 | 功能 | 描述 | 验收标准 |
|------|------|------|----------|
| F01 | 竞品输入 | 用户输入竞品名称列表和分析意图描述 | 支持 1-5 个竞品，接受自然语言描述分析目标 |
| F02 | 分析目标解析 | 从自然语言描述中解析结构化分析目标 | 输出 goal_type/product_stage/focus_area/output_expectation |
| F03 | 竞品分类 | 自动判断竞品类型（7 类）并决定采集策略 | 分类结果合理，有分类理由 |
| F04 | 数据采集 | 按竞品分类差异化采集公开数据 | 覆盖 ≥ 4 个数据源，输出符合 CompetitorProfile Schema |
| F05 | 竞品分析 | 基于四维框架（定位/功能/商业/运营）进行结构化对比 | 输出符合 CompetitiveAnalysis Schema，每条结论有来源 |
| F06 | 报告生成 | 组装结构化报告，含四段式执行摘要和时间分层行动建议 | 输出符合 FinalReport Schema |
| F07 | 质量检查 | 校验报告完整性和溯源有效性 | 可识别 Schema 缺失、无来源结论、失效链接 |
| F08 | 反馈闭环 | 质检打回 → 上游修正 → 重新提交 | 打回后输出有改善（字段补全或来源补充） |
| F09 | 信息溯源 | 报告中展示数据来源和原文片段 | 每条结论可点击溯源链接查看原文 |
| F10 | 可观测性 | 展示 Agent 决策过程和中间产物 | 每个 Agent 的输入/输出/耗时可查看 |

### P1 — 增强功能（有时间则做）

| 编号 | 功能 | 描述 | 验收标准 |
|------|------|------|----------|
| F11 | 采集降级策略 | 数据源不可用时的自动降级 | 单源失败不影响整体报告产出 |
| F12 | 报告质量评分 | 对报告质量进行量化评分 | 输出 0-1 的质量评分和具体警告项 |
| F13 | 进度展示 | 实时展示分析进度 | 用户可看到当前处于采集/分析/撰写/质检哪个阶段 |
| F14 | 历史报告缓存 | 相同竞品短期内不重复采集 | 7 天内的相同竞品分析直接返回缓存 |

### P2 — 扩展功能（优先级最低）

| 编号 | 功能 | 描述 | 验收标准 |
|------|------|------|----------|
| F15 | 报告导出 | 导出为 Markdown / PDF | 支持至少一种导出格式 |
| F16 | 自定义分析维度 | 用户添加自定义对比维度 | 支持用户输入额外维度并纳入分析 |
| F17 | 历史对比 | 对比两次分析结果的差异 | 展示功能变化、定价变化等 diff |

---

## 8. 数据源与采集策略

### 8.1 数据源清单

| 数据源 | 类型 | 采集内容 | 优先级 | 可靠性 |
|--------|------|----------|--------|--------|
| App Store | 应用商店 | 评分、评论、版本更新日志 | P0 | 高 |
| 应用宝 | 应用商店 | 评分、评论、下载量 | P0 | 高 |
| 竞品官网 | 官方站点 | 功能介绍、定价页面 | P0 | 高 |
| 36氪 | 行业媒体 | 产品动态、行业分析 | P1 | 中 |
| 虎嗅 | 行业媒体 | 产品动态、深度分析 | P1 | 中 |
| 微博 | 社交媒体 | 用户反馈、舆情 | P2 | 低 |
| 小红书 | 社交媒体 | 用户体验、口碑 | P2 | 低 |
| 知乎 | 社区 | 深度讨论、专业评价 | P1 | 中 |

### 8.2 采集策略

- **并行采集**：多个竞品的数据采集并行执行，同一竞品的多个数据源并行执行
- **超时控制**：单个数据源采集超时 30 秒，超时后跳过
- **频率控制**：同一域名的请求间隔 ≥ 2 秒，避免触发反爬
- **User-Agent 轮换**：使用 3-5 个不同的 User-Agent 随机切换
- **robots.txt 遵守**：采集前检查目标站点的 robots.txt，遵守其规则

### 8.3 降级策略

| 降级场景 | 处理方式 |
|----------|----------|
| 单个数据源不可用 | 跳过该源，标记为不可用，继续其他源 |
| 某竞品所有商店源不可用 | 使用官网 + 媒体源兜底，标记评分数据缺失 |
| 某竞品所有源不可用 | 从分析中移除该竞品，提示用户 |
| 所有竞品所有源不可用 | 返回错误，建议稍后重试 |

---

## 9. 非功能性需求

### 9.1 性能要求

| 指标 | 要求 |
|------|------|
| 单竞品分析端到端时间 | ≤ 5 分钟 |
| 3 竞品对比分析端到端时间 | ≤ 8 分钟 |
| 5 竞品对比分析端到端时间 | ≤ 10 分钟 |
| 前端页面加载时间 | ≤ 2 秒 |

### 9.2 可靠性要求

| 指标 | 要求 |
|------|------|
| 单次分析成功率 | ≥ 90%（允许部分数据源失败） |
| LLM 调用成功率 | ≥ 95%（含重试） |
| 报告 Schema 合规率 | 100%（质检保证） |

### 9.3 可观测性要求

| 可观测项 | 记录内容 | 存储方式 |
|----------|----------|----------|
| Agent 调用日志 | 每个 Agent 的输入、输出、耗时 | 本地日志文件 |
| 决策过程 | Agent 的 Prompt + Response 完整记录 | 本地日志文件 |
| Token 消耗 | 每次 LLM 调用的 Token 用量和费用 | 本地日志文件 |
| 错误记录 | 失败的采集请求、超时、解析错误 | 本地日志文件 |
| 数据溯源 | 每条结论的来源 URL 和原文片段 | 报告内嵌 |

---

## 10. 验收标准

### 10.1 功能验收

| 验收项 | 验收标准 | 验证方式 |
|--------|----------|----------|
| 竞品输入 | 输入"支付宝"可正常启动分析 | 演示 |
| 数据采集 | 输出 CompetitorProfile 包含 basic_info、feature_tree、pricing | 检查输出 Schema |
| 竞品分析 | 输出 CompetitiveAnalysis 包含 feature_matrix、swot | 检查输出 Schema |
| 报告生成 | 输出 FinalReport 包含 executive_summary、action_items | 检查输出 Schema |
| 质量检查 | 故意构造缺陷报告，质检可识别并打回 | 演示 |
| 反馈闭环 | 打回后上游 Agent 修正并重新提交 | 演示 |
| 信息溯源 | 报告中每条结论可点击查看来源 | 演示 |
| 可观测性 | 可查看每个 Agent 的输入输出和耗时 | 演示 |

### 10.2 质量验收

| 验收项 | 验收标准 |
|--------|----------|
| 功能覆盖率 | feature_tree 至少覆盖 3 个功能模块 |
| 行动建议数量 | action_items 至少 3 条，含优先级 |
| 溯源链接有效率 | ≥ 80% 的溯源链接可访问 |
| 执行摘要长度 | 200-500 字 |
| 端到端成功率 | 单竞品分析成功率 ≥ 90% |

### 10.3 非功能验收

| 验收项 | 验收标准 |
|--------|----------|
| 性能 | 单竞品分析 ≤ 5 分钟 |
| 稳定性 | 连续 3 次分析无崩溃 |
| 错误处理 | 输入不存在的竞品，返回友好提示而非崩溃 |

---

## 11. 信息溯源

### 11.1 溯源机制

每条分析结论必须绑定数据来源：

```yaml
SourceReference:
  claim: str                 # 结论内容
  source_type: str           # app_store / official_site / media / social
  source_url: str            # 原始链接
  snippet: str               # 原文片段（50-200 字，用于佐证）
  collected_at: str          # 采集时间
```

### 11.2 溯源展示规则

- 报告中每个结论旁标注来源编号（如 [1][2]）
- 用户可点击查看原文片段
- 失效链接标记为"来源不可用"，不阻塞报告展示
- 所有来源 URL 汇总在报告末尾的"数据来源"章节

---

## 12. 可观测性

### 12.1 日志结构

每次分析任务生成一份完整的执行日志：

```
logs/
  {trace_id}/
    input.json               # 用户输入
    collector/
      {competitor}_raw.json  # 采集原始数据
      {competitor}_profile.json  # 结构化输出
    analyzer/
      analysis.json          # 分析结果
    writer/
      report_v1.json         # 报告初稿
      report_v2.json         # 修正后报告（如有打回）
    inspector/
      check_v1.json          # 质检结果
      check_v2.json          # 二次质检结果（如有打回）
    summary.json             # 汇总：总耗时、Token 消耗、重试次数
```

### 12.2 可观测界面

前端提供以下观测能力：
- 任务执行时间线（各阶段耗时）
- Agent 输入/输出查看器
- Token 消耗统计
- 错误日志查看

---

## 13. 技术方案概要

| 层 | 技术选型 | 选型理由 |
|----|----------|----------|
| Agent 编排 | LangGraph | 原生支持 DAG + 条件分支 + 环路，适合质检反馈闭环 |
| LLM | Doubao-Seed-2.0-lite | 课题指定资源 |
| 后端 | Python + FastAPI | 与 LangGraph 生态一致，异步支持好 |
| 前端 | Streamlit | 11 天极限计划，最快出活 |
| 数据采集 | httpx + BeautifulSoup | 异步 HTTP + HTML 解析 |

---

## 14. 版本边界

### 14.1 本版本（V1.0）包含

- 4 Agent 协作（采集、分析、撰写、质检）
- 采集 Agent 内部三步走（目标解析 → 竞品分类 → 差异化采集）
- 单次竞品分析（输入竞品名称 + 分析意图 → 输出报告）
- 四维分析框架（定位 / 功能 / 商业 / 运营）
- 反馈闭环（质检打回 → 上游修正）
- 信息溯源（结论绑定来源）
- 可观测性（Agent 日志查看）
- Streamlit 前端（报告展示 + 进度查看）

### 14.2 本版本不包含

| 排除功能 | 排除原因 |
|----------|----------|
| 定期监控 / 自动更新 | 需要定时任务和持久化存储，超出 MVP 范围 |
| 用户认证 / 多用户 | 个人项目，单用户即可 |
| 报告导出（PDF/Word） | P2 优先级，时间不够 |
| 自定义分析维度 | P2 优先级，时间不够 |
| 历史报告对比 | P2 优先级，时间不够 |
| 多语言支持 | 中文场景即可 |
| 数据库存储 | 使用文件系统存储，简化架构 |

### 14.3 假设与约束

| 假设/约束 | 说明 |
|-----------|------|
| LLM 服务稳定 | 假设 Doubao API 可用率 ≥ 99% |
| 网络可达 | 假设运行环境可访问目标数据源网站 |
| 中文场景 | 所有分析对象为中文产品，数据源为中文网站 |
| 单用户使用 | 不考虑并发用户场景 |
| 公开数据 | 仅采集公开可访问的数据，不涉及付费数据源 |
