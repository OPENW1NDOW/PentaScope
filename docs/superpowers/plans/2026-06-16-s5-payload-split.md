# S5 Payload 拆分优化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 S5 writer phase 2 从单次 LLM 调用拆为两次（数据层 + 战略层），使 S5 PASS 率从 0% 提升到 >80%。

**Architecture:** Phase 2a 产出 vendor_profiles + perceptual_map + strategy_canvas，Phase 2b 产出 errc_grid + blue_ocean_move + positioning_statement + category_strategy。两层串行，各自独立校验和重试。merge 后运行 normalizer + 跨字段校验。错误反馈增强仅 S5 生效。

**Tech Stack:** Python, Pydantic v2, LangGraph, OpenAI SDK (MiMo)

---

## 文件结构

| 文件 | 操作 | 职责 |
|------|------|------|
| `src/agents/prompts/writer/payload/s5_phase2a.py` | 新建 | Phase 2a 数据层 prompt |
| `src/agents/prompts/writer/payload/s5_phase2b.py` | 新建 | Phase 2b 战略层 prompt |
| `src/agents/prompts/writer/payload/s5.py` | 修改 | 改为 import 两个新 prompt，保持 S5_PAYLOAD_PROMPT 向后兼容 |
| `src/agents/prompts/writer/payload/__init__.py` | 修改 | 新增 S5_PHASE2A/B_PROMPT 导出 |
| `src/agents/writer_orchestrator.py` | 修改 | 新增 S5 拆分方法 + 路由逻辑 + 错误反馈增强 |
| `tests/unit/test_writer_orchestrator.py` | 修改 | 新增 S5 拆分单测 |

---

### Task 1: 创建 s5_phase2a.py prompt

**Files:**
- Create: `src/agents/prompts/writer/payload/s5_phase2a.py`
- Reference: `src/agents/prompts/writer/payload/s5.py` (提取数据层部分)

- [ ] **Step 1: 创建 s5_phase2a.py**

从 `s5.py` 的 `S5_PAYLOAD_PROMPT` 提取 vendor_profiles / perceptual_map / strategy_canvas 相关约束，移除 errc_grid / blue_ocean_move / positioning_statement / category_strategy 部分。

```python
# src/agents/prompts/writer/payload/s5_phase2a.py
"""S5 战略定位场景 — Phase 2a 数据层 prompt。"""
from src.agents.prompts.writer.payload._common import SOURCE_REFS_PROTOCOL, SCHEMA_FIELD_CONSTRAINTS

S5_PHASE2A_PROMPT = f"""你是一个资深战略咨询顾问，正在产出 S5 战略定位场景的数据层载荷（Phase 2a）。

本阶段只产出 vendor_profiles、perceptual_map、strategy_canvas 三个模块。后续阶段会产出 errc_grid、blue_ocean_move、positioning_statement、category_strategy。

【返回 JSON 字段约束】

返回单个 JSON 对象，含以下字段：

- vendor_profiles: list[S5VendorProfile]（每个被分析的竞品 1 条）
  - competitor_name (≥1 字), is_self: bool（我方填 True，竞品填 False）
  - ability_to_execute_score: float (0-5)（执行能力，Gartner MQ 横轴）
  - ability_to_execute_rationale: str (≥50 字)
  - completeness_of_vision_score: float (0-5)（愿景完整度，纵轴）
  - completeness_of_vision_rationale: str (≥50 字)
  - **不要填 mq_quadrant**（代码自动派生）
  - overview: str (20-200 字)
  - strengths: 2-5 条 {{point (≥10), evidence (≥10), source_refs}}
  - cautions: 1-4 条 {{point, evidence, source_refs}}
  - source_refs: list[SourceRef], ≥1 条
- perceptual_map: PerceptualMap
  - artifact_id, artifact_type="perceptual_map", title
  - x_axis: PerceptualAxis {{attribute (≥4 字), low_label (≥2), high_label (≥2), scale_max (3-10, 默认 5), rationale (≥20)}}
  - y_axis: PerceptualAxis（**attribute 必须不同于 x_axis**）
  - plotted_brands: list[PlottedBrand], ≥3 条
    - competitor_name (≥1 字), is_self: bool
    - x_score / y_score: float (0 ≤ score ≤ axis.scale_max)
    - bubble_size_metric: float Optional
    - **confidence: "high" | "medium" | "low"（必填）**
    - **score_rationale: str (≥20 字)（必填）**
    - source_refs: list[SourceRef]
  - white_space: list[WhiteSpaceZone]（可空数组）
    - 每条含 `quadrant`（必须 "top_right" | "top_left" | "bottom_right" | "bottom_left" | "center" 5 选 1）+ `opportunity_description` (≥20 字)
  - cluster_zones: list[ClusterZone]（可空数组）
  - **display_watermark**（用默认值即可："基于公开信息 AI 推断，非客户调研真实分数"）
- strategy_canvas: StrategyCanvas
  - artifact_id, artifact_type="strategy_canvas", title
  - competitive_factors: list[CompetitiveFactor], 5-15 条
    - name (≥4 字), industry_avg_level: float (0-10)
  - value_curves: list[ValueCurve], ≥2 条
    - competitor_name (≥1), is_self: bool
    - **factor_levels: dict[str, float]，key 必须严格等于 competitive_factors 中所有 name 的集合**（多 1 个少 1 个都不允许）
    - 每个 value: 0-10
    - source_refs

【一致性约束】
- vendor_profiles[*].competitor_name 必须完全等于 perceptual_map.plotted_brands[*].competitor_name 集合
- vendor_profiles[*].competitor_name 必须完全等于 strategy_canvas.value_curves[*].competitor_name 集合
- is_self=True 的实体在所有结构中必须指向同一个 competitor_name

{SOURCE_REFS_PROTOCOL}

{SCHEMA_FIELD_CONSTRAINTS}

【S5 枚举速查】
- vendor_profiles[*].is_self: bool（我方=True, 竞品=False）
- perceptual_map.plotted_brands[*].confidence: high | medium | low
- white_space[*].quadrant: top_right | top_left | bottom_right | bottom_left | center
- perceptual_map.x_axis.attribute ≠ y_axis.attribute（两轴必须不同）

【高频踩坑】
- vendor_profiles[*].strengths：list 长度**必须 2-5 条**，每条 point ≥10 字、evidence ≥10 字
- vendor_profiles[*].cautions：list 长度**必须 1-4 条**
- vendor_profiles[*].overview：20-200 字
- vendor_profiles[*].ability_to_execute_rationale / completeness_of_vision_rationale：≥50 字
- perceptual_map 的 low_label / high_label：**≥2 字符**（"低""高" 单字会被拒）
- strategy_canvas.value_curves[*].factor_levels：dict key 必须**严格等于** competitive_factors 所有 name 集合

只返回 JSON 对象，不要 Markdown，不要解释。
"""
```

