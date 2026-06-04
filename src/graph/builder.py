import logging
from langgraph.graph import StateGraph, END
from src.graph.state import AnalysisState
from src.agents.collector import CollectorAgent
from src.agents.analyzer import AnalyzerAgent
from src.agents.writer import WriterAgent
from src.agents.inspector import InspectorAgent
from src.agents.collection_pipeline import CollectionPipeline
from src.tools.sources import SerpApiSource
from src.utils.config import settings

logger = logging.getLogger(__name__)


def build_graph(llm, http, parser, trace_writer=None):
    """构建 LangGraph 状态图，返回 (compiled_graph, node_trace)"""
    search_source = SerpApiSource(http=http, api_key=settings.SEARCH_API_KEY)
    pipeline = CollectionPipeline(
        llm=llm, http=http, parser=parser, search_source=search_source,
        max_top_n=settings.SEARCH_TOP_N, pick_timeout=settings.PICK_LLM_TIMEOUT,
        max_concurrency=settings.MAX_FETCH_CONCURRENCY,
    )
    collector = CollectorAgent(llm=llm, pipeline=pipeline)
    analyzer = AnalyzerAgent(llm=llm)
    writer = WriterAgent(llm=llm)
    inspector = InspectorAgent(llm=llm)

    # 记录节点执行与路由决策序列（可观测性追溯）
    node_trace: list = []

    def _save(stage: str, data):
        # 落盘是辅助能力，trace_writer 为 None 时跳过
        if trace_writer is not None:
            trace_writer.save_stage(stage, data)

    async def collector_node(state: AnalysisState) -> dict:
        logger.info("[graph] → collector")
        node_trace.append("collector")
        profiles, goal = await collector.collect(state["user_input"])
        _save("01_profiles", profiles)
        return {"profiles": profiles, "analysis_goal": goal, "current_node": "collector"}

    async def analyzer_node(state: AnalysisState) -> dict:
        logger.info("[graph] → analyzer")
        node_trace.append("analyzer")
        analysis = await analyzer.analyze(state["profiles"])
        _save("02_analysis", analysis)
        return {"analysis": analysis, "current_node": "analyzer"}

    async def writer_node(state: AnalysisState) -> dict:
        logger.info("[graph] → writer")
        node_trace.append("writer")
        competitors = [c.name for c in state["user_input"].competitors]
        report = await writer.write(state["analysis"], competitors)
        # 从采集阶段汇总信息溯源，回填到报告（writer 拿不到 profile，需在此补全）
        sources = sorted({
            src
            for profile in state.get("profiles", [])
            for src in profile.metadata.data_sources
        })
        if sources:
            report.metadata.data_sources = sources
        goal = state.get("analysis_goal")
        if goal is not None:
            report.metadata.analysis_goal = goal
        _save("03_report", report)
        return {"report": report, "current_node": "writer"}

    async def inspector_node(state: AnalysisState) -> dict:
        logger.info("[graph] → inspector")
        node_trace.append("inspector")
        report = state["report"]
        competitors = [c.name for c in state["user_input"].competitors]
        feedback = await inspector.inspect(
            report,
            competitors=competitors,
            retry_count=state.get("retry_count", 0),
            max_retries=state.get("max_retries", 2),
        )
        # 根据质检 issue 严重度回填质量分（0-1，writer 默认填 0，此处给出真实评分）
        penalty = {"critical": 0.4, "major": 0.2, "minor": 0.05}
        score = max(0.0, 1.0 - sum(penalty[i.severity] for i in feedback.issues))
        report.metadata.quality_score = round(score, 2)
        _save("04_feedback", feedback)
        return {
            "report": report,
            "feedback": feedback,
            "retry_count": state.get("retry_count", 0) + (0 if feedback.passed else 1),
            "current_node": "inspector",
        }

    def should_continue(state: AnalysisState) -> str:
        """质检通过→结束，不通过且未超限→回到 writer，超限→强制结束"""
        feedback = state.get("feedback")
        if feedback is None or feedback.passed:
            return "end"

        retry_count = state.get("retry_count", 0)
        max_retries = state.get("max_retries", 2)

        if retry_count >= max_retries:
            logger.warning("[graph] 质检打回超限 (%d/%d), 强制结束", retry_count, max_retries)
            node_trace.append(f"reject->end(retry={retry_count})")
            return "end"

        # 根据 issues 中的 agent 字段决定回到哪个节点
        target_agents = {issue.agent for issue in feedback.issues}
        issues_summary = [f"{i.agent}:{i.severity}:{i.field}" for i in feedback.issues]
        if "collector" in target_agents:
            target = "collector"
        elif "analyzer" in target_agents:
            target = "analyzer"
        else:
            target = "writer"
        node_trace.append(f"reject->{target} issues={issues_summary}")
        return target

    # 构建图
    graph = StateGraph(AnalysisState)

    graph.add_node("collector", collector_node)
    graph.add_node("analyzer", analyzer_node)
    graph.add_node("writer", writer_node)
    graph.add_node("inspector", inspector_node)

    graph.set_entry_point("collector")

    graph.add_edge("collector", "analyzer")
    graph.add_edge("analyzer", "writer")
    graph.add_edge("writer", "inspector")

    graph.add_conditional_edges("inspector", should_continue, {
        "end": END,
        "collector": "collector",
        "analyzer": "analyzer",
        "writer": "writer",
    })

    return graph.compile(), node_trace
