# Task 20/21 设计方案：Writer 4 阶段编排 + 5 套场景 prompt

> v1 起草于 2026-06-08，v2 整合双模型 doubt-driven 审查发现的 18 条问题。
> 原 v1 见 git 历史。本版本是落地依据。

## 背景与目标

R2 架构（Task 19 完成）下，BaseReport 通用骨架 + 5 场景 discriminated union 已落地。
Writer 阶段要把 LLM 单次 4-5K 字调用拆成多次小调用，目标产出 7000-8000 字咨询级报告。
本方案对应 plan 的 Task 20（5 套 4 阶段 prompt）+ Task 21（WriterOrchestrator 编排）。

## 已锁定的产品决策

- **Q1=C**：先用「writer 机械透传 analyzer.swot」保底，后续按 scenario 加 prompt 调整 SWOT 视角；本次方案落地的是 C 的「先用」一步
- **Q2=c（v2 修订，原 d 被审查证伪）**：metadata.confidence_level writer 阶段按「采集 completeness 平均值」派生：
  - completeness 平均 ≥ 0.8 → "high"
  - 0.5 ≤ 平均 < 0.8 → "medium"
  - 平均 < 0.5 → "low"
  - 推翻 d 的"保守 medium 起步"理由：inspector 是单向降档机制（按 issue 严重度倒推回填），从 medium 起步零 issue 时永远停留 medium 不会升 high → 业务语义破坏
- **P2=a**：phase 3 narrative 5-6 个 section 用 `asyncio.gather` 并行（section 间无依赖）
- **P3=a**：prompts 拆文件组织 `src/agents/prompts/writer/{outline,payload,narrative}/`

## 4 阶段总览

LLM 单次调用 4-5K 字上限 vs 报告字数目标 7-8K。拆成 4 阶段：

```
Phase 1 (1 次)         outline   骨架字段（title 至 recommendations，不含 swot/sections/payload）
Phase 2 (1 次)         payload   场景特有载荷 scenario_payload
Phase 3 (5-6 次并行)    narrative 各 analysis_section 的 narrative
Phase 4 (0 次 LLM)     assemble  代码合并 + 透传 SWOT + 聚合 source_refs + 构 ReportMetadata + BaseReport 校验
```

调用次数（成功路径）：S1 ≈ 7 次，S2-S5 ≈ 8 次。
**最坏情况熔断**：`WRITER_MAX_LLM_CALLS=15` 上限，超过 raise 走 graph 重试（M2）。

## Phase 1: outline（骨架）

### 输入预处理（C6 修订）
```python
competitor_names: list[str] = [c.name for c in scenario_input.competitors]
# 所有 prompt 字符串注入 + ReportScope.competitors 都用这个 list[str]，绝不直接传 list[CompetitorBasic]
```

### 输出 JSON 结构
（同 v1，省略未变部分）

字段额外加严约束（M6）：
- `key_findings[*].statement/evidence/implication` 各 ≥25 字（schema min=20，留 5 字缓冲）
- `executive_summary.context` 100-180 字（schema 80-200，留 20/20 缓冲）
- `executive_summary.implications` 130-220 字（schema 100-250）
- `recommendations[*].action/rationale` 各 ≥25 字

### Prompt 模板
（同 v1，但用 `{competitor_names_str}` 而非 `{competitors}`）

新增硬约束段：
```
【字数硬约束（不达标会被拒）】
- key_findings 每条三段式：statement/evidence/implication 各 25-80 字
- executive_summary.context 100-180 字
- executive_summary.implications 130-220 字
- recommendations 每条 action/rationale 各 25+ 字
```

### Token 估算（M3 修订）
中文 ≈ 1.5-1.8 char/token（不是 1:1）：
- 输入 ~5500 token（profiles 摘要 600 字 + analysis 摘要 800 字 + prompt 主干 2500 字 ≈ 3900 字 ÷1.5）
- 输出 ~2000 token（outline 1500 字 ÷1.5 + JSON 结构开销）
- 单次 ~7500 token，处于 Doubao 上下文范围内

