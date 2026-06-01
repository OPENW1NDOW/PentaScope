# 可观测性与中间产物追溯 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为每次分析按 trace_id 落盘四阶段产物 + 重试快照 + 元信息 + 日志副本，新增追溯 API 与前端面板，使「每个 Agent 的决策过程与中间产物均可追溯」可验证。

**Architecture:** 新增 `TraceWriter`（`src/tools/`，与 llm_client/http_client 平级）封装容错落盘、版本快照、原子写；注入 `build_graph` 后各节点产出即落盘；`routes.py` 在 ainvoke 前后写两次 meta；新增 `GET /api/v1/trace/{trace_id}` 供前端读取；前端加「执行追溯」面板。日志在 `main.py` 启动时接线。

**Tech Stack:** Python 3.14, Pydantic v2, FastAPI, LangGraph, Streamlit, pytest (asyncio_mode=auto)。

设计依据：`docs/superpowers/specs/2026-06-02-observability-trace-persistence-design.md`

---

## File Structure

- **Create** `src/tools/trace_writer.py` — TraceWriter 类：trace_id 生成、容错落盘、版本快照、原子写、meta 写入。
- **Create** `src/utils/paths.py` — 项目根绝对路径解析（`runs/` 与 `logs/` 基目录），供后端各处统一引用，避免依赖 CWD。
- **Modify** `src/graph/builder.py` — `build_graph` 增加 `trace_writer` 参数；各节点产出后 `save_stage`；`should_continue` 记录路由决策到 node_trace。
- **Modify** `src/api/routes.py` — trace_id 用 `TraceWriter.new_trace_id`；创建 TraceWriter 注入 build_graph；ainvoke 前后两次写 meta；新增 `GET /trace/{trace_id}` 路由。
- **Modify** `src/api/main.py` — 启动时调用 `setup_logger` 接线 root logger。
- **Modify** `src/utils/logger.py` — 增加 `setup_logger` 配置 root logger 的能力（现有签名返回命名 logger，需补一个初始化 root 的入口）。
- **Modify** `src/api/schemas.py` — 新增 `TraceResponse` 模型。
- **Modify** `src/frontend/app.py` — 新增「执行追溯」面板，调用 trace API。
- **Modify** `.gitignore` — 增加 `runs/`。
- **Create** `tests/unit/test_trace_writer.py` — TraceWriter 单测。
- **Create** `tests/integration/test_trace_api.py` — 追溯 API 测试。
- **Modify** `tests/integration/test_graph.py` — 验证集成落盘（如已有 graph 测试则追加用例）。

**stage 常量集合**（硬编码，全程引用）：`"01_profiles"`, `"02_analysis"`, `"03_report"`, `"04_feedback"`。

---

## Task 1: 项目根路径工具

**Files:**
- Create: `src/utils/paths.py`
- Test: `tests/unit/test_paths.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_paths.py
from pathlib import Path
from src.utils.paths import project_root, runs_dir, logs_dir


def test_project_root_contains_src():
    root = project_root()
    assert (root / "src").is_dir()


def test_runs_dir_under_root():
    assert runs_dir() == project_root() / "runs"


def test_logs_dir_under_root():
    assert logs_dir() == project_root() / "logs"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_paths.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.utils.paths'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/utils/paths.py
from pathlib import Path


def project_root() -> Path:
    """项目根目录（src/utils/paths.py 向上两级）"""
    return Path(__file__).resolve().parents[2]


def runs_dir() -> Path:
    return project_root() / "runs"


def logs_dir() -> Path:
    return project_root() / "logs"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_paths.py -v`
Expected: PASS（3 passed）

- [ ] **Step 5: Commit**

```bash
git add src/utils/paths.py tests/unit/test_paths.py
git commit -m "feat: add project root path helper for runs/logs dirs"
```

---

## Task 2: TraceWriter — trace_id 生成与碰撞规避

**Files:**
- Create: `src/tools/trace_writer.py`
- Test: `tests/unit/test_trace_writer.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_trace_writer.py
import re
from src.tools.trace_writer import TraceWriter


def test_new_trace_id_format(tmp_path):
    tid = TraceWriter.new_trace_id(base_dir=tmp_path)
    assert re.fullmatch(r"\d{8}-\d{6}-[0-9a-f]{6}", tid)


def test_new_trace_id_collision_avoidance(tmp_path):
    tid = TraceWriter.new_trace_id(base_dir=tmp_path)
    (tmp_path / tid).mkdir()
    tid2 = TraceWriter.new_trace_id(base_dir=tmp_path)
    assert tid2 != tid
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_trace_writer.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.tools.trace_writer'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/tools/trace_writer.py
import json
import logging
import os
import secrets
from datetime import datetime, timezone, timedelta
from pathlib import Path
from pydantic import BaseModel

logger = logging.getLogger(__name__)

_BEIJING = timezone(timedelta(hours=8))


class TraceWriter:
    def __init__(self, trace_id: str, base_dir: Path):
        self.trace_id = trace_id
        self.dir = Path(base_dir) / trace_id
        self._written: set[str] = set()

    @staticmethod
    def new_trace_id(base_dir: Path) -> str:
        base = Path(base_dir)
        while True:
            ts = datetime.now(_BEIJING).strftime("%Y%m%d-%H%M%S")
            tid = f"{ts}-{secrets.token_hex(3)}"  # 3 bytes -> 6 hex
            if not (base / tid).exists():
                return tid
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_trace_writer.py -v`
Expected: PASS（2 passed）

