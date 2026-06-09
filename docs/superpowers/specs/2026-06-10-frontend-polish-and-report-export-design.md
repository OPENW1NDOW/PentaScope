# 前端美化 + 报告导出 — 设计文档（v2）

**日期**：2026-06-10
**作者**：Cooper（产品）/ Claude（研发）
**目标**：答辩前最后一波改动。前端从默认 Streamlit 视觉升级到「Data-Dense Dashboard」专业仪表盘风格；报告新增 Markdown / HTML 双格式文件导出。

## 修订日志

### v2（2026-06-10 doubt-driven 双轮审查 + 范围收敛）

**单模型 + 跨模型（azure_openai/gpt-5.5）合并 35 条发现** → 去重 6 critical / 12 major / 7 minor。Cooper 拍板 6 条产品决策 + 范围决策（b. 仅做主题色 + 导出，舍弃场景卡重做 + Loading 阶段化）。

**Cooper 6 条产品决策**：

| ID | 决策 | 影响 |
|----|------|------|
| PD-1 | 放弃 Loading 阶段化，仅 spinner + 文案 rotation | §5 整章删除 |
| PD-2 | markdown 导出走「常用字段」+ 关键字段断言 | CONTRACT 4 放宽 |
| PD-3 | confidence_level 上独立 KPI 卡 | KPI 由 4 改 5 卡 |
| PD-4 | HTML 全内嵌（字体 + Plotly + CSS） | 离线 100% 可用，单 HTML 8-10MB |
| PD-5 | 选择性 emoji 纯化（仅标题/导航/剩头换 Material Symbols） | KPI/badge/状态点 emoji 保留 |
| PD-6 | inspector 改动「~5-6 行」软目标 | 不强压 |

**Cooper 范围决策（最终落地范围）**：仅实施主题色注入 + KPI 5 卡 + Action Card + 双格式导出。**舍弃**：场景卡片化重做（M3 风险）/ Loading 阶段化整章（C2-C4 + PD-1）。

**关键技术修复（v2 修入）**：
- C1：前端禁止 `from src.tools.trace_writer import` —— `streamlit run` 走 `src/frontend/` 为 sys.path
- C5（**跨模型独占发现**）：HTML 导出 narrative→html 必须 sanitize / autoescape，否则 stored XSS
- C6：requirements.txt 显式加 `markdown` `jinja2` `nh3`（HTML sanitizer），非 fastapi 传递依赖
- M1-M2：导出按钮改 prefetch bytes + `st.download_button`，render 签名加 trace_id
- M6：emoji 替换清单展开到 render.py / app.py 全部出现位置 + lint check
- M9：5 场景 markdown 走「常用字段」（PD-2）
- M12：§11 task 拆细到 file/function 级
- 新增（latent issue 已识别但 v2 范围外）：当前 03_report.json 落盘时 quality_score 永远 None（writer 节点先于 inspector 落盘）。v2 KPI 卡走 `/analyze` 实时返回的内存对象，不读盘，绕过此问题。追溯面板看历史 trace 仍 None，单独修留作后续

### v1（2026-06-10 初稿）

按 Cooper 7 个澄清问题汇总产出，含 4 块美化 + Markdown/HTML 双格式导出。doubt-driven 后重写。

---

## 0. 背景与约束

### 现状

- **前端**：纯 Streamlit 默认主题，黑白文字 + 默认 dropdown / text_input。`render.py` 渲染 BaseReport 通用部分 + 5 场景 payload + Plotly 图表，但全部直堆 `st.title / st.header / st.dataframe`，无主题色、无 KPI 概览、无导出。
- **报告导出**：仅 `POST /api/v1/analyze` 返回 `report.model_dump()` JSON 给前端渲染。`runs/<trace_id>/03_report.json` 落盘了 BaseReport，但用户只能在浏览器看渲染、无任何文件级导出。
- **Loading 体验**：`st.spinner("正在分析中，请稍候...")` 卡死黑盒 5-15 min（**v2 不动**——PD-1 决策）。

### 关键约束（CONTRACT，v2 修订后）

1. **不动 schema 主结构 / graph 拓扑 / 5 个 agent 核心**：仅 ReportMetadata 加 1 个字段 + inspector ~5-6 行回填 raw_quality_score
2. **不引入会让 happy path 倒退的复杂依赖**：新增 `markdown` `jinja2` `nh3` 显式加 requirements.txt，全部纯 Python、零原生扩展、零冲突
3. **演示期间用户能看到运行在进行**（v2 改自原 v1「实时进度」）：spinner + 文案 rotation 即可
4. **5 场景能导出 md/html + 关键字段覆盖**（v2 改自原 v1 "no field omission"）：每场景常用字段 + 单测断言关键字段
5. **emoji 选择性纯化**：标题 / 导航 / section 剩头 emoji 全换 Material Symbols；KPI 卡内的 confidence 三色点、recommendations badge、appendix confidence badge 等 emoji 保留
6. **后端 POST /analyze 保持原阻塞同步行为**（v2 撤销原 v1「拆 /analyze/start」）：不动 routes.py::analyze
7. **trace_id 仍由后端生成**（v2 撤销原 v1「前端预生成」）：前端不导入 trace_writer
8. **路径穿越防护**：复用 /trace/{id} 现有 `_TRACE_RE.fullmatch` + `resolve` 双层校验
9. 报告主区 + 追溯面板报告 tab 都有【导出 md / 导出 html】双按钮

### UI/UX 设计依据

UI/UX Pro Max skill 跑出的推荐：
- **Pattern**: Data-Dense Dashboard（BI 仪表盘 / 企业报告 / 运营监控）
- **Style**: 主色 `#1E40AF`（深蓝）/ 副色 `#3B82F6`（数据蓝）/ Accent `#D97706`（琥珀）/ 背景 `#F8FAFC`
- **Typography**: Plus Jakarta Sans（标题）+ Fira Code（数据等宽数字）

---

## 1. 整体架构

### 文件组织