### 失败处理（C9 修订）
```python
async def _call_with_validation(
    system_prompt, user_prompt, schema_cls, max_retries=1, max_tokens=4096,
) -> BaseModel:
    for attempt in range(max_retries + 1):
        raw = await self.llm.call_json(system_prompt, user_prompt, max_tokens=max_tokens)
        try:
            return schema_cls(**raw)
        except ValidationError as e:
            if attempt >= max_retries:
                raise
            error_summary = self._serialize_validation_error(e, max_chars=1500)
            user_prompt = f"{user_prompt}\n\n【上次校验失败，请修复】\n{error_summary}"
    # not reached
```

`_serialize_validation_error` 实现要点：
- `e.errors()[:5]`（前 5 条）
- 每条仅留 `loc / msg / type` 三字段
- json.dumps + ensure_ascii=False
- 最终截断到 1500 字符
- 测试断言：嵌套 5 层错误的 e 输出 ≤ 1500 字符

注：本方案需要在 `LLMClient.call_json` 增加可选 `max_tokens` 参数（M3）。修改是兼容的：缺省值 None 时不传 OpenAI SDK，保持现有行为。

## Phase 2: payload（场景特有载荷）

### 关键修订

**C5 — Phase 2 prompt 显式禁止编 evidence_url**（feature_matrix 等）：
```
【evidence_url 强约束】
- evidence_url 只能从下方 profiles_source_urls 列表中选，不在列表中的 URL 视为编造
- 若该项无来源，填 source_missing_reason="未在公开页发现"，不要写 evidence_url
- profiles_source_urls 列表（请只用这些）：{discovered_urls_json}
```

**C8 — SourceRef.source_type 显式枚举**：
```
【source_refs 字段约束】
SourceRef 对象 = {url, title, source_type, accessed_at}
- url：必须来自 profiles_source_urls
- title：未知时填空字符串 ""
- source_type：必须是 ["official_website","third_party_review","industry_report","news","user_review","regulatory","other"] 其一，不确定时填 "other"
- accessed_at：未知时省略
```

**C4 — S3 wtp_research 兜底**（normalizer 升级）：
更新 `src/agents/normalizers/s3.py`：normalizer 检测 `method=proxy_from_competitor_pricing` 且 `limitations` 缺失/为空时，自动填占位"基于公开竞品定价反推，未做正式 WTP 调研"。否则 model_validator 必抛。
其他场景 normalizer 同样审一遍：检查 model_validator 触发的字段强制依赖关系，正向兜底。

**M4 — S2 recommender 产物透传**：
S2 phase 2 prompt 把 `competitor_recommendations` 已确定的字段以**只读上下文**形式提供（不让 LLM 重写），但要求 `entry_strategy.target_segments` 与 recommended_competitors 中的"挑战者/新兴玩家"产生关联。

**M5 — S4 prior_report_data 不进 prompt**：
S4 phase 2 prompt 仅声明"假设这是首次/增量监控"。
prior_report_data 在 phase 4 assemble 阶段做 diff：
- 现期 monitored_competitors 与 prior 的差集 → `review_period.newly_added_competitors / dropped_competitors`
- prior 的 changes 不灌进 prompt，避免 FIATuple.fact 字段被污染

### Token 估算（M3 修订）
- 输入 ~6000 token（完整 analysis JSON ≈ 8000 字 ÷1.5 + prompt 主干）
- 输出 ~2500 token 上限（prompt 强制"分类不超过 5 个，每分类 features 不超过 6 行"压输出体积）
- max_tokens=4096 传 LLMClient

### Normalizer 接通
LLM 返回后用 Task 19 的 `normalize_for_scenario(scenario, raw)` 跑一遍，再实例化 `S{N}Payload(**cleaned)`。

### 失败处理
- normalize 后实例化 ValidationError → `_call_with_validation` 重试 1 次
- 仍失败 → raise，graph 走 writer 重试（最多 2 次）

## Phase 3: narrative（章节正文）

### 关键修订

