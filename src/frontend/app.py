import streamlit as st
import httpx

API_BASE = "http://localhost:8000/api/v1"

st.set_page_config(page_title="竞品分析 Agent 系统", layout="wide")
st.title("竞品分析 Agent 系统")

# 输入区
st.header("输入")
col1, col2 = st.columns([1, 1])

with col1:
    competitor_names = st.text_area(
        "竞品名称（每行一个）",
        placeholder="支付宝\n微信支付",
        height=100,
    )

with col2:
    analysis_context = st.text_area(
        "分析意图描述",
        placeholder="分析支付宝最近的新功能，我们准备做一个类似的功能",
        height=100,
    )

if st.button("开始分析", type="primary"):
    if not competitor_names.strip():
        st.error("请输入至少一个竞品名称")
    elif not analysis_context.strip():
        st.error("请输入分析意图描述")
    else:
        competitors = [{"name": name.strip()} for name in competitor_names.strip().split("\n") if name.strip()]

        with st.spinner("正在分析中，请稍候..."):
            try:
                response = httpx.post(
                    f"{API_BASE}/analyze",
                    json={"competitors": competitors, "analysis_context": analysis_context},
                    timeout=600,
                )
                data = response.json()

                if response.status_code != 200:
                    detail = data.get("detail", data)
                    if isinstance(detail, list):
                        msgs = [d.get("msg", str(d)) for d in detail]
                        st.error("请求校验失败：" + "；".join(msgs))
                    else:
                        st.error(f"请求失败（{response.status_code}）：{detail}")
                elif data["status"] == "completed":
                    report = data["report"]
                    st.success(f"分析完成！Trace ID: {data['trace_id']}")

                    # 执行摘要
                    st.header("执行摘要")
                    es = report.get("executive_summary", {})
                    for label, key in [
                        ("竞品做对了什么", "what_competitors_did_right"),
                        ("竞品的短板", "what_competitors_did_wrong"),
                        ("我们的机会", "our_opportunities"),
                        ("下一步行动", "next_steps_summary"),
                    ]:
                        st.subheader(label)
                        st.write(es.get(key, ""))

                    # 行动建议
                    st.header("行动建议")
                    ai = report.get("action_items", {})
                    for layer_name, layer_label in [
                        ("immediate", "即时（1个月内）"),
                        ("short_term", "短期（3个月内）"),
                        ("long_term", "长期（6-12个月）"),
                    ]:
                        items = ai.get(layer_name, [])
                        if items:
                            st.subheader(layer_label)
                            for item in items:
                                priority = item.get("priority", "")
                                desc = item.get("description", "")
                                rationale = item.get("rationale", "")
                                st.markdown(f"**[{priority}]** {desc}")
                                if rationale:
                                    st.caption(f"依据：{rationale}")

                    # 报告章节
                    st.header("详细报告")
                    for section in report.get("sections", []):
                        st.subheader(section.get("title", ""))
                        st.markdown(section.get("content", ""))

                    # 元数据
                    with st.expander("元数据"):
                        st.json(report.get("metadata", {}))

                else:
                    st.error(f"分析失败: {data.get('error', '未知错误')}")

            except httpx.ConnectError:
                st.error("无法连接后端服务，请确认 FastAPI 已启动 (uvicorn src.api.main:app --port 8000)")
            except Exception as e:
                st.error(f"发生错误: {e}")