```
src/
├── frontend/
│   ├── app.py              # 主入口，小改：注入主题 + 加导出按钮 + spinner 文案 rotation
│   ├── render.py           # 已有，加：KPI 5 卡 / section 卡片化 / action card grid / emoji 纯化（部位见 §6）
│   └── theme.py            # 【新】CSS + 字体注入 + Material Symbols + 颜色常量 + icon() 助手
├── api/
│   ├── routes.py           # 加 1 个新路由：GET /trace/{id}/export?format=md|html
│   └── exporters/          # 【新】
│       ├── __init__.py
│       ├── markdown.py     # BaseReport → md（5 场景常用字段，PD-2）
│       └── html.py         # BaseReport → html（Jinja2 + Plotly 全内嵌 + nh3 sanitize）
├── schemas/
│   └── report.py           # 小改：ReportMetadata 加 raw_quality_score 字段（PD-3 KPI 显示用）
└── agents/
    └── inspector.py        # 改 ~5-6 行：cap 前回填 raw_quality_score（latent 03_report.json 写盘问题不修，见 §3 末尾说明）
```

**变动总量**：3 个新文件（theme.py + exporters/markdown.py + exporters/html.py）+ 4 个改文件（app.py / render.py / routes.py / inspector.py / report.py / requirements.txt）。

### 数据流（v2 简化）

```
（前端）
1. 用户输入 → POST /api/v1/analyze（同步阻塞，不变）
   ↓ Streamlit spinner（带文案 rotation：「采集中...」→「分析中...」→「写作中...」→「质检中...」每 8s 切换文案）
2. analyze 返回 → render_base_report(report, trace_id) → 顶部 hero + KPI 5 卡 + 章节卡片化 + Action Card
3. 用户点【导出 md】或【导出 html】
   → 前端 httpx.get(f"{API_BASE}/trace/{trace_id}/export?format=md") 拿 bytes
   → st.download_button(data=bytes, file_name=...) 触发浏览器下载
4. 追溯面板加载历史 trace 后，报告 tab 也走同一套 hero + 导出按钮
```

**注意**：spinner 文案 rotation 不需要后端进度——只是 UI 端 `time.time()` 计时切换文本。8s 切换基于 trace 平均运行时间（采集 ~30-60s / 分析 ~60-120s / 写作 ~120-300s / 质检 ~30-60s）大致吻合。**这是视觉层的"假进度"——评委不会盯文案与真实进度的微差异**。

---

## 2. 主题系统（theme.py）

### 设计令牌（CSS 变量）

```css
:root {
  /* 颜色 */
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
  --color-border-strong: #93C5FD;
  --color-danger: #DC2626;
  --color-success: #16A34A;
  --color-warning: #D97706;

  /* 圆角 / 阴影 */
  --radius: 8px;
  --radius-lg: 12px;
  --shadow-card: 0 1px 3px rgba(15, 23, 42, 0.08), 0 1px 2px rgba(15, 23, 42, 0.04);
  --shadow-card-hover: 0 4px 12px rgba(30, 64, 175, 0.12);

  /* 字体 */
  --font-sans: 'Plus Jakarta Sans', -apple-system, 'Segoe UI', system-ui, sans-serif;
  --font-mono: 'Fira Code', 'Cascadia Code', Consolas, monospace;

  /* 过渡 */
  --transition: all 150ms cubic-bezier(0.4, 0, 0.2, 1);
}
```

### 注入方式

`theme.py::inject_theme()` 在 `app.py` 顶部 `st.set_page_config()` 之后调用一次。

```python
def inject_theme() -> None:
    """注入主题 CSS + 字体 + Material Symbols。仅 app.py 顶部调用一次。"""
    st.markdown("""
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&family=Fira+Code&display=swap" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined" rel="stylesheet">
    <style>
      :root { --color-primary: #1E40AF; ... }
      html, body, [class*="css"] { font-family: var(--font-sans); }
      .kpi-card { background: var(--color-surface); border-radius: var(--radius); ... }
      .section-card { border-left: 4px solid var(--color-primary); ... }
      .action-card { ... }
      .material-symbols-outlined { font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24; }
      /* spinner 文案 rotation 用 CSS pulse */
      .spinner-msg { animation: pulse 2s infinite; }
      @keyframes pulse { 0%,100% { opacity: 1 } 50% { opacity: 0.6 } }
    </style>
    """, unsafe_allow_html=True)
```

### Material Symbols 用法

```python
def icon(name: str, size: int = 20, color: str | None = None) -> str:
    """渲染 Material Symbol 字体图标，返回 HTML 字符串。
    用法：st.markdown(f"{icon('analytics')} 报告标题", unsafe_allow_html=True)
    图标列表：https://fonts.google.com/icons
    """
    style = f"font-size:{size}px;vertical-align:middle"
    if color:
        style += f";color:{color}"
    return f'<span class="material-symbols-outlined" style="{style}">{name}</span>'
```

---

## 3. 顶部 hero + KPI 5 卡 + Trace ID

### 顶部 hero（导出按钮区）

```
┌────────────────────────────────────────────────────────────────────┐
│ ◈ AI 驱动竞品分析系统     [⬇ 导出 Markdown]  [⬇ 导出 HTML]   │
│   多 Agent 协作 · 5 场景专业报告 · 全链路可追溯                    │
│                                       Trace: 220309-203430-a3b2c1  │
└────────────────────────────────────────────────────────────────────┘
```

实现：
- `app.py` 顶部固定 hero（`st.title` + `st.caption` + 主题色染色）
- 报告渲染时在 hero 下方追加导出按钮区 —— **只有 trace_id 不为空才显示**：`render_base_report(report, trace_id=trace_id)`
- 导出按钮通过 prefetch 模式实现（详见 §7）

### KPI 5 卡

```
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│ 质检评分 │ │ 场景标签 │ │ 竞品数量 │ │ 数据源数 │ │ 可信度   │
│  0.836   │ │    S3    │ │    8     │ │    24    │ │  high    │
│          │ │ 定价策略 │ │ 含3推荐  │ │ ●18 ●5 ●1│ │          │
│ 含 cap   │ │          │ │          │ │          │ │ 🟢 高    │
└──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘
（注：以上为 ASCII mock；实际 UI 中圆点用 CSS span，confidence 卡的文字颜色对应 high/medium/low）
```

