import logging
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter
from src.api.schemas import AnalysisRequest, AnalysisResponse
from src.schemas.input import CompetitorInput
from src.tools.llm_client import LLMClient
from src.tools.http_client import HttpClient
from src.tools.html_parser import HtmlParser
from src.tools.trace_writer import TraceWriter
from src.graph.builder import build_graph
from src.utils.paths import runs_dir

logger = logging.getLogger(__name__)
router = APIRouter()
_BEIJING = timezone(timedelta(hours=8))


@router.post("/analyze", response_model=AnalysisResponse)
async def analyze(request: AnalysisRequest):
    """执行竞品分析"""
    trace_id = TraceWriter.new_trace_id(base_dir=runs_dir())
    tw = TraceWriter(trace_id, base_dir=runs_dir())
    logger.info("[api] 收到分析请求, trace_id=%s, competitors=%s",
                trace_id, [c.name for c in request.competitors])

    started = datetime.now(_BEIJING).isoformat()
    tw.save_meta({
        "trace_id": trace_id,
        "status": "running",
        "started_at": started,
        "input": {
            "competitors": [c.model_dump() for c in request.competitors],
            "analysis_context": request.analysis_context,
        },
    })

    http = HttpClient()
    node_trace: list = []
    try:
        user_input = CompetitorInput(
            competitors=request.competitors,
            analysis_context=request.analysis_context,
        )
        llm = LLMClient()
        parser = HtmlParser()
        graph, node_trace = build_graph(llm=llm, http=http, parser=parser, trace_writer=tw)
        result = await graph.ainvoke({
            "user_input": user_input, "retry_count": 0, "max_retries": 2, "trace_id": trace_id,
        })
        report = result.get("report")
        tw.save_meta({
            "trace_id": trace_id, "status": "completed",
            "started_at": started, "ended_at": datetime.now(_BEIJING).isoformat(),
            "retry_count": result.get("retry_count", 0),
            "node_trace": node_trace,
            "input": {
                "competitors": [c.name for c in request.competitors],
                "analysis_context": request.analysis_context,
            },
        })
        return AnalysisResponse(
            trace_id=trace_id, status="completed",
            report=report.model_dump() if report else None,
        )
    except Exception as e:
        logger.error("[api] 分析失败: %s", e, exc_info=True)
        tw.save_meta({
            "trace_id": trace_id, "status": "failed",
            "started_at": started, "ended_at": datetime.now(_BEIJING).isoformat(),
            "node_trace": node_trace, "error": str(e),
        })
        return AnalysisResponse(trace_id=trace_id, status="failed", error=str(e))
    finally:
        await http.close()
