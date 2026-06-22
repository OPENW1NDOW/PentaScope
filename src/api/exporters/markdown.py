"""BaseReport → Markdown 导出器（PD-2 关键字段覆盖）。

策略：纯字符串拼接 + format 模板，零模板引擎依赖。
按 BaseReport schema 顺序输出；5 场景 payload 各有 _render_sN_md 函数。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Callable
from urllib.parse import urlparse

from src.utils.translations import _t

_BEIJING = timezone(timedelta(hours=8))

_SCENARIO_NAMES = {
    "S1": "S1 功能迭代",
    "S2": "S2 市场进入",
    "S3": "S3 定价策略",
    "S4": "S4 持续监控",
    "S5": "S5 战略定位",
}

import threading

_CN_NUMBERS = ["一", "二", "三", "四", "五", "六", "七", "八", "九", "十",
               "十一", "十二", "十三", "十四", "十五", "十六", "十七", "十八", "十九", "二十"]

_md_local = threading.local()


def _reset_md_counter():
    _md_local.l2 = 0
    _md_local.l3 = 0


def _md_h2(title: str) -> str:
    _md_local.l2 = getattr(_md_local, "l2", 0) + 1
    _md_local.l3 = 0
    n = _md_local.l2
    prefix = _CN_NUMBERS[n - 1] if n <= len(_CN_NUMBERS) else str(n)
    return f"{prefix}、{title}"


def _md_h3(title: str) -> str:
    _md_local.l3 = getattr(_md_local, "l3", 0) + 1
    n = _md_local.l3
    prefix = _CN_NUMBERS[n - 1] if n <= len(_CN_NUMBERS) else str(n)
    return f"（{prefix}）{title}"


# ============ 公共骨架渲染 ============

def _render_at_a_glance(items: list) -> str:
    if not items:
        return ""
    lines = [f"\n## {_md_h2('核心要点')}\n"]
    for it in items:
        lines.append(f"- {it}")
    return "\n".join(lines)


def _render_executive_summary(es: dict) -> str:
    if not es:
        return ""
    lines = [f"\n## {_md_h2('执行摘要')}"]
    for label, key in [("背景定位", "context"), ("核心论断", "core_thesis"),
                       ("现实启示", "implications")]:
        v = es.get(key)
        if v:
            lines.append(f"\n### {_md_h3(label)}\n\n{v}")
    kfb = es.get("key_findings_brief") or []
    if kfb:
        lines.append(f"\n### {_md_h3('关键发现速览')}\n")
        for f in kfb:
            lines.append(f"- {f}")
    pf = es.get("path_forward") or []
    if pf:
        lines.append(f"\n### {_md_h3('行动路径')}\n")
        for p in pf:
            lines.append(f"- {p}")
    return "\n".join(lines)


def _render_scope(scope: dict) -> str:
    if not scope:
        return ""
    lines = [f"\n## {_md_h2('分析范围')}\n"]
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
    lines = [f"\n## {_md_h2('方法论')}\n"]
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
    lines = [f"\n## {_md_h2('关键发现')}\n"]
    for i, f in enumerate(findings, 1):
        lines.append(f"### {_md_h3(f'发现 {i}')}")
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
    lines = [f"\n## {_md_h2('详细章节')}\n"]
    for sec in sections:
        lines.append(f"### {_md_h3(sec.get('heading', ''))}")
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
    lines = [f"\n## {_md_h2('SWOT 分析')}\n"]
    for key, label in [("strengths", "优势 S"), ("weaknesses", "劣势 W"),
                       ("opportunities", "机会 O"), ("threats", "威胁 T")]:
        entries = swot.get(key) or []
        if entries:
            lines.append(f"### {_md_h3(label)}\n")
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
    lines = [f"\n## {_md_h2('行动建议')}\n"]
    groups: dict[str, list] = {"immediate": [], "short_term": [], "long_term": []}
    for r in recs:
        groups.setdefault(r.get("timeline", "long_term"), []).append(r)
    for tl_key, tl_label in [("immediate", "即时（1 个月内）"),
                             ("short_term", "短期（3 个月内）"),
                             ("long_term", "长期（6-12 个月）")]:
        items = groups.get(tl_key) or []
        if not items:
            continue
        lines.append(f"### {_md_h3(tl_label)}\n")
        for r in items:
            priority = r.get("priority", "")
            action = r.get("action", "")
            lines.append(f"#### [{_t(priority)}] {action}")
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
    for i, ref in enumerate(refs, 1):
        if not isinstance(ref, dict):
            continue
        url = ref.get("url", "")
        title = ref.get("title", "") or (urlparse(url).netloc if url else "") or f"来源 {i}"
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
        out.append(
            "| 竞品 | 功能广度 (feature_breadth) | 易用性 (usability) | "
            "性价比 (cost_effectiveness) | 稳定性 (stability) | 设计质量 (design_quality) |"
        )
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
                f"| {g.get('feature_name', '')} | "
                f"{', '.join(g.get('competitors_have_it') or [])} | "
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
            out.append(
                f"| {label} | {data.get('intensity', '')} | "
                f"{data.get('implication', '')} |"
            )
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
        out.append(
            f"\n### 当前定价基线\n\n模式：`{pb.get('current_pricing_model', '')}` · "
            f"层级数：{pb.get('current_tier_count', '')}"
        )
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
                    out.append(
                        f"| {t.get('name', '')} | {t.get('monthly_price', '')} | "
                        f"{t.get('annual_price', '')} |"
                    )
    rs = p.get("recommendations_summary") or {}
    if rs:
        out.append("\n### 定价方案总结\n")
        out.append(rs.get("recommended_packaging_summary", ""))
        if rs.get("expected_arr_uplift_pct") is not None:
            out.append(
                f"\n预期 ARR 提升：{rs['expected_arr_uplift_pct']}%"
                f"（依据：{rs.get('expected_arr_uplift_basis', '')}）"
            )
    return "\n".join(out)


def _render_s4_md(p: dict) -> str:
    out = []
    rp = p.get("review_period") or {}
    if rp:
        out.append(
            f"\n### 监控周期\n\n周期：{rp.get('review_period_label', '')} · "
            f"竞品：{', '.join(rp.get('monitored_competitors') or [])}"
        )
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
            out.append(
                f"| {it.get('competitor_name', '')} | {ct} | {fact} | "
                f"{it.get('severity', '')} |"
            )
    threats = p.get("threats") or []
    if threats:
        out.append("\n### 威胁评估\n")
        out.append("| 标题 | 严重度 | 可能性 | 应对 |")
        out.append("|------|--------|--------|------|")
        for t in threats:
            out.append(
                f"| {t.get('title', '')} | {t.get('severity', '')} | "
                f"{t.get('likelihood', '')} | {t.get('recommended_response', '')} |"
            )
    opps = p.get("opportunities") or []
    if opps:
        out.append("\n### 机会识别\n")
        out.append("| 类型 | 投入 | 影响 | 描述 |")
        out.append("|------|------|------|------|")
        for o in opps:
            out.append(
                f"| {o.get('opportunity_type', '')} | "
                f"{o.get('estimated_effort', '')} | "
                f"{o.get('expected_impact', '')} | {o.get('description', '')} |"
            )
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
                f"| {v.get('competitor_name', '')} | "
                f"{v.get('ability_to_execute_score', '')} | "
                f"{v.get('completeness_of_vision_score', '')} | "
                f"{v.get('mq_quadrant', '')} | {v.get('overview', '')} |"
            )
    pm = p.get("perceptual_map") or {}
    if pm:
        out.append("\n### 感知地图 Perceptual Map\n")
        x_axis = pm.get("x_axis") or {}
        y_axis = pm.get("y_axis") or {}
        out.append(
            f"X 轴：{x_axis.get('attribute', '')} "
            f"({x_axis.get('low_label', '')} → {x_axis.get('high_label', '')})"
        )
        out.append(
            f"Y 轴：{y_axis.get('attribute', '')} "
            f"({y_axis.get('low_label', '')} → {y_axis.get('high_label', '')})"
        )
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
                levels = [
                    str((vc.get("factor_levels") or {}).get(f, "")) for f in factors
                ]
                out.append(
                    f"| {vc.get('competitor_name', '')} | {self_mark} | "
                    + " | ".join(levels) + " |"
                )
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
    out.append(
        "\n> 注：可视化图表（Magic Quadrant / Perceptual Map / Strategy Canvas）见 HTML 版本"
    )
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

    PD-2 宽松字段覆盖：每场景渲染常用字段；嵌套深字段（如 S3
    pricing_page_audit 8 法则）放弃覆盖。
    """
    _reset_md_counter()
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
        parts.append(f"\n## {_md_h2('背景')}\n\n{bg}")

    parts.append(_render_scope(report.get("scope") or {}))
    parts.append(_render_methodology(report.get("methodology") or {}))
    parts.append(_render_key_findings(report.get("key_findings") or []))
    parts.append(_render_analysis_sections(report.get("analysis_sections") or []))
    parts.append(_render_swot(report.get("swot") or {}))

    conclusions = report.get("conclusions")
    if conclusions:
        parts.append(f"\n## {_md_h2('结论')}\n\n{conclusions}")

    parts.append(_render_recommendations(report.get("recommendations") or []))

    # 场景专属
    payload = report.get("scenario_payload") or {}
    scenario_type = (
        payload.get("scenario_type")
        or (report.get("metadata") or {}).get("scenario")
        or ""
    )
    fn = _SCENARIO_RENDERERS.get(scenario_type)
    scenario_full = _SCENARIO_NAMES.get(scenario_type, scenario_type)
    if fn:
        parts.append(f"\n## {_md_h2(f'场景专属：{scenario_full}')}\n")
        parts.append(fn(payload))
    elif scenario_type:
        parts.append(f"\n## 场景专属：{scenario_type}\n\n（未注册渲染器，跳过细节）")

    parts.append(_render_appendix(report.get("appendix") or {}))

    parts.append(f"\n\n---\n\n*由 AI 驱动竞品分析 Agent 协作系统生成 · trace `{trace_id}`*\n")

    return "\n".join(p for p in parts if p)
