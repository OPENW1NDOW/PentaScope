# 前端报告渲染优化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复前端报告渲染中英文枚举暴露、排版层级混乱、图表交互等 18 个问题，同步更新 HTML 导出模板。

**Architecture:** 在 render.py 顶部新增翻译函数 `_t()`，各渲染函数调用 `_t()` 翻译枚举值；调整渲染顺序和布局；在 html.py 注册 Jinja2 filter `t` 供模板使用；更新 narrative prompt 约束 LLM 输出。

**Tech Stack:** Python / Streamlit / Plotly / Jinja2

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `src/frontend/render.py` | Modify | 翻译函数 + 渲染逻辑修改 |
| `src/frontend/theme.py` | Modify | 新增 `.report-subtitle` CSS class |
| `src/api/exporters/html.py` | Modify | 注册 `t` filter 到 Jinja2 env |
| `src/api/exporters/templates/report.html.j2` | Modify | 模板同步翻译/布局变更 |
| `src/agents/prompts/writer/narrative/_common.py` | Modify | 新增输出语言规范 |

---

### Task 1: 翻译基础设施（R1）

**Files:**
- Modify: `src/frontend/render.py` (顶部新增)
- Modify: `src/api/exporters/html.py:76-81`

- [ ] **Step 1: 在 render.py 顶部新增 `_t()` 函数和映射表**

在 `from __future__ import annotations` 之后、`import streamlit as st` 之前插入：

```python
from urllib.parse import urlparse

_TRANSLATIONS: dict[str, str] = {
    # 通用程度
    "high": "高 (high)", "medium": "中 (medium)", "low": "低 (low)",
    # S1 wave_position
    "wave_leader": "领导者 (wave_leader)",
    "wave_strong_performer": "强劲表现者 (wave_strong_performer)",
    "wave_contender": "竞争者 (wave_contender)",
    "wave_follower": "跟随者 (wave_follower)",
    # S2 市场角色
    "challenger": "挑战者 (challenger)", "incumbent": "在位者 (incumbent)",
    "emerging": "新兴 (emerging)",
    # S2 可触达性
    "hard": "困难 (hard)", "moderate": "适中 (moderate)", "easy": "容易 (easy)",
    # S2 趋势方向/时间窗/影响
    "up": "上升 (up)", "down": "下降 (down)", "flat": "持平 (flat)",
    "short_term": "短期 (short_term)", "mid_term": "中期 (mid_term)",
    "long_term": "长期 (long_term)",
    "mixed": "混合 (mixed)", "negative": "负面 (negative)", "positive": "正面 (positive)",
    # S2 进入模式
    "differentiation": "差异化 (differentiation)",
    "niche_first": "利基优先 (niche_first)",
    "cost_leadership": "成本领先 (cost_leadership)",
    # S2 集中度
    "concentrated": "集中 (concentrated)", "fragmented": "分散 (fragmented)",
    # S3 定价模式
    "unknown": "未知 (unknown)", "freemium": "免费增值 (freemium)",
    "hybrid": "混合模式 (hybrid)", "subscription": "订阅制 (subscription)",
    # S3/通用 priority
    "critical": "紧急 (critical)", "important": "重要 (important)",
    "consider": "可选 (consider)",
    # S4 变更类型
    "new_feature": "新功能 (new_feature)",
    "removed_feature": "功能下架 (removed_feature)",
    "feature_updated": "功能更新 (feature_updated)",
    "tier_added": "新增层级 (tier_added)", "tier_removed": "移除层级 (tier_removed)",
    "price_increased": "涨价 (price_increased)",
    "price_decreased": "降价 (price_decreased)",
    "packaging_restructured": "套餐重组 (packaging_restructured)",
    "discount_changed": "折扣变更 (discount_changed)",
    "headline_changed": "标语变更 (headline_changed)",
    "positioning_shift": "定位转变 (positioning_shift)",
    "brand_update": "品牌更新 (brand_update)",
    "campaign_launch": "活动上线 (campaign_launch)",
    "funding": "融资 (funding)", "partnership": "合作 (partnership)",
    "leadership": "高管变动 (leadership)", "legal": "法律/合规 (legal)",
    "product_launch": "产品发布 (product_launch)",
    "acquisition": "收购 (acquisition)", "ipo": "IPO (ipo)",
    "layoff": "裁员 (layoff)", "other": "其他 (other)",
    "hired": "入职 (hired)", "departed": "离职 (departed)",
    "promoted": "晋升 (promoted)", "demoted": "降级 (demoted)",
    "joined_board": "加入董事会 (joined_board)",
    "title_changed": "头衔变更 (title_changed)",
    "founder_exit": "创始人离开 (founder_exit)",
    # S4 威胁象限
    "act_now": "立即行动 (act_now)", "contingency": "应急准备 (contingency)",
    "monitor": "持续监控 (monitor)", "deprioritize": "低优先 (deprioritize)",
    # S4 机会类型
    "product_gap": "产品差距 (product_gap)",
    "abandoned_segment": "放弃的细分市场 (abandoned_segment)",
    "messaging_white_space": "信息空白 (messaging_white_space)",
    "operational_weakness": "运营弱点 (operational_weakness)",
    # S4 完整度
    "partial": "部分 (partial)", "complete": "完整 (complete)",
    # S4 battlecard section_name
    "quick_summary": "快速摘要 (quick_summary)",
    "primary_threat": "核心威胁 (primary_threat)",
    "why_they_win": "为何他们赢 (why_they_win)",
    "why_we_win": "为何我们赢 (why_we_win)",
    "landmines": "竞争陷阱 (landmines)",
    "talk_track": "话术要点 (talk_track)",
    # S5 MQ 象限
    "leaders": "领导者 (leaders)", "challengers": "挑战者 (challengers)",
    "visionaries": "远见者 (visionaries)", "niche_players": "利基者 (niche_players)",
}


def _t(val) -> str:
    """翻译枚举值为「中文 (英文)」格式。非字符串或未命中则原样返回。"""
    if val is None:
        return ""
    if not isinstance(val, str):
        return str(val)
    if not val:
        return ""
    return _TRANSLATIONS.get(val, val)
```

