# LLM-as-Critic 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 inspector 的 quality_score 三项加权（coverage/confidence/pass_rate）替换为 LLM-as-critic 4 维 rubric 评分（evidence/specificity/coherence/actionability），作为字数约束渐进退役的前置基础设施。

**Architecture:** Critic 作为 inspector 内部子模块嵌入（路线 A），单次 LLM 调用同时输出 rubric 评分 + 关联 issues；CoT 推理改结构化 bullet list；失败降级 retry 1 次后走 critic_failed terminal 路由（不消耗 max_retries）；删除 v3-R17 placeholder cap 机制。

**Tech Stack:** Python 3.14 / Pydantic v2 / OpenAI SDK / pytest / LangGraph

**Spec:** `docs/superpowers/specs/2026-06-19-llm-as-critic-design.md` v4

---

## 文件结构

| 文件 | 操作 | 职责 |
|------|------|------|
| `src/schemas/feedback.py` | 修改 | 加 CriticScores BaseModel + FeedbackIssue.dimension/issue_type 字段 |
| `src/schemas/report.py` | 修改 | ReportMetadata 加 critic_scores/score_source/critic_prompt_version |
| `src/agents/quality_score.py` | 重写 | 删旧三函数；新增 calc_critic_score(scores) |
| `src/agents/prompts/inspector/__init__.py` | 新建 | 模块包 |
| `src/agents/prompts/inspector/critic.py` | 新建 | CRITIC_SYSTEM prompt + CRITIC_PROMPT_VERSION |
| `src/agents/inspector.py` | 大改 | 删 7 项旧组件；新增 7 项新组件（critic 子函数 + 主流程改造） |
| `src/graph/state.py` | 修改 | AnalysisState 加 discovered_sources 字段 |
| `src/graph/builder.py` | 修改 | collector_node 写 sources / inspector_node 传 sources / _should_continue 加 agent="end" 特判 |
| `src/agents/collector.py` | 修改 | 保存 Tavily search snippet 到 discovered_sources |
| `src/agents/prompts/__init__.py` | 修改 | 删 INSPECTOR_SYSTEM 常量 |
| `pyproject.toml` | 修改 | 加 pytest marker `eval` 配置 |
| `tests/unit/test_inspector_critic.py` | 新建 | critic 单元 + 集成测试（mock LLM） |
| `tests/eval/__init__.py` | 新建 | eval 测试包 |
| `tests/eval/test_critic_judgment.py` | 新建 | 5 条反例集 fixture + critic 判断力测试（手动跑） |

---

## 任务依赖顺序

按 TDD 自底向上：
- Task 1-3：Schema 层（CriticScores / FeedbackIssue 扩展 / ReportMetadata 扩展）
- Task 4：calc_critic_score 重写（quality_score.py）
- Task 5：critic prompt 落盘
- Task 6-10：inspector 子函数（_score_to_severity / _build_limited_pairs / _sample_items_deterministic / _build_critic_inputs / _safe_minimal_fallback / _map_issue_type_to_agent）
- Task 11：_critic_check 主流程
- Task 12：删除 inspector 旧组件 + 重写 inspect() 主入口
- Task 13：graph state + builder 改造
- Task 14：collector 保存 snippet
- Task 15：清理旧 INSPECTOR_SYSTEM
- Task 16：pyproject.toml 加 eval marker
- Task 17：反例集 eval 测试
- Task 18：影响面 grep 验收脚本
- Task 19：全量回归 + lint + commit

---

## Task 1: 新增 CriticScores schema + FeedbackIssue 扩展

**Files:**
- Modify: `src/schemas/feedback.py`
- Test: `tests/unit/test_inspector_critic.py` (新建)

- [ ] **Step 1: 写失败测试 — CriticScores 基础校验**

创建 `tests/unit/test_inspector_critic.py`：

```python
"""LLM-as-critic 单元 + 集成测试。

测试三层（spec v4）：
1. 单元测试（机制正确性，CI required）
2. 集成测试（端到端 mock LLM，CI required）
3. 反例集 eval（手动 pytest -m eval，不进 CI）—— 见 tests/eval/
"""
import pytest
from pydantic import ValidationError


def test_critic_scores_basic_validation():
    """CriticScores 4 维分数 1-4 整数校验。"""
    from src.schemas.feedback import CriticScores

    scores = CriticScores(evidence=4, specificity=3, coherence=2, actionability=1)
    assert scores.evidence == 4
    assert scores.specificity == 3
    assert scores.coherence == 2
    assert scores.actionability == 1
    assert scores.reasoning == {}


def test_critic_scores_rejects_out_of_range():
    """score 不能小于 1 或大于 4。"""
    from src.schemas.feedback import CriticScores

    with pytest.raises(ValidationError):
        CriticScores(evidence=0, specificity=2, coherence=2, actionability=2)
    with pytest.raises(ValidationError):
        CriticScores(evidence=5, specificity=2, coherence=2, actionability=2)


def test_critic_scores_reasoning_is_list_of_str():
    """reasoning 字段是 dict[str, list[str]]，每个维度对应 bullet list。"""
    from src.schemas.feedback import CriticScores

    scores = CriticScores(
        evidence=3, specificity=3, coherence=3, actionability=3,
        reasoning={
            "evidence": ["[Step 1] ...", "[Step 2] ..."],
            "specificity": ["[Step 1] ..."],
        },
    )
    assert scores.reasoning["evidence"] == ["[Step 1] ...", "[Step 2] ..."]


def test_feedback_issue_new_fields_optional():
    """FeedbackIssue 新增 dimension / issue_type 必须 Optional 默认 None（旧 trace 兼容）。"""
    from src.schemas.feedback import FeedbackIssue

    issue = FeedbackIssue(
        agent="writer", field="key_findings[0]", severity="major",
        reason="...", suggestion="...",
    )
    assert issue.dimension is None
    assert issue.issue_type is None


def test_feedback_issue_new_fields_settable():
    """FeedbackIssue 新增字段能正常设置。"""
    from src.schemas.feedback import FeedbackIssue

    issue = FeedbackIssue(
        agent="writer", field="key_findings[0]", severity="major",
        reason="...", suggestion="...",
        dimension="evidence", issue_type="source_irrelevant",
    )
    assert issue.dimension == "evidence"
    assert issue.issue_type == "source_irrelevant"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/unit/test_inspector_critic.py -v`
Expected: 5 个测试都 FAIL（CriticScores import 不到 / FeedbackIssue 没新字段）

- [ ] **Step 3: 修改 src/schemas/feedback.py**

```python
# 末尾追加（feedback.py 不 import report.py，避免循环）

class CriticScores(BaseModel):
    """critic 4 维评分（持久化到 ReportMetadata.critic_scores）

    每维 1-4 整数分；reasoning 是 dict[dim, list[bullet]] 结构化短列表（spec v4-M9）。
    """
    evidence: int = Field(ge=1, le=4)
    specificity: int = Field(ge=1, le=4)
    coherence: int = Field(ge=1, le=4)
    actionability: int = Field(ge=1, le=4)
    reasoning: dict[str, list[str]] = Field(default_factory=dict)
    """{dim: [bullet1, bullet2, ...]}，CoT 推理过程（短 bullet，每条 ≤80 Python len 字符）"""
```

并修改现有 `FeedbackIssue` 加 2 个 Optional 字段：

```python
class FeedbackIssue(BaseModel):
    agent: str
    field: str
    severity: Literal["critical", "major", "minor"]
    reason: str
    suggestion: str
    # v4 新增（Optional 兼容旧 trace 反序列化）
    dimension: Optional[str] = None
    """critic 维度名（"evidence"/"specificity"/"coherence"/"actionability"）
    或 "programmatic" / "critic_failed"——用于去重 + 反馈路由"""
    issue_type: Optional[str] = None
    """枚举: url_not_discovered / source_mismatch / source_irrelevant /
    vague_description / cross_field_contradiction / vague_recommendation /
    critic_failed / programmatic_*"""
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/unit/test_inspector_critic.py -v`
Expected: 5 PASS

- [ ] **Step 5: Commit**

```bash
git add src/schemas/feedback.py tests/unit/test_inspector_critic.py
git commit -m "feat(critic): CriticScores schema + FeedbackIssue 扩展 dimension/issue_type"
```

---

## Task 2: ReportMetadata 扩展 3 个 Optional 字段

**Files:**
- Modify: `src/schemas/report.py`
- Test: `tests/unit/test_inspector_critic.py`（追加）

- [ ] **Step 1: 写失败测试 — 旧 trace 反序列化兼容**

在 `tests/unit/test_inspector_critic.py` 末尾追加：

```python
def test_report_metadata_v4_fields_optional():
    """v4 新增字段必须 Optional 默认 None，旧 v1 trace 反序列化兼容。"""
    from src.schemas.report import ReportMetadata

    # 模拟旧 v1 trace：不含 critic_scores / score_source / critic_prompt_version
    old_metadata_dict = {
        "scenario": "S5",
        "schema_version": "2.0",
        "warnings": [],
        "data_sources": [{
            "url": "https://example.com",
            "title": "test",
            "accessed_at": "2026-06-18",
            "source_type": "other",
            "confidence": "medium",
        }],
    }
    md = ReportMetadata.model_validate(old_metadata_dict)

    # v4 修订（cycle3/C1）：旧 trace 期望统一为 None
    assert md.critic_scores is None
    assert md.score_source is None
    assert md.critic_prompt_version is None


def test_report_metadata_v4_fields_settable():
    """v4 新增字段能正常设置。"""
    from src.schemas.report import ReportMetadata
    from src.schemas.feedback import CriticScores

    md = ReportMetadata.model_validate({
        "scenario": "S5",
        "schema_version": "2.0",
        "warnings": [],
        "data_sources": [{
            "url": "https://example.com", "title": "t",
            "accessed_at": "2026-06-18", "source_type": "other",
            "confidence": "medium",
        }],
        "critic_scores": {
            "evidence": 3, "specificity": 3, "coherence": 3, "actionability": 3,
            "reasoning": {},
        },
        "score_source": "critic",
        "critic_prompt_version": "critic-prompt-v1.0.0",
    })
    assert md.critic_scores.evidence == 3
    assert md.score_source == "critic"
    assert md.critic_prompt_version == "critic-prompt-v1.0.0"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/unit/test_inspector_critic.py::test_report_metadata_v4_fields_optional -v`
Expected: FAIL（字段不存在）

- [ ] **Step 3: 修改 src/schemas/report.py**

在 `ReportMetadata` 类追加 3 个字段（保持 import 顺序：先 import CriticScores from feedback）：

```python
# 在 report.py 顶部 import 区追加（不形成循环：feedback 不 import report）
from src.schemas.feedback import CriticScores

# ReportMetadata 类追加字段
class ReportMetadata(BaseModel):
    # ...现有字段...

    # v4 新增（spec v4 cycle2/C2 + cycle3/C1）：critic 评分相关
    critic_scores: Optional[CriticScores] = None
    """critic 4 维评分；critic 失败降级时为 None"""
    score_source: Optional[Literal["critic", "fallback"]] = None
    """quality_score 的来源；"critic"=critic 真分；"fallback"=critic 失败降级 0.5；
    None=旧 v1 trace（来自旧 coverage/confidence/pass_rate 三项加权）"""
    critic_prompt_version: Optional[str] = None
    """critic prompt 版本（如 "critic-prompt-v1.0.0"），用于历史分数可比"""
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/unit/test_inspector_critic.py -v -k "report_metadata"`
Expected: 2 PASS

- [ ] **Step 5: 跑全量测试确认无回归**