- [ ] **Step 2: 验证文件语法**

Run: `python -c "from src.agents.prompts.writer.payload.s5_phase2a import S5_PHASE2A_PROMPT; print(len(S5_PHASE2A_PROMPT))"`
Expected: 输出字符数（应 > 2000）

- [ ] **Step 3: Commit**

```bash
git add src/agents/prompts/writer/payload/s5_phase2a.py
git commit -m "feat(writer): S5 phase 2a 数据层 prompt"
```

---

### Task 2: 创建 s5_phase2b.py prompt

**Files:**
- Create: `src/agents/prompts/writer/payload/s5_phase2b.py`
- Reference: `src/agents/prompts/writer/payload/s5.py` (提取战略层部分)

- [ ] **Step 1: 创建 s5_phase2b.py**

从 `s5.py` 提取 errc_grid / blue_ocean_move / positioning_statement / category_strategy 部分。注入 competitive_factors 和 vendor_names 为动态上下文。

```python
# src/agents/prompts/writer/payload/s5_phase2b.py
"""S5 战略定位场景 — Phase 2b 战略层 prompt。"""
from src.agents.prompts.writer.payload._common import SOURCE_REFS_PROTOCOL, SCHEMA_FIELD_CONSTRAINTS

S5_PHASE2B_PROMPT = f"""你是一个资深战略咨询顾问，正在产出 S5 战略定位场景的战略层载荷（Phase 2b）。

数据层（vendor_profiles + perceptual_map + strategy_canvas）已由前序阶段产出。本阶段基于 strategy_canvas 的 competitive_factors 产出战略判断。

【上下文（前序阶段产出）】
{{phase2a_context}}

【返回 JSON 字段约束】

返回单个 JSON 对象，含以下字段：

- errc_grid: ERRCGrid
  - artifact_id, artifact_type="errc_grid", title
  - eliminate / reduce / raise_level / create: list[ERRCAction]（每条 factor (≥4) + rationale (≥20)）
  - 注意是 raise_level（不是 raise）
  - **factor 建议基于 strategy_canvas 的 competitive_factors，但允许合理扩展**
- blue_ocean_move: BlueOceanMove **（Optional，可省略整个字段）**
  - 如果省略，返回空对象 {{}} 或不包含此字段
  - 如果填写：
    - new_value_curve_summary (≥50)
    - focus_assessment ∈ {{focused, scattered, uncertain}}, focus_rationale (≥20)
    - divergence_assessment ∈ {{divergent, overlapping, uncertain}}, divergence_rationale (≥20)
    - compelling_tagline (10-40 字)
    - target_noncustomers: list[str], ≥1 条
- positioning_statement: PositioningStatement
  - target_customer (≥10 字), need_or_opportunity (≥10 字)
  - product_name (≥2 字), product_category (≥4 字)
  - key_benefit (≥20 字), primary_alternative (≥4 字)
  - primary_differentiation (≥20 字)
  - **confidence: "from_user_brief" | "llm_inferred" | "low_confidence"（必填）**
  - **不要填 full_statement_text**（代码自动拼装 + 加水印）
- category_strategy: CategoryStrategy（**必填**，schema 强制不可省略也不可传 null）
  - chosen_category: str (≥4 字)，明确我方所属或希望进入的品类
  - why_this_category: str (≥30 字)，说明选这个品类的理由
  - competitors_implied: list[str], ≥1 条，列出该品类隐含的关键竞品

{SOURCE_REFS_PROTOCOL}

{SCHEMA_FIELD_CONSTRAINTS}

【S5 枚举速查】
- errc_grid 的字段名是 raise_level（**不是 raise**）
- blue_ocean_move.focus_assessment: focused | scattered | uncertain
- blue_ocean_move.divergence_assessment: divergent | overlapping | uncertain
- positioning_statement.confidence: from_user_brief | llm_inferred | low_confidence

【高频踩坑】
- errc_grid 的 eliminate / reduce / raise_level / create 每条 factor ≥4 字、rationale ≥20 字
- blue_ocean_move 是 **Optional**——如果不确定，宁可省略也不要填不完整的内容
- category_strategy 必填（非 Optional），不可省略也不可传 null
- positioning_statement 每个字段都有最小字数要求，写完心里数一遍

只返回 JSON 对象，不要 Markdown，不要解释。
"""
```

