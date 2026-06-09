# 前端美化 + 报告导出 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不动 graph 拓扑 / agent 核心 / schema 主结构的前提下，给 Streamlit 前端注入 Data-Dense Dashboard 主题色 + KPI 5 卡 + Section/Action 卡片化，并新增 Markdown / HTML 双格式报告导出（HTML 全内嵌字体+Plotly+nh3 sanitize）。

**Architecture:** 3 个新文件（`src/frontend/theme.py` / `src/api/exporters/markdown.py` / `src/api/exporters/html.py`）+ 6 个改文件（`schemas/report.py` / `agents/inspector.py` / `frontend/app.py` / `frontend/render.py` / `api/routes.py` / `requirements.txt`）。前端通过 CSS `<style>` 注入主题；导出走 `GET /api/v1/trace/{trace_id}/export?format=md|html`，Jinja2 模板渲染 + nh3 sanitize narrative。

**Tech Stack:** Python 3.14 / Streamlit 1.35+ / FastAPI / Pydantic v2 / Jinja2 / markdown / nh3 / Plotly。

---

## File Structure

```
src/
├── frontend/
│   ├── app.py              # 改：注入 theme + 调 render_analysis_response 时传 trace_id
│   ├── render.py           # 改：加 _render_kpi_strip / _render_export_buttons；section/action 卡片化；emoji 局部纯化
│   └── theme.py            # 新：inject_theme() + icon() + CSS 常量
├── api/
│   ├── routes.py           # 改：加 export_trace 路由
│   └── exporters/
│       ├── __init__.py     # 新：包标识
│       ├── markdown.py     # 新：render_markdown(report, trace_id) + _render_sN_md ×5
│       ├── html.py         # 新：render_html(report, trace_id) + _safe_markdown + Plotly 内嵌
│       ├── templates/
│       │   └── report.html.j2   # 新：HTML 模板
│       └── fonts/
│           ├── PlusJakartaSans-Regular.woff2   # 新：字体文件（构建时下载）
│           ├── PlusJakartaSans-Bold.woff2
│           └── FiraCode-Regular.woff2
├── schemas/
│   └── report.py           # 改：ReportMetadata 加 raw_quality_score 字段
└── agents/
    └── inspector.py        # 改：cap 前回填 raw_quality_score（5-6 行）

tests/
├── unit/
│   ├── test_inspector_raw_quality_score.py   # 新
│   ├── test_exporters_markdown.py            # 新
│   ├── test_exporters_html.py                # 新
│   ├── test_exporters_html_xss.py            # 新（C5 stored XSS 防护）
│   ├── test_export_path_traversal.py         # 新（路径穿越防护）
│   └── test_emoji_lint.py                    # 新（PD-5 选择性纯化白名单）
└── integration/
    └── test_export_e2e.py                    # 新

requirements.txt            # 改：加 markdown / jinja2 / nh3
```

---

## Task 1: ReportMetadata 加 raw_quality_score 字段（schema 改动）

**Files:**
- Modify: `src/schemas/report.py:121`
- Test: `tests/unit/test_schemas.py`（已存在并 module-level skip，不动；本字段单测在 Task 2 一起测）

- [ ] **Step 1: 修改 `src/schemas/report.py:121` 之后插入新字段**

打开 `src/schemas/report.py`，在 `quality_score` 字段（第 121 行）之后、`quality_score_calculation_note` 之前插入：

```python
    quality_score: Optional[float] = Field(default=None, ge=0, le=1)
    raw_quality_score: Optional[float] = Field(
        default=None,
        ge=0,
        le=1,
        description=(
            "cap 前的初始加权分（含 placeholder pass_rate 影响）。"
            "用于 KPI 卡显示模型实际算分。命名 raw 仅指 cap 前，"
            "不代表完全无任何惩罚——v3-R17 cap 仅是惩罚之一。"
        ),
    )
    quality_score_calculation_note: str = Field(default="")
```

- [ ] **Step 2: 运行已有测试确认无回归**

```bash
pytest tests/unit/ -x -q 2>&1 | tail -5
```

Expected: 既有测试全过（387 passed），无新增失败。

- [ ] **Step 3: ruff 检查**

```bash
ruff check src/schemas/report.py
```

Expected: All checks passed.

- [ ] **Step 4: Commit**

```bash
git add src/schemas/report.py
git commit -m "feat(schema): ReportMetadata 加 raw_quality_score 字段（PD-3 KPI 显示用）"
```

---

## Task 2: inspector cap 前回填 raw_quality_score

**Files:**
- Modify: `src/agents/inspector.py:387-393`
- Test: `tests/unit/test_inspector_raw_quality_score.py`

- [ ] **Step 1: 写失败测试 `tests/unit/test_inspector_raw_quality_score.py`**

```python
"""验证 inspector 在 cap 前后均正确写入 raw_quality_score 与 quality_score。"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock

from src.agents.inspector import InspectorAgent
from src.schemas.feedback import FeedbackIssue


@pytest.fixture
def inspector(monkeypatch):
    """构造 InspectorAgent，mock LLM 调用。"""
    llm = AsyncMock()
    llm.call_json = AsyncMock(return_value={"issues": []})  # 无 LLM issues
    return InspectorAgent(llm=llm)


def _make_minimal_report(*, with_placeholder: bool):
    """构造满足 schema 但内容简单的 BaseReport，可选附 placeholder warning。"""
    from tests.fixtures.minimal_report import build_minimal_report  # 复用 G1 E2E fixture
    rep = build_minimal_report()
    if with_placeholder:
        rep.metadata.warnings.append("placeholder_section: vendor_profiles")
    return rep


@pytest.mark.asyncio
async def test_raw_quality_score_no_placeholder(inspector):
    """无 placeholder 时 raw_quality_score == quality_score。"""
    report = _make_minimal_report(with_placeholder=False)
    feedback = await inspector.inspect(report=report, retry_count=0, max_retries=2)

    assert report.metadata.raw_quality_score is not None
    assert report.metadata.quality_score is not None
    assert report.metadata.raw_quality_score == report.metadata.quality_score
    assert "capped" not in (report.metadata.quality_score_calculation_note or "")


@pytest.mark.asyncio
async def test_raw_quality_score_with_placeholder_caps_only_final(inspector):
    """有 placeholder 时 raw_quality_score 保留 cap 前真实分；quality_score 被 cap 到 0.5。"""
    report = _make_minimal_report(with_placeholder=True)
    feedback = await inspector.inspect(report=report, retry_count=0, max_retries=2)

    raw = report.metadata.raw_quality_score
    final = report.metadata.quality_score
    assert raw is not None and final is not None
    # raw 是 cap 前；final 应 ≤ raw（cap 触发时 final == 0.5）
    assert final <= raw
    if raw > 0.5:
        assert final == 0.5
        assert "capped" in (report.metadata.quality_score_calculation_note or "")
```

如果 `tests/fixtures/minimal_report.py` 不存在，先看 `tests/integration/test_graph.py` G1 fixture 的写法复用（已经有最小 BaseReport fixture）；如果 G1 fixture 不能直接 import，在测试文件顶部本地构造一个最小 report。具体可参考 `tests/integration/test_graph.py` 现有用法。

- [ ] **Step 2: 跑测试确认 fail**

```bash
pytest tests/unit/test_inspector_raw_quality_score.py -v
```

Expected: FAIL（`raw_quality_score` 字段当前 inspector 不写入，永远 None）。

- [ ] **Step 3: 改 `src/agents/inspector.py:387-393`**

把当前代码：
```python
        # 回填 quality_score（v3-R22 inspector 一次性写入）
        score, note = calc_quality_score(report, unique_issues)
        # v3-R17：placeholder warnings 强制 cap 到 0.5
        if _detect_placeholder_warnings(report) and score > _QUALITY_SCORE_CAP_ON_PLACEHOLDER:
            note = f"{note}; capped to {_QUALITY_SCORE_CAP_ON_PLACEHOLDER} due to placeholder warnings (v3-R17)"
            score = _QUALITY_SCORE_CAP_ON_PLACEHOLDER
        report.metadata.quality_score = score
        report.metadata.quality_score_calculation_note = note
```

替换为：
```python
        # 回填 quality_score（v3-R22 inspector 一次性写入）
        score, note = calc_quality_score(report, unique_issues)
        report.metadata.raw_quality_score = score  # PD-3：保留 cap 前真实分供 KPI 显示
        # v3-R17：placeholder warnings 强制 cap 到 0.5
        if _detect_placeholder_warnings(report) and score > _QUALITY_SCORE_CAP_ON_PLACEHOLDER:
            note = f"{note}; capped to {_QUALITY_SCORE_CAP_ON_PLACEHOLDER} due to placeholder warnings (v3-R17)"
            score = _QUALITY_SCORE_CAP_ON_PLACEHOLDER
        report.metadata.quality_score = score
        report.metadata.quality_score_calculation_note = note
```

- [ ] **Step 4: 跑测试确认 PASS**

```bash
pytest tests/unit/test_inspector_raw_quality_score.py -v
```

Expected: 2 passed.

- [ ] **Step 5: 跑全套 inspector 测试确认无回归**

```bash
pytest tests/unit/test_inspector.py -q
```

Expected: 全过。

- [ ] **Step 6: Commit**

```bash
git add src/agents/inspector.py tests/unit/test_inspector_raw_quality_score.py
git commit -m "feat(inspector): cap 前回填 raw_quality_score（PD-3 KPI 显示真实分）"
```

---

## Task 3: requirements.txt 加 markdown / jinja2 / nh3

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: 改 `requirements.txt`，在文件末尾加 3 行**

把：
```
plotly>=5.20.0
httpx>=0.27.0
beautifulsoup4>=4.12.0
pydantic>=2.7.0
python-dotenv>=1.0.0
pytest>=8.2.0
pytest-asyncio>=0.23.0
pytest-httpx>=0.30.0
ruff>=0.4.0
```

改为：
```
plotly>=5.20.0
httpx>=0.27.0
beautifulsoup4>=4.12.0
pydantic>=2.7.0
python-dotenv>=1.0.0
markdown>=3.6
jinja2>=3.1
nh3>=0.2
pytest>=8.2.0
pytest-asyncio>=0.23.0
pytest-httpx>=0.30.0
ruff>=0.4.0
```

- [ ] **Step 2: 在当前 venv 安装新依赖**

```bash
.\venv\Scripts\pip install markdown jinja2 nh3
```

Expected: 三个包全部成功安装（nh3 在 Windows 有 pre-built wheel）。

- [ ] **Step 3: 验证 import 可用**

```bash
.\venv\Scripts\python -c "import markdown, jinja2, nh3; print(markdown.__version__, jinja2.__version__, nh3.__version__)"
```

Expected: 三个版本号正常输出。

- [ ] **Step 4: Commit**

```bash
git add requirements.txt
git commit -m "feat: 加 markdown / jinja2 / nh3 依赖（HTML 导出 + XSS 防护）"
```

---

## Task 4: theme.py 主题系统基础

**Files:**
- Create: `src/frontend/theme.py`

- [ ] **Step 1: 创建 `src/frontend/theme.py`**

```python
"""前端主题系统：CSS 变量 + 字体 + Material Symbols 注入 + icon() 助手。

只在 app.py 顶部 st.set_page_config() 之后调用 inject_theme() 一次。
图标通过 icon(name, size, color) 助手生成 HTML 字符串，传给
st.markdown(..., unsafe_allow_html=True) 渲染。
"""
from __future__ import annotations

import streamlit as st

# Data-Dense Dashboard 颜色令牌（与 HTML 导出 CSS 同源）
COLOR_PRIMARY = "#1E40AF"
COLOR_PRIMARY_HOVER = "#1E3A8A"
COLOR_SECONDARY = "#3B82F6"
COLOR_ACCENT = "#D97706"
COLOR_BG = "#F8FAFC"
COLOR_SURFACE = "#FFFFFF"
COLOR_TEXT = "#0F172A"
COLOR_TEXT_SECONDARY = "#475569"
COLOR_MUTED = "#E9EEF6"
COLOR_BORDER = "#DBEAFE"
COLOR_DANGER = "#DC2626"
COLOR_SUCCESS = "#16A34A"
COLOR_WARNING = "#D97706"

_THEME_CSS = """
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&family=Fira+Code&display=swap" rel="stylesheet">
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined" rel="stylesheet">
<style>
:root {
  --color-primary: #1E40AF;
  --color-primary-hover: #1E3A8A;
  --color-secondary: #3B82F6;
  --color-accent: #D97706;
  --color-bg: #F8FAFC;
  --color-surface: #FFFFFF;
  --color-text: #0F172A;
  --color-text-secondary: #475569;
  --color-muted: #E9EEF6;
  --color-border: #DBEAFE;
  --color-danger: #DC2626;
  --color-success: #16A34A;
  --color-warning: #D97706;
  --radius: 8px;
  --shadow-card: 0 1px 3px rgba(15, 23, 42, 0.08), 0 1px 2px rgba(15, 23, 42, 0.04);
  --transition: all 150ms cubic-bezier(0.4, 0, 0.2, 1);
}

html, body, [class*="css"] {
  font-family: 'Plus Jakarta Sans', -apple-system, 'Segoe UI', system-ui, sans-serif;
  color: var(--color-text);
}

/* 主背景色 */
.stApp { background-color: var(--color-bg); }

/* 数字字体 */
.kpi-num, .num { font-family: 'Fira Code', 'Cascadia Code', Consolas, monospace; }

/* KPI 卡片 */
.kpi-card {
  background: var(--color-surface);
  padding: 16px;
  border-radius: var(--radius);
  box-shadow: var(--shadow-card);
  border-left: 3px solid var(--color-primary);
}
.kpi-card-label { font-size: 12px; color: var(--color-text-secondary); margin-bottom: 4px; }
.kpi-card-main { font-size: 28px; font-weight: 600; color: var(--color-primary); }
.kpi-card-sub { font-size: 12px; color: var(--color-text-secondary); margin-top: 4px; }

/* Section 卡片 */
.section-card {
  background: var(--color-surface);
  margin: 16px 0;
  padding: 20px;
  border-left: 4px solid var(--color-primary);
  border-radius: var(--radius);
  box-shadow: var(--shadow-card);
}

/* Action 卡片 */
.action-card {
  background: var(--color-surface);
  padding: 16px;
  border-radius: var(--radius);
  border-left: 4px solid var(--color-accent);
  box-shadow: var(--shadow-card);
  margin-bottom: 12px;
}
.action-card.priority-critical { border-left-color: var(--color-danger); }
.action-card.priority-important { border-left-color: var(--color-warning); }
.action-card.priority-consider { border-left-color: var(--color-primary); }

/* 导出按钮 */
.btn-export {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  background: var(--color-primary);
  color: white !important;
  border-radius: var(--radius);
  text-decoration: none;
  font-size: 14px;
  margin-right: 8px;
  transition: var(--transition);
}
.btn-export:hover {
  background: var(--color-primary-hover);
  color: white !important;
  text-decoration: none;
}

/* Material Symbols 默认配置 */
.material-symbols-outlined {
  font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24;
  vertical-align: middle;
}

/* Streamlit primary button 主色 */
.stButton > button[kind="primary"] {
  background-color: var(--color-primary);
  border-color: var(--color-primary);
}
.stButton > button[kind="primary"]:hover {
  background-color: var(--color-primary-hover);
  border-color: var(--color-primary-hover);
}
</style>
"""


def inject_theme() -> None:
    """注入主题 CSS + 字体 + Material Symbols。仅 app.py 顶部调用一次。"""
    st.markdown(_THEME_CSS, unsafe_allow_html=True)


def icon(name: str, size: int = 20, color: str | None = None) -> str:
    """渲染 Material Symbol 字体图标，返回 HTML 字符串。

    用法：st.markdown(f"{icon('analytics')} 报告标题", unsafe_allow_html=True)
    图标列表：https://fonts.google.com/icons
    """
    style = f"font-size:{size}px"
    if color:
        style += f";color:{color}"
    return f'<span class="material-symbols-outlined" style="{style}">{name}</span>'
```

