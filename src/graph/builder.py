"""LangGraph 编排（v3）：5 场景路由 + WriterOrchestrator + writer 异常路由 + S4 prior 读盘。

变化点（相对 v2）：
- 入口改为 set_conditional_entry_point：S2 → recommender → collector，其他场景直接 collector
- writer_node 接通 WriterOrchestrator + 外层 try/except 转 RejectionFeedback（[v3-R02]）
- S4 在 writer_node 前读 prior_report_data（[v3-R09]）
- 删除旧的 data_sources list[str] 覆盖代码（[v3-R16]）
- 删除旧的 quality_score 倒推回填（F 阶段重写 inspector）
- inspector_node 加 report=None 兜底（writer 抛错时 skip 质检）
"""
import json
import logging
from pathlib import Path

from langgraph.graph import StateGraph, END

from src.agents.analyzer import AnalyzerAgent
from src.agents.collection_pipeline import CollectionPipeline
from src.agents.collector import CollectorAgent
from src.agents.inspector import InspectorAgent
from src.agents.recommender import RecommenderAgent
from src.agents.writer_orchestrator import WriterOrchestrator
from src.graph.state import AnalysisState
from src.schemas.feedback import FeedbackIssue, RejectionFeedback
from src.schemas.input import CompetitorBasic
from src.tools.sources import TavilySource
from src.utils.config import settings
from src.utils.paths import runs_dir

logger = logging.getLogger(__name__)


# 暴露为模块级常量供测试 monkeypatch 用（runs_dir() 在导入时求值一次）
RUNS_DIR: Path = runs_dir()