**C2 — 占位长度 + 闸门双兜底**：
1. 占位 narrative 写死 ≥320 字符（heading 写死"【数据不足占位章节】"≥4 字符，narrative 写死固定文案 + 当时 payload 的 model_dump_json 截断 280 字符凑长度），内容大致：
   ```
   【本节因数据不足暂未生成深度分析】
   原因：phase 3 narrative 调用失败 ≥1 次重试。
   现有数据片段（供后续核查）：{payload_dump_truncated_280}
   建议：在 metadata.warnings 中查阅 placeholder_section: 标记定位失败原因。
   ```
2. metadata.warnings 加 `placeholder_section:{section_type}` 前缀，inspector 后续按前缀降 quality_score 到 ≤0.5
3. 硬闸门：成功 narrative 数 < ⌈expected_n / 2⌉ 时（即 5 个 section 失败 ≥3 / 6 个失败 ≥3）整体 raise，走 graph collector/analyzer 回边，避免"幽灵报告"通过校验

**C8 / C12 — narrative 输出的 source_refs 同样规范**：
- prompt 显式"找不到来源时 source_refs 留空数组 []，禁止编占位 url"
- phase 4 后置过滤：剔除 url 不在 `discovered_urls_set` 中的 SourceRef（M10）

**P2=a — 并行执行**：
```python
results = await asyncio.gather(
    *(self._phase3_one_section(scenario, st, outline, payload_dict, analysis)
      for st in section_types),
    return_exceptions=True,
)
sections, warnings = [], []
for st, r in zip(section_types, results):
    if isinstance(r, Exception):
        sections.append(self._build_placeholder_section(st, payload_dict))
        warnings.append(f"placeholder_section:{st}:{type(r).__name__}")
    else:
        sections.append(r)
```

并行优势：5-6 次串行 60-90s → 并行 ~15-20s（取最慢一次）。

### `_SECTION_CONTEXT_MAP`（M7 新增）
显式枚举每 section_type 取哪段 payload/analysis 字段：
```python
_SECTION_CONTEXT_MAP: dict[str, list[str]] = {
    "overview": ["analysis"],
    "vendor_profile_analysis": ["payload.vendor_profiles", "analysis.positioning"],
    "feature_matrix_analysis": ["payload.feature_matrix", "analysis.feature_matrix"],
    "jtbd_analysis": ["payload.job_statement", "analysis.user_sentiment"],
    "roadmap_analysis": ["payload.feature_gaps", "payload.roadmap_recommendations"],
    "market_sizing_analysis": ["payload.market_sizing"],
    "five_forces_analysis": ["payload.five_forces", "payload.industry_attractiveness_1_5"],
    "competitive_landscape_analysis": ["payload.players", "payload.market_concentration"],
    "trends_analysis": ["payload.key_trends"],
    "entry_strategy_analysis": ["payload.entry_strategy", "payload.competitor_recommendations"],
    "pricing_baseline_analysis": ["payload.pricing_baseline"],
    "value_drivers_analysis": ["payload.value_drivers", "payload.feature_classification"],
    "competitive_pricing_analysis": ["payload.competitive_pricing_matrix", "payload.pricing_page_audit"],
    "packaging_design_analysis": ["payload.packaging"],
    "pricing_recommendations_analysis": ["payload.recommendations_summary", "payload.rollout_plan"],
    "monitoring_overview": ["payload.review_period", "payload.trends"],
    "competitive_moves_analysis": ["payload.feature_changes", "payload.pricing_changes",
                                    "payload.messaging_changes", "payload.news_events", "payload.org_changes"],
    "threat_assessment_analysis": ["payload.threats"],
    "opportunity_identification_analysis": ["payload.opportunities", "payload.monitoring_actions"],
    "battlecard_analysis": ["payload.battlecards"],
    "vendor_positioning_analysis": ["payload.vendor_profiles"],
    "perceptual_map_analysis": ["payload.perceptual_map"],
    "strategy_canvas_analysis": ["payload.strategy_canvas", "payload.errc_grid", "payload.blue_ocean_move"],
    "errc_analysis": ["payload.errc_grid"],
    "positioning_statement_analysis": ["payload.positioning_statement", "payload.category_strategy"],
}
```

实现一个 `_dot_walk(obj, path)` 工具按路径取值。

## Phase 4: assemble（代码合并，0 LLM 调用）

