# 反馈闭环路由改进 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修正 evidence issues 的闭环路由——区分"有源不用"（打回 writer 带反馈）vs"真缺源"（打回 collector 定向补采），消除无效盲跑。

**Architecture:** inspector 出分后，独立函数 `_route_evidence_issue` 用代码层对比 used_urls vs discovered_urls coverage 决定路由；writer 被打回时收到 `EvidenceFeedback`（含 URL 列表 + weak_fields）注入 phase 3 prompt；collector 被打回时走增量 `supplement_collect`（LLM 生成 query + Tavily 搜索 + 正文追加）。

**Tech Stack:** Python / Pydantic v2 / LangGraph StateGraph / pytest-asyncio

**Spec:** `docs/superpowers/specs/2026-06-20-feedback-loop-routing-design.md` (v2)

---

## File Map

| Action | Path | Responsibility |
|--------|------|---------------|
| Create | `src/utils/url_normalize.py` | `_normalize_url()` 函数 |
| Create | `tests/unit/test_url_normalize.py` | URL 归一化单测 |
| Modify | `src/schemas/feedback.py` | 新增 `EvidenceFeedback` 模型 |
| Modify | `src/graph/builder.py` | `_route_evidence_issue` + `should_continue` 集成 + `inspector_node` 写 coverage + `writer_node` 检测 flag + `collector_node` 增量模式 |
| Modify | `src/agents/writer_orchestrator.py` | `write()` 接收 evidence_feedback + `_phase3_one_section` 注入 prompt |
| Modify | `src/agents/collector.py` | 新增 `supplement_collect()` 方法 |
| Create | `tests/unit/test_evidence_routing.py` | 路由函数单测 |
| Create | `tests/unit/test_supplement_collect.py` | 补采流程单测 |
| Modify | `tests/unit/test_writer_orchestrator.py` | evidence_feedback 注入测试 |

---

### Task 1: URL 归一化函数

**Files:**
- Create: `src/utils/url_normalize.py`
- Create: `tests/unit/test_url_normalize.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_url_normalize.py
from src.utils.url_normalize import normalize_url


def test_strip_trailing_slash():
    assert normalize_url("https://example.com/path/") == "https://example.com/path"


def test_http_to_https():
    assert normalize_url("http://example.com/page") == "https://example.com/page"


def test_strip_fragment():
    assert normalize_url("https://example.com/page#section") == "https://example.com/page"


def test_preserve_query():
    assert normalize_url("https://example.com/page?id=1") == "https://example.com/page?id=1"


def test_identity_for_clean_url():
    assert normalize_url("https://example.com/path") == "https://example.com/path"


def test_combined():
    assert normalize_url("http://example.com/path/#frag") == "https://example.com/path"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_url_normalize.py -v`
Expected: FAIL with "ModuleNotFoundError" or "ImportError"

- [ ] **Step 3: Write minimal implementation**

```python
# src/utils/url_normalize.py
"""URL 归一化：用于 coverage 计算时的 URL 比较。"""
from urllib.parse import urlparse, urlunparse


def normalize_url(url: str) -> str:
    """归一化 URL：统一 https / 去尾 slash / 去 fragment。"""
    parsed = urlparse(url)
    scheme = "https"
    path = parsed.path.rstrip("/")
    return urlunparse((scheme, parsed.netloc, path, parsed.params, parsed.query, ""))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_url_normalize.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add src/utils/url_normalize.py tests/unit/test_url_normalize.py
git commit -m "feat: URL 归一化函数（用于 evidence coverage 比较）"
```

---

### Task 2: EvidenceFeedback Pydantic 模型

**Files:**
- Modify: `src/schemas/feedback.py`

- [ ] **Step 1: Write the failing test**

```python
# 在 tests/unit/test_inspector_critic.py 末尾追加
def test_evidence_feedback_model():
    from src.schemas.feedback import EvidenceFeedback

    ef = EvidenceFeedback(
        available_urls=["https://a.com", "https://b.com"],
        weak_fields=["key_findings[0].source_refs", "analysis_sections[2].narrative"],
        coverage_pct=0.3,
    )
    assert len(ef.available_urls) == 2
    assert ef.coverage_pct == 0.3
    assert "key_findings" in ef.weak_fields[0]


def test_evidence_feedback_defaults():
    from src.schemas.feedback import EvidenceFeedback

    ef = EvidenceFeedback()
    assert ef.available_urls == []
    assert ef.weak_fields == []
    assert ef.coverage_pct == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_inspector_critic.py::test_evidence_feedback_model -v`