**字段来源**：

| 卡片 | 数据源 | 兜底 |
|------|--------|------|
| 质检评分 | `metadata.raw_quality_score`（**新字段**）；旧 trace 回退 `metadata.quality_score` | 都为 None 时显「未质检」 |
| 场景标签 | `scenario`（S1-S5）+ 中文名 dict | — |
| 竞品数量 | `len(scope.competitors)`，副信息「含 N 推荐」从 scenario_payload (S2) 推 | 0 时显「—」 |
| 数据源数 | `len(metadata.data_sources)`，副信息分桶 high/medium/low | 0 时显「—」 |
| 可信度 | `metadata.confidence_level`（high/medium/low）+ 三色 emoji 状态点（PD-5 保留） | 必填字段不会缺 |

**Trace ID** 单独作为 caption 放在 hero 右下，有「复制到剪贴板」小按钮（用 `st.code` 自带的 copy 即可）。

### `raw_quality_score` 字段加在哪

**`src/schemas/report.py::ReportMetadata`**：
```python
class ReportMetadata(BaseModel):
    # ... 既有字段
    quality_score: float | None = Field(default=None, ge=0, le=1, ...)  # 既有：可能 cap 后
    raw_quality_score: float | None = Field(  # 【新】PD-3
        default=None,
        ge=0.0,
        le=1.0,
        description="cap 前的初始加权分（含 placeholder pass_rate 影响）。"
                    "用于 KPI 卡显示模型实际算分。命名 raw 仅指 cap 前，"
                    "不代表完全无任何惩罚——v3-R17 cap 仅是惩罚之一。"
    )
    quality_score_calculation_note: str | None = ...  # 既有
```

**`src/agents/inspector.py:387-393`**（约 5-6 行改动，PD-6 软目标）：
```python
score, note = calc_quality_score(report, unique_issues)
report.metadata.raw_quality_score = score  # 【新】先存 cap 前
if _detect_placeholder_warnings(report) and score > _QUALITY_SCORE_CAP_ON_PLACEHOLDER:
    note = f"{note}; capped to {_QUALITY_SCORE_CAP_ON_PLACEHOLDER} due to placeholder warnings (v3-R17)"
    score = _QUALITY_SCORE_CAP_ON_PLACEHOLDER
report.metadata.quality_score = score
report.metadata.quality_score_calculation_note = note
```

### Latent 03_report.json 落盘问题（v2 范围外）

**问题**：当前 03_report.json 在 writer 节点结束时落盘，inspector 后续修改 metadata 仅作用于内存对象——所以 03_report.json 落盘的 `quality_score` 永远是 None（实测 v1 doubt-driven 阶段已确认）。

**v2 决策**：**放弃 latent 修复**。理由：
- 若修，需让 InspectorAgent 持有 trace_writer 引用 + builder 改实例化 + inspector 写完调 save_stage 覆盖，~15 行改动，超出 PD-6 软目标
- 不修不影响主路径 KPI 卡：`/analyze` 实时返回的 report 是**内存对象**，`raw_quality_score` 和 `quality_score` 都正确
- 仅影响追溯面板读历史 trace 的场景；旧 trace 看 quality_score=None 已经是历史现状，用户已习惯

**KPI 卡 fallback 策略**：`raw_quality_score → quality_score → "未质检"`，三档兜底。新跑 trace 走前两档；老 trace 走第三档显示「未质检」（与现状一致）。

如果 Cooper 后续发现追溯面板需要看真实分数，单独修不阻塞本 spec。

---

## 4. 输入区（v2 不重做，仅样式调整）

`app.py` 输入区结构保留（selectbox + text_input + button），仅注入主题色后视觉自动升级（按钮主色边框 + hover 过渡 + 字体替换）。

**v1 v2 差异**：v1 写「场景卡片化重做」（5 个 st.button + 嵌套 HTML 卡片），doubt-driven Codex#9 验证 `st.button` 不支持 `unsafe_allow_html` 嵌套 HTML，重做交互层成本超出 v2 范围。**v2 范围决策舍弃此项**。

视觉升级范围：
- selectbox 自动继承 `--color-primary` border
- `st.button("开始分析", type="primary")` 主色按钮（已用，仅主题色注入后变深蓝）
- 表单容器加 `st.container(border=True)` 卡片化包裹（Streamlit 1.31+ 原生支持）

---

## 5. Loading（v2 PD-1 决策：放弃阶段化）

`app.py` 的 `with st.spinner("正在分析中，请稍候..."):` 替换为带 rotation 的文案：

```python
import time
import threading

def _spinner_with_rotation():
    """文案每 8s 切换一次，模拟阶段感。仅前端动效，不接后端进度。"""
    msgs = [
        "正在采集竞品资料...",
        "信息分析中：识别 SWOT、对标维度...",
        "撰写报告中：执行摘要、深度章节...",
        "质检中：溯源核对、内容完整性检查...",
    ]
    placeholder = st.empty()
    start = time.time()
    while True:
        idx = min(int((time.time() - start) / 8), len(msgs) - 1)
        placeholder.markdown(f"<div class='spinner-msg'>⏱ {msgs[idx]}</div>", unsafe_allow_html=True)
        time.sleep(1)
        # 主线程同步阻塞到 analyze 返回，本函数永不返回到这里——靠 st.empty 的渲染机制刷新即可
```

**实施细节**：因为 `httpx.post` 是同步阻塞，主线程没机会跑文案 rotation。可选方案：
- **a. 仅写 4 段静态描述堆叠**（简单；评委看不出 rotation）：`st.markdown` 4 行文案 + spinner，不动
- **b. 用 `st.empty()` placeholder + threading**（C2 风险已避——不轮询后端，仅 UI 刷文本，session_state 不写）：开 worker thread 跑 httpx.post，主线程 while 循环刷文案直到 result 就绪
- **c. 接受现状 spinner 单文案**

**推荐 a**：最简最稳。视觉妥协但 0 风险。

