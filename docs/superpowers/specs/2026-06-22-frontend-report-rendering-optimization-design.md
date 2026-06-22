# 前端报告渲染优化 Spec

## 背景与目标

走查 5 个场景（S1-S5）的历史报告发现前端渲染存在系统性问题：英文枚举值直接暴露给用户、排版层级混乱、渲染顺序与业务逻辑不一致、图表允许不必要的交互操作。这些问题严重影响报告的可读性和专业感。

**目标**：修复 `src/frontend/render.py` 的渲染逻辑 + `src/agents/prompts/writer/` 的 narrative prompt 约束，使报告输出对非技术用户友好、排版清晰、无英文 code value 暴露。

**验证标准**：用 trace `20260620-124502-636fd4`（S1）和 `20260619-203923-9f5681`（S5）在前端追溯面板查看，所有问题消失。

---

## 修改文件

| 文件 | 角色 |
|------|------|
| `src/frontend/render.py` | 主渲染逻辑，~15 处修改 |
| `src/frontend/theme.py` | 补充 subtitle CSS class |
| `src/agents/prompts/writer/narrative/_common.py` | narrative prompt 增加中文输出约束 |
| `src/api/exporters/templates/report.html.j2` | HTML 导出模板同步翻译/布局/去卡片 |

---

## R1：枚举值翻译系统

**位置**：`render.py` 顶部新增

在 `render.py` 中新增翻译函数 `_t(val)` 和映射表 `_TRANSLATIONS`。对所有 `st.dataframe`、`st.metric`、`st.markdown`、`st.caption`、`st.expander` label 中涉及枚举字段的输出调用 `_t()`。

`_t()` 实现约束：
- `if not val or not isinstance(val, str): return str(val) if val is not None else ""`
- 仅精确匹配 key，不做模糊/子串匹配，不会误改竞品名或自由文本
- 未命中映射表的值原样返回（passthrough）

映射表格式为 `英文 → "中文 (英文)"`：

```
high → 高 (high)
medium → 中 (medium)
low → 低 (low)
challenger → 挑战者 (challenger)
incumbent → 在位者 (incumbent)
emerging → 新兴 (emerging)
hard → 困难 (hard)
moderate → 适中 (moderate)
easy → 容易 (easy)
up → 上升 (up)
down → 下降 (down)
flat → 持平 (flat)
short_term → 短期 (short_term)
mid_term → 中期 (mid_term)
long_term → 长期 (long_term)
mixed → 混合 (mixed)
negative → 负面 (negative)
positive → 正面 (positive)
new_feature → 新功能 (new_feature)
pricing_change → 定价变更 (pricing_change)
act_now → 立即行动 (act_now)
contingency → 应急准备 (contingency)
monitor → 持续监控 (monitor)
partial → 部分 (partial)
complete → 完整 (complete)
product_gap → 产品差距 (product_gap)
critical → 紧急 (critical)
important → 重要 (important)
consider → 可选 (consider)
differentiation → 差异化 (differentiation)
niche_first → 利基优先 (niche_first)
cost_leadership → 成本领先 (cost_leadership)
unknown → 未知 (unknown)
freemium → 免费增值 (freemium)
hybrid → 混合模式 (hybrid)
subscription → 订阅制 (subscription)
wave_leader → 领导者 (wave_leader)
wave_strong_performer → 强劲表现者 (wave_strong_performer)
wave_contender → 竞争者 (wave_contender)
wave_follower → 跟随者 (wave_follower)
```

S4 变更类型补充：
```
removed_feature → 功能下架 (removed_feature)
feature_updated → 功能更新 (feature_updated)
tier_added → 新增层级 (tier_added)
tier_removed → 移除层级 (tier_removed)
price_increased → 涨价 (price_increased)
price_decreased → 降价 (price_decreased)
packaging_restructured → 套餐重组 (packaging_restructured)
discount_changed → 折扣变更 (discount_changed)
headline_changed → 标语变更 (headline_changed)
positioning_shift → 定位转变 (positioning_shift)
brand_update → 品牌更新 (brand_update)
campaign_launch → 活动上线 (campaign_launch)
funding → 融资 (funding)
partnership → 合作 (partnership)
leadership → 高管变动 (leadership)
legal → 法律/合规 (legal)
product_launch → 产品发布 (product_launch)
acquisition → 收购 (acquisition)
ipo → IPO (ipo)
layoff → 裁员 (layoff)
other → 其他 (other)
hired → 入职 (hired)
departed → 离职 (departed)
promoted → 晋升 (promoted)
demoted → 降级 (demoted)
joined_board → 加入董事会 (joined_board)
title_changed → 头衔变更 (title_changed)
founder_exit → 创始人离开 (founder_exit)
abandoned_segment → 放弃的细分市场 (abandoned_segment)
messaging_white_space → 信息空白 (messaging_white_space)
operational_weakness → 运营弱点 (operational_weakness)
deprioritize → 低优先 (deprioritize)
```