- [ ] **Step 5: Commit**

```bash
git add src/tools/trace_writer.py tests/unit/test_trace_writer.py
git commit -m "feat: TraceWriter.new_trace_id with Beijing-time format and collision avoidance"
```

---

## Task 3: TraceWriter.save_stage — 单模型与列表序列化

**Files:**
- Modify: `src/tools/trace_writer.py`
- Test: `tests/unit/test_trace_writer.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_trace_writer.py （追加）
import json
from pathlib import Path
from datetime import datetime
from pydantic import BaseModel
from src.tools.trace_writer import TraceWriter


class _Dummy(BaseModel):
    name: str
    when: datetime  # 验证 model_dump(mode="json") 处理 datetime


def test_save_stage_single_model(tmp_path):
    tw = TraceWriter("t-1", base_dir=tmp_path)
    tw.save_stage("02_analysis", _Dummy(name="a", when=datetime(2026, 6, 2, 14, 30)))
    f = tmp_path / "t-1" / "02_analysis.json"
    assert f.exists()
    data = json.loads(f.read_text(encoding="utf-8"))
    assert data["name"] == "a"
    assert isinstance(data["when"], str)  # datetime 被序列化为字符串


def test_save_stage_list(tmp_path):
    tw = TraceWriter("t-2", base_dir=tmp_path)
    tw.save_stage("01_profiles", [_Dummy(name="x", when=datetime(2026, 6, 2)),
                                  _Dummy(name="y", when=datetime(2026, 6, 2))])
    data = json.loads((tmp_path / "t-2" / "01_profiles.json").read_text(encoding="utf-8"))
    assert isinstance(data, list) and len(data) == 2


def test_save_stage_empty_list(tmp_path):
    tw = TraceWriter("t-3", base_dir=tmp_path)
    tw.save_stage("01_profiles", [])
    data = json.loads((tmp_path / "t-3" / "01_profiles.json").read_text(encoding="utf-8"))
    assert data == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_trace_writer.py -k save_stage -v`
Expected: FAIL — `AttributeError: 'TraceWriter' object has no attribute 'save_stage'`

- [ ] **Step 3: Write minimal implementation**

在 `src/tools/trace_writer.py` 的 `TraceWriter` 类内追加：

```python
    def _atomic_write_json(self, path: Path, obj) -> None:
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(
            json.dumps(obj, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(tmp, path)

    @staticmethod
    def _serialize(data):
        if isinstance(data, list):
            return [m.model_dump(mode="json") for m in data]
        return data.model_dump(mode="json")

    def save_stage(self, stage: str, data) -> None:
        try:
            self.dir.mkdir(parents=True, exist_ok=True)
            target = self.dir / f"{stage}.json"
            obj = self._serialize(data)
            self._atomic_write_json(target, obj)
            self._written.add(stage)
        except Exception as e:  # noqa: BLE001 — 落盘是辅助能力，绝不阻塞主流程
            logger.warning("[trace] 落盘失败 stage=%s trace=%s: %s", stage, self.trace_id, e)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_trace_writer.py -k save_stage -v`
Expected: PASS（3 passed）

- [ ] **Step 5: Commit**

```bash
git add src/tools/trace_writer.py tests/unit/test_trace_writer.py
git commit -m "feat: TraceWriter.save_stage with json-mode serialization and atomic write"
```

---

## Task 4: TraceWriter.save_stage — 重试快照 _vN