- [ ] **Step 2: 在 html.py 注册 Jinja2 `t` filter**

在 `src/api/exporters/html.py` 第 81 行 `_jinja_env.filters["safe_md"] = _safe_markdown` 之后添加：

```python
from src.frontend.render import _t, _TRANSLATIONS

_jinja_env.filters["t"] = _t
```

- [ ] **Step 3: Commit**

```bash
git add src/frontend/render.py src/api/exporters/html.py
git commit -m "feat(render): add _t() translation infrastructure for enum values"
```

---

### Task 2: 图表只读化 + 副标题样式（R2, R4）

**Files:**
- Modify: `src/frontend/render.py:26-30` (`_render_chart_or_skip`)
- Modify: `src/frontend/render.py:1365-1367` (subtitle)
- Modify: `src/frontend/theme.py` (CSS)

- [ ] **Step 1: 修改 `_render_chart_or_skip` 禁止图表交互**

```python
def _render_chart_or_skip(fig, fallback_msg: str = "（plotly 未安装，跳过图表）"):
    if not _PLOTLY_OK or fig is None:
        st.caption(fallback_msg)
        return
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False, "scrollZoom": False})
```

- [ ] **Step 2: 修改副标题渲染**

将 `render_base_report` 中的：
```python
if subtitle:
    st.caption(subtitle)
```

改为：
```python
if subtitle:
    from html import escape as _html_escape
    st.markdown(
        f'<p class="report-subtitle">{_html_escape(subtitle)}</p>',
        unsafe_allow_html=True,
    )
```

- [ ] **Step 3: 在 theme.py 的 `_THEME_CSS` 中添加 `.report-subtitle` class**

在 `.btn-export` 之前插入：

```css
.report-subtitle {
    font-size: 17px;
    color: var(--color-text-secondary);
    margin-top: -12px;
    margin-bottom: 20px;
    line-height: 1.5;
}
```

- [ ] **Step 4: Commit**