- [ ] **Step 2: 验证 import 不崩**

```bash
.\venv\Scripts\python -c "from src.frontend.theme import inject_theme, icon; print(icon('analytics'))"
```

Expected: 输出 `<span class="material-symbols-outlined" style="font-size:20px">analytics</span>`。

- [ ] **Step 3: ruff 检查**

```bash
ruff check src/frontend/theme.py
```

Expected: All checks passed.

- [ ] **Step 4: Commit**

```bash
git add src/frontend/theme.py
git commit -m "feat(frontend): theme.py 主题系统（CSS + 字体 + Material Symbols + icon helper）"
```

---

## Task 5: app.py 调 inject_theme + 修 import 路径

**Files:**
- Modify: `src/frontend/app.py:1-9`

- [ ] **Step 1: 修改 `src/frontend/app.py` 顶部 import + page_config 之后**

把：
```python
import streamlit as st
import httpx

from render import render_analysis_response, render_trace_report_tab

API_BASE = "http://localhost:8000/api/v1"

st.set_page_config(page_title="竞品分析 Agent 系统", layout="wide")
st.title("竞品分析 Agent 系统")
```

替换为：
```python
import streamlit as st
import httpx

from render import render_analysis_response, render_trace_report_tab
from theme import inject_theme

API_BASE = "http://localhost:8000/api/v1"

st.set_page_config(
    page_title="AI 驱动竞品分析系统",
    page_icon=":material/analytics:",
    layout="wide",
)
inject_theme()

st.title("AI 驱动竞品分析系统")
st.caption("多 Agent 协作 · 5 场景专业报告 · 全链路可追溯")
```

> 注：`from theme import inject_theme`（不是 `from src.frontend.theme import ...`）—— 因为 `streamlit run src/frontend/app.py` 启动时把 `src/frontend/` 加入 sys.path（C1 修复点）。

- [ ] **Step 2: 启动后端 + 前端验证**

后端：
```bash
.\venv\Scripts\uvicorn src.api.main:app --reload
```

前端（另一终端）：
```bash
.\venv\Scripts\streamlit run src\frontend\app.py
```

打开浏览器：
- 标题"AI 驱动竞品分析系统"应是深蓝色（`#1E40AF`）
- 背景应是浅灰（`#F8FAFC`）
- 字体应是 Plus Jakarta Sans

如果字体没生效（仍 Streamlit 默认 Source Sans Pro），打开浏览器开发者工具看 Network 是否有 `fonts.googleapis.com` 加载成功。

- [ ] **Step 3: Commit**

```bash
git add src/frontend/app.py
git commit -m "feat(frontend): 注入主题 + 修页签标题"
```

---

## Task 6: render.py 改 render_base_report 签名 + render_analysis_response 调用处

**Files:**
- Modify: `src/frontend/render.py:1074-1108`（`render_analysis_response` 函数）
- Modify: `src/frontend/render.py:1111-1122`（`render_trace_report_tab` 函数）
- Modify: `src/frontend/render.py:1125-1166`（`render_base_report` 函数）
- Modify: `src/frontend/app.py:170`（调用处补传 trace_id）

- [ ] **Step 1: 改 `render_base_report` 签名加 trace_id 参数**

打开 `src/frontend/render.py`，定位 `def render_base_report(report: dict) -> None:`（约第 1125 行）：

把：
```python
def render_base_report(report: dict) -> None:
    """主入口：按 BaseReport schema 顺序渲染。"""
    if not report:
        st.warning("报告为空")
        return

    title = report.get("title", "")
    subtitle = report.get("subtitle", "")
    if title:
        st.title(title)
    if subtitle:
        st.caption(subtitle)
```

替换为：
```python
def render_base_report(report: dict, *, trace_id: str | None = None) -> None:
    """主入口：按 BaseReport schema 顺序渲染。

    trace_id 不为空时顶部显示导出双按钮（Markdown / HTML）+ KPI 5 卡。
    """
    if not report:
        st.warning("报告为空")
        return

    if trace_id:
        _render_export_buttons(trace_id)
    _render_kpi_strip(report)

    title = report.get("title", "")
    subtitle = report.get("subtitle", "")
    if title:
        st.title(title)
    if subtitle:
        st.caption(subtitle)
```

> 注：`_render_export_buttons` 在 Task 8 实现，`_render_kpi_strip` 在 Task 7 实现。本 task 暂时占位空函数避免 import 报错。

在 `render_base_report` 函数定义之前加占位（具体实现在 Task 7-8 替换）：
```python
def _render_export_buttons(trace_id: str) -> None:
    """占位，Task 8 实现真实双按钮。"""
    pass


def _render_kpi_strip(report: dict) -> None:
    """占位，Task 7 实现 5 张 KPI 卡。"""
    pass
```

- [ ] **Step 2: 改 `render_analysis_response` 调 render_base_report 时传 trace_id**

定位约第 1108 行 `render_base_report(report)`，改为：
```python
    render_base_report(report, trace_id=trace_id)
```

- [ ] **Step 3: 改 `render_trace_report_tab` 签名加 trace_id**

把：
```python
def render_trace_report_tab(report: dict | None) -> None:
    """[fix16] 追溯面板「报告」tab 用：渲染历史 trace 的美化报告 + 折叠原始 JSON。"""
    if not report:
        st.warning("该 trace 报告为空（可能 graph 失败强制结束 / 未跑到 writer 阶段）")
        return
    render_base_report(report)
    with st.expander("查看原始 JSON（诊断用）", expanded=False):
        st.json(report)
```

替换为：
```python
def render_trace_report_tab(report: dict | None, *, trace_id: str | None = None) -> None:
    """[fix16] 追溯面板「报告」tab 用：渲染历史 trace 的美化报告 + 折叠原始 JSON。

    trace_id 不为空时顶部显示导出双按钮。
    """
    if not report:
        st.warning("该 trace 报告为空（可能 graph 失败强制结束 / 未跑到 writer 阶段）")
        return
    render_base_report(report, trace_id=trace_id)
    with st.expander("查看原始 JSON（诊断用）", expanded=False):
        st.json(report)
```

- [ ] **Step 4: 改 `src/frontend/app.py:170` 调用处**

定位 `app.py` 第 170 行 `render_trace_report_tab(t["stages"].get("report"))`，改为：
```python
                    render_trace_report_tab(t["stages"].get("report"), trace_id=tid_input)
```

- [ ] **Step 5: 启动前端验证不崩**

```bash
.\venv\Scripts\streamlit run src\frontend\app.py
```

打开浏览器，跑一次分析或加载历史 trace；当前 KPI 条 + 导出按钮还是空的（占位），但应不报错。

- [ ] **Step 6: Commit**

```bash
git add src/frontend/render.py src/frontend/app.py
git commit -m "refactor(frontend): render_base_report/render_trace_report_tab 签名加 trace_id（M1-M2 准备）"
```

---

## Task 7: render.py KPI 5 卡

**Files:**
- Modify: `src/frontend/render.py`（替换 `_render_kpi_strip` 占位）

- [ ] **Step 1: 替换 `_render_kpi_strip` 为真实实现**

把上一 task 的占位：
```python
def _render_kpi_strip(report: dict) -> None:
    """占位，Task 7 实现 5 张 KPI 卡。"""
    pass
```

替换为：
```python
_SCENARIO_LABELS = {
    "S1": "功能迭代",
    "S2": "市场进入",
    "S3": "定价策略",
    "S4": "持续监控",
    "S5": "战略定位",
}


def _format_quality_score(meta: dict) -> tuple[str, str]:
    """返回 (主数字, 副信息) 元组。

    优先 raw_quality_score，回退 quality_score；皆无显「未质检」。
    note 含 capped 时副信息显示 cap 后真实值。
    """
    raw = meta.get("raw_quality_score")
    final = meta.get("quality_score")
    note = meta.get("quality_score_calculation_note") or ""

    if raw is not None:
        main = f"{raw:.3f}"
        if "capped" in note and final is not None and final < raw:
            sub = f"⚠ cap 后 {final:.2f}"
        else:
            sub = ""
    elif final is not None:
        main = f"{final:.3f}"
        sub = "（无 raw 字段）"
    else:
        main = "—"
        sub = "未质检"
    return main, sub


def _format_data_sources(meta: dict) -> tuple[str, str]:
    """KPI 数据源数 = 总数 + 三档分桶副信息。"""
    sources = meta.get("data_sources") or []
    total = len(sources)
    if total == 0:
        return "—", ""
    high = sum(1 for s in sources if (s.get("confidence") or "") == "high")
    mid = sum(1 for s in sources if (s.get("confidence") or "") == "medium")
    low = sum(1 for s in sources if (s.get("confidence") or "") == "low")
    return str(total), f"高 {high} 中 {mid} 低 {low}"


def _format_competitors(report: dict) -> tuple[str, str]:
    scope = report.get("scope") or {}
    comps = scope.get("competitors") or []
    total = len(comps)
    if total == 0:
        return "—", ""
    # S2 含 recommender 推荐：副信息提示
    payload = report.get("scenario_payload") or {}
    sub = ""
    if payload.get("scenario_type") == "S2":
        rec = payload.get("competitor_recommendations") or {}
        rec_list = rec.get("recommended_competitors") or []
        if rec_list:
            sub = f"含 {len(rec_list)} 推荐"
    return str(total), sub


def _confidence_color(level: str) -> str:
    return {
        "high": "#16A34A",
        "medium": "#D97706",
        "low": "#DC2626",
    }.get(level or "", "#475569")


def _render_kpi_strip(report: dict) -> None:
    """5 张 KPI 卡：质检评分 / 场景标签 / 竞品数量 / 数据源数 / 可信度。

    visualisation by st.columns(5) + st.markdown HTML（继承 theme.py 注入的 .kpi-card class）。
    """
    if not report:
        return
    meta = report.get("metadata") or {}

    qs_main, qs_sub = _format_quality_score(meta)
    scenario = meta.get("scenario") or "—"
    scenario_sub = _SCENARIO_LABELS.get(scenario, "")
    comp_main, comp_sub = _format_competitors(report)
    src_main, src_sub = _format_data_sources(meta)
    conf_level = meta.get("confidence_level") or "—"
    conf_color = _confidence_color(conf_level)

    cols = st.columns(5)
    cards = [
        (cols[0], "质检评分", qs_main, qs_sub, None),
        (cols[1], "场景标签", scenario, scenario_sub, None),
        (cols[2], "竞品数量", comp_main, comp_sub, None),
        (cols[3], "数据源数", src_main, src_sub, None),
        (cols[4], "可信度", conf_level, "", conf_color),
    ]
    for col, label, main, sub, color in cards:
        with col:
            color_attr = f"color:{color}" if color else ""
            st.markdown(
                f"""<div class="kpi-card">
  <div class="kpi-card-label">{label}</div>
  <div class="kpi-card-main kpi-num" style="{color_attr}">{main}</div>
  <div class="kpi-card-sub">{sub}</div>
</div>""",
                unsafe_allow_html=True,
            )
    st.markdown("")  # 空行间距
```

- [ ] **Step 2: 启动前端肉眼验证**

跑一次分析，看顶部应出现 5 张 KPI 卡：
- 质检评分（Fira Code 数字 + cap 提示如有）
- 场景标签 S3 + 中文副标
- 竞品数量
- 数据源数 + 三档分桶
- 可信度 high/medium/low + 染色

- [ ] **Step 3: Commit**

```bash
git add src/frontend/render.py
git commit -m "feat(frontend): KPI 5 卡（质检 / 场景 / 竞品 / 数据源 / 可信度）"
```

---

## Task 8: render.py 导出双按钮（直链）

**Files:**
- Modify: `src/frontend/render.py`（替换 `_render_export_buttons` 占位）

- [ ] **Step 1: 替换 `_render_export_buttons` 为真实实现**

把 Task 6 的占位：
```python
def _render_export_buttons(trace_id: str) -> None:
    """占位，Task 8 实现真实双按钮。"""
    pass
```