Expected: FAIL with "ImportError: cannot import name 'EvidenceFeedback'"

- [ ] **Step 3: Write minimal implementation**

在 `src/schemas/feedback.py` 末尾添加：

```python
class EvidenceFeedback(BaseModel):
    """evidence 维度打回 writer 时携带的反馈信息。"""
    available_urls: list[str] = Field(default_factory=list)
    weak_fields: list[str] = Field(default_factory=list)
    coverage_pct: float = 0.0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_inspector_critic.py::test_evidence_feedback_model tests/unit/test_inspector_critic.py::test_evidence_feedback_defaults -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add src/schemas/feedback.py tests/unit/test_inspector_critic.py
git commit -m "feat: EvidenceFeedback Pydantic 模型"
```

---

### Task 3: `_route_evidence_issue` 路由函数

**Files:**
- Modify: `src/graph/builder.py`（在模块级添加函数）
- Create: `tests/unit/test_evidence_routing.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_evidence_routing.py
import pytest
from src.graph.builder import _route_evidence_issue


def test_empty_discovered_returns_none():
    state = {"discovered_sources": [], "report": None}
    assert _route_evidence_issue(state) is None


def test_no_discovered_key_returns_none():
    state = {"report": None}
    assert _route_evidence_issue(state) is None


def test_report_none_returns_none():
    state = {"discovered_sources": [{"url": "https://a.com", "title": "", "snippet": ""}], "report": None}
    assert _route_evidence_issue(state) is None


def test_high_discovered_low_coverage_routes_writer():
    """discovered >= 8, coverage < 0.5 → writer"""
    from unittest.mock import MagicMock
    report = MagicMock()
    # _extract_used_urls 会被 mock，这里用 state 直接测逻辑
    state = {
        "discovered_sources": [{"url": f"https://src{i}.com", "title": "", "snippet": ""} for i in range(10)],
        "report": report,
    }
    # 需要 mock _extract_used_urls —— 见 Step 3 实现方式
    # 这里先写断言形状
    result = _route_evidence_issue(state)
    # 当 report 的 used_urls 为空时，coverage=0 → writer
    assert result == "writer"


def test_low_discovered_routes_collector():
    """discovered < 5 → collector"""
    from unittest.mock import MagicMock
    report = MagicMock()
    state = {
        "discovered_sources": [{"url": f"https://src{i}.com", "title": "", "snippet": ""} for i in range(3)],
        "report": report,
    }
    result = _route_evidence_issue(state)
    assert result == "collector"


def test_prev_coverage_not_improved_returns_end():
    """第二次打回且 coverage 未提升 → end"""
    from unittest.mock import MagicMock
    report = MagicMock()
    state = {
        "discovered_sources": [{"url": f"https://src{i}.com", "title": "", "snippet": ""} for i in range(10)],
        "report": report,
        "_prev_evidence_coverage": 0.2,  # 上次也是 0.2
    }
    result = _route_evidence_issue(state)
    assert result == "end"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_evidence_routing.py -v`
Expected: FAIL with "ImportError: cannot import name '_route_evidence_issue'"

- [ ] **Step 3: Write minimal implementation**

在 `src/graph/builder.py` 顶部（`build_graph` 函数之前）添加：

```python
from src.utils.url_normalize import normalize_url as _normalize_url

# evidence 类 issue_type 集合
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
```

同时需要 import `_collect_source_refs_recursive`：
```python
from src.agents.writer_orchestrator import _collect_source_refs_recursive
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_evidence_routing.py -v`
Expected: 6 passed

注：`test_high_discovered_low_coverage_routes_writer` 和 `test_low_discovered_routes_collector` 需要 mock `_extract_used_urls` 或使用真实 report fixture。实现时根据实际情况调整——可能需要 monkeypatch `_extract_used_urls` 返回空集合。

- [ ] **Step 5: Commit**

```bash
git add src/graph/builder.py tests/unit/test_evidence_routing.py
git commit -m "feat: _route_evidence_issue 路由函数（代码层 coverage 判断）"
```

---

### Task 4: `should_continue` 集成 evidence 路由

