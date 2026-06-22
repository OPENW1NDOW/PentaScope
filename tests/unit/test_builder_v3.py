"""builder.py v3 单测：_load_prior_report_data / _route_entry / build_graph 编译 / writer 异常路由。

writer_node 是 build_graph 内的闭包，直接拿不到——通过编译图执行 + 校验 state 输出来覆盖。
"""
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.graph.builder import _load_prior_report_data, _route_entry, build_graph


# ========== 1. build_graph 编译 ==========

def test_build_graph_compiles():
    """build_graph 返回 (compiled_graph, node_trace) 二元组，不抛 import / 编译错误。"""
    graph, node_trace = build_graph(llm=MagicMock(), http=MagicMock(), parser=MagicMock())
    assert graph is not None
    assert isinstance(node_trace, list)
    assert node_trace == []


def test_build_graph_contains_all_nodes():
    """编译后的图应当包含 recommender / collector / analyzer / writer / inspector 5 个节点。"""
    graph, _ = build_graph(llm=MagicMock(), http=MagicMock(), parser=MagicMock())
    # langgraph CompiledStateGraph 暴露 nodes 属性（dict-like）
    nodes = set(graph.nodes.keys())
    assert {"recommender", "collector", "analyzer", "writer", "inspector"}.issubset(nodes)


# ========== 2. _route_entry ==========

def test_route_entry_s2_goes_recommender():
    """[v3] S2 入口 → recommender。"""
    ui = MagicMock()
    ui.scenario = "S2"
    state = {"user_input": ui}
    assert _route_entry(state) == "recommender"


@pytest.mark.parametrize("scenario", ["S1", "S3", "S4", "S5"])
def test_route_entry_non_s2_goes_collector(scenario):
    """[v3] 非 S2 入口 → collector。"""
    ui = MagicMock()
    ui.scenario = scenario
    state = {"user_input": ui}
    assert _route_entry(state) == "collector"


# ========== 3. _load_prior_report_data ==========

def test_load_prior_report_data_empty_trace_id():
    """prior_trace_id 为空字符串 / None → 返回 None（不读盘）。"""
    assert _load_prior_report_data("") is None
    assert _load_prior_report_data(None) is None


def test_load_prior_report_data_handles_missing_file(tmp_path, monkeypatch):
    """prior_trace_id 文件不存在 → 返回 None。"""
    monkeypatch.setattr("src.graph.builder.RUNS_DIR", tmp_path)
    result = _load_prior_report_data("nonexistent")
    assert result is None


def test_load_prior_report_data_handles_invalid_json(tmp_path, monkeypatch):
    """prior 报告 JSON 解析失败 → 返回 None。"""
    monkeypatch.setattr("src.graph.builder.RUNS_DIR", tmp_path)
    bad_dir = tmp_path / "abc123"
    bad_dir.mkdir()
    (bad_dir / "03_report.json").write_text("{ this is not valid json", encoding="utf-8")
    result = _load_prior_report_data("abc123")
    assert result is None


def test_load_prior_report_data_validates_scenario(tmp_path, monkeypatch):
    """prior 报告 scenario != S4 → 返回 None。"""
    monkeypatch.setattr("src.graph.builder.RUNS_DIR", tmp_path)
    bad_dir = tmp_path / "abc123"
    bad_dir.mkdir()
    (bad_dir / "03_report.json").write_text(
        '{"metadata":{"scenario":"S2","schema_version":"2.0"}}',
        encoding="utf-8",
    )
    result = _load_prior_report_data("abc123")
    assert result is None


def test_load_prior_report_data_validates_schema_version(tmp_path, monkeypatch):
    """prior 报告 schema_version != 2.0 → 返回 None。"""
    monkeypatch.setattr("src.graph.builder.RUNS_DIR", tmp_path)
    bad_dir = tmp_path / "abc123"
    bad_dir.mkdir()
    (bad_dir / "03_report.json").write_text(
        '{"metadata":{"scenario":"S4","schema_version":"1.0"}}',
        encoding="utf-8",
    )
    result = _load_prior_report_data("abc123")
    assert result is None


