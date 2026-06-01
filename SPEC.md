# Spec: AI 驱动的竞品分析 Agent 协作系统

## Objective

构建一个多 Agent 协作的竞品分析系统。用户输入竞品名称和分析意图，系统自动完成信息采集、结构化分析、报告撰写、质量校验，输出一份带溯源的竞品分析报告。

**核心考察点**：多 Agent 协作与输出可信度（35%）、技术深度与工程完整度（25%）、业务价值与产品体验（20%）。

**成功标准**：
- 输入"支付宝"，10 分钟内产出结构化竞品分析报告
- 报告包含四维分析（定位/功能/商业/运营）、SWOT、行动建议（时间分层）
- 每条结论绑定数据来源，支持溯源查看
- 质检 Agent 可识别问题并打回上游 Agent 修正（反馈闭环）
- 全链路可观测：每个 Agent 的输入/输出/耗时可查

## Tech Stack

| 层 | 技术 | 版本 |
|----|------|------|
| Agent 编排 | LangGraph | latest |
| LLM | Doubao-Seed-2.0-lite（OpenAI 兼容 API） | EP: ep-20260514111325-xjmj7 |
| LLM 客户端 | openai SDK（兼容模式） | latest |
| 后端 | FastAPI + uvicorn | latest |
| 前端 | Streamlit | latest |
| 数据采集 | httpx + BeautifulSoup4 | latest |
| 依赖管理 | venv + pip + requirements.txt | - |
| 测试 | pytest + pytest-asyncio | latest |
| Python | 3.11+ | - |

## Commands

```bash
# 环境初始化
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 开发
uvicorn src.api.main:app --reload --port 8000    # 启动后端
streamlit run src/frontend/app.py                  # 启动前端

# 测试
pytest                                          # 运行所有测试
pytest tests/unit/                              # 只跑单元测试
pytest tests/integration/                       # 只跑集成测试
pytest --cov=src --cov-report=term-missing       # 带覆盖率

# 代码检查
ruff check src/                                 # lint
ruff format src/                                # format
```

## Project Structure

```
ByteDance-AI-Full-Stack-Challenge/
├── SPEC.md                     # 本文件：技术规格
├── PROGRESS.md                 # 进度日志
├── DECISIONS.md                # 技术决策记录
├── CLAUDE.md                   # AI 协作指令
├── docs/
│   ├── PRD.md                  # 产品需求文档
│   └── competition-materials/  # 赛题材料
├── src/
│   ├── __init__.py
│   ├── api/                    # FastAPI 后端
│   │   ├── __init__.py
│   │   ├── main.py             # FastAPI app 入口
│   │   ├── routes.py           # API 路由
│   │   └── schemas.py          # 请求/响应 Pydantic 模型
│   ├── agents/                 # Agent 定义
│   │   ├── __init__.py
│   │   ├── collector.py        # 采集 Agent（目标解析+竞品分类+差异化采集）
│   │   ├── analyzer.py         # 分析 Agent（四维框架+SWOT+雷达评分）
│   │   ├── writer.py           # 撰写 Agent（四段式摘要+时间分层建议）
│   │   ├── inspector.py        # 质检 Agent（Schema 校验+溯源检查）
│   │   └── prompts.py          # 所有 Agent 的 Prompt 模板
│   ├── graph/                  # LangGraph 编排
│   │   ├── __init__.py
│   │   ├── state.py            # AnalysisState TypedDict 定义
│   │   └── builder.py          # StateGraph 构建（节点+边+条件路由）
│   ├── tools/                  # Agent 工具
│   │   ├── __init__.py
│   │   ├── http_client.py      # httpx 封装（异步请求+超时+重试）
│   │   ├── html_parser.py      # BeautifulSoup 封装
│   │   ├── llm_client.py       # Doubao LLM 客户端（OpenAI 兼容）
│   │   └── validators.py       # Schema 校验器 + URL 校验器
│   ├── schemas/                # 数据 Schema 定义
│   │   ├── __init__.py
│   │   ├── input.py            # CompetitorInput, CompetitorBasic, AnalysisGoal
│   │   ├── profile.py          # CompetitorProfile
│   │   ├── analysis.py         # CompetitiveAnalysis
│   │   ├── report.py           # FinalReport
│   │   └── feedback.py         # RejectionFeedback, AgentMessage
│   ├── frontend/               # Streamlit 前端
│   │   ├── __init__.py
│   │   └── app.py              # Streamlit 入口
│   └── utils/                  # 通用工具
│       ├── __init__.py
│       ├── logger.py           # 结构化日志
│       └── config.py           # 配置管理（API key、模型 endpoint 等）
├── tests/
│   ├── __init__.py
│   ├── unit/                   # 单元测试
│   │   ├── test_schemas.py     # Schema 校验测试
│   │   ├── test_collector.py   # 采集 Agent 测试
│   │   ├── test_analyzer.py    # 分析 Agent 测试
│   │   ├── test_writer.py      # 撰写 Agent 测试
│   │   └── test_inspector.py   # 质检 Agent 测试
│   └── integration/            # 集成测试
│       ├── test_graph.py       # 完整图运行测试
│       └── test_api.py         # API 端点测试
├── logs/                       # 运行日志（gitignore）
├── requirements.txt
├── .gitignore
└── .env.example                # 环境变量模板
```