```bash
git add src/frontend/render.py src/frontend/theme.py
git commit -m "feat(render): read-only charts + subtitle styling (R2, R4)"
```

---

### Task 3: 渲染顺序 + scope/methodology 布局（R3, R5）

**Files:**
- Modify: `src/frontend/render.py:1349-1396` (`render_base_report`)
- Modify: `src/frontend/render.py:230-260` (`_render_scope_and_methodology`)

- [ ] **Step 1: 调整 `render_base_report` 中 scenario_payload 位置**

将 `render_scenario_payload(report.get("scenario_payload"))` 从 `_render_recommendations` 之后移到 `_render_analysis_sections` 之后、`_render_swot` 之前：

```python
_render_key_findings(report.get("key_findings") or [])
_render_analysis_sections(report.get("analysis_sections") or [])

render_scenario_payload(report.get("scenario_payload"))

_render_swot(report.get("swot") or {})

conclusions = report.get("conclusions", "")
if conclusions:
    st.header("结论")
    st.write(conclusions)

_render_recommendations(report.get("recommendations") or [])
```

- [ ] **Step 2: 重写 `_render_scope_and_methodology` 为上下布局**

```python
def _render_scope_and_methodology(scope: dict, methodology: dict) -> None:
    if scope:
        st.subheader("分析范围")
        st.markdown(f"**竞品**：{', '.join(scope.get('competitors', []))}")
        st.markdown(f"**时间窗**：{scope.get('time_window', '')}")
        regions = scope.get("regions") or []
        if regions:
            st.markdown(f"**区域**：{', '.join(regions)}")
        exclusions = scope.get("exclusions") or []
        if exclusions:
            st.markdown(f"**排除**：{', '.join(exclusions)}")
    if methodology:
        with st.expander("方法论", expanded=False):
            st.write(methodology.get("data_collection_approach", ""))
            ec = methodology.get("evaluation_criteria") or []
            if ec:
                st.markdown("**评估维度**：")
                for c in ec:
                    st.markdown(f"- {c}")
            lim = methodology.get("limitations") or []
            if lim:
                st.markdown("**已知局限**：")
                for l_ in lim:
                    st.markdown(f"- {l_}")
            ssn = methodology.get("sample_size_note", "")
            if ssn:
                st.caption(ssn)
```

- [ ] **Step 3: Commit**

```bash
git add src/frontend/render.py
git commit -m "feat(render): reorder scenario_payload + vertical scope/methodology (R3, R5)"
```

---

### Task 4: 关键发现中文化 + source_refs 域名 + 详细章节去卡片（R6, R7）

**Files:**
- Modify: `src/frontend/render.py:177-191` (`_render_source_refs`)
- Modify: `src/frontend/render.py:263-276` (`_render_key_findings`)
- Modify: `src/frontend/render.py:279-297` (`_render_analysis_sections`)

- [ ] **Step 1: 修改 `_render_source_refs` 空 title fallback**

```python
def _render_source_refs(refs: list[dict] | None, *, prefix: str = "来源") -> None:
    if not refs:
        return
    parts = []
    for i, ref in enumerate(refs, 1):
        url = ref.get("url", "") if isinstance(ref, dict) else ""
        title = ref.get("title", "") if isinstance(ref, dict) else ""
        label = title or (urlparse(url).netloc if url else "") or f"来源 {i}"
        if url:
            parts.append(f"[{label}]({url})")
        else:
            parts.append(label)
    if parts:
        st.caption(f"{prefix}：" + " · ".join(parts))
```

- [ ] **Step 2: 修改 `_render_key_findings` 中文化**

```python
def _render_key_findings(findings: list[dict]) -> None:
    if not findings:
        return
    st.header("关键发现")
    for i, f in enumerate(findings, 1):
        st.markdown(f"**发现 {i}**：{f.get('statement', '')}")
        ev = f.get("evidence", "")
        impl = f.get("implication", "")
        if ev:
            st.caption(f"依据：{ev}")
        if impl:
            st.caption(f"启示：{impl}")
        _render_source_refs(f.get("source_refs"))
        st.markdown("---")
```

