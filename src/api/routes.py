import asyncio
import logging
import re
import json
from datetime import datetime, timezone, timedelta
from typing import Literal

from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import StreamingResponse
from pydantic import ValidationError

from src.api.schemas import (
    AnalysisRequest,
    AnalysisResponse,
    PickScenarioRequest,
    PickScenarioResponse,
    TraceResponse,
    TraceSummary,
    TracesResponse,
)
from src.api.exporters.markdown import render_markdown
from src.schemas.report import BaseReport
from src.tools.llm_client import LLMClient
from src.tools.http_client import HttpClient
from src.tools.html_parser import HtmlParser
from src.tools.scenario_picker import ai_pick_scenario
from src.tools.trace_writer import TraceWriter
from src.graph.builder import build_graph
from src.utils.paths import runs_dir

logger = logging.getLogger(__name__)
router = APIRouter()
_BEIJING = timezone(timedelta(hours=8))
_analyze_lock = asyncio.Lock()

# SSE 进度队列注册表：trace_id → ProgressSnapshotQueue
_progress_queues: dict[str, "ProgressSnapshotQueue"] = {}


class ProgressSnapshotQueue(asyncio.Queue):
    """带进度快照的 SSE 队列：晚加入的客户端可回放当前节点状态。"""

    def __init__(self) -> None:
        super().__init__()
        self.current_node: str | None = None
        self.completed_nodes: list[dict] = []

    async def put(self, item: dict) -> None:
        event_type = item.get("event")
        data = item.get("data") or {}
        if event_type == "node_start":
            self.current_node = data.get("node")
        elif event_type == "node_complete":
            self.completed_nodes.append({
                "node": data.get("node"),
                "duration_ms": data.get("duration_ms"),
            })
            self.current_node = None
        elif event_type in ("analysis_complete", "analysis_failed"):
            self.current_node = None
        await super().put(item)

    def snapshot_events(self) -> list[dict]:
        """供 SSE 连接时回放的事件列表（不含终结事件）。"""
        events: list[dict] = []
        for item in self.completed_nodes:
            events.append({
                "event": "node_complete",
                "data": {
                    "node": item.get("node"),
                    "duration_ms": item.get("duration_ms"),
                },
            })
        if self.current_node:
            events.append({
                "event": "node_start",
                "data": {"node": self.current_node},
            })
        return events


