# 项目功能测试指南

本文档介绍如何手动测试本项目的 5 个分析场景与「AI 帮我选场景」能力，包含每个场景的输入字段、可复制粘贴的具体案例、预期产出与功能检查清单。

> 适合谁看：第一次跑通项目、想快速体验各场景能力，或在二次开发前对照功能基线的使用者。

---

## 目录

1. [启动服务](#启动服务)
2. [全局检查清单](#全局检查清单)
3. [测试 0：AI 帮我选场景](#测试-0ai-帮我选场景)
4. [测试 1：S1 功能迭代](#测试-1s1-功能迭代)
5. [测试 2：S2 市场进入](#测试-2s2-市场进入)
6. [测试 3：S3 定价策略](#测试-3s3-定价策略)
7. [测试 4：S4 持续监控](#测试-4s4-持续监控)
8. [测试 5：S5 战略定位](#测试-5s5-战略定位)
9. [功能检查总清单](#功能检查总清单)
10. [常见限制](#常见限制)
11. [故障排查](#故障排查)

---

## 启动服务

需要分别启动后端与前端两个进程：

```powershell
# 终端 1：后端
.\venv\Scripts\Activate.ps1
uvicorn src.api.main:app --reload

# 终端 2：前端
.\venv\Scripts\Activate.ps1
streamlit run src/frontend/app.py
```

打开浏览器访问：`http://localhost:8501`

> 启动前需在项目根目录配置 `.env`，至少包含 `LLM_API_KEY` + `LLM_BASE_URL` + `LLM_MODEL`；搜索功能需要 `TAVILY_API_KEY`。详情见 README。

---

## 全局检查清单

每个场景跑完都建议确认：

1. **不报错**：分析过程中后端日志无 ERROR、前端无红色异常框
2. **trace_id 写出**：成功页面顶部显示 `Trace ID: 20260608-XXXXXX-XXXXXX`
3. **元数据面板**三个 metric 都有值：
   - 场景 = 你选的 scenario
   - 置信度 = high / medium / low
   - 质检评分 = 0.000–1.000 数字（不是「未质检」）
4. **附录 → 完整数据来源**：至少 3 个真实 URL（不是 example.com 占位）
5. **追溯面板**（页面底部展开）：填上面的 trace_id 点「加载追溯」，4 个 tab（采集 / 分析 / 报告 / 质检）都有 JSON 内容

---

## 测试 0：AI 帮我选场景

**目的**：验证 `/api/v1/pick-scenario` 端点 + 前端按钮 + 推荐结果回填到 selectbox

### 操作步骤

1. 在「分析意图描述」输入框填以下任一文案
2. 点 「AI 帮我选场景」 按钮
3. 观察 selectbox 是否自动跳到推荐场景，下方 caption 是否出现 `🟢 high — 理由...`

### 测试文案与预期场景

| 输入文案 | 预期推荐 | 关键词依据 |
|---|---|---|
| `我们已经有协作文档产品，想看飞书文档、语雀有哪些功能我们没做，决定下个迭代要补什么` | S1 | 已有产品 + 看竞品功能差距 |
| `我准备进入国产 AI 大模型赛道，目前还没产品，想调研一下市场头部玩家有哪些` | S2 | 还没产品 + 市场调研 + 头部玩家 |
| `我们的协作办公产品想调价格，用户反馈现在太贵，想看钉钉、企业微信怎么定价` | S3 | 调价 + 竞品定价 |
| `我们每个季度都跟踪几个核心竞品的最新动作，这次想更新一下战卡` | S4 | 每季度跟踪 + 战卡（监控） |
| `我们的产品市场定位有点尴尬，想重新做一次定位、找到差异化` | S5 | 重新定位 + 差异化 |

### 预期表现

- 5 段文案中至少 4 段推荐结果与预期一致（LLM 推断有少量随机性）
- 置信度合理（明确文案 → high；模糊文案 → medium 或 low）
- rationale 不是空话，**应引用文案中的关键词**（如「已有产品」「调研」等）

---

## 测试 1：S1 功能迭代

**适用产品**：已有可对标的成熟产品 + 想看竞品功能矩阵

> 推荐参考 trace_id：`20260620-201224-88f548`（quality_score=1.0, retries=0）

### 输入

- **分析场景**：S1 功能迭代（已有产品对标）
- **我方产品名称**：`飞书文档`
- **我方产品简介（选填）**：`字节跳动旗下协作文档平台，集成即时通讯、视频会议、多维表格于一体`
- **竞品名称（每行一个）**：
  ```
  语雀
  腾讯文档
  金山文档
  ```
- **分析意图描述**：
  ```
  我们想了解语雀、腾讯文档、金山文档在协作文档领域的功能矩阵，重点是 AI 写作辅助、
  多人实时协作、知识库管理、移动端体验四个维度，找到飞书文档还没补齐的功能差距，
  以便下个版本规划迭代方向。
  ```

> 你也可以替换为任何国产已有产品，把竞品换成同赛道 2-5 个对手。

### 预期产出

1. **路由**：后端日志显示 `[graph] → collector` **直接进入**（不经过 recommender）
2. **vendor_profiles 表**：
   - 至少有 3 行（语雀 / 腾讯文档 / 金山文档 各一行）
   - 每行有 `wave_position`（wave_leader / wave_strong_performer / wave_contender 之一）
   - 「优势数 / 警示数」都 ≥ 1
3. **功能矩阵**：
   - 至少 4-8 行功能（AI 写作 / 实时协作 / 知识库 / 移动端等）
   - 每个竞品列都有 0/1/2 评分
   - 加权总分（百分比）显示在表下方 caption
4. **5 维雷达图（Plotly）**：
   - 多边形图，每个竞品一条折线
   - 5 个轴：功能广度 / 易用性 / 性价比 / 稳定性 / 设计质量
   - 半径 0-5 范围
5. **功能差距表**：至少 1 行，包含 build / skip / differentiate 之一的建议
6. **路线图**：3 列 must_build / should_skip / should_differentiate，至少 must_build 有内容

### 常见问题

- 雷达图缺失 → plotly 没安装或竞品名不一致触发了 schema validator
- vendor_profiles 数 < 竞品数 → 元数据 warnings 会标 major issue

---

## 测试 2：S2 市场进入

**适用场景**：还没产品，想看赛道格局

> 推荐参考 trace_id：`20260620-144341-10b7e6`（quality_score=1.0, retries=0）
streamlit run src/frontend/app.py
### 输入

- **分析场景**：S2 市场进入（无产品调研）
- **行业 / 赛道（必填）**：`国产 AI 大模型`
- **已知竞品（可选）**：留空（让 recommender 自动推荐）
- **分析意图描述**：
  ```
  我们准备进入国产 AI 大模型赛道，目前还没有产品。想调研当前头部玩家（如文心一言、
  通义千问、豆包、Kimi 等）的 TAM/SAM/SOM 市场规模、Porter 五力格局，
  找到适合切入的细分场景与差异化策略。重点关注 ToB 企业 API 服务市场。
  ```

> 行业关键词可以替换为任意细分赛道，例如「协作办公」「企业 IM」「跨境电商 ERP」。

### 预期产出

1. **路由**：后端日志显示 `[graph] → recommender` **先经过 recommender**，再 → collector
2. **Recommender 推荐玩家表**：
   - 至少 3 个推荐（文心一言 / 通义千问 / 豆包 / Kimi / 智谱 等）
   - 每条有 `confidence`（high/medium/low）+ `why_recommended` 理由 ≥ 10 字
   - `selection_method` = hybrid（既搜索又 LLM 推断）
3. **市场规模 TAM/SAM/SOM 三 metric**：
   - 三个数字都不是 「—」（即 amount 不为 None）
   - hover 显示 basis（measured / estimated / inferred 之一，不能全是 unknown）
4. **Porter 五力蜘蛛网图（Plotly）**：
   - 5 角形蛛网图，半径 1=低 / 3=中 / 5=高
   - 表格下方有 5 维 intensity 列
5. **市场玩家表**：
   - 至少 3 行（来自 recommender 推荐 + LLM 综合）
   - 至少有 2 种不同 `market_role`（incumbent + challenger 等）
   - 「推荐 ✓」列至少 1 个标记
6. **关键趋势表**：≥ 2 条，含 `direction`（up/flat/down）+ `time_horizon`
7. **进入策略**：`recommended_mode` 显示（niche_focus / differentiation 等）+ 主要风险列出

### 常见问题

- recommender 表为空 → 检查 `TAVILY_API_KEY` 是否已配 / 网络是否可达 Tavily
- TAM/SAM/SOM 全是 「—」 → 元数据 warnings 会标 critical issue（market_sizing 全 unknown）
- 后端日志若出现 `WriterRouteToEnd: scope 全空` → recommender 没产出有效玩家

---

## 测试 3：S3 定价策略

**适用场景**：已有产品 + 准备调价 / 重新打包

> 推荐参考 trace_id：`20260620-151025-436f94`（quality_score=0.833, retries=0）

### 输入

- **分析场景**：S3 定价策略
- **我方产品名称**：`钉钉`
- **我方产品简介**：`阿里巴巴旗下企业协作与办公平台，覆盖即时通讯、审批、考勤、项目管理`
- **竞品名称**：
  ```
  企业微信
  飞书
  华为WeLink
  ```
- **分析意图描述**：
  ```
  钉钉当前专业版定价 9800 元/年起，用户反馈中小企业成本敏感。想看企业微信、飞书、
  华为WeLink 的定价模型、套餐切分、免费版功能边界，参考 GBB 三层套餐法重新设计
  定价方案，目标是 SMB 市场 ARR 提升 15-20%。
  ```

### 预期产出

1. **当前定价基线**：显示 `current_pricing_model`（per_seat 等）+ tier 数 + 痛点列表
2. **价值驱动表**：≥ 3 行，importance 分布合理（不全 high）
3. **功能分类**：3 列 hygiene / preference / premium 都有内容
4. **GBB 三层套餐卡片**：
   - 至少 3 个 tier（good / better / best 完整）
   - **必须有且只有 1 个**带 ⭐ 的 is_recommended（schema 强约束）
   - 每个 tier 显示月费 + 年费 + 对象 + 包含功能
   - 年付折扣 % 显示在底部
5. **竞品定价矩阵**：≥ 2 个竞品，每个 expander 展开后有套餐表
6. **定价方案总结**：
   - `expected_arr_uplift_pct` 显示数字（不是 None）
   - `basis` 不是 `llm_inferred`（如果是 → 元数据 warnings 标 minor）
7. **Rollout 步骤表**：≥ 3 步

### 常见问题

- 套餐 tier < 3 → 元数据 warnings 标 minor（GBB 不达三层）
- 出现 2 个 ⭐ 推荐 tier → schema validator 会直接拦截 writer 输出，graph 会重试

---

## 测试 4：S4 持续监控

**适用场景**：建立竞品基线 + 后续按周期跟踪

> 推荐参考 trace_id：`20260610-041859-5fdda8`（quality_score=0.717, retries=2）

### 输入（首次模式）

- **分析场景**：S4 持续监控
- **我方产品名称**：`神策数据`
- **我方产品简介**：`国产用户行为分析与数据驱动平台，服务互联网与传统企业`
- **竞品名称**：
  ```
  GrowingIO
  火山引擎数据分析
  友盟
  ```
- **上次监控 trace_id（选填）**：**留空**（首次监控模式）
- **分析意图描述**：
  ```
  我们要为 GrowingIO、火山引擎数据分析、友盟建立首次监控基线，覆盖功能变更、
  定价变更、营销文案、新闻事件、组织变化五个维度。这次是首次监控所以所有变更
  都是基线快照，下季度再跑增量对比。
  ```

### 预期产出

1. **监控周期**：显示「模式：**首次基线**」（因为 prior_trace_id 留空）
2. **首次模式硬约束**（schema validator 强制）：
   - 所有 changes 必须 `is_baseline=True`（表里「基线」列全 ✓）
   - **MonitoringTrends 必须全 None**（页面不显示「趋势方向」区块）
3. **5 类 changes 表**（feature / pricing / messaging / news / org）：
   - 每个 expander 展开后有数据
   - 每行至少包含：竞品 / 类型 / 事实 / 严重度
4. **威胁评估表**：
   - 每行有 `quadrant`（act_now / contingency / monitor / deprioritize 之一）
   - 严重度 + 可能性两列
5. **机会识别表**：≥ 1 行，含 `opportunity_type`
6. **活体战卡 expander**：
   - 每个竞品一个 expander
   - 至少 4 个 section（schema min_length=4）
   - 至少有 1 个 section 不是 「empty」（completeness=partial 或 full）

### 进阶：增量模式

跑完上面的首次监控后：
1. 复制 Trace ID（如 `20260608-XXXXXX-XXXXXX`）
2. 重新打开新分析页面
3. 同样的输入，但**填上次的 trace_id**到对应字段
4. 跑一遍，监控周期应显示「模式：**增量**」
5. 后端日志应显示 `[graph] prior 报告 scenario == S4`，prior_data 被注入

### 常见问题

- 首次模式下 trends 区块出现数据 → schema validator 会拦截
- 改 prior_trace_id 为 `../../etc/passwd` → 后端日志出现 `[graph] prior_trace_id 含非法字符，拒绝加载`，graph 仍能跑（降级首次模式）— 路径穿越防护正常工作

---

## 测试 5：S5 战略定位

**适用场景**：产品已有但想重新定位 / 品牌升级

> 推荐参考 trace_id：`20260619-203923-9f5681`（quality_score=0.9, retries=0）

### 输入

- **分析场景**：S5 战略定位
- **我方产品名称**：`即时设计`
- **我方产品简介**：`国产云端 UI 设计协作工具，浏览器原生 + 多人实时编辑 + 本土化资源库`
- **竞品名称**：
  ```
  Figma
  MasterGo
  Pixso
  ```
- **分析意图描述**：
  ```
  即时设计当前在国内独立设计师群体有一定份额，但企业端渗透不足。想做一次
  Gartner Magic Quadrant 风格的定位评估，用 ERRC 战略画布找出与 Figma、MasterGo、
  Pixso 的价值曲线差异，最终用 Geoffrey Moore 6 位模板写出新定位陈述，目标是从
  「Figma 国产替代」升级为「企业级产品设计协作平台」。
  ```

### 预期产出

1. **竞品画像 Gartner MQ 表**：
   - 每行有 `执行力 / 愿景完整度` 评分（0-5）+ `mq_quadrant`（mq_leader / mq_challenger / mq_visionary / mq_niche_player）
   - 象限由代码自动派生（执行力 ≥ 2.5 + 愿景 ≥ 2.5 = mq_leader）
2. **Magic Quadrant 散点图（Plotly）**：
   - 4 个象限分隔线 + 4 个标签（Leaders / Challengers / Visionaries / Niche Players）
   - 每个竞品一个点，名称标在散点上方
3. **感知地图 Perceptual Map（Plotly）**：
   - 二维散点图
   - **我方品牌（即时设计）必须用 ⭐ 红色标记**（is_self=True）
   - 竞品用蓝色圆点
   - X/Y 轴标签显示 `attribute (low_label → high_label)`
   - 底部 watermark：`⚠️ 基于公开信息 AI 推断，非客户调研真实分数`
4. **战略画布折线图（Plotly）**：
   - 至少 5 个竞争要素（横轴）
   - 每个品牌一条折线，**我方折线加粗实线**（其他竞品虚线）
   - Y 轴 0-10
5. **ERRC 4 宫格**：
   - Eliminate / Reduce / Raise / Create 4 列
   - 至少 1 列有内容（写好的策略至少在某一类有动作）
6. **蓝海战略动作**（如果生成了）：
   - `compelling_tagline` 显示
   - `focus_assessment` + `divergence_assessment` 两个 metric
7. **定位陈述卡片**：
   - **For X who Y, ProductName is a Category that Benefit. Unlike Alternative, our product Differentiation.** 完整 6 位
   - 置信度显示（from_user_brief / llm_inferred / low_confidence）
   - 如果是 `llm_inferred` → 陈述前会有 `[AI 推断版本，请人工校对]` 前缀
8. **品类战略**：
   - `chosen_category` 显示
   - `competitors_implied` 必须是 vendor_profiles 竞品名的子集（schema 跨字段一致性）

### 常见问题

- 感知地图缺红色 ⭐ → is_self=True 没被设置
- 战略画布折线缺失 → value_curves 与 competitive_factors 名称不一致触发 schema validator
- positioning_statement.confidence=low_confidence → 元数据 warnings 标 minor

---

## 功能检查总清单

5 场景全跑完后，**至少满足以下 6 条**算功能基线达标：

- [ ] S1-S5 所有场景都成功产出报告（前端不出红色异常框）
- [ ] S2 路由经过 recommender，其他场景直走 collector（看后端日志）
- [ ] AI 帮我选场景按钮工作正常，5 段测试文案至少 4 段推荐准确
- [ ] 所有场景的 Plotly 图表都正常渲染（雷达 / 蜘蛛网 / Perceptual Map / MQ / 战略画布）
- [ ] 所有场景的元数据面板都显示 quality_score 数字 + warnings（如有）
- [ ] 追溯面板可以加载任一 trace_id 查看 4 阶段产物

---

## 常见限制

- LLM 调用耗时较长，单场景从提交到出报告可能 **5-15 分钟**
- 网络抖动 / LLM API 偶发限流 → 可能触发 graph 重试或 quality_score 偏低
- Tavily API 配额耗尽 → S2 recommender 会降级为纯 LLM 推断（confidence 全部 low）
- 首次跑 S4 增量模式（带 prior_trace_id）需要先跑过一次 S4 首次模式建立 prior

---

## 故障排查

| 现象 | 排查方向 |
|---|---|
| 前端报 `ModuleNotFoundError: 'src'` | 确认 streamlit 是从项目根目录启动（`streamlit run src/frontend/app.py`） |
| 后端报 LLM 401 | 检查 `.env` 里 `LLM_API_KEY` 是否正确 |
| S2 recommender 推荐为空 | 检查 `.env` 里 `TAVILY_API_KEY` 是否正确，或 Tavily 配额是否耗尽 |
| 图表显示「plotly 未安装，跳过图表」 | `pip install plotly>=5.20.0` |
| 整个流程无限重试 | 检查后端日志看是哪个 agent 在 raise，`max_retries=2` 应该会强制结束 |
| 报告内容质量低 / quality_score 偏低 | 检查竞品名是否准确、分析意图是否具体；模糊输入会导致 LLM 推断不稳定 |