替换为：
```python
# API_BASE 与 app.py 同源；render.py 当前未 import，本 task 内联常量
_EXPORT_API_BASE = "http://localhost:8000/api/v1"


def _render_export_buttons(trace_id: str) -> None:
    """报告区顶部导出双按钮：直链 <a download>，浏览器原生触发下载。

    使用 HTML <a> 而非 st.download_button：
    - st.download_button 要求 data 已 materialized（不接受 lazy callable）
    - HTML <a download> 让浏览器直接调后端 GET /export 路由，零前端预拉
    """
    md_url = f"{_EXPORT_API_BASE}/trace/{trace_id}/export?format=md"
    html_url = f"{_EXPORT_API_BASE}/trace/{trace_id}/export?format=html"
    st.markdown(
        f"""<div style="margin-bottom:16px">
  <a href="{md_url}" download class="btn-export">
    <span class="material-symbols-outlined">download</span> 导出 Markdown
  </a>
  <a href="{html_url}" download class="btn-export">
    <span class="material-symbols-outlined">download</span> 导出 HTML
  </a>
  <span style="color:var(--color-text-secondary);font-size:12px;margin-left:12px">
    Trace: <code>{trace_id}</code>
  </span>
</div>""",
        unsafe_allow_html=True,
    )
```

- [ ] **Step 2: 启动前端验证按钮显示**

跑一次分析，看 KPI 卡上方应有【⬇ 导出 Markdown】【⬇ 导出 HTML】两个深蓝色按钮 + 右侧 Trace ID。**点击当前应该 404**——`/export` 路由还没实现（Task 13 会加），但按钮 hover 主色应该有平滑过渡。

- [ ] **Step 3: Commit**

```bash
git add src/frontend/render.py
git commit -m "feat(frontend): 导出双按钮（直链 a download，待 Task 13 后端路由就绪）"
```

---

## Task 9: render.py Section 卡片化 + 主色剩头

**Files:**
- Modify: `src/frontend/render.py:279-288`（`_render_analysis_sections` 函数）

- [ ] **Step 1: 改 `_render_analysis_sections`**

把：
```python
def _render_analysis_sections(sections: list[dict]) -> None:
    if not sections:
        return
    st.header("详细章节")
    for sec in sections:
        st.subheader(sec.get("heading", ""))
        st.caption(f"section_type: `{sec.get('section_type', '')}`")
        st.markdown(sec.get("narrative", ""))
        _render_source_refs(sec.get("source_refs"))
```

替换为：
```python
def _render_analysis_sections(sections: list[dict]) -> None:
    if not sections:
        return
    st.header("详细章节")
    for sec in sections:
        # 用 markdown HTML 包成 .section-card 应用主色剩头 + 浅色背景
        heading = sec.get("heading", "")
        section_type = sec.get("section_type", "")
        narrative = sec.get("narrative", "") or ""
        st.markdown(
            f"""<div class="section-card">
  <h3 style="margin-top:0;color:var(--color-primary)">{heading}</h3>
  <small style="color:var(--color-text-secondary)">section_type: <code>{section_type}</code></small>
</div>""",
            unsafe_allow_html=True,
        )
        # narrative 走 st.markdown 保留 markdown 渲染（不进 .section-card 内层避免 HTML 嵌套问题）
        st.markdown(narrative)
        _render_source_refs(sec.get("source_refs"))
```

- [ ] **Step 2: 启动前端验证**

跑一次分析，每个 detailed section 顶部应有主色 4px 左剩头 + 浅色背景卡片包裹标题；narrative 紧跟其下。

- [ ] **Step 3: Commit**

```bash
git add src/frontend/render.py
git commit -m "feat(frontend): section 卡片化（主色剩头 + 浅色背景）"
```

---

## Task 10: render.py Action Card grid

**Files:**
- Modify: `src/frontend/render.py:316-344`（`_render_recommendations` 函数）

- [ ] **Step 1: 改 `_render_recommendations`**

把：
```python
def _render_recommendations(recs: list[dict]) -> None:
    if not recs:
        return
    st.header("行动建议")
    timeline_groups: dict[str, list[dict]] = {"immediate": [], "short_term": [], "long_term": []}
    for r in recs:
        tl = r.get("timeline", "long_term")
        timeline_groups.setdefault(tl, []).append(r)
    for tl_key, tl_label in [
        ("immediate", "即时（1 个月内）"),
        ("short_term", "短期（3 个月内）"),
        ("long_term", "长期（6-12 个月）"),
    ]:
        items = timeline_groups.get(tl_key) or []
        if not items:
            continue
        st.subheader(tl_label)
        for r in items:
            priority = r.get("priority", "")
            target = r.get("target_role", "")
            action = r.get("action", "")
            rationale = r.get("rationale", "")
            badge = {"critical": "🔴", "important": "🟡", "consider": "🟢"}.get(priority, "")
            st.markdown(f"{badge} **[{priority}]** {action}")
            if target:
                st.caption(f"对象：{target}")
            if rationale:
                st.caption(f"依据：{rationale}")
            _render_source_refs(r.get("source_refs"))
```

替换为：
```python
def _render_recommendations(recs: list[dict]) -> None:
    if not recs:
        return
    st.header("行动建议")
    timeline_groups: dict[str, list[dict]] = {"immediate": [], "short_term": [], "long_term": []}
    for r in recs:
        tl = r.get("timeline", "long_term")
        timeline_groups.setdefault(tl, []).append(r)
    for tl_key, tl_label in [
        ("immediate", "即时（1 个月内）"),
        ("short_term", "短期（3 个月内）"),
        ("long_term", "长期（6-12 个月）"),
    ]:
        items = timeline_groups.get(tl_key) or []
        if not items:
            continue
        st.subheader(tl_label)
        # grid 布局：每行 2 张卡
        for i in range(0, len(items), 2):
            cols = st.columns(2)
            for col_idx, item_idx in enumerate(range(i, min(i + 2, len(items)))):
                r = items[item_idx]
                priority = r.get("priority", "")
                target = r.get("target_role", "")
                action = r.get("action", "")
                rationale = r.get("rationale", "")
                # 保留 PD-5 emoji 状态点（recommendations badge 在白名单内）
                badge = {"critical": "🔴", "important": "🟡", "consider": "🟢"}.get(priority, "")
                priority_class = f"priority-{priority}" if priority in ("critical", "important", "consider") else ""
                with cols[col_idx]:
                    refs = r.get("source_refs") or []
                    refs_html = ""
                    if refs:
                        parts = []
                        for ref in refs:
                            if isinstance(ref, dict):
                                url = ref.get("url", "")
                                title = ref.get("title", "") or "链接"
                                if url:
                                    parts.append(f'<a href="{url}" target="_blank">{title}</a>')
                        if parts:
                            refs_html = f'<small style="color:var(--color-text-secondary)">来源：{" · ".join(parts)}</small>'
                    st.markdown(
                        f"""<div class="action-card {priority_class}">
  <div style="font-size:14px;font-weight:600">{badge} [{priority}] {action}</div>
  {f'<small style="color:var(--color-text-secondary)">对象：{target}</small><br>' if target else ''}
  {f'<small style="color:var(--color-text-secondary)">依据：{rationale}</small><br>' if rationale else ''}
  {refs_html}
</div>""",
                        unsafe_allow_html=True,
                    )
```

- [ ] **Step 2: 启动前端验证**

跑一次产出 recommendations 的分析（如 S3 happy path），看行动建议区按 timeline 分 3 组，每组 2 列 grid 卡片，priority 对应主色/警告/危险左剩头。

- [ ] **Step 3: Commit**

```bash
git add src/frontend/render.py
git commit -m "feat(frontend): Action Card grid（timeline 分组 + 2 列 grid + priority 染色）"
```

---

## Task 11: 后端 exporters 包结构 + 字体文件

**Files:**
- Create: `src/api/exporters/__init__.py`
- Create: `src/api/exporters/fonts/.gitkeep`
- Create: `src/api/exporters/templates/.gitkeep`

- [ ] **Step 1: 创建包结构**

```bash
mkdir -p "src/api/exporters/fonts"
mkdir -p "src/api/exporters/templates"
```

Windows PowerShell：
```powershell
New-Item -ItemType Directory -Force -Path "src\api\exporters\fonts"
New-Item -ItemType Directory -Force -Path "src\api\exporters\templates"
```

- [ ] **Step 2: 创建 `src/api/exporters/__init__.py`**

```python
"""报告导出模块：BaseReport → markdown / html。

启动时校验字体文件存在（PD-4 全内嵌）。失败 raise 让导出立即报错而非运行时再炸。
"""
from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_FONTS_DIR = Path(__file__).parent / "fonts"
_REQUIRED_FONTS = [
    "PlusJakartaSans-Regular.woff2",
    "PlusJakartaSans-Bold.woff2",
    "FiraCode-Regular.woff2",
]


def check_fonts() -> None:
    """校验必需字体文件存在。开发阶段下载到 fonts/ 目录后调用。"""
    missing = [f for f in _REQUIRED_FONTS if not (_FONTS_DIR / f).is_file()]
    if missing:
        raise FileNotFoundError(
            f"导出 HTML 需要字体文件 {missing}，"
            f"请下载 woff2 放到 {_FONTS_DIR}。"
            f"下载源：https://fonts.google.com/specimen/Plus+Jakarta+Sans + Fira+Code"
        )
    logger.debug("[exporters] 字体文件全部就绪：%s", _REQUIRED_FONTS)
```

- [ ] **Step 3: 下载 3 个字体 woff2**

下载 Plus Jakarta Sans Regular + Bold 与 Fira Code Regular 的 woff2 字体文件，保存到 `src/api/exporters/fonts/`。

可用 Python 一行：
```bash
.\venv\Scripts\python -c "
import urllib.request
import os

# Google Fonts 静态资源链接（来自 fonts.googleapis.com 解析）
fonts = {
    'PlusJakartaSans-Regular.woff2': 'https://fonts.gstatic.com/s/plusjakartasans/v8/LDIbaomQNQcsA88c7O9yZ4KMCoOg4IA6-91aHEjcWuA_qU79TWFE-J4P.woff2',
    'PlusJakartaSans-Bold.woff2': 'https://fonts.gstatic.com/s/plusjakartasans/v8/LDIbaomQNQcsA88c7O9yZ4KMCoOg4IA6-91aHEjcWuA_KU09TWFE-J4P.woff2',
    'FiraCode-Regular.woff2': 'https://fonts.gstatic.com/s/firacode/v22/uU9eCBsR6Z2vfE9aq3bL0fxyUs4tcw4W_D1sJVD7MOzlojwUKQ.woff2',
}
for name, url in fonts.items():
    target = os.path.join('src', 'api', 'exporters', 'fonts', name)
    print(f'Downloading {name}...')
    urllib.request.urlretrieve(url, target)
    print(f'  → {target} ({os.path.getsize(target)} bytes)')
"
```

> 注：上述 gstatic 链接随版本变化，下载前先打开 https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;700&family=Fira+Code 看 `src: url(...)` 拿最新链接。如果 urlretrieve 拿到 0 字节或 HTML 错误页，手动浏览器下载。

校验：
```bash
ls -la "src/api/exporters/fonts/"
```

Expected: 3 个 .woff2 文件，每个 30-50KB。

- [ ] **Step 4: 验证 check_fonts 通过**

```bash
.\venv\Scripts\python -c "from src.api.exporters import check_fonts; check_fonts(); print('OK')"
```

Expected: 输出 `OK`。

- [ ] **Step 5: 删 .gitkeep 占位**

```bash
rm "src/api/exporters/fonts/.gitkeep" "src/api/exporters/templates/.gitkeep"
```

- [ ] **Step 6: Commit**

```bash
git add src/api/exporters/__init__.py src/api/exporters/fonts/*.woff2
git commit -m "feat(exporters): 包结构 + 3 字体文件 + check_fonts 校验"
```

> 注：fonts/ 下 woff2 是二进制资源，体积约 100KB，commit 进 repo 让评委 clone 即可跑。**不**走 git lfs。

---

## Task 12: exporters/markdown.py（5 场景常用字段）

**Files:**
- Create: `src/api/exporters/markdown.py`
- Test: `tests/unit/test_exporters_markdown.py`

- [ ] **Step 1: 写失败测试 `tests/unit/test_exporters_markdown.py`**