- [ ] **Step 3: 修改 `_render_analysis_sections` 去卡片去 section_type**

```python
def _render_analysis_sections(sections: list[dict]) -> None:
    if not sections:
        return
    st.header("详细章节")
    for sec in sections:
        heading = sec.get("heading", "")
        narrative = sec.get("narrative", "") or ""
        st.subheader(heading)
        st.markdown(narrative)
        _render_source_refs(sec.get("source_refs"))
```

- [ ] **Step 4: Commit**

```bash
git add src/frontend/render.py
git commit -m "feat(render): Chinese findings + domain fallback + remove section cards (R6, R7)"
```

---

### Task 5: S1 payload 翻译 + 路线图标题（R8）

**Files:**
- Modify: `src/frontend/render.py:506-624` (`_render_s1_payload`)

- [ ] **Step 1: 修改 S1 vendor_profiles 表中 wave_position 翻译**

在 `_render_s1_payload` 的 `st.dataframe` 行：
```python
rows = [
    {
        "竞品": v.get("competitor_name", ""),
        "波次定位": _t(v.get("wave_position", "")),
        "一句话": v.get("one_line_pitch", ""),
        "最佳适配": v.get("best_fit_for", ""),
        "优势数": len(v.get("strengths") or []),
        "警示数": len(v.get("cautions") or []),
    }
    for v in vps
]
```

- [ ] **Step 2: 修改路线图建议标题**

```python
# roadmap_recommendations
rr = p.get("roadmap_recommendations") or {}
if rr:
    st.subheader("路线图建议")
    cols = st.columns(3)
    with cols[0]:
        st.markdown("**必须建设 (must_build)**")
        for x in rr.get("must_build") or []:
            st.markdown(f"- {x}")
    with cols[1]:
        st.markdown("**建议跳过 (should_skip)**")
        for x in rr.get("should_skip") or []:
            st.markdown(f"- {x}")
    with cols[2]:
        st.markdown("**差异化方向 (should_differentiate)**")
        for x in rr.get("should_differentiate") or []:
            st.markdown(f"- {x}")
    st.caption(rr.get("rationale_summary", ""))
```

- [ ] **Step 3: Commit**

```bash
git add src/frontend/render.py
git commit -m "feat(render): S1 wave_position translation + roadmap labels (R8)"
```

---

### Task 6: 行动建议 priority 翻译去 emoji + KPI 可信度（R9, R10 partial）

**Files:**
- Modify: `src/frontend/render.py:326-391` (`_render_recommendations`)
- Modify: `src/frontend/render.py:1314-1346` (`_render_kpi_strip`)

- [ ] **Step 1: 修改 `_render_recommendations` 去 emoji + 翻译 priority**

在函数中将：
```python
badge = {"critical": "🔴", "important": "🟡", "consider": "🟢"}.get(priority, "")
```
改为：
```python
badge = ""
```

将展示文本中：
```python
f"<div style=\"font-size:14px;font-weight:600\">{badge} [{priority}] {action}</div>"
```
改为：
```python
f"<div style=\"font-size:14px;font-weight:600\">[{_t(priority)}] {action}</div>"
```

`priority_class` 逻辑保持不变（已用 raw priority 推导）。

- [ ] **Step 2: 修改 KPI 卡可信度翻译**

在 `_render_kpi_strip` 中将：
```python
conf_level = meta.get("confidence_level") or "—"
```
改为：
```python
conf_level = _t(meta.get("confidence_level") or "") or "—"
```

- [ ] **Step 3: Commit**

```bash
git add src/frontend/render.py
git commit -m "feat(render): translate priority labels + confidence KPI (R9)"
```

---

### Task 7: S2 payload 翻译（R1 应用, R15）

**Files:**
- Modify: `src/frontend/render.py:627-769` (`_render_s2_payload`)

- [ ] **Step 1: 修改五力表 intensity 翻译**

```python
rows = [
    {
        "维度": label,
        "强度": _t((ff.get(k) or {}).get("intensity", "")),
        "影响": (ff.get(k) or {}).get("implication", ""),
    }
    for k, label in forces_map
]
```