## Code Style

**核心原则**：代码英文命名，注释中文，Schema 严格类型化。

```python
from pydantic import BaseModel, Field
from typing import Literal

class CompetitorBasic(BaseModel):
    """竞品基础信息（用户输入）"""
    name: str = Field(..., min_length=2, max_length=50, description="竞品名称")
    company: str = Field(default="", description="所属公司（选填，系统可推断）")
    category: str = Field(default="", description="行业分类（选填，系统可推断）")

class AnalysisGoal(BaseModel):
    """解析后的分析目标"""
    goal_type: Literal[
        "feature_iteration", "pricing_strategy",
        "market_entry", "competitive_monitoring"
    ] = "competitive_monitoring"
    product_stage: Literal["entering", "growing", "mature"] = "growing"
    focus_area: str = ""
    output_expectation: Literal["info", "knowledge", "action"] = "action"

class SourceReference(BaseModel):
    """单条溯源引用"""
    claim: str = Field(..., description="结论内容")
    source_type: Literal["app_store", "official_site", "media", "social"] = "official_site"
    source_url: str = Field(..., description="原始链接")
    snippet: str = Field(default="", description="原文片段")
    collected_at: str = Field(..., description="采集时间 ISO 8601")
```

**命名规范**：
- 文件名：`snake_case.py`
- 类名：`PascalCase`
- 函数/变量：`snake_case`
- 常量：`UPPER_SNAKE_CASE`
- Agent 函数：`{role}_agent`（如 `collector_agent`）

**日志规范**：
```python
import logging
logger = logging.getLogger(__name__)

# 每个 Agent 入口/出口打日志
logger.info("[collector] 开始采集, competitors=%d", len(competitors))
logger.info("[collector] 采集完成, profiles=%d,耗时=%.1fs", len(profiles), elapsed)
```

## Testing Strategy

| 测试层级 | 范围 | 工具 | 覆盖率目标 |
|----------|------|------|-----------|
| 单元测试 | Schema 校验、工具函数、单个 Agent 逻辑 | pytest | ≥ 80% |
| 集成测试 | LangGraph 完整图运行、API 端点 | pytest + httpx.AsyncClient | 核心链路 100% |

**测试重点**：
- `test_schemas.py`：验证所有 Schema 的校验规则（必填字段、类型约束、边界值）
- `test_collector.py`：Mock HTTP 响应，验证采集逻辑和降级策略
- `test_inspector.py`：构造缺陷报告，验证质检能识别并打回
- `test_graph.py`：端到端运行完整图（Mock LLM），验证反馈闭环

**Mock 策略**：
- LLM 调用：使用 `unittest.mock.patch` 或 `pytest-httpx` mock HTTP 响应
- 网页采集：使用本地 HTML fixture 文件，不依赖真实网络
- 集成测试中可选择性跳过网络测试（`@pytest.mark.skipif`）

## Boundaries

### Always
- 每个 Agent 的输入输出使用 Pydantic 模型，不用裸 dict
- LLM 调用必须有超时设置（30s）和重试逻辑（最多 2 次）
- 所有 Agent 间消息通过 LangGraph State 传递，不使用全局变量
- 日志记录每个 Agent 的输入/输出摘要和耗时
- 采集请求遵守 robots.txt 和频率控制（同域名间隔 ≥ 2s）
- Schema 校验失败时返回明确的错误信息，不静默吞掉

### Ask first
- 新增 Python 依赖包
- 修改 LangGraph 的图结构（增删节点或边）
- 修改 Schema 的字段定义（影响所有下游 Agent）
- 调整质检打回的 max_retries 值
- 添加新的数据源

### Never
- 提交 .env 文件或 API key 到 Git
- 在代码中硬编码 Doubao API key 或 endpoint
- 跳过 Schema 校验直接传递数据
- 使用 `print()` 替代 `logging`
- 删除测试用例来让 CI 通过
- 在 Agent 内部直接操作其他 Agent 的状态（必须通过 State 传递）

## 已确认决策

1. **Doubao 结构化输出**：支持 JSON mode，使用 `response_format={"type": "json_object"}` 约束 LLM 输出
2. **数据源采集策略**：应用商店（App Store/应用宝）用 URL 模板直接拼接搜索地址；媒体/社交源（36氪/虎嗅/微博等）通过搜索获取结果 URL
3. **流式进度展示**：需要实现。LangGraph streaming + Streamlit 实时更新，展示当前 Agent 阶段和进度

## Open Questions

（暂无）