```python
"""验证 markdown 导出器：5 场景关键字段断言 + 不崩。"""
from __future__ import annotations

import pytest

from src.api.exporters.markdown import render_markdown


def _minimal_base_report(scenario: str, payload: dict) -> dict:
    """构造满足 markdown 渲染需要的最小 BaseReport dict。"""
    return {
        "title": f"{scenario} 测试报告",
        "subtitle": "单元测试用",
        "at_a_glance": ["要点 1", "要点 2"],
        "executive_summary": {
            "context": "背景上下文",
            "core_thesis": "核心论断",
            "key_findings_brief": ["finding A"],
            "implications": "现实启示",
            "path_forward": ["路径 1"],
        },
        "scope": {"competitors": ["A", "B"], "time_window": "2026"},
        "methodology": {"data_collection_approach": "搜 X 渠道"},
        "key_findings": [
            {"statement": "F1", "evidence": "E1", "implication": "I1", "source_refs": []},
        ],
        "analysis_sections": [
            {"heading": "分析章节 A", "section_type": "vendor_profiles", "narrative": "正文。", "source_refs": []},
        ],
        "swot": {
            "strengths": [{"point": "S1", "evidence": "E1", "source_refs": []}],
            "weaknesses": [], "opportunities": [], "threats": [],
        },
        "recommendations": [
            {"priority": "critical", "timeline": "immediate", "action": "做 X",
             "target_role": "产品", "rationale": "理由", "source_refs": []},
        ],
        "appendix": {"glossary": {}, "data_sources_full": []},
        "metadata": {
            "scenario": scenario,
            "raw_quality_score": 0.85,
            "quality_score": 0.85,
            "confidence_level": "high",
            "data_sources": [{"url": "https://example.com", "confidence": "high"}],
        },
        "scenario_payload": {**payload, "scenario_type": scenario},
    }


def test_markdown_s1_basic():
    """S1 场景：vendor_profiles + radar_scores 关键字段出现。"""
    rep = _minimal_base_report("S1", {
        "vendor_profiles": [
            {"competitor_name": "竞品A", "wave_position": "wave_leader",
             "one_line_pitch": "A 的卖点", "best_fit_for": "中型企业",
             "strengths": ["强 1", "强 2"], "cautions": ["注意 1"]},
        ],
        "radar_scores": [
            {"competitor_name": "竞品A", "feature_breadth": 4, "usability": 5,
             "cost_effectiveness": 3, "stability": 4, "design_quality": 4},
        ],
    })
    out = render_markdown(rep, trace_id="test-trace-001")

    # 顶部
    assert "# S1 测试报告" in out
    assert "test-trace-001" in out
    # at_a_glance
    assert "要点 1" in out
    # executive_summary
    assert "核心论断" in out
    # SWOT
    assert "S1" in out  # SWOT entry point S1
    # recommendations
    assert "做 X" in out
    # S1 payload
    assert "竞品A" in out
    assert "wave_leader" in out
    # 5 维评分（关键字段，PD-2）
    assert "feature_breadth" in out or "功能广度" in out


def test_markdown_s2_basic():
    """S2：market_sizing TAM/SAM/SOM + players。"""
    rep = _minimal_base_report("S2", {
        "market_sizing": {
            "tam": {"amount": 100, "unit": "亿", "currency": "USD", "value_basis": "industry_report"},
            "sam": {"amount": 30, "unit": "亿", "currency": "USD", "value_basis": "estimated"},
            "som": {"amount": 5, "unit": "亿", "currency": "USD", "value_basis": "inferred"},
        },
        "players": [
            {"name": "P1", "company": "公司 1", "market_role": "market_leader",
             "market_share_pct": 40, "key_differentiator": "差异化"},
        ],
    })
    out = render_markdown(rep, trace_id="t2")
    assert "TAM" in out and "SAM" in out and "SOM" in out
    assert "P1" in out
    assert "market_leader" in out


def test_markdown_s3_basic():
    """S3：packaging tiers 关键字段。"""
    rep = _minimal_base_report("S3", {
        "packaging": {
            "tiers": [
                {"name": "Basic", "position": "good", "monthly_price": 10,
                 "annual_price": 100, "currency": "USD", "is_recommended": False,
                 "target_persona": "个人", "included_features": ["F1"]},
                {"name": "Pro", "position": "better", "monthly_price": 30,
                 "annual_price": 300, "currency": "USD", "is_recommended": True,
                 "target_persona": "团队", "included_features": ["F1", "F2"]},
            ],
        },
    })
    out = render_markdown(rep, trace_id="t3")
    assert "Basic" in out and "Pro" in out
    assert "10" in out and "30" in out  # 月费


def test_markdown_s4_basic():
    """S4：feature_changes 关键字段。"""
    rep = _minimal_base_report("S4", {
        "review_period": {"review_period_label": "2026-Q1", "monitored_competitors": ["C1"]},
        "feature_changes": [
            {"competitor_name": "C1", "change_type": "new_feature",
             "fia": {"fact": "C1 上了新功能 X", "impact": "影响 Y", "act": "我们应该 Z"},
             "severity": "high"},
        ],
    })
    out = render_markdown(rep, trace_id="t4")
    assert "C1" in out
    assert "new_feature" in out or "功能变更" in out


def test_markdown_s5_basic():
    """S5：vendor_profiles + perceptual_map 关键字段。"""
    rep = _minimal_base_report("S5", {
        "vendor_profiles": [
            {"competitor_name": "V1", "ability_to_execute_score": 4,
             "completeness_of_vision_score": 3, "mq_quadrant": "challenger",
             "overview": "V1 概览"},
        ],
        "perceptual_map": {
            "x_axis": {"attribute": "价格", "low_label": "低端", "high_label": "高端", "scale_max": 5},
            "y_axis": {"attribute": "功能", "low_label": "简单", "high_label": "强大", "scale_max": 5},
            "plotted_brands": [
                {"competitor_name": "V1", "x_score": 4, "y_score": 3, "is_self": False,
                 "confidence": "high", "score_rationale": "依据 X"},
            ],
        },
    })
    out = render_markdown(rep, trace_id="t5")
    assert "V1" in out
    assert "challenger" in out
    assert "感知地图" in out or "Perceptual" in out or "perceptual_map" in out


def test_markdown_unknown_scenario_does_not_crash():
    """场景未知时仍能返回完整 markdown（不为空 + 含 title）。"""
    rep = _minimal_base_report("S99", {})
    out = render_markdown(rep, trace_id="t99")
    assert "# S99 测试报告" in out
    assert "test-trace" not in out  # trace_id 是 t99，不是 test-trace
    assert "t99" in out


def test_markdown_handles_missing_optional_fields():
    """部分 optional 字段缺失时不崩。"""
    minimal = {"title": "极简", "metadata": {"scenario": "S1"}}
    out = render_markdown(minimal, trace_id="t-min")
    assert "# 极简" in out
    assert "t-min" in out
```

- [ ] **Step 2: 跑测试确认 fail**

```bash
pytest tests/unit/test_exporters_markdown.py -v
```

Expected: ImportError —— `src.api.exporters.markdown` 还不存在。

- [ ] **Step 3: 创建 `src/api/exporters/markdown.py`**