**Files:**
- Modify: `src/tools/trace_writer.py`
- Test: `tests/unit/test_trace_writer.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_trace_writer.py （追加）
def test_save_stage_creates_v1_snapshot_on_rewrite(tmp_path):
    tw = TraceWriter("t-4", base_dir=tmp_path)
    tw.save_stage("03_report", _Dummy(name="first", when=datetime(2026, 6, 2)))
    tw.save_stage("03_report", _Dummy(name="second", when=datetime(2026, 6, 2)))
    d = tmp_path / "t-4"
    latest = json.loads((d / "03_report.json").read_text(encoding="utf-8"))
    v1 = json.loads((d / "03_report_v1.json").read_text(encoding="utf-8"))
    assert latest["name"] == "second"   # 最新版无版本号
    assert v1["name"] == "first"        # 历史版本 _v1


def test_save_stage_v_number_from_disk(tmp_path):
    """进程重启场景：内存计数归零，但 N 应取磁盘已有最大版本+1"""
    tw = TraceWriter("t-5", base_dir=tmp_path)
    tw.save_stage("03_report", _Dummy(name="r1", when=datetime(2026, 6, 2)))
    tw.save_stage("03_report", _Dummy(name="r2", when=datetime(2026, 6, 2)))  # 产生 _v1
    # 模拟新实例（内存计数清零）
    tw2 = TraceWriter("t-5", base_dir=tmp_path)
    tw2.save_stage("03_report", _Dummy(name="r3", when=datetime(2026, 6, 2)))  # 应产生 _v2，不覆盖 _v1
    d = tmp_path / "t-5"
    assert (d / "03_report_v1.json").exists()
    assert (d / "03_report_v2.json").exists()
    assert json.loads((d / "03_report_v1.json").read_text(encoding="utf-8"))["name"] == "r1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_trace_writer.py -k snapshot -v`
Expected: FAIL — 只有 `03_report.json`，无 `_v1`（旧文件被直接覆盖）

- [ ] **Step 3: Write minimal implementation**

在 `save_stage` 的 `mkdir` 之后、写入 `target` 之前，插入快照逻辑。修改 `save_stage` 为：

```python
    def _next_version(self, stage: str) -> int:
        existing = list(self.dir.glob(f"{stage}_v*.json"))
        nums = []
        for p in existing:
            suffix = p.stem[len(stage) + 2:]  # 去掉 "{stage}_v"
            if suffix.isdigit():
                nums.append(int(suffix))
        return (max(nums) + 1) if nums else 1

    def save_stage(self, stage: str, data) -> None:
        try:
            self.dir.mkdir(parents=True, exist_ok=True)
            target = self.dir / f"{stage}.json"
            if target.exists():
                n = self._next_version(stage)
                os.replace(target, self.dir / f"{stage}_v{n}.json")
            obj = self._serialize(data)
            self._atomic_write_json(target, obj)
            self._written.add(stage)
        except Exception as e:  # noqa: BLE001
            logger.warning("[trace] 落盘失败 stage=%s trace=%s: %s", stage, self.trace_id, e)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_trace_writer.py -v`
Expected: PASS（全部，含之前用例）

- [ ] **Step 5: Commit**

```bash
git add src/tools/trace_writer.py tests/unit/test_trace_writer.py
git commit -m "feat: TraceWriter retry snapshots with disk-based version numbering"
```

---

## Task 5: TraceWriter.save_meta 与落盘容错

**Files:**
- Modify: `src/tools/trace_writer.py`
- Test: `tests/unit/test_trace_writer.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_trace_writer.py （追加）
def test_save_meta_overwrites(tmp_path):
    tw = TraceWriter("t-6", base_dir=tmp_path)
    tw.save_meta({"status": "running"})
    tw.save_meta({"status": "completed"})
    data = json.loads((tmp_path / "t-6" / "meta.json").read_text(encoding="utf-8"))
    assert data["status"] == "completed"   # 覆盖写，无版本快照
    assert not (tmp_path / "t-6" / "meta_v1.json").exists()


def test_save_stage_failure_does_not_raise(tmp_path, monkeypatch):
    tw = TraceWriter("t-7", base_dir=tmp_path)

    def boom(*a, **k):
        raise OSError("disk full")
    monkeypatch.setattr(tw, "_atomic_write_json", boom)
    # 不抛异常即通过
    tw.save_stage("01_profiles", _Dummy(name="x", when=datetime(2026, 6, 2)))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_trace_writer.py -k "meta or failure" -v`
Expected: FAIL — `AttributeError: ... has no attribute 'save_meta'`

- [ ] **Step 3: Write minimal implementation**

在 `TraceWriter` 类内追加：

```python
    def save_meta(self, meta: dict) -> None:
        try:
            self.dir.mkdir(parents=True, exist_ok=True)
            self._atomic_write_json(self.dir / "meta.json", meta)
        except Exception as e:  # noqa: BLE001
            logger.warning("[trace] meta 落盘失败 trace=%s: %s", self.trace_id, e)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_trace_writer.py -v`
Expected: PASS（全部）

- [ ] **Step 5: Commit**

```bash
git add src/tools/trace_writer.py tests/unit/test_trace_writer.py
git commit -m "feat: TraceWriter.save_meta and verify warn-only failure handling"
```