Run: `pytest tests/ -x --tb=short`
Expected: 451 passed（原数）+ 7 新测试 = 458 passed

- [ ] **Step 6: Commit**

```bash
git add src/schemas/report.py tests/unit/test_inspector_critic.py
git commit -m "feat(critic): ReportMetadata 加 critic_scores/score_source/critic_prompt_version 三字段（兼容旧 trace）"
```

---

## Task 3: 旧 trace 反序列化集成测试

**Files:**
- Test: `tests/unit/test_inspector_critic.py`（追加）

- [ ] **Step 1: 写失败测试 — 真实历史 trace 反序列化**

```python
def test_v1_trace_can_be_loaded_with_v4_schema():
    """spec v4 验收 2：runs/20260618-095358-c5ab5c/03_report.json 能用 v4 BaseReport schema 加载。"""
    import json
    from pathlib import Path
    from src.schemas.report import BaseReport

    # 找一个真实历史 trace（v1 schema 落盘的）
    trace_path = Path("runs/20260618-095358-c5ab5c/03_report.json")
    if not trace_path.exists():
        pytest.skip(f"trace fixture 不存在: {trace_path}")

    raw = json.loads(trace_path.read_text(encoding="utf-8"))
    report = BaseReport.model_validate(raw)

    # v4 修订（cycle3/C1）：旧 trace 反序列化后所有 v4 新字段必须为 None
    assert report.metadata.critic_scores is None
    assert report.metadata.score_source is None
    assert report.metadata.critic_prompt_version is None
```

- [ ] **Step 2: 运行测试**

Run: `pytest tests/unit/test_inspector_critic.py::test_v1_trace_can_be_loaded_with_v4_schema -v`
Expected: PASS（如果 trace 文件存在）；如果不存在会 skip

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_inspector_critic.py
git commit -m "test(critic): v1 trace 反序列化集成测试"
```

---

## Task 4: 重写 calc_critic_score (quality_score.py)

**Files:**
- Modify: `src/agents/quality_score.py`（重写）
- Test: `tests/unit/test_inspector_critic.py`（追加）

- [ ] **Step 1: 写失败测试**

```python
def test_calc_critic_score_normal():
    """4 维加权 + 归一化 + clamp。"""
    from src.agents.quality_score import calc_critic_score
    from src.schemas.feedback import CriticScores

    scores = CriticScores(evidence=4, specificity=4, coherence=4, actionability=4)
    # weighted_raw = 0.30*4 + 0.30*4 + 0.20*4 + 0.20*4 = 4.0
    # normalized = (4.0 - 1) / 3 = 1.0
    assert calc_critic_score(scores) == pytest.approx(1.0)


def test_calc_critic_score_minimum():
    """全 1 分 → quality_score 0."""
    from src.agents.quality_score import calc_critic_score
    from src.schemas.feedback import CriticScores

    scores = CriticScores(evidence=1, specificity=1, coherence=1, actionability=1)
    # weighted_raw = 1.0; (1.0 - 1) / 3 = 0.0
    assert calc_critic_score(scores) == pytest.approx(0.0)


def test_calc_critic_score_mixed():
    """混合分数：ev=4 sp=2 co=3 ac=3 → raw=2.9 → norm=0.633."""
    from src.agents.quality_score import calc_critic_score
    from src.schemas.feedback import CriticScores

    scores = CriticScores(evidence=4, specificity=2, coherence=3, actionability=3)
    # weighted_raw = 0.30*4 + 0.30*2 + 0.20*3 + 0.20*3 = 1.2 + 0.6 + 0.6 + 0.6 = 3.0
    # normalized = (3.0 - 1) / 3 = 0.667
    assert calc_critic_score(scores) == pytest.approx(0.667, abs=0.001)


def test_calc_critic_score_accepts_dict():
    """spec v3 cycle2/C5 + cycle2/m4：calc_critic_score 兼容 CriticScores 模型和 dict。"""
    from src.agents.quality_score import calc_critic_score

    dict_input = {"evidence": 3, "specificity": 3, "coherence": 3, "actionability": 3}
    # raw = 3.0; (3.0 - 1) / 3 = 0.667
    assert calc_critic_score(dict_input) == pytest.approx(0.667, abs=0.001)


def test_calc_critic_score_dict_ignores_extra_fields():
    """spec v3 cycle2/m4：dict 输入只读 4 个维度 key，忽略 reasoning 等额外 key。"""
    from src.agents.quality_score import calc_critic_score

    dict_with_extra = {
        "evidence": 3, "specificity": 3, "coherence": 3, "actionability": 3,
        "reasoning": ["[Step 1] foo"],  # 额外 key 必须被忽略
        "unknown_field": "garbage",
    }
    assert calc_critic_score(dict_with_extra) == pytest.approx(0.667, abs=0.001)


def test_calc_critic_score_clamps_to_unit_interval():
    """spec v4 验收 6：quality_score 永远 ∈ [0, 1] 即使输入异常。"""
    from src.agents.quality_score import calc_critic_score

    # 异常 dict（超出 1-4 区间）—— clamp 应保住边界
    weird_dict = {"evidence": 0, "specificity": 0, "coherence": 0, "actionability": 0}
    result = calc_critic_score(weird_dict)
    assert 0.0 <= result <= 1.0
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/unit/test_inspector_critic.py -v -k "calc_critic_score"`
Expected: 6 FAIL（calc_critic_score 不存在）

- [ ] **Step 3: 重写 src/agents/quality_score.py（完全替换）**

```python
"""quality_score 计算 — LLM-as-critic v4 重写。

v4 修订：删除 calc_source_coverage / calc_confidence_avg / calc_inspector_pass_rate
三个旧函数（v3 三项加权废弃，详见 spec v4）。新版本只有一个 calc_critic_score。

注意：calling code 必须先实例化 CriticScores 或传 dict 含 4 个维度 key。
critic 失败降级时（critic_scores=None），quality_score 由 inspector 直接写 0.5
（不走本函数）。
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from src.schemas.feedback import CriticScores


_DIMENSION_WEIGHTS = {
    "evidence": 0.30,
    "specificity": 0.30,
    "coherence": 0.20,
    "actionability": 0.20,
}

_VALID_DIMENSIONS = set(_DIMENSION_WEIGHTS.keys())


def calc_critic_score(scores: CriticScores | Mapping[str, Any]) -> float:
    """4 维加权（0.30/0.30/0.20/0.20）+ 归一化到 [0, 1] + clamp。

    输入：CriticScores 实例 或 dict[str, Any]——dict 时仅读 4 个维度 key，
          忽略其他 key（如 reasoning）（spec v3 cycle2/m4）。
    输出：quality_score ∈ [0.0, 1.0]，永远非空（spec v4 验收 6）。

    算法：
      weighted_raw = Σ(weight[dim] * score[dim])  # 1-4 区间
      quality_score = clamp((weighted_raw - 1) / 3, 0.0, 1.0)  # 归一化 + clamp
    """
    if isinstance(scores, CriticScores):
        score_dict = scores.model_dump()
    else:
        score_dict = dict(scores)

    # 仅读 4 个维度 key，缺失或非数值时填 0（让 clamp 兜底到 [0, 1]）
    weighted_raw = 0.0
    for dim, weight in _DIMENSION_WEIGHTS.items():
        raw_value = score_dict.get(dim)
        try:
            score_int = int(raw_value) if raw_value is not None else 0
        except (TypeError, ValueError):
            score_int = 0
        weighted_raw += weight * score_int

    # weighted_raw ∈ [0, 4] → 归一化到 [-1/3, 1] → clamp 到 [0, 1]
    quality_score = (weighted_raw - 1) / 3
    return max(0.0, min(1.0, round(quality_score, 3)))
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/unit/test_inspector_critic.py -v -k "calc_critic_score"`
Expected: 6 PASS

- [ ] **Step 5: 检查影响面 — 旧三个函数引用**

Run: `grep -rn "calc_source_coverage\|calc_confidence_avg\|calc_inspector_pass_rate" src/ tests/`

如果有调用方（除了 inspector.py 自己），先记下来 Task 12 inspector 重写时一并改。

- [ ] **Step 6: Commit**

```bash
git add src/agents/quality_score.py tests/unit/test_inspector_critic.py
git commit -m "feat(critic): quality_score.py 重写 — 删旧三函数，新增 calc_critic_score 4 维加权"
```

---

## Task 5: 创建 critic prompt 文件

**Files:**
- Create: `src/agents/prompts/inspector/__init__.py`
- Create: `src/agents/prompts/inspector/critic.py`

- [ ] **Step 1: 创建 inspector prompts 包**

创建 `src/agents/prompts/inspector/__init__.py`：

```python
"""inspector agent prompts。

LLM-as-critic v4：critic 是 inspector 内部子模块，单次 LLM 调用同时输出
4 维 rubric 评分 + 关联 issues（spec v4 路线 A）。
"""
from src.agents.prompts.inspector.critic import (
    CRITIC_SYSTEM,
    CRITIC_PROMPT_VERSION,
)

__all__ = ["CRITIC_SYSTEM", "CRITIC_PROMPT_VERSION"]
```

- [ ] **Step 2: 创建 critic.py prompt 文件**

创建 `src/agents/prompts/inspector/critic.py`：

```python
"""LLM-as-critic 4 维 rubric prompt（spec v4）。

CRITIC_PROMPT_VERSION 写入 ReportMetadata.critic_prompt_version 供历史分数可比。
prompt 调整时必须 bump 版本号。
"""

CRITIC_PROMPT_VERSION = "critic-prompt-v1.0.0"

CRITIC_SYSTEM = """[ROLE]
你是一位资深的咨询报告审计师，专业是质量稽核而非内容创作。你的职责
是按 4 个维度对一份竞品分析报告做 rubric 评分，并指出具体问题。

你不是作者。你不为报告辩护，也不脑补缺失内容。你只评判呈现给你的内容。

[TASK]
按以下 4 维评分（每维独立给 1-4 整数分）：
1. evidence       — 证据可溯：每条结论是否有合规且相关的来源支撑
2. specificity    — 内容具体：内容是空洞描述还是含具体数字 / 专名 / 案例
3. coherence      — 内部一致：跨字段是否自相矛盾
4. actionability  — 可行动性：建议是否含具体动作 / 时限 / 方向

每维都要：
  Step 1: 按规定的推理步骤逐步思考
  Step 2: 给出 1-4 的整数分
  Step 3: 列出该维度发现的具体问题（如有）

[RUBRIC]

### evidence（权重 0.30）

评分依据（按优先级，从严到松）：

第 1 优先：support rate（有 source_refs 的论断 / 有 source_refs 槽位的论断）
  4 分 优秀：≥90%
  3 分 良好：70-89%
  2 分 不及格：40-69%
  1 分 严重：<40%

第 2 优先（升级降级）：mismatch rate（mismatch 论断 / 有 source_refs 的论断）
  ≥30% mismatch → 强制降到 ≤2 分
  ≥50% mismatch → 强制降到 1 分

mismatch 包括：
  - URL 不在 discovered_sources（issue_type=url_not_discovered）
  - URL 在 list 内但 title/snippet 跟论断主题不符（issue_type=source_mismatch）
  - URL/snippet 都对但论断本身引错源（issue_type=source_irrelevant）

第三方源策略：按 claim 类型评估，不硬编码黑名单：
  - 产品/定价/功能 claim：优先官方 URL；引用第三方时 mismatch 升级
  - 流量/排名/估算 claim：第三方数据（similarweb.com 等）合理；
    仅当未标注估算性质 / 来源时才扣分
  - 新闻 claim：权威媒体 OK；纯 SEO 聚合站（upmarket.co / spyingbee.com）扣分