```python
"""BaseReport → Markdown 导出器（PD-2 关键字段覆盖）。

策略：纯字符串拼接 + format 模板，零模板引擎依赖。
按 BaseReport schema 顺序输出；5 场景 payload 各有 _render_sN_md 函数。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Callable

_BEIJING = timezone(timedelta(hours=8))

_SCENARIO_NAMES = {
    "S1": "S1 功能迭代",
    "S2": "S2 市场进入",
    "S3": "S3 定价策略",
    "S4": "S4 持续监控",
    "S5": "S5 战略定位",
}


# ============ 公共骨架渲染 ============

def _render_at_a_glance(items: list) -> str:
    if not items:
        return ""
    lines = ["\n## 一图看懂\n"]
    for it in items:
        lines.append(f"- {it}")
    return "\n".join(lines)


def _render_executive_summary(es: dict) -> str:
    if not es:
        return ""
    lines = ["\n## 执行摘要"]
    for label, key in [("背景定位", "context"), ("核心论断", "core_thesis"),
                       ("现实启示", "implications")]:
        v = es.get(key)
        if v:
            lines.append(f"\n### {label}\n\n{v}")
    kfb = es.get("key_findings_brief") or []
    if kfb:
        lines.append("\n### 关键发现速览\n")
        for f in kfb:
            lines.append(f"- {f}")
    pf = es.get("path_forward") or []
    if pf:
        lines.append("\n### 行动路径\n")
        for p in pf:
            lines.append(f"- {p}")
    return "\n".join(lines)


def _render_scope(scope: dict) -> str:
    if not scope:
        return ""
    lines = ["\n## 分析范围\n"]
    comps = scope.get("competitors") or []
    if comps:
        lines.append(f"- 竞品：{', '.join(comps)}")
    tw = scope.get("time_window")
    if tw:
        lines.append(f"- 时间窗：{tw}")
    regions = scope.get("regions") or []
    if regions:
        lines.append(f"- 区域：{', '.join(regions)}")
    return "\n".join(lines)


def _render_methodology(meth: dict) -> str:
    if not meth:
        return ""
    lines = ["\n## 方法论\n"]
    approach = meth.get("data_collection_approach")
    if approach:
        lines.append(approach)
    ec = meth.get("evaluation_criteria") or []
    if ec:
        lines.append("\n**评估维度**：")
        for c in ec:
            lines.append(f"- {c}")
    lim = meth.get("limitations") or []
    if lim:
        lines.append("\n**已知局限**：")
        for l_ in lim:
            lines.append(f"- {l_}")
    return "\n".join(lines)


def _render_key_findings(findings: list) -> str:
    if not findings:
        return ""
    lines = ["\n## 关键发现\n"]
    for i, f in enumerate(findings, 1):
        lines.append(f"### Finding {i}")
        lines.append(f"\n{f.get('statement', '')}\n")
        if f.get("evidence"):
            lines.append(f"**依据**：{f['evidence']}")
        if f.get("implication"):
            lines.append(f"**启示**：{f['implication']}")
        refs = f.get("source_refs") or []
        if refs:
            lines.append(_format_source_refs(refs))
    return "\n".join(lines)


def _render_analysis_sections(sections: list) -> str:
    if not sections:
        return ""
    lines = ["\n## 详细章节\n"]
    for sec in sections:
        lines.append(f"### {sec.get('heading', '')}")
        st = sec.get("section_type", "")
        if st:
            lines.append(f"\n> section_type: `{st}`")
        nar = sec.get("narrative", "")
        if nar:
            lines.append(f"\n{nar}")
        refs = sec.get("source_refs") or []
        if refs:
            lines.append("\n" + _format_source_refs(refs))
    return "\n".join(lines)


def _render_swot(swot: dict) -> str:
    if not swot:
        return ""
    has_any = any(swot.get(k) for k in ("strengths", "weaknesses", "opportunities", "threats"))
    if not has_any:
        return ""
    lines = ["\n## SWOT 分析\n"]
    for key, label in [("strengths", "优势 S"), ("weaknesses", "劣势 W"),
                       ("opportunities", "机会 O"), ("threats", "威胁 T")]:
        entries = swot.get(key) or []
        if entries:
            lines.append(f"### {label}\n")
            for e in entries:
                lines.append(f"- **{e.get('point', '')}**")
                if e.get("evidence"):
                    lines.append(f"  - 依据：{e['evidence']}")
                refs = e.get("source_refs") or []
                if refs:
                    lines.append(f"  - {_format_source_refs(refs).strip()}")
    return "\n".join(lines)


def _render_recommendations(recs: list) -> str:
    if not recs:
        return ""
    lines = ["\n## 行动建议\n"]
    groups: dict[str, list] = {"immediate": [], "short_term": [], "long_term": []}
    for r in recs:
        groups.setdefault(r.get("timeline", "long_term"), []).append(r)
    for tl_key, tl_label in [("immediate", "即时（1 个月内）"),
                             ("short_term", "短期（3 个月内）"),
                             ("long_term", "长期（6-12 个月）")]:
        items = groups.get(tl_key) or []
        if not items:
            continue
        lines.append(f"### {tl_label}\n")
        for r in items:
            priority = r.get("priority", "")
            action = r.get("action", "")
            lines.append(f"#### [{priority}] {action}")
            if r.get("target_role"):
                lines.append(f"- 对象：{r['target_role']}")
            if r.get("rationale"):
                lines.append(f"- 依据：{r['rationale']}")
            refs = r.get("source_refs") or []
            if refs:
                lines.append(f"- {_format_source_refs(refs).strip()}")
    return "\n".join(lines)


def _render_appendix(appx: dict) -> str:
    if not appx:
        return ""
    glossary = appx.get("glossary") or {}
    sources = appx.get("data_sources_full") or []
    if not (glossary or sources):
        return ""
    lines = ["\n## 附录\n"]
    if glossary:
        lines.append("### 术语表\n")
        for term, defi in glossary.items():
            lines.append(f"- **{term}**：{defi}")
    if sources:
        lines.append("\n### 完整数据来源\n")
        for ds in sources:
            url = ds.get("url", "")
            title = ds.get("title", "") or url or "(无标题)"
            conf = ds.get("confidence") or ""
            tag = f"[{conf}] " if conf else ""
            if url:
                lines.append(f"- {tag}[{title}]({url})")
            else:
                lines.append(f"- {tag}{title}")
    return "\n".join(lines)


def _format_source_refs(refs: list) -> str:
    parts = []
    for ref in refs:
        if not isinstance(ref, dict):
            continue
        url = ref.get("url", "")
        title = ref.get("title", "") or "链接"
        if url:
            parts.append(f"[{title}]({url})")
        else:
            parts.append(title)
    if not parts:
        return ""
    return f"**来源**：{' · '.join(parts)}"


# ============ 5 场景 payload 渲染 ============

def _render_s1_md(p: dict) -> str:
    out = []
    vps = p.get("vendor_profiles") or []
    if vps:
        out.append("\n### 竞品画像（Forrester Wave 风格）\n")
        out.append("| 竞品 | 波次定位 | 一句话 | 最佳适配 |")
        out.append("|------|----------|--------|----------|")
        for v in vps:
            out.append(
                f"| {v.get('competitor_name', '')} | {v.get('wave_position', '')} | "
                f"{v.get('one_line_pitch', '')} | {v.get('best_fit_for', '')} |"
            )
    rs = p.get("radar_scores") or []
    if rs:
        out.append("\n### 5 维评分（雷达图数据）\n")
        out.append("| 竞品 | 功能广度 (feature_breadth) | 易用性 (usability) | 性价比 (cost_effectiveness) | 稳定性 (stability) | 设计质量 (design_quality) |")
        out.append("|------|---|---|---|---|---|")
        for r in rs:
            out.append(
                f"| {r.get('competitor_name', '')} | {r.get('feature_breadth', '')} | "
                f"{r.get('usability', '')} | {r.get('cost_effectiveness', '')} | "
                f"{r.get('stability', '')} | {r.get('design_quality', '')} |"
            )
    fgs = p.get("feature_gaps") or []
    if fgs:
        out.append("\n### 功能差距\n")
        out.append("| 功能 | 竞品已有 | 投入 | 影响 |")
        out.append("|------|----------|------|------|")
        for g in fgs:
            out.append(
                f"| {g.get('feature_name', '')} | {', '.join(g.get('competitors_have_it') or [])} | "
                f"{g.get('estimated_effort', '')} | {g.get('estimated_impact', '')} |"
            )
    out.append("\n> 注：可视化雷达图见 HTML 版本")
    return "\n".join(out)


def _render_s2_md(p: dict) -> str:
    out = []
    ms = p.get("market_sizing") or {}
    if ms:
        out.append("\n### 市场规模 TAM/SAM/SOM\n")
        out.append("| 维度 | 数值 | 单位 | 货币 | 依据 |")
        out.append("|------|------|------|------|------|")
        for label, key in [("TAM", "tam"), ("SAM", "sam"), ("SOM", "som")]:
            mv = ms.get(key) or {}
            out.append(
                f"| {label} | {mv.get('amount', '—')} | {mv.get('unit', '')} | "
                f"{mv.get('currency', '')} | {mv.get('value_basis', '')} |"
            )
    ff = p.get("five_forces") or {}
    if ff:
        out.append("\n### Porter 五力\n")
        out.append("| 维度 | 强度 | 影响 |")
        out.append("|------|------|------|")
        forces = [("new_entrants", "新进入者"), ("supplier_power", "供应商"),
                  ("buyer_power", "买家"), ("substitute_threat", "替代品"),
                  ("competitive_rivalry", "现有竞争")]
        for k, label in forces:
            data = ff.get(k) or {}
            out.append(f"| {label} | {data.get('intensity', '')} | {data.get('implication', '')} |")
    players = p.get("players") or []
    if players:
        out.append("\n### 市场玩家\n")
        out.append("| 名称 | 公司 | 市场角色 | 份额% | 差异化 |")
        out.append("|------|------|----------|-------|--------|")
        for pl in players:
            out.append(
                f"| {pl.get('name', '')} | {pl.get('company', '')} | "
                f"{pl.get('market_role', '')} | {pl.get('market_share_pct', '')} | "
                f"{pl.get('key_differentiator', '')} |"
            )
    es = p.get("entry_strategy") or {}
    if es:
        out.append(f"\n### 进入策略\n\n推荐模式：`{es.get('recommended_mode', '')}`\n")
        out.append(f"初始定位：{es.get('initial_positioning', '')}")
    rec = p.get("competitor_recommendations") or {}
    rcs = rec.get("recommended_competitors") or []
    if rcs:
        out.append("\n### Recommender 推荐玩家\n")
        out.append("| 名称 | 公司 | 推荐理由 | 置信度 |")
        out.append("|------|------|----------|--------|")
        for r in rcs:
            out.append(
                f"| {r.get('name', '')} | {r.get('company', '')} | "
                f"{r.get('why_recommended', '')} | {r.get('confidence', '')} |"
            )
    return "\n".join(out)


def _render_s3_md(p: dict) -> str:
    out = []
    pb = p.get("pricing_baseline") or {}
    if pb:
        out.append(f"\n### 当前定价基线\n\n模式：`{pb.get('current_pricing_model', '')}` · "
                   f"层级数：{pb.get('current_tier_count', '')}")
    pkg = p.get("packaging") or {}
    tiers = pkg.get("tiers") or []
    if tiers:
        out.append("\n### 推荐套餐设计 GBB\n")
        out.append("| 套餐 | 定位 | 月费 | 年费 | 货币 | 推荐 | 对象 |")
        out.append("|------|------|------|------|------|------|------|")
        for t in tiers:
            rec = "★" if t.get("is_recommended") else ""
            out.append(
                f"| {t.get('name', '')} | {t.get('position', '')} | "
                f"{t.get('monthly_price', '')} | {t.get('annual_price', '')} | "
                f"{t.get('currency', '')} | {rec} | {t.get('target_persona', '')} |"
            )
    cpm = p.get("competitive_pricing_matrix") or []
    if cpm:
        out.append("\n### 竞品定价矩阵\n")
        for cp in cpm:
            out.append(f"#### {cp.get('competitor_name', '')}")
            ts = cp.get("tiers") or []
            if ts:
                out.append("\n| 套餐 | 月费 | 年费 |")
                out.append("|------|------|------|")
                for t in ts:
                    out.append(f"| {t.get('name', '')} | {t.get('monthly_price', '')} | {t.get('annual_price', '')} |")
    rs = p.get("recommendations_summary") or {}
    if rs:
        out.append("\n### 定价方案总结\n")
        out.append(rs.get("recommended_packaging_summary", ""))
        if rs.get("expected_arr_uplift_pct") is not None:
            out.append(f"\n预期 ARR 提升：{rs['expected_arr_uplift_pct']}%（依据：{rs.get('expected_arr_uplift_basis', '')}）")
    return "\n".join(out)


def _render_s4_md(p: dict) -> str:
    out = []
    rp = p.get("review_period") or {}
    if rp:
        out.append(f"\n### 监控周期\n\n周期：{rp.get('review_period_label', '')} · "
                   f"竞品：{', '.join(rp.get('monitored_competitors') or [])}")
    for key, label in [("feature_changes", "功能变更"), ("pricing_changes", "定价变更"),
                       ("messaging_changes", "信息变更"), ("news_events", "新闻事件"),
                       ("org_changes", "组织变更")]:
        items = p.get(key) or []
        if not items:
            continue
        out.append(f"\n### {label}\n")
        out.append("| 竞品 | 类型 | 事实 | 严重度 |")
        out.append("|------|------|------|--------|")
        for it in items:
            ct = it.get("change_type") or it.get("category") or it.get("action") or ""
            fact = (it.get("fia") or {}).get("fact", "")
            out.append(f"| {it.get('competitor_name', '')} | {ct} | {fact} | {it.get('severity', '')} |")
    threats = p.get("threats") or []
    if threats:
        out.append("\n### 威胁评估\n")
        out.append("| 标题 | 严重度 | 可能性 | 应对 |")
        out.append("|------|--------|--------|------|")
        for t in threats:
            out.append(f"| {t.get('title', '')} | {t.get('severity', '')} | "
                       f"{t.get('likelihood', '')} | {t.get('recommended_response', '')} |")
    opps = p.get("opportunities") or []
    if opps:
        out.append("\n### 机会识别\n")
        out.append("| 类型 | 投入 | 影响 | 描述 |")
        out.append("|------|------|------|------|")
        for o in opps:
            out.append(f"| {o.get('opportunity_type', '')} | {o.get('estimated_effort', '')} | "
                       f"{o.get('expected_impact', '')} | {o.get('description', '')} |")
    return "\n".join(out)


def _render_s5_md(p: dict) -> str:
    out = []
    vps = p.get("vendor_profiles") or []
    if vps:
        out.append("\n### 竞品画像（Gartner MQ）\n")
        out.append("| 竞品 | 执行力 | 愿景完整度 | 象限 | 概览 |")
        out.append("|------|--------|------------|------|------|")
        for v in vps:
            out.append(
                f"| {v.get('competitor_name', '')} | {v.get('ability_to_execute_score', '')} | "
                f"{v.get('completeness_of_vision_score', '')} | {v.get('mq_quadrant', '')} | "
                f"{v.get('overview', '')} |"
            )
    pm = p.get("perceptual_map") or {}
    if pm:
        out.append("\n### 感知地图 Perceptual Map\n")
        x_axis = pm.get("x_axis") or {}
        y_axis = pm.get("y_axis") or {}
        out.append(f"X 轴：{x_axis.get('attribute', '')} ({x_axis.get('low_label', '')} → {x_axis.get('high_label', '')})")
        out.append(f"Y 轴：{y_axis.get('attribute', '')} ({y_axis.get('low_label', '')} → {y_axis.get('high_label', '')})")
        brands = pm.get("plotted_brands") or []
        if brands:
            out.append("\n| 品牌 | 我方 | X | Y | 置信度 | 理由 |")
            out.append("|------|------|---|---|--------|------|")
            for b in brands:
                self_mark = "✓" if b.get("is_self") else ""
                out.append(
                    f"| {b.get('competitor_name', '')} | {self_mark} | "
                    f"{b.get('x_score', '')} | {b.get('y_score', '')} | "
                    f"{b.get('confidence', '')} | {b.get('score_rationale', '')} |"
                )
    sc = p.get("strategy_canvas") or {}
    if sc:
        out.append("\n### 战略画布\n")
        factors = [f.get("name", "") for f in sc.get("competitive_factors") or []]
        if factors:
            out.append("| 品牌 | 我方 | " + " | ".join(factors) + " |")
            out.append("|------|------|" + "|".join(["---"] * len(factors)) + "|")
            for vc in sc.get("value_curves") or []:
                self_mark = "✓" if vc.get("is_self") else ""
                levels = [str((vc.get("factor_levels") or {}).get(f, "")) for f in factors]
                out.append(f"| {vc.get('competitor_name', '')} | {self_mark} | " + " | ".join(levels) + " |")
    ps = p.get("positioning_statement") or {}
    if ps:
        out.append("\n### 定位陈述（Geoffrey Moore 6 位模板）\n")
        for label, key in [("目标客户 For", "target_customer"),
                           ("核心需求 who", "need_or_opportunity"),
                           ("产品品类 is a", "product_category"),
                           ("核心价值 that", "key_benefit"),
                           ("主要替代 Unlike", "primary_alternative"),
                           ("差异化 our product", "primary_differentiation")]:
            v = ps.get(key)
            if v:
                out.append(f"- **{label}**：{v}")
        out.append(f"\n> 置信度：`{ps.get('confidence', '')}`")
    out.append("\n> 注：可视化图表（Magic Quadrant / Perceptual Map / Strategy Canvas）见 HTML 版本")
    return "\n".join(out)


_SCENARIO_RENDERERS: dict[str, Callable[[dict], str]] = {
    "S1": _render_s1_md,
    "S2": _render_s2_md,
    "S3": _render_s3_md,
    "S4": _render_s4_md,
    "S5": _render_s5_md,
}


# ============ 主入口 ============

def render_markdown(report: dict, *, trace_id: str) -> str:
    """渲染 BaseReport dict 为 Markdown 字符串。

    PD-2 宽松字段覆盖：每场景渲染常用字段（vendor_profiles / market_sizing /
    packaging / threats / vendor_profiles+perceptual_map+canvas 等）；
    嵌套深字段（如 S3 pricing_page_audit 8 法则）放弃覆盖。
    """
    parts: list[str] = []

    title = report.get("title") or "竞品分析报告"
    parts.append(f"# {title}")
    subtitle = report.get("subtitle")
    if subtitle:
        parts.append(f"\n_{subtitle}_")

    now_str = datetime.now(_BEIJING).strftime("%Y-%m-%d %H:%M")
    parts.append(f"\n> Trace ID: `{trace_id}` · 生成于 {now_str}\n")

    # 公共骨架
    parts.append(_render_at_a_glance(report.get("at_a_glance") or []))
    parts.append(_render_executive_summary(report.get("executive_summary") or {}))

    bg = report.get("background")
    if bg:
        parts.append(f"\n## 背景\n\n{bg}")

    parts.append(_render_scope(report.get("scope") or {}))
    parts.append(_render_methodology(report.get("methodology") or {}))
    parts.append(_render_key_findings(report.get("key_findings") or []))
    parts.append(_render_analysis_sections(report.get("analysis_sections") or []))
    parts.append(_render_swot(report.get("swot") or {}))

    conclusions = report.get("conclusions")
    if conclusions:
        parts.append(f"\n## 结论\n\n{conclusions}")

    parts.append(_render_recommendations(report.get("recommendations") or []))

    # 场景专属
    payload = report.get("scenario_payload") or {}
    scenario_type = payload.get("scenario_type") or (report.get("metadata") or {}).get("scenario") or ""
    fn = _SCENARIO_RENDERERS.get(scenario_type)
    scenario_full = _SCENARIO_NAMES.get(scenario_type, scenario_type)
    if fn:
        parts.append(f"\n## 场景专属：{scenario_full}\n")
        parts.append(fn(payload))
    elif scenario_type:
        parts.append(f"\n## 场景专属：{scenario_type}\n\n（未注册渲染器，跳过细节）")

    parts.append(_render_appendix(report.get("appendix") or {}))

    parts.append(f"\n\n---\n\n*由 AI 驱动竞品分析 Agent 协作系统生成 · trace `{trace_id}`*\n")

    # 过滤空段落 + 合并
    return "\n".join(p for p in parts if p)
```

- [ ] **Step 4: 跑测试确认 PASS**

```bash
pytest tests/unit/test_exporters_markdown.py -v
```

Expected: 7 passed.

- [ ] **Step 5: ruff 检查**

```bash
ruff check src/api/exporters/markdown.py
```

Expected: All checks passed.

- [ ] **Step 6: Commit**

```bash
git add src/api/exporters/markdown.py tests/unit/test_exporters_markdown.py
git commit -m "feat(exporters): markdown 导出器（5 场景常用字段覆盖，PD-2）"
```

---

## Task 13: 后端 /trace/{id}/export 路由

**Files:**
- Modify: `src/api/routes.py`（在 `get_trace` 之后追加新路由）

- [ ] **Step 1: 在 `src/api/routes.py` 末尾追加路由 + import**

打开 `src/api/routes.py`，文件顶部 import 段加：
```python
from typing import Literal
from fastapi import Response
from pydantic import ValidationError

from src.schemas.report import BaseReport
from src.api.exporters.markdown import render_markdown
```

