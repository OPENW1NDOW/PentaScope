"""前端渲染模块：BaseReport 通用骨架 + scenario_payload 分场景渲染。

F1 实现 BaseReport 通用部分（at_a_glance / executive_summary / methodology /
key_findings / analysis_sections / swot / recommendations / appendix）。

F2/F3 后续在 render_scenario_payload + Plotly 图表中扩展。
"""
from __future__ import annotations

import html as _html
from urllib.parse import urlparse

import streamlit as st

# F3 Plotly 图表：plotly 是可选依赖；导入失败时图表静默退化为文字提示
try:
    import plotly.graph_objects as go  # type: ignore
    _PLOTLY_OK = True
except ImportError:  # pragma: no cover
    go = None
    _PLOTLY_OK = False


# ============ 枚举值翻译（从 utils 导入，避免跨层依赖） ============
import sys as _sys
from pathlib import Path as _Path
_PROJECT_ROOT = str(_Path(__file__).resolve().parents[2])
if _PROJECT_ROOT not in _sys.path:
    _sys.path.insert(0, _PROJECT_ROOT)
from src.utils.translations import _t  # noqa: E402


# ============ 章节编号 ============

_CN_NUMBERS = ["一", "二", "三", "四", "五", "六", "七", "八", "九", "十",
               "十一", "十二", "十三", "十四", "十五", "十六", "十七", "十八", "十九", "二十"]


class _HeadingCounter:
    """报告章节编号计数器：一、/（一）/ 1. 三级编号"""

    def __init__(self):
        self.l2 = 0
        self.l3 = 0

    def reset(self):
        self.l2 = 0
        self.l3 = 0

    def h2(self, title: str) -> str:
        self.l2 += 1
        self.l3 = 0
        prefix = _CN_NUMBERS[self.l2 - 1] if self.l2 <= len(_CN_NUMBERS) else str(self.l2)
        return f"{prefix}、{title}"

    def h3(self, title: str) -> str:
        self.l3 += 1
        prefix = _CN_NUMBERS[self.l3 - 1] if self.l3 <= len(_CN_NUMBERS) else str(self.l3)
        return f"（{prefix}）{title}"


_hc = _HeadingCounter()


# ============ F3 图表（Plotly） ============

_FIVE_FORCES_INTENSITY_NUM = {"low": 1, "medium": 3, "high": 5}


def _render_chart_or_skip(fig, fallback_msg: str = "（plotly 未安装，跳过图表）"):
    if not _PLOTLY_OK or fig is None:
        st.caption(fallback_msg)
        return
    st.plotly_chart(fig, use_container_width=True, config={"staticPlot": True})


def _radar_chart_s1(radar_scores: list[dict]):
    """S1 雷达图：5 维 × N 个竞品"""
    if not _PLOTLY_OK or not radar_scores:
        return None
    dims = ["feature_breadth", "usability", "cost_effectiveness", "stability", "design_quality"]
    labels_cn = ["功能广度", "易用性", "性价比", "稳定性", "设计质量"]
    fig = go.Figure()
    for r in radar_scores:
        values = [r.get(d, 0) or 0 for d in dims]
        # 闭合多边形
        fig.add_trace(go.Scatterpolar(
            r=values + [values[0]],
            theta=labels_cn + [labels_cn[0]],
            fill="toself",
            name=r.get("competitor_name", ""),
        ))
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 5])),
        showlegend=True,
        height=400,
    )
    return fig


def _radar_chart_five_forces(ff: dict):
    """S2 五力蜘蛛网"""
    if not _PLOTLY_OK or not ff:
        return None
    forces = [
        ("new_entrants", "新进入者"),
        ("supplier_power", "供应商"),
        ("buyer_power", "买家"),
        ("substitute_threat", "替代品"),
        ("competitive_rivalry", "现有竞争"),
    ]
    values = [_FIVE_FORCES_INTENSITY_NUM.get((ff.get(k) or {}).get("intensity", ""), 0) for k, _ in forces]
    labels = [lbl for _, lbl in forces]
    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=values + [values[0]],
        theta=labels + [labels[0]],
        fill="toself",
        name="行业五力",
    ))
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 5], tickvals=[1, 3, 5], ticktext=["低", "中", "高"])),
        showlegend=False,
        height=380,
    )
    return fig


def _scatter_perceptual_map(pm: dict):
    """S5 二维感知地图（带 is_self 高亮）"""
    if not _PLOTLY_OK or not pm:
        return None
    brands = pm.get("plotted_brands") or []
    if not brands:
        return None
    x_axis = pm.get("x_axis") or {}
    y_axis = pm.get("y_axis") or {}
    fig = go.Figure()
    others_x = [b.get("x_score", 0) for b in brands if not b.get("is_self")]
    others_y = [b.get("y_score", 0) for b in brands if not b.get("is_self")]
    others_text = [b.get("competitor_name", "") for b in brands if not b.get("is_self")]
    if others_x:
        fig.add_trace(go.Scatter(
            x=others_x, y=others_y, mode="markers+text", text=others_text,
            textposition="top center", marker=dict(size=14, color="#3b82f6"),
            name="竞品",
        ))
    selves = [b for b in brands if b.get("is_self")]
    if selves:
        fig.add_trace(go.Scatter(
            x=[b.get("x_score", 0) for b in selves],
            y=[b.get("y_score", 0) for b in selves],
            mode="markers+text", text=[b.get("competitor_name", "我方") for b in selves],
            textposition="top center", marker=dict(size=20, color="#ef4444", symbol="star"),
            name="我方",
        ))
    fig.update_layout(
        xaxis_title=f"{x_axis.get('attribute', 'X')} ({x_axis.get('low_label', '')} → {x_axis.get('high_label', '')})",
        yaxis_title=f"{y_axis.get('attribute', 'Y')} ({y_axis.get('low_label', '')} → {y_axis.get('high_label', '')})",
        height=420, showlegend=True,
    )
    fig.update_xaxes(range=[0, x_axis.get("scale_max", 5)])
    fig.update_yaxes(range=[0, y_axis.get("scale_max", 5)])
    return fig