- [ ] **Step 2: 修改市场玩家表 market_role 翻译 + market_concentration**

```python
st.caption(f"市场集中度：{_t(p.get('market_concentration', ''))}")
st.dataframe([
    {
        "名称": pl.get("name", ""),
        "公司": pl.get("company", ""),
        "角色": _t(pl.get("market_role", "")),
        "份额%": pl.get("market_share_pct", ""),
        "增速%": pl.get("yoy_growth_pct", ""),
        "差异化": pl.get("key_differentiator", ""),
        "推荐": "✓" if pl.get("is_recommended") else "",
        "已采集": "✓" if pl.get("is_collected") else "",
    }
    for pl in players
], use_container_width=True)
```

- [ ] **Step 3: 修改消费者分群 addressability 翻译**

```python
st.dataframe([
    {
        "分群": s.get("name", ""),
        "份额%": s.get("share_pct", ""),
        "可触达": _t(s.get("addressability", "")),
        "核心需求": " / ".join(s.get("key_needs") or []),
    }
    for s in segs
], use_container_width=True)
```

- [ ] **Step 4: 修改关键趋势表 direction/time_horizon/impact_on_entry 翻译**

```python
st.dataframe([
    {
        "趋势": t.get("trend_name", ""),
        "方向": _t(t.get("direction", "")),
        "时间窗": _t(t.get("time_horizon", "")),
        "对进入影响": _t(t.get("impact_on_entry", "")),
    }
    for t in trends
], use_container_width=True)
```

- [ ] **Step 5: 修改进入策略 recommended_mode + 风险格式（R15）**

```python
st.markdown(f"**推荐模式**：{_t(es.get('recommended_mode', ''))}")
```

风险列表：
```python
for r in risks:
    st.markdown(
        f"- {r.get('description', '')} "
        f"（可能性：{_t(r.get('likelihood', ''))} / 影响：{_t(r.get('impact', ''))}）"
    )
```

- [ ] **Step 6: Commit**

```bash
git add src/frontend/render.py
git commit -m "feat(render): S2 payload enum translations (R1/R15)"
```

---

### Task 8: S3 payload 修改（R10, R11）

**Files:**
- Modify: `src/frontend/render.py:773-909` (`_render_s3_payload`)

- [ ] **Step 1: 修改定价基线为多行 + 翻译 pricing_model（R11）**

```python
pb = p.get("pricing_baseline") or {}
if pb:
    st.subheader("当前定价基线")
    if pb.get("current_pricing_model"):
        st.markdown(f"**定价模式**：{_t(pb.get('current_pricing_model', ''))}")
    if pb.get("current_tier_count"):
        st.markdown(f"**层级数**：{pb.get('current_tier_count', '')}")
    if pb.get("current_arpu_note"):
        st.markdown(f"**ARPU 备注**：{pb.get('current_arpu_note', '')}")
    pains = pb.get("pain_points") or []
    if pains:
        st.markdown("**痛点**：")
        for pp in pains:
            st.markdown(f"- {pp}")
```

- [ ] **Step 2: 修改竞品定价矩阵去 expander（R10）**

```python
cpm = p.get("competitive_pricing_matrix") or []
if cpm:
    st.subheader("竞品定价矩阵")
    for cp in cpm:
        st.markdown(f"**{cp.get('competitor_name', '')}** — {_t(cp.get('pricing_model', ''))}")
        ts = cp.get("tiers") or []
        if ts:
            st.dataframe([
                {
                    "套餐": t.get("name", ""),
                    "月费": t.get("monthly_price", ""),
                    "年费": t.get("annual_price", ""),
                    "货币": t.get("currency", ""),
                    "热销": "✓" if t.get("observed_is_most_popular") else "",
                    "对象": t.get("observed_target_persona", ""),
                }
                for t in ts
            ], use_container_width=True)
        if cp.get("free_plan_strategy"):
            st.caption(f"免费策略：{_t(cp.get('free_plan_strategy', ''))}")
```

