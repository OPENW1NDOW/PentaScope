# Project Progress

AI 驱动的竞品分析 Agent 协作系统 — 项目进度日志。

> 每次结束工作前更新，下次在另一台电脑开 Claude 时先读此文件。

## Format

```markdown
## YYYY-MM-DD
- 完成：...
- 进行中：...
- 下一步：...
- 阻塞：...（可选）
```

---

## 2026-06-04（数据源拓展真实跑通验证 + SerpAPI 鉴权 bug 修复）
- 完成：
  - 走 brainstorming → doubt-driven（单模型 + Codex gpt-5.5 跨模型对抗审查，捕获 B1 import 固化/B4 主线成败混淆等盲点）定稿验证方案 `docs/superpowers/specs/2026-06-04-datasource-verification-design.md`
  - 三路径端到端真实冒烟（非补单测；逻辑分支已 117 单测覆盖，本次只验真实环境契合度），证据看落盘 01_profiles.json 的 pipeline_trace + run.log：
    - 路径 A（语雀 vs 飞书，无 key）：search_skipped/no_api_key + saas→itunes 路由 + 真实 trackViewUrl，completeness 0.9；run.log 确认无 search/pick LLM 日志
    - 路径 A'（小米 vs OPPO，无 key）：default→空专源 + completeness=0.0 占位、不调 extract LLM、零数据源 HTTP（仅 Doubao）
    - 路径 B（语雀 vs 飞书，有 key）：修复后 SerpAPI 200、pick method=llm picked=3、抓到真实官网（feishu.cn/partnershare.cn），主线全打通
  - **systematic-debugging 抓出真实 bug（修复前主线在中文场景 100% 失效）**：SerpAPI 用 `Authorization: Bearer` header 鉴权时，遇非 ASCII（中文）query 返回 401「Invalid API key」（误导性极强）。证伪 4 个假设（env 污染/key 激活延迟/二次编码/headers 干扰），用同脚本同时刻 ASCII vs 中文对比锁定根因
  - TDD 修复（119 测试全绿 + ruff 清）：
    - `sources.py`：SerpAPI 鉴权改 `api_key=` query 参数（去掉 Bearer header）；新增中文 query 编码回归测试
    - `logger.py`：httpx/httpcore 日志压到 WARNING——其 INFO 会明文打含 api_key 的完整 URL（防泄漏）；新增防泄漏测试
    - `test_config.py`：修预存测试隔离 bug（reload 时 load_dotenv 重读 .env 真实 key 致 SEARCH_API_KEY 断言失败，monkeypatch 屏蔽 load_dotenv）
  - 安全核查：.gitignore 已覆盖 .env/logs/runs/.claude，别人 clone 看不到含 key 文件；清理本地历史明文泄漏（app.log + 旧 trace），残留=0
  - **关键认知**：报告 quality_score 由 inspector 按 issue 严重度倒推回填（builder.py:602），全链路真正的质量分只有「采集 completeness_score」+「质检倒推 quality_score」两处；analyzer/writer 不自评。报告质量低与数据源好坏无关，由 writer 加工缺陷决定（课题②）
- 进行中：无
- 下一步（新 session）：
  1. 【报告质量，独立课题②】沿用待办：抓 04_feedback 完整 issues 确认是否仍是三老问题（source_refs 下沉断链 / SWOT 丢失 / focus_area 空），debug writer + collector
  2. iTunes 同名 App 污染（搜「语雀」带出 flomo/石墨；搜「飞书文档」带出腾讯文档/石墨）——top3 混入同赛道他家，profile 可能混入别家信息，可考虑结果过滤或 limit 调整
- 阻塞：无
- 安全提醒：**SEARCH_API_KEY（SerpAPI）本 session 在终端/日志多处明文出现过，务必轮换**；Doubao API Key 同样务必轮换（沿用历史提醒）。两者均走 .env、勿提交