### 1. 透传 SWOT（Q1=C 决策 + C7 修订）
```python
swot = analysis.swot if analysis.swot else _build_placeholder_swot()
```

`_build_placeholder_swot()`：4 象限各填 1 条 SwotEntry，文案保证字符数：
- point："采集数据不足，本象限暂未生成具体条目（占位）"（≥10 OK）
- evidence："见 metadata.warnings 中的采集警告说明"（≥10 OK）
- dimension="overall"

同时往 `metadata.warnings` 加 `placeholder_swot` 标记，inspector 降分。

### 2. 聚合 source_refs → metadata.data_sources（M1 + M10）
```python
def _collect_urls_recursive(obj: Any) -> set[str]:
    """递归 walk model_dump 后的 dict，收集所有 SourceRef-like 对象的 url。"""
    urls = set()
    if isinstance(obj, dict):
        if {"url", "source_type"} <= obj.keys():
            urls.add(obj["url"])
        for v in obj.values():
            urls |= _collect_urls_recursive(v)
    elif isinstance(obj, list):
        for item in obj:
            urls |= _collect_urls_recursive(item)
    return urls

# 后置过滤幻觉 url（M10）
discovered = {u for p in profiles for u in p.source_urls}
collected = _collect_urls_recursive({
    "outline": outline_dict, "payload": payload_dict,
    "sections": [s.model_dump() for s in sections], "swot": swot.model_dump(),
})
final_urls = collected & discovered  # 不在 profiles 的 url 全剔
```

**C3 修订（profiles 全无 URL 时）**：直接 raise `RuntimeError("profiles 中无 source_urls，无法构造可溯源报告")`，让 graph should_continue 走 collector 回边重新采集，**不在 writer 编 placeholder URL**。

### 3. 构 ReportMetadata（Q2=c 修订）
```python
avg_completeness = sum(p.metadata.completeness_score for p in profiles) / len(profiles)
if avg_completeness >= 0.8:
    confidence_level = "high"
elif avg_completeness >= 0.5:
    confidence_level = "medium"
else:
    confidence_level = "low"

metadata = ReportMetadata(
    report_id=f"r-{trace_id[:8]}",
    trace_id=trace_id,
    scenario=scenario,
    publication_date=date.today(),
    data_sources=[DataSource(url=u, confidence="medium") for u in sorted(final_urls)],
    confidence_level=confidence_level,
    contributing_agents=["collector", "analyzer", "writer"],
    warnings=warnings,
    quality_score_calculation_note="confidence_level 由采集 completeness 平均值派生",
)
```

注意：`confidence_level` 由 writer 派生后，inspector 不再回填该字段（避免双重写入语义混乱）；inspector 只回填 `quality_score`。

### 4. scope.competitors 兜底（C1 修订）
```python
if scenario_input.competitors:
    scope_competitors = [c.name for c in scenario_input.competitors]
elif scenario == "S2" and competitor_recommendations:
    scope_competitors = [r.name for r in competitor_recommendations.recommended_competitors]
else:
    raise RuntimeError(f"scope.competitors 无法构造：scenario={scenario}, recommender 也未产出")
```

### 5. 构 BaseReport
（同 v1）BaseReport 实例化时若 model_validator 失败 raise，graph 重试 writer。

## WriterOrchestrator 完整骨架