- [ ] **Step 3: Commit**

```bash
git add src/frontend/render.py
git commit -m "feat(render): S3 pricing baseline multi-line + matrix unfold (R10, R11)"
```

---

### Task 9: S4 payload 修改（R12, R17）

**Files:**
- Modify: `src/frontend/render.py:912-1031` (`_render_s4_payload`)

- [ ] **Step 1: 修改变更检测去 expander + 翻译枚举（R17）**

```python
for key, label in change_groups:
    items = p.get(key) or []
    if not items:
        continue
    if not rendered_any:
        st.subheader("变更检测")
        rendered_any = True
    st.markdown(f"**{label}**（{len(items)} 条）")
    st.dataframe([
        {
            "竞品": it.get("competitor_name", ""),
            "类型": _t(it.get("change_type", "") or it.get("category", "") or it.get("action", "")),
            "事实": (it.get("fia") or {}).get("fact", ""),
            "严重度": _t(it.get("severity", "")),
            "基线": "✓" if it.get("is_baseline") else "",
        }
        for it in items
    ], use_container_width=True)
```

- [ ] **Step 2: 修改威胁评估表翻译**

```python
st.dataframe([
    {
        "标题": t.get("title", ""),
        "严重度": _t(t.get("severity", "")),
        "可能性": _t(t.get("likelihood", "")),
        "象限": _t(t.get("quadrant", "")),
        "应对": t.get("recommended_response", ""),
    }
    for t in threats
], use_container_width=True)
```

- [ ] **Step 3: 修改机会识别表翻译**

```python
st.dataframe([
    {
        "类型": _t(o.get("opportunity_type", "")),
        "投入": _t(o.get("estimated_effort", "")),
        "影响": _t(o.get("expected_impact", "")),
        "描述": o.get("description", ""),
        "首步": o.get("first_step", ""),
    }
    for o in opps
], use_container_width=True)
```

- [ ] **Step 4: 修改活体战卡去 expander + 翻译（R12）**

```python
bcs = p.get("battlecards") or []
if bcs:
    st.subheader("活体战卡")
    for bc in bcs:
        st.markdown(
            f"**{bc.get('competitor_name', '')}** — "
            f"完整度：{_t(bc.get('overall_completeness', ''))}"
        )
        for sec in bc.get("sections") or []:
            st.markdown(f"**{_t(sec.get('section_name', ''))}** "
                        f"({_t(sec.get('completeness', ''))})")
            if sec.get("content"):
                st.write(sec.get("content", ""))
```

- [ ] **Step 5: Commit**

```bash
git add src/frontend/render.py
git commit -m "feat(render): S4 unfold expanders + enum translations (R12, R17)"
```

---

### Task 10: S5 payload 修改（R13, R14）

**Files:**
- Modify: `src/frontend/render.py:123-151` (`_scatter_magic_quadrant`)
- Modify: `src/frontend/render.py:1036-1053` (`_render_s5_payload`)

- [ ] **Step 1: 修改 MQ 图表标签中文化（R13）**

```python
def _scatter_magic_quadrant(vps: list[dict]):
    if not _PLOTLY_OK or not vps:
        return None
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=[v.get("ability_to_execute_score", 0) for v in vps],
        y=[v.get("completeness_of_vision_score", 0) for v in vps],
        mode="markers+text",
        text=[v.get("competitor_name", "") for v in vps],
        textposition="top center",
        marker=dict(size=16, color="#3b82f6"),
        name="竞品",
    ))
    fig.add_shape(type="line", x0=2.5, y0=0, x1=2.5, y1=5, line=dict(color="gray", dash="dash"))
    fig.add_shape(type="line", x0=0, y0=2.5, x1=5, y1=2.5, line=dict(color="gray", dash="dash"))
    fig.add_annotation(x=4, y=4.5, text="领导者 (Leaders)", showarrow=False, font=dict(color="#888"))
    fig.add_annotation(x=4, y=0.5, text="挑战者 (Challengers)", showarrow=False, font=dict(color="#888"))
    fig.add_annotation(x=1, y=4.5, text="远见者 (Visionaries)", showarrow=False, font=dict(color="#888"))
    fig.add_annotation(x=1, y=0.5, text="利基者 (Niche Players)", showarrow=False, font=dict(color="#888"))
    fig.update_layout(
        xaxis_title="执行力 (Ability to Execute)",
        yaxis_title="愿景完整度 (Completeness of Vision)",
        xaxis=dict(range=[0, 5]), yaxis=dict(range=[0, 5]),
        height=440, showlegend=False,
    )
    return fig
```