---

## Task 6: 日志接线（setup_logger 配置 root logger）

**Files:**
- Modify: `src/utils/logger.py`
- Modify: `src/api/main.py`
- Test: `tests/unit/test_logger.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_logger.py
import logging
from src.utils.logger import init_logging


def test_init_logging_configures_root_with_file(tmp_path):
    log_file = tmp_path / "app.log"
    init_logging(log_file=log_file, level=logging.INFO)
    root = logging.getLogger()
    assert root.level == logging.INFO
    logging.getLogger("x").info("hello-trace")
    for h in root.handlers:
        h.flush()
    assert log_file.exists()
    assert "hello-trace" in log_file.read_text(encoding="utf-8")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_logger.py -v`
Expected: FAIL — `ImportError: cannot import name 'init_logging'`

- [ ] **Step 3: Write minimal implementation**

在 `src/utils/logger.py` 末尾追加（保留现有 `setup_logger` 不动）：

```python
def init_logging(log_file=None, level: int = logging.INFO) -> None:
    """初始化 root logger：控制台 + 文件。API 启动时调用一次。"""
    from src.utils.paths import logs_dir

    if log_file is None:
        logs_dir().mkdir(exist_ok=True)
        log_file = logs_dir() / "app.log"

    root = logging.getLogger()
    root.setLevel(level)

    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    has_file = any(isinstance(h, logging.FileHandler) for h in root.handlers)
    if not has_file:
        fh = logging.FileHandler(str(log_file), encoding="utf-8")
        fh.setFormatter(formatter)
        root.addHandler(fh)

    has_console = any(
        isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
        for h in root.handlers
    )
    if not has_console:
        import sys
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(formatter)
        root.addHandler(ch)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_logger.py -v`
Expected: PASS

- [ ] **Step 5: 接线 main.py**

修改 `src/api/main.py`：

```python
from fastapi import FastAPI
from src.api.routes import router
from src.utils.logger import init_logging

init_logging()

app = FastAPI(title="竞品分析 Agent 系统", version="1.0.0")
app.include_router(router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 6: 验证后端启动日志可见**

Run: `python -c "import src.api.main"`
Expected: 无异常；项目根生成 `logs/app.log`。

- [ ] **Step 7: Commit**

```bash
git add src/utils/logger.py src/api/main.py tests/unit/test_logger.py
git commit -m "feat: wire up root logging to console and logs/app.log on API startup"
```

---

## Task 7: graph 接线 — 注入 TraceWriter 并各节点落盘

**Files:**
- Modify: `src/graph/builder.py`
- Test: `tests/integration/test_graph.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/integration/test_graph.py （追加；现有文件已构造 mock agent，沿用其风格）
# 若现有 test_graph.py 已有 mock LLM/agent 装配，复用之；此处给出独立最小用例。
import json
from pathlib import Path
from unittest.mock import AsyncMock
from src.graph.builder import build_graph
from src.tools.trace_writer import TraceWriter


async def test_graph_persists_stage_artifacts(tmp_path, monkeypatch,
                                               sample_competitor_profile,
                                               sample_competitive_analysis,
                                               sample_final_report):
    from src.schemas.profile import CompetitorProfile
    from src.schemas.analysis import CompetitiveAnalysis
    from src.schemas.report import FinalReport
    from src.schemas.feedback import RejectionFeedback
    from src.schemas.input import CompetitorInput, CompetitorBasic

    # mock 四个 agent 的方法，避免真实 LLM
    monkeypatch.setattr("src.graph.builder.CollectorAgent.collect",
                        AsyncMock(return_value=[CompetitorProfile(**sample_competitor_profile)]))
    monkeypatch.setattr("src.graph.builder.AnalyzerAgent.analyze",
                        AsyncMock(return_value=CompetitiveAnalysis(**sample_competitive_analysis)))
    monkeypatch.setattr("src.graph.builder.WriterAgent.write",
                        AsyncMock(return_value=FinalReport(**sample_final_report)))
    monkeypatch.setattr("src.graph.builder.InspectorAgent.inspect",
                        AsyncMock(return_value=RejectionFeedback(passed=True, issues=[])))

    tw = TraceWriter("graph-1", base_dir=tmp_path)
    graph = build_graph(llm=None, http=None, parser=None, trace_writer=tw)

    user_input = CompetitorInput(
        competitors=[CompetitorBasic(name="支付宝")],
        analysis_context="测试",
    )
    await graph.ainvoke({
        "user_input": user_input, "retry_count": 0, "max_retries": 2, "trace_id": "graph-1",
    })

    d = tmp_path / "graph-1"
    assert (d / "01_profiles.json").exists()
    assert (d / "02_analysis.json").exists()
    assert (d / "03_report.json").exists()
    assert (d / "04_feedback.json").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_graph.py::test_graph_persists_stage_artifacts -v`
Expected: FAIL — `build_graph() got an unexpected keyword argument 'trace_writer'`

- [ ] **Step 3: Write minimal implementation**

修改 `src/graph/builder.py`：

1. 函数签名加参数：

```python
def build_graph(llm, http, parser, trace_writer=None) -> StateGraph:
```

2. 在 `build_graph` 内创建 agent 之后定义一个安全落盘助手，并在四个节点产出处调用：

```python
    def _save(stage: str, data):
        if trace_writer is not None:
            trace_writer.save_stage(stage, data)
