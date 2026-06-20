# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# PentaScope — AI 驱动的竞品分析 Agent 协作系统

## 项目概述

面向产品经理 / 市场分析师的多 Agent 竞品分析系统。由信息采集、分析师、报告撰写、质检四个专职 Agent 组成（S2 场景前置一个推荐 Agent），完成从公开信息采集到结构化竞品报告的全链路产出。

## 上下文恢复

每次对话开始时，先读以下文件了解项目状态：
- `PROGRESS.md` — 当前进度、进行中的任务、下一步 1-2 session 计划
- `DECISIONS.md` — 已做出的技术决策及其理由
- `OPEN_QUESTIONS.md` — 已发现但未决定如何应对的深层问题（跨 session 反复回访）
- `docs/PRD.md` — 产品需求文档

三文档边界：
- 已经决定怎么修 → DECISIONS（写决策）+ PROGRESS（排期实施）
- 还没决定怎么修，但讨论过 → OPEN_QUESTIONS
- 一两天就能消化 → 留在 PROGRESS 不要分
- 跨 session 反复回访 / 跨场景跨模块 / 修复路径不明 / 可能引发架构级改动 → 移到 OPEN_QUESTIONS

## 技术栈

- **LLM**: 任意 OpenAI API 兼容模型（通过环境变量 `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL` 配置）；支持分层调用（`MODEL_FAST` 轻任务 + `MODEL_PRO` 强推理）
- **编排框架**: LangGraph（StateGraph）
- **Agent 构建**: 纯 Python 函数 + LangGraph 节点（手写，不用 LangChain 封装）
- **后端**: FastAPI + uvicorn
- **前端**: Streamlit + Plotly（调用后端 API，前后端分离）
- **数据校验**: Pydantic v2；HTTP 用 httpx；HTML 解析用 BeautifulSoup4

## 设计取向

1. 多 Agent 协作与输出可信度 — 角色划分、结构化消息、反馈闭环、信息溯源
2. 技术深度与工程完整度 — 端到端链路、可观测性、错误恢复
3. 业务价值与产品体验 — 效率提升、交互设计、业务闭环
4. 代码质量与文档 — 模块化、文档齐全、Git 规范
5. 合规与安全 — 数据采集合规、隐私安全

## Schema 设计

5 场景（S1 功能迭代 / S2 市场进入 / S3 定价策略 / S4 竞争监控 / S5 定位策略）共用一条契约链：

`ScenarioInput`（输入，分支校验）→ `CompetitorProfile`（采集产出）→ `CompetitiveAnalysis`（分析产出）→ `BaseReport` + 场景 Payload（报告产出）→ `RejectionFeedback`（质检产出）

各场景 Payload schema 在 `src/schemas/scenarios/s1..s5.py`，通用 schema 在 `src/schemas/{input,profile,analysis,report,feedback,common}.py`。改动数据流时先改这里。

## 项目约定

- 代码用英文命名，注释和文档用中文
- 遵循 CLAUDE.md 全局规则（简洁、手术式修改、目标驱动）
- Git 提交信息格式：`<type>: <description>`（feat / fix / docs / refactor）

## 结束对话流程

每次对话结束前，必须按顺序执行以下步骤：

1. 更新 `PROGRESS.md` — 记录本次完成、进行中、下一步
2. 更新 `DECISIONS.md` — 记录本次做出的技术决策（如有）
3. `git add` → `git commit` → `git push origin master` — 同步到远程仓库
   - **关键：push 前必须先跑 `git status`，确认本次实际参与项目开发、且保存在本地的所有新增/改动文件都已纳入提交，一个都不能漏。** 这包括但不限于代码、文档、配置，以及技能（spec-driven、writing-plans 等）产出并落盘到本地的过程文档（如 `docs/SPEC.md`、`docs/superpowers/plans/` 下的计划文件）。
   - 技能调用不会自动 `git add`，需显式添加。除 `.gitignore` 明确排除者（如 `.env`、密钥等敏感文件）外，本地的开发产物都应同步到远程，避免换电脑后丢失。