def _scatter_magic_quadrant(vps: list[dict]):
    """S5 Gartner Magic Quadrant 散点（execute × vision，含象限分隔线）"""
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
    # 象限分隔线（2.5 中点）
    fig.add_shape(type="line", x0=2.5, y0=0, x1=2.5, y1=5, line=dict(color="gray", dash="dash"))
    fig.add_shape(type="line", x0=0, y0=2.5, x1=5, y1=2.5, line=dict(color="gray", dash="dash"))
    # 象限标签
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


def _line_strategy_canvas(sc: dict):
    """S5 战略画布：每个品牌一条折线（x=factors，y=levels）"""
    if not _PLOTLY_OK or not sc:
        return None
    factors = [f.get("name", "") for f in sc.get("competitive_factors") or []]
    if not factors:
        return None
    fig = go.Figure()
    for vc in sc.get("value_curves") or []:
        levels = [(vc.get("factor_levels") or {}).get(f, 0) for f in factors]
        is_self = vc.get("is_self")
        fig.add_trace(go.Scatter(
            x=factors, y=levels, mode="lines+markers",
            name=vc.get("competitor_name", ""),
            line=dict(width=4 if is_self else 2, dash="solid" if is_self else "dot"),
        ))
    fig.update_layout(
        yaxis_title="水平 (0-10)", yaxis=dict(range=[0, 10]),
        xaxis_title="竞争要素", height=420, showlegend=True,
    )
    return fig


def _render_source_refs(refs: list[dict] | None, *, prefix: str = "来源") -> None:
    """渲染 SourceRef 列表为 caption 行（小字）"""
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


def _render_at_a_glance(items: list[str]) -> None:
    if not items:
        return
    st.header(_hc.h2("核心要点"))
    for it in items:
        st.markdown(f"- {it}")


def _render_executive_summary(es: dict) -> None:
    """5 段式执行摘要（v3 BaseReport 替代旧 4 段）"""
    if not es:
        return
    st.header(_hc.h2("执行摘要"))
    for label, key in [
        ("背景定位", "context"),
        ("核心论断", "core_thesis"),
        ("现实启示", "implications"),
    ]:
        val = es.get(key, "")
        if val:
            st.subheader(_hc.h3(label))
            st.write(val)

    kfb = es.get("key_findings_brief") or []
    if kfb:
        st.subheader(_hc.h3("关键发现速览"))
        for f in kfb:
            st.markdown(f"- {f}")

    pf = es.get("path_forward") or []
    if pf:
        st.subheader(_hc.h3("行动路径"))
        for p in pf:
            st.markdown(f"- {p}")


def _render_scope_and_methodology(scope: dict, methodology: dict) -> None:
    if scope:
        st.subheader(_hc.h3("分析范围"))
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


def _render_key_findings(findings: list[dict]) -> None:
    if not findings:
        return
    st.header(_hc.h2("关键发现"))
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


def _render_analysis_sections(sections: list[dict]) -> None:
    if not sections:
        return
    st.header(_hc.h2("详细章节"))
    for sec in sections:
        heading = sec.get("heading", "")
        narrative = sec.get("narrative", "") or ""
        st.subheader(_hc.h3(heading))
        st.markdown(narrative)
        _render_source_refs(sec.get("source_refs"))


def _render_swot(swot: dict) -> None:
    if not swot:
        return
    has_any = any(swot.get(k) for k in ("strengths", "weaknesses", "opportunities", "threats"))
    if not has_any:
        return
    st.header(_hc.h2("SWOT 分析"))
    cols = st.columns(2)
    quadrants = [
        (cols[0], "strengths", "优势 S"),
        (cols[1], "weaknesses", "劣势 W"),
        (cols[0], "opportunities", "机会 O"),
        (cols[1], "threats", "威胁 T"),
    ]
    for col, key, label in quadrants:
        with col:
            entries = swot.get(key) or []
            st.subheader(_hc.h3(label))
            for e in entries:
                st.markdown(f"- **{e.get('point', '')}**")
                ev = e.get("evidence", "")
                if ev:
                    st.caption(f"依据：{ev}")
                _render_source_refs(e.get("source_refs"))


def _safe_href_url(url: str) -> str:
    """过滤前端 href 用 URL：仅允许 http/https，非法协议返回空字符串。"""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return ""
    return _html.escape(url)