文件末尾追加路由（注意复用 §7 spec 的双层路径穿越防护）：
```python
@router.get("/trace/{trace_id}/export")
async def export_trace(trace_id: str, format: Literal["md", "html"] = "md"):
    """导出指定 trace 的报告为 markdown 或 html。

    - 路径穿越防护：复用 GET /trace/{id} 的 fullmatch + resolve 双层校验
    - 旧 trace schema 漂移容忍：BaseReport.model_validate 失败时回退 dict 模式（M10）
    - HTML 导出待 Task 15 完成；当前 format=html 走 NotImplementedError 占位
    """
    if not _TRACE_RE.fullmatch(trace_id):
        raise HTTPException(status_code=404, detail="trace not found")
    base = runs_dir()
    trace_dir = (base / trace_id).resolve()
    if base.resolve() not in trace_dir.parents and trace_dir != base.resolve():
        raise HTTPException(status_code=404, detail="trace not found")
    if not trace_dir.is_dir():
        raise HTTPException(status_code=404, detail="trace not found")
    report_path = trace_dir / "03_report.json"
    if not report_path.is_file():
        raise HTTPException(status_code=404, detail="该 trace 未产出报告")

    raw = _load_json(report_path)
    if raw is None:
        raise HTTPException(status_code=500, detail="report.json 解析失败")

    # M10 修入：旧 trace schema 漂移容忍
    try:
        report = BaseReport.model_validate(raw)
        report_dict = report.model_dump()
    except ValidationError as e:
        logger.warning(
            "[export] BaseReport.model_validate failed for %s, dict fallback: %s",
            trace_id, str(e)[:200],
        )
        report_dict = raw

    if format == "md":
        body = render_markdown(report_dict, trace_id=trace_id)
        return Response(
            content=body,
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="report-{trace_id}.md"'},
        )
    elif format == "html":
        # Task 15 实现 render_html
        from src.api.exporters.html import render_html
        body = render_html(report_dict, trace_id=trace_id)
        return Response(
            content=body,
            media_type="text/html; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="report-{trace_id}.html"'},
        )
    else:
        raise HTTPException(status_code=400, detail="format must be md or html")
```

- [ ] **Step 2: 启动后端验证 markdown 导出可用**

```bash
.\venv\Scripts\uvicorn src.api.main:app --reload
```

挑一个有 03_report.json 的真实 trace（如 PROGRESS.md 的 `20260609-203430-a4aab7`）测试：

```bash
curl -o /tmp/test.md "http://localhost:8000/api/v1/trace/20260609-203430-a4aab7/export?format=md"
```

Windows PowerShell：
```powershell
Invoke-WebRequest "http://localhost:8000/api/v1/trace/20260609-203430-a4aab7/export?format=md" -OutFile "$env:TEMP\test.md"
```

Expected: 下载到 markdown 文件，编辑器打开内容完整 + 含 `# S2 测试...` 标题 + KPI 数据 + 章节卡片。

- [ ] **Step 3: 路径穿越测试**

```bash
curl -i "http://localhost:8000/api/v1/trace/..%2F..%2Fetc%2Fpasswd/export?format=md"
```

Expected: 404 Not Found。

- [ ] **Step 4: format=html 应仍 ImportError**

```bash
curl "http://localhost:8000/api/v1/trace/20260609-203430-a4aab7/export?format=html"
```

Expected: 500 错误（`from src.api.exporters.html import render_html` 失败）—— 这是预期，Task 15 后修复。

- [ ] **Step 5: Commit**

```bash
git add src/api/routes.py
git commit -m "feat(api): 加 GET /trace/{id}/export?format=md|html 路由（md 已可用，html 待 Task 15）"
```

---

## Task 14: 路径穿越单测

**Files:**
- Create: `tests/unit/test_export_path_traversal.py`

- [ ] **Step 1: 写测试**

```python
"""验证 GET /trace/{id}/export 路径穿越防护（M7 修入）。

复用 GET /trace/{id} 已有 fullmatch + resolve 双层校验，
攻击 trace_id 应一律返 404。
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.mark.parametrize("bad_trace_id", [
    "../../etc/passwd",
    "..%2F..%2Fetc%2Fpasswd",
    "20260610-203430-../etc",
    "20260610-203430-aaaaaa/../",
    "20260610-203430-aaaaaa\\..\\windows",  # Windows
    "..\\..\\windows\\system32",
    "0000",                              # 不符合 \d{8}-\d{6}-[0-9a-f]{6} 格式
    "abcdef",
    "/etc/passwd",
    ".",
    "..",
    "",
])
def test_export_path_traversal_returns_404(client, bad_trace_id):
    """非法 trace_id 应一律 404，不访问磁盘。"""
    # 用 url_for 不能传非法字符，直接拼路径
    response = client.get(f"/api/v1/trace/{bad_trace_id}/export?format=md")
    # 路径中含 .. 或 \ 时 starlette 会 422 / 404，符合预期
    assert response.status_code in (404, 422), \
        f"trace_id={bad_trace_id!r} got {response.status_code}, expected 404/422"


def test_export_unknown_format_returns_400(client):
    """非法 format 参数应 422（pydantic Literal 校验）。"""
    response = client.get("/api/v1/trace/20260610-203430-aaaaaa/export?format=docx")
    assert response.status_code == 422
```

- [ ] **Step 2: 跑测试确认 PASS**

```bash
pytest tests/unit/test_export_path_traversal.py -v
```

Expected: 13 passed。

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_export_path_traversal.py
git commit -m "test(export): 路径穿越防护单测（M7 修入）"
```

---

## Task 15: exporters/html.py + 模板（含 nh3 sanitize）

**Files:**
- Create: `src/api/exporters/html.py`
- Create: `src/api/exporters/templates/report.html.j2`
- Test: `tests/unit/test_exporters_html.py`

- [ ] **Step 1: 写失败测试 `tests/unit/test_exporters_html.py`**

```python
"""验证 html 导出器：5 场景关键字段 + Plotly 嵌入 + 字体 base64。"""
from __future__ import annotations

import pytest

from src.api.exporters.html import render_html
from tests.unit.test_exporters_markdown import _minimal_base_report  # 复用 fixture


def test_html_basic_structure():
    """生成的 HTML 含 doctype + meta + style + body。"""
    rep = _minimal_base_report("S1", {})
    out = render_html(rep, trace_id="t-html")

    assert out.startswith("<!DOCTYPE html>")
    assert "<html" in out
    assert "<head>" in out and "</head>" in out
    assert "<body>" in out and "</body>" in out
    assert "t-html" in out
    assert rep["title"] in out


def test_html_kpi_strip_present():
    """KPI 5 卡的标签都出现。"""
    rep = _minimal_base_report("S2", {})
    out = render_html(rep, trace_id="t-kpi")
    assert "质检评分" in out
    assert "场景标签" in out
    assert "竞品数量" in out
    assert "数据源数" in out
    assert "可信度" in out


def test_html_font_base64_inlined():
    """PD-4 全内嵌：HTML 含 woff2 字体 base64 字符串。"""
    rep = _minimal_base_report("S1", {})
    out = render_html(rep, trace_id="t")
    assert "data:font/woff2;base64," in out
    # 至少含 Plus Jakarta Sans 字体声明
    assert "Plus Jakarta Sans" in out


def test_html_s1_radar_plotly_embedded():
    """S1 场景含雷达图：HTML 含 plotly.js + scatterpolar trace。"""
    rep = _minimal_base_report("S1", {
        "radar_scores": [
            {"competitor_name": "A", "feature_breadth": 4, "usability": 4,
             "cost_effectiveness": 4, "stability": 4, "design_quality": 4},
        ],
    })
    out = render_html(rep, trace_id="t-s1")
    # Plotly 全内嵌（PD-4）：第一张图 include_plotlyjs=True 会嵌入完整 plotly.min.js
    assert "Plotly.newPlot" in out or "plotly.js" in out.lower()


def test_html_s2_renders_without_crash():
    """S2 含 five_forces，HTML 渲染不崩。"""
    rep = _minimal_base_report("S2", {
        "five_forces": {
            "new_entrants": {"intensity": "low", "implication": "X"},
            "supplier_power": {"intensity": "medium", "implication": "Y"},
            "buyer_power": {"intensity": "high", "implication": "Z"},
            "substitute_threat": {"intensity": "low", "implication": "W"},
            "competitive_rivalry": {"intensity": "medium", "implication": "V"},
        },
    })
    out = render_html(rep, trace_id="t-s2")
    assert "S2" in out


def test_html_s5_renders_without_crash():
    """S5 含 vendor_profiles MQ + perceptual_map，不崩。"""
    rep = _minimal_base_report("S5", {
        "vendor_profiles": [
            {"competitor_name": "V1", "ability_to_execute_score": 3,
             "completeness_of_vision_score": 4, "mq_quadrant": "visionary",
             "overview": "V1 概览"},
        ],
        "perceptual_map": {
            "x_axis": {"attribute": "X", "low_label": "低", "high_label": "高", "scale_max": 5},
            "y_axis": {"attribute": "Y", "low_label": "低", "high_label": "高", "scale_max": 5},
            "plotted_brands": [
                {"competitor_name": "V1", "x_score": 3, "y_score": 4,
                 "is_self": False, "confidence": "high", "score_rationale": "依据"},
            ],
        },
    })
    out = render_html(rep, trace_id="t-s5")
    assert "S5" in out
    assert "V1" in out