## 2026-06-03（数据源拓展：采集管线重构）
- 完成：
  - 走完整 brainstorming → 三轮 doubt-driven（每节单模型 + Codex gpt-5.5 跨模型对抗审查）→ writing-plans → subagent-driven 流程
  - 设计文档 `docs/superpowers/specs/2026-06-03-datasource-expansion-design.md`，实现计划 `docs/superpowers/plans/2026-06-03-datasource-expansion.md`（15 Task）
  - 采集层从 collector 内 3 个硬编码 URL 源，重构为分层管线 `CollectorAgent(agent) → CollectionPipeline(tool) → sources(插件)`：
    - 主线两步走：SerpAPI 搜索 → LLM 选页（独立短超时 wait_for，失败退规则）→ 抓正文 → 质量闸门过滤
    - 结构化专源按 category 路由、可插拔（saas→iTunes；硬件电商源列入未来扩展）
    - 无 SEARCH_API_KEY 时跳过搜索主线、仅走专源（不退回 SERP 抓取）
    - 全空时产 completeness=0.0 占位 profile（不调 extract LLM，防幻觉）
    - 顶层 collect 改部分降级（单竞品失败产占位，不拖垮全局，语义从「快速失败」变更）
    - pipeline_trace 随 profile.metadata 落盘（与 graph node_trace 分离）
  - 新增 `src/tools/sources.py`（iTunes+SerpAPI+路由）、`src/agents/collection_pipeline.py`、`src/tools/quality_gate.py`；`HttpClient.get_json`（key 走 header、URL/异常双重脱敏、UA 加锁）；`ProfileMetadata.pipeline_trace`；config 加 4 个可选配置
  - 117 测试全绿（原 51 → 117）、ruff 全清；TDD + 小步提交（21 commits）
  - doubt-driven + 代码审查捕获并修复的真实问题：路由原语用错（competitor_type 误当 SaaS/硬件类别）、密钥经 query/异常消息泄漏、CollectionPipeline `_current_name` 实例属性并发数据竞争（A 报告混入 B 数据，改参数传递）、集成测试 6 步序列隐式依赖环境变量为空（显式 monkeypatch 屏蔽）、_rate_limit check-then-act 限速竞态（加 per-domain 锁）、iTunes 空壳记录污染 sources
  - **重要发现**：subagent 报「集成测试全绿」一度是占位降级路径假象（extract response 未被消费），亲自核实后在 Task15 让集成测试走真实采集路径（saas 路由 + mock get_json + call_index==6 断言锁定）
- 进行中：无
- 下一步（新 session）：
  1. feat/datasource-expansion 合并回 master（本 session 进行中）
  2. 真实跑通验证：配 `SEARCH_API_KEY`（SerpAPI）验证搜索主线；无 key 验证专源降级路径；Demo 建议用 Notion 类 SaaS（数据源契合）
  3. 【报告质量，独立课题】沿用 06-02 待办：溯源下沉断链、SWOT 丢失、focus_area 空（与本次数据源拓展无关）
- 阻塞：无
- 安全提醒：验收用的 Doubao API Key 在历史对话中明文出现过，务必轮换（沿用历史提醒）；新引入的 SEARCH_API_KEY 走 .env，勿提交