def _render_recommendations(recs: list[dict]) -> None:
    if not recs:
        return
    st.header(_hc.h2("行动建议"))
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
        st.subheader(_hc.h3(tl_label))
        # grid 布局：每行 2 张卡
        for i in range(0, len(items), 2):
            cols = st.columns(2)
            for col_idx, item_idx in enumerate(range(i, min(i + 2, len(items)))):
                r = items[item_idx]
                priority = r.get("priority", "")
                target = r.get("target_role", "")
                action = r.get("action", "")
                rationale = r.get("rationale", "")
                priority_class = (
                    f"priority-{priority}"
                    if priority in ("critical", "important", "consider")
                    else ""
                )
                with cols[col_idx]:
                    refs = r.get("source_refs") or []
                    refs_html = ""
                    if refs:
                        parts = []
                        for ref in refs:
                            if isinstance(ref, dict):
                                url = ref.get("url", "")
                                title = _html.escape(ref.get("title", "") or "链接")
                                safe_url = _safe_href_url(url) if url else ""
                                if safe_url:
                                    parts.append(
                                        f'<a href="{safe_url}" target="_blank">{title}</a>'
                                    )
                        if parts:
                            refs_html = (
                                f'<small style="color:var(--color-text-secondary)">'
                                f'来源：{" · ".join(parts)}</small>'
                            )
                    target_html = (
                        f'<small style="color:var(--color-text-secondary)">'
                        f'对象：{_html.escape(target)}</small><br>'
                        if target else ''
                    )
                    rationale_html = (
                        f'<small style="color:var(--color-text-secondary)">'
                        f'依据：{_html.escape(rationale)}</small><br>'
                        if rationale else ''
                    )
                    st.markdown(
                        f"""<div class="action-card {priority_class}">
  <div style="font-size:14px;font-weight:600">[{_t(priority)}] {_html.escape(action)}</div>
  {target_html}
  {rationale_html}
  {refs_html}
</div>""",
                        unsafe_allow_html=True,
                    )


def _collect_all_references(report: dict) -> list[dict]:
    """递归扫全报告（含 5 场景 payload 深嵌套），收集所有 source_refs + metadata.data_sources。

    实现：
    - 通用递归：遇 dict 含 'source_refs' / 'data_sources' 列表就提取所有 {url,title}
      然后继续递归 dict/list 子节点
    - 按 url 去重，保留首次出现的 title
    - schema 全部统一用 source_refs 命名（10 个 schema 文件验证），所以递归方式
      无论 5 场景 payload 怎么嵌套都能 cover
    """
    seen_urls: set[str] = set()
    refs: list[dict] = []

    def _add(url: str, title: str = "") -> None:
        if not url or url in seen_urls:
            return
        seen_urls.add(url)
        refs.append({"url": url, "title": title or url})

    def _walk(node) -> None:
        if isinstance(node, dict):
            # 提取 source_refs（5 场景 + BaseReport 4 处通用都用这个名）
            for ref in node.get("source_refs") or []:
                if isinstance(ref, dict):
                    _add(ref.get("url", ""), ref.get("title", ""))
            # metadata.data_sources（顶层数据源也是链接来源之一）
            for ds in node.get("data_sources") or []:
                if isinstance(ds, dict):
                    _add(ds.get("url", ""), ds.get("title", ""))
            # 继续向下递归 dict 子值
            for v in node.values():
                if isinstance(v, (dict, list)):
                    _walk(v)
        elif isinstance(node, list):
            for it in node:
                _walk(it)

    _walk(report)
    return refs


def _render_appendix(appendix: dict | None, *, report: dict | None = None) -> None:
    glossary = (appendix or {}).get("glossary") or {}
    sources_full = (appendix or {}).get("data_sources_full") or []
    references = _collect_all_references(report or {}) if report else []
    if not (glossary or sources_full or references):
        return
    with st.expander("附录", expanded=False):
        if glossary:
            st.subheader("术语表")
            for term, defi in glossary.items():
                st.markdown(f"- **{term}**：{defi}")
        if sources_full:
            st.subheader("完整数据来源")
            for ds in sources_full:
                url = ds.get("url", "")
                title = ds.get("title", "") or url
                conf = ds.get("confidence", "")
                badge = {"high": "🟢", "medium": "🟡", "low": "🟠"}.get(conf, "")
                if url:
                    st.markdown(f"- {badge} [{title}]({url})")
                else:
                    st.markdown(f"- {badge} {title}")
        if references:
            st.subheader("参考资料")
            st.caption(f"全报告共引用 {len(references)} 处独立链接")
            for ref in references:
                st.markdown(f"- [{ref['title']}]({ref['url']})")


def _render_metadata_panel(metadata: dict) -> None:
    if not metadata:
        return
    with st.expander("元数据 & 质检", expanded=False):
        cols = st.columns(3)
        cols[0].metric("场景", metadata.get("scenario", ""))
        cols[1].metric("置信度", metadata.get("confidence_level", ""))
        qs = metadata.get("quality_score")
        if qs is not None:
            cols[2].metric("质检评分", f"{qs:.2f}")
        else:
            cols[2].metric("质检评分", "未质检")
        note = metadata.get("quality_score_calculation_note", "")
        if note:
            st.caption(f"评分依据：{note}")
        warnings = metadata.get("warnings") or []
        if warnings:
            st.markdown("**警告**：")
            for w in warnings:
                st.markdown(f"- {w}")
        st.json(metadata)


def render_scenario_payload(payload: dict | None) -> None:
    """scenario_payload 按 scenario_type 分发到 5 个专属渲染函数（F2）。

    图表（雷达 / Perceptual Map / MQ）由 F3 在各 _render_sX_payload 内补齐。
    """
    if not payload:
        return
    scenario_type = payload.get("scenario_type", "")
    fn = globals().get(f"_render_{scenario_type.lower()}_payload")
    if fn is None:
        st.header(_hc.h2("场景专属数据"))
        st.caption(f"未知场景：`{scenario_type}`，回退原始 JSON")
        st.json(payload)
        return
    fn(payload)


# ============ S1 功能迭代 ============