```

- [ ] **Step 2: 创建 `src/api/exporters/templates/report.html.j2`**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <title>{{ report.title or "竞品分析报告" }}</title>
  <style>
    @font-face {
      font-family: 'Plus Jakarta Sans';
      src: url(data:font/woff2;base64,{{ font_jakarta_regular }}) format('woff2');
      font-weight: 400;
      font-display: swap;
    }
    @font-face {
      font-family: 'Plus Jakarta Sans';
      src: url(data:font/woff2;base64,{{ font_jakarta_bold }}) format('woff2');
      font-weight: 700;
      font-display: swap;
    }
    @font-face {
      font-family: 'Fira Code';
      src: url(data:font/woff2;base64,{{ font_fira }}) format('woff2');
      font-display: swap;
    }
    :root {
      --color-primary: #1E40AF;
      --color-secondary: #3B82F6;
      --color-accent: #D97706;
      --color-bg: #F8FAFC;
      --color-surface: #FFFFFF;
      --color-text: #0F172A;
      --color-text-secondary: #475569;
      --color-border: #DBEAFE;
      --color-danger: #DC2626;
      --color-success: #16A34A;
      --color-warning: #D97706;
    }
    * { box-sizing: border-box; }
    body {
      font-family: 'Plus Jakarta Sans', -apple-system, sans-serif;
      background: var(--color-bg);
      padding: 32px;
      max-width: 1200px;
      margin: 0 auto;
      color: var(--color-text);
      line-height: 1.6;
    }
    h1, h2, h3 { color: var(--color-primary); }
    h1 { margin: 0 0 8px; }
    h2 { margin-top: 32px; padding-bottom: 8px; border-bottom: 2px solid var(--color-border); }
    .num { font-family: 'Fira Code', monospace; }
    .hero {
      background: var(--color-surface);
      padding: 24px;
      border-left: 4px solid var(--color-primary);
      border-radius: 8px;
      margin-bottom: 24px;
      box-shadow: 0 1px 3px rgba(15,23,42,0.08);
    }
    .kpi-strip {
      display: grid;
      grid-template-columns: repeat(5, 1fr);
      gap: 16px;
      margin: 24px 0;
    }
    .kpi-card {
      background: var(--color-surface);
      padding: 16px;
      border-radius: 8px;
      box-shadow: 0 1px 3px rgba(15,23,42,0.08);
      border-left: 3px solid var(--color-primary);
    }
    .kpi-card-label { font-size: 12px; color: var(--color-text-secondary); }
    .kpi-card-main { font-size: 28px; font-weight: 600; color: var(--color-primary); margin: 4px 0; }
    .kpi-card-sub { font-size: 12px; color: var(--color-text-secondary); }
    .section-card {
      background: var(--color-surface);
      margin: 16px 0;
      padding: 20px;
      border-left: 4px solid var(--color-primary);
      border-radius: 8px;
      box-shadow: 0 1px 3px rgba(15,23,42,0.08);
    }
    .section-card h3 { margin-top: 0; }
    .action-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
      gap: 12px;
      margin: 12px 0;
    }
    .action-card {
      background: var(--color-surface);
      padding: 16px;
      border-radius: 8px;
      border-left: 4px solid var(--color-accent);
      box-shadow: 0 1px 3px rgba(15,23,42,0.08);
    }
    .action-card.priority-critical { border-left-color: var(--color-danger); }
    .action-card.priority-important { border-left-color: var(--color-warning); }
    .action-card.priority-consider { border-left-color: var(--color-primary); }
    table { border-collapse: collapse; width: 100%; margin: 12px 0; font-size: 14px; }
    th, td { border: 1px solid var(--color-border); padding: 8px 12px; text-align: left; }
    th { background: #E9EEF6; }
    code { background: #E9EEF6; padding: 2px 6px; border-radius: 4px; font-family: 'Fira Code', monospace; font-size: 13px; }
    a { color: var(--color-primary); text-decoration: none; }
    a:hover { text-decoration: underline; }
    .source-refs { font-size: 12px; color: var(--color-text-secondary); margin-top: 8px; }
    @media print { .no-print { display: none } body { padding: 8px; } }
  </style>
</head>
<body>
  <header class="hero">
    <h1>{{ report.title or "竞品分析报告" }}</h1>
    {% if report.subtitle %}<p>{{ report.subtitle }}</p>{% endif %}
    <small class="num">Trace: {{ trace_id }} · 生成于 {{ generated_at }}</small>
  </header>

  {# KPI 5 卡 #}
  {% set meta = report.metadata or {} %}
  <div class="kpi-strip">
    <div class="kpi-card">
      <div class="kpi-card-label">质检评分</div>
      <div class="kpi-card-main num">
        {%- set raw = meta.raw_quality_score -%}
        {%- set final = meta.quality_score -%}
        {%- if raw is not none -%}{{ "%.3f"|format(raw) }}
        {%- elif final is not none -%}{{ "%.3f"|format(final) }}
        {%- else -%}—{%- endif -%}
      </div>
      <div class="kpi-card-sub">
        {%- if "capped" in (meta.quality_score_calculation_note or "") and final is not none and raw is not none and final < raw -%}
          cap 后 {{ "%.2f"|format(final) }}
        {%- elif raw is none and final is none -%}
          未质检
        {%- endif -%}
      </div>
    </div>
    <div class="kpi-card">
      <div class="kpi-card-label">场景标签</div>
      <div class="kpi-card-main">{{ meta.scenario or "—" }}</div>
      <div class="kpi-card-sub">{{ scenario_label }}</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-card-label">竞品数量</div>
      <div class="kpi-card-main num">{{ ((report.scope or {}).competitors or [])|length }}</div>
      <div class="kpi-card-sub">{{ competitors_sub }}</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-card-label">数据源数</div>
      <div class="kpi-card-main num">{{ (meta.data_sources or [])|length }}</div>
      <div class="kpi-card-sub">{{ sources_sub }}</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-card-label">可信度</div>
      <div class="kpi-card-main" style="color:{{ confidence_color }}">{{ meta.confidence_level or "—" }}</div>
      <div class="kpi-card-sub"></div>
    </div>
  </div>

  {# at_a_glance #}
  {% if report.at_a_glance %}
    <h2>一图看懂</h2>
    <ul>
    {% for it in report.at_a_glance %}<li>{{ it }}</li>{% endfor %}
    </ul>
  {% endif %}

  {# executive_summary #}
  {% if report.executive_summary %}
    {% set es = report.executive_summary %}
    <h2>执行摘要</h2>
    {% if es.context %}<h3>背景定位</h3><div>{{ es.context | safe_md }}</div>{% endif %}
    {% if es.core_thesis %}<h3>核心论断</h3><div>{{ es.core_thesis | safe_md }}</div>{% endif %}
    {% if es.implications %}<h3>现实启示</h3><div>{{ es.implications | safe_md }}</div>{% endif %}
    {% if es.key_findings_brief %}
      <h3>关键发现速览</h3>
      <ul>{% for f in es.key_findings_brief %}<li>{{ f }}</li>{% endfor %}</ul>
    {% endif %}
    {% if es.path_forward %}
      <h3>行动路径</h3>
      <ul>{% for p in es.path_forward %}<li>{{ p }}</li>{% endfor %}</ul>
    {% endif %}
  {% endif %}

  {# scope + methodology #}
  {% if report.scope %}
    <h2>分析范围</h2>
    <ul>
      <li><strong>竞品</strong>：{{ (report.scope.competitors or [])|join(", ") }}</li>
      {% if report.scope.time_window %}<li><strong>时间窗</strong>：{{ report.scope.time_window }}</li>{% endif %}
    </ul>
  {% endif %}
  {% if report.methodology and report.methodology.data_collection_approach %}
    <h2>方法论</h2>
    <div>{{ report.methodology.data_collection_approach | safe_md }}</div>
  {% endif %}

  {# 关键发现 #}
  {% if report.key_findings %}
    <h2>关键发现</h2>
    {% for f in report.key_findings %}
      <div class="section-card">
        <h3>Finding {{ loop.index }}</h3>
        <div>{{ f.statement | safe_md }}</div>
        {% if f.evidence %}<small><strong>依据</strong>：{{ f.evidence }}</small><br>{% endif %}
        {% if f.implication %}<small><strong>启示</strong>：{{ f.implication }}</small>{% endif %}
        {% if f.source_refs %}
          <div class="source-refs">来源：
            {% for ref in f.source_refs %}{% if ref.url %}<a href="{{ ref.url }}">{{ ref.title or ref.url }}</a>{% if not loop.last %} · {% endif %}{% endif %}{% endfor %}
          </div>
        {% endif %}
      </div>
    {% endfor %}
  {% endif %}

  {# 详细章节 #}
  {% if report.analysis_sections %}
    <h2>详细章节</h2>
    {% for section in report.analysis_sections %}
      <div class="section-card">
        <h3>{{ section.heading }}</h3>
        <small>section_type: <code>{{ section.section_type }}</code></small>
        <div>{{ section.narrative | safe_md }}</div>
        {% if section.source_refs %}
          <div class="source-refs">来源：
            {% for ref in section.source_refs %}{% if ref.url %}<a href="{{ ref.url }}">{{ ref.title or ref.url }}</a>{% if not loop.last %} · {% endif %}{% endif %}{% endfor %}
          </div>
        {% endif %}
      </div>
    {% endfor %}
  {% endif %}

  {# SWOT #}
  {% if report.swot %}
    <h2>SWOT 分析</h2>
    {% for key, label in [("strengths","优势 S"), ("weaknesses","劣势 W"), ("opportunities","机会 O"), ("threats","威胁 T")] %}
      {% if report.swot[key] %}
        <h3>{{ label }}</h3>
        <ul>
          {% for e in report.swot[key] %}
            <li><strong>{{ e.point }}</strong>{% if e.evidence %} — {{ e.evidence }}{% endif %}</li>
          {% endfor %}
        </ul>
      {% endif %}
    {% endfor %}
  {% endif %}

  {# 行动建议 #}
  {% if report.recommendations %}
    <h2>行动建议</h2>
    {% set tl_groups = {"immediate":[], "short_term":[], "long_term":[]} %}
    {% for r in report.recommendations %}{% set _ = tl_groups[r.timeline or "long_term"].append(r) %}{% endfor %}
    {% for tl_key, tl_label in [("immediate","即时（1 个月内）"), ("short_term","短期（3 个月内）"), ("long_term","长期（6-12 个月）")] %}
      {% if tl_groups[tl_key] %}
        <h3>{{ tl_label }}</h3>
        <div class="action-grid">
          {% for r in tl_groups[tl_key] %}
            <div class="action-card priority-{{ r.priority }}">
              <strong>[{{ r.priority }}]</strong> {{ r.action }}
              {% if r.target_role %}<br><small>对象：{{ r.target_role }}</small>{% endif %}
              {% if r.rationale %}<br><small>依据：{{ r.rationale }}</small>{% endif %}
            </div>
          {% endfor %}
        </div>
      {% endif %}
    {% endfor %}
  {% endif %}

  {# 5 场景图表 + payload 表格（5 张图 inline） #}
  {% if scenario_charts %}
    <h2>场景专属可视化（{{ scenario_type }}）</h2>
    {% for chart in scenario_charts %}
      <div>{{ chart | safe }}</div>
    {% endfor %}
  {% endif %}

  <hr style="margin-top:48px">
  <small>由 AI 驱动竞品分析 Agent 协作系统生成 · trace <code>{{ trace_id }}</code></small>
</body>
</html>
```

- [ ] **Step 3: 创建 `src/api/exporters/html.py`**

```python
"""BaseReport → HTML 导出器（PD-4 全内嵌：字体 + Plotly + CSS）。

C5 修入：narrative 走 markdown→html→nh3 sanitize 三步保 XSS 安全。
PD-4 修入：字体 base64 内嵌 + Plotly include_plotlyjs=True 内嵌 plotly.min.js。
"""
from __future__ import annotations

import base64
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jinja2
import markdown as md_lib
import nh3

from src.api.exporters import check_fonts

logger = logging.getLogger(__name__)

_BEIJING = timezone(timedelta(hours=8))
_FONTS_DIR = Path(__file__).parent / "fonts"
_TEMPLATES_DIR = Path(__file__).parent / "templates"

_SCENARIO_LABELS = {
    "S1": "功能迭代", "S2": "市场进入", "S3": "定价策略",
    "S4": "持续监控", "S5": "战略定位",
}

_FONT_BASE64_CACHE: dict[str, str] = {}


def _font_base64(name: str) -> str:
    """读字体文件并返回 base64 字符串（缓存到模块级 dict 避免重复读盘）。"""
    if name not in _FONT_BASE64_CACHE:
        path = _FONTS_DIR / name
        _FONT_BASE64_CACHE[name] = base64.b64encode(path.read_bytes()).decode()
    return _FONT_BASE64_CACHE[name]


# nh3 sanitizer config（C5 修入）
_NH3_ALLOWED_TAGS = {
    "p", "br", "strong", "em", "ul", "ol", "li", "h1", "h2", "h3", "h4", "h5", "h6",
    "blockquote", "code", "pre", "a", "table", "thead", "tbody", "tr", "th", "td",
    "hr", "div", "span",
}
_NH3_ALLOWED_ATTRS = {"a": {"href", "title"}}


def _safe_markdown(text: str) -> str:
    """C5 修入：narrative 等 LLM 文本走 markdown→html→nh3 sanitize 三步。

    nh3 strips:
    - <script> tags
    - inline event handlers (onclick=...)
    - javascript: URIs
    - 任何不在 _NH3_ALLOWED_TAGS 内的标签
    """
    if not text or not isinstance(text, str):
        return ""
    raw_html = md_lib.markdown(text, extensions=["extra", "nl2br"])
    return nh3.clean(
        raw_html,
        tags=_NH3_ALLOWED_TAGS,
        attributes=_NH3_ALLOWED_ATTRS,
    )


# Jinja2 environment（autoescape 强开 = C5 双层防护）
_jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(_TEMPLATES_DIR)),
    autoescape=jinja2.select_autoescape(["html", "j2"]),
)
_jinja_env.filters["safe_md"] = _safe_markdown


def _confidence_color(level: str) -> str:
    return {"high": "#16A34A", "medium": "#D97706", "low": "#DC2626"}.get(level or "", "#475569")


def _competitors_sub(report: dict) -> str:
    """KPI 竞品数量副信息。S2 时显示「含 N 推荐」。"""
    payload = report.get("scenario_payload") or {}
    if payload.get("scenario_type") == "S2":
        rec = payload.get("competitor_recommendations") or {}
        rec_list = rec.get("recommended_competitors") or []
        if rec_list:
            return f"含 {len(rec_list)} 推荐"
    return ""


def _sources_sub(meta: dict) -> str:
    sources = meta.get("data_sources") or []
    if not sources:
        return ""
    high = sum(1 for s in sources if (s.get("confidence") or "") == "high")
    mid = sum(1 for s in sources if (s.get("confidence") or "") == "medium")
    low = sum(1 for s in sources if (s.get("confidence") or "") == "low")
    return f"高 {high} 中 {mid} 低 {low}"


def _build_scenario_charts(report: dict) -> tuple[str, list[str]]:
    """生成 5 场景的 Plotly 图表 HTML 字符串列表。

    返回 (scenario_type, charts_list)。第一张 include_plotlyjs=True 内嵌 plotly.min.js；
    后续图 include_plotlyjs=False 共享。
    """
    payload = report.get("scenario_payload") or {}
    scenario_type = payload.get("scenario_type") or (report.get("metadata") or {}).get("scenario") or ""

    charts: list[str] = []
    figs = []

    if scenario_type == "S1":
        from src.frontend.render import _radar_chart_s1
        fig = _radar_chart_s1(payload.get("radar_scores") or [])
        if fig is not None:
            figs.append(fig)
    elif scenario_type == "S2":
        from src.frontend.render import _radar_chart_five_forces
        fig = _radar_chart_five_forces(payload.get("five_forces") or {})
        if fig is not None:
            figs.append(fig)
    elif scenario_type == "S5":
        from src.frontend.render import (
            _scatter_perceptual_map,
            _scatter_magic_quadrant,
            _line_strategy_canvas,
        )
        for builder, arg in [
            (_scatter_perceptual_map, payload.get("perceptual_map") or {}),
            (_scatter_magic_quadrant, payload.get("vendor_profiles") or []),
            (_line_strategy_canvas, payload.get("strategy_canvas") or {}),
        ]:
            fig = builder(arg)
            if fig is not None:
                figs.append(fig)

    for i, fig in enumerate(figs):
        try:
            charts.append(fig.to_html(
                include_plotlyjs=(i == 0),  # 第一张内嵌完整 plotly.min.js
                full_html=False,
            ))
        except Exception as e:  # noqa: BLE001
            logger.warning("[html_export] Plotly to_html failed: %s", e)

    return scenario_type, charts


def render_html(report: dict, *, trace_id: str) -> str:
    """渲染 BaseReport dict 为完整 HTML 字符串。

    所有资源（字体 / Plotly / CSS）全部内嵌，单 HTML 文件离线 100% 可用。
    """
    check_fonts()  # 启动校验，缺字体 raise FileNotFoundError

    template = _jinja_env.get_template("report.html.j2")

    scenario_type, scenario_charts = _build_scenario_charts(report)
    meta = report.get("metadata") or {}

    return template.render(
        report=report,
        trace_id=trace_id,
        generated_at=datetime.now(_BEIJING).strftime("%Y-%m-%d %H:%M"),
        font_jakarta_regular=_font_base64("PlusJakartaSans-Regular.woff2"),
        font_jakarta_bold=_font_base64("PlusJakartaSans-Bold.woff2"),
        font_fira=_font_base64("FiraCode-Regular.woff2"),
        scenario_label=_SCENARIO_LABELS.get(meta.get("scenario") or "", ""),
        competitors_sub=_competitors_sub(report),
        sources_sub=_sources_sub(meta),
        confidence_color=_confidence_color(meta.get("confidence_level") or ""),
        scenario_type=scenario_type,
        scenario_charts=scenario_charts,
    )
```

- [ ] **Step 4: 跑测试确认 PASS**

```bash
pytest tests/unit/test_exporters_html.py -v
```

Expected: 6 passed.

如果 fonts 文件没下载会 FileNotFoundError，回 Task 11 Step 3 下载。

- [ ] **Step 5: 真实 trace 生成 HTML 离线测试**

```bash
.\venv\Scripts\uvicorn src.api.main:app --reload &
curl -o "$env:TEMP\test.html" "http://localhost:8000/api/v1/trace/20260609-203430-a4aab7/export?format=html"
```

PowerShell：
```powershell
Invoke-WebRequest "http://localhost:8000/api/v1/trace/20260609-203430-a4aab7/export?format=html" -OutFile "$env:TEMP\test.html"
```

**关键验收（PD-4）**：双击打开 `$env:TEMP\test.html`，**断网**后刷新——字体仍是 Plus Jakarta Sans，图表仍能交互（hover tooltip / zoom）。

- [ ] **Step 6: ruff 检查**

```bash
ruff check src/api/exporters/html.py
```

Expected: All checks passed.

- [ ] **Step 7: Commit**

```bash
git add src/api/exporters/html.py src/api/exporters/templates/report.html.j2 tests/unit/test_exporters_html.py
git commit -m "feat(exporters): html 导出器 + Jinja2 模板（PD-4 全内嵌 + C5 nh3 sanitize）"
```

---

## Task 16: XSS sanitize 单测

**Files:**
- Create: `tests/unit/test_exporters_html_xss.py`

- [ ] **Step 1: 写测试**

