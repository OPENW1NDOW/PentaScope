import logging
from langgraph.graph import StateGraph, END
from src.graph.state import AnalysisState
from src.agents.collector import CollectorAgent
from src.agents.analyzer import AnalyzerAgent
from src.agents.writer import WriterAgent
from src.agents.inspector import InspectorAgent

logger = logging.getLogger(__name__)


def build_graph(llm, http, parser) -> StateGraph:
    """构建 LangGraph 状态图"""
    collector = CollectorAgent(llm=llm, http=http, parser=parser)
    analyzer = AnalyzerAgent(llm=llm)
    writer = WriterAgent(llm=llm)
    inspector = InspectorAgent(llm=llm)

    async def collector_node(state: AnalysisState) -> dict:
        logger.info("[graph] → collector")
        profiles = await collector.collect(state["user_input"])
        return {"profiles": profiles, "current_node": "collector"}

    async def analyzer_node(state: AnalysisState) -> dict:
        logger.info("[graph] → analyzer")
        analysis = await analyzer.analyze(state["profiles"])
        return {"analysis": analysis, "current_node": "analyzer"}

    async def writer_node(state: AnalysisState) -> dict:
        logger.info("[graph] → writer")
        competitors = [c.name for c in state["user_input"].competitors]
        report = await writer.write(state["analysis"], competitors)
        return {"report": report, "current_node": "writer"}

    async def inspector_node(state: AnalysisState) -> dict:
        logger.info("[graph] → inspector")
        feedback = await inspector.inspect(
            state["report"],
            retry_count=state.get("retry_count", 0),
            max_retries=state.get("max_retries", 2),
        )
        return {
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
            return "end"

        # 根据 issues 中的 agent 字段决定回到哪个节点
        target_agents = {issue.agent for issue in feedback.issues}
        if "collector" in target_agents:
            return "collector"
        return "writer"

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
        "writer": "writer",
    })

    return graph.compile()