def _render_s1_payload(p: dict) -> None:
    st.header(_hc.h2("S1 功能迭代分析"))

    # vendor_profiles 表
    vps = p.get("vendor_profiles") or []
    if vps:
        st.subheader(_hc.h3("竞品画像（Forrester Wave 风格）"))
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
        st.dataframe(rows, use_container_width=True)

    # feature_matrix 表（categories × competitors 评分）
    fm = p.get("feature_matrix") or {}
    if fm.get("categories"):
        st.subheader(_hc.h3("功能矩阵"))
        st.caption(
            f"我方：{fm.get('our_product_name', '')} | "
            f"竞品：{', '.join(fm.get('competitors', []))} | "
            f"评分制：0=不支持 / 1=部分 / 2=完整支持"
        )
        rows = []
        for cat in fm.get("categories", []):
            for f in cat.get("features", []):
                row = {
                    "类别": cat.get("name", ""),
                    "权重": cat.get("weight", ""),
                    "功能": f.get("name", ""),
                }
                for comp, fs in (f.get("scores") or {}).items():
                    row[comp] = fs.get("score", "") if isinstance(fs, dict) else fs
                rows.append(row)
        if rows:
            st.dataframe(rows, use_container_width=True)
        ws = fm.get("weighted_scores") or {}
        if ws:
            st.caption("加权总分（百分比）：" + " · ".join(f"{k}={v}" for k, v in ws.items()))

    # 雷达图（F3）
    radar_scores = p.get("radar_scores") or []
    if radar_scores:
        st.subheader(_hc.h3("5 维雷达图"))
        _render_chart_or_skip(_radar_chart_s1(radar_scores))

    # tier1_disqualifiers
    t1d = p.get("tier1_disqualifiers") or []
    if t1d:
        st.subheader(_hc.h3("Tier 1 一票否决项"))
        for d in t1d:
            failing = ", ".join(d.get("competitors_failing") or [])
            st.markdown(f"- **{d.get('feature', '')}**：{failing} 不达标")
            st.caption(f"启示：{d.get('implication', '')}")

    # white_space_features
    ws_features = p.get("white_space_features") or []
    if ws_features:
        st.subheader(_hc.h3("无人触及功能（white space）"))
        st.dataframe([
            {
                "功能": w.get("feature", ""),
                "无人做的原因": w.get("why_no_one_supports", ""),
                "机会": w.get("opportunity_estimate", ""),
            }
            for w in ws_features
        ], use_container_width=True)

    # job_statement
    js = p.get("job_statement") or {}
    if js:
        st.subheader(_hc.h3("用户工作 JTBD"))
        st.markdown(
            f"**情境**：{js.get('situation', '')}\n\n"
            f"**动机**：{js.get('motivation', '')}\n\n"
            f"**期望结果**：{js.get('outcome', '')}"
        )
        st.caption(f"层次：{js.get('layer', '')}")

    # feature_gaps
    fgs = p.get("feature_gaps") or []
    if fgs:
        st.subheader(_hc.h3("功能差距"))
        st.dataframe([
            {
                "功能": g.get("feature_name", ""),
                "竞品已有": ", ".join(g.get("competitors_have_it") or []),
                "未满足结果": g.get("underserved_outcome", ""),
                "投入": g.get("estimated_effort", ""),
                "影响": g.get("estimated_impact", ""),
                "建议": g.get("recommendation", ""),
            }
            for g in fgs
        ], use_container_width=True)

    # roadmap_recommendations
    rr = p.get("roadmap_recommendations") or {}
    if rr:
        st.subheader(_hc.h3("路线图建议"))
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


# ============ S2 市场进入 ============

def _render_market_value(label: str, mv: dict) -> None:
    if not mv:
        return
    amount = mv.get("amount")
    unit = mv.get("unit", "")
    currency = mv.get("currency", "")
    basis = mv.get("value_basis", "")
    year = mv.get("year", "")
    geo = mv.get("geography", "")
    if amount is None:
        st.metric(label, "—", help=f"basis={basis}")
    else:
        st.metric(label, f"{amount} {unit} {currency}", help=f"{geo} {year} ({basis})")


