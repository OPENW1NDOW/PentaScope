# PentaScope 前端迁移规格说明书

> Streamlit → Next.js · Notion 风格 · 2026-06-25

---

## 一、背景与目标

### 1.1 当前状态

PentaScope 前端基于 Streamlit（4 文件 ~1900 行）：

| 文件 | 行数 | 职责 |
|------|------|------|
| `src/frontend/app.py` | 196 | 入口：输入表单 + API 调用 + session state |
| `src/frontend/render.py` | 1468 | 报告渲染：BaseReport + 5 场景 Payload + Plotly 图表 |
| `src/frontend/theme.py` | 224 | CSS 设计系统：颜色 token + 组件样式 |

### 1.2 核心限制

1. **无实时进度** — 分析请求阻塞最长 3600s，UI 完全冻结，无 Agent 状态反馈
2. **无路由/历史** — 单页应用，无法保存/回看历史分析
3. **图表不可交互** — Plotly `staticPlot=True`，表格不可排序过滤
4. **全量隐藏数据** — CriticScores、PESTEL、PricingPageAudit、CompetitorProfile 等丰富数据仅以 raw JSON 呈现

### 1.3 目标

- 迁移到 **React + Next.js**（App Router）
- **Notion 风格**设计系统（暖白底、棕黑文字、系统字体、pastel 标签）
- 新增三大功能：**实时进度**、**多页面路由 + 历史**、**交互式图表**
- Streamlit 前端保留不删除，作为备用

---

## 二、后端改造（Python 侧）

### 2.1 CORS 中间件

**修改文件**：`src/api/main.py`

```python
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 2.2 SSE 实时进度端点

**新增端点**：`GET /api/v1/analyze/{trace_id}/stream`

**SSE 事件格式**：
```
event: node_start
data: {"node": "collector", "timestamp": "...", "message": "开始采集竞品数据..."}

event: node_complete
data: {"node": "collector", "timestamp": "...", "duration_ms": 12345}