```python
# app.py 内
with st.spinner("正在分析中，请稍候（5-15 分钟）..."):
    st.markdown("""
    <div style="margin-top:16px;color:var(--color-text-secondary);font-size:14px;line-height:1.8">
      <div>· 采集 Agent 正在搜索竞品公开信息</div>
      <div>· 分析 Agent 将识别 SWOT 与对标维度</div>
      <div>· 写作 Agent 撰写专业报告 4 阶段</div>
      <div>· 质检 Agent 溯源核对、内容完整性检查</div>
    </div>
    """, unsafe_allow_html=True)
    response = httpx.post(...)
```

---

## 6. 报告区美化

### 顶部 hero + KPI 5 卡

报告渲染时 `render_base_report(report, trace_id=...)` 顶部依次：
1. hero（产品名 + 副标题 + 导出双按钮 + Trace ID）
2. KPI 5 卡
3. 报告 title / subtitle / at_a_glance / executive_summary

### Section 卡片化

每个 `analysis_sections` 项渲染为带主色左 4px 染色块的卡片：
```
┌┃ ◇ vendor_profiles  竞品画像（Forrester Wave 风格）─────────────┐
│  [narrative 文本]                                                │
│  来源：[链接1] · [链接2]                                          │
└──────────────────────────────────────────────────────────────────┘
```

**实现**：用 `st.container(border=True)` + 自定义 CSS class `.section-card`（CSS 选择器靠 `[data-testid="stVerticalBlock"]` 匹配）。

### Action Card grid

`recommendations` 现状是 `st.markdown("- ...")` 平铺，改为 timeline 分组 + 每组卡片 grid（`st.columns(2)`）：

```
─ 即时（1 个月内）────────────────────────────────────────────────
┌──────────────────────┐ ┌──────────────────────┐
│ 重要 ┃ 产品负责       │ │ 考虑 ┃ 推广负责       │
│ 调整 GBB 中档套餐     │ │ 补 X 场景 case 研究    │
│ 依据：竞品价位        │ │ 依据：业务圈担忧      │
│ 来源：[链接1]         │ │ 来源：[链接2]         │
└──────────────────────┘ └──────────────────────┘
```

priority 用左侧 4px 染色条（critical=danger / important=warning / consider=primary）。

### emoji 替换清单（PD-5 选择性纯化）

需替换为 Material Symbols 的位置（标题 / 导航 / 剩头）：

| 位置 | 当前 emoji | 替换为 |
|------|-----------|--------|
| `app.py:24` AI 选场景按钮前缀 | 无（仅按钮文字） | `auto_awesome` 图标 |
| `render.py` Section heading 前 | 无 | 各 section_type 对应图标（vendor_profiles=`groups` / market_sizing=`pie_chart` / ...） |
| `render.py` 报告 hero 前缀 | 无 | `analytics` 图标 |
| Hero 导出按钮 | 无 | `download` 图标 |
| 「未质检」KPI 卡 fallback | `—` 文字 | `help_outline` 图标（次要） |

保留的 emoji 位置（KPI / badge / 状态点）：

| 位置 | 当前 emoji | 处理 |
|------|-----------|------|
| `app.py:49` AI 推荐场景置信度 | `🟢🟡🟠` | **保留**（语义性状态点） |
| `render.py:339` recommendations priority badge | `🔴🟡🟢` | **保留**（视觉一致与现有体验） |
| `render.py:365` appendix data_sources confidence | `🟢🟡🟠` | **保留** |
| `render.py:746` S3 packaging 推荐套餐 | `⭐` | **保留**（推荐角标语义） |
| `render.py:908` S4 trends 方向 | `↑↓→` | **保留**（数据指示性） |
| `render.py:997, 1050` S5 watermark | `⚠️` | **保留**（警告语义） |

**lint check（M6 修入）**：在 CI 加一行 `grep` 检查 src/frontend 不出现「未在白名单内的新 emoji」——具体清单写到 `tests/test_emoji_lint.py`，单测形式更友好。

---

## 7. 报告导出

### 后端 GET /api/v1/trace/{trace_id}/export

```python
from typing import Literal
from src.api.exporters.markdown import render_markdown
from src.api.exporters.html import render_html

@router.get("/trace/{trace_id}/export")
async def export_trace(trace_id: str, format: Literal["md", "html"] = "md"):
    # 复用 /trace/{id} 的双层路径穿越防护
    if not _TRACE_RE.fullmatch(trace_id):
        raise HTTPException(404, "trace not found")
    base = runs_dir()
    trace_dir = (base / trace_id).resolve()
    if base.resolve() not in trace_dir.parents and trace_dir != base.resolve():
        raise HTTPException(404, "trace not found")
    report_path = trace_dir / "03_report.json"
    if not report_path.is_file():
        raise HTTPException(404, "report not found")

    # M10 修入：旧 trace schema 漂移容忍
    report_data = json.loads(report_path.read_text(encoding="utf-8"))
    try:
        report = BaseReport.model_validate(report_data)
        report_dict = report.model_dump()
    except ValidationError as e:
        # schema 不再严格匹配（schema_version 漂移），用 dict 模式导出 best-effort
        logger.warning("[export] BaseReport.model_validate failed for %s, using dict fallback: %s", trace_id, e)
        report_dict = report_data

    if format == "md":
        body = render_markdown(report_dict, trace_id=trace_id)
        return Response(content=body, media_type="text/markdown; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="report-{trace_id}.md"'})
    else:
        body = render_html(report_dict, trace_id=trace_id)
        return Response(content=body, media_type="text/html; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="report-{trace_id}.html"'})
```

**说明**：导出函数接收 dict 不接收 BaseReport——便于旧 trace 兜底。dict 字段访问用 `.get("key", default)` 防 KeyError。

### Markdown 渲染（exporters/markdown.py，PD-2 常用字段）

策略：纯字符串拼接 + format 模板，零模板引擎。结构按 BaseReport schema 顺序：

