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

## 2026-06-04: 报告质量提升走「溯源为脉」而非「只改 writer」（方案 C）
- 选择：报告质量提升以「事实-URL 绑定链」为主线贯穿全链路——pipeline 输出带【来源】标记文本 → collector 抽取时绑定每条 fact 的 source_url → analyzer 透传维度 source_urls（代码兜底）→ writer 机械透传 SWOT/雷达/功能矩阵 + 按 dimension 下沉 source_refs → inspector 程序化硬查 + severity 分级 pass/fail
- 理由：最初设想「只改 writer 做机械下沉」，两轮 doubt-driven（单模型 + Codex gpt-5.5 跨模型，20 条命中）核对源码后证伪——溯源断链的真正根因在**采集层**：collector 抽取 prompt 只给 sample_reviews 留 source_url、正文被 merge 成无【来源】锚点的 blob，导致 analysis 各维度 source_urls 恒空。不碰采集层就修不了「每条结论可溯源」（课题 35% 评分核心 + 引用强制反幻觉）
- 关键设计原则：**能用代码保证的结构与溯源不赌 LLM**——SWOT/雷达/功能矩阵由 writer 代码透传（100% 不丢），溯源由代码机械下沉，LLM 只负责写散文深度
- 溯源粒度：维度+竞品级（不追 per-entry，per-entry 需改 analysis schema 结构，留作增强）
- severity 分级 pass/fail：从「有任何 issue 就 fail」改为「只 critical/major 阻断，minor 放行」——因 action_item 溯源等只能软查，硬查会逼成假闭环（无限重试耗尽）
- 备选：纯 prompt 工程不加代码兜底（排除：溯源/SWOT 仍可能丢，时灵时不灵）；writer 分章多次 LLM 生成（排除：调用成倍、耗时长，Cooper 选单次增强）

## 2026-06-04: 删除全链路文本截断，依赖 Doubao 256K 上下文
- 选择：删掉 analyzer(12000)/writer(8000)/inspector(15000) 的序列化文本截断，全量入参
- 理由：Doubao-Seed-2.0-lite 至少 256K context，analysis/profile 序列化通常几万字符远小于上限；截断会逐级丢信息（writer 8000 最致命，常导致没看到 SWOT/雷达就开写）。删截断是最简方案，无需结构化瘦身/分片模块（YAGNI）
- 已知 trade-off：llm_client 无 max_tokens，超长输入「迷失在中间」可能损害引用准确率——验证阶段实测观察，必要时回调
- 备选：上下文分片管理器（排除：256K 下根本触发不了，为答辩话术造无用模块）

## 2026-06-04: analyzer 反馈回边为「保险」，当前效用有限
- 选择：should_continue 认 analyzer 类 issue 并加 graph 回边（inspector→analyzer），但不作为主路径
- 理由：SWOT/雷达/功能矩阵现由 writer 代码透传 + analyzer 兜底保证，正常流程不该触发 analyzer 打回；回边是保险。但 analyzer 重跑读相同 profiles，重采相同 prompt → 大概率产出相同结果，效用有限（最终 code review 指出）
- 待增强：重打 analyzer 时把 feedback.issues 附加进 prompt（「上次 SWOT 缺 X，请补全」），让回边从「随机重采」变「定向修复」——留作下一课题
- 备选：不加 analyzer 回边（排除：analyzer 类 issue 会被静默打给 writer，writer 改不了上游 → 假闭环）

## 2026-06-04: SerpAPI 鉴权从 Bearer header 反转为 api_key query 参数
- 选择：`SerpApiSource.search` 用 `&api_key=<quote(key)>` query 参数鉴权，去掉 `Authorization: Bearer` header（**反转 06-03「key 走 header 防泄漏」决策**）
- 理由：真实跑通验证发现 SerpAPI 用 Bearer header 鉴权时，**遇非 ASCII（中文）query 返回 401「Invalid API key」**——竞品名恒为中文，导致搜索主线在真实场景 100% 失效（systematic-debugging 证伪 env/激活/编码/headers 后锁定）。api_key query 是 SerpAPI 标准用法，中文 query 正常
- 防泄漏补偿：query 参数的 key 由 `HttpClient._redact_key` 在自有日志脱敏为 `api_key=***`；并把 httpx/httpcore 日志压到 WARNING（其 INFO 会绕过脱敏、明文打完整请求 URL）——见下条
- 备选：保留 Bearer + 对中文 query 做特殊处理（排除：SerpAPI 服务端行为不可控，治标不治本）