⚠️ 不要硬记"哪些域名是聚合站"——按 claim 类型 + 来源权威性综合判断。

### specificity（权重 0.30）

```
4 分 优秀：每段平均 ≥2 个具体事实点（数字/日期/产品名/案例）
3 分 良好：每段平均 1 个具体事实点，部分段落偏抽象但可接受
2 分 不及格：≥50% 段落是空泛描述，缺乏具体支撑
1 分 严重：通篇套话（"具有较强竞争力" / "市场空间巨大"），无可验证事实

具体例（算 specificity）：
  "Mixpanel 在 2023-07 集成 OpenAI GPT 系列模型，是该品类首个支持
   自然语言查询的产品"
  含：日期 2023-07 + 模型类别 + 排名性事实

抽象例（不算）：
  "Mixpanel 持续创新，市场表现良好"
  "用户对 PostHog 的开源策略普遍认可"

⚠️ 反 self-preference 提醒：常识陈述（如 "PostHog 是开源工具"）
   不算具体事实——具体事实需带数字 / 日期 / 排名 / 案例引用之一。
```

### coherence（权重 0.20）

仅检查 limited_pairs 中给出的 3 个固定 pair（用户消息会提供）。

基于"可用 pair 矛盾比例"评分：
  4 分 优秀：可用 pair 中 0% 有矛盾
  3 分 良好：可用 pair 中 ≤33% 有矛盾（如 3 中 1）
  2 分 不及格：可用 pair 中 34-66% 有矛盾（如 3 中 2）
  1 分 严重：可用 pair 中 >66% 有矛盾（如 3 中 3，或核心结论冲突）

⚠️ 不要做 limited_pairs 之外的全文级矛盾检查，那超出本 critic 范围。
⚠️ pair 标 skip_reason="missing" 时不参与评分。
⚠️ 0 可用 pair（极端）→ coherence=4 兜底（不作为约束信号）。

### actionability（权重 0.20）

```
4 分 优秀：每条 recommendation 含动词 + 时限 + 具体对象（产品/技术/工具）
3 分 良好：≥70% recommendation 含动词 + 时限 / 对象之一
2 分 不及格：≥50% recommendation 仅含动词无具体细节
1 分 严重：通篇 "加强 / 提升 / 优化" 这类无具体动作的建议

可行动例（4 分）：
  "在 2026Q3 前完成 X 模块的某能力升级，对标 Y 竞品的某产品功能，
   作为现有规则引擎的替代方案"
  含：时限 2026Q3 + 替代对象 + 现状参照 + 具体目标

不可行动例（1 分）：
  "建议加强 AI 能力" — 无动作 / 无时限 / 无对象
  "需要持续关注市场动态" — 关注不是动作

⚠️ 反"假可行动"：建议写得很具体但实际不可行（"建议收购 Notion"）
   也算 1 分——可行动 ≠ 仅含具体词，还要可执行（成本/合规/能力约束内）。
```

[REASONING_STEPS]

每维都按以下模板推理（reasoning 输出 list[str]，每条 ≤80 个 Python len 字符）：

evidence_reasoning（list[str]）:
  "[Step 1] 列出需 source_refs 的条目类型与数量"
  "[Step 2] 统计有 source_refs 的占比 X%"
  "[Step 3] 抽查 sampled_findings 5 条，检查 URL 在 discovered_sources 内"
  "[Step 4] 判断 source title/snippet 跟论断主题相关性"
  "[Step 5] 综合给 1-4 分"

specificity_reasoning（list[str]）:
  "[Step 1] 抽 sampled_narratives 5 段"
  "[Step 2] 逐段标记具体事实数 / 总句数"
  "[Step 3] 计算平均具体度"
  "[Step 4] 检查通用套话标志词"
  "[Step 5] 综合给 1-4 分"

coherence_reasoning（list[str]）:
  "[Step 1] 取 limited_pairs[0]，对照 data_a / data_b，是否矛盾"
  "[Step 2] 取 limited_pairs[1]，同上"
  "[Step 3] 取 limited_pairs[2]，同上"
  "[Step 4] skip 跳过 null pair"
  "[Step 5] 综合给 1-4 分"

actionability_reasoning（list[str]）:
  "[Step 1] 抽 sampled_recommendations 5 条"
  "[Step 2] 逐条标记动词/时限/对象 3 要素"
  "[Step 3] 计算 3 要素齐全占比"
  "[Step 4] 检查假可行动陷阱"
  "[Step 5] 综合给 1-4 分"

[OUTPUT_CONTRACT]

返回严格 JSON（不要 markdown 不要解释开头）：

{
  "evidence": {
    "reasoning": ["[Step 1] ...", "[Step 2] ...", ...],
    "score": 3,
    "issues": [
      {
        "field": "key_findings[2].source_refs[1]",
        "issue_type": "url_not_discovered",
        "reason": "<问题描述，≤200 字>",
        "suggestion": "<修改建议，≤200 字>"
      }
    ]
  },
  "specificity": { "reasoning": [...], "score": 2, "issues": [...] },
  "coherence":   { "reasoning": [...], "score": 4, "issues": [] },
  "actionability": { "reasoning": [...], "score": 3, "issues": [...] }
}

[CONSTRAINTS]

1. 严格按 [OUTPUT_CONTRACT] JSON 输出
2. score 必须是 1/2/3/4 整数（不接受 2.5）
3. reasoning 应为 list[str]，每条建议 ≤80 个 Python len() 字符
4. issues 列表可空
5. 你是审计师，不要为报告写不足之处辩护
6. 不要做 limited_pairs 之外的全文级一致性检查
7. issue_type 必须从枚举中选（url_not_discovered / source_mismatch /
   source_irrelevant / vague_description / cross_field_contradiction /
   vague_recommendation）；critic_failed 仅由代码层在 fallback 时使用