```

3. 各节点 return 前调用（落盘点见设计 §7）：

```python
    async def collector_node(state: AnalysisState) -> dict:
        logger.info("[graph] → collector")
        profiles = await collector.collect(state["user_input"])
        _save("01_profiles", profiles)
        return {"profiles": profiles, "current_node": "collector"}

    async def analyzer_node(state: AnalysisState) -> dict:
        logger.info("[graph] → analyzer")
        analysis = await analyzer.analyze(state["profiles"])
        _save("02_analysis", analysis)
        return {"analysis": analysis, "current_node": "analyzer"}
```

writer_node 在回填 sources 之后、return 前加 `_save("03_report", report)`；inspector_node 在回填 quality_score 之后、return 前加 `_save("04_feedback", feedback)`。

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/integration/test_graph.py::test_graph_persists_stage_artifacts -v`
Expected: PASS

- [ ] **Step 5: 回归 — 现有 graph 测试不破**

Run: `pytest tests/integration/test_graph.py -v`
Expected: 现有用例仍 PASS（`trace_writer` 默认 None，旧调用不受影响）

- [ ] **Step 6: Commit**

```bash
git add src/graph/builder.py tests/integration/test_graph.py
git commit -m "feat: inject TraceWriter into build_graph and persist stage artifacts"
```

---

## Task 8: node_trace 路由决策记录

**Files:**
- Modify: `src/graph/builder.py`
- Test: `tests/integration/test_graph.py`

**说明：** node_trace 记录节点执行序列与每次打回的 issues 摘要。用 `build_graph` 闭包内的可变 list 收集，`should_continue` 决策时追加。最终由 routes.py 写入 meta（Task 9）。为让 routes 拿到，`build_graph` 返回 `(compiled_graph, node_trace_list)`。

- [ ] **Step 1: Write the failing test**

```python
# tests/integration/test_graph.py （追加）
async def test_build_graph_returns_node_trace(tmp_path, monkeypatch,
                                               sample_competitor_profile,
                                               sample_competitive_analysis,
                                               sample_final_report):
    from src.schemas.profile import CompetitorProfile
    from src.schemas.analysis import CompetitiveAnalysis
    from src.schemas.report import FinalReport
    from src.schemas.feedback import RejectionFeedback
    from src.schemas.input import CompetitorInput, CompetitorBasic

    monkeypatch.setattr("src.graph.builder.CollectorAgent.collect",
                        AsyncMock(return_value=[CompetitorProfile(**sample_competitor_profile)]))
    monkeypatch.setattr("src.graph.builder.AnalyzerAgent.analyze",
                        AsyncMock(return_value=CompetitiveAnalysis(**sample_competitive_analysis)))
    monkeypatch.setattr("src.graph.builder.WriterAgent.write",
                        AsyncMock(return_value=FinalReport(**sample_final_report)))
    monkeypatch.setattr("src.graph.builder.InspectorAgent.inspect",
                        AsyncMock(return_value=RejectionFeedback(passed=True, issues=[])))

    graph, node_trace = build_graph(llm=None, http=None, parser=None, trace_writer=None)
    user_input = CompetitorInput(competitors=[CompetitorBasic(name="支付宝")], analysis_context="测试")
    await graph.ainvoke({"user_input": user_input, "retry_count": 0, "max_retries": 2, "trace_id": "nt-1"})

    assert node_trace[:4] == ["collector", "analyzer", "writer", "inspector"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_graph.py::test_build_graph_returns_node_trace -v`
Expected: FAIL — `cannot unpack non-sequence`（build_graph 仍返回单值）

- [ ] **Step 3: Write minimal implementation**

修改 `src/graph/builder.py`：

1. 在 `build_graph` 开头创建 `node_trace: list = []`。
2. 每个节点开头 `node_trace.append("<name>")`（在现有 `logger.info` 旁）。
3. `should_continue` 中打回时记录决策摘要：

```python
    def should_continue(state: AnalysisState) -> str:
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
        target = "collector" if "collector" in target_agents else "writer"
        node_trace.append(f"reject->{target} issues={issues_summary}")
        return target
```