- [ ] **Step 2: 验证文件语法**

Run: `python -c "from src.agents.prompts.writer.payload.s5_phase2b import S5_PHASE2B_PROMPT; print(len(S5_PHASE2B_PROMPT))"`
Expected: 输出字符数（应 > 1500）

- [ ] **Step 3: Commit**

```bash
git add src/agents/prompts/writer/payload/s5_phase2b.py
git commit -m "feat(writer): S5 phase 2b 战略层 prompt"
```

---

### Task 3: 更新 s5.py 和 __init__.py 导出

**Files:**
- Modify: `src/agents/prompts/writer/payload/s5.py`
- Modify: `src/agents/prompts/writer/payload/__init__.py`

- [ ] **Step 1: 修改 s5.py**

保持 `S5_PAYLOAD_PROMPT` 不变（向后兼容），新增 import。

```python
# 在 s5.py 末尾追加
from src.agents.prompts.writer.payload.s5_phase2a import S5_PHASE2A_PROMPT
from src.agents.prompts.writer.payload.s5_phase2b import S5_PHASE2B_PROMPT
```

- [ ] **Step 2: 修改 __init__.py**

新增两个 prompt 的导出。

```python
# 在 __init__.py 中追加 import 和 dict 条目
from src.agents.prompts.writer.payload.s5_phase2a import S5_PHASE2A_PROMPT
from src.agents.prompts.writer.payload.s5_phase2b import S5_PHASE2B_PROMPT

# WRITER_PAYLOAD_PROMPTS dict 不变（S5 仍指向 S5_PAYLOAD_PROMPT）
# 新增独立 dict 给拆分路径使用
S5_SPLIT_PROMPTS = {
    "phase2a": S5_PHASE2A_PROMPT,
    "phase2b": S5_PHASE2B_PROMPT,
}
```

- [ ] **Step 3: 验证 import**

Run: `python -c "from src.agents.prompts.writer.payload import S5_SPLIT_PROMPTS; print(list(S5_SPLIT_PROMPTS.keys()))"`
Expected: `['phase2a', 'phase2b']`

- [ ] **Step 4: Commit**

```bash
git add src/agents/prompts/writer/payload/s5.py src/agents/prompts/writer/payload/__init__.py
git commit -m "feat(writer): S5 split prompt 导出"
```

---

### Task 4: 增强 _serialize_validation_error

**Files:**
- Modify: `src/agents/writer_orchestrator.py:498-507`
- Test: `tests/unit/test_writer_orchestrator.py`

- [ ] **Step 1: 写失败测试**

在 `tests/unit/test_writer_orchestrator.py` 末尾追加：