event: analysis_complete
data: {"trace_id": "...", "status": "completed"}
```

**实现**：`asyncio.Queue` + `StreamingResponse`，trace_id 作为关联键。

**修改文件**：
- `src/api/routes.py` — SSE 端点
- `src/graph/builder.py` — 节点前后注入进度
- `src/graph/state.py` — 新增 `progress_queue` 字段

### 2.3 历史分析列表端点

**新增端点**：`GET /api/v1/traces?page=1&page_size=20`

扫描 `runs/` 目录，读取 `meta.json`，返回摘要列表。

### 2.4 配置项

**修改文件**：`src/utils/config.py` — 新增 `FRONTEND_ORIGIN`

---

## 三、前端工程

### 3.1 项目结构

```
frontend/
├── package.json
├── next.config.ts
├── tailwind.config.ts
├── tsconfig.json
├── src/
│   ├── app/                    # Next.js App Router
│   │   ├── layout.tsx          # Root layout (sidebar + providers)
│   │   ├── page.tsx            # 首页 / 新建分析
│   │   ├── analyze/
│   │   │   └── [traceId]/
│   │   │       └── page.tsx    # 分析进行中 / 结果页
│   │   └── history/
│   │       └── page.tsx        # 历史分析列表
│   ├── components/
│   │   ├── ui/                 # shadcn/ui 基础组件
│   │   ├── layout/             # Sidebar, Header, PageContainer
│   │   ├── analysis/           # 分析表单、进度条、Agent 状态
│   │   ├── report/             # 报告渲染组件
│   │   │   ├── KpiStrip.tsx
│   │   │   ├── ExecutiveSummary.tsx
│   │   │   ├── KeyFindings.tsx
│   │   │   ├── SwotGrid.tsx
│   │   │   ├── Recommendations.tsx
│   │   │   ├── ScenarioPayload.tsx
│   │   │   ├── s1/ s2/ s3/ s4/ s5/
│   │   └── charts/             # Recharts 图表
│   │       ├── RadarChart.tsx
│   │       ├── PerceptualMap.tsx
│   │       ├── MagicQuadrant.tsx
│   │       └── StrategyCanvas.tsx
│   ├── lib/
│   │   ├── api.ts              # API 客户端
│   │   ├── sse.ts              # SSE 连接管理
│   │   ├── translations.ts     # 翻译映射表
│   │   └── utils.ts
│   ├── hooks/
│   │   ├── useAnalysis.ts
│   │   ├── useSSE.ts
│   │   └── useTraces.ts
│   ├── types/
│   │   ├── report.ts           # BaseReport TypeScript 类型
│   │   ├── scenarios.ts        # S1-S5 payload 类型
│   │   └── api.ts
│   └── styles/
│       └── globals.css         # Tailwind + design tokens
├── public/
│   └── fonts/
└── .env.local                  # NEXT_PUBLIC_API_URL
```

### 3.2 技术栈

| 层级 | 选择 | 理由 |
|------|------|------|
| 框架 | Next.js 15 (App Router) | 文件路由、RSC、SSR 灵活 |
| 样式 | Tailwind CSS 4 | 原子化、与 shadcn/ui 集成 |
| 组件库 | shadcn/ui | 可复制、可定制、无运行时 |
| 图表 | Recharts | React 原生、声明式、交互 |
| 表格 | @tanstack/react-table | 排序/过滤/分页 |
| 状态 | Zustand | 轻量、TypeScript 友好 |
| HTTP | 原生 fetch + SWR | 缓存、重试 |
| Markdown | react-markdown + remark-gfm | 安全渲染 LLM Markdown |
| 图标 | Lucide React | 与 shadcn/ui 配套 |

---

## 四、设计系统（Notion 风格）

### 4.1 色彩

```css
:root {
  /* 背景 */
  --bg-page:     #F7F6F3;    /* Notion 暖白底 */
  --bg-surface:  #FFFFFF;
  --bg-hover:    rgba(55,53,47,0.04);
  --bg-selected: rgba(55,53,47,0.08);

  /* 文字 */
  --text-primary:   #37352F; /* Notion 棕黑 */
  --text-secondary: #787774;
  --text-tertiary:  #B4B4B0;

  /* 边框 */
  --border:        #E9E9E7;
  --divider:       #F1F1EF;
  --border-active: #2EAADC;

  /* 标签色 — 9 色 pastel */
  --tag-gray:   #E3E2E0; --tag-gray-text:   #3B3B3B;
  --tag-brown:  #ECE4D6; --tag-brown-text:  #5C3B10;
  --tag-orange: #FADEC9; --tag-orange-text: #5C3B10;
  --tag-yellow: #FDECC8; --tag-yellow-text: #5C3B10;
  --tag-green:  #DBEDDB; --tag-green-text:  #1C3829;
  --tag-blue:   #D3E5EF; --tag-blue-text:   #183347;
  --tag-purple: #E8DEEE; --tag-purple-text: #3C1F64;
  --tag-pink:   #F5E0E9; --tag-pink-text:   #4C1932;
  --tag-red:    #FFE2DD; --tag-red-text:    #601C18;

  /* 语义色 */
  --success: #4DAB9A; --warning: #E9973F; --danger: #D44C47; --info: #2EAADC;
}
```

### 4.2 排版

```css
--font-sans: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans SC',
             'Helvetica Neue', Helvetica, Arial, sans-serif;
--font-mono: 'Fira Code', 'Cascadia Code', 'JetBrains Mono', 'SF Mono', Menlo, monospace;

