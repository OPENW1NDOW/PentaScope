# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# AI 驱动的竞品分析 Agent 协作系统

## 项目概述

字节跳动 CIS 部门 AI 全栈项目挑战赛课题。目标是构建一个多 Agent 协作的竞品分析系统，由信息采集、分析师、报告撰写、质检四个专职 Agent 组成，完成从公开信息采集到结构化竞品报告的全链路产出。

## 上下文恢复

每次对话开始时，先读以下文件了解项目状态：
- `PROGRESS.md` — 当前进度、进行中的任务、下一步计划
- `DECISIONS.md` — 已做出的技术决策及其理由
- `docs/PRD.md` — 产品需求文档

## 技术栈

- **LLM**: Doubao-Seed-2.0-lite（通过 OpenAI SDK 调用火山方舟 Ark 端点）
- **编排框架**: LangGraph（StateGraph）
- **Agent 构建**: 纯 Python 函数 + LangGraph 节点（手写，不用 LangChain 封装）
- **后端**: FastAPI + uvicorn
- **前端**: Streamlit（调用后端 API，前后端分离）
- **数据校验**: Pydantic v2；HTTP 用 httpx；HTML 解析用 BeautifulSoup4

## 核心考察点（来自课题评分标准）

1. 多 Agent 协作与输出可信度（35%）— 角色划分、结构化消息、反馈闭环、信息溯源
2. 技术深度与工程完整度（25%）— 端到端链路、可观测性、错误恢复
3. 业务价值与产品体验（20%）— 效率提升、交互设计、业务闭环
4. 代码质量与文档（10%）— 模块化、文档齐全、Git 规范
5. 合规与答辩（10%）— 数据采集合规、隐私安全

## Schema 设计要求

Agent 产出必须符合预定义的竞品知识 Schema：
- **功能树**：竞品功能模块、子功能、支持情况
- **定价模型**：价格方案、计费方式、免费/付费划分
- **用户画像**：目标用户、使用场景、满意度

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

## 时间节点

- 5月20日：开营
- 5月20日～6月10日：开发阶段（3周）
- 6月10日：提交成果
- 6月12日～6月19日：答辩

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
pytest -k collector                      # 按关键字筛选
ruff check src tests                     # lint
ruff check --fix src tests               # 自动修复
```

运行需在项目根目录配置 `.env`：
- `DOUBAO_API_KEY` 必填
- 搜索主线按 `SEARCH_PROVIDER` 切换：`serpapi`（需 `SEARCH_API_KEY`）或 `tavily`（需 `TAVILY_API_KEY`）；缺 key 则跳过搜索主线、仅走专源/占位降级
- 其余配置见 `src/utils/config.py` 默认值

## 代码架构

四 Agent 流水线由 LangGraph `StateGraph` 编排，核心在 `src/graph/builder.py`：

```
collector → analyzer → writer → inspector ─┬─(passed)──────────────→ END
                ↑          ↑                 ├─(issues→writer)──────→ writer
                │          └─────────────────┼─(issues→collector)───→ collector
                └────────────────────────────┴─(issues→analyzer)────→ analyzer
```

- **共享状态** `src/graph/state.py::AnalysisState`：一个 TypedDict，节点间通过返回 dict 增量更新（`profiles`/`analysis`/`report`/`feedback`/`retry_count` 等）。所有跨 Agent 数据都是 Pydantic 模型，而非裸 dict。
- **反馈闭环** `builder.py::should_continue`：质检不通过时，按 `feedback.issues[].agent` 字段决定打回 `collector` / `analyzer` / `writer`（analyzer 回边为保险，正常流程 SWOT/雷达/矩阵由 writer 代码透传 + analyzer 兜底已保证）；`retry_count >= max_retries`（默认 2）则强制结束。这是课题要求的「质检→上游反馈闭环」的实现点。
- **Agent**（`src/agents/`）：对外暴露单个 async 方法（`collect`/`analyze`/`write`/`inspect`），所有 prompt 集中在 `src/agents/prompts.py`。**采集层已分层下沉**（06-03）：`CollectorAgent` 不再直持 `http`/`parser`，而是持有 `CollectionPipeline`（`src/agents/collection_pipeline.py`），后者编排「搜索 API → LLM 选页 → 抓正文 → 质量闸门」主线，搜索源插件在 `src/tools/sources.py`（SerpAPI / Tavily 双 provider，按 `SEARCH_PROVIDER` 切换；iTunes 已于 06-06 因同名污染移除）。analyzer/writer/inspector 仍为 `(llm)` 依赖。
- **Schema**（`src/schemas/`）：竞品知识的契约层，对应 PRD 的功能树/定价模型/用户画像。`input`(输入) → `profile`(采集产出) → `analysis`(分析产出) → `report`(报告) → `feedback`(质检)，与流水线各阶段一一对应。改动数据流时先改这里。
- **工具**（`src/tools/`）：`llm_client`（Doubao 纯 prompt 约束 + 代码块剥离，**不**用 `response_format`——06-01 实测端点不支持；带超时/重试）、`http_client`（httpx async，同域名限速 `COLLECT_INTERVAL` 加 per-domain 锁，URL/异常双重脱敏 key）、`sources`（SerpAPI/Tavily 搜索源）、`quality_gate`（采集质量闸门）、`trace_writer`（中间产物落盘）、`html_parser`、`validators`。
- **入口**：后端 `src/api/main.py`（路由 `src/api/routes.py` 的 `POST /api/v1/analyze`，每请求生成 `trace_id` 并构图执行）；前端 `src/frontend/app.py`。
- **可观测性**：日志统一走 `src/utils/logger.py`，图节点切换打 `[graph] → <node>` 日志，配合 `trace_id` 串联一次分析的全链路（评分项之一，勿移除）。`quality_score` 由 `inspector_node` 按 issue 严重度倒推回填（06-01 决策），不靠 LLM 自评——改 inspector 时勿动这条回填链。
- **中间产物追溯**：`src/tools/trace_writer.py::TraceWriter` 把每次分析的四阶段产物（profile/analysis/report/feedback）、meta 和 `run.log` 落盘到 `runs/<trace_id>/`（路径见 `src/utils/paths.py`，不依赖 CWD）；反馈闭环重试时旧产物存为 `_vN` 快照。追溯接口 `GET /api/v1/trace/{trace_id}`（路由 `src/api/routes.py`，含路径穿越双重防护，`?version=` 取历史版本），前端「执行追溯」面板按 tab 展示。改追溯数据结构时连同 `src/schemas` 与该面板一起改。