S4 battlecard section_name 补充：
```
quick_summary → 快速摘要 (quick_summary)
primary_threat → 核心威胁 (primary_threat)
why_they_win → 为何他们赢 (why_they_win)
why_we_win → 为何我们赢 (why_we_win)
landmines → 竞争陷阱 (landmines)
talk_track → 话术要点 (talk_track)
```

S5 MQ quadrant 补充（用于 dataframe 表格翻译）：
```
leaders → 领导者 (leaders)
challengers → 挑战者 (challengers)
visionaries → 远见者 (visionaries)
niche_players → 利基者 (niche_players)
```

未收录的值原样返回（不报错）。后续遇到新枚举值时增量补充。

**应用点**：

- S2 五力表 `intensity` 列
- S2 市场玩家表 `market_role` 列
- S2 消费者分群 `addressability` 列
- S2 关键趋势 `direction` / `time_horizon` / `impact_on_entry` 列
- S2 进入策略 `recommended_mode`
- S2 进入策略风险 `likelihood` / `impact` 字段
- S3 定价基线 `current_pricing_model`
- S3 竞品定价矩阵 expander 标题中的 `pricing_model`
- S3 行动建议 `priority` 标签
- S4 变更检测 `change_type` / `severity` 列
- S4 威胁评估 `severity` / `likelihood` / `quadrant` 列
- S4 机会识别 `opportunity_type` / `estimated_effort` / `expected_impact` 列
- S4 活体战卡 `overall_completeness`
- S5 MQ 图坐标轴 / 象限标签
- KPI 卡 `confidence_level`
- S2 `market_concentration` caption

---

## R2：图表只读化

**位置**：`render.py` 中所有 `st.plotly_chart` 调用

将现有的：
```python
st.plotly_chart(fig, use_container_width=True)
```

改为：
```python
st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False, "scrollZoom": False})
```

影响函数：`_render_chart_or_skip`（所有图表统一入口，改这一处即可）。

---

## R3：渲染顺序调整

**位置**：`render.py` `render_base_report` 函数（L1349-1396）

将 `render_scenario_payload(report.get("scenario_payload"))` 从当前位置（在 `_render_recommendations` 之后）移到 `_render_analysis_sections` 之后、`_render_swot` 之前。

**新顺序**：
```
kpi_strip → title → subtitle → at_a_glance → executive_summary → background
→ scope+methodology → key_findings → analysis_sections → scenario_payload
→ swot → conclusions → recommendations → appendix → metadata_panel
```

---

## R4：副标题样式增强

**位置**：`render.py` L1367 + `theme.py`

当前：`st.caption(subtitle)` — 灰色 12px。

改为：
```python
from html import escape
st.markdown(f'<p class="report-subtitle">{escape(subtitle)}</p>', unsafe_allow_html=True)
```

`theme.py` 中新增：
```css
.report-subtitle {
    font-size: 17px;
    color: var(--color-text-secondary);
    margin-top: -12px;
    margin-bottom: 20px;
    line-height: 1.5;
}
```

---

## R5：scope/methodology 布局

**位置**：`render.py` `_render_scope_and_methodology` 函数（L230-260）

当前：`st.columns(2)` 并排，左侧 scope + `st.subheader("分析范围")`，右侧 `st.subheader("方法论")` + `st.expander("数据采集与评估")`。

改为：
- 去掉 `st.columns(2)` 包裹
- scope 全宽紧凑展示：`st.subheader("分析范围")` + 竞品 / 时间窗 / 区域 / 排除 各一行 markdown
- methodology：去掉 `st.subheader("方法论")`，直接用 `st.expander("方法论", expanded=False)` 全宽折叠，expander 内部包含 data_collection_approach / evaluation_criteria / limitations / sample_size_note
- 若 scope 或 methodology 为空 dict 则整块跳过（保持当前 `if scope:` / `if methodology:` 逻辑）

---

## R6：关键发现中文化 + source_refs 域名显示

**位置**：`render.py` `_render_key_findings` 函数（L263-276）和 `_render_source_refs` 函数（L177-191）

1. `f"**Finding {i}**：..."` → `f"**发现 {i}**：..."`