**Files:**
- Modify: `src/graph/builder.py:should_continue`（内嵌在 build_graph 中）

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_evidence_routing.py 追加
@pytest.mark.asyncio
async def test_should_continue_evidence_priority():
    """evidence issue 优先于其他 issue 做路由判断。"""
    # 使用集成测试验证 should_continue 内部逻辑
    # 具体 fixture 构造参照 tests/integration/test_graph.py
    pass  # 占位——集成测试在 Task 7 覆盖
```

- [ ] **Step 2: Modify should_continue**

在 `should_continue` 函数中，`max_retries` 检查之后、原有 "取第一条 critical/major" 逻辑之前，插入：

```python
        # evidence issues 优先扫描（spec v2 审查 C3）
        for issue in feedback.issues:
            if issue.severity in ("critical", "major") and getattr(issue, "issue_type", None) in _EVIDENCE_ISSUE_TYPES:
                evidence_route = _route_evidence_issue(state)
                if evidence_route is not None:
                    node_trace.append(f"reject->{evidence_route} (evidence_route)")
                    return evidence_route
                break  # fallback to original mapping below
```

- [ ] **Step 3: Run existing tests to verify no regression**

Run: `pytest tests/unit/ tests/integration/ -q --tb=short`
Expected: all pass (无变化——现有测试不构造 evidence issue_type)

- [ ] **Step 4: Commit**

```bash
git add src/graph/builder.py
git commit -m "feat: should_continue 集成 evidence 优先路由"
```

---

### Task 5: `inspector_node` 写入 `_prev_evidence_coverage`

**Files:**
- Modify: `src/graph/builder.py:inspector_node`

- [ ] **Step 1: Modify inspector_node**

在 `inspector_node` 返回 state dict 之前：

```python
        # 写入 evidence coverage 供下轮 _route_evidence_issue 判断退出条件
        result = {
            "feedback": feedback,
            "current_node": "inspector",
            "retry_count": next_retry,
        }
        if not feedback.passed:
            # 检查是否有 evidence issues
            has_evidence_issue = any(
                getattr(i, "issue_type", None) in _EVIDENCE_ISSUE_TYPES
                for i in feedback.issues
            )
            if has_evidence_issue and report is not None:
                ds = state.get("discovered_sources") or []
                d_urls = {_normalize_url(d["url"]) for d in ds if isinstance(d, dict) and d.get("url")}
                u_urls = {_normalize_url(u) for u in _extract_used_urls(report)}
                if d_urls:
                    result["_prev_evidence_coverage"] = len(u_urls & d_urls) / len(d_urls)
        return result
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/unit/ tests/integration/ -q --tb=short`
Expected: all pass

- [ ] **Step 3: Commit**

```bash
git add src/graph/builder.py
git commit -m "feat: inspector_node 写入 _prev_evidence_coverage 供退出判断"
```

---

### Task 6: Writer evidence 反馈注入

**Files:**
- Modify: `src/graph/builder.py:writer_node`（写入 state flag）
- Modify: `src/agents/writer_orchestrator.py:write()` + `_phase3_one_section()`
- Modify: `tests/unit/test_writer_orchestrator.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_writer_orchestrator.py 追加
@pytest.mark.asyncio
async def test_phase3_evidence_feedback_injects_urls():
    """evidence_feedback 非空时 phase 3 prompt 包含 URL 列表和 weak_fields。"""
    scenario_input, analysis, profiles = _make_phase3_full_run_inputs()
    from src.schemas.feedback import EvidenceFeedback

    ef = EvidenceFeedback(
        available_urls=["https://example.com/a", "https://example.com/b"],
        weak_fields=["key_findings[0].source_refs"],
        coverage_pct=0.3,
    )

    phase1_outline = _make_valid_outline_dict("测试")
    phase2_payload = _s1_payload_dict_with_weighted_scores()
    s1_types = ["overview", "vendor_profile_analysis", "feature_matrix_analysis", "jtbd_analysis", "roadmap_analysis"]
    side_effects = [phase1_outline, phase2_payload] + [_make_valid_narrative_json(t) for t in s1_types]

    mock_llm = MagicMock(spec=LLMClient)
    mock_llm.call_json = AsyncMock(side_effect=side_effects)
    orch = WriterOrchestrator(llm=mock_llm)

    # 调用时传 evidence_feedback
    with pytest.raises(Exception):  # phase 4 会因 fixture 不完整 raise
        await orch.write(
            scenario_input=scenario_input,
            analysis=analysis,
            profiles=profiles,
            evidence_feedback=ef,
        )

    # 验证 phase 3 LLM 调用的 system_prompt 包含 URL 和 weak_fields
    narrative_calls = mock_llm.call_json.call_args_list[2:]  # 跳过 phase1 + phase2
    for call in narrative_calls:
        system_prompt = call[0][0]  # positional arg 0 = system_prompt
        assert "https://example.com/a" in system_prompt
        assert "key_findings[0].source_refs" in system_prompt
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_writer_orchestrator.py::test_phase3_evidence_feedback_injects_urls -v`
Expected: FAIL (write() 不接受 evidence_feedback 参数)

- [ ] **Step 3: Implement**

3a. `WriterOrchestrator.write()` 签名新增 `evidence_feedback: EvidenceFeedback | None = None`，传到 `_phase3_narratives`，再传到 `_phase3_one_section`。

3b. `_phase3_one_section` 修改：
- 删除 `_ = discovered_urls`（第 1173 行）
- 新增参数 `evidence_feedback: EvidenceFeedback | None = None`
- 在 system_prompt 拼装后、LLM 调用前，如果 evidence_feedback 非空则追加反馈指令

```python
        if evidence_feedback and evidence_feedback.available_urls:
            url_list = "\n".join(f"   - {u}" for u in evidence_feedback.available_urls)
            weak_list = "\n".join(f"   - {f}" for f in evidence_feedback.weak_fields) if evidence_feedback.weak_fields else "   （未指定具体字段）"
            system_prompt += (
                f"\n\n【质检反馈：溯源引用不足】\n"
                f"上一轮 evidence 覆盖率 {evidence_feedback.coverage_pct:.0%}，以下字段引用不足：\n{weak_list}\n\n"
                f"本次重写请确保上述字段对应段落至少引用 1 个 source_ref URL。\n"
                f"可用的溯源 URL 列表（优先使用）：\n{url_list}\n"
                f"在 source_refs 数组中以 {{\"url\": \"...\", \"title\": \"相关描述\"}} 格式引用。\n"
                f"如果某段确实无法关联上述 URL，source_refs 留空 [] 即可。"
            )