def test_load_prior_data_rejects_path_traversal(tmp_path, monkeypatch):
    """[D3 review C-new] prior_trace_id 含 ../ \\ : 等非法字符 → 返回 None，不读盘。"""
    monkeypatch.setattr("src.graph.builder.RUNS_DIR", tmp_path)

    # 反正常情况：先在 tmp_path 之外放一个伪敏感文件，确保越过去能命中
    secret = tmp_path.parent / "secret_run" / "03_report.json"
    secret.parent.mkdir(parents=True, exist_ok=True)
    secret.write_text(
        '{"metadata":{"scenario":"S4","schema_version":"2.0"},"leaked":true}',
        encoding="utf-8",
    )

    # 各种路径穿越尝试都应被白名单拒绝
    for bad_id in [
        "../secret_run",
        "..\\secret_run",
        "../../etc/passwd",
        "abc/../def",
        "abc:def",
        "abc\\def",
        "ABC123",  # 大写字母不在 [a-f0-9-]
        "abc_123",  # 下划线不在白名单
        "a" * 65,  # 超长
    ]:
        assert _load_prior_report_data(bad_id) is None, f"{bad_id!r} 未被白名单拦截"


def test_load_prior_report_data_returns_data_when_valid(tmp_path, monkeypatch):
    """prior 报告 scenario=S4 + schema_version=2.0 → 返回 data dict。"""
    monkeypatch.setattr("src.graph.builder.RUNS_DIR", tmp_path)
    good_dir = tmp_path / "abc456"
    good_dir.mkdir()
    (good_dir / "03_report.json").write_text(
        '{"metadata":{"scenario":"S4","schema_version":"2.0"},"foo":"bar"}',
        encoding="utf-8",
    )
    result = _load_prior_report_data("abc456")
    assert result is not None
    assert result["foo"] == "bar"
    assert result["metadata"]["scenario"] == "S4"


# ========== 4. writer_node 异常路由（通过编译图运行覆盖）==========

def _make_minimal_state(scenario: str = "S1"):
    """构造最小可执行 state，writer 节点会读 user_input/profiles/analysis。"""
    from src.schemas.input import CompetitorBasic, ScenarioInput

    ui = ScenarioInput(
        scenario=scenario,
        competitors=[CompetitorBasic(name="ProdA", company="CoA")],
        analysis_context="测试上下文",
        our_product_name="OurProd",
    )
    return {
        "user_input": ui,
        "profiles": [MagicMock()],
        "analysis": MagicMock(),
        "retry_count": 0,
        "max_retries": 2,
    }


@pytest.mark.asyncio
async def test_writer_node_runtime_error_routes_to_collector(monkeypatch):
    """[v3-R02] writer raise WriterRouteToCollector → feedback.issues[0].agent='collector' + retry_count+1。"""
    from src.agents.writer_orchestrator import WriterRouteToCollector

    async def _raise(*args, **kwargs):
        raise WriterRouteToCollector(
            "phase 4: profiles 0 个 URL，建议 graph 回 collector 重新采集"
        )

    monkeypatch.setattr(
        "src.agents.writer_orchestrator.WriterOrchestrator.write",
        _raise,
    )

    graph, _ = build_graph(llm=MagicMock(), http=MagicMock(), parser=MagicMock())

    # 直接拿到 writer 节点的 runnable 并执行（compile 后图节点暴露在 .nodes）
    state = _make_minimal_state("S1")
    result = await graph.nodes["writer"].ainvoke(state)

    assert "feedback" in result
    fb = result["feedback"]
    assert fb.passed is False
    assert len(fb.issues) == 1
    assert fb.issues[0].agent == "collector"
    assert fb.issues[0].severity == "critical"
    assert fb.issues[0].field == "writer_runtime"
    assert result["retry_count"] == 1


@pytest.mark.asyncio
async def test_writer_node_runtime_error_routes_to_writer(monkeypatch):
    """[v3-R02] writer raise WriterRouteToWriter → feedback.issues[0].agent='writer'。"""
    from src.agents.writer_orchestrator import WriterRouteToWriter

    async def _raise(*args, **kwargs):
        raise WriterRouteToWriter("phase 4: 0 个 source_refs，建议 graph 回 writer 重试")

    monkeypatch.setattr(
        "src.agents.writer_orchestrator.WriterOrchestrator.write",
        _raise,
    )

    graph, _ = build_graph(llm=MagicMock(), http=MagicMock(), parser=MagicMock())
    state = _make_minimal_state("S1")
    result = await graph.nodes["writer"].ainvoke(state)

    fb = result["feedback"]
    assert fb.issues[0].agent == "writer"
    assert fb.issues[0].field == "writer_runtime"
    assert result["retry_count"] == 1