## 2026-06-04: httpx/httpcore 日志级别压到 WARNING（防 key 泄漏）
- 选择：`init_logging` 内 `logging.getLogger("httpx"/"httpcore").setLevel(WARNING)`
- 理由：httpx 的 INFO 日志会打 `HTTP Request: GET <完整URL>`，含 query 里的 api_key——这条不经过我们的 `_redact_key`，会明文落 run.log/app.log。压到 WARNING 后不打请求行，但保留真实错误（WARNING/ERROR）
- 备选：自写 httpx event hook 脱敏（排除：过度工程，压级别已足够）

## 2026-06-03: 采集层重构为分层管线（collector → pipeline → sources）
- 选择：采集逻辑从 CollectorAgent 下沉到独立的 `CollectionPipeline`（tool 层），数据源做成 `sources.py` 内可插拔插件；collector 构造器从 `(llm, http, parser)` 改为 `(llm, pipeline)`
- 理由：原 collector 内联 3 个硬编码 URL 源、职责饱满；新增「搜索→选页→正文→闸门 + 专源路由」会让它膨胀且无法独立单测。下沉后每层单一职责、可独立测试，专源可插拔
- 备选：在 collector 内线性扩展（排除：膨胀、专源无处安放）、全套配置化插件框架（排除：当前 3-5 源，过度设计）

## 2026-06-03: 两步走采集（搜索 API → LLM 选页 → 正文页）
- 选择：用专业搜索 API（默认 SerpAPI）拿候选 URL → LLM 选最相关 Top N → 抓正文页 → 质量闸门过滤
- 理由：原 Bing/搜狗抓的是搜索结果页（SERP）摘要而非内容页正文，信噪比低——这是「质量低」的首要根因。两步走直取官网/文档正文
- 备选：只加更多搜索源（排除：SERP 噪声依旧）、专源优先（排除：源零散、覆盖不全）

## 2026-06-03: 只实现 SerpAPI，不做 provider 抽象
- 选择：搜索源只实现 SerpApiSource，key 走 Authorization header（不进 query 防泄漏）；换 provider 列入未来扩展
- 理由：SerpAPI/Bing/Brave/Google CSE 响应 JSON 结构各不相同，「配置切换 provider」需各写 parser——doubt-driven 判定「config alone 可换」是假承诺。当前 YAGNI 只做一个
- 备选：provider 可配置抽象（排除：假承诺 + 过度设计）、默认 Bing（排除：微软已宣布退役）

## 2026-06-03: 按 category 路由用独立 detect_category（不复用 competitor_type）
- 选择：新增零 LLM 的 `detect_category`（规则匹配 category/name/company → saas/default），用于专源路由
- 理由：doubt-driven 捕获方向性错误——原计划用 `classify_competitor` 的 `competitor_type` 路由，但其枚举是「核心/标杆/间接竞品」（竞争关系），无 SaaS/硬件（产品形态）维度，硬件竞品会被错配到 iTunes
- 备选：复用 competitor_type（排除：维度不对口）、LLM 判类别（排除：会多一次 LLM 调用，打破集成测试 6 步序列）

## 2026-06-03: 顶层 collect 从「快速失败」改为「部分降级」
- 选择：顶层 `collect()` 用 `asyncio.gather(return_exceptions=True)`，单竞品彻底失败 → 产 completeness=0.0 占位 profile，其余竞品正常产出
- 理由：多竞品场景下一颗老鼠屎不该坏一锅汤；质检会诚实反映占位 profile 的低质量。全空也不调 extract LLM（防 LLM 编造画像）
- 备选：保留快速失败（排除：单竞品失败拖垮整个分析）；注意 parse_goal 失败仍整体中止（公共前置，合理）