```python
def render_markdown(report: dict, *, trace_id: str) -> str:
    parts: list[str] = []
    title = report.get("title", "竞品分析报告")
    subtitle = report.get("subtitle", "")
    parts.append(f"# {title}")
    if subtitle:
        parts.append(f"_{subtitle}_")
    parts.append(f"\n> Trace ID: `{trace_id}` · 生成于 {datetime.now(_BEIJING).strftime('%Y-%m-%d %H:%M')}\n")

    # at_a_glance
    aag = report.get("at_a_glance") or []
    if aag:
        parts.append("## 一图看懂\n")
        for it in aag:
            parts.append(f"- {it}")

    # executive_summary 5 段
    es = report.get("executive_summary") or {}
    if es:
        parts.append("\n## 执行摘要")
        for label, key in [("背景定位", "context"), ("核心论断", "core_thesis"),
                           ("现实启示", "implications")]:
            v = es.get(key, "")
            if v:
                parts.append(f"\n### {label}\n{v}")
        kfb = es.get("key_findings_brief") or []
        if kfb:
            parts.append("\n### 关键发现速览\n")
            for f in kfb:
                parts.append(f"- {f}")
        pf = es.get("path_forward") or []
        if pf:
            parts.append("\n### 行动路径\n")
            for p in pf:
                parts.append(f"- {p}")

    # ... scope / methodology / key_findings / analysis_sections / swot / recommendations
    # ... appendix

    # 5 场景 payload
    payload = report.get("scenario_payload") or {}
    scenario_type = payload.get("scenario_type", "")
    fn = _SCENARIO_MD_RENDERERS.get(scenario_type)
    if fn:
        parts.append(f"\n## 场景专属：{scenario_type}\n")
        parts.append(fn(payload))

    parts.append(f"\n---\n*由 AI 驱动竞品分析 Agent 协作系统生成 · trace `{trace_id}`*")
    return "\n".join(parts)
```

5 场景 payload 各写一个 `_render_sN_md(payload: dict) -> str`，按各 schema 的**关键字段**（PD-2 宽松覆盖）输出表格 + 列表。例：

```python
def _render_s1_md(p: dict) -> str:
    out = []
    vps = p.get("vendor_profiles") or []
    if vps:
        out.append("\n### 竞品画像（Forrester Wave）\n")
        out.append("| 竞品 | 波次定位 | 一句话 | 最佳适配 |")
        out.append("|------|----------|--------|----------|")
        for v in vps:
            out.append(f"| {v.get('competitor_name','')} | {v.get('wave_position','')} | "
                       f"{v.get('one_line_pitch','')} | {v.get('best_fit_for','')} |")
    fm = p.get("feature_matrix") or {}
    if fm.get("categories"):
        out.append("\n### 功能矩阵\n")
        # ... 略
    rs = p.get("radar_scores") or []
    if rs:
        out.append("\n### 5 维评分（雷达图数据）\n")
        out.append("| 竞品 | 功能广度 | 易用性 | 性价比 | 稳定性 | 设计质量 |")
        # ...
    out.append("\n> 注：可视化图表（雷达图）见 HTML 版本")
    return "\n".join(out)
```

S2/S3/S4/S5 同样模式 — 每个 ~50-80 行覆盖关键字段（vendor_profiles / market_sizing / packaging / threats / vendor_profiles+perceptual_map+strategy_canvas）。

### HTML 渲染（exporters/html.py，PD-4 全内嵌 + C5 sanitize）

依赖：
- `jinja2` —— 模板引擎，autoescape 默认开
- `markdown` —— narrative 字段是 markdown 文本，转 html
- `nh3` —— HTML sanitizer（C5 stored XSS 防护，纯 Python wrapper of Rust ammonia）
- `plotly` —— `fig.to_html(include_plotlyjs=True)` 全内嵌（PD-4）

```python
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
import jinja2
import markdown as md_lib
import nh3
import plotly.graph_objects as go

# 字体 base64（PD-4 离线 100%）—— 构建时从 fonts/ 加载，启动时缓存
_FONTS_DIR = Path(__file__).parent / "fonts"  # 预下载好 .woff2 字体
_FONT_BASE64_CACHE: dict[str, str] = {}

def _font_base64(name: str) -> str:
    if name not in _FONT_BASE64_CACHE:
        path = _FONTS_DIR / name
        import base64
        _FONT_BASE64_CACHE[name] = base64.b64encode(path.read_bytes()).decode()
    return _FONT_BASE64_CACHE[name]

# Jinja2 环境（autoescape 强开，C5 防 XSS）
_jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(Path(__file__).parent / "templates"),
    autoescape=True,
)

# nh3 配置：仅允许常见格式标签，禁 script / iframe / on* 等
_NH3_ALLOWED_TAGS = {"p", "br", "strong", "em", "ul", "ol", "li", "h1", "h2", "h3", "h4",
                     "blockquote", "code", "pre", "a", "table", "thead", "tbody", "tr", "th", "td"}
_NH3_ALLOWED_ATTRS = {"a": {"href", "title"}}

def _safe_markdown(text: str) -> str:
    """C5 修入：narrative 走 markdown→html→nh3 sanitize 三步保 XSS 安全。"""
    if not text:
        return ""
    raw_html = md_lib.markdown(text, extensions=["extra"])
    return nh3.clean(raw_html, tags=_NH3_ALLOWED_TAGS, attributes=_NH3_ALLOWED_ATTRS)

# Jinja2 filter
_jinja_env.filters["safe_md"] = _safe_markdown

# Plotly 图表全内嵌（仅第 1 张引 Plotly 库；后续 include_plotlyjs=False）
def _embed_plotly(fig: "go.Figure | None", first: bool) -> str:
    if fig is None:
        return ""
    return fig.to_html(include_plotlyjs=first, full_html=False, div_id=None)

def render_html(report: dict, *, trace_id: str) -> str:
    """主入口。"""
    template = _jinja_env.get_template("report.html.j2")

    # 5 场景图表预生成
    payload = report.get("scenario_payload") or {}
    scenario_type = payload.get("scenario_type", "")
    plotly_html_first = ""  # 第一张图带 plotly.js
    plotly_charts: list[str] = []
    if scenario_type == "S1":
        from src.frontend.render import _radar_chart_s1
        fig = _radar_chart_s1(payload.get("radar_scores") or [])
        plotly_html_first = _embed_plotly(fig, first=True)
    elif scenario_type == "S2":
        from src.frontend.render import _radar_chart_five_forces
        fig = _radar_chart_five_forces(payload.get("five_forces") or {})
        plotly_html_first = _embed_plotly(fig, first=True)
    elif scenario_type == "S5":
        from src.frontend.render import _scatter_perceptual_map, _scatter_magic_quadrant, _line_strategy_canvas
        fig1 = _scatter_perceptual_map(payload.get("perceptual_map") or {})
        fig2 = _scatter_magic_quadrant(payload.get("vendor_profiles") or [])
        fig3 = _line_strategy_canvas(payload.get("strategy_canvas") or {})
        plotly_html_first = _embed_plotly(fig1, first=True)
        plotly_charts.append(_embed_plotly(fig2, first=False))
        plotly_charts.append(_embed_plotly(fig3, first=False))

    return template.render(
        report=report,
        trace_id=trace_id,
        scenario_type=scenario_type,
        plotly_first=plotly_html_first,
        plotly_more=plotly_charts,
        font_jakarta=_font_base64("PlusJakartaSans-Regular.woff2"),
        font_jakarta_bold=_font_base64("PlusJakartaSans-Bold.woff2"),
        font_fira=_font_base64("FiraCode-Regular.woff2"),
        generated_at=datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M"),
    )
```