@pytest.mark.asyncio
async def test_writer_node_routes_to_end_on_unrecoverable_error(monkeypatch):
    """[D3 review C1] writer raise WriterRouteToEnd → feedback.passed=True 强制结束图，retry 不增。"""
    from src.agents.writer_orchestrator import WriterRouteToEnd

    async def _raise(*args, **kwargs):
        raise WriterRouteToEnd(
            "writer LLM 调用超限 13 次（上限 12），疑似无限重试"
        )

    monkeypatch.setattr(
        "src.agents.writer_orchestrator.WriterOrchestrator.write",
        _raise,
    )

    graph, _ = build_graph(llm=MagicMock(), http=MagicMock(), parser=MagicMock())
    state = _make_minimal_state("S1")
    result = await graph.nodes["writer"].ainvoke(state)

    fb = result["feedback"]
    # 关键：passed=True 让 should_continue 走 end 分支
    assert fb.passed is True
    assert fb.issues[0].agent == "writer"
    assert fb.issues[0].field == "writer_unrecoverable"
    assert fb.issues[0].severity == "critical"
    # 不可恢复错误不应增加 retry_count（直接结束）
    assert "retry_count" not in result


@pytest.mark.asyncio
async def test_writer_node_routes_to_collector_on_url_rejection(monkeypatch):
    """[D3 review C1] WriterRouteToCollector 即使 message 不含旧关键词也能正确路由（不依赖子串匹配）。"""
    from src.agents.writer_orchestrator import WriterRouteToCollector

    async def _raise(*args, **kwargs):
        # 故意不含旧的「回 collector」中文措辞，证明 isinstance 路由不再依赖文本
        raise WriterRouteToCollector("URL whitelist rejected all sources")

    monkeypatch.setattr(
        "src.agents.writer_orchestrator.WriterOrchestrator.write",
        _raise,
    )

    graph, _ = build_graph(llm=MagicMock(), http=MagicMock(), parser=MagicMock())
    state = _make_minimal_state("S1")
    result = await graph.nodes["writer"].ainvoke(state)

    fb = result["feedback"]
    assert fb.passed is False
    assert fb.issues[0].agent == "collector"
    assert result["retry_count"] == 1


@pytest.mark.asyncio
async def test_writer_node_validation_error_routes_to_writer(monkeypatch):
    """非 RuntimeError（如 ValidationError）→ feedback agent=writer + field=writer_validation。"""
    async def _raise(*args, **kwargs):
        raise ValueError("pretend pydantic validation error")

    monkeypatch.setattr(
        "src.agents.writer_orchestrator.WriterOrchestrator.write",
        _raise,
    )

    graph, _ = build_graph(llm=MagicMock(), http=MagicMock(), parser=MagicMock())
    state = _make_minimal_state("S1")
    result = await graph.nodes["writer"].ainvoke(state)

    fb = result["feedback"]
    assert fb.issues[0].agent == "writer"
    assert fb.issues[0].field == "writer_validation"
    assert result["retry_count"] == 1


@pytest.mark.asyncio
async def test_writer_node_skips_when_analyzer_failed(monkeypatch):
    """[fix12 prove-it] analyzer 抛错时 state 不含 analysis 但带 feedback agent=analyzer
    → writer 应直接 skip + 透传 feedback，不调 writer.write，避免拿不到 analysis 触发 KeyError。

    现象（trace 20260609-201635-49d605）：
    analyzer 抛 APITimeoutError → state.analysis 缺失 → writer_node 走 writer.write
    时 state['analysis'] KeyError → 兜成 feedback agent=writer，污染反馈闭环
    （应该回 analyzer 重试，结果回 writer 重试）。
    """
    from src.schemas.feedback import FeedbackIssue, RejectionFeedback

    # writer.write 被 spy：如果它被调说明 skip 没生效
    write_called = {"flag": False}

    async def _spy_write(*args, **kwargs):
        write_called["flag"] = True
        raise AssertionError("writer.write 不应在 analyzer 失败时被调")

    monkeypatch.setattr(
        "src.agents.writer_orchestrator.WriterOrchestrator.write",
        _spy_write,
    )

    graph, _ = build_graph(llm=MagicMock(), http=MagicMock(), parser=MagicMock())
    # 构造 analyzer 失败后的 state：feedback 标记 analyzer 失败，analysis 缺失
    analyzer_feedback = RejectionFeedback(
        passed=False,
        issues=[FeedbackIssue(
            severity="critical", agent="analyzer", field="analyzer_validation",
            reason="APITimeoutError",
            suggestion="LLM 超时",
        )],
        retry_count=1, max_retries=2,
    )
    from src.schemas.input import CompetitorBasic, ScenarioInput
    ui = ScenarioInput(
        scenario="S1",
        competitors=[CompetitorBasic(name="ProdA")],
        analysis_context="测试",
        our_product_name="OurProd",
    )
    state = {
        "user_input": ui,
        "profiles": [MagicMock()],
        # 故意不放 analysis 字段
        "feedback": analyzer_feedback,
        "retry_count": 1,
        "max_retries": 2,
    }
    result = await graph.nodes["writer"].ainvoke(state)

    # 1) writer.write 不应被调
    assert write_called["flag"] is False, "analyzer 失败时 writer.write 不应被调"
    # 2) feedback 应透传（仍指向 analyzer，让 should_continue 路由回 analyzer）
    assert result.get("feedback") is not None
    assert result["feedback"].issues[0].agent == "analyzer"