- [ ] **Step 2: 修改 S5 vendor_profiles 表去 overview 列 + mq_quadrant 翻译（R14）**

```python
vps = p.get("vendor_profiles") or []
if vps:
    st.subheader("竞品画像 Gartner MQ")
    _render_chart_or_skip(_scatter_magic_quadrant(vps))
    st.dataframe([
        {
            "竞品": v.get("competitor_name", ""),
            "执行力": v.get("ability_to_execute_score", ""),
            "愿景完整度": v.get("completeness_of_vision_score", ""),
            "象限": _t(v.get("mq_quadrant", "")),
        }
        for v in vps
    ], use_container_width=True)
    for v in vps:
        overview = v.get("overview", "")
        if overview:
            st.caption(f"{v.get('competitor_name', '')}：{overview}")
```

- [ ] **Step 3: Commit**

```bash
git add src/frontend/render.py
git commit -m "feat(render): S5 MQ bilingual labels + vendor table fix (R13, R14)"
```

---

### Task 11: Writer Prompt 约束（R16）

**Files:**
- Modify: `src/agents/prompts/writer/narrative/_common.py:20-21`

- [ ] **Step 1: 在 `【撰写要求】` 第 20 行后插入新规则**

在 `- source_refs 列出本节真实引用的 URL...` 这行之后、`【narrative 字段值内部排版要求（重要）】` 之前，插入：

```
- **输出语言规范**：正文全部用中文表达，不得在行文中直接使用 schema 英文枚举值（如 wave_leader、wave_strong_performer、niche_first、act_now 等），应使用对应中文表述
- **数字格式规范**：行内数字不得用 markdown 加粗（如 **87.5分** 是错误格式）。仅独立指标/结论性数字可加粗（如独立成句的 "综合评分：**87.5 分**"）。普通行文中的数字直接书写
```

- [ ] **Step 2: 修改现有排版要求中的加粗规则**

将第 27 行：
```
- **强调**：关键判断或核心数字用 `**加粗**`
```
改为：
```
- **强调**：关键判断用 `**加粗**`（但行内数字不加粗，见上方数字格式规范）
```

- [ ] **Step 3: Commit**

```bash
git add src/agents/prompts/writer/narrative/_common.py
git commit -m "feat(writer): add narrative language + number format constraints (R16)"
```

---

### Task 12: HTML 导出模板同步（R18）

**Files:**
- Modify: `src/api/exporters/templates/report.html.j2`

- [ ] **Step 1: 在模板中对枚举值使用 `| t` filter**

全文搜索并替换以下模式（示例）：

KPI 可信度（约 L140）：
```jinja2
{# 原 #}
{{ meta.confidence_level }}
{# 改为 #}
{{ meta.confidence_level | t }}
```

analysis_sections section_type 行——**删除整行**（去掉 section_type 显示）。

findings 标题（约 L193）：
```jinja2
{# 原 #}
<strong>Finding {{ loop.index }}</strong>
{# 改为 #}
<strong>发现 {{ loop.index }}</strong>
```

source_refs 空 title fallback（约 L200）：目前模板用 `ref.title or ref.url`，改为取域名：
```jinja2
{# 在 Python 端 render_html() 中预处理 source_refs，为空 title 填入 netloc #}
```

（具体实现：在 `html.py` 的 `render_html()` 中，遍历 report dict 递归给空 title 的 source_ref 补上 `urlparse(url).netloc`，这样模板无需改动 source_refs 逻辑）

- [ ] **Step 2: 去掉 .section-card 包装改为 `<h3>`**