2. `_render_source_refs` 中空 title 的处理逻辑：
   ```python
   # 当前
   label = title or f"链接 {i}"
   # 改为（顶部 import urlparse）
   from urllib.parse import urlparse
   # 渲染时
   label = title or (urlparse(url).netloc if url else "") or f"来源 {i}"
   ```
   三层 fallback：有 title 用 title → 有 URL 取域名 → 兜底 "来源 N"

---

## R7：详细章节去卡片 + 去 section_type

**位置**：`render.py` `_render_analysis_sections` 函数（L279-297）

当前用 `.section-card` HTML div 包装 heading + 显示 `section_type: <code>...</code>`。

改为：
```python
st.subheader(heading)
st.markdown(narrative)
_render_source_refs(sec.get("source_refs"))
```

去掉 `section_type` 显示行和 `.section-card` HTML 包装。保持全部展开无折叠。

---

## R8：S1 路线图英文字段名翻译

**位置**：`render.py` `_render_s1_payload` 中路线图部分（L610-624）

```python
# 当前
st.markdown("**must_build**")
st.markdown("**should_skip**")
st.markdown("**should_differentiate**")

# 改为
st.markdown("**必须建设 (must_build)**")
st.markdown("**建议跳过 (should_skip)**")
st.markdown("**差异化方向 (should_differentiate)**")
```

---

## R9：行动建议 priority 翻译 + 去 emoji

**位置**：`render.py` `_render_recommendations` 函数（L326-391）

1. 展示文本中 `[{priority}]` 用 `_t(priority)` 替换：`[critical]` → `[紧急 (critical)]`
2. 去掉 emoji badge（`🔴`/`🟡`/`🟢`），改为纯文字 + 卡片左边框颜色区分（已有 `.priority-critical` 等 CSS class）
3. **CSS class 必须用原始 raw priority 值推导**（在翻译之前），确保 `.priority-critical` 等 class 正确绑定

改动行：
```python
# 当前
badge = {"critical": "🔴", "important": "🟡", "consider": "🟢"}.get(priority, "")
# 改为
badge = ""
# priority_class 保持用 raw priority（已有逻辑正确，无需改动）
# 展示文本用 _t(priority)
```

---

## R10：S3 竞品定价矩阵去折叠

**位置**：`render.py` `_render_s3_payload` 竞品定价矩阵部分（L860-879）

当前：
```python
for cp in cpm:
    with st.expander(f"{cp.get('competitor_name', '')} - {cp.get('pricing_model', '')}"):
        ...
```

改为：
```python
for cp in cpm:
    st.markdown(f"**{cp.get('competitor_name', '')}** — {_t(cp.get('pricing_model', ''))}")
    # 表格直接展示
    ...
```

---

## R11：S3 定价基线排版

**位置**：`render.py` `_render_s3_payload` 定价基线部分（L778-790）

当前所有信息挤在一行 markdown：`模式: ... | 层级数: ... | ARPU 备注: ...`

改为多行独立展示（`current_pricing_model` 使用 `_t()` 翻译）：
```python
if pb.get("current_pricing_model"):
    st.markdown(f"**定价模式**：{_t(pb.get('current_pricing_model', ''))}")
if pb.get("current_tier_count"):
    st.markdown(f"**层级数**：{pb.get('current_tier_count', '')}")
if pb.get("current_arpu_note"):
    st.markdown(f"**ARPU 备注**：{pb.get('current_arpu_note', '')}")
```

---

## R12：S4 活体战卡去折叠

**位置**：`render.py` `_render_s4_payload` 活体战卡部分（L1019-1031）

当前：
```python
for bc in bcs:
    with st.expander(f"{bc.get('competitor_name', '')} - 完整度: {bc.get('overall_completeness', '')}"):
```

改为：
```python
for bc in bcs:
    st.markdown(f"**{bc.get('competitor_name', '')}** — 完整度：{_t(bc.get('overall_completeness', ''))}")
    for sec in bc.get("sections") or []:
        ...
```

---

## R13：S5 MQ 图表标签中文化

**位置**：`render.py` `_scatter_magic_quadrant` 函数（L123-151）

坐标轴改为：
```python
xaxis_title="执行力 (Ability to Execute)"
yaxis_title="愿景完整度 (Completeness of Vision)"
```

象限标签改为：
```python
fig.add_annotation(x=4, y=4.5, text="领导者 (Leaders)", ...)
fig.add_annotation(x=4, y=0.5, text="挑战者 (Challengers)", ...)
fig.add_annotation(x=1, y=4.5, text="远见者 (Visionaries)", ...)
fig.add_annotation(x=1, y=0.5, text="利基者 (Niche Players)", ...)
```

---

## R14：S5 竞品画像表截断处理

**位置**：`render.py` `_render_s5_payload` vendor_profiles 表（L1043-1053）

