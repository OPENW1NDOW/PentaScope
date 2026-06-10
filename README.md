# PentaScope

**AI 驱动的竞品分析 Agent 协作系统**

> Penta = 5 场景 · Scope = 全景视角。基于 LangGraph 的多 Agent 编排，从公开信息采集到 5 场景咨询级竞品报告的全链路自动化。

![Python](https://img.shields.io/badge/python-3.10%2B-blue) ![LangGraph](https://img.shields.io/badge/LangGraph-0.2%2B-orange) ![FastAPI](https://img.shields.io/badge/FastAPI-0.111%2B-green) ![Streamlit](https://img.shields.io/badge/Streamlit-1.35%2B-red) ![Tests](https://img.shields.io/badge/tests-445%20passed-brightgreen) ![License](https://img.shields.io/badge/license-MIT-lightgrey)

---

## 核心价值

- **效率**：端到端 10 分钟以内产出 7000-8000 字咨询级报告（vs 人工 2-3 天）
- **专业度**：5 个分析场景按业界标杆框架组织（Forrester Wave / Gartner Magic Quadrant / Porter 五力 / GBB / Blue Ocean ERRC）
- **可信度**：每条结论绑定原始 URL，全链路可溯源，质检 Agent 三项加权评分
- **可靠性**：LangGraph 状态机 + 质检反馈闭环，问题自动打回上游 Agent 修复

---

## 5 场景能力

| 场景 | 适用情境 | 核心产出 |
|---|---|---|
| **S1 功能迭代** | 已有产品看竞品功能差距 | Forrester Wave 风格表 + 5 维雷达 + 功能矩阵 + 路线图 |
| **S2 市场进入** | 还没产品看赛道格局 | Top 玩家推荐 + TAM/SAM/SOM + Porter 五力 + 进入策略 |
| **S3 定价策略** | 调价 / 重新打包 | GBB 三层套餐 + 竞品定价矩阵 + ARR 预测 |
| **S4 持续监控** | 季度跟踪 / 战卡更新 | 5 类变更 + 威胁象限 + 活体战卡 + 增量 diff |
| **S5 战略定位** | 重新定位 / 品牌升级 | Magic Quadrant + Perceptual Map + Strategy Canvas + ERRC |

---

## 系统架构

```
                 ┌─(S2)─→ recommender ─┐
   set_entry ───┤                       ├─→ collector → analyzer → writer → inspector ─┬─(passed)─→ END
                 └─(其他)──────────────┘                  ↑          ↑          ↑      │
                                                          │          │          │      ├─(issues→writer)────→ writer
                                                          │          │          │      ├─(issues→analyzer)──→ analyzer
                                                          │          │          │      └─(issues→collector)─→ collector
                                                          └──────────┴──────────┴── 反馈闭环回边
```

| 节点 | 职责 |
|---|---|
| **recommender**（S2 入口） | 搜索行业头部玩家 + LLM 推理产出 Top 3-5 推荐竞品 |
| **collector** | Tavily 一次调用直返带正文，抽取结构化 `CompetitorProfile` |
| **analyzer** | 跨竞品对比 + 各维度结论绑定 source URL，产 `CompetitiveAnalysis` |
| **writer** | 4 阶段编排（outline / payload / narrative / assemble），产 `BaseReport` |
| **inspector** | `_check_common` + 5 场景 dispatcher + LLM 质检，产 `RejectionFeedback` |

---

## 核心亮点

### 1. Multi-Agent 协作 + 反馈闭环

- **LangGraph StateGraph 编排**：5 节点流水线，节点间通过 Pydantic 模型严格契约（不传裸 dict）
- **质检反馈闭环**：质检不通过时按 `feedback.issues[].agent` 字段路由打回上游（collector / analyzer / writer），`retry_count + 1`，`max_retries = 2` 强制结束，避免假闭环
- **类型安全的异常路由**：Writer 三类自定义异常（`WriterRouteToCollector` / `WriterRouteToWriter` / `WriterRouteToEnd`）用 `isinstance` 判断，脱离脆弱字符串匹配
- **Writer 4 阶段编排**：突破单次 LLM 4-5K 字上限，通过 outline → payload → narrative 并发 → assemble，稳定产出 7000-8000 字报告

### 2. 5 场景专业报告 + 业界框架可视化

- **共享骨架 + 场景定制**：BaseReport 13 通用元素 + scenario discriminated union，5 套场景 Payload schema 各有专属字段
- **Plotly 交互图表**：S1 5 维多边形雷达 / S2 Porter 五力蜘蛛网 / S5 Perceptual Map + Magic Quadrant + Strategy Canvas 折线
- **Schema 强约束反幻觉**：S2 `MarketValue` 必填 `value_basis`、S3 GBB 强制 1 个 `is_recommended`、S4 首次模式强制 `is_baseline=True`、S5 `competitors_implied` 必须是 vendor_profiles 子集

### 3. 全链路信息溯源 + 质量评分

- **4 道防线确保溯源不断链**：collector 抽取时绑定 fact-URL → analyzer prompt 各维度 source_urls 输出槽 → writer 机械透传 + 按 dimension 下沉 source_refs → inspector 程序化硬查
- **三项加权 quality_score**：`source_coverage`（条目带 source_refs 占比）+ `confidence_avg`（数据源 confidence 数值化均值）+ `inspector_pass_rate`（按 issue 严重度倒推），placeholder warnings 强制 cap 至 0.5
- **TraceWriter 中间产物追溯**：每次分析的 4 阶段产物（profile / analysis / report / feedback）+ meta + run.log 落盘到 `runs/<trace_id>/`，反馈闭环重试时旧产物存 `_vN` 快照
- **trace_id 串联全链路**：北京时间格式 `YYYYMMDD-HHMMSS-<6hex>`，前后端 + 日志统一引用

### 4. 产品体验亮点

- **AI 帮我选场景**：填分析意图 → LLM 推断 + 置信度（high/medium/low）+ rationale 引用关键词，自动回填到场景 selectbox
- **Markdown / HTML 双格式导出**：HTML 全内嵌字体 woff2 base64 + Plotly + CSS 单文件 3-5MB，断网可用
- **HTML 导出三道 XSS 防护**：narrative 走 `markdown.markdown()` → `nh3.clean()` sanitize → Jinja2 autoescape，挡 stored XSS
- **执行追溯面板**：前端可加载任一 trace_id，4 个 tab 分别查看采集 / 分析 / 报告 / 质检产物，反馈闭环 `_vN` 快照可对比

---

## 技术栈

| 层 | 技术 | 职责 |
|---|---|---|
| LLM | Doubao-Seed-2.0-lite（OpenAI SDK 调火山方舟）| 全链路推理 |
| Agent 编排 | LangGraph StateGraph | 5 节点 DAG + 条件分支 + 环路 |
| 后端 | FastAPI + uvicorn | REST API |
| 前端 | Streamlit + Plotly | 交互式 UI + 图表 |
| 数据校验 | Pydantic v2 | 全链路 Schema 契约 |
| 数据采集 | Tavily API + httpx + BeautifulSoup4 | 一次调用直返带正文 |
| 报告导出 | markdown + Jinja2 + nh3 | Markdown / HTML 双格式 |
| 测试 | pytest + pytest-asyncio + ruff | 445 passed / ruff clean |

---

## 快速开始

### 环境准备

```powershell
# Windows (PowerShell)
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

```bash
# macOS / Linux
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 配置

```bash
cp .env.example .env
# 编辑 .env 填入：
# - DOUBAO_API_KEY    必填（火山方舟 Ark 端点 key）
# - TAVILY_API_KEY    选填（S2 场景需要；缺 key 时 S2 走占位降级）
```

### 启动

```powershell
# 终端 1：后端 API
uvicorn src.api.main:app --reload
# → http://127.0.0.1:8000  (健康检查 /health)

# 终端 2：前端
streamlit run src/frontend/app.py
# → http://localhost:8501
```

### 测试

```powershell
pytest                          # 全部测试
pytest tests/integration        # 5 场景 E2E
ruff check src tests            # lint
```

详细的 5 场景测试用例（含可复制粘贴的输入）见 [`docs/TESTING_GUIDE.md`](docs/TESTING_GUIDE.md)。

---

## 项目结构

```
.
├── src/
│   ├── agents/           # 5 个 Agent + prompts/ + normalizers/
│   ├── api/              # FastAPI 后端 + 报告导出 (markdown/html)
│   ├── frontend/         # Streamlit 前端 + theme + render
│   ├── graph/            # LangGraph 状态机 (builder / state)
│   ├── schemas/          # Pydantic 模型 (含 scenarios/s1-s5)
│   ├── tools/            # LLM/HTTP/sources/trace_writer/quality_gate
│   └── utils/            # 配置 / 日志 / 路径
├── tests/                # 单元测试 + 集成测试
├── docs/                 # PRD / SPEC / 测试指南 / superpowers 设计文档
├── PROGRESS.md           # 开发进度日志
├── DECISIONS.md          # 技术决策记录
├── CLAUDE.md             # AI 协作指引
└── README.md             # 本文件
```

---

## 文档导航

| 文档 | 内容 |
|---|---|
| [docs/PRD.md](docs/PRD.md) | 产品需求文档（V3.0，14 章节） |
| [docs/TESTING_GUIDE.md](docs/TESTING_GUIDE.md) | 5 场景手动测试指南，含可复制粘贴案例 |
| [docs/SPEC.md](docs/SPEC.md) | 技术规格 |
| [docs/竞品分析SOP.md](docs/竞品分析SOP.md) | 业务流程 SOP |
| [DECISIONS.md](DECISIONS.md) | 技术决策追溯 |
| [PROGRESS.md](PROGRESS.md) | 开发进度日志 |

---

## 测试与质量

- 445 个单元测试 + 集成测试全过
- ruff lint 全清
- 5 场景端到端 happy path 验证（含 S2 真跑 quality_score=0.800、S3 quality_score=0.836）
- 安全：路径穿越白名单（`^[a-f0-9-]+$` + 长度 ≤64）、HTML XSS sanitize、API key URL/异常双重脱敏

---

## License

MIT License — 详见 [LICENSE](LICENSE)。

## Author

[OPENW1NDOW](https://github.com/OPENW1NDOW)
