import logging
from langgraph.graph import StateGraph, END
from src.graph.state import AnalysisState
from src.agents.collector import CollectorAgent
from src.agents.analyzer import AnalyzerAgent
from src.agents.recommender import RecommenderAgent
from src.agents.inspector import InspectorAgent
from src.agents.collection_pipeline import CollectionPipeline
from src.tools.sources import TavilySource
from src.schemas.input import CompetitorBasic
from src.utils.config import settings

logger = logging.getLogger(__name__)


def build_graph(llm, http, parser, trace_writer=None):
    """构建 LangGraph 状态图，返回 (compiled_graph, node_trace)

    流水线：(S2 → recommender →) collector → analyzer → writer → inspector → END
                                          ↑__feedback 闭环回 collector/analyzer/writer__|

    备注（D 阶段过渡）：writer_node 当前为占位（NotImplementedError 短路 pass），
    BaseReport 真实产出由 E 大类（worktree-scenario-writer-frontend）的 WriterOrchestrator 实现后接入。
    """
    search_source = TavilySource(http=http, api_key=settings.TAVILY_API_KEY)
    pipeline = CollectionPipeline(search_source=search_source)
    collector = CollectorAgent(llm=llm, pipeline=pipeline)
    analyzer = AnalyzerAgent(llm=llm)
    recommender = RecommenderAgent(llm=llm, search_source=search_source)
    inspector = InspectorAgent(llm=llm)

    node_trace: list = []

    def _save(stage: str, data):
        if trace_writer is not None:
            trace_writer.save_stage(stage, data)

    async def recommender_node(state: AnalysisState) -> dict:
        """S2 专用：根据 industry 推荐 Top 玩家，合并到 user_input.competitors"""
        logger.info("[graph] → recommender")
        node_trace.append("recommender")
        ui = state["user_input"]
        rec = await recommender.recommend(
            industry=ui.industry or "",
            context=ui.analysis_context,
            user_provided_competitors=[c.name for c in ui.competitors],
        )
        existing_names = {c.name for c in ui.competitors}
        merged = list(ui.competitors) + [
            CompetitorBasic(name=r.name, company=r.company)
            for r in rec.recommended_competitors
            if r.name not in existing_names
        ]
        new_input = ui.model_copy(update={"competitors": merged})
        return {
            "user_input": new_input,
            "competitor_recommendations": rec,
            "current_node": "recommender",
        }

    async def collector_node(state: AnalysisState) -> dict:
        logger.info("[graph] → collector")
        node_trace.append("collector")
        profiles, goal = await collector.collect(state["user_input"])
        _save("01_profiles", profiles)
        return {"profiles": profiles, "analysis_goal": goal, "current_node": "collector"}

    async def analyzer_node(state: AnalysisState) -> dict:
        logger.info("[graph] → analyzer")
        node_trace.append("analyzer")
        feedback = state.get("feedback")
        issues = feedback.issues if feedback is not None else None
        analysis = await analyzer.analyze(state["profiles"], feedback_issues=issues)
        _save("02_analysis", analysis)
        return {"analysis": analysis, "current_node": "analyzer"}

    async def writer_node(state: AnalysisState) -> dict:
        # D 阶段过渡：BaseReport 产出由 E 大类 WriterOrchestrator 实现，本节点暂为 no-op
        logger.info("[graph] → writer (D-phase no-op)")
        node_trace.append("writer")
        return {"current_node": "writer"}

    async def inspector_node(state: AnalysisState) -> dict:
        logger.info("[graph] → inspector")
        node_trace.append("inspector")
        report = state.get("report")
        if report is None:
            # writer 还没接通时跳过质检，避免崩
            logger.warning("[inspector] state.report 为 None（writer 未接通），跳过质检")
            return {"current_node": "inspector"}
        competitors = [c.name for c in state["user_input"].competitors]
        feedback = await inspector.inspect(
            report,
            competitors=competitors,
            retry_count=state.get("retry_count", 0),
            max_retries=state.get("max_retries", 2),
        )
        # quality_score 由 inspector 内部按 spec Part 4.5 三项加权公式回填到 report.metadata
        _save("04_feedback", feedback)
        return {
            "report": report,
            "feedback": feedback,
            "retry_count": state.get("retry_count", 0) + (0 if feedback.passed else 1),
            "current_node": "inspector",
        }

    def should_continue(state: AnalysisState) -> str:
        """质检通过→结束；不通过且未超限→按 issue.agent 打回 collector/analyzer/writer
        （优先级 collector > analyzer > writer，打回越上游越能顺带解决下游 issue）；超限→强制结束。
        """
        feedback = state.get("feedback")
        if feedback is None or feedback.passed:
            return "end"

        retry_count = state.get("retry_count", 0)
        max_retries = state.get("max_retries", 2)

        if retry_count >= max_retries:
            logger.warning("[graph] 质检打回超限 (%d/%d), 强制结束", retry_count, max_retries)
            node_trace.append(f"reject->end(retry={retry_count})")
            return "end"

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

    def route_entry(state: AnalysisState) -> str:
        """按 scenario 路由入口：S2 走 recommender 先推荐 Top 玩家，其他场景直接采集。"""
        ui = state["user_input"]
        return "recommender" if ui.scenario == "S2" else "collector"

    graph = StateGraph(AnalysisState)

    graph.add_node("recommender", recommender_node)
    graph.add_node("collector", collector_node)
    graph.add_node("analyzer", analyzer_node)
    graph.add_node("writer", writer_node)
    graph.add_node("inspector", inspector_node)

    graph.set_conditional_entry_point(route_entry, {
        "recommender": "recommender",
        "collector": "collector",
    })
    graph.add_edge("recommender", "collector")
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