def _load_prior_report_data(prior_trace_id: str) -> dict | None:
    """[v3-R02 / v3-R09] 读上轮 BaseReport JSON。

    校验 metadata.scenario == 'S4' + schema_version == '2.0'，否则返回 None（降级首次模式）。
    文件不存在 / JSON 解析失败 / 字段不匹配 都安全返回 None（log warning）。
    """
    if not prior_trace_id:
        return None
    prior_path = Path(RUNS_DIR) / prior_trace_id / "03_report.json"
    if not prior_path.exists():
        logger.warning("[graph] prior_trace_id=%s 报告不存在，降级为首次监控", prior_trace_id)
        return None
    try:
        with open(prior_path, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("[graph] prior_trace_id 读取失败 %s，降级为首次监控", e)
        return None
    meta = data.get("metadata", {}) if isinstance(data, dict) else {}
    if meta.get("scenario") != "S4":
        logger.warning("[graph] prior 报告 scenario != S4，降级为首次监控")
        return None
    if meta.get("schema_version") != "2.0":
        logger.warning("[graph] prior 报告 schema_version != 2.0，降级为首次监控")
        return None
    return data


def _route_entry(state: AnalysisState) -> str:
    """[v3] 入口路由：S2 走 recommender → collector；其他场景直接 collector。

    模块级独立函数（非闭包），便于单测直接 import + 调用。
    """
    ui = state["user_input"]
    return "recommender" if ui.scenario == "S2" else "collector"


def build_graph(llm, http, parser, trace_writer=None):
    """构建 LangGraph 状态图，返回 (compiled_graph, node_trace)。

    v3 改造：
    - set_conditional_entry_point 按 scenario 路由：S2 走 recommender → collector，其他场景直接 collector
    - writer_node 接通 WriterOrchestrator + 外层 try/except 转 RejectionFeedback（[v3-R02]）
    - S4 在 writer_node 前置读 prior_report_data（[v3-R09]）
    - 删除旧 data_sources 覆盖代码（[v3-R16]）
    - 删除旧 quality_score 倒推回填（F 阶段重写 inspector）
    - inspector_node 加 report=None 兜底
    """
    _ = parser  # 旧签名保留，pipeline 自带解析逻辑，parser 不再透传

    search_source = TavilySource(http=http, api_key=settings.TAVILY_API_KEY)
    pipeline = CollectionPipeline(search_source=search_source)
    collector = CollectorAgent(llm=llm, pipeline=pipeline)
    analyzer = AnalyzerAgent(llm=llm)
    writer = WriterOrchestrator(llm=llm)  # v3: WriterOrchestrator 替代 WriterAgent
    inspector = InspectorAgent(llm=llm)
    recommender = RecommenderAgent(llm=llm, search_source=search_source)  # v3: S2 专用

    # 记录节点执行与路由决策序列（可观测性追溯）
    node_trace: list = []

    def _save(stage: str, data):
        # 落盘是辅助能力，trace_writer 为 None 时跳过
        if trace_writer is not None:
            trace_writer.save_stage(stage, data)

    # ========== recommender_node（S2 专用）==========

    async def recommender_node(state: AnalysisState) -> dict:
        """[v3] S2 专用：根据 industry + 用户 context 产出 CompetitorRecommendations。

        把推荐 + 用户填的合并到 user_input.competitors，让 collector 能直接用。
        """
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
        """[v3-R02] writer_node 接通 WriterOrchestrator + 异常路由。

        - [v3-R09] S4 场景前置读 prior_report_data
        - RuntimeError 含 "回 collector" / "回 writer" → 按 hint 转 feedback agent
        - 其他异常（含 ValidationError）→ feedback agent=writer
        """
        logger.info("[graph] → writer")
        node_trace.append("writer")
        ui = state["user_input"]

        # [v3-R09] S4 场景前置读 prior_report_data
        prior_data = None
        if ui.scenario == "S4" and ui.prior_trace_id:
            prior_data = _load_prior_report_data(ui.prior_trace_id)

        try:
            report = await writer.write(
                scenario_input=ui,
                analysis=state["analysis"],
                profiles=state["profiles"],
                analysis_goal=state.get("analysis_goal"),
                competitor_recommendations=state.get("competitor_recommendations"),
                prior_report_data=prior_data,
                trace_id=state.get("trace_id", ""),
            )
            _save("03_report", report)
            return {"report": report, "current_node": "writer"}
        except RuntimeError as e:
            msg = str(e)
            if "回 collector" in msg:
                agent = "collector"
            elif "回 writer" in msg:
                agent = "writer"
            else:
                agent = "writer"
            feedback = RejectionFeedback(
                passed=False,
                issues=[FeedbackIssue(
                    severity="critical",
                    agent=agent,
                    field="writer_runtime",
                    reason=msg[:200],
                    suggestion="见 message",
                )],
                retry_count=state.get("retry_count", 0),
                max_retries=state.get("max_retries", 2),
            )
            logger.warning("[graph] writer raised RuntimeError → 转 feedback agent=%s", agent)
            return {
                "feedback": feedback,
                "current_node": "writer",
                "retry_count": state.get("retry_count", 0) + 1,
            }
        except Exception as e:
            # Pydantic ValidationError 等其他异常 → feedback agent=writer
            logger.warning("[graph] writer raised non-runtime error: %s", type(e).__name__)
            feedback = RejectionFeedback(
                passed=False,
                issues=[FeedbackIssue(
                    severity="critical",
                    agent="writer",
                    field="writer_validation",
                    reason=str(e)[:200],
                    suggestion="LLM 输出不符合 schema，建议 graph 重试 writer",
                )],
                retry_count=state.get("retry_count", 0),
                max_retries=state.get("max_retries", 2),
            )
            return {
                "feedback": feedback,
                "current_node": "writer",
                "retry_count": state.get("retry_count", 0) + 1,
            }

    async def inspector_node(state: AnalysisState) -> dict:
        """质检节点。[v3] report 为 None 时（writer 抛错走 feedback）skip 质检。"""
        logger.info("[graph] → inspector")
        node_trace.append("inspector")
        report = state.get("report")
        if report is None:
            logger.info("[graph] inspector skip：report 为 None（writer 已转 feedback）")
            return {"current_node": "inspector"}

        ui = state["user_input"]
        competitors_names = [c.name for c in ui.competitors]
        feedback = await inspector.inspect(
            report,
            competitors=competitors_names,
            retry_count=state.get("retry_count", 0),
            max_retries=state.get("max_retries", 2),
        )
        _save("04_feedback", feedback)
        return {"feedback": feedback, "current_node": "inspector"}

    def should_continue(state: AnalysisState) -> str:
        """v3 should_continue：按 feedback.issues[*].agent 路由回 collector/analyzer/writer，
        或 retry_count >= max_retries 强制结束。"""
        feedback = state.get("feedback")
        retry_count = state.get("retry_count", 0)
        max_retries = state.get("max_retries", 2)

        # 没 feedback 或已通过 → 结束
        if feedback is None or feedback.passed:
            return "end"

        if retry_count >= max_retries:
            logger.warning("[graph] 达到 max_retries=%d，强制结束", max_retries)
            node_trace.append(f"reject->end(retry={retry_count})")
            return "end"

        # 取第一条 critical/major issue 的 agent 决定回边
        for issue in feedback.issues:
            if issue.severity in ("critical", "major"):
                target = issue.agent
                node_trace.append(f"reject->{target} ({issue.field})")
                return target
        return "end"

    # ========== 构图 ==========

    graph = StateGraph(AnalysisState)
    graph.add_node("recommender", recommender_node)
    graph.add_node("collector", collector_node)
    graph.add_node("analyzer", analyzer_node)
    graph.add_node("writer", writer_node)
    graph.add_node("inspector", inspector_node)

    # [v3] scenario 路由：S2 走 recommender → collector；其他场景直接 collector
    graph.set_conditional_entry_point(_route_entry, {
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