4. 函数末尾改为 `return graph.compile(), node_trace`。

- [ ] **Step 4: 修复 Task 7 测试的解包**

Task 7 用例改为 `graph, _ = build_graph(...)`（解包二元组）。

- [ ] **Step 5: Run tests**

Run: `pytest tests/integration/test_graph.py -v`
Expected: PASS（含 Task 7 用例，已解包修正）

- [ ] **Step 6: Commit**

```bash
git add src/graph/builder.py tests/integration/test_graph.py
git commit -m "feat: build_graph returns node_trace recording routing decisions"
```

---

## Task 9: routes.py — trace_id 生成、TraceWriter 注入、两次写 meta

**Files:**
- Modify: `src/api/routes.py`
- Test: `tests/integration/test_trace_api.py`（本任务先建文件，测 analyze 落盘）

- [ ] **Step 1: Write the failing test**

```python
# tests/integration/test_trace_api.py
import json
from pathlib import Path
from unittest.mock import AsyncMock
import pytest
from httpx import AsyncClient, ASGITransport


@pytest.fixture
def mock_agents(monkeypatch, sample_competitor_profile,
                sample_competitive_analysis, sample_final_report):
    from src.schemas.profile import CompetitorProfile
    from src.schemas.analysis import CompetitiveAnalysis
    from src.schemas.report import FinalReport
    from src.schemas.feedback import RejectionFeedback
    monkeypatch.setattr("src.graph.builder.CollectorAgent.collect",
                        AsyncMock(return_value=[CompetitorProfile(**sample_competitor_profile)]))
    monkeypatch.setattr("src.graph.builder.AnalyzerAgent.analyze",
                        AsyncMock(return_value=CompetitiveAnalysis(**sample_competitive_analysis)))
    monkeypatch.setattr("src.graph.builder.WriterAgent.write",
                        AsyncMock(return_value=FinalReport(**sample_final_report)))
    monkeypatch.setattr("src.graph.builder.InspectorAgent.inspect",
                        AsyncMock(return_value=RejectionFeedback(passed=True, issues=[])))


async def test_analyze_persists_meta(monkeypatch, tmp_path, mock_agents):
    # 把 runs 基目录指向 tmp_path
    monkeypatch.setattr("src.api.routes.runs_dir", lambda: tmp_path)
    from src.api.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/api/v1/analyze", json={
            "competitors": [{"name": "支付宝"}],
            "analysis_context": "测试",
        })
    assert resp.status_code == 200
    tid = resp.json()["trace_id"]
    meta = json.loads((tmp_path / tid / "meta.json").read_text(encoding="utf-8"))
    assert meta["status"] == "completed"
    assert meta["node_trace"][:4] == ["collector", "analyzer", "writer", "inspector"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_trace_api.py::test_analyze_persists_meta -v`
Expected: FAIL — meta.json 不存在 / `runs_dir` 未在 routes 导入

- [ ] **Step 3: Write minimal implementation**

