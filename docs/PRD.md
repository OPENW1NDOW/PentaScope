# PRD: AI 驱动的竞品分析 Agent 协作系统

## 1. 产品概述

### 1.1 产品定位

面向企业产品经理的自动化竞品分析工具。用户输入竞品名称，系统自动完成从信息采集到结构化报告的全链路产出，并给出可执行的行动建议。

### 1.2 目标用户

- **主要用户**：企业产品经理
- **次要用户**：市场分析师、战略分析师

### 1.3 核心价值

| 传统方式 | 本系统 |
|----------|--------|
| 2-3 天手动搜集整理 | 分钟级自动化产出 |
| 信息源分散，覆盖不全 | 多源并行采集，覆盖率高 |
| 分析维度因人而异 | Schema 驱动，输出一致 |
| 报告导向 | 行动导向（输出行动建议） |

### 1.4 使用场景

产品经理收到任务"分析一下支付宝最近的新功能"，在系统中输入竞品名称（支持同时分析多个竞品），系统自动完成采集、分析、撰写、质检，输出一份结构化的竞品分析报告和行动建议。

---

## 2. 竞品知识 Schema

### 2.1 输入

```yaml
CompetitorInput:
  product_name: str          # 竞品名称，如"支付宝"
  company: str               # 所属公司，如"蚂蚁集团"
  category: str              # 行业分类，如"金融科技"
```

### 2.2 采集 Agent 输出

```yaml
CompetitorProfile:
  basic_info:
    name: str
    company: str
    version: str             # 当前版本号
    release_date: str        # 最近更新日期
    platform: list[str]      # iOS/Android/Web
  feature_tree:
    - module: str            # 功能模块名
      features:
        - name: str
          description: str
          is_new: bool       # 是否为近期新增
  pricing:
    model: str               # 免费/付费/订阅
    tiers: list              # 价格档位
  user_reviews:
    rating: float            # 综合评分
    positive_summary: str    # 好评关键词总结
    negative_summary: str    # 差评关键词总结
    sample_reviews: list[str] # 代表性评论
  recent_updates:
    - date: str
      title: str
      summary: str
      source_url: str        # 溯源链接
```

### 2.3 分析 Agent 输出

```yaml
CompetitiveAnalysis:
  feature_matrix:
    - feature: str
      our_product: str       # 我方状态
      competitors: dict      # {竞品名: 状态}
      gap_level: str         # 领先/持平/落后
  pricing_comparison: str    # 定价对比分析
  user_sentiment: str        # 用户情感对比
  swot:
    strengths: list[str]
    weaknesses: list[str]
    opportunities: list[str]
    threats: list[str]
```

### 2.4 最终报告输出

```yaml
FinalReport:
  title: str
  executive_summary: str     # 执行摘要
  sections: list[Section]    # 各章节内容
  action_items: list[str]    # 行动建议
  metadata:
    competitors_analyzed: list[str]
    generated_at: str
    data_sources: list[str]  # 所有数据来源 URL
```

---

## 3. Agent 角色设计

### 3.1 总体架构

```
用户输入竞品列表
       │
       ▼
  ┌─────────────┐
  │  采集 Agent   │  并行采集多个竞品的公开数据
  └──────┬──────┘
         │ CompetitorProfile[]
         ▼
  ┌─────────────┐
  │  分析 Agent   │  结构化对比、生成 SWOT
  └──────┬──────┘
         │ CompetitiveAnalysis
         ▼
  ┌─────────────┐
  │  撰写 Agent   │  组装报告、生成行动建议
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

### 3.2 各 Agent 职责

| Agent | 输入 | 输出 | 核心职责 |
|-------|------|------|----------|
| 采集 Agent | 竞品名称列表 | CompetitorProfile[] | 从应用商店、官网、行业媒体、社交媒体等公开源并行采集数据 |
| 分析 Agent | CompetitorProfile[] | CompetitiveAnalysis | 生成功能矩阵对比、定价对比、用户情感对比、SWOT 分析 |
| 撰写 Agent | CompetitiveAnalysis | FinalReport | 组装结构化报告，生成执行摘要和行动建议 |
| 质检 Agent | FinalReport | 通过/不通过 + 原因 | 校验 Schema 完整性、结论有数据支撑、溯源链接有效 |

### 3.3 反馈闭环

质检 Agent 发现问题时，输出结构化的打回消息：

```yaml
RejectionFeedback:
  passed: bool
  issues:
    - agent: str             # 问题归属的 Agent
      field: str             # 问题字段
      reason: str            # 具体问题描述
      suggestion: str        # 修改建议
```

被打回的 Agent 根据 `issues` 中的反馈进行修正，修正后重新提交给质检 Agent。

---

## 4. 数据源

| 数据源 | 采集方式 | 采集内容 |
|--------|----------|----------|
| 应用商店（App Store/应用宝等） | 网页抓取 | 评分、评论、版本更新日志 |
| 竞品官网 | 网页抓取 | 功能介绍、定价页面 |
| 行业媒体（36氪、虎嗅等） | 网页抓取 | 产品动态、行业分析 |
| 社交媒体（微博、小红书等） | 网页抓取 | 用户反馈、舆情 |

---

## 5. 信息溯源

每条分析结论必须绑定数据来源：

```yaml
SourceReference:
  claim: str                 # 结论内容
  source_type: str           # app_store / official_site / media / social
  source_url: str            # 原始链接
  snippet: str               # 原文片段（用于佐证）
```

报告中每个结论旁标注来源编号，用户可点击查看原文。

---

## 6. 可观测性

| 可观测项 | 记录内容 |
|----------|----------|
| Agent 调用日志 | 每个 Agent 的输入、输出、耗时 |
| 决策过程 | Agent 的推理过程（Prompt + Response） |
| Token 消耗 | 每次 LLM 调用的 Token 用量 |
| 错误记录 | 失败的采集请求、超时、解析错误 |

---

## 7. 技术方案概要

| 层 | 技术选型 |
|----|----------|
| Agent 编排 | LangGraph（DAG 可视化、状态管理） |
| LLM | Doubao-Seed-2.0-lite（EP: ep-20260514111325-xjmj7） |
| 后端 | Python + FastAPI |
| 前端 | Streamlit（最简方案） |
| 数据采集 | requests + BeautifulSoup / httpx |

---

## 8. 评分标准映射

| 评分维度 | 权重 | 本系统对应 |
|----------|------|-----------|
| 多 Agent 协作与输出可信度 | 35% | 4 Agent 角色清晰、结构化消息传递、反馈闭环、Schema 一致性、信息溯源 |
| 技术深度与工程完整度 | 25% | 端到端链路、可观测性、异常处理 |
| 业务价值与产品体验 | 20% | 效率提升可量化、行动导向、交互流畅 |
| 代码质量与文档 | 10% | 模块化、README、Git 规范 |
| 合规、材料与答辩 | 10% | 合规采集、数据脱敏、答辩清晰 |