def _render_s2_payload(p: dict) -> None:
    st.header(_hc.h2("S2 市场进入分析"))

    # market_sizing
    ms = p.get("market_sizing") or {}
    if ms:
        st.subheader(_hc.h3("市场规模 TAM/SAM/SOM"))
        cols = st.columns(3)
        with cols[0]:
            _render_market_value("TAM", ms.get("tam") or {})
        with cols[1]:
            _render_market_value("SAM", ms.get("sam") or {})
        with cols[2]:
            _render_market_value("SOM", ms.get("som") or {})
        cagr = ms.get("cagr_pct")
        if cagr is not None:
            st.caption(f"CAGR: {cagr}% / 预测年限: {ms.get('forecast_years', '—')} 年")

    # five_forces
    ff = p.get("five_forces") or {}
    if ff:
        st.subheader(_hc.h3("Porter 五力分析"))
        _render_chart_or_skip(_radar_chart_five_forces(ff))
        forces_map = [
            ("new_entrants", "新进入者威胁"),
            ("supplier_power", "供应商议价力"),
            ("buyer_power", "买家议价力"),
            ("substitute_threat", "替代品威胁"),
            ("competitive_rivalry", "现有竞争"),
        ]
        rows = [
            {
                "维度": label,
                "强度": _t((ff.get(k) or {}).get("intensity", "")),
                "影响": (ff.get(k) or {}).get("implication", ""),
            }
            for k, label in forces_map
        ]
        st.dataframe(rows, use_container_width=True)
        ia = p.get("industry_attractiveness_1_5")
        if ia is not None:
            st.caption(f"行业吸引力评分（1-5）：{ia}")

    # players
    players = p.get("players") or []
    if players:
        st.subheader(_hc.h3("市场玩家"))
        st.caption(f"市场集中度：{_t(p.get('market_concentration', ''))}")
        st.dataframe([
            {
                "名称": pl.get("name", ""),
                "公司": pl.get("company", ""),
                "角色": _t(pl.get("market_role", "")),
                "份额%": pl.get("market_share_pct", ""),
                "增速%": pl.get("yoy_growth_pct", ""),
                "推荐": "✓" if pl.get("is_recommended") else "",
                "已采集": "✓" if pl.get("is_collected") else "",
            }
            for pl in players
        ], use_container_width=True)
        for pl in players:
            diff = pl.get("key_differentiator", "")
            if diff:
                st.caption(f"{pl.get('name', '')}：{diff}")

    # consumer_segments
    segs = p.get("consumer_segments") or []
    if segs:
        st.subheader(_hc.h3("消费者分群"))
        st.dataframe([
            {
                "分群": s.get("name", ""),
                "份额%": s.get("share_pct", ""),
                "可触达": _t(s.get("addressability", "")),
            }
            for s in segs
        ], use_container_width=True)
        for s in segs:
            needs = s.get("key_needs") or []
            if needs:
                st.caption(f"{s.get('name', '')}：{' / '.join(needs)}")

    # key_trends
    trends = p.get("key_trends") or []
    if trends:
        st.subheader(_hc.h3("关键趋势"))
        st.dataframe([
            {
                "趋势": t.get("trend_name", ""),
                "方向": _t(t.get("direction", "")),
                "时间窗": _t(t.get("time_horizon", "")),
                "对进入影响": _t(t.get("impact_on_entry", "")),
            }
            for t in trends
        ], use_container_width=True)

    # entry_strategy
    es = p.get("entry_strategy") or {}
    if es:
        st.subheader(_hc.h3("进入策略"))
        st.markdown(f"**推荐模式**：{_t(es.get('recommended_mode', ''))}")
        st.markdown(f"**目标分群**：{', '.join(es.get('target_segments') or [])}")
        st.markdown(f"**初始定位**：{es.get('initial_positioning', '')}")
        ksf = es.get("key_success_factors") or []
        if ksf:
            st.markdown("**关键成功因素**：")
            for k in ksf:
                st.markdown(f"- {k}")
        risks = es.get("main_risks") or []
        if risks:
            st.markdown("**主要风险**：")
            for r in risks:
                st.markdown(
                    f"- {r.get('description', '')} "
                    f"（可能性：{_t(r.get('likelihood', ''))} / 影响：{_t(r.get('impact', ''))}）"
                )

    # competitor_recommendations（recommender 产出）
    rec = p.get("competitor_recommendations") or {}
    if rec:
        st.subheader(_hc.h3("Recommender 推荐玩家"))
        st.caption(f"行业：{rec.get('user_provided_industry', '')} | 方法：{rec.get('selection_method', '')}")
        rcs = rec.get("recommended_competitors") or []
        st.dataframe([
            {
                "名称": r.get("name", ""),
                "公司": r.get("company", ""),
                "推荐理由": r.get("why_recommended", ""),
                "置信度": r.get("confidence", ""),
            }
            for r in rcs
        ], use_container_width=True)


# ============ S3 定价策略 ============

