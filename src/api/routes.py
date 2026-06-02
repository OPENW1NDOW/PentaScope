import uuid
import logging
from fastapi import APIRouter
from src.api.schemas import AnalysisRequest, AnalysisResponse
from src.schemas.input import CompetitorInput
from src.tools.llm_client import LLMClient
from src.tools.http_client import HttpClient
from src.tools.html_parser import HtmlParser
from src.graph.builder import build_graph

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/analyze", response_model=AnalysisResponse)
async def analyze(request: AnalysisRequest):
    """执行竞品分析"""
    trace_id = str(uuid.uuid4())[:8]
    logger.info("[api] 收到分析请求, trace_id=%s, competitors=%s", trace_id, [c.name for c in request.competitors])

    http = HttpClient()
    try:
        user_input = CompetitorInput(
            competitors=request.competitors,
            analysis_context=request.analysis_context,
        )

        llm = LLMClient()
        parser = HtmlParser()

        graph, _ = build_graph(llm=llm, http=http, parser=parser)

        result = await graph.ainvoke({
            "user_input": user_input,
            "retry_count": 0,
            "max_retries": 2,
            "trace_id": trace_id,
        })

        report = result.get("report")
        return AnalysisResponse(
            trace_id=trace_id,
            status="completed",
            report=report.model_dump() if report else None,
        )
    except Exception as e:
        logger.error("[api] 分析失败: %s", e, exc_info=True)
        return AnalysisResponse(trace_id=trace_id, status="failed", error=str(e))
    finally:
        await http.close()