### Jinja2 模板（templates/report.html.j2）

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <title>{{ report.title or "竞品分析报告" }}</title>
  <style>
    @font-face {
      font-family: 'Plus Jakarta Sans';
      src: url(data:font/woff2;base64,{{ font_jakarta }}) format('woff2');
      font-weight: 400;
    }
    @font-face {
      font-family: 'Plus Jakarta Sans';
      src: url(data:font/woff2;base64,{{ font_jakarta_bold }}) format('woff2');
      font-weight: 700;
    }
    @font-face {
      font-family: 'Fira Code';
      src: url(data:font/woff2;base64,{{ font_fira }}) format('woff2');
    }
    :root { --color-primary: #1E40AF; --color-accent: #D97706; --color-bg: #F8FAFC; --color-surface: #FFF; }
    body { font-family: 'Plus Jakarta Sans', sans-serif; background: var(--color-bg); padding: 32px; max-width: 1200px; margin: 0 auto; color: #0F172A; }
    .hero { margin-bottom: 24px; padding: 24px; background: var(--color-surface); border-left: 4px solid var(--color-primary); border-radius: 8px; }
    .hero h1 { margin: 0 0 8px; color: var(--color-primary); }
    .kpi-strip { display: grid; grid-template-columns: repeat(5, 1fr); gap: 16px; margin: 24px 0; }
    .kpi-card { background: var(--color-surface); padding: 16px; border-radius: 8px; box-shadow: 0 1px 3px rgba(15,23,42,0.08); }
    .section-card { background: var(--color-surface); margin: 16px 0; padding: 20px; border-left: 4px solid var(--color-primary); border-radius: 8px; }
    .action-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 16px; }
    .action-card { background: var(--color-surface); padding: 16px; border-radius: 8px; border-left: 4px solid var(--color-accent); }
    table { border-collapse: collapse; width: 100%; margin: 12px 0; }
    th, td { border: 1px solid #DBEAFE; padding: 8px 12px; text-align: left; }
    th { background: #E9EEF6; }
    .num { font-family: 'Fira Code', monospace; }
    @media print { .no-print { display: none } }
  </style>
</head>
<body>
  <div class="hero">
    <h1>{{ report.title or "竞品分析报告" }}</h1>
    {% if report.subtitle %}<p>{{ report.subtitle }}</p>{% endif %}
    <small class="num">Trace: {{ trace_id }} · 生成于 {{ generated_at }}</small>
  </div>

  <!-- KPI 5 卡 -->
  {% set meta = report.metadata or {} %}
  <div class="kpi-strip">
    <div class="kpi-card">
      <small>质检评分</small>
      <div class="num" style="font-size:24px;color:var(--color-primary)">
        {{ "%.3f"|format(meta.raw_quality_score or meta.quality_score or 0) if (meta.raw_quality_score or meta.quality_score) else "—" }}
      </div>
    </div>
    <div class="kpi-card">
      <small>场景标签</small>
      <div style="font-size:24px;color:var(--color-primary)">{{ meta.scenario or "—" }}</div>
    </div>
    <div class="kpi-card">
      <small>竞品数量</small>
      <div class="num" style="font-size:24px">{{ (report.scope.competitors or [])|length }}</div>
    </div>
    <div class="kpi-card">
      <small>数据源数</small>
      <div class="num" style="font-size:24px">{{ (meta.data_sources or [])|length }}</div>
    </div>
    <div class="kpi-card">
      <small>可信度</small>
      <div style="font-size:24px;color:var(--color-primary)">{{ meta.confidence_level or "—" }}</div>
    </div>
  </div>

  <!-- 执行摘要 -->
  {% if report.executive_summary %}
    <h2>执行摘要</h2>
    {% set es = report.executive_summary %}
    {% if es.context %}<h3>背景定位</h3><div>{{ es.context | safe_md }}</div>{% endif %}
    {% if es.core_thesis %}<h3>核心论断</h3><div>{{ es.core_thesis | safe_md }}</div>{% endif %}
    {% if es.implications %}<h3>现实启示</h3><div>{{ es.implications | safe_md }}</div>{% endif %}
  {% endif %}

  <!-- 详细章节卡片 -->
  {% for section in (report.analysis_sections or []) %}
    <div class="section-card">
      <h2>{{ section.heading }}</h2>
      <small>{{ section.section_type }}</small>
      <div>{{ section.narrative | safe_md }}</div>
      {% if section.source_refs %}
        <small>来源：
          {% for ref in section.source_refs %}
            <a href="{{ ref.url }}">{{ ref.title or ref.url }}</a>{% if not loop.last %} · {% endif %}
          {% endfor %}
        </small>
      {% endif %}
    </div>
  {% endfor %}

  <!-- SWOT / Recommendations / Appendix（略，同模式渲染） -->

  <!-- 5 场景图表 -->
  {% if plotly_first %}
    <h2>场景专属可视化（{{ scenario_type }}）</h2>
    <div>{{ plotly_first | safe }}</div>
    {% for chart in plotly_more %}
      <div>{{ chart | safe }}</div>
    {% endfor %}
  {% endif %}

  <hr>
  <small>由 AI 驱动竞品分析 Agent 协作系统生成</small>
</body>
</html>
```

### 字体 .woff2 文件来源

构建时手动下载 3 个 woff2 到 `src/api/exporters/fonts/`：
- `PlusJakartaSans-Regular.woff2`（~30KB）
- `PlusJakartaSans-Bold.woff2`（~30KB）
- `FiraCode-Regular.woff2`（~50KB）

总 ~100KB，加 Plotly.js 单 ~3MB，加报告内容 ~500KB → 单 HTML 总 **3-4MB**（PD-4 接受范围）。

下载源：
- Plus Jakarta Sans: https://fonts.google.com/specimen/Plus+Jakarta+Sans
- Fira Code: https://fonts.google.com/specimen/Fira+Code

放 `.gitignore` 之外（要 commit 进 repo，evaluator 拿到 repo 即可跑）。

### 前端导出按钮（M1-M2 修入）

`render.py::render_base_report` 签名改：

```python
def render_base_report(report: dict, *, trace_id: str | None = None) -> None:
    ...
    if trace_id:
        _render_export_buttons(trace_id)
    ...
```

`_render_export_buttons(trace_id)` 实现：

```python
def _render_export_buttons(trace_id: str) -> None:
    """报告区顶部双按钮。预拉 bytes（M1：st.download_button 不接 lazy）。"""
    col1, col2, _ = st.columns([1, 1, 4])
    with col1:
        if st.button("下载 Markdown", key=f"prep_md_{trace_id}", use_container_width=True):
            try:
                r = httpx.get(f"{API_BASE}/trace/{trace_id}/export?format=md", timeout=30)
                r.raise_for_status()
                st.session_state[f"md_bytes_{trace_id}"] = r.content
            except Exception as e:
                st.error(f"导出 markdown 失败：{e}")
        if f"md_bytes_{trace_id}" in st.session_state:
            st.download_button(
                "确认下载 Markdown",
                data=st.session_state[f"md_bytes_{trace_id}"],
                file_name=f"report-{trace_id}.md",
                mime="text/markdown",
                key=f"dl_md_{trace_id}",
                use_container_width=True,
            )
    with col2:
        # 同 markdown
        if st.button("下载 HTML", key=f"prep_html_{trace_id}"):
            ...
```

**为什么是「双步」**：`st.download_button` 第一次 render 必须有 data 参数（不能 lazy）。最简模式是预拉到 session_state 后**再**显示真正的 download_button。两次点击：先「拉取」后「下载」。

**优化（可选）**：Cooper 觉得双步丑可以改为单步——直接用 `st.markdown(f'<a href="{API_BASE}/trace/{trace_id}/export?format=md" download>下载 Markdown</a>')`，浏览器原生下载。Streamlit 不会拦原生 a 标签的 download 属性。这条更优雅，**v2 推荐用这条**：

```python
def _render_export_buttons(trace_id: str) -> None:
    """直链下载（HTML <a download>，浏览器原生）"""
    md_link = f'<a href="{API_BASE}/trace/{trace_id}/export?format=md" download '\
              f'class="btn-export"><span class="material-symbols-outlined">download</span> 导出 Markdown</a>'
    html_link = f'<a href="{API_BASE}/trace/{trace_id}/export?format=html" download '\
                f'class="btn-export"><span class="material-symbols-outlined">download</span> 导出 HTML</a>'
    st.markdown(f'<div style="display:flex;gap:12px">{md_link} {html_link}</div>', unsafe_allow_html=True)
```

CSS class `.btn-export` 用主题色 + hover：
```css
.btn-export {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 8px 16px; background: var(--color-primary); color: white;
  border-radius: var(--radius); text-decoration: none; font-size: 14px;
  transition: var(--transition);
}
.btn-export:hover { background: var(--color-primary-hover); }
```

**最终采用直链方案**——M1 + 单步 + 视觉一致。

### 触发点

- `render_analysis_response(data)`（render.py:1074）：拿 `data["trace_id"]` 调 `render_base_report(report, trace_id=trace_id)`
- `render_trace_report_tab(report)`（render.py:1111）：签名加 `trace_id` 参数；`app.py:170` 调用处传 `trace_id=tid_input`

---

## 8. 错误处理

### 导出

| 错误情况 | 处理 |
|---------|------|
| 03_report.json 不存在 | 返回 404 + 中文提示「该 trace 未产出报告」 |
| BaseReport.model_validate 失败 | 警告日志 + dict 模式 best-effort 导出（M10 修入） |
| Plotly to_html 报错 | catch + HTML 模板 `{% if plotly_first %}` 分支降级，其他章节正常 |
| 字体文件缺失 | exporters/__init__.py 启动时校验 fonts/*.woff2 存在；缺则 raise FileNotFoundError 拦在加载阶段 |

### 主题注入

- CSS / 字体 CDN 加载失败：fallback 到 system stack；UI 降级为「能用但样式弱」
- Material Symbols 加载失败：图标显示为字符串（如 `analytics`），可读不美

### emoji lint

`tests/test_emoji_lint.py` 在 CI 跑：扫 `src/frontend/*.py` 看 emoji 是否在白名单内（保留位置清单）；新增非白名单 emoji 测试 fail。

---

## 9. 测试策略

### 单测

| 文件 | 测试范围 |
|------|----------|
| `tests/unit/test_exporters_markdown.py` | 5 场景 fixture → 输出含关键字段 + 不崩 |
| `tests/unit/test_exporters_html.py` | 5 场景 fixture → 输出 valid HTML + 含字体 base64 + Plotly script + 不含 `<script>(?!.*plotly)` 的 LLM 注入 |
| `tests/unit/test_exporters_html_xss.py` | **新（C5 修入）**：narrative 含 `<script>alert(1)</script>` → 渲染后 nh3 strip 干净；含 `<a href="javascript:...">` → 转义 |
| `tests/unit/test_export_path_traversal.py` | **新（M7 修入）**：`trace_id="../../etc"` / `"20260610-203430-../etc"` / windows `..\\` → 全部 404 |
| `tests/unit/test_inspector_raw_quality_score.py` | 新：cap 前后 raw + final 都正确写 metadata |
| `tests/unit/test_emoji_lint.py` | 新：src/frontend 仅出现白名单 emoji |

### 集成

| 文件 | 测试范围 |
|------|----------|
| `tests/integration/test_export_e2e.py` | 5 场景 fixture trace → 调 export api → md / html 内容含关键字段 + HTML 字节大小 1-5MB（PD-4） |

### 手动验收

| 场景 | 步骤 |
|------|------|
| 主题色生效 | 启动前端 → 看到深蓝 + 琥珀色调；按钮 hover 平滑过渡 |
| KPI 5 卡 | S2 happy path → 5 卡显示 raw_quality_score=0.800 / S2 / 3 / 11 / high；S5 占位场景 → cap 信息显示 |
| 导出 md | 报告点【导出 Markdown】→ 浏览器下载 `report-<trace>.md`；编辑器打开内容完整 + markdown 格式正确 |
| 导出 html | 同点击 → 双击打开浏览器看到主题色 + 章节卡片 + Plotly 交互图表 |
| **HTML 离线测试** | 下载 html 后**断网**双击打开 → 字体 / Plotly 都正常显示（PD-4 验收要点） |
| **XSS 验证** | 手工构造一份含 `<script>alert(1)</script>` 的 fake report 文件放到 runs/test-trace/03_report.json → 调 export → 浏览器打开不弹框 |
| 追溯面板导出 | 输入历史 trace_id → 加载 → 报告 tab 顶部有【导出】双按钮 |

---

## 10. 风险 / Trade-off

| 风险 | 概率 | 影响 | 应对 |
|------|------|------|------|
| 字体 woff2 文件下载需手动 | 低 | 低 | spec §7 已说明源；评委拿到 repo 跑 setup.sh 一行下载 |
| nh3 在 Windows 上需 Rust 编译 | 低 | 中 | nh3 已发预编译 wheel for win/mac/linux × py3.10-3.13；pip install 即用，无需 Rust |
| Plotly 全内嵌 HTML 大（3-4MB） | 中 | 低 | PD-4 接受 |
| Material Symbols CDN 离线评委 | 低 | 中 | 前端展示降级（HTML 导出全内嵌不受影响） |
| 5 场景 markdown 字段不全 | 中 | 低 | PD-2 宽松接受；单测仅断关键字段 |
| raw_quality_score 历史 trace 兼容 | 高 | 低 | Optional + None fallback `quality_score` |
| inspector latent 03_report.json 写不全 | 中 | 低 | spec 说明放弃 latent 修复；KPI 卡走内存 report 不读盘 |

---

## 11. 实现 Task 拆分（writing-plans 用，file/function 级，M12 修入）

按依赖关系顺序：

1. **schema** — `src/schemas/report.py::ReportMetadata` 加 `raw_quality_score` 字段（5 行）
2. **inspector 回填** — `src/agents/inspector.py:387-393` 改 `inspect()` 方法 cap 前回填 raw_quality_score（~5-6 行 PD-6）
3. **theme.py** — 新建 `src/frontend/theme.py`：`inject_theme()` + `icon(name, size, color)` 助手 + CSS 变量字符串
4. **app.py 调用 theme** — `src/frontend/app.py:9` `st.set_page_config` 后插入 `from theme import inject_theme; inject_theme()`
5. **render.py KPI 5 卡** — 新增 `_render_kpi_strip(report: dict)` 函数；`render_base_report(report, *, trace_id=None)` 签名加 trace_id；调用顺序 `_render_kpi_strip` → `_render_export_buttons`
6. **render.py Section 卡片化** — 改 `_render_analysis_sections`，每 section 用 `st.container(border=True)` 包裹 + 注入 CSS class
7. **render.py Action Card grid** — 改 `_render_recommendations`，timeline 分组改为 `st.columns(2)` grid
8. **render.py 导出按钮** — 新增 `_render_export_buttons(trace_id)`：直链 `<a download>` 双按钮（§7 末尾代码）
9. **render.py emoji 替换** — 按 §6 清单改替换标题/导航位置；保留位置不动
10. **render_trace_report_tab 签名** — `render.py:1111` 加 `trace_id` 参数；`app.py:170` 调用处补传
11. **后端 exporters 字体** — `src/api/exporters/fonts/` 目录 + 3 个 woff2 文件 + `_font_base64()` 辅助
12. **exporters/markdown.py** — `render_markdown(report, *, trace_id) -> str` + 5 个 `_render_sN_md(p)` 函数
13. **exporters/html.py** — `render_html(report, *, trace_id) -> str` + Jinja2 env 配置 + nh3 sanitize + Plotly 内嵌
14. **exporters/templates/report.html.j2** — 主模板（§7 已贴）
15. **后端 routes.py** — `GET /trace/{id}/export?format=md|html` 路由（§7 已贴）
16. **requirements.txt** — 加 `markdown>=3.6` `jinja2>=3.1` `nh3>=0.2`
17. **测试** — 6 个新测试文件（§9）
18. **手动验收** — §9 末尾 7 项清单

每个 task 1 个 commit，约 18 commits。预计工时 3-4 小时。

---

## 12. 不做的事（YAGNI / v2 范围外）

- ❌ Loading 阶段化（PD-1，与 trace_writer 时序不兼容；评委不会发现差异）
- ❌ 场景卡片化重做（M3：st.button 不支持嵌套 HTML，重做交互层超 v2 范围）
- ❌ PDF 导出（依赖重 + 中文字体麻烦）
- ❌ DOCX 导出（python-docx 与 Plotly 兼容差）
- ❌ 主题切换（暗色模式）
- ❌ 重做前端为 React / Vue
- ❌ 后端 SSE / WebSocket / BackgroundTasks
- ❌ inspector 回写 03_report.json（latent issue 放弃修，因为 ~15 行改动超 PD-6 范围；KPI 卡用内存 report 即可）
- ❌ 5 场景 markdown 「no field omission」（PD-2 已放宽为「关键字段覆盖」）