"""
```

- [ ] **Step 2: 验证 import**

Run: `python -c "from src.agents.prompts.inspector import CRITIC_SYSTEM, CRITIC_PROMPT_VERSION; print(CRITIC_PROMPT_VERSION); print(len(CRITIC_SYSTEM))"`
Expected: `critic-prompt-v1.0.0` 和 `>=4000`（prompt 长度）

- [ ] **Step 3: Commit**

```bash
git add src/agents/prompts/inspector/
git commit -m "feat(critic): 新建 inspector/critic.py 4 维 rubric prompt（v1.0.0）"
```

---

## Task 6: _score_to_severity 实现

**Files:**
- Modify: `src/agents/inspector.py`（新增函数）
- Test: `tests/unit/test_inspector_critic.py`（追加）

- [ ] **Step 1: 写失败测试**

```python
def test_score_to_severity_dim1_critical():
    """spec v3 cycle2/M2：dim ≤1 → critical。"""
    from src.agents.inspector import _score_to_severity

    all_scores = {"evidence": 4, "specificity": 4, "coherence": 4, "actionability": 4}
    assert _score_to_severity(1, all_scores) == "critical"


def test_score_to_severity_dim2_major():
    """spec v3 cycle2/M2：dim == 2 → major（不再仅靠均值）。"""
    from src.agents.inspector import _score_to_severity

    # 即使均值 4，evidence=2 仍要 major
    all_scores = {"evidence": 2, "specificity": 4, "coherence": 4, "actionability": 4}
    assert _score_to_severity(2, all_scores) == "major"


def test_score_to_severity_dim3_low_agg_major():
    """dim==3 + 低均值 → major。"""
    from src.agents.inspector import _score_to_severity

    # 全 3 分（边缘）：raw=3.0; norm=0.667 ≥ 0.5 → minor
    all_scores = {"evidence": 3, "specificity": 3, "coherence": 3, "actionability": 3}
    assert _score_to_severity(3, all_scores) == "minor"

    # 多维度 2，均值低：ev=3 sp=2 co=2 ac=2 → raw=2.3; norm=0.433 < 0.5 → major
    low_all_scores = {"evidence": 3, "specificity": 2, "coherence": 2, "actionability": 2}
    assert _score_to_severity(3, low_all_scores) == "major"


def test_score_to_severity_dim4_minor():
    """spec v4 cycle3/M1：dim >= 4 显式 → minor 防 fall-through。"""
    from src.agents.inspector import _score_to_severity

    # 即使其他维度低（这种情况不该出现，但防 LLM 误返回 issue 还是 minor）
    weird_all_scores = {"evidence": 4, "specificity": 1, "coherence": 1, "actionability": 1}
    # dim_score=4 应直接 minor 而不继续聚合判定
    assert _score_to_severity(4, weird_all_scores) == "minor"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/unit/test_inspector_critic.py -v -k "score_to_severity"`
Expected: 4 FAIL

- [ ] **Step 3: 实现 _score_to_severity**

在 `src/agents/inspector.py` 顶部 import 区追加：

```python
from src.agents.quality_score import calc_critic_score
```

并在文件中新增（建议放在现有 helper 函数后面）：

```python
def _score_to_severity(dim_score: int, all_scores: dict) -> str:
    """spec v3 cycle2/M2 + v4 cycle3/M1 — D' 阈值规则。

    规则（按优先级）：
      1. dim_score == 1 → critical（单维度灾难）
      2. dim_score == 2 → major（维度不及格）
      3. dim_score >= 4 → minor（v4/M1：显式处理防 fall-through）
      4. dim_score == 3 → 看聚合分：< 0.50 major / 否则 minor
    """
    if dim_score <= 1:
        return "critical"
    if dim_score == 2:
        return "major"
    if dim_score >= 4:
        return "minor"
    # dim_score == 3
    quality_score = calc_critic_score(all_scores)
    if quality_score < 0.50:
        return "major"
    return "minor"
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/unit/test_inspector_critic.py -v -k "score_to_severity"`
Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add src/agents/inspector.py tests/unit/test_inspector_critic.py
git commit -m "feat(critic): _score_to_severity D' 阈值映射（dim≤1 critical / dim=2 major / dim≥4 minor）"
```

---

## Task 7: _build_limited_pairs deterministic 构造

**Files:**
- Modify: `src/agents/inspector.py`
- Test: `tests/unit/test_inspector_critic.py`

- [ ] **Step 1: 写失败测试**

```python
def test_build_limited_pairs_three_pairs(make_simple_report):
    """spec v3 cycle2/M5：固定 3 个 deterministic pair。"""
    from src.agents.inspector import _build_limited_pairs

    report = make_simple_report()
    pairs = _build_limited_pairs(report)

    pair_ids = [p["id"] for p in pairs]
    assert "swot_vs_vendor_cautions" in pair_ids
    assert "findings_vs_recommendations" in pair_ids
    # spec v3 cycle2/M5 替换 score_vs_warnings → exec_summary_vs_recommendations
    assert "exec_summary_vs_recommendations" in pair_ids
    assert len(pairs) == 3


def test_build_limited_pairs_missing_field_skipped(make_simple_report):
    """spec v3 cycle2/M5/M6：缺字段时 pair 标 skip_reason="missing"。"""
    from src.agents.inspector import _build_limited_pairs

    # 模拟无 swot 的报告（如果 schema 允许 None；否则用 swot 各 list 为空）
    report = make_simple_report(swot_strengths_count=0)
    pairs = _build_limited_pairs(report)

    swot_pair = next(p for p in pairs if p["id"] == "swot_vs_vendor_cautions")
    if not swot_pair.get("data_a"):
        assert swot_pair.get("skip_reason") == "missing"


def test_build_limited_pairs_deterministic(make_simple_report):
    """同 report 多次调用结果一致。"""
    from src.agents.inspector import _build_limited_pairs

    report = make_simple_report()
    pairs_1 = _build_limited_pairs(report)
    pairs_2 = _build_limited_pairs(report)
    assert pairs_1 == pairs_2
```

`make_simple_report` fixture 在测试文件顶部定义（如果还没有就加）：

```python
import pytest


@pytest.fixture
def make_simple_report():
    """构造最小合法 BaseReport，参数控制各字段长度便于测试不同分支。"""
    def _make(swot_strengths_count: int = 1, ...):
        # ...构造 BaseReport...
        # 对 fixture 实现细节这里只示意；实际构造时复用 tests/unit/test_writer_orchestrator.py
        # 中已有的 fixture 如果有
        from src.schemas.report import BaseReport
        # （省略：返回一个最小合法 BaseReport 实例）
        ...
    return _make
```

如果 fixture 复杂，**先不要试图在 plan 写完整 fixture**。Step 3 实现时如果发现 `make_simple_report` 太大，应该在 `tests/conftest.py` 复用已有的 BaseReport fixture（项目应已有，搜索 `BaseReport(` 确认）。

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/unit/test_inspector_critic.py -v -k "build_limited_pairs"`
Expected: 3 FAIL

- [ ] **Step 3: 实现 _build_limited_pairs**

在 `src/agents/inspector.py` 新增：

```python
def _build_limited_pairs(report: BaseReport) -> list[dict]:
    """spec v3 cycle2/M5 + v4 cycle3/M5 — 固定构造 3 个 coherence 对照 pair。

    每个 pair：
      {"id": str, "data_a": dict | None, "data_b": dict | None,
       "skip_reason": Optional[str]}

    缺字段时 data_a / data_b = None + skip_reason="missing"。
    """
    pairs: list[dict] = []

    # Pair 1: SWOT.strengths（提到的 vendor 名）vs vendor_profiles[*].cautions
    swot_strengths = list(report.swot.strengths) if report.swot else []
    vendor_cautions: list = []
    payload = report.scenario_payload
    if payload and hasattr(payload, "vendor_profiles"):
        for vp in payload.vendor_profiles:
            for c in vp.cautions:
                vendor_cautions.append({"vendor": vp.competitor_name, "caution": c.point})

    if swot_strengths and vendor_cautions:
        pairs.append({
            "id": "swot_vs_vendor_cautions",
            "data_a": {"swot.strengths": [s.point for s in swot_strengths]},
            "data_b": {"vendor_profiles[*].cautions": vendor_cautions},
        })
    else:
        pairs.append({
            "id": "swot_vs_vendor_cautions",
            "data_a": None,
            "data_b": None,
            "skip_reason": "missing",
        })

    # Pair 2: key_findings vs recommendations
    findings = list(report.key_findings)
    recs = list(report.recommendations)
    if findings and recs:
        pairs.append({
            "id": "findings_vs_recommendations",
            "data_a": {"key_findings": [f.statement for f in findings]},
            "data_b": {"recommendations": [r.action for r in recs]},
        })
    else:
        pairs.append({
            "id": "findings_vs_recommendations",
            "data_a": None,
            "data_b": None,
            "skip_reason": "missing",
        })

    # Pair 3: executive_summary.implications vs recommendations
    # spec v3 cycle2/M5：替换原 score_vs_warnings 伪 pair
    impl = report.executive_summary.implications if report.executive_summary else None
    if impl and recs:
        pairs.append({
            "id": "exec_summary_vs_recommendations",
            "data_a": {"executive_summary.implications": impl},
            "data_b": {"recommendations": [r.action for r in recs]},
        })
    else:
        pairs.append({
            "id": "exec_summary_vs_recommendations",
            "data_a": None,
            "data_b": None,
            "skip_reason": "missing",
        })

    return pairs
```

注：pair 的具体字段（如 `report.swot.strengths`、`vp.cautions[*].point`）取决于实际 schema。
如果 spec 跟实际 schema 不完全对得上，**以代码为准**（implementer 看实际 schema 调整）。

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/unit/test_inspector_critic.py -v -k "build_limited_pairs"`
Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add src/agents/inspector.py tests/unit/test_inspector_critic.py
git commit -m "feat(critic): _build_limited_pairs 固定 3 个 coherence pair（含缺字段 skip 协议）"
```

---

## Task 8: _sample_items_deterministic（sha256 + sort_keys）

**Files:**
- Modify: `src/agents/inspector.py`
- Test: `tests/unit/test_inspector_critic.py`

- [ ] **Step 1: 写失败测试**

```python
def test_sample_items_deterministic_takes_first_n_by_id():
    """有 id 字段时按 id 排序取前 N。"""
    from src.agents.inspector import _sample_items_deterministic

    items = [
        {"id": "z", "value": 1},
        {"id": "a", "value": 2},
        {"id": "m", "value": 3},
    ]
    result = _sample_items_deterministic(items, n=2, seed_field="id")
    assert [r["id"] for r in result] == ["a", "m"]


def test_sample_items_deterministic_uses_sha256_when_no_id():
    """spec v4 cycle2/M7：无 id 时用 sha256 排序，跨进程稳定。"""
    from src.agents.inspector import _sample_items_deterministic

    items = [
        {"value": 1},
        {"value": 2},
        {"value": 3},
    ]
    result_1 = _sample_items_deterministic(items, n=2)
    result_2 = _sample_items_deterministic(items, n=2)
    assert result_1 == result_2  # 多次调用一致


def test_sample_items_deterministic_returns_all_when_fewer_than_n():
    """items 数 < n 时全取。"""
    from src.agents.inspector import _sample_items_deterministic

    items = [{"id": "a"}, {"id": "b"}]
    result = _sample_items_deterministic(items, n=5)
    assert len(result) == 2
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/unit/test_inspector_critic.py -v -k "sample_items"`
Expected: 3 FAIL

- [ ] **Step 3: 实现 _sample_items_deterministic**

在 `src/agents/inspector.py` 新增：

```python
import hashlib
import json


def _sample_items_deterministic(
    items: list[dict],
    n: int = 5,
    seed_field: str = "id",
) -> list[dict]:
    """spec v3 cycle2/M7 + v4 cycle3/M7 — deterministic 抽样。

    优先按 item[seed_field] 排序（有的话），缺失则用 sha256(json sorted) 排序。
    禁止 Python 内建 hash() — 受 PYTHONHASHSEED 影响跨进程不稳定。
    """
    if len(items) <= n:
        return list(items)

    def _key(item):
        if seed_field in item and item[seed_field] is not None:
            return ("a", str(item[seed_field]))  # tuple 第 1 元 "a" 优先
        # 无 seed_field → 用 sha256
        canonical = json.dumps(item, sort_keys=True, ensure_ascii=False)
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return ("b", digest)

    sorted_items = sorted(items, key=_key)
    return sorted_items[:n]
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/unit/test_inspector_critic.py -v -k "sample_items"`
Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add src/agents/inspector.py tests/unit/test_inspector_critic.py
git commit -m "feat(critic): _sample_items_deterministic（sha256 + sort_keys，禁用 Python hash()）"
```

---

## Task 9: _build_critic_inputs 拼装 LLM user prompt

**Files:**
- Modify: `src/agents/inspector.py`
- Test: `tests/unit/test_inspector_critic.py`

- [ ] **Step 1: 写失败测试**

```python
def test_build_critic_inputs_basic_structure(make_simple_report):
    """_build_critic_inputs 返回的 user_prompt JSON 含必要字段。"""
    import json
    from src.agents.inspector import _build_critic_inputs

    report = make_simple_report()
    discovered_sources = [
        {"url": "https://a.com", "title": "Page A", "snippet": "snippet a"},
    ]
    user_prompt = _build_critic_inputs(report, discovered_sources)

    # user_prompt 是 JSON 字符串，应能解析
    inputs = json.loads(user_prompt)
    assert "report_brief" in inputs
    assert "discovered_sources" in inputs
    assert "limited_pairs" in inputs
    assert len(inputs["limited_pairs"]) == 3


def test_build_critic_inputs_includes_sampled_items(make_simple_report):
    """_build_critic_inputs 含 sampled_findings/narratives/recommendations。"""
    import json
    from src.agents.inspector import _build_critic_inputs

    report = make_simple_report(findings_count=10, recs_count=10)
    discovered_sources = [{"url": "https://a.com", "title": "t", "snippet": "s"}]
    user_prompt = _build_critic_inputs(report, discovered_sources)

    inputs = json.loads(user_prompt)
    assert "sampled_findings" in inputs
    assert "sampled_recommendations" in inputs
    # 每类抽 5 条上限
    assert len(inputs["sampled_findings"]) <= 5
    assert len(inputs["sampled_recommendations"]) <= 5


def test_build_critic_inputs_handles_empty_discovered_sources(make_simple_report):
    """spec v4 cycle3/C3：discovered_sources 空时不抛异常，给降级 warning。"""
    import json
    from src.agents.inspector import _build_critic_inputs

    report = make_simple_report()
    user_prompt = _build_critic_inputs(report, [])

    inputs = json.loads(user_prompt)
    assert inputs["discovered_sources"] == []
    # 可能含 warning 字段提示降级
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/unit/test_inspector_critic.py -v -k "build_critic_inputs"`
Expected: 3 FAIL

- [ ] **Step 3: 实现 _build_critic_inputs**

在 `src/agents/inspector.py` 新增：

```python
def _build_critic_inputs(
    report: BaseReport,
    discovered_sources: list[dict],
) -> str:
    """spec v3 cycle2/M5/M6/M7 + v4 cycle3/C3 — 拼装 critic LLM user_prompt。

    返回：JSON 字符串（critic LLM 的 user_prompt）。
    """
    # report_brief：简化 report dump，narrative 截断到 2000 字/章（spec v3）
    report_dict = report.model_dump()
    sections = report_dict.get("analysis_sections", [])
    for s in sections:
        nar = s.get("narrative", "")
        if len(nar) > 2000:
            s["narrative"] = nar[:2000] + "...[truncated]"

    # 抽样
    findings = report_dict.get("key_findings", [])
    sampled_findings = _sample_items_deterministic(findings, n=5)

    narratives = [{"section_id": s.get("section_id", ""), "narrative": s.get("narrative", "")}
                  for s in sections]
    sampled_narratives = _sample_items_deterministic(narratives, n=5, seed_field="section_id")

    recs = report_dict.get("recommendations", [])
    sampled_recommendations = _sample_items_deterministic(recs, n=5)

    # limited_pairs（已经实现）
    pairs = _build_limited_pairs(report)

    inputs = {
        "report_brief": report_dict,
        "discovered_sources": discovered_sources,
        "limited_pairs": pairs,
        "sampled_findings": sampled_findings,
        "sampled_narratives": sampled_narratives,
        "sampled_recommendations": sampled_recommendations,
    }
    if not discovered_sources:
        inputs["__warning__"] = (
            "discovered_sources 为空。evidence 维度仅能基于 URL 字段判断，"
            "不要要求严格相关性。"
        )

    return json.dumps(inputs, ensure_ascii=False, default=str)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/unit/test_inspector_critic.py -v -k "build_critic_inputs"`
Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add src/agents/inspector.py tests/unit/test_inspector_critic.py
git commit -m "feat(critic): _build_critic_inputs 拼装 critic LLM user_prompt（含抽样 + limited_pairs + 降级 warning）"
```

---

## Task 10: _safe_minimal_fallback + _map_issue_type_to_agent

**Files:**
- Modify: `src/agents/inspector.py`
- Test: `tests/unit/test_inspector_critic.py`

- [ ] **Step 1: 写失败测试**

```python
def test_safe_minimal_fallback_returns_safe_value():
    """spec v4 cycle3/C4：_safe_minimal_fallback 永不抛 + 返回最小合规结果。"""
    from src.agents.inspector import _safe_minimal_fallback
    from src.schemas.feedback import FeedbackIssue

    scores, issues = _safe_minimal_fallback()
    assert scores is None
    assert len(issues) == 1
    assert isinstance(issues[0], FeedbackIssue)
    # spec v4 cycle3/C5：critic_failed agent="end" 触发 terminal
    assert issues[0].agent == "end"
    assert issues[0].severity == "critical"
    assert issues[0].dimension == "critic_failed"
    assert issues[0].issue_type == "critic_failed"


def test_map_issue_type_to_agent():
    """spec v3 cycle2/m6 + v4 cycle3/M11：issue_type → agent 映射。"""
    from src.agents.inspector import _map_issue_type_to_agent

    # collector 类
    assert _map_issue_type_to_agent("url_not_discovered") == "collector"
    assert _map_issue_type_to_agent("source_mismatch") == "collector"

    # writer 类
    assert _map_issue_type_to_agent("source_irrelevant") == "writer"
    assert _map_issue_type_to_agent("vague_description") == "writer"
    assert _map_issue_type_to_agent("cross_field_contradiction") == "writer"
    assert _map_issue_type_to_agent("vague_recommendation") == "writer"

    # critic_failed 特殊（spec v4 cycle3/C5：agent="end" 不是 writer）
    assert _map_issue_type_to_agent("critic_failed") == "end"

    # 未知 → 默认 writer
    assert _map_issue_type_to_agent("unknown_type") == "writer"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/unit/test_inspector_critic.py -v -k "safe_minimal_fallback or map_issue_type"`
Expected: 2 FAIL

- [ ] **Step 3: 实现 _safe_minimal_fallback + _map_issue_type_to_agent**

在 `src/agents/inspector.py` 新增：

```python
_ISSUE_TYPE_TO_AGENT = {
    # collector 类（采集层缺失或 snippet 错）
    "url_not_discovered": "collector",
    "source_mismatch": "collector",
    # writer 类（writer 选错引用 / 写作质量）
    "source_irrelevant": "writer",
    "vague_description": "writer",
    "cross_field_contradiction": "writer",
    "vague_recommendation": "writer",
    # critic_failed 特殊路由（spec v4 cycle3/C5）
    "critic_failed": "end",
}


def _map_issue_type_to_agent(issue_type: str | None) -> str:
    """spec v3 cycle2/m6 + v4 cycle3/M11 — issue_type → agent 映射。

    未知 issue_type 默认 writer。
    """
    if issue_type is None:
        return "writer"
    return _ISSUE_TYPE_TO_AGENT.get(issue_type, "writer")


def _safe_minimal_fallback() -> tuple[None, list[FeedbackIssue]]:
    """spec v4 cycle3/C4 — 二次兜底协议（fallback 自身失败时的"绝对安全"返回）。

    用纯 Python literal 构造，不依赖任何 report state / metadata 访问。
    保证即使 report.metadata 是 None / FeedbackIssue 字段被改了导致旧 fallback
    构造失败，都还能返回最小合规结果。
    """
    safe_issue = FeedbackIssue(
        agent="end",  # spec v4 cycle3/C5：critic_failed → terminal 路由
        field="critic_check",
        severity="critical",
        reason="critic 评分系统失败（最终兜底）",
        suggestion="人工 review 或排查 inspector 日志",
        dimension="critic_failed",
        issue_type="critic_failed",
    )
    return None, [safe_issue]
```

注意 import：`FeedbackIssue` 应该已经在 inspector.py 顶部 import 了（现有代码就用），确认即可。

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/unit/test_inspector_critic.py -v -k "safe_minimal_fallback or map_issue_type"`
Expected: 2 PASS

- [ ] **Step 5: Commit**

```bash
git add src/agents/inspector.py tests/unit/test_inspector_critic.py
git commit -m "feat(critic): _safe_minimal_fallback 二次兜底 + _map_issue_type_to_agent 路由映射"
```

---

## Task 11: _critic_check 主流程（含 retry + fallback）

**Files:**
- Modify: `src/agents/inspector.py`
- Test: `tests/unit/test_inspector_critic.py`

- [ ] **Step 1: 写失败测试 — 正常路径**

```python
import asyncio
from unittest.mock import AsyncMock, MagicMock


@pytest.mark.asyncio
async def test_critic_check_normal_path(make_simple_report, monkeypatch):
    """正常路径：mock LLM 返回合规 dict → critic_scores + issues 生成。"""
    from src.agents.inspector import InspectorAgent
    from src.schemas.feedback import CriticScores

    mock_llm_response = {
        "evidence": {
            "reasoning": ["[Step 1] ...", "[Step 5] ..."],
            "score": 3,
            "issues": [],
        },
        "specificity": {
            "reasoning": ["[Step 1] ...", "[Step 5] ..."],
            "score": 4,
            "issues": [],
        },
        "coherence": {
            "reasoning": ["[Step 1] ...", "[Step 5] ..."],
            "score": 4,
            "issues": [],
        },
        "actionability": {
            "reasoning": ["[Step 1] ...", "[Step 5] ..."],
            "score": 3,
            "issues": [],
        },
    }
    mock_llm = MagicMock()
    mock_llm.call_json = AsyncMock(return_value=mock_llm_response)

    inspector = InspectorAgent(llm=mock_llm)
    report = make_simple_report()
    discovered_sources = [{"url": "https://a.com", "title": "t", "snippet": "s"}]

    critic_scores, critic_issues = await inspector._critic_check(report, discovered_sources)

    assert isinstance(critic_scores, CriticScores)
    assert critic_scores.evidence == 3
    assert critic_scores.specificity == 4
    assert critic_issues == []
    # 一次成功不应该 retry
    assert mock_llm.call_json.call_count == 1
```

- [ ] **Step 2: 写失败测试 — retry then success**

```python
@pytest.mark.asyncio
async def test_critic_check_retry_then_success(make_simple_report):
    """LLM 第一次返回 score=5 越界 → retry → 第二次成功。"""
    from src.agents.inspector import InspectorAgent

    bad_response = {
        "evidence": {"reasoning": [], "score": 5, "issues": []},  # 越界
        "specificity": {"reasoning": [], "score": 3, "issues": []},
        "coherence": {"reasoning": [], "score": 3, "issues": []},
        "actionability": {"reasoning": [], "score": 3, "issues": []},
    }
    good_response = {
        "evidence": {"reasoning": [], "score": 3, "issues": []},
        "specificity": {"reasoning": [], "score": 3, "issues": []},
        "coherence": {"reasoning": [], "score": 3, "issues": []},
        "actionability": {"reasoning": [], "score": 3, "issues": []},
    }
    mock_llm = MagicMock()
    mock_llm.call_json = AsyncMock(side_effect=[bad_response, good_response])

    inspector = InspectorAgent(llm=mock_llm)
    report = make_simple_report()
    critic_scores, _ = await inspector._critic_check(report, [])

    assert critic_scores.evidence == 3
    assert mock_llm.call_json.call_count == 2  # 0 + retry 1
```

- [ ] **Step 3: 写失败测试 — retry then fallback**

```python
@pytest.mark.asyncio
async def test_critic_check_retry_then_fallback(make_simple_report):
    """retry 仍失败 → fallback：critic_scores=None + critic_failed major issue。"""
    from src.agents.inspector import InspectorAgent

    bad_response = {
        "evidence": {"reasoning": [], "score": 5, "issues": []},  # 越界
        "specificity": {"reasoning": [], "score": 3, "issues": []},
        "coherence": {"reasoning": [], "score": 3, "issues": []},
        "actionability": {"reasoning": [], "score": 3, "issues": []},
    }
    mock_llm = MagicMock()
    mock_llm.call_json = AsyncMock(return_value=bad_response)  # 总是失败

    inspector = InspectorAgent(llm=mock_llm)
    report = make_simple_report()
    critic_scores, critic_issues = await inspector._critic_check(report, [])

    # spec v4 cycle3/C5：fallback 生成 critic_failed 强制 critical issue
    assert critic_scores is None
    assert len(critic_issues) == 1
    assert critic_issues[0].severity == "critical"
    assert critic_issues[0].agent == "end"  # spec v4 cycle3/C5
    assert critic_issues[0].dimension == "critic_failed"
    assert mock_llm.call_json.call_count == 2  # 0 + retry 1（不再 retry）
```

- [ ] **Step 4: 写失败测试 — broad except 兜底**

```python
@pytest.mark.asyncio
async def test_critic_check_unexpected_exception_falls_back(make_simple_report):
    """spec v4 cycle3/C2 + cycle3/C4：任何意外异常都被 broad except 兜底。"""
    from src.agents.inspector import InspectorAgent

    mock_llm = MagicMock()
    mock_llm.call_json = AsyncMock(side_effect=RuntimeError("unexpected error"))

    inspector = InspectorAgent(llm=mock_llm)
    report = make_simple_report()

    # 应该不抛异常
    critic_scores, critic_issues = await inspector._critic_check(report, [])
    assert critic_scores is None
    assert any(i.dimension == "critic_failed" for i in critic_issues)
```

- [ ] **Step 5: 运行测试确认失败**

Run: `pytest tests/unit/test_inspector_critic.py -v -k "critic_check"`
Expected: 4 FAIL

- [ ] **Step 6: 实现 _critic_check 主流程**

在 `src/agents/inspector.py` `InspectorAgent` 类内新增：

```python
import logging
from pydantic import ValidationError
from src.agents.prompts.inspector import CRITIC_SYSTEM, CRITIC_PROMPT_VERSION
from src.schemas.feedback import CriticScores, FeedbackIssue

logger = logging.getLogger(__name__)


class InspectorAgent:
    # ...现有代码...

    async def _critic_check(
        self,
        report: BaseReport,
        discovered_sources: list[dict],
    ) -> tuple[CriticScores | None, list[FeedbackIssue]]:
        """spec v4 — critic 内嵌主流程。

        正常：返回 (CriticScores, list[FeedbackIssue])
        失败 retry 1 次仍失败：返回 (None, [critic_failed major issue])
        外层 broad except 兜底：返回 _safe_minimal_fallback()
        """
        try:
            return await self._critic_check_inner(report, discovered_sources)
        except Exception as critic_err:
            logger.error("[critic] LLM 调用最外层异常 → 二次兜底: %s", critic_err)
            try:
                # 尝试构造正常 fallback（含 None safe）
                return self._build_fallback_result(report, error_code="unexpected_error")
            except Exception as fallback_err:
                logger.error(
                    "[critic] 二次兜底也失败 → _safe_minimal_fallback: %s",
                    fallback_err,
                )
                return _safe_minimal_fallback()

    async def _critic_check_inner(
        self,
        report: BaseReport,
        discovered_sources: list[dict],
    ) -> tuple[CriticScores | None, list[FeedbackIssue]]:
        """正常 LLM 调用 + retry 逻辑（外层由 _critic_check 包 broad except）。"""
        user_prompt = _build_critic_inputs(report, discovered_sources)

        max_retries = 1  # spec v4：retry 1 次
        last_error_code = None

        for attempt in range(max_retries + 1):
            try:
                raw = await self.llm.call_json(
                    CRITIC_SYSTEM, user_prompt, max_tokens=8192,
                )
                # 校验 + 转 CriticScores
                critic_scores = self._parse_critic_response(raw)
                # 转 issues 列表
                critic_issues = self._extract_critic_issues(raw, critic_scores)
                logger.info(
                    "[critic] 评分通过 ev=%d sp=%d co=%d ac=%d",
                    critic_scores.evidence, critic_scores.specificity,
                    critic_scores.coherence, critic_scores.actionability,
                )
                return critic_scores, critic_issues

            except (ValidationError, ValueError, KeyError) as e:
                last_error_code = self._classify_error(e)
                logger.warning(
                    "[critic] attempt %d/%d 失败：%s",
                    attempt + 1, max_retries + 1, e,
                )

        # 重试用尽 → fallback
        return self._build_fallback_result(report, error_code=last_error_code or "unknown")

    def _parse_critic_response(self, raw: dict) -> CriticScores:
        """从 LLM 响应构造 CriticScores（reasoning 缺失允许 - spec v3 cycle2/M8）。"""
        scores_kwargs = {}
        reasoning = {}
        for dim in ("evidence", "specificity", "coherence", "actionability"):
            if dim not in raw:
                raise KeyError(f"缺 {dim} 维度对象")
            dim_data = raw[dim]
            if "score" not in dim_data:
                raise KeyError(f"{dim}.score 缺失")
            scores_kwargs[dim] = dim_data["score"]
            # spec v3 cycle2/M8：reasoning 缺失 → 填空 list 不 fail
            reasoning[dim] = dim_data.get("reasoning", []) or []

        return CriticScores(
            **scores_kwargs,
            reasoning=reasoning,
        )

    def _extract_critic_issues(
        self,
        raw: dict,
        critic_scores: CriticScores,
    ) -> list[FeedbackIssue]:
        """从 LLM 响应提取 issues + 用 _score_to_severity 计算 severity。"""
        all_scores = {
            "evidence": critic_scores.evidence,
            "specificity": critic_scores.specificity,
            "coherence": critic_scores.coherence,
            "actionability": critic_scores.actionability,
        }
        issues: list[FeedbackIssue] = []
        for dim in ("evidence", "specificity", "coherence", "actionability"):
            dim_data = raw.get(dim, {})
            for raw_issue in dim_data.get("issues", []):
                try:
                    issue_type = raw_issue.get("issue_type")
                    issue = FeedbackIssue(
                        agent=_map_issue_type_to_agent(issue_type),
                        field=raw_issue.get("field", "<unknown>"),
                        severity=_score_to_severity(all_scores[dim], all_scores),
                        reason=raw_issue.get("reason", ""),
                        suggestion=raw_issue.get("suggestion", ""),
                        dimension=dim,
                        issue_type=issue_type,
                    )
                    issues.append(issue)
                except (ValidationError, KeyError) as e:
                    logger.warning("[critic] issue 构造失败跳过：%s, raw=%s", e, raw_issue)
        return issues

    def _classify_error(self, e: Exception) -> str:
        """把异常分类成 error_code（spec v4 cycle3/C2）。"""
        msg = str(e).lower()
        if "json" in msg or isinstance(e, ValueError):
            return "json_parse_error"
        if "score" in msg and ("range" in msg or "le" in msg or "ge" in msg):
            return "score_out_of_range"
        if isinstance(e, KeyError):
            return "field_missing"
        return "unexpected_error"

    def _build_fallback_result(
        self,
        report: BaseReport,
        error_code: str,
    ) -> tuple[None, list[FeedbackIssue]]:
        """spec v4 cycle2/C3 + cycle3/C5 — 失败降级。

        生成 critic_failed critical issue（agent="end" terminal 路由）。
        None safe：metadata.warnings 可能 None → 用 list(... or []) 兜底。
        """
        # warnings 写入由调用方 inspect() 做（这里只产 issue）
        fallback_issue = FeedbackIssue(
            agent="end",  # spec v4 cycle3/C5：terminal 路由
            field="critic_check",
            severity="critical",  # spec v4 cycle3/C5
            reason=f"critic 系统故障：{error_code}（非报告内容问题）",
            suggestion="检查 critic LLM 配置 / 重新跑整个分析；不要让 writer 重写",
            dimension="critic_failed",
            issue_type="critic_failed",
        )
        return None, [fallback_issue]
```

- [ ] **Step 7: 运行测试确认通过**

Run: `pytest tests/unit/test_inspector_critic.py -v -k "critic_check"`
Expected: 4 PASS

- [ ] **Step 8: Commit**

```bash
git add src/agents/inspector.py tests/unit/test_inspector_critic.py
git commit -m "feat(critic): _critic_check 主流程（retry + fallback + broad except + 二次兜底）"
```

---

## Task 12: 删除旧组件 + 重写 inspect() 主入口

**Files:**
- Modify: `src/agents/inspector.py`（大改）
- Test: `tests/unit/test_inspector_critic.py`

- [ ] **Step 1: 写失败测试 — inspect() 端到端**

```python
@pytest.mark.asyncio
async def test_inspect_with_critic_replaces_quality_score(make_simple_report):
    """spec v4：inspect() 用 critic_score 完全替换旧三项。"""
    from src.agents.inspector import InspectorAgent
    from src.schemas.feedback import RejectionFeedback

    mock_llm_response = {
        "evidence": {"reasoning": [], "score": 3, "issues": []},
        "specificity": {"reasoning": [], "score": 3, "issues": []},
        "coherence": {"reasoning": [], "score": 3, "issues": []},
        "actionability": {"reasoning": [], "score": 3, "issues": []},
    }
    mock_llm = MagicMock()
    mock_llm.call_json = AsyncMock(return_value=mock_llm_response)

    inspector = InspectorAgent(llm=mock_llm)
    report = make_simple_report()

    feedback = await inspector.inspect(report, discovered_sources=[])

    # 全 3 分 → critic_score = 0.667
    assert report.metadata.quality_score == pytest.approx(0.667, abs=0.01)
    assert report.metadata.score_source == "critic"
    assert report.metadata.critic_scores is not None
    assert report.metadata.critic_scores.evidence == 3
    assert report.metadata.critic_prompt_version == "critic-prompt-v1.0.0"
    assert isinstance(feedback, RejectionFeedback)


@pytest.mark.asyncio
async def test_inspect_critic_failure_warnings_and_passed(make_simple_report):
    """spec v4：critic 失败 → critic_failed critical → passed=False + warnings + score_source=fallback。"""
    from src.agents.inspector import InspectorAgent

    mock_llm = MagicMock()
    mock_llm.call_json = AsyncMock(side_effect=RuntimeError("simulated critic failure"))

    inspector = InspectorAgent(llm=mock_llm)
    report = make_simple_report()

    feedback = await inspector.inspect(report, discovered_sources=[])

    # 失败降级
    assert report.metadata.score_source == "fallback"
    assert report.metadata.quality_score == 0.5
    assert report.metadata.critic_scores is None
    assert any("critic_failed" in w for w in (report.metadata.warnings or []))
    # spec v4 cycle3/C5：critic_failed → passed=False
    assert feedback.passed is False


@pytest.mark.asyncio
async def test_inspect_v3_r17_cap_removed(make_simple_report):
    """spec v4：v3-R17 cap 0.5 删除——placeholder warnings 不再 cap quality_score。"""
    from src.agents.inspector import InspectorAgent

    mock_llm_response = {
        "evidence": {"reasoning": [], "score": 4, "issues": []},
        "specificity": {"reasoning": [], "score": 4, "issues": []},
        "coherence": {"reasoning": [], "score": 4, "issues": []},
        "actionability": {"reasoning": [], "score": 4, "issues": []},
    }
    mock_llm = MagicMock()
    mock_llm.call_json = AsyncMock(return_value=mock_llm_response)

    inspector = InspectorAgent(llm=mock_llm)
    report = make_simple_report()
    # 加 placeholder warning（v3 会触发 cap，v4 应该不再）
    report.metadata.warnings = ["placeholder_section:overview:ValidationError"]

    await inspector.inspect(report, discovered_sources=[])

    # 全 4 分 → critic_score = 1.0；如果 cap 0.5 还在会被压回 0.5
    assert report.metadata.quality_score == pytest.approx(1.0, abs=0.01)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/unit/test_inspector_critic.py -v -k "test_inspect_with_critic or test_inspect_critic_failure or test_inspect_v3_r17"`
Expected: 3 FAIL

- [ ] **Step 3: 大改 inspector.py — 删除旧组件**

读 `src/agents/inspector.py` 全文，**删除以下组件**：

```python
# 删除：_QUALITY_SCORE_CAP_ON_PLACEHOLDER 常量
# 删除：_detect_placeholder_warnings 函数
# 删除：_check_warnings_prefix 函数
# 删除：_llm_check 方法（被 _critic_check 替换）
# 删除：旧的 inspect() 内 quality_score 计算（用旧三项的部分）
```

- [ ] **Step 4: 重写 inspect() 主入口**

```python
async def inspect(
    self,
    report: BaseReport,
    competitors: list[str] | None = None,
    retry_count: int = 0,
    max_retries: int = 2,
    discovered_sources: list[dict] | None = None,  # spec v4 cycle3/C3
) -> RejectionFeedback:
    """执行质检 + 回填 quality_score。spec v4 重写。

    competitors 参数保留兼容旧 graph 调用。
    discovered_sources 是 v4 新增——critic evidence rubric 需要 source title/snippet。
    """
    logger.info("[inspector] 开始质检 v4, scenario=%s, retry=%d", report.scenario, retry_count)
    _ = competitors  # 兼容 graph 旧 signature
    # spec v4 cycle3/C3：None safe
    discovered_sources = discovered_sources or []

    # Step 1: 程序硬查
    prog_issues = self._programmatic_checks(report)

    # Step 2: critic 评分（含 retry + fallback + broad except）
    critic_scores, critic_issues = await self._critic_check(report, discovered_sources)

    # Step 3: 合并 + 去重（key = (agent, field, dimension)）spec v3 cycle2/M3
    all_issues = prog_issues + critic_issues
    seen: dict[tuple[str, str, str | None], FeedbackIssue] = {}
    sev_rank = {"critical": 0, "major": 1, "minor": 2}
    for issue in sorted(all_issues, key=lambda i: sev_rank[i.severity]):
        key = (issue.agent, issue.field, issue.dimension)
        if key not in seen:
            seen[key] = issue
    unique_issues = list(seen.values())

    # Step 4: quality_score 计算
    if critic_scores is not None:
        quality_score = calc_critic_score(critic_scores)
        score_source = "critic"
        report.metadata.critic_scores = critic_scores
        report.metadata.critic_prompt_version = CRITIC_PROMPT_VERSION
    else:
        # fallback 路径
        quality_score = 0.5
        score_source = "fallback"
        report.metadata.critic_scores = None
        report.metadata.critic_prompt_version = None
        # 写 warnings（None safe，spec v3 cycle2/C3）
        existing_warnings = list(report.metadata.warnings or [])
        # 提取 error_code 从 critic_issues
        error_code = "unknown"
        for i in critic_issues:
            if i.issue_type == "critic_failed":
                # reason 里有 error_code，提取
                if "：" in i.reason:
                    error_code = i.reason.split("：")[1].split("（")[0].strip()
                break
        existing_warnings.append(f"critic_failed:{error_code}")
        report.metadata.warnings = existing_warnings

    # 写 metadata（spec v4 cycle3/C2：calculation_note 加 prog_issues 计数）
    report.metadata.quality_score = max(0.0, min(1.0, quality_score))
    report.metadata.score_source = score_source

    prog_critical = sum(1 for i in prog_issues if i.severity == "critical")
    prog_major = sum(1 for i in prog_issues if i.severity == "major")

    if critic_scores is not None:
        cs = critic_scores
        report.metadata.quality_score_calculation_note = (
            f"{CRITIC_PROMPT_VERSION} | "
            f"ev={cs.evidence} sp={cs.specificity} co={cs.coherence} ac={cs.actionability} "
            f"→ norm={quality_score:.3f} | "
            f"prog_issues={prog_critical} critical / {prog_major} major"
        )
    else:
        report.metadata.quality_score_calculation_note = (
            f"fallback | quality_score=0.5 | "
            f"prog_issues={prog_critical} critical / {prog_major} major"
        )

    # Step 5: passed 判定（spec v3 cycle2/M2）
    passed = not any(
        issue.severity in {"critical", "major"} for issue in unique_issues
    )

    feedback = RejectionFeedback(
        passed=passed,
        issues=unique_issues,
        retry_count=retry_count,
        max_retries=max_retries,
    )
    logger.info(
        "[inspector] 质检完成 v4, passed=%s, issues=%d (prog=%d, critic=%d), score=%.3f source=%s",
        passed, len(unique_issues), len(prog_issues), len(critic_issues),
        report.metadata.quality_score, score_source,
    )
    return feedback
```

- [ ] **Step 5: 删除 _programmatic_checks 里的 _check_warnings_prefix 调用**

修改 `_programmatic_checks` 方法：

```python
def _programmatic_checks(self, report: BaseReport) -> list[FeedbackIssue]:
    """通用硬查 + 场景硬查。
    spec v4：删除 _check_warnings_prefix（v3-R17 cap 一并删）。
    """
    return _check_common(report) + _dispatch_scenario_check(report)
```

并把 `_QUALITY_SCORE_CAP_ON_PLACEHOLDER` / `_detect_placeholder_warnings` / `_check_warnings_prefix` 全部删除。

- [ ] **Step 6: 运行新测试 + 检查老测试是否回归**

Run: `pytest tests/unit/test_inspector_critic.py -v`
Expected: 全部 PASS

Run: `pytest tests/ -x --tb=short`
Expected: 大部分 PASS；如果有 inspector 旧测试 fail（可能因为接口签名 / 旧逻辑变了），按需调整。**注意**：项目可能有 `tests/unit/test_inspector.py`，里面会引用 `_QUALITY_SCORE_CAP_ON_PLACEHOLDER` 等已删除符号 → 删除/调整这些测试。

- [ ] **Step 7: Commit**

```bash
git add src/agents/inspector.py tests/unit/test_inspector_critic.py tests/unit/test_inspector*.py
git commit -m "feat(critic): inspector.inspect() v4 重写（critic 接管 quality_score）+ 删除旧组件"
```

---

## Task 13: graph state + builder 改造

**Files:**
- Modify: `src/graph/state.py`
- Modify: `src/graph/builder.py`
- Test: `tests/unit/test_graph_critic_integration.py`（新建，集成测试）

- [ ] **Step 1: 修改 src/graph/state.py**

读 `src/graph/state.py` 看现有 `AnalysisState` 定义，在末尾追加：

```python
class AnalysisState(TypedDict):
    # ...现有字段...
    discovered_sources: list[dict]  # spec v4 cycle3/C3：[{"url", "title", "snippet"}]
```

注：TypedDict 字段不会强制存在（`total=True` 默认强制；用 `state.get(...)` 读才安全）。

- [ ] **Step 2: 修改 src/graph/builder.py — inspector_node 传 discovered_sources**

找到 `inspector_node` 函数：

```python
# spec v4 cycle3/C3 修订
async def inspector_node(state: AnalysisState):
    # ...现有逻辑...

    # v4 修订：传 discovered_sources，None safe
    discovered_sources = state.get("discovered_sources") or []
    feedback = await inspector.inspect(
        report,
        retry_count=state.get("retry_count", 0),
        max_retries=state.get("max_retries", 2),
        discovered_sources=discovered_sources,  # v4 新增
    )
    # ...现有逻辑...
```

- [ ] **Step 3: 修改 builder.py _should_continue 加 agent="end" 特判**

找到 `_should_continue` 函数（builder.py 大约 425 行附近），在 max_retries 检查**之前**加 critic_failed terminal 特判：

```python
def _should_continue(state) -> str:
    feedback = state.get("feedback")
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 2)

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

    # 取第一条 critical/major issue 的 agent 决定回边
    for issue in feedback.issues:
        if issue.severity in ("critical", "major"):
            target = issue.agent
            node_trace.append(f"reject->{target} ({issue.field})")
            return target
    return "end"
```

- [ ] **Step 4: 写集成测试**

创建 `tests/unit/test_graph_critic_integration.py`：

```python
"""graph + critic 集成测试（spec v4 cycle3/C3 + cycle3/C5）。"""
import pytest
from unittest.mock import AsyncMock, MagicMock


def test_inspector_node_handles_missing_discovered_sources():
    """spec v4 cycle3/C3：state 缺 discovered_sources 时不抛 KeyError。"""
    # 构造没有 discovered_sources 字段的旧 state
    state = {
        "report": ...,  # mock BaseReport
        # 故意不设 discovered_sources
    }
    # inspector_node 应能用 state.get(..., []) 兜底
    # ...具体实现根据 builder 接口
```

注：完整的 graph integration 测试比较重，**这个 task 只验证 builder 改动不抛异常**。完整 E2E 留 Task 17 验收阶段。

- [ ] **Step 5: 运行测试**

Run: `pytest tests/unit/test_graph_critic_integration.py -v`
Expected: PASS

- [ ] **Step 6: 跑全量测试看回归**

Run: `pytest tests/ -x --tb=short`
Expected: 大部分 PASS；可能 graph E2E 测试需调整传 `discovered_sources=[]` 或 mock。

- [ ] **Step 7: Commit**

```bash
git add src/graph/state.py src/graph/builder.py tests/unit/test_graph_critic_integration.py
git commit -m "feat(critic): graph state 加 discovered_sources + builder agent='end' 特判"
```

---

## Task 14: collector 保存 Tavily snippet

**Files:**
- Modify: `src/agents/collector.py` 或 `src/agents/collection_pipeline.py`
- Test: `tests/unit/test_collector.py`（追加）

- [ ] **Step 1: 找到 Tavily 搜索的代码位置**

```bash
grep -rn "tavily" src/agents/ src/tools/sources.py
```

找到 Tavily 返回结果处理的位置——通常在 `TavilySource.search()` 或类似方法。

- [ ] **Step 2: 写失败测试**

在 `tests/unit/test_collector.py` 末尾追加：

```python
def test_tavily_search_preserves_snippet():
    """spec v4 cycle3/M4：Tavily 返回的 content（snippet）字段必须保存到 discovered_sources。"""
    # mock Tavily 返回
    mock_tavily_response = {
        "results": [
            {
                "url": "https://example.com/page1",
                "title": "Example Page 1",
                "content": "This is the snippet content for evidence judgment",
            },
        ]
    }
    # ...调用 TavilySource → 验证 SearchResult 含 snippet 字段
```

- [ ] **Step 3: 修改 sources.py 保留 snippet**

如果 `SearchResult` 模型还没 snippet 字段，新增：

```python
class SearchResult(BaseModel):
    url: str
    title: str
    snippet: str = ""  # spec v4 cycle3/M4 新增
    # ...
```

并在 TavilySource 处理时 populate：

```python
results.append(SearchResult(
    url=item["url"],
    title=item.get("title", ""),
    snippet=item.get("content", ""),  # v4 新增
))
```

- [ ] **Step 4: 修改 collector.py / collection_pipeline.py 把 snippet 写到 state**

找 collector 把搜索结果汇总成 `discovered_urls` 的位置（grep `discovered_urls`），改成同时收集 `discovered_sources` list[dict]：

```python
discovered_sources = []
for sr in search_results:
    discovered_sources.append({
        "url": sr.url,
        "title": sr.title,
        "snippet": sr.snippet,
    })

# 返回时 collector 把 discovered_sources 也放进 state（builder.collector_node 写）
return {
    "profiles": profiles,
    # ...其他字段...
    "discovered_sources": discovered_sources,  # v4 新增
}
```

- [ ] **Step 5: builder.py collector_node 把 discovered_sources 写入 state**

```python
async def collector_node(state: AnalysisState):
    # ...现有逻辑...
    result = await collector.collect(...)
    return {
        # ...现有字段...
        "discovered_sources": result.get("discovered_sources", []),  # v4 强制 populate
    }
```

- [ ] **Step 6: 运行全量测试**

Run: `pytest tests/ -x --tb=short`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/agents/ src/tools/sources.py src/graph/builder.py tests/unit/test_collector.py
git commit -m "feat(critic): collector 保存 Tavily snippet 到 discovered_sources"
```

---

## Task 15: 清理旧 INSPECTOR_SYSTEM 常量

**Files:**
- Modify: `src/agents/prompts/__init__.py`

- [ ] **Step 1: 删除 INSPECTOR_SYSTEM 常量**

读 `src/agents/prompts/__init__.py`，删除 INSPECTOR_SYSTEM = """...""" 那段（spec v3 已说明搬到 inspector/critic.py）。

- [ ] **Step 2: 检查影响面**

```bash
grep -rn "INSPECTOR_SYSTEM" src/ tests/
```

应该已经无引用（inspector.py Task 12 改造时已经改用 CRITIC_SYSTEM）。如果有遗留，改掉。

- [ ] **Step 3: 跑全量测试**

Run: `pytest tests/ -x --tb=short`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add src/agents/prompts/__init__.py
git commit -m "refactor(prompts): 删除旧 INSPECTOR_SYSTEM 常量（已搬到 inspector/critic.py）"
```

---

## Task 16: pyproject.toml 加 pytest marker `eval`

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: 修改 pyproject.toml**

读 `pyproject.toml` 看现有 pytest 配置（应该有 `[tool.pytest.ini_options]` 节）。

在 markers 列表里加 eval：

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
markers = [
    "eval: 反例集 critic 判断力测试，依赖真 LLM 调用，不进 CI（手动 pytest -m eval）",
]
```

如果原来没 markers 节，整段加上。

- [ ] **Step 2: 验证 marker 配置**

Run: `pytest --markers | grep eval`
Expected: 看到 `@pytest.mark.eval: 反例集 critic 判断力测试...`

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "test(critic): 加 pytest marker eval 用于反例集测试（pytest -m eval 触发）"
```

---

## Task 17: 反例集 eval 测试

**Files:**
- Create: `tests/eval/__init__.py`
- Create: `tests/eval/test_critic_judgment.py`

- [ ] **Step 1: 创建 eval 测试包**

创建 `tests/eval/__init__.py`：（空文件，让 pytest discover 这个包）

- [ ] **Step 2: 创建 test_critic_judgment.py**

创建 `tests/eval/test_critic_judgment.py`：

```python
"""critic 判断力反例集测试（spec v4 测试第 3 层）。