@router.post("/analyze", response_model=AnalysisResponse)
async def analyze(request: AnalysisRequest):
    """执行竞品分析"""
    if _analyze_lock.locked():
        raise HTTPException(status_code=429, detail="已有分析任务正在运行，请等待完成后再提交")

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
            "scenario": request.scenario,
            "competitors": [c.model_dump() for c in request.competitors],
            "industry": request.industry,
            "analysis_context": request.analysis_context,
            "our_product_name": request.our_product_name,
            "prior_trace_id": request.prior_trace_id,
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

    # 创建 SSE 进度队列
    progress_queue = ProgressSnapshotQueue()
    _progress_queues[trace_id] = progress_queue

    http = HttpClient()
    node_trace: list = []
    async with _analyze_lock:
        try:
            user_input = request.to_scenario_input()
            llm = LLMClient()
            parser = HtmlParser()
            graph, node_trace = build_graph(
                llm=llm, http=http, parser=parser, trace_writer=tw,
                progress_queue=progress_queue,
            )
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
                    "scenario": request.scenario,
                    "competitors": [c.model_dump() for c in request.competitors],
                    "industry": request.industry,
                    "analysis_context": request.analysis_context,
                    "our_product_name": request.our_product_name,
                    "prior_trace_id": request.prior_trace_id,
                },
            })
            # 推送完成事件
            await progress_queue.put({
                "event": "analysis_complete",
                "data": {"trace_id": trace_id, "status": "completed"},
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
            await progress_queue.put({
                "event": "analysis_failed",
                "data": {"trace_id": trace_id, "error": str(e)[:200]},
            })
            return AnalysisResponse(trace_id=trace_id, status="failed", error=str(e))
        finally:
            if run_handler is not None:
                logging.getLogger().removeHandler(run_handler)
                run_handler.close()
            await http.close()
            # 清理队列注册表
            _progress_queues.pop(trace_id, None)


@router.post("/pick-scenario", response_model=PickScenarioResponse)
async def pick_scenario(request: PickScenarioRequest):
    """AI 帮用户选场景（前端不确定时调用）"""
    llm = LLMClient()
    result = await ai_pick_scenario(request.user_text, llm=llm)
    return PickScenarioResponse(**result)


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


def _resolve_status(meta: dict, trace_dir, now: datetime) -> str | None:
    status = meta.get("status")
    if status == "running" and meta.get("started_at"):
        try:
            started = datetime.fromisoformat(meta["started_at"])
            if started.tzinfo is None:
                started = started.replace(tzinfo=timezone.utc)
            if (now - started).total_seconds() > 7200:
                meta["status"] = "failed"
                meta["ended_at"] = now.isoformat()
                meta["failure_reason"] = "process interrupted: status not updated within 2h"
                (trace_dir / "meta.json").write_text(
                    json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                status = "failed"
        except (ValueError, TypeError):
            pass
    return status


@router.get("/analyze/{trace_id}/stream")
async def stream_analysis_progress(trace_id: str):
    """SSE 实时进度端点"""
    if not _TRACE_RE.fullmatch(trace_id):
        raise HTTPException(status_code=404, detail="trace not found")

    queue = _progress_queues.get(trace_id)
    if queue is None:
        # 分析已完成或不存在，尝试读 meta 返回最终状态
        base = runs_dir()
        meta_path = base / trace_id / "meta.json"
        if meta_path.is_file():
            meta = _load_json(meta_path) or {}
            status = meta.get("status", "unknown")
            async def _final_status():
                yield f"event: analysis_{'complete' if status == 'completed' else 'failed'}\n"
                yield f"data: {json.dumps({'trace_id': trace_id, 'status': status}, ensure_ascii=False)}\n\n"
            return StreamingResponse(_final_status(), media_type="text/event-stream")
        raise HTTPException(status_code=404, detail="trace not found")

    async def event_generator():
        for snap in queue.snapshot_events():
            event_type = snap.get("event", "message")
            data = json.dumps(snap.get("data", {}), ensure_ascii=False)
            yield f"event: {event_type}\n"
            yield f"data: {data}\n\n"
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=30.0)
            except asyncio.TimeoutError:
                # 心跳，防止连接断开
                yield ": heartbeat\n\n"
                continue
            event_type = item.get("event", "message")
            data = json.dumps(item.get("data", {}), ensure_ascii=False)
            yield f"event: {event_type}\n"
            yield f"data: {data}\n\n"
            # 终结事件
            if event_type in ("analysis_complete", "analysis_failed"):
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/traces", response_model=TracesResponse)
async def list_traces(
    page: int = 1,
    page_size: int = 20,
    scenario: Literal["S1", "S2", "S3", "S4", "S5"] | None = None,
    status: Literal["completed", "failed", "running"] | None = None,
):
    """历史分析列表"""
    base = runs_dir()
    if not base.is_dir():
        return TracesResponse(traces=[], total=0, page=page, page_size=page_size)

    now = datetime.now(timezone.utc)
    all_dirs = [d for d in base.iterdir() if d.is_dir() and _TRACE_RE.fullmatch(d.name)]

    if scenario is not None or status is not None:
        filtered = []
        for d in all_dirs:
            meta = _load_json(d / "meta.json") or {}
            input_data = meta.get("input", {})
            if scenario is not None and input_data.get("scenario") != scenario:
                continue
            if status is not None and _resolve_status(meta, d, now) != status:
                continue
            filtered.append(d)
        all_dirs = filtered

    dirs = sorted(all_dirs, key=lambda d: d.name, reverse=True)
    total = len(dirs)
    start = (page - 1) * page_size
    page_dirs = dirs[start : start + page_size]

    traces = []
    for d in page_dirs:
        meta = _load_json(d / "meta.json") or {}
        input_data = meta.get("input", {})
        competitors = [c.get("name", "") for c in input_data.get("competitors", [])]
        traces.append(TraceSummary(
            trace_id=d.name,
            scenario=input_data.get("scenario"),
            status=_resolve_status(meta, d, now),
            started_at=meta.get("started_at"),
            ended_at=meta.get("ended_at"),
            competitors=competitors,
        ))

    return TracesResponse(traces=traces, total=total, page=page, page_size=page_size)


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


@router.get("/trace/{trace_id}/export")
async def export_trace(trace_id: str, format: Literal["md", "html"] = "md"):
    """导出指定 trace 的报告为 markdown 或 html。

    - 路径穿越防护：复用 GET /trace/{id} 的 fullmatch + resolve 双层校验
    - 旧 trace schema 漂移容忍：BaseReport.model_validate 失败时回退 dict 模式（M10）
    """
    if not _TRACE_RE.fullmatch(trace_id):
        raise HTTPException(status_code=404, detail="trace not found")
    base = runs_dir()
    trace_dir = (base / trace_id).resolve()
    if base.resolve() not in trace_dir.parents and trace_dir != base.resolve():
        raise HTTPException(status_code=404, detail="trace not found")
    if not trace_dir.is_dir():
        raise HTTPException(status_code=404, detail="trace not found")
    report_path = trace_dir / "03_report.json"
    if not report_path.is_file():
        raise HTTPException(status_code=404, detail="该 trace 未产出报告")

    raw = _load_json(report_path)
    if raw is None:
        raise HTTPException(status_code=500, detail="report.json 解析失败")

    # M10 修入：旧 trace schema 漂移容忍
    try:
        report = BaseReport.model_validate(raw)
        report_dict = report.model_dump()
    except ValidationError as e:
        logger.warning(
            "[export] BaseReport.model_validate failed for %s, dict fallback: %s",
            trace_id, str(e)[:200],
        )
        report_dict = raw

    if format == "md":
        body = render_markdown(report_dict, trace_id=trace_id)
        return Response(
            content=body,
            media_type="text/markdown; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="report-{trace_id}.md"'
            },
        )
    elif format == "html":
        # Task 15 实现 render_html
        from src.api.exporters.html import render_html
        body = render_html(report_dict, trace_id=trace_id)
        return Response(
            content=body,
            media_type="text/html; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="report-{trace_id}.html"'
            },
        )
    else:
        raise HTTPException(status_code=400, detail="format must be md or html")