def _render_s3_payload(p: dict) -> None:
    st.header(_hc.h2("S3 定价策略分析"))

    # pricing_baseline
    pb = p.get("pricing_baseline") or {}
    if pb:
        st.subheader(_hc.h3("当前定价基线"))
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

    # value_drivers
    vds = p.get("value_drivers") or []
    if vds:
        st.subheader(_hc.h3("价值驱动因素"))
        st.dataframe([
            {"驱动": v.get("driver_name", ""), "重要性": v.get("importance", ""), "证据": v.get("evidence", "")}
            for v in vds
        ], use_container_width=True)

    # feature_classification
    fc = p.get("feature_classification") or {}
    if fc:
        st.subheader(_hc.h3("功能分类"))
        cols = st.columns(3)
        with cols[0]:
            st.markdown("**Hygiene 基础**")
            for x in fc.get("hygiene_factors") or []:
                st.markdown(f"- {x}")
        with cols[1]:
            st.markdown("**Preference 偏好**")
            for x in fc.get("preference_drivers") or []:
                st.markdown(f"- {x}")
        with cols[2]:
            st.markdown("**Premium 溢价**")
            for x in fc.get("premium_drivers") or []:
                st.markdown(f"- {x}")

    # wtp_research
    wtp = p.get("wtp_research")
    if wtp:
        st.subheader(_hc.h3("支付意愿研究"))
        st.markdown(
            f"**方法**：`{wtp.get('method', '')}` | **置信度**：{wtp.get('confidence', '')}"
        )
        st.caption(f"理由：{wtp.get('rationale', '')}")
        if wtp.get("limitations"):
            st.caption(f"局限：{wtp.get('limitations', '')}")

    # packaging
    pkg = p.get("packaging") or {}
    tiers = pkg.get("tiers") or []
    if tiers:
        st.subheader(_hc.h3("推荐套餐设计 GBB"))
        cols = st.columns(len(tiers))
        for col, t in zip(cols, tiers):
            with col:
                badge = "⭐" if t.get("is_recommended") else ""
                st.markdown(f"### {badge} {t.get('name', '')}")
                st.caption(f"position: `{t.get('position', '')}`")
                mp = t.get("monthly_price")
                ap = t.get("annual_price")
                cur = t.get("currency", "")
                if mp is not None:
                    st.markdown(f"**月费**：{mp} {cur}")
                if ap is not None:
                    st.markdown(f"**年费**：{ap} {cur}")
                st.markdown(f"**对象**：{t.get('target_persona', '')}")
                feats = t.get("included_features") or []
                if feats:
                    st.markdown("**包含**：")
                    for f in feats:
                        st.markdown(f"- {f}")
        adv = pkg.get("annual_discount_pct")
        if adv is not None:
            st.caption(f"年付折扣：{adv}% | 默认周期：{pkg.get('default_billing_cycle', '')}")
        st.caption(pkg.get("rationale", ""))

    # competitive_pricing_matrix
    cpm = p.get("competitive_pricing_matrix") or []
    if cpm:
        st.subheader(_hc.h3("竞品定价矩阵"))
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

    # recommendations_summary
    rs = p.get("recommendations_summary") or {}
    if rs:
        st.subheader(_hc.h3("定价方案总结"))
        st.write(rs.get("recommended_packaging_summary", ""))
        uplift = rs.get("expected_arr_uplift_pct")
        basis = rs.get("expected_arr_uplift_basis", "")
        if uplift is not None:
            st.metric("预期 ARR 提升 %", f"{uplift}%", help=f"basis={basis}")
        st.caption(f"理由：{rs.get('expected_uplift_rationale', '')}")
        risks = rs.get("main_risks") or []
        if risks:
            st.markdown("**主要风险**：")
            for r in risks:
                st.markdown(f"- {r.get('description', '')}（缓解：{r.get('mitigation', '')}）")

    # rollout_plan
    rp = p.get("rollout_plan") or []
    if rp:
        st.subheader(_hc.h3("Rollout 步骤"))
        st.dataframe([
            {
                "步骤": s.get("step_name", ""),
                "周期": s.get("duration", ""),
                "负责团队": s.get("owner_team", ""),
                "成功指标": s.get("success_metric", ""),
            }
            for s in rp
        ], use_container_width=True)


# ============ S4 持续监控 ============

def _render_s4_payload(p: dict) -> None:
    st.header(_hc.h2("S4 持续监控分析"))

    # review_period
    rp = p.get("review_period") or {}
    if rp:
        st.subheader(_hc.h3("监控周期"))
        prior = rp.get("prior_trace_id")
        st.caption(
            f"周期：{rp.get('review_period_label', '')} | "
            f"竞品：{', '.join(rp.get('monitored_competitors') or [])} | "
            f"模式：{'增量' if prior else '首次基线'}"
        )

    # 5 类 changes
    change_groups = [
        ("feature_changes", "功能变更"),
        ("pricing_changes", "定价变更"),
        ("messaging_changes", "信息变更"),
        ("news_events", "新闻事件"),
        ("org_changes", "组织变更"),
    ]
    rendered_any = False
    for key, label in change_groups:
        items = p.get(key) or []
        if not items:
            continue
        if not rendered_any:
            st.subheader(_hc.h3("变更检测"))
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

    # threats
    threats = p.get("threats") or []
    if threats:
        st.subheader(_hc.h3("威胁评估"))
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

    # opportunities
    opps = p.get("opportunities") or []
    if opps:
        st.subheader(_hc.h3("机会识别 OSCOM"))
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

    # trends
    trends = p.get("trends") or {}
    if any(trends.get(k) for k in ("sentiment_trend", "pricing_trend", "release_velocity_trend", "threat_level_trend")):
        st.subheader(_hc.h3("趋势方向"))
        cols = st.columns(4)
        labels = [
            (cols[0], "情感", "sentiment_trend"),
            (cols[1], "定价", "pricing_trend"),
            (cols[2], "迭代速度", "release_velocity_trend"),
            (cols[3], "威胁等级", "threat_level_trend"),
        ]
        for col, label, key in labels:
            with col:
                v = trends.get(key) or "—"
                arrow = {"up": "↑", "down": "↓", "flat": "→"}.get(v, "")
                st.metric(label, f"{v} {arrow}")
        if trends.get("rationale"):
            st.caption(trends.get("rationale", ""))

    # monitoring_actions
    actions = p.get("monitoring_actions") or []
    if actions:
        st.subheader(_hc.h3("推荐行动"))
        st.dataframe([
            {
                "行动": a.get("description", ""),
                "团队": a.get("owner_team", ""),
                "优先级": a.get("priority_tier", ""),
                "截止": a.get("due_date_estimate", ""),
            }
            for a in actions
        ], use_container_width=True)

    # battlecards
    bcs = p.get("battlecards") or []
    if bcs:
        st.subheader(_hc.h3("活体战卡"))
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


# ============ S5 战略定位 ============