## 2026-06-02（可观测性与中间产物追溯）
- 完成：
  - 走完整 brainstorming → doubt-driven（单模型 + Codex 跨模型对抗审查）→ writing-plans → subagent-driven 流程
  - 设计文档 `docs/superpowers/specs/2026-06-02-observability-trace-persistence-design.md`，实现计划 `docs/superpowers/plans/2026-06-02-observability-trace-persistence.md`
  - SPEC.md 移入 docs/，修正过时的 JSON mode 决策（与 DECISIONS 06-01 对齐）
  - 14 个 Task 全部实现（feat/observability-trace 分支），71 测试通过、ruff 全清：
    - TraceWriter（src/tools/trace_writer.py）：trace_id 北京时间格式+碰撞规避、save_stage（json mode 序列化+原子写+重试快照 _vN）、save_meta、容错仅 warning 不抛
    - src/utils/paths.py：项目根/runs/logs 绝对路径，不依赖 CWD
    - 日志接线：init_logging 配 root logger（控制台+logs/app.log），修复 setup_logger 从未被调用的 bug；每次分析另存 runs/<trace_id>/run.log
    - graph 各节点产出落盘四阶段产物，build_graph 返回 (graph, node_trace) 记录路由决策
    - routes.py：trace_id 新格式、TraceWriter 注入、ainvoke 前后两次写 meta（running/completed/failed）
    - 追溯 API GET /trace/{trace_id}：路径穿越双重防护（fullmatch + resolve 校验）、按需取历史版本
    - 前端「执行追溯」面板：6 tab 展示中间产物+日志+快照对比
  - doubt-driven 暴露并修复的真实问题：原子写、model_dump(mode=json)、路径穿越正则未锚定、meta 两次写防孤儿、快照覆盖全 4 stage、logger 幂等判断按 baseFilename
  - 手动 UI 验证通过：真实跑通多次分析，产物落盘/meta/run.log/node_trace 全正常；反馈闭环+重试快照真实生效（ef2b68 打回 collector，01~04 的 _v1 快照全保存，验证了「快照覆盖全 4 stage」修正）；追溯面板加载成功；顺手修了前端 trace_id 输入 strip（粘贴空格导致 404）
- 进行中：无
- 下一步（新 session）：
  1. feat/observability-trace 分支合并回 master
  2. 【报告质量，独立课题】UI 验证时质检诚实暴露上游 Agent 3 类真实缺陷（与可观测性功能无关，是先前就存在、现在才被追溯照出）：
     - 溯源下沉断链：report 顶层有 12 条 data_sources，但各 section 的 source_refs、各 action_item 的 source_urls 全空（与 06-01 修过的 report.data_sources 断链同类、不同位置）
     - SWOT 丢失：analysis 里有 SWOT，但 writer 没写进最终报告的 SWOT 模块
     - focus_area 空：collector 解析目标时未填 analysis_goal.focus_area
     - 后果：质检每次发现 3+ issue、打回重试 2 次仍不通过、quality_score=0.0
     - 修复方向：debug writer（下沉 source_refs/source_urls、补 SWOT 模块）、collector（填 focus_area）
  3. 数据源场景适配（手机品牌 iTunes 不契合，Demo 建议用 Notion 类 SaaS）— 沿用 06-01 待办
  4. 【可选小优化】Windows 控制台中文乱码（GBK），run.log/app.log 文件本身 UTF-8 正常，仅终端显示乱码
- 阻塞：无
- 安全提醒：验收用的 Doubao API Key 在历史对话中明文出现过，务必轮换（沿用 06-01 提醒）

## 2026-06-01（前后端手动验收）
- 完成：
  - 环境搭建：Python 3.14 + venv，依赖全装（无 wheel 兼容问题），51 测试通过
  - 真实 Doubao API 端到端验收，跑通完整四 Agent 链路，产出高质量结构化报告
  - 验收中修复 4 个真实问题：
    - `response_format=json_object` Doubao 不支持（400）→ 改纯 prompt 约束 + 代码块剥离
    - `LLM_TIMEOUT=30s` 太短（单次调用实测 30.4s）→ 调到 120s
    - 数据源抓取全失败（百科403/AppStore404/百度反爬）→ 换 iTunes API + Bing + 搜狗，补全请求头
    - `report.data_sources` 断链（writer 拿不到 profile sources）→ graph 层 writer_node 回填
  - 顺手修两处瑕疵：前端行动建议层级标签（immediate=即时）、quality_score 由 inspector_node 按 issue 严重度回填（0-1）
  - 验证溯源恢复：报告 data_sources 含 3 个真实来源，正文用上 iTunes 真实评分（4.7/5，2万+评价）
  - CLAUDE.md 补充常用命令 + 代码架构（/init）