## 常用命令

环境（Windows，venv + pip）：

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

运行（后端与前端需分别在两个终端启动，前端依赖后端 API）：

```powershell
# 后端 API（默认 http://127.0.0.1:8000，健康检查 /health）
uvicorn src.api.main:app --reload

# 前端
streamlit run src/frontend/app.py
```

测试与 lint：

```powershell
pytest                                   # 全部测试（pytest-asyncio auto 模式）
pytest tests/unit/test_collector.py      # 单个文件
pytest tests/unit/test_collector.py::test_name   # 单个用例
pytest tests/integration                 # 端到端集成测试（5 场景 graph E2E + API + trace）
pytest -k collector                      # 按关键字筛选
ruff check src tests                     # lint
ruff check --fix src tests               # 自动修复
```

运行需在项目根目录配置 `.env`：
- `LLM_API_KEY` 必填（兼容旧名 `DOUBAO_API_KEY`）
- `LLM_BASE_URL` 必填——OpenAI API 兼容端点地址
- `LLM_MODEL` 必填——模型标识 / endpoint ID
- `TAVILY_API_KEY` 选填——搜索主线 Tavily 的鉴权 key；缺 key 则跳过搜索主线、走占位降级（completeness=0.0）
- `MODEL_FAST` / `MODEL_PRO` 选填——分层模型，不配则统一用 `LLM_MODEL`
- 其余配置见 `src/utils/config.py` 默认值，writer 相关两项重点：
  - `WRITER_MAX_LLM_CALLS=18` — writer 4 阶段总 LLM 调用熔断阈值
  - `WRITER_NARRATIVE_CONCURRENCY=3` — Phase 3 narrative 并发上限

## 代码架构

5 节点流水线由 LangGraph `StateGraph` 编排（v3），核心在 `src/graph/builder.py`：

```
                 ┌─(S2)─→ recommender ─┐
   set_entry ───┤                       ├─→ collector → analyzer → writer → inspector ─┬─(passed)─→ END
                 └─(其他)──────────────┘                  ↑          ↑          ↑      │
                                                          │          │          │      ├─(issues→writer)────→ writer
                                                          │          │          │      ├─(issues→analyzer)──→ analyzer
                                                          │          │          │      └─(issues→collector)─→ collector
                                                          └──────────┴──────────┴── 反馈闭环回边
```