def _render_s5_payload(p: dict) -> None:
    st.header(_hc.h2("S5 战略定位分析"))

    # vendor_profiles（含 Gartner MQ 评分）
    vps = p.get("vendor_profiles") or []
    if vps:
        st.subheader(_hc.h3("竞品画像 Gartner MQ"))
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

    # perceptual_map
    pm = p.get("perceptual_map") or {}
    if pm:
        st.subheader(_hc.h3("感知地图 Perceptual Map"))
        _render_chart_or_skip(_scatter_perceptual_map(pm))
        x_axis = pm.get("x_axis") or {}
        y_axis = pm.get("y_axis") or {}
        st.caption(
            f"X 轴：{x_axis.get('attribute', '')} ({x_axis.get('low_label', '')} → {x_axis.get('high_label', '')}) | "
            f"Y 轴：{y_axis.get('attribute', '')} ({y_axis.get('low_label', '')} → {y_axis.get('high_label', '')})"
        )
        brands = pm.get("plotted_brands") or []
        st.dataframe([
            {
                "品牌": b.get("competitor_name", ""),
                "我方": "✓" if b.get("is_self") else "",
                "X": b.get("x_score", ""),
                "Y": b.get("y_score", ""),
                "置信": b.get("confidence", ""),
                "理由": b.get("score_rationale", ""),
            }
            for b in brands
        ], use_container_width=True)
        ws = pm.get("white_space") or []
        if ws:
            st.markdown("**空白区域机会**")
            for w in ws:
                st.markdown(f"- `{w.get('quadrant', '')}`：{w.get('opportunity_description', '')}")
        cz = pm.get("cluster_zones") or []
        if cz:
            st.markdown("**聚集区域**")
            for c in cz:
                st.markdown(f"- {', '.join(c.get('brands_in_cluster') or [])}：{c.get('implication', '')}")
        if pm.get("display_watermark"):
            st.caption(f"⚠️ {pm.get('display_watermark', '')}")

    # strategy_canvas
    sc = p.get("strategy_canvas") or {}
    if sc:
        st.subheader(_hc.h3("战略画布"))
        _render_chart_or_skip(_line_strategy_canvas(sc))
        factors = [f.get("name", "") for f in sc.get("competitive_factors") or []]
        rows = []
        for vc in sc.get("value_curves") or []:
            row = {"品牌": vc.get("competitor_name", ""), "我方": "✓" if vc.get("is_self") else ""}
            for f in factors:
                row[f] = (vc.get("factor_levels") or {}).get(f, "")
            rows.append(row)
        if rows:
            st.dataframe(rows, use_container_width=True)

    # errc_grid
    eg = p.get("errc_grid") or {}
    if eg:
        st.subheader(_hc.h3("ERRC 4 宫格"))
        cols = st.columns(4)
        for col, key, label in [
            (cols[0], "eliminate", "Eliminate 消除"),
            (cols[1], "reduce", "Reduce 减少"),
            (cols[2], "raise_level", "Raise 提升"),
            (cols[3], "create", "Create 创造"),
        ]:
            with col:
                st.markdown(f"**{label}**")
                for a in eg.get(key) or []:
                    st.markdown(f"- {a.get('factor', '')}")
                    st.caption(a.get("rationale", ""))

    # blue_ocean_move
    bom = p.get("blue_ocean_move")
    if bom:
        st.subheader(_hc.h3("蓝海战略动作"))
        st.markdown(f"**新价值曲线**：{bom.get('new_value_curve_summary', '')}")
        cols = st.columns(2)
        cols[0].metric("聚焦", bom.get("focus_assessment", ""))
        cols[1].metric("发散", bom.get("divergence_assessment", ""))
        st.markdown(f"**广告语**：> {bom.get('compelling_tagline', '')}")
        targets = bom.get("target_noncustomers") or []
        if targets:
            st.caption(f"目标非客户：{', '.join(targets)}")

    # positioning_statement —— [fix21] 6 位模板分行渲染 + 水印独立 warning
    ps = p.get("positioning_statement") or {}
    if ps:
        st.subheader(_hc.h3("定位陈述（Geoffrey Moore 6 位模板）"))
        st.caption(f"置信度：`{ps.get('confidence', '')}`")
        if ps.get("confidence") and ps["confidence"] != "from_user_brief":
            st.warning("⚠️ 本定位陈述为 AI 推断版本，请人工校对后再对外使用")
        # 6 位模板按 markdown 列表分行渲染（不再依赖 full_statement_text 的英文连接词长串）
        st.markdown(
            f"- **For**（目标客户）：{ps.get('target_customer', '')}\n"
            f"- **who**（核心需求/机会）：{ps.get('need_or_opportunity', '')}\n"
            f"- **{ps.get('product_name', '')} is a**（产品品类）：{ps.get('product_category', '')}\n"
            f"- **that**（核心价值）：{ps.get('key_benefit', '')}\n"
            f"- **Unlike**（主要替代方案）：{ps.get('primary_alternative', '')}\n"
            f"- **our product**（差异化）：{ps.get('primary_differentiation', '')}"
        )

    # category_strategy
    cs = p.get("category_strategy") or {}
    if cs:
        st.subheader(_hc.h3("品类战略"))
        st.markdown(f"**选定品类**：{cs.get('chosen_category', '')}")
        st.caption(f"理由：{cs.get('why_this_category', '')}")
        implied = cs.get("competitors_implied") or []
        if implied:
            st.markdown(f"**隐含竞品**：{', '.join(implied)}")
        if cs.get("risk_of_category_choice"):
            st.caption(f"风险：{cs.get('risk_of_category_choice', '')}")