```python
def test_serialize_validation_error_enhanced_s5():
    """S5 增强错误反馈：human-readable 字段路径 + 期望值。"""
    from pydantic import ValidationError
    from src.schemas.scenarios.s5 import S5PositioningPayload

    # 构造一个会触发 multiple errors 的 raw dict
    raw = {
        "scenario_type": "S5",
        "vendor_profiles": [{
            "competitor_name": "A",
            "ability_to_execute_score": 3.0,
            "ability_to_execute_rationale": "短",  # < 50 字
            "completeness_of_vision_score": 3.0,
            "completeness_of_vision_rationale": "短",  # < 50 字
            "overview": "短",  # < 20 字
            "strengths": [],  # < 2 条
            "cautions": [],
            "source_refs": [],
        }],
        "perceptual_map": {
            "artifact_id": "pm1", "artifact_type": "perceptual_map", "title": "t",
            "x_axis": {"attribute": "ab", "low_label": "低", "high_label": "高", "rationale": "test rationale long enough"},
            "y_axis": {"attribute": "cd", "low_label": "低", "high_label": "高", "rationale": "test rationale long enough"},
            "plotted_brands": [],
        },
        "strategy_canvas": {
            "artifact_id": "sc1", "artifact_type": "strategy_canvas", "title": "t",
            "competitive_factors": [],
            "value_curves": [],
        },
        "errc_grid": {"artifact_id": "e1", "artifact_type": "errc_grid", "title": "t"},
        "positioning_statement": {
            "target_customer": "短",
            "need_or_opportunity": "短",
            "product_name": "P",
            "product_category": "cat",
            "key_benefit": "短",
            "primary_alternative": "alt",
            "primary_differentiation": "短",
            "confidence": "llm_inferred",
        },
        "category_strategy": {
            "chosen_category": "cat",
            "why_this_category": "短",
            "competitors_implied": ["X"],
        },
    }

    try:
        S5PositioningPayload(**raw)
    except ValidationError as e:
        result = WriterOrchestrator._serialize_validation_error_enhanced(e)
        # 应包含人类可读的字段路径
        assert "vendor_profiles" in result or "strengths" in result
        # 应包含期望值描述（如 "≥2" 或 "至少"）
        assert "≥" in result or "至少" in result or "条" in result
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/unit/test_writer_orchestrator.py::test_serialize_validation_error_enhanced_s5 -xvs`
Expected: FAIL (方法不存在)

- [ ] **Step 3: 实现 _serialize_validation_error_enhanced**

在 `writer_orchestrator.py` 的 `_serialize_validation_error` 方法后追加：