--text-3xl:  32px;  /* 页面标题 */
--text-2xl:  24px;  /* 区块标题 */
--text-xl:   20px;  /* 子标题 */
--text-base: 15px;  /* 正文 */
--text-sm:   13px;  /* 辅助/表格 */
--text-xs:   12px;  /* 标签 */
```

### 4.3 间距

4px 网格：4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64px

### 4.4 圆角 & 阴影

```css
--radius-sm: 3px; --radius-md: 4px; --radius-lg: 6px;
--shadow-sm: none;
--shadow-md: 0 1px 3px rgba(0,0,0,0.04);  /* 仅弹窗 */
```

**关键**：Notion 用背景色差 + 边框分隔层级，不用阴影。

### 4.5 图表色板

```javascript
const CHART_COLORS = ['#2EAADC', '#4DAB9A', '#E9973F', '#D44C47', '#9A6DD7', '#E255A1'];
```

---

## 五、页面设计

### 5.1 首页 — 新建分析 `/`

- 5 张场景选择卡片（S1-S5），选中高亮
- "AI 帮我选场景" 按钮 → 调用 `/pick-scenario`
- 动态表单（S2 显示 industry，S4 显示 prior_trace_id）
- 提交后跳转 `/analyze/{traceId}`

### 5.2 分析页 — `/analyze/[traceId]`

**阶段一：进行中**
- Agent 流水线步骤条（recommender → collector → analyzer → writer → inspector）
- 当前节点脉动动画，已完成 ✓ + 耗时
- 实时日志流面板
- SSE 连接管理

**阶段二：完成**
- 成功 → 渲染完整报告
- 失败 → 错误卡片 + 重试按钮

### 5.3 报告页 — 复用 `/analyze/[traceId]`

左侧 sticky 目录导航，右侧滚动内容区。

区块顺序与 Streamlit `render.py::render_base_report` 对齐（2026-06-23 拍板：scenario_payload 在 analysis_sections 之后、SWOT 之前）：

区块顺序与 Streamlit `render.py::render_base_report` 对齐（2026-06-23 拍板：scenario_payload 在 analysis_sections 之后、SWOT 之前）：

| 序号 | 区块 | 组件 |
|------|------|------|
| 0 | 标题 + 导出 | ReportHeader（含导出双按钮） |
| 1 | KPI 指标条 | KpiStrip（属性表风格，无阴影） |
| 2 | 核心要点 | AtAGlance |
| 3 | 执行摘要 | ExecutiveSummary |
| 4 | 背景 | Background |
| 5 | 范围 & 方法论 | ScopeMethodology（折叠面板） |
| 6 | 关键发现 | KeyFindings（左边框卡片） |
| 7 | 详细章节 | AnalysisSections |
| 8 | 场景负载 | ScenarioPayload（S1-S5 动态分发） |
| 9 | SWOT | SwotGrid（2×2 网格） |
| 10 | 结论 | Conclusions |
| 11 | 行动建议 | Recommendations（边框卡片 + 标签色标） |
| 12 | 附录 | Appendix（折叠面板） |
| 13 | 元数据 | MetadataPanel（含 CriticScores 评分条） |

### 5.4 历史页 — `/history`

- 表格列表（trace_id、场景、状态、时间、竞品）
- 按场景/状态筛选
- 点击跳转查看

---

## 六、API 客户端

```typescript
const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'

export const api = {
  analyze:     (input) => fetch(`${API_BASE}/analyze`, { method: 'POST', body: JSON.stringify(input) }),
  pickScenario: (text) => fetch(`${API_BASE}/pick-scenario`, { method: 'POST', body: JSON.stringify({ user_text: text }) }),
  getTrace:    (id)    => fetch(`${API_BASE}/trace/${id}`),
  getTraces:   (page)  => fetch(`${API_BASE}/traces?page=${page}`),
  exportUrl:   (id, f) => `${API_BASE}/trace/${id}/export?format=${f}`,
  sseUrl:      (id)    => `${API_BASE}/analyze/${id}/stream`,
}
```

---

## 七、实施计划

| Phase | 内容 | 周期 |
|-------|------|------|
| 1 | 后端改造（CORS + SSE + 历史列表） | ~2 天 |
| 2 | 前端骨架（Next.js 初始化 + 路由 + API + 类型） | ~3 天 |
| 3 | 报告渲染（通用骨架 + 5 场景 + 图表 + 表格） | ~4 天 |
| 4 | 交互增强（进度可视化 + 日志流 + 历史页 + 导出） | ~2 天 |
| 5 | 打磨（响应式 + 错误边界 + 新增数据渲染 + 测试） | ~2 天 |

---

## 八、验证方案

1. **后端**：curl 测试 SSE / CORS / 历史列表
2. **前端**：`npm run dev` 完整走 S1-S5 分析流程
3. **交互**：图表 hover、表格排序、SSE 断线重连
4. **对比**：同一 trace_id 在 Streamlit 和 Next.js 渲染一致
5. **性能**：Lighthouse ≥ 90
