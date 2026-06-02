import logging
import re
import json
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException
from src.api.schemas import AnalysisRequest, AnalysisResponse, TraceResponse
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

    # 为本次分析挂一个 run.log 文件 handler（按 trace_id 留存单次运行日志）
    # 与其它落盘一致：失败仅 warning，绝不阻塞主分析流程
    run_handler = None
    try:
        trace_dir = runs_dir() / trace_id
        trace_dir.mkdir(parents=True, exist_ok=True)
        run_handler = logging.FileHandler(str(trace_dir / "run.log"), encoding="utf-8")
        run_handler.setFormatter(logging.Formatter(
            "[%(asctime)s] %(levelname)s %(name)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
        logging.getLogger().addHandler(run_handler)
    except Exception as e:  # noqa: BLE001
        logger.warning("[api] run.log handler 创建失败 trace=%s: %s", trace_id, e)

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
                "competitors": [c.model_dump() for c in request.competitors],
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
        if run_handler is not None:
            logging.getLogger().removeHandler(run_handler)
            run_handler.close()
        await http.close()


_TRACE_RE = re.compile(r"\d{8}-\d{6}-[0-9a-f]{6}")

_STAGE_FILES = {
    "profiles": "01_profiles.json",
    "analysis": "02_analysis.json",
    "report": "03_report.json",
    "feedback": "04_feedback.json",
}


def _load_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


@router.get("/trace/{trace_id}", response_model=TraceResponse)
async def get_trace(trace_id: str, version: str | None = None):
    if not _TRACE_RE.fullmatch(trace_id):
        raise HTTPException(status_code=404, detail="trace not found")
    base = runs_dir()
    trace_dir = (base / trace_id).resolve()
    # 双重防护：解析后必须仍在 runs/ 下
    if base.resolve() not in trace_dir.parents and trace_dir != base.resolve():
        raise HTTPException(status_code=404, detail="trace not found")
    if not trace_dir.is_dir():
        raise HTTPException(status_code=404, detail="trace not found")

    # 按需取指定历史版本内容
    if version is not None:
        if not re.fullmatch(r"0[1-4]_[a-z]+_v\d+", version):
            raise HTTPException(status_code=404, detail="version not found")
        vf = trace_dir / f"{version}.json"
        if not vf.is_file():
            raise HTTPException(status_code=404, detail="version not found")
        return TraceResponse(trace_id=trace_id, stages={version: _load_json(vf)})

    stages = {key: _load_json(trace_dir / fn) for key, fn in _STAGE_FILES.items()}
    snapshots = sorted(p.stem for p in trace_dir.glob("0[1-4]_*_v*.json"))
    log_path = trace_dir / "run.log"
    log_text = log_path.read_text(encoding="utf-8") if log_path.is_file() else ""

    return TraceResponse(
        trace_id=trace_id,
        meta=_load_json(trace_dir / "meta.json"),
        stages=stages,
        snapshots=snapshots,
        log=log_text,
    )