修改 `src/api/routes.py`：

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/integration/test_trace_api.py::test_analyze_persists_meta -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/api/routes.py tests/integration/test_trace_api.py
git commit -m "feat: generate trace_id, inject TraceWriter, write running/completed meta in analyze route"
```

---

## Task 10: 追溯 API — GET /trace/{trace_id}

**Files:**
- Modify: `src/api/schemas.py`
- Modify: `src/api/routes.py`
- Test: `tests/integration/test_trace_api.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/integration/test_trace_api.py （追加）
async def test_get_trace_returns_stages(monkeypatch, tmp_path, mock_agents):
    monkeypatch.setattr("src.api.routes.runs_dir", lambda: tmp_path)
    from src.api.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        post = await ac.post("/api/v1/analyze", json={
            "competitors": [{"name": "支付宝"}], "analysis_context": "测试"})
        tid = post.json()["trace_id"]
        resp = await ac.get(f"/api/v1/trace/{tid}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["trace_id"] == tid
    assert body["meta"]["status"] == "completed"
    assert "report" in body["stages"]
    assert body["stages"]["profiles"] is not None


async def test_get_trace_404_when_missing(monkeypatch, tmp_path):
    monkeypatch.setattr("src.api.routes.runs_dir", lambda: tmp_path)
    from src.api.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/v1/trace/20260602-143052-abcdef")
    assert resp.status_code == 404


async def test_get_trace_rejects_path_traversal(monkeypatch, tmp_path):
    monkeypatch.setattr("src.api.routes.runs_dir", lambda: tmp_path)
    from src.api.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 非法格式（含 ../）必须被拒，返回 404（FastAPI 路径参数不跨 /，这里测纯非法格式）
        resp = await ac.get("/api/v1/trace/not-a-valid-id")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_trace_api.py -k trace -v`
Expected: FAIL — 404 路由不存在（GET /trace 未定义）

- [ ] **Step 3: Write minimal implementation**

在 `src/api/schemas.py` 追加：

```python
class TraceResponse(BaseModel):
    """追溯 API 响应"""
    trace_id: str
    meta: dict | None = None
    stages: dict = Field(default_factory=dict)
    snapshots: list[str] = Field(default_factory=list)
    log: str = ""
```

在 `src/api/routes.py` 追加（顶部加 `import re`、`from fastapi import HTTPException`、`from src.api.schemas import TraceResponse`）：

```python
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
    import json as _json
    log_path = trace_dir / "run.log"
    log_text = log_path.read_text(encoding="utf-8") if log_path.is_file() else ""

    return TraceResponse(
        trace_id=trace_id,
        meta=_load_json(trace_dir / "meta.json"),
        stages=stages,
        snapshots=snapshots,
        log=log_text,
    )
```

需在 `routes.py` 顶部确保 `import json`。

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/integration/test_trace_api.py -k trace -v`
Expected: PASS（3 passed）

- [ ] **Step 5: Commit**

```bash
git add src/api/schemas.py src/api/routes.py tests/integration/test_trace_api.py
git commit -m "feat: add GET /trace/{trace_id} endpoint with path-traversal guard and version fetch"
```

---

## Task 11: run.log 每次分析日志副本

**Files:**
- Modify: `src/api/routes.py`
- Test: `tests/integration/test_trace_api.py`

**说明：** 在 analyze 期间为该 trace 挂一个临时 FileHandler 写 `runs/<trace_id>/run.log`，结束后移除。轻度并发下可能有少量串扰（设计 §8 已记录为可接受权衡）。

- [ ] **Step 1: Write the failing test**

```python
# tests/integration/test_trace_api.py （追加）
async def test_run_log_created(monkeypatch, tmp_path, mock_agents):
    monkeypatch.setattr("src.api.routes.runs_dir", lambda: tmp_path)
    from src.api.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        post = await ac.post("/api/v1/analyze", json={
            "competitors": [{"name": "支付宝"}], "analysis_context": "测试"})
        tid = post.json()["trace_id"]
    log_file = tmp_path / tid / "run.log"
    assert log_file.exists()
    assert "→ collector" in log_file.read_text(encoding="utf-8")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_trace_api.py::test_run_log_created -v`
Expected: FAIL — run.log 不存在

- [ ] **Step 3: Write minimal implementation**

在 `analyze` 函数内，创建 tw 后、`try` 之前挂 handler；`finally` 中移除。修改 `analyze`：

```python
    # 在 save_meta(running) 之后：
    trace_dir = runs_dir() / trace_id
    trace_dir.mkdir(parents=True, exist_ok=True)
    run_handler = logging.FileHandler(str(trace_dir / "run.log"), encoding="utf-8")
    run_handler.setFormatter(logging.Formatter(
        "[%(asctime)s] %(levelname)s %(name)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
    logging.getLogger().addHandler(run_handler)
```

并在 `finally` 块中：

```python
    finally:
        logging.getLogger().removeHandler(run_handler)
        run_handler.close()
        await http.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/integration/test_trace_api.py::test_run_log_created -v`
Expected: PASS（依赖 Task 6 的 root logger 已配置 INFO level）

- [ ] **Step 5: Commit**

```bash
git add src/api/routes.py tests/integration/test_trace_api.py
git commit -m "feat: write per-trace run.log copy during analysis"
```

---

## Task 12: 前端「执行追溯」面板

**Files:**
- Modify: `src/frontend/app.py`
- 手动验证（Streamlit UI 无单测）

- [ ] **Step 1: 阅读现有 app.py 结构**

Run: 先 Read `src/frontend/app.py` 全文，确认现有 API base url、展示报告的代码位置、`data['trace_id']` 的使用处（`app.py:53` 附近）。

- [ ] **Step 2: 新增追溯面板**

在报告展示区之后追加一个 `st.expander("执行追溯（中间产物）", expanded=False)`，内部：
- 一个 `st.text_input` 预填当前 `trace_id`，按钮「加载追溯」。
- 点击后 `requests.get(f"{API_BASE}/trace/{trace_id}")`，非 200 用 `st.error` 展示 detail。
- 200 时用 `st.tabs(["元信息","采集","分析","报告","质检","日志"])` 分页展示 `meta`/`stages.*`/`log`；用 `st.json` 渲染各阶段，`st.code` 渲染 `log`。
- 若 `snapshots` 非空，列出版本名，提供下拉 `st.selectbox` 选某版本，按钮加载 `?version=xxx` 取内容并 `st.json` 展示，便于对比打回前后。

实现示例（沿用现有 requests + API_BASE 模式；若现有用 httpx 则相应替换）：

```python
with st.expander("执行追溯（中间产物）", expanded=False):
    tid_input = st.text_input("Trace ID", value=st.session_state.get("last_trace_id", ""))
    if st.button("加载追溯") and tid_input:
        r = requests.get(f"{API_BASE}/trace/{tid_input}")
        if r.status_code != 200:
            st.error(f"加载失败：{r.json().get('detail', r.status_code)}")
        else:
            t = r.json()
            tabs = st.tabs(["元信息", "采集", "分析", "报告", "质检", "日志"])
            with tabs[0]:
                st.json(t.get("meta") or {})
            with tabs[1]:
                st.json(t["stages"].get("profiles"))
            with tabs[2]:
                st.json(t["stages"].get("analysis"))
            with tabs[3]:
                st.json(t["stages"].get("report"))
            with tabs[4]:
                st.json(t["stages"].get("feedback"))
            with tabs[5]:
                st.code(t.get("log") or "（无日志）")
            if t.get("snapshots"):
                st.markdown("**重试快照**")
                ver = st.selectbox("选择历史版本", t["snapshots"])
                if st.button("查看该版本"):
                    rv = requests.get(f"{API_BASE}/trace/{tid_input}", params={"version": ver})
                    if rv.status_code == 200:
                        st.json(rv.json()["stages"].get(ver))
```

并在分析成功处记录 `st.session_state["last_trace_id"] = data["trace_id"]`（`app.py:53` 附近）。

- [ ] **Step 3: 手动验证**

Run（两个终端）：
```bash
uvicorn src.api.main:app --reload
streamlit run src/frontend/app.py
```
操作：跑一次分析 → 展开「执行追溯」→ 确认四阶段 JSON、日志、（如有打回）快照对比均能展示。

- [ ] **Step 4: Commit**

```bash
git add src/frontend/app.py
git commit -m "feat: add execution trace panel to frontend"
```

---

## Task 13: .gitignore 加入 runs/

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: 修改 .gitignore**

在 `# Logs` 段落附近加：

```
# Runtime artifacts
runs/
```

- [ ] **Step 2: 验证**

Run: `git status`
Expected: `runs/` 下的运行产物不出现在待提交列表。

- [ ] **Step 3: Commit**

```bash
git add .gitignore
git commit -m "chore: gitignore runs/ artifacts directory"
```

---

## Task 14: 全量回归与文档更新

**Files:**
- Modify: `docs/SPEC.md`（补目录树 `runs/` 与 `trace_writer.py`）
- Modify: `PROGRESS.md`、`DECISIONS.md`（结束流程，按 CLAUDE.md）

- [ ] **Step 1: 全量测试**

Run: `pytest -v`
Expected: 全部 PASS（原 51 + 新增用例）。

- [ ] **Step 2: lint**

Run: `ruff check src tests`
Expected: 无 error（必要时 `ruff check --fix src tests`）。

- [ ] **Step 3: 更新 SPEC.md 目录树**

在 `docs/SPEC.md` 的 Project Structure 中，`src/tools/` 下补 `trace_writer.py`，`src/utils/` 下补 `paths.py`，根目录补 `runs/  # 运行产物（gitignore）`。

- [ ] **Step 4: 更新 PROGRESS.md / DECISIONS.md**

PROGRESS：记录本次完成可观测性落盘 + 追溯 API + 前端面板；DECISIONS：记录「中间产物按 trace_id 落盘、单用户轻度并发权衡、不存 prompt 留作扩展」等本次决策。

- [ ] **Step 5: Commit**

```bash
git add docs/SPEC.md PROGRESS.md DECISIONS.md
git commit -m "docs: update spec structure and progress for trace persistence"
```

---

## Self-Review（计划自审记录）

- **Spec 覆盖**：§4 目录结构→Task 2/3/4/13；§5 trace_id→Task 2/9；§6 TraceWriter→Task 2-5；§7 graph 接线+meta 两次写+node_trace→Task 7/8/9；§8 追溯 API+日志→Task 6/10/11；前端面板→Task 12；测试策略→各 Task 内嵌 + Task 14 回归。无遗漏。
- **占位符**：无 TBD/TODO，所有代码步骤含完整代码。
- **类型一致性**：`build_graph` 在 Task 7 加 `trace_writer` 参数、Task 8 改为返回二元组（Task 7 用例同步解包修正）；`save_stage`/`save_meta`/`new_trace_id` 签名贯穿一致；stage 常量 `01_profiles`/`02_analysis`/`03_report`/`04_feedback` 全程统一；`runs_dir`/`logs_dir`/`project_root` 在 Task 1 定义后各处引用一致。
