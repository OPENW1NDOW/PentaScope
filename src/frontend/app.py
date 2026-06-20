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

# 输入区
st.header("输入")

analysis_context = st.text_area(
    "分析意图描述",
    placeholder="例：分析飞书和语雀的协作文档差异，重点看定价",
    height=80,
    key="analysis_context",
)

# AI 帮选场景：根据 analysis_context 调后端推断
col_pick, col_info = st.columns([1, 4])
with col_pick:
    if st.button("AI 帮我选场景", help="根据分析意图描述自动推断最合适的场景"):
        if not (analysis_context or "").strip():
            st.warning("请先填写分析意图描述")
        else:
            try:
                with st.spinner("AI 正在推断..."):
                    pr = httpx.post(
                        f"{API_BASE}/pick-scenario",
                        json={"user_text": analysis_context},
                        timeout=60,
                    )
                if pr.status_code == 200:
                    pj = pr.json()
                    st.session_state["picked_scenario"] = pj["scenario"]
                    st.session_state["pick_confidence"] = pj["confidence"]
                    st.session_state["pick_rationale"] = pj["rationale"]
                else:
                    st.error(f"推断失败（{pr.status_code}）：{pr.text}")
            except httpx.ConnectError:
                st.error("无法连接后端服务")
            except Exception as e:
                st.error(f"推断出错: {e}")
with col_info:
    if "picked_scenario" in st.session_state:
        conf = st.session_state.get("pick_confidence", "low")
        emoji = {"high": "🟢", "medium": "🟡", "low": "🟠"}.get(conf, "")
        st.caption(
            f"AI 推荐：**{st.session_state['picked_scenario']}**（置信度 {emoji} {conf}）— "
            f"{st.session_state.get('pick_rationale', '')}"
        )

_options = ["S1", "S2", "S3", "S4", "S5"]
_default_idx = _options.index(st.session_state["picked_scenario"]) if st.session_state.get("picked_scenario") in _options else 0
scenario = st.selectbox(
    "选择分析场景",
    options=_options,
    index=_default_idx,
    format_func=lambda s: {
        "S1": "S1 功能迭代（已有产品对标）",
        "S2": "S2 市场进入（无产品调研）",
        "S3": "S3 定价策略",
        "S4": "S4 持续监控",
        "S5": "S5 战略定位",
    }[s],
)

# 按 scenario 切换字段
industry = ""
our_product_name = ""
our_product_brief = ""
prior_trace_id = ""
competitor_names = ""

if scenario == "S2":
    industry = st.text_input("行业 / 赛道（必填）", placeholder="知识管理 SaaS")
    competitor_names = st.text_area(
        "已知竞品（可选，每行一个）",
        placeholder="留空则由 AI 推荐 Top 3-5",
        height=80,
    )
else:
    our_product_name = st.text_input("我方产品名称（必填）", placeholder="如：MyProduct")
    our_product_brief = st.text_area("我方产品简介（选填）", height=60)
    competitor_names = st.text_area(
        "竞品名称（每行一个，必填）",
        placeholder="支付宝\n微信支付",
        height=100,
    )
    if scenario == "S4":
        prior_trace_id = st.text_input(
            "上次监控 trace_id（选填）",
            placeholder="留空则首次监控",
        )