```python
"""验证 HTML 导出器的 XSS 防护（C5 critical / 跨模型独占发现）。

narrative / executive_summary / 章节文本可能含 LLM 生成或网页爬来的 HTML，
必须经 nh3 sanitize + Jinja2 autoescape 双层防护。
"""
from __future__ import annotations

import pytest

from src.api.exporters.html import render_html, _safe_markdown
from tests.unit.test_exporters_markdown import _minimal_base_report


def test_safe_markdown_strips_script():
    """直接测试 _safe_markdown 函数：<script> 应被 strip。"""
    text = "正常文本 <script>alert('XSS')</script> 后面"
    out = _safe_markdown(text)
    assert "<script>" not in out
    assert "alert" not in out
    assert "正常文本" in out
    assert "后面" in out


def test_safe_markdown_strips_inline_event_handler():
    """inline event handler (onclick) 应被 strip。"""
    text = '<a href="https://example.com" onclick="alert(1)">link</a>'
    out = _safe_markdown(text)
    assert "onclick" not in out
    # link 内容仍保留
    assert "link" in out


def test_safe_markdown_strips_javascript_uri():
    """javascript: 协议 URL 应被 strip。"""
    text = '<a href="javascript:alert(1)">click</a>'
    out = _safe_markdown(text)
    assert "javascript:" not in out


def test_safe_markdown_strips_iframe():
    """<iframe> 应被 strip。"""
    text = '<iframe src="https://evil.com"></iframe>'
    out = _safe_markdown(text)
    assert "<iframe" not in out


def test_safe_markdown_preserves_safe_html():
    """安全的 HTML（strong/em/ul/li/a 等）应保留。"""
    text = "**bold** *italic* and a [link](https://example.com)"
    out = _safe_markdown(text)
    assert "<strong>" in out
    assert "<em>" in out
    assert "<a " in out and "https://example.com" in out


def test_html_export_strips_script_in_narrative():
    """端到端：恶意 narrative 通过 render_html 后 HTML 不含 <script>。"""
    rep = _minimal_base_report("S1", {})
    rep["analysis_sections"][0]["narrative"] = (
        "正常分析。<script>alert('XSS')</script> 文末。"
    )
    out = render_html(rep, trace_id="t-xss")
    # script 标签和 alert 字面量都不应出现在最终 HTML 中
    # 注意：autoescape 会把任何字面 < > 转义；nh3 strip 真实标签
    assert "<script>" not in out
    assert "<script " not in out
    # 但正文内容应保留（被转义）
    assert "正常分析" in out


def test_html_export_strips_iframe_in_executive_summary():
    """executive_summary 含 iframe 攻击向量也应被 strip。"""
    rep = _minimal_base_report("S2", {})
    rep["executive_summary"]["context"] = (
        "市场背景。<iframe src='https://evil.com'></iframe>"
    )
    out = render_html(rep, trace_id="t-xss2")
    assert "<iframe" not in out
    assert "市场背景" in out


def test_html_export_jinja_autoescape_for_metadata():
    """非 markdown 字段（如 title）走 Jinja autoescape，含 < 应转义为 &lt;。"""
    rep = _minimal_base_report("S1", {})
    rep["title"] = "<script>alert(1)</script>"  # 不会过 markdown
    out = render_html(rep, trace_id="t-title")
    # 标题里的 < 应转义为 &lt;
    assert "<script>" not in out
    assert "&lt;script&gt;" in out or "alert" not in out  # 一种或转义、或被丢
```

- [ ] **Step 2: 跑测试确认 PASS**

```bash
pytest tests/unit/test_exporters_html_xss.py -v
```

Expected: 8 passed.

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_exporters_html_xss.py
git commit -m "test(exporters): HTML XSS 防护单测（C5 跨模型独占发现）"
```

---

## Task 17: emoji lint 白名单单测

**Files:**
- Create: `tests/unit/test_emoji_lint.py`

- [ ] **Step 1: 写测试**

```python
"""验证 src/frontend/*.py 中 emoji 仅出现在 PD-5 白名单内位置。

PD-5「选择性纯化」：标题/导航/剩头 emoji 全换 Material Symbols；
KPI/badge/状态点 emoji 保留（视觉一致 + 评委友好）。

白名单（保留位置）：
- src/frontend/app.py 的 pick_confidence emoji（行 49 周边）
- src/frontend/render.py 的 recommendations badge（🔴🟡🟢）
- src/frontend/render.py 的 appendix data_sources confidence（🟢🟡🟠）
- src/frontend/render.py 的 S3 packaging 推荐套餐（⭐）
- src/frontend/render.py 的 S4 trends 方向（↑↓→）
- src/frontend/render.py 的 S5 watermark（⚠️）

新位置出现这些 emoji 视为 lint fail；新位置出现非白名单内其他 emoji 也 fail。
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest


# Emoji 正则（覆盖常见 emoji range；够用即可，不追求完美）
_EMOJI_RE = re.compile(
    "[\U0001F300-\U0001F6FF"  # symbols & pictographs
    "\U0001F900-\U0001F9FF"   # supplemental symbols
    "\U0001F600-\U0001F64F"   # emoticons
    "\U00002600-\U000027BF"   # miscellaneous + dingbats
    "\U00002B00-\U00002BFF"   # arrows
    "✅-⛿"
    "]"
)

# 允许出现 emoji 的代码行匹配模式（基于代码上下文识别白名单位置）
_ALLOWED_CONTEXTS = [
    # AI 推荐场景置信度（app.py）
    re.compile(r'(pick_confidence|conf_emoji|emoji\s*=\s*\{)'),
    # recommendations priority badge
    re.compile(r'badge\s*=\s*\{["\']critical'),
    # appendix data_sources confidence badge
    re.compile(r'badge\s*=\s*\{["\']high'),
    # S3 packaging recommended star
    re.compile(r'is_recommended.*"⭐"|⭐.*is_recommended'),
    # S4 trends arrow（包含字符串：'up': '↑'）
    re.compile(r'["\']up["\']\s*:\s*["\']↑'),
    # S5 watermark
    re.compile(r'display_watermark|watermark.*⚠'),
]


def _is_allowed_line(line: str) -> bool:
    """判断一行代码是否符合白名单上下文。"""
    return any(pat.search(line) for pat in _ALLOWED_CONTEXTS)


@pytest.mark.parametrize("filename", ["app.py", "render.py", "theme.py"])
def test_no_unauthorized_emoji_in_frontend(filename):
    """src/frontend/<filename> 中 emoji 仅出现在白名单内位置。"""
    fp = Path(__file__).parent.parent.parent / "src" / "frontend" / filename
    if not fp.exists():
        pytest.skip(f"{filename} not yet created")

    violations: list[tuple[int, str]] = []
    for lineno, line in enumerate(fp.read_text(encoding="utf-8").splitlines(), 1):
        if _EMOJI_RE.search(line):
            if not _is_allowed_line(line):
                violations.append((lineno, line.strip()))

    assert not violations, (
        f"{filename} 中以下行含未授权 emoji（PD-5 选择性纯化白名单外）：\n"
        + "\n".join(f"  L{ln}: {txt}" for ln, txt in violations)
        + "\n\n如需新增 emoji 请加到 tests/unit/test_emoji_lint.py 的 _ALLOWED_CONTEXTS。"
    )
```

- [ ] **Step 2: 跑测试确认 PASS（基于现状）**

```bash
pytest tests/unit/test_emoji_lint.py -v
```

Expected: 3 passed (app.py / render.py / theme.py 都不出现非白名单 emoji)。

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_emoji_lint.py
git commit -m "test(frontend): emoji 选择性纯化白名单 lint（PD-5）"
```

---

## Task 18: 集成测试 + 手动验收

**Files:**
- Create: `tests/integration/test_export_e2e.py`

- [ ] **Step 1: 写集成测试**

```python
"""E2E：5 场景 fixture trace → 调 export api → 验证 md/html 内容。"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.utils.paths import runs_dir


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def real_trace_id() -> str:
    """选一个真实存在的 trace_id（PROGRESS.md 中 S2 happy path）。

    若该 trace 已被清理，跳过该测试。
    """
    candidates = [
        "20260609-203430-a4aab7",  # S2 happy path
        "20260609-220309-e58ee9",  # S3 happy path
    ]
    for tid in candidates:
        if (runs_dir() / tid / "03_report.json").is_file():
            return tid
    pytest.skip("no real trace fixture available")


def test_export_md_e2e(client, real_trace_id):
    """E2E：调 export markdown，下载到的内容含关键字段。"""
    response = client.get(f"/api/v1/trace/{real_trace_id}/export?format=md")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    body = response.content.decode("utf-8")
    assert real_trace_id in body
    assert "# " in body  # 有 markdown 标题
    assert len(body) > 500  # 内容不为空


def test_export_html_e2e(client, real_trace_id):
    """E2E：调 export html，验证字节大小符合 PD-4 全内嵌预期 + 含字体 base64。"""
    response = client.get(f"/api/v1/trace/{real_trace_id}/export?format=html")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    body = response.content
    # PD-4 全内嵌预期：单 HTML > 500KB（plotly.min.js ~3MB + 字体 100KB + 内容）
    # 上限 10MB 防失控
    assert 100_000 < len(body) < 15_000_000, f"HTML size {len(body)} out of expected range"
    # 关键内嵌资源
    text = body.decode("utf-8")
    assert "data:font/woff2;base64," in text
    assert real_trace_id in text


def test_export_html_offline_safe(client, real_trace_id, tmp_path):
    """模拟离线：保存 HTML 到本地，仅检查不含 fonts.googleapis.com 等外网 CDN 引用。"""
    response = client.get(f"/api/v1/trace/{real_trace_id}/export?format=html")
    text = response.content.decode("utf-8")
    # PD-4 离线 100%：不应有外部 CDN 引用
    assert "fonts.googleapis.com" not in text
    assert "fonts.gstatic.com" not in text
    # plotly.com / cdn.plot.ly 不应作为 src 出现（应内嵌）
    assert 'src="https://cdn.plot.ly' not in text


def test_export_404_for_missing_trace(client):
    """不存在的 trace 应 404。"""
    response = client.get("/api/v1/trace/20990101-000000-deadbe/export?format=md")
    assert response.status_code == 404


def test_export_404_for_missing_report(client, tmp_path, monkeypatch):
    """trace 目录存在但 03_report.json 缺失应 404 'report not found'。"""
    fake_trace = "20260101-000000-faaaaa"
    fake_dir = runs_dir() / fake_trace
    fake_dir.mkdir(parents=True, exist_ok=True)
    (fake_dir / "meta.json").write_text("{}", encoding="utf-8")  # 有 meta 无 report
    try:
        response = client.get(f"/api/v1/trace/{fake_trace}/export?format=md")
        assert response.status_code == 404
        assert "report" in response.json()["detail"].lower() or "未产出" in response.json()["detail"]
    finally:
        # 清理
        (fake_dir / "meta.json").unlink()
        fake_dir.rmdir()
```

- [ ] **Step 2: 跑集成测试**

```bash
pytest tests/integration/test_export_e2e.py -v
```

Expected: 5 passed（如果没有真实 trace fixture 跳过 3 条，仅跑 missing_trace + missing_report）。

- [ ] **Step 3: 手动验收清单**

启动后端 + 前端：
```bash
.\venv\Scripts\uvicorn src.api.main:app --reload
.\venv\Scripts\streamlit run src\frontend\app.py
```

逐条验收：
- [ ] 主题色生效：标题深蓝（`#1E40AF`），背景浅灰，按钮 hover 平滑过渡
- [ ] KPI 5 卡：跑一次 S2/S3 → 5 张卡显示完整（quality + scenario + 竞品数 + 数据源 + confidence）
- [ ] cap 提示：跑一次 S5 触发 placeholder cap → 第 1 张卡显示 raw + cap 后 0.50
- [ ] Section 卡片：每个 detail section 有主色左剩头 + 浅色背景
- [ ] Action Card grid：recommendations 按 timeline 分 3 组 + 2 列 grid + priority 染色
- [ ] 导出 md：报告页点【导出 Markdown】→ 浏览器下载 `report-<trace>.md`，编辑器打开内容完整 + markdown 表格正确
- [ ] 导出 html：点【导出 HTML】→ 下载 → 双击打开浏览器：主题色 + 章节卡片 + KPI + Plotly 交互图表
- [ ] **HTML 离线测试（PD-4 关键）**：下载后**断网**双击打开 → 字体 / Plotly 图表都正常
- [ ] **XSS 验证**：手工构造 `runs/20260101-000000-deadbe/03_report.json` 含 `<script>alert(1)</script>` 在 narrative → 调 export html → 浏览器打开**不弹框**
- [ ] 追溯面板：输入历史 trace_id → 加载 → 报告 tab 顶部有【导出】双按钮可用
- [ ] 路径穿越：浏览器访问 `/api/v1/trace/..%2F..%2Fetc/export?format=md` → 404

- [ ] **Step 4: 跑全套测试 + ruff 确认无回归**

```bash
pytest -q
ruff check src tests
```

Expected: 全过 + 0 errors。

- [ ] **Step 5: 最终 Commit + push**

```bash
git add tests/integration/test_export_e2e.py
git commit -m "test(integration): export E2E（md/html/离线/404 路径穿越）"
git log --oneline -20
git push origin master
```

Expected: 看到 v2 实施期间的 ~18 个 commit 全部推送到远程。

---

## 总结

完成所有 18 个 task 后：
- 3 个新文件：`theme.py` / `markdown.py` / `html.py`
- 6 个改文件：`report.py` / `inspector.py` / `app.py` / `render.py` / `routes.py` / `requirements.txt`
- 4 个新资源：`templates/report.html.j2` + 3 个 woff2 字体文件
- 7 个新测试文件：覆盖 schema / inspector / markdown / html / xss / path-traversal / emoji-lint

预计工时：3-5 小时（不含字体下载试错）。

写到这里 plan 结束。下一步用 `superpowers:subagent-driven-development` 或 `superpowers:executing-plans` 执行。