CI 默认跳过（pyproject.toml @ eval marker），手动跑：
  pytest tests/eval/ -m eval

每个 fixture 是手工构造的"明显该低分"报告，期望 critic 给低分。
LLM 抽风时输出可能不稳定——eval 失败 = 提示人工检查 prompt 是否需要调整。

运行需要：
- 真实 LLM API key（.env DOUBAO_API_KEY 等）
- 网络访问

不在 CI 跑的原因：spec v4 cycle3/C6 — record/replay 实际不测 critic 判断力，
rubric 调整后录像失效但测试仍绿；本层是"人类对 critic 的抽查"，应手动跑、手动看 reasoning。
"""
import os
import pytest


pytestmark = pytest.mark.eval


@pytest.fixture
def real_inspector():
    """真实 LLM-backed inspector（不 mock）。"""
    if not os.environ.get("DOUBAO_API_KEY"):
        pytest.skip("DOUBAO_API_KEY 未配置，跳过真 LLM 测试")
    from src.agents.inspector import InspectorAgent
    from src.tools.llm_client import LLMClient
    return InspectorAgent(llm=LLMClient())


def make_report_all_placeholder():
    """全章节 placeholder 的报告 — 期望 specificity ≤ 2。"""
    # 构造 BaseReport，所有 narrative 都是 "原本应承载...因 LLM 失败自动生成占位..." 这种
    # ...具体构造（实施时按 schema 写）
    ...


def make_report_no_source_refs():
    """所有 finding 无 source_refs — 期望 evidence ≤ 1。"""
    ...


def make_report_third_party_only():
    """所有 source 全是 upmarket.co / spyingbee.com 等聚合站 — 期望 evidence ≤ 2。"""
    ...


def make_report_swot_self_contradiction():
    """SWOT.strengths 说 X 强 + vendor.cautions 说 X 弱 — 期望 coherence ≤ 2。"""
    ...


def make_report_vague_recommendations():
    """所有 recommendation 是 "加强 AI" / "持续关注" — 期望 actionability ≤ 1。"""
    ...


@pytest.mark.asyncio
async def test_eval_all_placeholder_low_specificity(real_inspector):
    """spec v4 验收 9：手动 eval 1/5 — placeholder 报告 specificity ≤ 2。"""
    report = make_report_all_placeholder()
    discovered_sources = [{"url": "https://x.com", "title": "x", "snippet": "x"}]
    critic_scores, _ = await real_inspector._critic_check(report, discovered_sources)
    assert critic_scores is not None, "critic 不应在反例集上 fallback"
    assert critic_scores.specificity <= 2, (
        f"全 placeholder 报告 specificity={critic_scores.specificity}，期望 ≤ 2"
    )


@pytest.mark.asyncio
async def test_eval_no_source_low_evidence(real_inspector):
    """spec v4 验收 9：手动 eval 2/5 — 无 source 报告 evidence ≤ 1。"""
    report = make_report_no_source_refs()
    critic_scores, _ = await real_inspector._critic_check(report, [])
    assert critic_scores is not None
    assert critic_scores.evidence <= 1, (
        f"无 source 报告 evidence={critic_scores.evidence}，期望 ≤ 1"
    )


@pytest.mark.asyncio
async def test_eval_third_party_only_low_evidence(real_inspector):
    """spec v4 验收 9：手动 eval 3/5 — 全聚合站报告 evidence ≤ 2。"""
    report = make_report_third_party_only()
    discovered_sources = [
        {"url": "https://upmarket.co", "title": "x", "snippet": "x"},
        {"url": "https://spyingbee.com", "title": "y", "snippet": "y"},
    ]
    critic_scores, _ = await real_inspector._critic_check(report, discovered_sources)
    assert critic_scores is not None
    assert critic_scores.evidence <= 2


@pytest.mark.asyncio
async def test_eval_swot_contradiction_low_coherence(real_inspector):
    """spec v4 验收 9：手动 eval 4/5 — SWOT 矛盾报告 coherence ≤ 2。"""
    report = make_report_swot_self_contradiction()
    critic_scores, _ = await real_inspector._critic_check(report, [])
    assert critic_scores is not None
    assert critic_scores.coherence <= 2


@pytest.mark.asyncio
async def test_eval_vague_recommendations_low_actionability(real_inspector):
    """spec v4 验收 9：手动 eval 5/5 — 套话建议报告 actionability ≤ 1。"""
    report = make_report_vague_recommendations()
    critic_scores, _ = await real_inspector._critic_check(report, [])
    assert critic_scores is not None
    assert critic_scores.actionability <= 1
```

注：5 个 `make_report_*` fixture 函数 **暂时留空**——实施这个 task 时按真实 BaseReport schema 构造。
spec v4 是"手动验收"清单，不强求 CI 跑通——5 个 fixture 都是 placeholder 也接受（人工实施 eval 时再补）。

- [ ] **Step 3: 验证 eval 测试默认不跑（CI 友好）**

Run: `pytest tests/ --tb=short` （不带 -m eval）
Expected: 不跑 eval 目录的测试

Run: `pytest tests/eval/ -m eval --collect-only`
Expected: 看到 5 个测试被 collect

- [ ] **Step 4: Commit**

```bash
git add tests/eval/
git commit -m "test(critic): 反例集 eval 框架（5 fixture 占位 + 手动 pytest -m eval 触发）"
```

---

## Task 18: 影响面 grep 验收脚本

**Files:**
- Create: `scripts/verify_no_legacy_quality_score.py`

- [ ] **Step 1: 创建验收脚本**

spec v4 cycle3/M8：grep 命令跨平台不可靠，改用 Python 脚本。

创建 `scripts/verify_no_legacy_quality_score.py`：

```python
"""spec v4 验收 8 — 影响面回归检查（cycle3/M8）。