## 2026-06-03: 可观测性不阻塞 + 安全脱敏（沿用既有取向）
- 选择：pipeline_trace 随 profile.metadata 落盘（不碰 graph 闭包 node_trace）；HttpClient 对 URL 和异常消息双重脱敏 key；per-domain 锁串行化限速读-睡-写
- 理由：trace 进 metadata 避免反向依赖图层、也保证可追溯随产物走；密钥可能经 run.log / /trace 接口 / report.data_sources 泄漏，必须脱敏；并发 fetch 同域名下 check-then-act 会击穿 COLLECT_INTERVAL（合规评分点）
- 备选：trace 注入闭包（排除：反向依赖 + 污染 node_trace 断言）、仅 URL 脱敏（排除：异常消息也可能含 key）

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

## 2026-06-02: 中间产物按 trace_id 落盘（独立 TraceWriter）
- 选择：新建 src/tools/trace_writer.py，graph 各节点产出后调 save_stage 落盘到 runs/<trace_id>/，落盘逻辑单一出口
- 理由：开题要求「每个 Agent 的决策过程与中间产物均可追溯」，是评分硬要求；独立模块容错/快照命名集中、builder.py 保持清爽、可独立单测
- 备选：节点内分散落盘（排除：重复代码、污染编排逻辑）、LangGraph 回调钩子（排除：与「手写 graph 求透明」取向冲突，见 05-31）

## 2026-06-02: trace_id 改用北京时间格式
- 选择：`YYYYMMDD-HHMMSS-` + 6 位随机 hex（东八区，datetime.now(timezone(timedelta(hours=8)))），生成后查目录碰撞则重生成
- 理由：可读、可按时间排序、防同秒碰撞（系统要考虑轻度并发）；替换原 uuid4()[:8]。已验证不破坏现有契约（测试用任意字符串 trace_id、前端只展示不解析）
- 备选：纯时间戳（排除：同秒碰撞覆盖）、保留 uuid（排除：不可读、无法排序）

## 2026-06-02: 落盘容错与并发权衡
- 选择：落盘失败仅 warning 不抛、原子写（临时文件+os.replace）、重试快照 _vN 按磁盘最大版本+1；不做跨进程文件锁
- 理由：可观测性是辅助能力，绝不能阻塞核心分析；原子写防写撕裂；_vN 取磁盘版本避免进程重启后内存计数归零覆盖历史。面向答辩演示的轻度并发，「不同 trace 目录+原子写+碰撞规避」已足够，完整锁是过度设计
- 备选：落盘失败即请求失败（排除：鲁棒性差）、内存计数器定版本号（排除：进程重启丢历史）、跨进程锁（排除：过度设计）

## 2026-06-02: 决策过程追溯用 node_trace 轻量覆盖
- 选择：meta.json 记录 node_trace（节点执行序列 + 每次打回的 issues 摘要和目标 agent），不存 prompt/LLM 原始响应
- 理由：评分要求「决策过程可追溯」，但全存 prompt/原始响应范围爆炸；node_trace + feedback.json（质检决策）已轻量覆盖决策主体，prompt 留作未来扩展
- 备选：全量存 prompt 和 LLM 原始响应（排除：范围爆炸，收益边际递减）

## 2026-06-02: 追溯方法论 — doubt-driven 前置评审
- 选择：设计阶段用 doubt-driven（单模型 + Codex 跨模型对抗审查）在写码前审方案
- 理由：本功能跨模块、含路径穿越等安全断言，事前审查比事后调试便宜。实测捕获 8 处实质问题（原子写、model_dump mode、路径正则锚定、meta 孤儿、快照覆盖范围等），全部在写码前修正
- 备选：直接实现后 code review（排除：方向性缺陷到 review 阶段返工成本高）

## 2026-06-01: 采集数据传递方式
- 选择：Analyzer 和 Writer 使用 model_dump() 序列化完整数据传给 LLM
- 理由：原实现只传统计数字，LLM 无法生成有意义的分析/报告；完整数据传递是正确性问题
- 备选：手动拼接摘要文本（排除原因：丢失关键细节）