analysis_sections 渲染部分（约 L210-224），将：
```html
<div class="section-card">
  <h3>{{ sec.heading }}</h3>
  <small>section_type: <code>{{ sec.section_type }}</code></small>
  ...
</div>
```
改为：
```html
<h3>{{ sec.heading }}</h3>
<div>{{ sec.narrative | safe_md }}</div>
{% if sec.source_refs %}...{% endif %}
```

- [ ] **Step 3: 修改副标题样式**

```html
{# 原 #}
{% if report.subtitle %}<p>{{ report.subtitle }}</p>{% endif %}
{# 改为 #}
{% if report.subtitle %}<p class="report-subtitle">{{ report.subtitle }}</p>{% endif %}
```

在 `<style>` 块中添加：
```css
.report-subtitle {
    font-size: 17px;
    color: var(--color-text-secondary);
    margin-top: -8px;
    margin-bottom: 20px;
    line-height: 1.5;
}
```

- [ ] **Step 4: 调整渲染顺序 — scenario_payload 移到 analysis_sections 之后、swot 之前**

重排模板中的 section 块顺序。

- [ ] **Step 5: recommendations 去 emoji + priority 翻译**

```html
{# 原 #}
<div style="font-weight:600">{{ rec.priority }} {{ rec.action }}</div>
{# 改为 #}
<div style="font-weight:600">[{{ rec.priority | t }}] {{ rec.action }}</div>
```

- [ ] **Step 6: 在 html.py `render_html()` 中预处理 source_refs 空 title**

在 `return template.render(...)` 之前添加：

```python
def _fill_empty_titles(node):
    """递归为空 title 的 source_ref 填入域名。"""
    if isinstance(node, dict):
        if "source_refs" in node:
            for ref in node.get("source_refs") or []:
                if isinstance(ref, dict) and not ref.get("title"):
                    url = ref.get("url", "")
                    ref["title"] = urlparse(url).netloc if url else ""
        for v in node.values():
            if isinstance(v, (dict, list)):
                _fill_empty_titles(v)
    elif isinstance(node, list):
        for item in node:
            _fill_empty_titles(item)

import copy
report_copy = copy.deepcopy(report)
_fill_empty_titles(report_copy)
```

然后 `template.render(report=report_copy, ...)` 使用处理后的副本。

- [ ] **Step 7: Commit**

```bash
git add src/api/exporters/html.py src/api/exporters/templates/report.html.j2
git commit -m "feat(export): sync HTML template with render.py translations + layout (R18)"
```

---

### Task 13: 验证

- [ ] **Step 1: 启动后端**

```bash
uvicorn src.api.main:app --reload
```

- [ ] **Step 2: 启动前端**

```bash
streamlit run src/frontend/app.py
```

- [ ] **Step 3: 前端验证 5 个 trace**

在"执行追溯"面板逐一输入以下 trace ID，切换到"报告" tab 检查：
- `20260620-124502-636fd4`（S1）：副标题样式 / scope 布局 / 发现中文 / 无 section_type / 路线图中文 / payload 在 SWOT 前
- `20260620-144341-10b7e6`（S2）：五力/玩家/趋势表枚举翻译 / 图表无工具栏 / 进入策略翻译
- `20260620-151025-436f94`（S3）：定价基线多行 / 定价矩阵无折叠 / priority 翻译无 emoji
- `20260620-211025-312494`（S4）：变更检测无折叠+翻译 / 威胁评估翻译 / 战卡无折叠
- `20260619-203923-9f5681`（S5）：MQ 图中文标签 / vendor 表无 overview 列 / mq_quadrant 翻译

- [ ] **Step 4: HTML 导出验证**

```bash
curl -o test_s1.html "http://localhost:8000/api/v1/trace/20260620-124502-636fd4/export?format=html"
```

打开 `test_s1.html` 检查：枚举已翻译 / 无 section_type / 副标题样式 / 顺序正确。

- [ ] **Step 5: Final commit (if any remaining fixes)**

```bash
git add -A
git commit -m "fix(render): verification fixes"
```