```python
@staticmethod
def _serialize_validation_error_enhanced(e: ValidationError, max_chars: int = 2000) -> str:
    """S5 专用增强错误反馈：人类可读字段路径 + 期望值描述。"""
    _TYPE_HINTS = {
        "string_too_short": lambda err: f"长度不足（要求 ≥{err.get('ctx', {}).get('min_length', '?')} 字符）",
        "string_too_long": lambda err: f"长度超限（要求 ≤{err.get('ctx', {}).get('max_length', '?')} 字符）",
        "missing": lambda err: "必填字段缺失",
        "value_error": lambda err: err.get("msg", "校验失败"),
        "int_parsing": lambda err: "应为整数",
        "float_parsing": lambda err: "应为浮点数",
        "enum": lambda err: f"应为 {err.get('ctx', {}).get('expected', '指定值')} 之一",
        "date_from_datetime_parsing": lambda err: "日期格式无效",
        "less_than_equal": lambda err: f"应 ≤{err.get('ctx', {}).get('le', '?')}",
        "greater_than_equal": lambda err: f"应 ≥{err.get('ctx', {}).get('ge', '?')}",
    }

    errs = e.errors()[:8]
    lines = []
    for i, err in enumerate(errs, 1):
        loc = ".".join(str(p) for p in err["loc"])
        err_type = err.get("type", "")
        hint_fn = _TYPE_HINTS.get(err_type)
        hint = hint_fn(err) if hint_fn else err.get("msg", err_type)
        lines.append(f"{i}. {loc}: {hint}")

    text = "\n".join(lines)
    return text[:max_chars]
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/unit/test_writer_orchestrator.py::test_serialize_validation_error_enhanced_s5 -xvs`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/agents/writer_orchestrator.py tests/unit/test_writer_orchestrator.py
git commit -m "feat(writer): S5 增强错误反馈 _serialize_validation_error_enhanced"
```

---

### Task 5: 实现 _call_s5_phase2a

**Files:**
- Modify: `src/agents/writer_orchestrator.py`
- Test: `tests/unit/test_writer_orchestrator.py`

- [ ] **Step 1: 写失败测试**

```python
@pytest.mark.asyncio
async def test_s5_phase2a_produces_data_layer(monkeypatch):
    """S5 phase 2a 产出 vendor_profiles + perceptual_map + strategy_canvas。"""
    from src.agents.prompts.writer.payload import S5_SPLIT_PROMPTS

    mock_raw = {
        "vendor_profiles": [{
            "competitor_name": "TestComp",
            "is_self": False,
            "ability_to_execute_score": 3.5,
            "ability_to_execute_rationale": "这是足够长的执行能力评分理由，至少五十个字符的描述。" * 2,
            "completeness_of_vision_score": 4.0,
            "completeness_of_vision_rationale": "这是足够长的愿景完整度评分理由，至少五十个字符的描述。" * 2,
            "overview": "这是一个竞品概述，至少二十个字符的描述内容。",
            "strengths": [
                {"point": "优势一条足够长", "evidence": "证据一条足够长", "source_refs": [{"url": "https://a.com", "title": "t", "source_type": "other"}]},
                {"point": "优势二条足够长", "evidence": "证据二条足够长", "source_refs": [{"url": "https://a.com", "title": "t", "source_type": "other"}]},
            ],
            "cautions": [
                {"point": "风险一条足够长", "evidence": "证据一条足够长", "source_refs": [{"url": "https://a.com", "title": "t", "source_type": "other"}]},
            ],
            "source_refs": [{"url": "https://a.com", "title": "t", "source_type": "other"}],
        }],
        "perceptual_map": {
            "artifact_id": "pm1", "artifact_type": "perceptual_map", "title": "感知地图",
            "x_axis": {"attribute": "易用性", "low_label": "低端", "high_label": "高端", "rationale": "这是轴的rationale至少二十字"},
            "y_axis": {"attribute": "功能深度", "low_label": "基础", "high_label": "全面", "rationale": "这是轴的rationale至少二十字"},
            "plotted_brands": [{
                "competitor_name": "TestComp", "is_self": False,
                "x_score": 3.5, "y_score": 4.0, "confidence": "medium",
                "score_rationale": "这是评分理由至少二十个字符的描述",
            }],
        },
        "strategy_canvas": {
            "artifact_id": "sc1", "artifact_type": "strategy_canvas", "title": "战略画布",
            "competitive_factors": [
                {"name": "易用性", "industry_avg_level": 5.0},
                {"name": "功能深度", "industry_avg_level": 6.0},
                {"name": "价格竞争力", "industry_avg_level": 4.0},
                {"name": "生态整合", "industry_avg_level": 3.0},
                {"name": "品牌影响力", "industry_avg_level": 7.0},
            ],
            "value_curves": [{
                "competitor_name": "TestComp", "is_self": False,
                "factor_levels": {"易用性": 3.5, "功能深度": 4.0, "价格竞争力": 5.0, "生态整合": 2.0, "品牌影响力": 6.0},
            }],
        },
    }

    orchestrator = WriterOrchestrator(llm=MagicMock())
    monkeypatch.setattr(orchestrator, "_llm_call_with_quota", AsyncMock(return_value=mock_raw))

    result = await orchestrator._call_s5_phase2a(
        scenario_input=MagicMock(),
        analysis=MagicMock(),
        profiles=[],
        competitor_names=["TestComp"],
        competitor_basics=[{"name": "TestComp"}],
        discovered_urls=["https://a.com"],
    )

    assert "vendor_profiles" in result
    assert "perceptual_map" in result
    assert "strategy_canvas" in result
    assert len(result["vendor_profiles"]) == 1
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/unit/test_writer_orchestrator.py::test_s5_phase2a_produces_data_layer -xvs`
Expected: FAIL (方法不存在)

- [ ] **Step 3: 实现 _call_s5_phase2a**

在 `writer_orchestrator.py` 的 `_call_phase2_with_validation` 方法前追加：

```python
async def _call_s5_phase2a(
    self,
    *,
    scenario_input: ScenarioInput,
    analysis: Any,
    profiles: list[CompetitorProfile],
    competitor_names: list[str],
    competitor_basics: list[dict],
    discovered_urls: list[str],
    max_retries: int = 2,
    max_tokens: int = 8192,
) -> dict:
    """S5 Phase 2a：数据层 LLM 调用，产出 vendor_profiles + perceptual_map + strategy_canvas。"""
    from src.agents.prompts.writer.payload import S5_SPLIT_PROMPTS
    from src.schemas.scenarios.s5 import S5VendorProfile, PerceptualMap, StrategyCanvas

    system_prompt = S5_SPLIT_PROMPTS["phase2a"]
    base_user_prompt = self._build_phase2_user_prompt(
        "S5", scenario_input, analysis, profiles,
        competitor_recommendations=None,
        competitor_names=competitor_names,
        competitor_basics=competitor_basics,
        discovered_urls=discovered_urls,
    )
    last_error_summary: str | None = None

    for attempt in range(max_retries + 1):
        current_user_prompt = base_user_prompt
        if last_error_summary:
            current_user_prompt = f"{base_user_prompt}\n\n【上次校验失败，请修复】\n{last_error_summary}"

        raw = await self._llm_call_with_quota(system_prompt, current_user_prompt, max_tokens=max_tokens)

        try:
            # 逐模块校验
            for vp in raw.get("vendor_profiles", []):
                S5VendorProfile(**vp)
            PerceptualMap(**raw.get("perceptual_map", {}))
            StrategyCanvas(**raw.get("strategy_canvas", {}))
            logger.info("[writer] S5 phase 2a 数据层校验通过")
            return raw
        except ValidationError as e:
            if attempt >= max_retries:
                raise
            last_error_summary = self._serialize_validation_error_enhanced(e, max_chars=2000)
            logger.warning("[writer] S5 phase 2a ValidationError 重试: %s", last_error_summary[:400])
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/unit/test_writer_orchestrator.py::test_s5_phase2a_produces_data_layer -xvs`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/agents/writer_orchestrator.py tests/unit/test_writer_orchestrator.py
git commit -m "feat(writer): S5 phase 2a 数据层调用"
```

