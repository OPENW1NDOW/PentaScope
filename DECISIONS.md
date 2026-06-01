# Technical Decisions

项目关键技术决策记录。每个决策包含选择、理由和被排除的备选方案。

> 决策会直接影响后续代码实现，比进度信息更重要。

## Format

```markdown
## YYYY-MM-DD: 决策标题
- 选择：...
- 理由：...
- 备选：...（排除原因：...）
```

---

## 2026-05-30: 编排框架选型
- 选择：LangGraph
- 理由：课题要求质检→采集的反馈闭环（DAG 循环），LangGraph 原生支持条件分支和环路
- 备选：CrewAI（排除原因：声明式编排，复杂闭环控制力弱，需要额外 hack）

## 2026-05-30: Agent 构建框架选型
- 选择：待定（LangChain 或纯手写）
- 理由：取决于 Doubao 模型的 SDK 适配情况
- 备选：Claude Agent SDK / OpenAI Agents SDK（排除原因：课题提供 Doubao 模型，需优先适配）

## 2026-05-30: LLM 选型
- 选择：Doubao-Seed-2.0-lite（EP: ep-20260514111325-xjmj7）
- 理由：课题官方提供的模型资源，所有成员共用
- 备选：无（课题要求使用指定资源）

## 2026-05-30: Agent 数量
- 选择：4 个（采集、分析、撰写、质检）
- 理由：职责边界清晰，覆盖竞品分析全链路；后续若行动建议质量不佳可加策略 Agent
- 备选：5 个（加策略 Agent）（排除原因：当前 4 个够用，避免过度设计）

## 2026-05-30: 竞品分析场景
- 选择：产品经理功能对标（场景 A）
- 理由：场景具体、数据源明确、可演示性强
- 备选：行业报告（场景 B）、SWOT 跟踪（场景 C）（排除原因：场景 B 太泛，场景 C 偏战略层）

## 2026-05-30: 竞品数量
- 选择：支持 N 个竞品（架构通用）
- 理由：架构上做通用，Demo 聚焦 1-2 个金融 case；答辩时展示通用性
- 备选：固定 2 个竞品（排除原因：限制灵活性）

## 2026-05-30: 前端方案
- 选择：Streamlit（最简方案）
- 理由：11 天极限计划，前端不是得分重点，Streamlit 最快出活
- 备选：React/Vue（排除原因：时间不够，UI 美化不是核心得分点）

## 2026-05-30: 产品定位
- 选择：面向企业产品经理的自动化竞品分析工具（内部使用）
- 理由：场景 A 锁定，目标用户明确
- 备选：通用分析平台（排除原因：太泛，无法聚焦）

## 2026-05-31: Agent 构建方式
- 选择：手写 Agent（纯 Python 函数 + LangGraph StateGraph）
- 理由：Agent 间是固定流水线，不需要 LangChain 的动态工具选择能力；Doubao 兼容性不确定；评分标准强调可观测性，手写逻辑更透明
- 备选：LangChain Agent 封装（排除原因：抽象层增加调试难度，Doubao function calling 兼容性未知）

## 2026-05-31: 前后端架构
- 选择：FastAPI 后端 + Streamlit 前端，前后端分离
- 理由：FastAPI 提供 API 端点，Streamlit 调用 API，职责清晰
- 备选：Streamlit 直接调用 LangGraph（排除原因：Cooper 要求前后端分离）

## 2026-05-31: 依赖管理
- 选择：venv + pip + requirements.txt
- 理由：纯 Python 项目，无重依赖（CUDA/科学计算），venv 最简单
- 备选：conda（排除原因：过重，不需要）

## 2026-05-31: 结构化输出方案
- 选择：Doubao JSON mode（response_format={"type": "json_object"}）
- 理由：Doubao 支持 JSON mode，直接约束 LLM 输出格式，比 Prompt 约束更可靠
- 备选：Prompt 约束 + 后处理解析（排除原因：JSON mode 更稳定）

## 2026-05-31: 目标设定实现方式
- 选择：采集 Agent 内部三步走（目标解析 → 竞品分类 → 差异化采集）
- 理由：目标解析是轻量 LLM 调用，不值得单独设 Agent；目标设定绑定前端 UI 会限制后续迁移为 skill
- 备选：独立目标设定 Agent / 前端 UI 下拉框（排除原因：前者过度设计，后者耦合前端形态）

## 2026-06-01: 放弃 JSON mode，改纯 prompt 约束（推翻 05-31 决策）
- 选择：去掉 `response_format={"type":"json_object"}`，靠 prompt 约束 + 代码块剥离 + 解析重试
- 理由：真实验收发现 Doubao-Seed-2.0-lite 端点不支持该参数，直接返回 400；实测纯 prompt 约束已能稳定输出合法 JSON
- 备选：保留 JSON mode（排除原因：模型不支持，是硬性失败）

## 2026-06-01: LLM 超时从 30s 调到 120s
- 选择：`LLM_TIMEOUT = 120`
- 理由：实测单次中等规模调用要 30.4s，30s 超时反复触发导致全链路失败；Doubao-Seed-2.0-lite 推理较慢
- 备选：换更快模型（排除原因：课题指定该模型资源）

## 2026-06-01: 数据源改为 iTunes API + Bing + 搜狗（推翻 05-30 数据源）
- 选择：iTunes Search API（结构化 JSON，含价格/评分/描述）+ Bing 搜索 + 搜狗搜索
- 理由：原数据源（App Store 页面/百度百科/百度搜索）实测全部失败（404/403/反爬）；新三源实测稳定返回真实内容，iTunes 还直接提供定价与满意度数据，强化信息溯源
- 备选：百度百科加反爬（排除原因：补全请求头后仍 403）、维基百科（排除原因：403）

## 2026-06-01: LLM 输出鲁棒性统一用「规整兜底」策略
- 选择：每个 Agent 在 Pydantic 校验前对 LLM 原始输出做 _normalize 规整（prompt 引导 + 代码兜底双保险）
- 理由：Doubao 输出不稳定，反复出现结构/枚举偏差（sample_reviews 填字符串、gap_level 填"小米领先"、priority 填"中等"、裸控制字符）。光靠 prompt 约束无法 100% 命中，必须代码兜底。枚举规整用「精确匹配→包含匹配→默认值」三级降级
- 备选：仅靠 prompt + 重试（排除原因：重试同样失败，6 品牌场景必现）、JSON Schema 强约束（排除原因：Doubao 不支持 response_format）

## 2026-06-01: 信息溯源与质量分在 graph 层回填
- 选择：`data_sources` 和 `quality_score` 由 graph 节点回填，而非依赖 writer LLM 自填
- 理由：writer 拿不到 profile 的 sources、LLM 自填的 quality_score 恒为 0 不可信；溯源应取自采集真实结果，质量分应取自质检 issue 严重度
- 备选：让 writer prompt 填这两个字段（排除原因：writer 无 source 数据、LLM 自评分不客观）

## 2026-06-01: 采集数据传递方式
- 选择：Analyzer 和 Writer 使用 model_dump() 序列化完整数据传给 LLM
- 理由：原实现只传统计数字，LLM 无法生成有意义的分析/报告；完整数据传递是正确性问题
- 备选：手动拼接摘要文本（排除原因：丢失关键细节）