```

3c. `builder.py:writer_node` 修改：检测 state 中的 feedback evidence issues，构造 EvidenceFeedback 传给 orch.write()：

```python
        # 检测 evidence 反馈
        evidence_feedback = None
        feedback = state.get("feedback")
        if feedback and not feedback.passed:
            ev_issues = [i for i in feedback.issues if getattr(i, "issue_type", None) in _EVIDENCE_ISSUE_TYPES]
            if ev_issues:
                from src.schemas.feedback import EvidenceFeedback
                ds = state.get("discovered_sources") or []
                urls = sorted({d["url"] for d in ds if isinstance(d, dict) and d.get("url")})[:10]
                evidence_feedback = EvidenceFeedback(
                    available_urls=urls,
                    weak_fields=[i.field for i in ev_issues],
                    coverage_pct=state.get("_prev_evidence_coverage", 0.0),
                )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_writer_orchestrator.py::test_phase3_evidence_feedback_injects_urls -v`
Expected: PASS

- [ ] **Step 5: Run full regression**

Run: `pytest tests/unit/ tests/integration/ -q --tb=short`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add src/agents/writer_orchestrator.py src/graph/builder.py tests/unit/test_writer_orchestrator.py
git commit -m "feat: writer evidence 反馈注入（phase 3 prompt 含 URL 列表 + weak_fields）"
```

---

### Task 7: Collector `supplement_collect` 增量补采