---

### Task 6: 实现 _call_s5_phase2b

**Files:**
- Modify: `src/agents/writer_orchestrator.py`
- Test: `tests/unit/test_writer_orchestrator.py`

- [ ] **Step 1: 写失败测试**

```python
@pytest.mark.asyncio
async def test_s5_phase2b_produces_strategy_layer(monkeypatch):
    """S5 phase 2b 产出 errc_grid + positioning_statement + category_strategy。"""
    mock_raw = {
        "errc_grid": {
            "artifact_id": "e1", "artifact_type": "errc_grid", "title": "ERRC",
            "eliminate": [{"factor": "低效功能", "rationale": "这是消除理由至少二十个字符"}],
            "reduce": [{"factor": "冗余流程", "rationale": "这是减少理由至少二十个字符"}],
            "raise_level": [{"factor": "易用性", "rationale": "这是提升理由至少二十个字符"}],
            "create": [{"factor": "智能辅助", "rationale": "这是创造理由至少二十个字符"}],
        },
        "positioning_statement": {
            "target_customer": "目标客户足够长的描述",
            "need_or_opportunity": "需求足够长的描述",
            "product_name": "产品",
            "product_category": "品类足够长",
            "key_benefit": "关键利益足够长的描述",
            "primary_alternative": "替代品",
            "primary_differentiation": "差异化足够长的描述",
            "confidence": "llm_inferred",
        },
        "category_strategy": {
            "chosen_category": "智能协作工具",
            "why_this_category": "选择此品类的理由至少三十个字符的详细描述说明",
            "competitors_implied": ["竞品A"],
        },
    }

    orchestrator = WriterOrchestrator(llm=MagicMock())
    monkeypatch.setattr(orchestrator, "_llm_call_with_quota", AsyncMock(return_value=mock_raw))

    result = await orchestrator._call_s5_phase2b(
        phase2a_output={"competitive_factors": [{"name": "易用性"}, {"name": "功能深度"}], "vendor_profiles": [{"competitor_name": "A"}]},
        scenario_input=MagicMock(),
        analysis=MagicMock(),
        discovered_urls=["https://a.com"],
    )

    assert "errc_grid" in result
    assert "positioning_statement" in result
    assert "category_strategy" in result
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/unit/test_writer_orchestrator.py::test_s5_phase2b_produces_strategy_layer -xvs`
Expected: FAIL

- [ ] **Step 3: 实现 _call_s5_phase2b**

