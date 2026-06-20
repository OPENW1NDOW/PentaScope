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
import re
from pathlib import Path

from langgraph.graph import StateGraph, END

from src.agents.analyzer import AnalyzerAgent
from src.agents.collection_pipeline import CollectionPipeline
from src.agents.collector import CollectorAgent
from src.agents.inspector import InspectorAgent
from src.agents.recommender import RecommenderAgent
from src.agents.writer_orchestrator import (
    WriterOrchestrator,
    WriterRouteToCollector,
    WriterRouteToEnd,
    WriterRouteToWriter,
)
from src.graph.state import AnalysisState
from src.schemas.feedback import FeedbackIssue, RejectionFeedback
from src.schemas.input import CompetitorBasic
from src.tools.sources import TavilySource
from src.utils.config import settings
from src.utils.paths import runs_dir

logger = logging.getLogger(__name__)


# 暴露为模块级常量供测试 monkeypatch 用（runs_dir() 在导入时求值一次）
RUNS_DIR: Path = runs_dir()


_TRACE_ID_PATTERN = re.compile(r"^[a-f0-9\-]+$")


def _serialize_writer_exception(e: Exception) -> dict:
    """把 writer 阶段的异常（含 ValidationError）序列化为可落盘的 dict。

    ValidationError 提取完整 errors() 列表 + 简短摘要；
    其他异常仅记录类型和 str()。
    """
    err_dict: dict = {
        "error_type": type(e).__name__,
        "error_message": str(e)[:1000],
    }
    errors_method = getattr(e, "errors", None)
    if callable(errors_method):
        try:
            errs = list(errors_method())
        except Exception:  # noqa: BLE001
            errs = None
        if errs is not None:
            # 去掉非 JSON 可序列化字段（如 ctx）
            safe_errs = []
            for err in errs:
                safe_errs.append({
                    "loc": list(err.get("loc", [])),
                    "msg": err.get("msg", ""),
                    "type": err.get("type", ""),
                })
            err_dict["errors"] = safe_errs
            # log 用的简短摘要：前 5 条 loc+msg
            err_dict["errors_summary"] = "; ".join(
                f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}"
                for err in safe_errs[:5]
            )
    return err_dict


def _load_prior_report_data(prior_trace_id: str) -> dict | None:
    """[v3-R02 / v3-R09] 读上轮 BaseReport JSON。

    校验 metadata.scenario == 'S4' + schema_version == '2.0'，否则返回 None（降级首次模式）。
    文件不存在 / JSON 解析失败 / 字段不匹配 都安全返回 None（log warning）。

    [D3 review C-new] prior_trace_id 来自前端用户输入，必须白名单校验后再拼路径，
    否则 ../../etc/passwd 一类输入可越过 RUNS_DIR 读任意文件。
    """
    if not prior_trace_id:
        return None
    # 安全闸：仅允许 UUID 类字符（含连字符），长度 ≤ 64
    if not _TRACE_ID_PATTERN.match(prior_trace_id) or len(prior_trace_id) > 64:
        logger.warning(
            "[graph] prior_trace_id 含非法字符，拒绝加载: %r", prior_trace_id
        )
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


from src.utils.url_normalize import normalize_url as _normalize_url
from src.agents.writer_orchestrator import _collect_source_refs_recursive

_EVIDENCE_ISSUE_TYPES = frozenset({"url_not_discovered", "source_mismatch", "source_irrelevant"})


def _extract_used_urls(report) -> set[str]:
    """从报告递归收集所有 source_refs 里的 url。"""
    if report is None:
        return set()
    dump = report.model_dump()
    refs, bare = _collect_source_refs_recursive(dump)
    urls = {r["url"] for r in refs if r.get("url")}
    urls |= bare
    return urls