```python
class WriterOrchestrator:
    def __init__(self, llm: LLMClient):
        self.llm = llm
        self._call_counter = 0  # M2 熔断计数

    async def write(self, *, scenario, scenario_input, analysis, profiles,
                    analysis_goal=None, competitor_recommendations=None,
                    prior_report_data=None, trace_id="") -> BaseReport:
        self._call_counter = 0
        competitor_names = [c.name for c in scenario_input.competitors]  # C6
        discovered_urls = sorted({u for p in profiles for u in p.source_urls})

        if not discovered_urls:  # C3
            raise RuntimeError("profiles 中无 source_urls，无法构造可溯源报告")

        outline = await self._phase1_outline(
            scenario, scenario_input, analysis, profiles,
            competitor_names, discovered_urls,
        )
        payload_dict = await self._phase2_payload(
            scenario, scenario_input, analysis, profiles,
            competitor_recommendations, prior_report_data,
            competitor_names, discovered_urls,
        )
        payload_model = self._build_payload_model(scenario, payload_dict)

        sections, warnings = await self._phase3_narratives(
            scenario, outline, payload_dict, analysis, discovered_urls,
        )

        report = self._phase4_assemble(
            scenario, scenario_input, outline, payload_model, sections,
            profiles, analysis, trace_id, warnings,
            competitor_recommendations, discovered_urls, competitor_names,
        )
        return report

    async def _llm_call_with_quota(self, *args, **kwargs):
        """所有 LLM 调用走这里，超过 WRITER_MAX_LLM_CALLS=15 raise"""
        self._call_counter += 1
        if self._call_counter > 15:
            raise RuntimeError(f"writer LLM 调用超限 {self._call_counter} 次，疑似无限重试")
        return await self.llm.call_json(*args, **kwargs)
```

## Prompts 组织（P3=a 修订）

```
src/agents/prompts/
├── __init__.py            # re-export 旧 COLLECTOR_*/ANALYZER_*/INSPECTOR_SYSTEM 给现有代码
├── collector.py           # 旧 collector prompt 迁过来（最小搬动）
├── analyzer.py            # 同上
├── inspector.py           # 同上
└── writer/
    ├── __init__.py        # WRITER_OUTLINE_PROMPTS / WRITER_PAYLOAD_PROMPTS / WRITER_NARRATIVE_PROMPTS dict 在这里组装
    ├── outline/
    │   ├── s1.py          # S1_OUTLINE_PROMPT
    │   ├── s2.py
    │   ├── s3.py
    │   ├── s4.py
    │   └── s5.py
    ├── payload/
    │   └── s{1..5}.py     # S{N}_PAYLOAD_PROMPT
    └── narrative/
        ├── _common.py     # NARRATIVE_TEMPLATE 共用模板
        └── sections.py    # SECTION_LABELS / SECTION_FOCUS_HINTS dict（28 个 section_type）
```

旧 `src/agents/prompts.py` → 改为 `src/agents/prompts/__init__.py`，对外接口零变化。

旧 `WRITER_SYSTEM` 直接删除（plan Part 0 已宣告废除，git 历史是回滚通道，M9 不采纳）。

## 测试策略（M8 修订）

### Task 21（WriterOrchestrator）单测
1. **phase 1 outline 调用 + Pydantic 失败重试**：mock LLM 第 1 次返回缺字段，第 2 次 OK → 总调用 2 次
2. **phase 2 payload normalize 工作**：mock LLM 返回带 `weighted_scores` 的 S1 payload → normalize 删掉后实例化成功
3. **phase 3 narrative 单 section 失败局部降级**：mock 让第 3 个 section 抛错 → 返回 placeholder narrative ≥320 字 + warning 含 `placeholder_section:` 前缀
4. **phase 3 半数失败硬闸门 raise**：5 个 section 中 3 个抛错 → raise RuntimeError
5. **phase 4 SWOT 透传**：传入有 SWOT 的 analysis → `report.swot == analysis.swot`
6. **phase 4 SWOT 占位字符数**：analysis.swot=None → placeholder swot 4 象限各 1 条且字符数过校验
7. **phase 4 confidence_level 派生**：profiles completeness=[0.9,0.85] → high；=[0.6,0.5] → medium；=[0.3,0.2] → low
8. **phase 4 source_refs 聚合 + 幻觉过滤**：payload 含 1 个 profiles 外的 url → 不进 metadata.data_sources
9. **phase 4 profiles 全无 url → raise**
10. **phase 4 scope.competitors S2 兜底**：competitors=[]，但 recommender 产出 3 个 → scope.competitors 用 recommender 名单
11. **`_serialize_validation_error` ≤ 1500 字符**：嵌套 5 层 ValidationError 序列化 ≤ 1500
12. **调用次数熔断**：mock LLM 全失败 → 超 15 次 raise
13. **phase 3 并行**：mock LLM 每次 sleep 1s，5 个 section 总耗时 < 3s（证明并行）