- 进行中：无
- 浏览器验收发现并修复：
    - 竞品上限 5→10（用户输入 6 个触发 422）
    - 前端错误处理 bug：未处理非 200 响应，直接读 data["status"] 抛 KeyError，掩盖真实校验错误 → 改为先判 status_code，解析 FastAPI detail 友好展示
    - LLM 输出结构偏差：sample_reviews 被填成字符串数组（应为 SampleReview 对象），导致采集校验失败 → ① prompt 补全元素结构示例 ② collector 加 _normalize_raw 兜底（字符串转 {content, rating:3}）
    - LLM JSON 含裸控制字符（字符串值内裸换行）→ Invalid control character → llm_client 改 json.loads(..., strict=False)
    - analyzer 枚举校验失败：feature_matrix.gap_level 被填 "小米领先" 等带主语值 → analyzer 加 _normalize（gap_level/our_product/competitors/swot.dimension 枚举规整：精确→包含匹配→默认）
    - writer 枚举校验失败：action_items.priority 被填 "中等" → writer 加 _normalize（priority 规整 + metadata 补充）
  - 最终验证成功：6 品牌（小米/VIVO/OPPO/三星/华为/苹果）完整跑通，产出高质量报告，data_sources 13 条真实 URL，quality_score 0.55，无校验错误
- 下一步（新 session 优先处理）：
  1. 【可观测性，评分项】修日志落盘：setup_logger 写了但从未被调用，logs/app.log 不生成；agent/graph 的 INFO/WARNING 日志（[graph] → collector、采集源成败、completeness）全部丢失。需在 api 启动时初始化 logger 并配置 root level，让全链路日志可见。
  2. 【数据源场景适配】手机品牌用 iTunes(App 搜索) 不契合——搜到的是同名 App 非手机硬件，导致溯源 URL 真但内容弱。Demo 建议用 Notion 类 SaaS 软件（数据源契合），手机仅作架构通用性展示；或为硬件场景换专业评测/电商源。
  3. quality_score 0.55 偏低反映数据完整度一般（质检诚实反映），与 #2 相关联。
- 已知非阻塞瑕疵：无（本轮 LLM 鲁棒性问题已全部修复）
- 阻塞：无
- 安全提醒：验收用的 Doubao API Key 在对话中明文出现过，务必轮换

## 2026-05-31 ~ 2026-06-01
- 完成：
  - PRD V3.0 重写（基于 MIT 模板 + 竞品分析 SOP，14 章节完整覆盖）
  - SPEC.md 技术规格（spec-driven development skill）
  - 18 个实现 Task 全部完成（subagent-driven development skill）
    - Task 1: 项目骨架
    - Task 2-5: 5 个 Schema（input/profile/analysis/report/feedback）
    - Task 6-9: 4 个工具（config/logger/LLM client/HTTP client/HTML parser/validators）
    - Task 10-14: 4 个 Agent + Prompts（collector/analyzer/writer/inspector）
    - Task 15-16: LangGraph State + Builder（含反馈闭环）
    - Task 17-18: FastAPI 后端 + Streamlit 前端
  - 代码审查（code-reviewer agent），发现 10 个问题
  - 10 个审查问题修复（4 批 subagent 并行修复）
  - receiving-code-review 验证：9 个修复合理，#8 为误判已回退
  - .env 配置（Doubao API Key）
  - 51 个测试全部通过
- 进行中：无
- 下一步：手动验收（启动前后端，真实 Doubao API 跑完整分析）
- 阻塞：无

## 2026-05-30
- 完成：
  - 开题材料研读与分析（CIS AI 全栈挑战赛开题材料）
  - lark-cli 安装验证、飞书认证、lark-cli skill 清理
  - PRD 撰写（产品定位、Schema 设计、4 Agent 角色定义、数据源、信息溯源、可观测性）
  - 项目文档结构整理（docs/ 分离项目内容与开发过程文档）
  - 开发计划制定（11 天极限计划，5/30-6/10）
- 进行中：PRD 待 Cooper 审阅确认
- 下一步：技术方案设计 + 项目骨架搭建（LangGraph hello world）
- 阻塞：无