```python
async def _call_s5_phase2b(
    self,
    *,
    phase2a_output: dict,
    scenario_input: ScenarioInput,
    analysis: Any,
    discovered_urls: list[str],
    max_retries: int = 2,
    max_tokens: int = 8192,
) -> dict:
    """S5 Phase 2b：战略层 LLM 调用，产出 errc_grid + blue_ocean_move + positioning_statement + category_strategy。"""
    from src.agents.prompts.writer.payload import S5_SPLIT_PROMPTS
    from src.schemas.scenarios.s5 import ERRCGrid, PositioningStatement, CategoryStrategy

    system_prompt = S5_SPLIT_PROMPTS["phase2b"]

    # 构建 phase2a 上下文摘要
    factors = [f["name"] for f in phase2a_output.get("strategy_canvas", {}).get("competitive_factors", [])]
    vendor_names = [vp["competitor_name"] for vp in phase2a_output.get("vendor_profiles", [])]
    phase2a_context = f"competitive_factors: {factors}\nvendor_names: {vendor_names}"

    base_user_prompt = (
        f"=== 前序阶段产出 ===\n{phase2a_context}\n\n"
        + self._build_phase2_user_prompt(
            "S5", scenario_input, analysis, [],
            competitor_recommendations=None,
            competitor_names=vendor_names,
            competitor_basics=[{"name": n} for n in vendor_names],
            discovered_urls=discovered_urls,
        )
    )
    last_error_summary: str | None = None

    for attempt in range(max_retries + 1):
        current_user_prompt = base_user_prompt
        if last_error_summary:
            current_user_prompt = f"{base_user_prompt}\n\n【上次校验失败，请修复】\n{last_error_summary}"

        raw = await self._llm_call_with_quota(system_prompt, current_user_prompt, max_tokens=max_tokens)

        try:
            # 逐模块校验（blue_ocean_move Optional 跳过）
            if raw.get("errc_grid"):
                ERRCGrid(**raw["errc_grid"])
            if raw.get("blue_ocean_move"):
                from src.schemas.scenarios.s5 import BlueOceanMove
                BlueOceanMove(**raw["blue_ocean_move"])
            PositioningStatement(**raw.get("positioning_statement", {}))
            CategoryStrategy(**raw.get("category_strategy", {}))
            logger.info("[writer] S5 phase 2b 战略层校验通过")
            return raw
        except ValidationError as e:
            if attempt >= max_retries:
                raise
            last_error_summary = self._serialize_validation_error_enhanced(e, max_chars=2000)
            logger.warning("[writer] S5 phase 2b ValidationError 重试: %s", last_error_summary[:400])
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/unit/test_writer_orchestrator.py::test_s5_phase2b_produces_strategy_layer -xvs`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/agents/writer_orchestrator.py tests/unit/test_writer_orchestrator.py
git commit -m "feat(writer): S5 phase 2b 战略层调用"
```

---

### Task 7: 实现 _merge_s5_payload + 路由逻辑

**Files:**
- Modify: `src/agents/writer_orchestrator.py`
- Test: `tests/unit/test_writer_orchestrator.py`

- [ ] **Step 1: 写失败测试**

```python
@pytest.mark.asyncio
async def test_s5_split_merge_produces_valid_payload(monkeypatch):
    """S5 拆分 merge 后产出合法 S5PositioningPayload。"""
    from src.schemas.scenarios.s5 import S5PositioningPayload

    phase2a = {
        "vendor_profiles": [{
            "competitor_name": "Comp", "is_self": False,
            "ability_to_execute_score": 3.0,
            "ability_to_execute_rationale": "理由" * 20,
            "completeness_of_vision_score": 3.0,
            "completeness_of_vision_rationale": "理由" * 20,
            "overview": "概述至少二十个字符",
            "strengths": [
                {"point": "优势一条足够长", "evidence": "证据一条足够长", "source_refs": [{"url": "https://a.com", "title": "t", "source_type": "other"}]},
                {"point": "优势二条足够长", "evidence": "证据二条足够长", "source_refs": [{"url": "https://a.com", "title": "t", "source_type": "other"}]},
            ],
            "cautions": [{"point": "风险一条足够长", "evidence": "证据一条足够长", "source_refs": [{"url": "https://a.com", "title": "t", "source_type": "other"}]}],
            "source_refs": [{"url": "https://a.com", "title": "t", "source_type": "other"}],
        }],
        "perceptual_map": {
            "artifact_id": "pm1", "artifact_type": "perceptual_map", "title": "t",
            "x_axis": {"attribute": "易用性", "low_label": "低端", "high_label": "高端", "rationale": "rationale至少二十字"},
            "y_axis": {"attribute": "功能深度", "low_label": "基础", "high_label": "全面", "rationale": "rationale至少二十字"},
            "plotted_brands": [{"competitor_name": "Comp", "is_self": False, "x_score": 3.0, "y_score": 3.0, "confidence": "medium", "score_rationale": "rationale至少二十字"}],
        },
        "strategy_canvas": {
            "artifact_id": "sc1", "artifact_type": "strategy_canvas", "title": "t",
            "competitive_factors": [{"name": "易用性", "industry_avg_level": 5.0}, {"name": "功能深度", "industry_avg_level": 5.0}, {"name": "价格", "industry_avg_level": 5.0}, {"name": "生态", "industry_avg_level": 5.0}, {"name": "品牌", "industry_avg_level": 5.0}],
            "value_curves": [{"competitor_name": "Comp", "is_self": False, "factor_levels": {"易用性": 3.0, "功能深度": 3.0, "价格": 3.0, "生态": 3.0, "品牌": 3.0}}],
        },
    }
    phase2b = {
        "errc_grid": {"artifact_id": "e1", "artifact_type": "errc_grid", "title": "t"},
        "positioning_statement": {
            "target_customer": "目标客户足够长", "need_or_opportunity": "需求足够长",
            "product_name": "P", "product_category": "品类长",
            "key_benefit": "利益足够长", "primary_alternative": "替代",
            "primary_differentiation": "差异化足够长", "confidence": "llm_inferred",
        },
        "category_strategy": {"chosen_category": "品类足够长", "why_this_category": "理由至少三十个字符描述", "competitors_implied": ["Comp"]},
    }

    orchestrator = WriterOrchestrator(llm=MagicMock())
    result = orchestrator._merge_s5_payload(phase2a, phase2b)
    # 应能成功实例化
    model = S5PositioningPayload(**result)
    assert model.scenario_type == "S5"
    assert len(model.vendor_profiles) == 1
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/unit/test_writer_orchestrator.py::test_s5_split_merge_produces_valid_payload -xvs`
Expected: FAIL

- [ ] **Step 3: 实现 _merge_s5_payload**

```python
def _merge_s5_payload(self, phase2a: dict, phase2b: dict) -> dict:
    """合并 S5 phase 2a + 2b 为完整的 S5PositioningPayload dict。"""
    merged = {
        "scenario_type": "S5",
        "vendor_profiles": phase2a.get("vendor_profiles", []),
        "perceptual_map": phase2a.get("perceptual_map", {}),
        "strategy_canvas": phase2a.get("strategy_canvas", {}),
        "errc_grid": phase2b.get("errc_grid", {}),
        "positioning_statement": phase2b.get("positioning_statement", {}),
        "category_strategy": phase2b.get("category_strategy", {}),
    }
    # blue_ocean_move Optional：有则加，无则不加
    if phase2b.get("blue_ocean_move"):
        merged["blue_ocean_move"] = phase2b["blue_ocean_move"]

    # 补充 artifact_id（如果 LLM 遗漏）
    for key in ("perceptual_map", "strategy_canvas", "errc_grid"):
        if isinstance(merged.get(key), dict) and "artifact_id" not in merged[key]:
            merged[key]["artifact_id"] = f"{key}_auto"

    return merged