if st.button("开始分析", type="primary"):
    competitors = [
        {"name": name.strip()}
        for name in (competitor_names or "").strip().split("\n")
        if name.strip()
    ]
    if not analysis_context.strip():
        st.error("请输入分析意图描述")
    elif scenario == "S2" and not industry.strip():
        st.error("S2 市场进入场景必须填写行业 / 赛道")
    elif scenario != "S2" and not competitors:
        st.error(f"{scenario} 场景必须至少填一个竞品")
    elif scenario != "S2" and not our_product_name.strip():
        st.error(f"{scenario} 场景必须填写我方产品名称")
    else:
        body = {
            "scenario": scenario,
            "competitors": competitors,
            "industry": industry or None,
            "analysis_context": analysis_context,
            "our_product_name": our_product_name or None,
            "our_product_brief": our_product_brief or None,
            "prior_trace_id": prior_trace_id or None,
        }

        # 输入一致性检查：对比 AI 推断场景与用户手选
        _proceed = True
        _picked = st.session_state.get("picked_scenario")
        _picked_conf = st.session_state.get("pick_confidence", "low")
        # 仅在用户未采纳 AI 推荐时检查（已采纳 = selectbox 值与推荐一致）
        if _picked and _picked != scenario and _picked_conf != "low":
            _rationale = st.session_state.get("pick_rationale", "")
            st.warning(
                f"AI 推断您的需求更适合 **{_picked}**（{_rationale}），"
                f"当前选择为 **{scenario}**。如确认无误可继续。"
            )
            col_go, col_switch = st.columns(2)
            with col_go:
                if st.button("继续使用当前场景", key="confirm_scenario"):
                    _proceed = True
            with col_switch:
                if st.button(f"切换到 {_picked}", key="switch_scenario"):
                    st.session_state["picked_scenario"] = _picked
                    st.rerun()
            if not st.session_state.get("confirm_scenario"):
                _proceed = False
        elif not _picked and analysis_context.strip():
            # 用户没点过"AI 帮我选"，自动做一次静默检查
            try:
                _check = httpx.post(
                    f"{API_BASE}/pick-scenario",
                    json={"user_text": analysis_context},
                    timeout=15,
                )
                if _check.status_code == 200:
                    _cj = _check.json()
                    if _cj["scenario"] != scenario and _cj["confidence"] != "low":
                        st.warning(
                            f"AI 推断您的需求更适合 **{_cj['scenario']}**"
                            f"（{_cj.get('rationale', '')}），当前选择为 **{scenario}**。"
                        )
                        st.session_state["picked_scenario"] = _cj["scenario"]
                        st.session_state["pick_confidence"] = _cj["confidence"]
                        st.session_state["pick_rationale"] = _cj.get("rationale", "")
                        col_go2, col_switch2 = st.columns(2)
                        with col_go2:
                            if st.button("继续使用当前场景", key="confirm_scenario_auto"):
                                _proceed = True
                        with col_switch2:
                            if st.button(f"切换到 {_cj['scenario']}", key="switch_scenario_auto"):
                                st.session_state["picked_scenario"] = _cj["scenario"]
                                st.rerun()
                        if not st.session_state.get("confirm_scenario_auto"):
                            _proceed = False
            except Exception:
                pass  # 静默检查失败不阻断

        if not _proceed:
            st.stop()

        with st.spinner("正在分析中，请稍候..."):
            try:
                response = httpx.post(
                    f"{API_BASE}/analyze",
                    json=body,
                    timeout=3600,
                )
                data = response.json()

                if response.status_code != 200:
                    detail = data.get("detail", data)
                    if isinstance(detail, list):
                        msgs = [d.get("msg", str(d)) for d in detail]
                        st.error("请求校验失败：" + "；".join(msgs))
                    else:
                        st.error(f"请求失败（{response.status_code}）：{detail}")
                else:
                    render_analysis_response(data)

            except httpx.ConnectError:
                st.error("无法连接后端服务，请确认 FastAPI 已启动 (uvicorn src.api.main:app --port 8000)")
            except Exception as e:
                st.error(f"发生错误: {e}")

# fix6：Streamlit 每次按钮点击全脚本重跑会让上面"开始分析"if 块跳过，
# 导致报告消失。从 session_state 恢复上次结果，让追溯按钮等任何重跑都不丢报告。
elif "last_response" in st.session_state:
    render_analysis_response(st.session_state["last_response"])

# 执行追溯面板（可观测性：查看每个 Agent 的中间产物与决策过程）
st.divider()
with st.expander("执行追溯（中间产物）", expanded=False):
    tid_input = st.text_input("Trace ID", value=st.session_state.get("last_trace_id", "")).strip()
    if st.button("加载追溯") and tid_input:
        try:
            r = httpx.get(f"{API_BASE}/trace/{tid_input}", timeout=30)
            if r.status_code != 200:
                st.error(f"加载失败：{r.json().get('detail', r.status_code)}")
            else:
                t = r.json()
                tabs = st.tabs(["元信息", "采集", "分析", "报告", "质检", "日志"])
                with tabs[0]:
                    st.json(t.get("meta") or {})
                with tabs[1]:
                    st.json(t["stages"].get("profiles"))
                with tabs[2]:
                    st.json(t["stages"].get("analysis"))
                with tabs[3]:
                    render_trace_report_tab(t["stages"].get("report"), trace_id=tid_input)
                with tabs[4]:
                    st.json(t["stages"].get("feedback"))
                with tabs[5]:
                    st.code(t.get("log") or "（无日志）")
                if t.get("snapshots"):
                    st.markdown("**重试快照（打回前的历史版本）**")
                    ver = st.selectbox("选择历史版本", t["snapshots"])
                    if st.button("查看该版本"):
                        rv = httpx.get(f"{API_BASE}/trace/{tid_input}", params={"version": ver}, timeout=30)
                        if rv.status_code == 200:
                            st.json(rv.json()["stages"].get(ver))
                        else:
                            st.error("加载该版本失败")
        except httpx.ConnectError:
            st.error("无法连接后端服务")
        except Exception as e:
            st.error(f"加载追溯出错: {e}")