### Task 20（prompts）
不写单测，由 Task 21 间接覆盖。但加 lint 测试：
- 5 个 OUTLINE/PAYLOAD/NARRATIVE prompt 文件都存在且 import 不报错
- `_SECTION_CONTEXT_MAP` 覆盖所有 28 个 section_type

## 落地拆分（v2 修订）

```
Task 20.0: src/tools/llm_client.py 加可选 max_tokens 参数（最小改动）
Task 20.1: src/agents/prompts/ 目录搬迁（旧文件→ __init__.py）
Task 20.2: src/agents/prompts/writer/outline/ 5 套
Task 20.3: src/agents/prompts/writer/payload/ 5 套
Task 20.4: src/agents/prompts/writer/narrative/ 模板 + sections 字典
Task 21.0: src/agents/normalizers/s3.py 升级（C4 wtp_research 兜底）+ 其他 normalizer 同审
Task 21.1: writer_orchestrator.py 骨架 + _call_with_validation 工具 + _serialize_validation_error
Task 21.2: phase 1 实现
Task 21.3: phase 2 实现（含 normalize 接通）
Task 21.4: phase 3 实现（asyncio.gather + 占位 + 半数闸门）
Task 21.5: phase 4 实现（SWOT 透传 + 递归 url 聚合 + confidence_level 派生 + scope 兜底 + raise 回边）
Task 21.6: 13 个单测全绿 + ruff
```

## 已修订决策清单（v2 vs v1）

| 编号 | 来源审查 | v1 倾向 | v2 决策 | 理由 |
|------|---------|--------|--------|------|
| C1 | 两审 | scope.competitors 直接透传 | S2 兜底从 recommender 取 | min_length=1 与空 list 矛盾 |
| C2 | 两审 | 占位 300 字 | 占位 ≥320 字 + warning + 半数闸门 | min_length=300 阈值漏检 |
| C3 | 两审 | placeholder URL | profiles 全无 url → raise 回 collector | 编 url 破坏溯源 |
| C4 | A | "Pydantic 报错走重试" | normalizer 主动补 limitations 占位 | 重试也修不了固定缺失 |
| C5 | A | 假设 analyzer 已填 feature_matrix | prompt 显式约束 evidence_url ∈ profiles，源问题留 worktree A 解决 | 跨 worktree 问题分隔 |
| C6 | A | prompt `{competitors}` 直注 | 入口预处理 list[str] | CompetitorBasic repr 污染 |
| C7 | A | placeholder swot 6 字符占位 | 改 ≥15 字符占位 | min_length=10 漏看 |
| C8 | A | LLM 自由填 source_type | prompt 列 7 枚举 + 兜底 "other" | 枚举校验抛错 |
| C9 | B | retry 直接灌 e | `_serialize_validation_error` ≤1500 字 | token 爆炸 |
| Q2 | A | d 保守 medium | c 按 completeness 派生 | inspector 单向降档冲突 |
| P2 | B | 串行 5-6 次 | asyncio.gather 并行 | 60-90s 超 FastAPI 默认超时 |
| P3 | B | dict 单文件 | prompts/ 目录拆文件 | 单文件超 1000 行难维护 |
| M1 | B | 硬遍历提 url | model_dump 后递归 walk | 5 场景嵌套差异大 |
| M2 | B | 不限调用次数 | WRITER_MAX_LLM_CALLS=15 熔断 | 最坏 42 次 |
| M3 | B | 估算偏低 | char/1.5 + max_tokens=4096 | 中文 token 比例 |
| M4 | B | recommender 产物 LLM 重写 | 只读上下文给 LLM | 双重幻觉 |
| M5 | B/A | prior_report 灌 prompt | phase 4 代码 diff | FIATuple.fact 污染 |
| M6 | A | schema min_length 直用 | prompt 加缓冲 5-20 字 | LLM 边界值不稳 |
| M7 | A | section context 落地时写 | spec 列 `_SECTION_CONTEXT_MAP` 28 项 | 临时写易错 |
| M8 | B/A | 仅成功路径计次断言 | 加局部失败/重试负向 case | 链路覆盖不全 |
| M10 | B | 仅 prompt 层约束 url | phase 4 后置过滤 | hallucination 兜底 |