```

- [ ] **Step 4: 实现路由逻辑**

修改 `_call_phase2_with_validation` 的开头，增加 S5 分支：

```python
async def _call_phase2_with_validation(self, *, scenario, ...):
    """Phase 2 LLM call → normalize → 注入 → 实例化场景 Payload schema。"""
    # S5 拆分路径
    if scenario == "S5":
        return await self._call_s5_phase2_split(
            scenario_input=scenario_input,
            analysis=analysis,
            profiles=profiles,
            competitor_recommendations=competitor_recommendations,
            prior_report_data=prior_report_data,
            competitor_names=competitor_names,
            competitor_basics=competitor_basics,
            discovered_urls=discovered_urls,
            warnings=warnings,
        )

    # S1~S4 原有路径（不变）
    base_user_prompt = self._build_phase2_user_prompt(...)
    ...
```

新增 `_call_s5_phase2_split` 方法：

```python
async def _call_s5_phase2_split(
    self,
    *,
    scenario_input: ScenarioInput,
    analysis: Any,
    profiles: list[CompetitorProfile],
    competitor_recommendations: Any,
    prior_report_data: Optional[dict],
    competitor_names: list[str],
    competitor_basics: list[dict],
    discovered_urls: list[str],
    warnings: list[str],
) -> Any:
    """S5 专用：phase 2a + 2b 拆分调用 → merge → normalize → 实例化。"""
    # Phase 2a
    phase2a_raw = await self._call_s5_phase2a(
        scenario_input=scenario_input,
        analysis=analysis,
        profiles=profiles,
        competitor_names=competitor_names,
        competitor_basics=competitor_basics,
        discovered_urls=discovered_urls,
    )

    # Phase 2b
    phase2b_raw = await self._call_s5_phase2b(
        phase2a_output=phase2a_raw,
        scenario_input=scenario_input,
        analysis=analysis,
        discovered_urls=discovered_urls,
    )

    # Merge
    merged = self._merge_s5_payload(phase2a_raw, phase2b_raw)

    # Normalize（仅 merge 后运行一次）
    discovered_set = set(discovered_urls)
    cleaned = normalize_for_scenario("S5", merged, discovered_urls=discovered_set, warnings=warnings)

    # 实例化
    from src.schemas.scenarios.s5 import S5PositioningPayload
    payload_model = S5PositioningPayload(**cleaned)
    logger.info("[writer] S5 phase 2 拆分完成: vendor=%d, factors=%d",
                len(payload_model.vendor_profiles),
                len(payload_model.strategy_canvas.competitive_factors))
    return payload_model
```

- [ ] **Step 5: 运行测试确认通过**

Run: `python -m pytest tests/unit/test_writer_orchestrator.py::test_s5_split_merge_produces_valid_payload -xvs`
Expected: PASS

- [ ] **Step 6: 运行全量回归**

Run: `python -m pytest tests/ -x --tb=short`
Expected: 443+ passed (原测试不减少)

- [ ] **Step 7: Commit**

```bash
git add src/agents/writer_orchestrator.py tests/unit/test_writer_orchestrator.py
git commit -m "feat(writer): S5 phase 2 拆分完整路径 + 路由 + merge"
```

---

### Task 8: 端到端验证

- [ ] **Step 1: 运行全量测试**

Run: `python -m pytest tests/ -x --tb=short`
Expected: 443+ passed, ruff clean

- [ ] **Step 2: 启动后端 + 前端，手动跑 S5 场景**

输入：Notion vs 飞书文档 vs 语雀，S5 战略定位场景。验证：
1. Phase 2a 和 2b 各自成功（看日志）
2. 报告完整产出（03_report.json 存在）
3. quality_score ≥ 0.7
4. 总耗时 < 15 分钟

- [ ] **Step 3: Commit 最终状态**

```bash
git add -A
git commit -m "feat: S5 payload 拆分优化完成"
```