def _route_evidence_issue(state: dict) -> str | None:
    """evidence 类 issue 的智能路由。返回 None 表示走原有映射。"""
    discovered = state.get("discovered_sources", [])
    if not discovered:
        return None

    discovered_urls = {_normalize_url(d["url"]) for d in discovered
                       if isinstance(d, dict) and d.get("url")}
    if not discovered_urls:
        return None

    report = state.get("report")
    if report is None:
        return None

    used_urls = {_normalize_url(u) for u in _extract_used_urls(report)}
    coverage = len(used_urls & discovered_urls) / len(discovered_urls)

    prev_coverage = state.get("_prev_evidence_coverage")
    if prev_coverage is not None and coverage >= prev_coverage - 0.05:
        return "end"

    if len(discovered_urls) >= 8 and coverage < 0.5:
        return "writer"
    elif len(discovered_urls) < 5:
        return "collector"
    else:
        return "writer"


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

    # 分层模型：fast（collector/recommender）+ pro（analyzer/writer/inspector）
    # 外部传入的 llm 作为 fallback（测试 mock 时只传一个 llm 即覆盖全部）
    from src.tools.llm_client import LLMClient
    if isinstance(llm, LLMClient) and settings.MODEL_FAST != settings.MODEL_PRO:
        llm_fast = LLMClient(model_ep=settings.MODEL_FAST)
        llm_pro = LLMClient(model_ep=settings.MODEL_PRO)
    else:
        llm_fast = llm
        llm_pro = llm

    search_source = TavilySource(http=http, api_key=settings.TAVILY_API_KEY)
    pipeline = CollectionPipeline(search_source=search_source)
    collector = CollectorAgent(llm=llm_fast, pipeline=pipeline)
    analyzer = AnalyzerAgent(llm=llm_pro)
    writer = WriterOrchestrator(llm=llm_pro)
    inspector = InspectorAgent(llm=llm_pro)
    recommender = RecommenderAgent(llm=llm_fast, search_source=search_source)

    # 记录节点执行与路由决策序列（可观测性追溯）
    node_trace: list = []

    def _save(stage: str, data):
        # 落盘是辅助能力，trace_writer 为 None 时跳过
        if trace_writer is not None:
            trace_writer.save_stage(stage, data)

    # ========== recommender_node（S2 专用）==========

    async def recommender_node(state: AnalysisState) -> dict:
        """[v3] S2 专用：根据 industry + 用户 context 产出 CompetitorRecommendations。

        [D3 review C2] 不再合并到 user_input.competitors。phase 4 union 是唯一合并点，
        collector_node 自行读两处构造采集列表。
        """
        logger.info("[graph] → recommender")
        node_trace.append("recommender")
        ui = state["user_input"]
        rec = await recommender.recommend(
            industry=ui.industry or "",
            context=ui.analysis_context,
            user_provided_competitors=[c.name for c in ui.competitors],
        )
        return {
            "competitor_recommendations": rec,
            "current_node": "recommender",
        }

    async def collector_node(state: AnalysisState) -> dict:
        """[D3 review C2] 静态采集名单 = user_input.competitors ∪ recommendations（按 name 去重）。

        recommender_node 不再合并到 ui.competitors，所以这里要主动 union；
        非 S2 场景 competitor_recommendations 为 None，退化为只读 ui.competitors。
        """
        logger.info("[graph] → collector")
        node_trace.append("collector")
        ui = state["user_input"]
        rec = state.get("competitor_recommendations")
        if rec is not None and rec.recommended_competitors:
            existing_names = {c.name for c in ui.competitors}
            merged = list(ui.competitors) + [
                CompetitorBasic(name=r.name, company=r.company)
                for r in rec.recommended_competitors
                if r.name and r.name not in existing_names
            ]
            collect_input = ui.model_copy(update={"competitors": merged})
        else:
            collect_input = ui
        profiles, goal, discovered_sources = await collector.collect(collect_input)
        _save("01_profiles", profiles)
        return {
            "profiles": profiles,
            "analysis_goal": goal,
            "discovered_sources": discovered_sources,
            "current_node": "collector",
        }

    async def analyzer_node(state: AnalysisState) -> dict:
        """[06-09 修复] analyzer 抛 ValueError 时兜底注入 feedback，不让 graph 崩溃。

        analyzer.analyze 内部 LLM 重试 1 次后仍 ValidationError 会 raise ValueError——
        修前没 try/except 直接冒到 LangGraph 崩溃。修后注入 feedback 让 should_continue 路由。
        """
        logger.info("[graph] → analyzer")
        node_trace.append("analyzer")
        feedback = state.get("feedback")
        issues = feedback.issues if feedback is not None else None
        try:
            analysis = await analyzer.analyze(
                state["profiles"],
                scenario_input=state["user_input"],  # [fix7] 注入场景上下文
                feedback_issues=issues,
            )
        except Exception as e:
            logger.warning("[graph] analyzer 抛 %s: %s", type(e).__name__, str(e)[:200])
            failed_feedback = RejectionFeedback(
                passed=False,
                issues=[FeedbackIssue(
                    severity="critical",
                    agent="analyzer",
                    field="analyzer_validation",
                    reason=str(e)[:200],
                    suggestion="LLM 输出不符合 CompetitiveAnalysis schema，graph 重试",
                )],
                retry_count=state.get("retry_count", 0),
                max_retries=state.get("max_retries", 2),
            )
            return {
                "feedback": failed_feedback,
                "current_node": "analyzer",
                "retry_count": state.get("retry_count", 0) + 1,
            }
        _save("02_analysis", analysis)
        return {"analysis": analysis, "current_node": "analyzer"}

    async def writer_node(state: AnalysisState) -> dict:
        """[v3-R02] writer_node 接通 WriterOrchestrator + 异常路由。

        - [v3-R09] S4 场景前置读 prior_report_data
        - [D3 review C1] 用 WriterRouteToCollector/Writer/End 三类异常 isinstance 判路由，
          不再依赖 RuntimeError 的中文措辞子串匹配
        - 其他 RuntimeError / Exception（含 ValidationError）→ feedback agent=writer
        """
        logger.info("[graph] → writer")
        node_trace.append("writer")
        ui = state["user_input"]

        # [fix12] analyzer 失败兜底：state 没 analysis 但 feedback 标记 analyzer 失败时，
        # writer 直接 skip 透传 feedback，让 should_continue 按 issue.agent='analyzer' 回 analyzer。
        # 不 skip 的话 writer 拿 state['analysis'] 立刻 KeyError，污染反馈闭环路由到 writer 重试。
        existing_feedback = state.get("feedback")
        if state.get("analysis") is None and existing_feedback is not None and not existing_feedback.passed:
            logger.info("[graph] writer skip：analyzer 失败兜底，透传 feedback agent=%s",
                        existing_feedback.issues[0].agent if existing_feedback.issues else "?")
            return {"feedback": existing_feedback, "current_node": "writer"}

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
        except WriterRouteToEnd as e:
            # 不可恢复（LLM quota / scope 全空 / scope 无法构造）→ passed=True 强制结束
            logger.warning("[graph] writer 不可恢复错误，强制终止图: %s", e)
            feedback = RejectionFeedback(
                passed=True,
                issues=[FeedbackIssue(
                    severity="critical",
                    agent="writer",
                    field="writer_unrecoverable",
                    reason=str(e)[:200],
                    suggestion="不可恢复错误，图直接终止",
                )],
                retry_count=state.get("retry_count", 0),
                max_retries=state.get("max_retries", 2),
            )
            return {
                "feedback": feedback,
                "current_node": "writer",
            }
        except WriterRouteToCollector as e:
            logger.warning("[graph] writer raised WriterRouteToCollector → 回 collector")
            feedback = RejectionFeedback(
                passed=False,
                issues=[FeedbackIssue(
                    severity="critical",
                    agent="collector",
                    field="writer_runtime",
                    reason=str(e)[:200],
                    suggestion="重新采集补齐 URL / 内容",
                )],
                retry_count=state.get("retry_count", 0),
                max_retries=state.get("max_retries", 2),
            )
            return {
                "feedback": feedback,
                "current_node": "writer",
                "retry_count": state.get("retry_count", 0) + 1,
            }
        except WriterRouteToWriter as e:
            logger.warning("[graph] writer raised WriterRouteToWriter → 回 writer")
            feedback = RejectionFeedback(
                passed=False,
                issues=[FeedbackIssue(
                    severity="critical",
                    agent="writer",
                    field="writer_runtime",
                    reason=str(e)[:200],
                    suggestion="writer 重试",
                )],
                retry_count=state.get("retry_count", 0),
                max_retries=state.get("max_retries", 2),
            )
            return {
                "feedback": feedback,
                "current_node": "writer",
                "retry_count": state.get("retry_count", 0) + 1,
            }
        except RuntimeError as e:
            # last resort：未来如果有遗漏的 RuntimeError 子类，兜底回 writer 重试一次
            logger.warning(
                "[graph] writer raised 未分类 RuntimeError，兜底回 writer: %s", e
            )
            feedback = RejectionFeedback(
                passed=False,
                issues=[FeedbackIssue(
                    severity="critical",
                    agent="writer",
                    field="writer_runtime",
                    reason=str(e)[:200],
                    suggestion="未分类 RuntimeError，兜底走 writer 重试",
                )],
                retry_count=state.get("retry_count", 0),
                max_retries=state.get("max_retries", 2),
            )
            return {
                "feedback": feedback,
                "current_node": "writer",
                "retry_count": state.get("retry_count", 0) + 1,
            }
        except Exception as e:
            # Pydantic ValidationError 等其他异常 → feedback agent=writer
            # 记录完整错误详情到 log + trace 文件，便于诊断 schema 校验失败的具体字段
            err_dict = _serialize_writer_exception(e)
            logger.warning(
                "[graph] writer raised non-runtime error: %s, errors=%s",
                err_dict["error_type"], err_dict.get("errors_summary", ""),
            )
            if trace_writer is not None:
                trace_writer.save_raw("04_writer_error", err_dict)
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
        """质检节点。[v3] report 为 None 时（writer 抛错走 feedback）skip 质检。

        [06-09 修复] inspector 打回（passed=False）时 retry_count +1，
        否则 inspector 反复打回 analyzer/writer 永远不会触发 max_retries 强制结束。
        """
        logger.info("[graph] → inspector")
        node_trace.append("inspector")
        report = state.get("report")
        if report is None:
            logger.info("[graph] inspector skip：report 为 None（writer 已转 feedback）")
            return {"current_node": "inspector"}

        ui = state["user_input"]
        competitors_names = [c.name for c in ui.competitors]
        discovered_sources = state.get("discovered_sources") or []
        feedback = await inspector.inspect(
            report,
            competitors=competitors_names,
            retry_count=state.get("retry_count", 0),
            max_retries=state.get("max_retries", 2),
            discovered_sources=discovered_sources,
        )
        _save("04_feedback", feedback)
        # inspector 回填 quality_score 后重新落盘 report（writer 先于 inspector 落盘，初始 score=None）
        _save("03_report", report)
        # 打回时 +1 retry_count；passed=True 不增（直接 end）
        next_retry = state.get("retry_count", 0)
        if not feedback.passed:
            next_retry += 1
        return {
            "feedback": feedback,
            "current_node": "inspector",
            "retry_count": next_retry,
        }

    def should_continue(state: AnalysisState) -> str:
        """v3 should_continue：按 feedback.issues[*].agent 路由回 collector/analyzer/writer，
        或 retry_count >= max_retries 强制结束。"""
        feedback = state.get("feedback")
        retry_count = state.get("retry_count", 0)
        max_retries = state.get("max_retries", 2)

        # 没 feedback 或已通过 → 结束
        if feedback is None or feedback.passed:
            return "end"

        # spec v4 cycle3/C5：critic_failed → terminal（不消耗 max_retries）
        if any(i.agent == "end" for i in feedback.issues):
            logger.warning("[graph] critic 系统故障 → terminate（不消耗 retry）")
            node_trace.append("reject->end (critic_failed)")
            return "end"

        if retry_count >= max_retries:
            logger.warning("[graph] 达到 max_retries=%d，强制结束", max_retries)
            node_trace.append(f"reject->end(retry={retry_count})")
            return "end"

        # evidence issues 优先扫描
        for issue in feedback.issues:
            if issue.severity in ("critical", "major") and getattr(issue, "issue_type", None) in _EVIDENCE_ISSUE_TYPES:
                evidence_route = _route_evidence_issue(state)
                if evidence_route is not None:
                    node_trace.append(f"reject->{evidence_route} (evidence_route)")
                    return evidence_route
                break

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