- **场景路由**（v3）：`set_conditional_entry_point` 按 `ScenarioInput.scenario` 分流——S2「市场进入」先走 `recommender` 推荐 Top 3-5 玩家，再 union 到 `collector`；其余 4 个场景直接进 `collector`。
- **共享状态** `src/graph/state.py::AnalysisState`：TypedDict，节点间通过返回 dict 增量更新（`profiles`/`analysis`/`report`/`feedback`/`competitor_recommendations`/`retry_count` 等）。所有跨 Agent 数据都是 Pydantic 模型，而非裸 dict。
- **反馈闭环** `builder.py::should_continue`：质检不通过时，按 `feedback.issues[].agent` 字段决定打回 `collector` / `analyzer` / `writer`；inspector 打回时 `retry_count +1`（06-09 修复，否则永远不触发上限），`retry_count >= max_retries`（默认 2）则强制结束。这是产品要求的「质检→上游反馈闭环」实现点。
- **Agent**（`src/agents/`）：
  - `RecommenderAgent.recommend`（S2 入口）— 搜索行业头部玩家 + LLM 推理产出 ≥3 条 `CompetitorRecommendations`
  - `CollectorAgent.collect` — 持有 `CollectionPipeline`（`src/agents/collection_pipeline.py`），编排「Tavily 搜索 → 质量闸门 → 全空兜底」主线；Tavily 一次调用直返带正文 SourceResult，跳过传统三步走
  - `AnalyzerAgent.analyze` — 产出 `CompetitiveAnalysis`；LLM ValidationError 时由 `analyzer_node` 兜底注入 feedback 不让 graph 崩溃（06-09 修复）
  - `WriterOrchestrator.write` — **替代旧 WriterAgent**，4 阶段编排：
    1. **outline**（LLM）— Phase 1 产出 section 骨架，Pydantic 失败重试
    2. **payload**（LLM）— Phase 2 实例化场景 Payload schema，含 S2 recommender 强制覆盖、S4 prior diff 前置注入
    3. **narrative**（LLM 并行）— Phase 3 `asyncio.Semaphore` 限速 + 半数硬闸门 + 占位降级
    4. **assemble**（0 LLM）— Phase 4 代码合成 `BaseReport`（SWOT 透传 + URL 双通道收集 + scope.competitors S2 union + ReportMetadata 构造）
  - `InspectorAgent.inspect` — `_check_common` + `_check_s1..s5` dispatcher + LLM 质检；`quality_score` 由 `src/agents/quality_score.py::calc_quality_score` 三项加权（source_coverage / confidence_avg / inspector_pass_rate），placeholder warnings 强制 cap 0.5（v3-R17 / v3-R22）。**改 inspector 时勿动这条 quality_score 回填链**。

  所有 prompt 集中在 `src/agents/prompts/`（含 `writer/` 子目录的 outline/payload/narrative 三套）。

  Writer 阶段错误用三类自定义异常路由（避免依赖中文措辞子串匹配）：`WriterRouteToCollector`（回采集）/ `WriterRouteToWriter`（重写）/ `WriterRouteToEnd`（不可恢复终止）。

- **工具**（`src/tools/`）：
  - `llm_client` — OpenAI API 兼容客户端，纯 prompt 约束 + 代码块剥离 + JSON 4 层兜底解析；支持分层模型（fast/pro）；带超时/重试；`call_json` 支持 `max_tokens`
  - `http_client` — httpx async，同域名限速 `COLLECT_INTERVAL` + per-domain 锁
  - `sources` — Tavily 搜索源（仅此一家，06-07 弃用 SerpAPI；iTunes 06-06 因同名污染移除）
  - `quality_gate` — 采集质量闸门
  - `scenario_picker` — `ai_pick_scenario` 函数，前端「AI 帮我选场景」按钮 + `/api/v1/pick-scenario` 后端的核心
  - `trace_writer` — 中间产物落盘
  - `html_parser`、`validators`

- **入口**：后端 `src/api/main.py` 暴露 3 个路由（`src/api/routes.py`）：
  - `POST /api/v1/analyze` — 主分析入口，每请求生成 `trace_id` 并构图执行
  - `POST /api/v1/pick-scenario` — 用户填了 `analysis_context` 后让 AI 选场景
  - `GET /api/v1/trace/{trace_id}` — 中间产物追溯（含路径穿越双重防护，`?version=` 取历史版本）

  前端 `src/frontend/app.py` + `src/frontend/render.py`（5 场景 BaseReport 渲染 + Plotly 图表：S1 5 维雷达、S2 五力蜘蛛网、S5 Perceptual Map / Magic Quadrant / Strategy Canvas）。

- **可观测性**：日志统一走 `src/utils/logger.py`，图节点切换打 `[graph] → <node>` 日志，配合 `trace_id` 串联一次分析的全链路（核心设计取向之一，勿移除）。
- **中间产物追溯**：`src/tools/trace_writer.py::TraceWriter` 把每次分析的四阶段产物（profile/analysis/report/feedback）、meta 和 `run.log` 落盘到 `runs/<trace_id>/`（路径见 `src/utils/paths.py`，不依赖 CWD）；反馈闭环重试时旧产物存为 `_vN` 快照。前端「执行追溯」面板按 tab 展示。改追溯数据结构时连同 `src/schemas` 与该面板一起改。