def render_analysis_response(data: dict) -> None:
    """统一处理 /analyze 响应：根据 status + report 决定 success/warning/error 文案。

    fix3：report=None 或空时不显示"分析完成"误导文案，而是 warning 提示
    用户去执行追溯面板查中间产物（包含 trace_id 链接）。

    fix6：把完整 data 存到 session_state['last_response']。Streamlit 每次按钮
    点击全脚本重跑，"开始分析" if 块在重跑时不再执行，报告会消失。主入口需在
    if 块外读 session_state['last_response'] 重新调用本函数，让结果跨重跑保留。
    """
    status = data.get("status")
    trace_id = data.get("trace_id", "")
    report = data.get("report")

    # fix6: 无条件持久化整个 response，便于主入口跨重跑恢复
    st.session_state["last_response"] = data

    if status != "completed":
        err = data.get("error", "未知错误")
        st.error(f"分析失败: {err}")
        return

    if not report:
        st.warning(
            f"分析未能产出有效报告（trace_id={trace_id}），"
            "请展开下方「执行追溯（中间产物）」面板查看 4 阶段中间产物 + run.log 定位原因。"
        )
        if trace_id:
            st.session_state["last_trace_id"] = trace_id
        return

    st.success(f"分析完成！Trace ID: {trace_id}")
    if trace_id:
        st.session_state["last_trace_id"] = trace_id
    render_base_report(report, trace_id=trace_id)


def render_trace_report_tab(report: dict | None, *, trace_id: str | None = None) -> None:
    """[fix16] 追溯面板「报告」tab 用：渲染历史 trace 的美化报告 + 折叠原始 JSON。

    解决问题：之前追溯面板只 st.json 展示原始 BaseReport JSON，可读性差。
    现在 default 渲染美化版，旁边折叠区保留原始 JSON 供诊断使用。
    trace_id 不为空时顶部也显示导出双按钮。
    """
    if not report:
        st.warning("该 trace 报告为空（可能 graph 失败强制结束 / 未跑到 writer 阶段）")
        return
    render_base_report(report, trace_id=trace_id)
    with st.expander("查看原始 JSON（诊断用）", expanded=False):
        st.json(report)


# API_BASE 与 app.py 同源；render.py 独立提供常量避免循环 import
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
  <a href="{md_url}" download class="btn-export">导出 Markdown</a>
  <a href="{html_url}" download class="btn-export">导出 HTML</a>
  <span style="color:var(--color-text-secondary);font-size:12px;margin-left:12px">
    Trace: <code>{trace_id}</code>
  </span>
</div>""",
        unsafe_allow_html=True,
    )


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


def _format_data_sources(report: dict) -> tuple[str, str]:
    """KPI 数据源数 = 全报告实际引用的独立 URL 去重数。"""
    urls = set()
    _collect_all_urls(report, urls)
    if not urls:
        return "—", ""
    return str(len(urls)), ""


def _collect_all_urls(obj, urls: set):
    """递归收集报告中所有 source_refs 的 url。"""
    if isinstance(obj, dict):
        if "url" in obj and "source_type" in obj and obj.get("url"):
            urls.add(obj["url"])
        for v in obj.values():
            _collect_all_urls(v, urls)
    elif isinstance(obj, list):
        for item in obj:
            _collect_all_urls(item, urls)


def _format_competitors(report: dict) -> tuple[str, str]:
    scope = report.get("scope") or {}
    comps = scope.get("competitors") or []
    total = len(comps)
    if total == 0:
        return "—", ""
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
    """5 张 KPI 卡：质检评分 / 场景标签 / 竞品数量 / 数据源数 / 可信度。"""
    if not report:
        return
    meta = report.get("metadata") or {}

    qs_main, qs_sub = _format_quality_score(meta)
    scenario = meta.get("scenario") or "—"
    scenario_sub = _SCENARIO_LABELS.get(scenario, "")
    comp_main, comp_sub = _format_competitors(report)
    src_main, src_sub = _format_data_sources(report)
    _raw_conf = meta.get("confidence_level") or ""
    conf_level = _t(_raw_conf) if _raw_conf else "—"
    conf_color = _confidence_color(conf_level)

    cols = st.columns(5)
    cards = [
        (cols[0], "质检评分", qs_main, qs_sub, None),
        (cols[1], "场景标签", scenario, scenario_sub, None),
        (cols[2], "竞品数量", comp_main, comp_sub, None),
        (cols[3], "参考资料", src_main, src_sub, None),
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


def render_base_report(report: dict, *, trace_id: str | None = None) -> None:
    """主入口：按 BaseReport schema 顺序渲染。

    trace_id 不为空时顶部显示导出双按钮（Markdown / HTML）+ KPI 5 卡。
    """
    if not report:
        st.warning("报告为空")
        return

    _hc.reset()

    if trace_id:
        _render_export_buttons(trace_id)
    _render_kpi_strip(report)

    title = report.get("title", "")
    subtitle = report.get("subtitle", "")
    if title:
        st.title(title)
    if subtitle:
        from html import escape as _html_escape
        st.markdown(
            f'<p class="report-subtitle">{_html_escape(subtitle)}</p>',
            unsafe_allow_html=True,
        )

    _render_at_a_glance(report.get("at_a_glance") or [])
    _render_executive_summary(report.get("executive_summary") or {})

    bg = report.get("background", "")
    if bg:
        st.header(_hc.h2("背景"))
        st.write(bg)

    _render_scope_and_methodology(
        report.get("scope") or {},
        report.get("methodology") or {},
    )

    _render_key_findings(report.get("key_findings") or [])
    _render_analysis_sections(report.get("analysis_sections") or [])

    render_scenario_payload(report.get("scenario_payload"))

    _render_swot(report.get("swot") or {})

    conclusions = report.get("conclusions", "")
    if conclusions:
        st.header(_hc.h2("结论"))
        st.write(conclusions)

    _render_recommendations(report.get("recommendations") or [])

    _render_appendix(report.get("appendix") or {}, report=report)
    _render_metadata_panel(report.get("metadata") or {})
