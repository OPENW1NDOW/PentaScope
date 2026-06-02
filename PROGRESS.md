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
- 进行中：无
- 下一步（新 session）：
  1. 手动 UI 验证前端追溯面板（启动前后端跑一次，确认 6 tab、快照对比渲染正常）
  2. feat/observability-trace 分支合并回 master
  3. 数据源场景适配（手机品牌 iTunes 不契合，Demo 建议用 Notion 类 SaaS）— 沿用 06-01 待办
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