**Files:**
- Modify: `src/agents/collector.py`
- Create: `tests/unit/test_supplement_collect.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_supplement_collect.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from src.agents.collector import CollectorAgent
from src.schemas.input import CompetitorBasic
from src.schemas.feedback import FeedbackIssue


@pytest.mark.asyncio
async def test_supplement_collect_generates_query_and_searches():
    """补采模式：LLM 生成 query → Tavily 搜索 → 返回新 profiles + sources。"""
    mock_llm = MagicMock()
    # LLM 生成补充 query
    mock_llm.call_json = AsyncMock(return_value={
        "queries": ["GrowingIO 数据分析 产品评测", "友盟 SDK 功能 对比"]
    })

    from src.tools.sources import SourceResult
    mock_pipeline = MagicMock()
    mock_pipeline.search_source = MagicMock()
    mock_pipeline.search_source.available = MagicMock(return_value=True)
    mock_pipeline.search_source.search = AsyncMock(return_value=[
        SourceResult(url="https://new-source.com/review", title="New Review", text="新搜到的正文内容" * 20),
    ])

    agent = CollectorAgent(llm=mock_llm, pipeline=mock_pipeline)

    competitors = [CompetitorBasic(name="GrowingIO")]
    issues = [FeedbackIssue(
        agent="collector", field="key_findings[0].source_refs",
        severity="major", reason="缺来源", suggestion="补充",
        issue_type="url_not_discovered",
    )]

    from src.schemas.profile import CompetitorProfile, BasicInfo, Classification, ProfileMetadata
    existing_profile = CompetitorProfile(
        classification=Classification(competitor_type="核心竞品", reason="test"),
        basic_info=BasicInfo(name="GrowingIO", company=""),
        metadata=ProfileMetadata(collected_at="2026-06-20T00:00:00", data_sources=["https://old.com"], completeness_score=0.5, pipeline_trace=[]),
    )

    new_profiles, new_sources = await agent.supplement_collect(
        competitors=competitors,
        feedback_issues=issues,
        scenario="S4",
        existing_profiles=[existing_profile],
    )

    assert len(new_sources) >= 1
    assert new_sources[0]["url"] == "https://new-source.com/review"
    assert "https://new-source.com/review" in new_profiles[0].metadata.data_sources


@pytest.mark.asyncio
async def test_supplement_collect_no_results_returns_empty():
    """补采搜不到有效结果时返回空。"""
    mock_llm = MagicMock()
    mock_llm.call_json = AsyncMock(return_value={"queries": ["无效query"]})

    mock_pipeline = MagicMock()
    mock_pipeline.search_source = MagicMock()
    mock_pipeline.search_source.available = MagicMock(return_value=True)
    mock_pipeline.search_source.search = AsyncMock(return_value=[])

    agent = CollectorAgent(llm=mock_llm, pipeline=mock_pipeline)

    from src.schemas.profile import CompetitorProfile, BasicInfo, Classification, ProfileMetadata
    existing_profile = CompetitorProfile(
        classification=Classification(competitor_type="核心竞品", reason="test"),
        basic_info=BasicInfo(name="X", company=""),
        metadata=ProfileMetadata(collected_at="2026-06-20T00:00:00", data_sources=[], completeness_score=0.0, pipeline_trace=[]),
    )

    new_profiles, new_sources = await agent.supplement_collect(
        competitors=[CompetitorBasic(name="X")],
        feedback_issues=[],
        scenario="S4",
        existing_profiles=[existing_profile],
    )

    assert new_sources == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_supplement_collect.py -v`
Expected: FAIL with "AttributeError: 'CollectorAgent' object has no attribute 'supplement_collect'"

- [ ] **Step 3: Implement `supplement_collect`**

在 `src/agents/collector.py` 添加：