@pytest.mark.asyncio
async def test_writer_node_persists_validation_error_to_trace(monkeypatch):
    """[fix2 prove-it] writer 抛 ValidationError 时落盘完整 errors() 详情到 trace_writer。

    现象（trace 20260609-161001-a2db5b）：
    第 1 次 writer phase 4 ValidationError，但 builder 只把 str(e)[:200] 写到 reason，
    run.log 看不到具体哪个字段错，下次诊断只能猜。修后必须落盘完整 errors()。
    """
    from pydantic import BaseModel, Field, ValidationError

    class _Strict(BaseModel):
        name: str = Field(min_length=10)

    async def _raise_validation(*args, **kwargs):
        try:
            _Strict(name="too short")
        except ValidationError as e:
            raise e

    monkeypatch.setattr(
        "src.agents.writer_orchestrator.WriterOrchestrator.write",
        _raise_validation,
    )

    saved_calls: list[tuple] = []

    class _FakeTraceWriter:
        def save_stage(self, *a, **k): pass
        def save_raw(self, stage, data):
            saved_calls.append((stage, data))

    graph, _ = build_graph(
        llm=MagicMock(), http=MagicMock(), parser=MagicMock(),
        trace_writer=_FakeTraceWriter(),
    )
    state = _make_minimal_state("S1")
    result = await graph.nodes["writer"].ainvoke(state)

    # 1) feedback 路由仍然走 writer_validation
    assert result["feedback"].issues[0].field == "writer_validation"
    # 2) trace_writer 收到 04_writer_error 落盘调用
    assert len(saved_calls) == 1
    stage, err_dict = saved_calls[0]
    assert stage == "04_writer_error"
    assert err_dict["error_type"] == "ValidationError"
    # 3) 完整 errors 列表保留 loc + msg + type
    assert len(err_dict["errors"]) >= 1
    assert err_dict["errors"][0]["loc"] == ["name"]
    assert "at least 10" in err_dict["errors"][0]["msg"]
    # 4) 简短摘要可读
    assert "name:" in err_dict["errors_summary"]


@pytest.mark.asyncio
async def test_writer_node_success_returns_report(monkeypatch):
    """writer 成功返回 report → state.report 写入，无 feedback。"""
    fake_report = MagicMock(name="BaseReport")

    async def _ok(*args, **kwargs):
        return fake_report

    monkeypatch.setattr(
        "src.agents.writer_orchestrator.WriterOrchestrator.write",
        _ok,
    )

    graph, _ = build_graph(llm=MagicMock(), http=MagicMock(), parser=MagicMock())
    state = _make_minimal_state("S1")
    result = await graph.nodes["writer"].ainvoke(state)

    assert result.get("report") is fake_report
    assert "feedback" not in result
    assert result["current_node"] == "writer"


# ========== 5. inspector_node：report=None 时 skip ==========

@pytest.mark.asyncio
async def test_inspector_node_skips_when_report_none(monkeypatch):
    """[v3] writer 抛错时 state.report 未写入 → inspector skip 质检，不调 LLM。"""
    inspect_mock = AsyncMock()
    monkeypatch.setattr(
        "src.agents.inspector.InspectorAgent.inspect",
        inspect_mock,
    )

    graph, _ = build_graph(llm=MagicMock(), http=MagicMock(), parser=MagicMock())
    state = _make_minimal_state("S1")
    # 不放 report，模拟 writer 抛错后的 state
    result = await graph.nodes["inspector"].ainvoke(state)

    inspect_mock.assert_not_called()
    assert result["current_node"] == "inspector"
    assert "feedback" not in result