`overview` 列文本过长导致 dataframe 显示不全。将 `overview` 从表格中移出，改为每个竞品单独一行展示：

```python
st.dataframe([
    {
        "竞品": v.get("competitor_name", ""),
        "执行力": v.get("ability_to_execute_score", ""),
        "愿景完整度": v.get("completeness_of_vision_score", ""),
        "象限": _t(v.get("mq_quadrant", "")),
    }
    for v in vps
], use_container_width=True)
# overview 单独展示
for v in vps:
    if v.get("overview"):
        st.caption(f"{v.get('competitor_name', '')}：{v.get('overview', '')}")
```

---

## R15：S2 进入策略风险格式

**位置**：`render.py` `_render_s2_payload` 进入策略风险部分（L748-753）

当前：`f"（风险={r.get('likelihood', '')}/影响={r.get('impact', '')}）"`

改为：`f"（可能性：{_t(r.get('likelihood', ''))} / 影响：{_t(r.get('impact', ''))}）"`

---

## R16：Writer Prompt — narrative 输出规范

**位置**：`src/agents/prompts/writer/narrative/_common.py`

在 narrative prompt 的指令部分追加以下约束：

```
输出语言规范：
- 正文必须全部使用中文表达，不得在行文中直接使用 schema 的英文枚举值（如 wave_leader、wave_strong_performer、niche_first 等）。应使用对应的中文表述。
- 行内数字不得用 markdown 加粗语法包裹（如 **87.5分** 是错误格式）。仅独立指标/结论性数字可加粗（如单独成句的"综合评分：**87.5 分**"）。普通行文中的数字直接书写即可（如 87.5 分）。
- 英文专有名词（产品名、公司名、技术术语如 JTBD、LLM）可以保留英文。
```

---

## R17：S4 变更检测去折叠

**位置**：`render.py` `_render_s4_payload` 变更检测部分（L929-954）

当前按 5 类变更用 `st.expander(f"{label}（{len(items)} 条）")` 折叠：

```python
with st.expander(f"{label}（{len(items)} 条）"):
    st.dataframe([...])
```

改为直接展示，用加粗标题分隔：

```python
st.markdown(f"**{label}**（{len(items)} 条）")
st.dataframe([...], use_container_width=True)
```

dataframe 中 `change_type`、`severity` 等枚举列使用 `_t()` 翻译。

---

## R18：HTML 导出模板同步

**位置**：`src/api/exporters/templates/report.html.j2`

同步 render.py 中的以下变更到 Jinja2 模板：

1. **翻译**：在模板中引入同等的翻译逻辑（Jinja2 filter 或在 Python exporter 代码中预处理 dict）
2. **渲染顺序**：scenario_payload 移到 analysis_sections 之后、swot 之前
3. **去 section-card**：analysis_sections 渲染去掉 `.section-card` div 包装，改为 `<h3>` 标签
4. **去 section_type**：不显示 section_type 标签
5. **副标题样式**：使用 `.report-subtitle` class
6. **source_refs 域名 fallback**：空 title 时显示域名
7. **Finding 中文化**：`Finding N` → `发现 N`
8. **priority 翻译 + 去 emoji**：同 R9 逻辑
9. **scope/methodology 布局**：改为上下结构

实现方式：在 exporter Python 层（`src/api/exporters/`）新增 `_t()` 翻译 helper，作为 Jinja2 全局 filter 注入，模板中用 `{{ value | t }}` 调用。避免在模板中重复映射表。

---

## 不在本次范围

- `src/frontend/theme.py` 除 R4 的 subtitle class 外不改动
- schema 定义（`src/schemas/`）不改动
- 其他 writer prompt（outline/payload）不改动
- 数字字号差异（字体特性决定）不处理

---

## 验证方式

1. `uvicorn src.api.main:app --reload`
2. `streamlit run src/frontend/app.py`
3. 在前端"执行追溯"面板输入以下 trace ID 切换到"报告" tab：
   - `20260620-124502-636fd4`（S1）：验证 R3/R4/R5/R6/R7/R8/R9
   - `20260620-144341-10b7e6`（S2）：验证 R1/R2/R15
   - `20260620-151025-436f94`（S3）：验证 R10/R11
   - `20260620-211025-312494`（S4）：验证 R12/R17 + R1 翻译
   - `20260619-203923-9f5681`（S5）：验证 R13/R14
4. HTML 导出验证：对上述每个 trace 调用 `GET /api/v1/trace/{trace_id}/export?format=html`，检查导出文件中枚举值已翻译、布局正确
5. writer prompt 修改需重新跑分析验证（R16 不影响历史报告展示）