旧三项 + cap 机制的 6 个符号必须在 src/ 下无遗留引用：
- calc_source_coverage
- calc_confidence_avg
- calc_inspector_pass_rate
- _QUALITY_SCORE_CAP_ON_PLACEHOLDER
- _detect_placeholder_warnings
- _check_warnings_prefix

CI 跑：python scripts/verify_no_legacy_quality_score.py
退出码 0 = 全清；非 0 = 有遗留引用，CI fail。
"""
import sys
from pathlib import Path

LEGACY_SYMBOLS = [
    "calc_source_coverage",
    "calc_confidence_avg",
    "calc_inspector_pass_rate",
    "_QUALITY_SCORE_CAP_ON_PLACEHOLDER",
    "_detect_placeholder_warnings",
    "_check_warnings_prefix",
]

SEARCH_DIRS = ["src"]


def main():
    repo_root = Path(__file__).parent.parent
    found_issues = []

    for search_dir in SEARCH_DIRS:
        target = repo_root / search_dir
        if not target.exists():
            continue
        for py_file in target.rglob("*.py"):
            try:
                content = py_file.read_text(encoding="utf-8")
            except Exception:
                continue
            for symbol in LEGACY_SYMBOLS:
                if symbol in content:
                    # 找到引用——记录文件 + 行号
                    for lineno, line in enumerate(content.splitlines(), 1):
                        if symbol in line:
                            found_issues.append((py_file, lineno, symbol, line.strip()))

    if found_issues:
        print("❌ 旧 quality_score 三项 / cap 机制 6 个符号有遗留引用：")
        for path, lineno, symbol, line in found_issues:
            print(f"  {path}:{lineno}  [{symbol}]  {line}")
        sys.exit(1)
    else:
        print("✅ 旧三项 / cap 机制无遗留引用（spec v4 验收 8 通过）")
        sys.exit(0)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 跑脚本验证**

Run: `python scripts/verify_no_legacy_quality_score.py`
Expected: `✅ 旧三项 / cap 机制无遗留引用` 退出码 0

如果有遗留 → Task 12 删除有问题 → 回头补。

- [ ] **Step 3: Commit**

```bash
git add scripts/verify_no_legacy_quality_score.py
git commit -m "test(critic): 影响面验收脚本 — 旧 quality_score 三项 + cap 6 符号无遗留"
```

---

## Task 19: 全量回归 + lint + 最终 commit

- [ ] **Step 1: 跑全量测试**

Run: `pytest tests/ --tb=short -m "not eval"`
Expected: 全 PASS / 0 failed

- [ ] **Step 2: ruff lint**

Run: `ruff check src tests scripts`
Expected: `All checks passed!`

如果有 lint error，按需修。

- [ ] **Step 3: 跑影响面验收脚本**

Run: `python scripts/verify_no_legacy_quality_score.py`
Expected: 退出码 0

- [ ] **Step 4: 检查未跟踪 / 未提交文件**

Run: `git status`
Expected: working tree clean（可能有少量改动需补 commit）

- [ ] **Step 5: 最终验收对照 spec v4**

把 spec v4 验收清单 1-8（CI required）逐条对照：

- [ ] 1. CI 测试全绿（`pytest -m "not eval"`）
- [ ] 2. lint 通过（`ruff check`）
- [ ] 3. 旧 trace 反序列化（test_v1_trace_can_be_loaded_with_v4_schema）
- [ ] 4. critic 失败降级（test_inspect_critic_failure_warnings_and_passed）
- [ ] 5. 新报告 metadata 含 critic_scores / score_source / critic_prompt_version
- [ ] 6. quality_score 永远 ∈ [0, 1]（test_calc_critic_score_clamps_to_unit_interval）
- [ ] 7. 本 PR diff 无 schema min_length / max_length 修改（手动 git diff 验证）
- [ ] 8. 影响面 grep 验收（`python scripts/verify_no_legacy_quality_score.py`）

如果都通过，进 Step 6 push。

- [ ] **Step 6: Push**

```bash
git push origin master
```

---

## Self-Review

按 writing-plans skill 要求，写完 plan 自审：

**1. Spec coverage**：
- ✅ 路线 A（critic 内嵌）：Task 6-12
- ✅ 4 维 rubric + CoT：Task 5
- ✅ 0.30/0.30/0.20/0.20 加权：Task 4
- ✅ 失败 retry+fallback+二次兜底：Task 11
- ✅ severity 映射：Task 6
- ✅ limited_pairs deterministic：Task 7
- ✅ deterministic 抽样：Task 8
- ✅ critic_inputs 含 title/snippet：Task 9 + Task 14
- ✅ Schema 改动：Task 1-2
- ✅ 旧组件删除：Task 12 + Task 15
- ✅ graph state + builder：Task 13
- ✅ 测试三层：Task 1-12（单元+集成）+ Task 17（eval）
- ✅ pytest marker：Task 16
- ✅ 影响面验收：Task 18
- ✅ 验收 1-8：Task 19

**2. Placeholder scan**：
- 5 个 `make_report_*` fixture 函数留空 — 标注 "实施时按 schema 构造"，spec 接受手动 eval 不强求完整
- Task 7 的 `make_simple_report` fixture 提到 "实施时复用 conftest"——这是合理简化（避免 plan 写完整 fixture）

**3. Type consistency**：
- CriticScores 字段名：evidence / specificity / coherence / actionability — 全 plan 一致
- FeedbackIssue 新增字段：dimension / issue_type — 全 plan 一致
- 函数签名 `_critic_check(report, discovered_sources)` — 全 plan 一致

无重大不一致。

---

## 待 plan 阶段消化（spec v4 文末清单）

实施过程中如果碰到这些问题再 patch（plan 没专门分 task）：

**Major（10 条）**：
- cycle3/M2 discovered_urls / discovered_sources 命名 — 全文 grep 改完
- cycle3/M3 source_mismatch 边界细化 — prompt 调整
- cycle3/M4 evidence support rate 分母 — _build_critic_inputs 加显式数据
- cycle3/M5 0 可用 pair 兜底改 None / programmatic issue — 视实测调整
- cycle3/M6 calc_critic_score dict 输入 defensive — 已在 Task 4 做了 try/except
- cycle3/M7 reasoning ≤80 字符代码裁剪 — _parse_critic_response 加 trim
- cycle3/M9 AnalysisState.discovered_sources TypedDict 子类型 — 见 Task 13
- cycle3/M10 deterministic guard — Task 18 的脚本提供了
- cycle3/M1 命名一致 / cycle3/M8 验收命令 — Task 18 已用 Python 脚本

**Minor（5 条）**：
plan 阶段写代码时碰到再补，文档级修订留 push 之后做。