@pytest.mark.asyncio
async def test_inspector_node_increments_retry_when_rejected(monkeypatch):
    """[06-09 修复] inspector 打回（passed=False）时 retry_count +1，否则死循环。"""
    from src.schemas.feedback import FeedbackIssue, RejectionFeedback

    fb = RejectionFeedback(
        passed=False,
        issues=[FeedbackIssue(agent="writer", field="x", severity="major", reason="r")],
        retry_count=1, max_retries=2,
    )
    monkeypatch.setattr(
        "src.agents.inspector.InspectorAgent.inspect",
        AsyncMock(return_value=fb),
    )

    graph, _ = build_graph(llm=MagicMock(), http=MagicMock(), parser=MagicMock())
    state = _make_minimal_state("S1")
    state["report"] = MagicMock()
    state["retry_count"] = 1
    result = await graph.nodes["inspector"].ainvoke(state)

    assert result["retry_count"] == 2  # 从 1 → 2


@pytest.mark.asyncio
async def test_inspector_node_keeps_retry_when_passed(monkeypatch):
    """inspector 通过（passed=True）时 retry_count 不增。"""
    from src.schemas.feedback import RejectionFeedback

    fb = RejectionFeedback(passed=True, issues=[], retry_count=1, max_retries=2)
    monkeypatch.setattr(
        "src.agents.inspector.InspectorAgent.inspect",
        AsyncMock(return_value=fb),
    )

    graph, _ = build_graph(llm=MagicMock(), http=MagicMock(), parser=MagicMock())
    state = _make_minimal_state("S1")
    state["report"] = MagicMock()
    state["retry_count"] = 1
    result = await graph.nodes["inspector"].ainvoke(state)

    assert result["retry_count"] == 1


@pytest.mark.asyncio
async def test_analyzer_node_catches_exception_and_injects_feedback(monkeypatch):
    """[06-09 修复] analyzer 抛 ValueError 时 graph 不应崩溃，注入 feedback 走异常路由。"""
    monkeypatch.setattr(
        "src.agents.analyzer.AnalyzerAgent.analyze",
        AsyncMock(side_effect=ValueError("LLM output validation failed")),
    )

    graph, _ = build_graph(llm=MagicMock(), http=MagicMock(), parser=MagicMock())
    state = _make_minimal_state("S1")
    result = await graph.nodes["analyzer"].ainvoke(state)

    assert "feedback" in result
    assert result["feedback"].passed is False
    assert result["feedback"].issues[0].agent == "analyzer"
    assert result["retry_count"] == 1  # 0 → 1


# ========== writer_node 基础设施错误不消耗 retry ==========

@pytest.mark.asyncio
async def test_writer_node_timeout_does_not_increment_retry():
    """APITimeoutError 等基础设施错误不应递增 retry_count。"""
    from httpx import ConnectTimeout
    from src.schemas.input import ScenarioInput, CompetitorBasic
    from src.schemas.profile import CompetitorProfile, BasicInfo, Classification, ProfileMetadata

    mock_llm = MagicMock()
    # phase 1 outline 调用时抛 timeout
    mock_llm.call_json = AsyncMock(side_effect=ConnectTimeout("timeout"))

    graph, _ = build_graph(llm=mock_llm, http=MagicMock(), parser=MagicMock())

    profile = CompetitorProfile(
        classification=Classification(competitor_type="核心竞品", reason="test"),
        basic_info=BasicInfo(name="TestComp", company=""),
        metadata=ProfileMetadata(
            collected_at="2026-06-22T00:00:00",
            data_sources=["https://example.com/a"],
            completeness_score=0.7,
            pipeline_trace=[],
        ),
    )

    state = {
        "user_input": ScenarioInput(
            scenario="S1",
            competitors=[CompetitorBasic(name="TestComp")],
            analysis_context="测试",
            our_product_name="MyProduct",
        ),
        "analysis": MagicMock(),
        "profiles": [profile],
        "retry_count": 0,
        "max_retries": 2,
        "trace_id": "test-timeout",
    }

    result = await graph.nodes["writer"].ainvoke(state)

    assert "feedback" in result
    # 基础设施错误不应递增 retry_count
    assert result["retry_count"] == 0, f"timeout 不应递增 retry_count，实际值={result['retry_count']}"