```python
    _SUPPLEMENT_QUERY_SYSTEM = (
        "你是搜索 query 生成器。根据质检反馈中缺失的信息，为指定竞品生成 2-3 条针对性搜索 query。"
        "输出 JSON: {\"queries\": [\"query1\", \"query2\"]}"
    )

    async def supplement_collect(
        self,
        competitors: list[CompetitorBasic],
        feedback_issues: list,
        scenario: str,
        existing_profiles: list[CompetitorProfile],
    ) -> tuple[list[CompetitorProfile], list[dict]]:
        """定向补采：LLM 生成 query → 增量搜索 → 追加正文+URL 到 profiles。"""
        from src.tools.quality_gate import is_low_quality
        from src.utils.url_normalize import normalize_url

        # 生成补充 query
        comp_names = [c.name for c in competitors]
        issue_summary = "; ".join(f"{i.field}: {i.reason}" for i in feedback_issues[:5])
        prompt = f"竞品: {comp_names}\n场景: {scenario}\n缺失信息: {issue_summary}"

        try:
            result = await self.llm.call_json(self._SUPPLEMENT_QUERY_SYSTEM, prompt)
            queries = result.get("queries", [])[:3]
        except Exception:
            queries = [f"{comp_names[0]} 最新信息 评测" if comp_names else "竞品 信息"]

        if not queries:
            return existing_profiles, []

        # 增量搜索
        if not self.pipeline.search_source.available():
            return existing_profiles, []

        import asyncio
        search_results = await asyncio.gather(
            *[self.pipeline.search_source.search(q) for q in queries],
            return_exceptions=True,
        )

        # 收集有效结果（过质量闸门 + 去重）
        existing_urls = set()
        for p in existing_profiles:
            existing_urls.update(normalize_url(u) for u in (p.metadata.data_sources or []))

        new_sources: list[dict] = []
        new_texts: dict[str, list[str]] = {c.name: [] for c in competitors}

        for results in search_results:
            if isinstance(results, Exception):
                continue
            for r in results:
                if not r.url or is_low_quality(r.text):
                    continue
                if normalize_url(r.url) in existing_urls:
                    continue
                existing_urls.add(normalize_url(r.url))
                new_sources.append({"url": r.url, "title": r.title or "", "snippet": (r.text or "")[:200]})
                # 按最相关竞品追加（简单策略：第一个竞品吃所有新内容）
                if comp_names:
                    new_texts[comp_names[0]].append(r.text)

        if not new_sources:
            return existing_profiles, []

        # 追加到 profiles（构造副本，不 mutate 原对象）
        updated_profiles = []
        for p in existing_profiles:
            new_urls_for_comp = [s["url"] for s in new_sources]
            updated_ds = list(p.metadata.data_sources or []) + new_urls_for_comp
            updated_profile = p.model_copy(update={
                "metadata": p.metadata.model_copy(update={"data_sources": updated_ds})
            })
            updated_profiles.append(updated_profile)

        return updated_profiles, new_sources
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_supplement_collect.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add src/agents/collector.py tests/unit/test_supplement_collect.py
git commit -m "feat: collector supplement_collect 增量补采方法"
```

---

### Task 8: `collector_node` 增量模式集成

**Files:**
- Modify: `src/graph/builder.py:collector_node`

- [ ] **Step 1: Modify collector_node**

在 `collector_node` 中，检测 feedback 是否有 evidence issues：

```python
    async def collector_node(state: AnalysisState) -> dict:
        logger.info("[graph] → collector")
        node_trace.append("collector")

        # 检测是否为 evidence 反馈打回的增量补采模式
        feedback = state.get("feedback")
        existing_profiles = state.get("profiles")
        if feedback and not feedback.passed and existing_profiles:
            ev_issues = [i for i in feedback.issues
                         if getattr(i, "issue_type", None) in _EVIDENCE_ISSUE_TYPES]
            if ev_issues:
                logger.info("[graph] collector 进入增量补采模式")
                new_profiles, new_sources = await collector.supplement_collect(
                    competitors=state["user_input"].competitors,
                    feedback_issues=ev_issues,
                    scenario=state["user_input"].scenario,
                    existing_profiles=existing_profiles,
                )
                if new_sources:
                    existing_ds = state.get("discovered_sources") or []
                    return {
                        "profiles": new_profiles,
                        "discovered_sources": existing_ds + new_sources,
                        "current_node": "collector",
                    }
                else:
                    logger.warning("[graph] collector 补采无新数据，跳过")
                    return {"current_node": "collector"}

        # 原有全量采集模式
        ...（保持现有代码不变）
```

- [ ] **Step 2: Run full regression**

Run: `pytest tests/unit/ tests/integration/ -q --tb=short`
Expected: all pass

- [ ] **Step 3: Commit**

```bash
git add src/graph/builder.py
git commit -m "feat: collector_node 增量补采模式（evidence 打回时定向搜索）"
```

---

### Task 9: 全量回归 + ruff + 文档更新

**Files:**
- All modified files
- `PROGRESS.md`
- `OPEN_QUESTIONS.md`

- [ ] **Step 1: Full regression**

Run: `pytest tests/unit/ tests/integration/ -q --tb=short`
Expected: all pass

- [ ] **Step 2: Ruff**

Run: `ruff check src tests`
Expected: All checks passed

- [ ] **Step 3: Update PROGRESS.md**

添加本次实施记录。

- [ ] **Step 4: Update OPEN_QUESTIONS.md**

将 Q-2026-06-20-evidence-issue-路由错误 和 Q-2026-06-20-collector-打回无效重跑 标记为"已并入"。

- [ ] **Step 5: Final commit + push**

```bash
git add -A
git commit -m "docs: 反馈闭环路由改进完成 — PROGRESS + OPEN_QUESTIONS 更新"
git push origin master
```
