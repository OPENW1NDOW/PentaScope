# Task 20/21 设计方案：Writer 4 阶段编排 + 5 套场景 prompt

> v1 起草于 2026-06-08，v2 整合首轮双模型 doubt-driven 审查（18 条）。
> v3 起草于 2026-06-08（晚），整合第二轮双模型 doubt-driven 审查（28 条 reconciled：11 critical + 12 major + 5 minor）。
> 协作模型从「双 worktree 并行」切换到「单 session 单线」后重审。
> 原 v1/v2 见 git 历史。本版本（v3）是落地依据。
>
> **v3 修订点用 `[v3-RXX]` 标记并嵌入对应章节**。文末有完整 v3 修订日志表。

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

### 输入预处理（C6 修订 + [v3-R01] 字段名修正 + [v3-R26] 结构信息保留）
```python
# [v3-R01] master src/schemas/profile.py 没有 CompetitorProfile.source_urls，正确字段是 metadata.data_sources（list[str]）。
# 跨场景统一用 collect_profile_urls 收集（含 metadata.data_sources + nested source_url 字段如 RecentUpdate.source_url）。
def collect_profile_urls(profile: CompetitorProfile) -> set[str]:
    urls: set[str] = set()
    urls.update(profile.metadata.data_sources or [])
    for ru in profile.recent_updates:
        if ru.source_url:
            urls.add(ru.source_url)
    for sr in profile.user_reviews.sample_reviews:
        if getattr(sr, "source_url", None):
            urls.add(sr.source_url)
    return urls

discovered_urls = sorted({u for p in profiles for u in collect_profile_urls(p)})

# 入口预处理（C6）
competitor_names: list[str] = [c.name for c in scenario_input.competitors]
# [v3-R26] 不只丢 names；保留结构供 prompt 注入（不直接 repr Pydantic 对象，而是 model_dump）
competitor_basics: list[dict] = [c.model_dump(exclude_none=True) for c in scenario_input.competitors]
# 产品/行业/我方信息也独立透传
our_product_brief = {
    "name": scenario_input.our_product_name or "",
    "brief": scenario_input.our_product_brief or "",
    "industry": scenario_input.industry or "",
}
```

### 输出 JSON 结构（[v3-R21] outline 必须覆盖 BaseReport 全部非 payload/sections/swot 字段）

v2 只列了 key_findings / executive_summary / recommendations，遗漏 title / at_a_glance / background / methodology / conclusions 等也是 BaseReport 必填。导致 phase 4 实例化时 ValidationError 而 LLM 已无机会重写——本节强制 outline LLM 一次性产出全部以下字段：

| 字段 | 类型 | 长度/数量约束 | schema 来源 |
|------|------|---------------|-------------|
| `title` | str | 12-78 字（schema 10-80 ±2 缓冲） | report.py BaseReport.title |
| `subtitle` | Optional str | 0-118 字 | BaseReport.subtitle |
| `at_a_glance` | list[str] | 3-6 条 | BaseReport.at_a_glance |
| `executive_summary.context` | str | 100-180 字（schema 80-200 ±20） | ExecutiveSummary.context |
| `executive_summary.core_thesis` | str | 60-110 字（schema 50-120 ±10） | ExecutiveSummary.core_thesis |
| `executive_summary.key_findings_brief` | list[str] | 2-4 条，每条 ≥30 字 | ExecutiveSummary.key_findings_brief |
| `executive_summary.implications` | str | 130-220 字（schema 100-250 ±30） | ExecutiveSummary.implications |
| `executive_summary.path_forward` | list[str] | 1-3 条 | ExecutiveSummary.path_forward |
| `background` | str | 220-1480 字（schema 200-1500 ±20） | BaseReport.background |
| `scope.time_window` | str | 必填 | ReportScope.time_window |
| `scope.regions` | list[str] | 默认 [] | ReportScope.regions |
| `scope.exclusions` | list[str] | 默认 [] | ReportScope.exclusions |
| `methodology.data_collection_approach` | str | ≥210 字（schema 200 ±10） | Methodology.data_collection_approach |
| `methodology.evaluation_criteria` | list[str] | ≥3 条 | Methodology.evaluation_criteria |
| `methodology.limitations` | list[str] | ≥2 条 | Methodology.limitations |
| `methodology.sample_size_note` | str | ≥85 字（schema 80 ±5） | Methodology.sample_size_note |
| `key_findings` | list[Finding] | 3-6 条，statement/evidence/implication 各 ≥25 字 | BaseReport.key_findings |
| `recommendations` | list[Recommendation] | ≥3 条，action/rationale 各 ≥25 字 | BaseReport.recommendations |
| `conclusions` | str | 220-1480 字（schema 200-1500 ±20） | BaseReport.conclusions |

注意：scope.competitors 不由 outline LLM 填，phase 4 由代码代填（见 [v3-R19] [v3-R26]）。
不让 LLM 填的字段：scenario_payload（phase 2）/ analysis_sections（phase 3）/ swot（phase 4 透传）/ metadata.* / appendix。

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

### 失败处理（C9 修订 + [v3-R04] 熔断不可绕开 + [v3-R03] LLMClient.call_json 改签名）
```python
async def _call_with_validation(
    self, system_prompt, user_prompt, schema_cls, max_retries=1, max_tokens=4096,
) -> BaseModel:
    for attempt in range(max_retries + 1):
        # [v3-R04] 必须走 _llm_call_with_quota，绝不直接调 self.llm.call_json
        raw = await self._llm_call_with_quota(system_prompt, user_prompt, max_tokens=max_tokens)
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

### LLMClient.call_json 签名扩展（[v3-R03]）

master `src/tools/llm_client.py:22` 当前签名 `async def call_json(self, system_prompt, user_prompt) -> dict`。Task 20.0 改为：

```python
async def call_json(
    self, system_prompt: str, user_prompt: str, *, max_tokens: int | None = None,
) -> dict:
    kwargs = {}
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens  # OpenAI SDK 不接受 max_tokens=None
    response = await self._client.chat.completions.create(
        model=self.model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        **kwargs,
    )
    # ... 现有 JSON 解析 + 代码块剥离逻辑保持
```

兼容性：现有所有调用点（collector / analyzer / inspector / recommender）不传 max_tokens，默认行为不变。仅 writer_orchestrator 4 个 phase 主动传 max_tokens。

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

**C4 + [v3-R15] — S3 wtp_research normalizer 强制 confidence=low**：
更新 `src/agents/normalizers/s3.py`：normalizer 检测 `method=proxy_from_competitor_pricing` 时：
1. 自动填占位 `limitations=["基于公开竞品定价反推，未做正式 WTP 调研"]`（如 limitations 已为空）
2. **强制** `confidence="low"`（不论 LLM 填了 high/medium 都覆盖）

理由：master `src/schemas/scenarios/s3.py:45-51` 的 model_validator 同时要求 method=proxy 时 confidence == "low"，单纯补 limitations 不够。

**[v3-R14] — S3/S4 source_refs 必填字段的"找不到来源"策略**：

master 现状：S3 `ObservedCompetitorTier.source_refs` / `CompetitorPricing.source_refs` / S4 `_BaseChange.source_refs`（FeatureChange/PricingChange/MessagingChange/NewsEvent/OrgChange）都是 `min_length=1`。

策略（Cooper 决策 a）：**无来源则不生成该条目**，prompt + normalizer 双防护：

- prompt 显式："如果某条目（如 ObservedCompetitorTier / FeatureChange）找不到 ≥1 个 source_refs（必须来自 profiles_source_urls），就不要生成该条目。宁缺勿滥。"
- normalizer 后置：扫描 S3 `observed_competitor_pricing[*]` 和 S4 `feature_changes / pricing_changes / messaging_changes / news_events / org_changes`，删除 `source_refs == [] or source_refs is None` 的条目，并在 metadata.warnings 加 `dropped_unverified_entries:s3.observed_competitor_pricing:N` 这种前缀。

`src/agents/normalizers/` 各场景 model_validator 同审一轮，覆盖以下兜底（Task 21.0 子任务）：
- s1: `FeatureScore._check_evidence`（score=2 必有 evidence_url；score=0 必有 source_missing_reason 或 evidence_url）—— normalizer 检测 score=2 但 evidence_url 不在 discovered_urls 时，降为 score=1 + 设 source_missing_reason
- s3: 上述强制 confidence=low + 删除空 source_refs 条目
- s4: 删除空 source_refs 的 changes；`_check_first_review_baseline` 触发条件预兜底（见 [v3-R09]）
- s5: `_check_axes_and_scores` PerceptualMap x/y 同 attribute 时 normalizer 互换某条 attribute（fallback 不优雅，宁可让 ValidationError 重试 LLM）

**[v3-R10] — S2 recommender 必填字段强制覆盖**（M4 修订）：

master `src/schemas/scenarios/s2.py:173` `S2MarketEntryPayload.competitor_recommendations` 是必填字段。v2 让 LLM "只读使用 + 不要重写" 不可靠，phase 2 后必须代码强制覆盖：

```python
# phase 2 normalize 后
payload_dict = normalize_for_scenario(scenario, raw)
if scenario == "S2" and competitor_recommendations is not None:
    # 强制覆盖（不论 LLM 写了什么）
    payload_dict["competitor_recommendations"] = competitor_recommendations.model_dump()
payload_model = self._build_payload_model(scenario, payload_dict)
```

**[v3-R09] — S4 prior diff 必须在 _build_payload_model 之前注入**（M5 修订）：

master `src/schemas/scenarios/s4.py:210-225` `_check_first_review_baseline` 是 model_validator(after)，payload 实例化时即触发。v2 把 prior diff 放 phase 4 太晚——必须前移到 phase 2 normalize 之后、`_build_payload_model` 之前：

```python
# phase 2 normalize 后、payload_model 实例化前
payload_dict = normalize_for_scenario(scenario, raw)
if scenario == "S2" and competitor_recommendations is not None:
    payload_dict["competitor_recommendations"] = competitor_recommendations.model_dump()
elif scenario == "S4":
    payload_dict = self._inject_s4_prior_diff(payload_dict, prior_report_data)
payload_model = self._build_payload_model(scenario, payload_dict)
```

`_inject_s4_prior_diff` 实现：
- prior_report_data is None → 不动 payload_dict（payload validator 走"首次监控全 baseline" 分支）
- prior_report_data 非空：
  - 解析 prior `metadata.scenario == "S4"` + `schema_version == "2.0"`，否则降级 None
  - prior_period.monitored_competitors vs current monitored_competitors → newly_added / dropped 写入 `review_period.newly_added_competitors / dropped_competitors`
  - prior 的 changes 不灌进 payload，仅作差集统计

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

**C2 — 占位长度 + 闸门双兜底（[v3-R12] 字符数硬核算 + [v3-R05] 半数闸门数学统一）**：

1. **占位 narrative ≥350 字符（schema min=300 + 50 字硬缓冲）**。固定模板字符数核算（不依赖 payload_dump 长度）：

```python
_PLACEHOLDER_NARRATIVE_TEMPLATE = (
    "【本节因数据不足暂未生成深度分析（自动占位）】\n\n"
    "本章节（{section_type}）原本应基于采集与分析阶段产出的具体数据展开 1500-3000 字的深度论述，"
    "但 phase 3 narrative LLM 调用在 1 次重试后仍未返回合规结果，故由代码自动落入占位模板。\n\n"
    "可用诊断信息：\n"
    "- metadata.warnings 中以 `placeholder_section:{section_type}` 为前缀的告警条目\n"
    "- 同 trace_id 下的 04_feedback.json，记录 inspector 对本节的具体扣分依据\n"
    "- 同 trace_id 下的 run.log，可定位 phase 3 LLM 调用失败的异常类型与时间点\n\n"
    "建议处理：等待 graph 反馈闭环重试 collector/analyzer，或手动指定更精准的数据源后重新发起分析。"
)
# 实测字符数（不替换 {section_type}）≈ 384 字符；替换后通常更长，留 50+ 字缓冲
```

2. metadata.warnings 加 `placeholder_section:{section_type}` 前缀，inspector 后续按前缀降 quality_score 到 ≤0.5（[v3-R17] inspector 必须实现承接逻辑）

3. **硬闸门数学统一（[v3-R05]）**：v2 同时写了"成功 < ⌈expected_n / 2⌉" 和 "5 个失败 ≥3 / 6 个失败 ≥3" 两个矛盾表述（5 个：⌈5/2⌉=3, 失败 ≥3 ⟺ 成功 ≤2 ⟺ 成功 <3 ✓；6 个：⌈6/2⌉=3, 但 v2 写"失败 ≥3"对应"成功 ≤3"⟺ "成功 <4"⟺ 阈值 4，互相矛盾）。统一为：

```python
def _check_narrative_gate(sections: list, expected_n: int) -> None:
    """半数闸门：失败数 ≥ ⌈expected_n / 2⌉ 即 raise"""
    failed_n = sum(1 for s in sections if "placeholder_section:" in s.heading)
    threshold = (expected_n + 1) // 2  # 等价于 ceil(expected_n / 2)
    if failed_n >= threshold:
        raise RuntimeError(
            f"phase 3 失败数 {failed_n} ≥ {threshold}（expected={expected_n}），"
            f"触发半数闸门，建议回 collector 重新采集"
        )
```

阈值表（一目了然）：
| expected_n | 阈值（失败 ≥ N 即 raise） |
|---|---|
| 5 | 3 |
| 6 | 3 |
| 7 | 4 |

**C8 / C12 — narrative 输出的 source_refs 同样规范**：
- prompt 显式"找不到来源时 source_refs 留空数组 []，禁止编占位 url"
- phase 4 后置过滤：剔除 url 不在 `discovered_urls_set` 中的 SourceRef（M10）

**P2=a — 并行执行 + [v3-R18] Semaphore 限速**：

```python
# WriterOrchestrator.__init__ 中
self._narrative_sem = asyncio.Semaphore(settings.WRITER_NARRATIVE_CONCURRENCY)  # default 3

async def _phase3_one_section_throttled(self, scenario, st, outline, payload_dict, analysis):
    async with self._narrative_sem:
        return await self._phase3_one_section(scenario, st, outline, payload_dict, analysis)

# Phase 3 主循环
results = await asyncio.gather(
    *(self._phase3_one_section_throttled(scenario, st, outline, payload_dict, analysis)
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

并行优势：5-6 次串行 60-90s → 并行（concurrency=3）~25-35s（限速后）。配置项 `WRITER_NARRATIVE_CONCURRENCY` 写入 `src/utils/config.py`，default 3，理由：Doubao 共享端点 RPM 限制按经验 ~10-15 req/min，并发 3 比 5-6 更安全。

### `_SECTION_CONTEXT_MAP`（M7 新增 + [v3-R20] 补 4 项达成 28 项全覆盖）

显式枚举每 section_type 取哪段 payload/analysis 字段。

**[v3-R20]** v2 列出 25 项漏掉 `executive_overview / background / conclusions_summary / consumer_segments_analysis` 4 个。补全后必须等于 master `src/schemas/report.py` AnalysisSection.section_type Literal 全部 28 个枚举值。Task 21.6 增加 lint 测试：从 `AnalysisSection.model_fields["section_type"]` 自动抽取 Literal args，断言与 `_SECTION_CONTEXT_MAP.keys()` 完全一致。

```python
_SECTION_CONTEXT_MAP: dict[str, list[str]] = {
    # 跨场景通用
    "overview": ["analysis"],
    "executive_overview": ["analysis", "outline.executive_summary"],  # [v3-R20] 新增
    "background": ["outline.background", "scenario_input"],            # [v3-R20] 新增
    "conclusions_summary": ["outline.conclusions", "outline.recommendations"],  # [v3-R20] 新增
    "vendor_profile_analysis": ["payload.vendor_profiles", "analysis.positioning"],
    "feature_matrix_analysis": ["payload.feature_matrix", "analysis.feature_matrix"],
    "jtbd_analysis": ["payload.job_statement", "analysis.user_sentiment"],
    "roadmap_analysis": ["payload.feature_gaps", "payload.roadmap_recommendations"],
    "market_sizing_analysis": ["payload.market_sizing"],
    "five_forces_analysis": ["payload.five_forces", "payload.industry_attractiveness_1_5"],
    "competitive_landscape_analysis": ["payload.players", "payload.market_concentration"],
    "consumer_segments_analysis": ["payload.consumer_segments"],  # [v3-R20] 新增
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

`_build_placeholder_swot()`：4 象限各填 1 条 SwotEntry。**[v3-R12] 字符数硬核算**（schema min=10，留 ≥15 字硬缓冲防文案微调时跌破阈值）：

```python
def _build_placeholder_swot() -> Swot:
    point_text = "采集数据不足，本象限当前由代码自动占位，等待数据补齐后由 LLM 重新生成具体条目"  # 36 字
    evidence_text = "详见报告 metadata.warnings 中以 placeholder_swot 为前缀的告警条目"  # 28 字
    placeholder = SwotEntry(
        point=point_text,
        evidence=evidence_text,
        dimension="overall",
    )
    return Swot(
        strengths=[placeholder],
        weaknesses=[placeholder],
        opportunities=[placeholder],
        threats=[placeholder],
    )
```

字符数硬约束（Task 21.6 测试断言）：
- `point_text` ≥25 字（schema min 10 + 15 缓冲）
- `evidence_text` ≥25 字（schema min 10 + 15 缓冲）

同时往 `metadata.warnings` 加 `placeholder_swot` 标记，inspector 降分（[v3-R17]）。

### 2. 聚合 source_refs → metadata.data_sources（[v3-R07] + [v3-R08] + [v3-R11] + [v3-R06]）

**[v3-R07] 必须收集 SourceRef + 多个 url 字段，不只是 SourceRef**：

v2 的 `_collect_urls_recursive` 只识别 `{url, source_type}` 同形 dict（即 SourceRef + DataSource），漏掉了所有"裸 url 字段"——S1 `FeatureScore.evidence_url` / S3 `PricingPageAudit.pricing_page_url` / S3 `RolloutStep.evidence_url` / `RecentUpdate.source_url` / `SampleReview.source_url` 等。这些 URL 不会进入 metadata.data_sources，导致溯源链断。

正确实现：双通道收集 — SourceRef-like 对象（保留全字段）+ 裸 url 字段名白名单（仅取 url）：

```python
_BARE_URL_FIELDS = {
    "evidence_url", "pricing_page_url", "source_url", "official_url", "url",
}

def _collect_source_refs_recursive(obj: Any) -> tuple[list[dict], set[str]]:
    """
    返回 (source_refs_full, bare_urls)：
    - source_refs_full: SourceRef 全字段 dict 列表（含 title/accessed_at/source_type）
    - bare_urls: 仅从 _BARE_URL_FIELDS 收集的 url 字符串集合
    """
    refs: list[dict] = []
    bare: set[str] = set()
    if isinstance(obj, dict):
        # [v3-R08] 区分 SourceRef vs DataSource：DataSource 含 confidence 字段
        if {"url", "source_type"} <= obj.keys() and "confidence" not in obj:
            # 是 SourceRef-like，保留全字段
            if obj.get("url"):
                refs.append({
                    "url": obj["url"],
                    "title": obj.get("title", ""),
                    "accessed_at": obj.get("accessed_at"),
                    "source_type": obj.get("source_type", "other"),
                })
        for k, v in obj.items():
            if k in _BARE_URL_FIELDS and isinstance(v, str) and v.startswith("http"):
                bare.add(v)
            sub_refs, sub_bare = _collect_source_refs_recursive(v)
            refs.extend(sub_refs)
            bare |= sub_bare
    elif isinstance(obj, list):
        for item in obj:
            sub_refs, sub_bare = _collect_source_refs_recursive(item)
            refs.extend(sub_refs)
            bare |= sub_bare
    return refs, bare

# 主流程
discovered = {u for p in profiles for u in collect_profile_urls(p)}  # [v3-R01]

dump = {
    "outline": outline_dict,
    "payload": payload_dict,
    "sections": [s.model_dump() for s in sections],
    "swot": swot.model_dump(),
}
collected_refs, collected_bare = _collect_source_refs_recursive(dump)

# 全字段去重 by url，过滤幻觉
ref_by_url: dict[str, dict] = {}
for r in collected_refs:
    if r["url"] in discovered and r["url"] not in ref_by_url:
        ref_by_url[r["url"]] = r

# 裸 url 字段补充：把不在 SourceRef 集合但在 discovered 的，构造最小 SourceRef
for u in collected_bare:
    if u in discovered and u not in ref_by_url:
        ref_by_url[u] = {"url": u, "title": "", "accessed_at": None, "source_type": "other"}

final_refs = list(ref_by_url.values())
final_urls = set(ref_by_url.keys())
```

**[v3-R11] 用全字段构 DataSource，不丢 title/accessed_at/source_type**：

```python
data_sources_models = [
    DataSource(
        url=r["url"], title=r["title"], accessed_at=r["accessed_at"],
        source_type=r["source_type"], confidence="medium",
    )
    for r in sorted(final_refs, key=lambda x: x["url"])
]
```

**[v3-R06] final_urls 空集合的兜底**（v2 漏看 ReportMetadata.data_sources min_length=1）：

```python
if not data_sources_models:
    # [v3-R06] LLM 完全没填 source_refs，但 profiles 实际有 url：raise 走 writer 重试（不是 collector 重试，因为采集没问题）
    raise RuntimeError(
        "writer phase 4: 报告内 0 个 source_refs 引用了 profiles 中的真实 URL，"
        "无法构造合规 ReportMetadata（data_sources min_length=1）。LLM 可能完全忽略了溯源约束，"
        "建议 graph 回 writer 重试一次。"
    )
```

[v3-R02 联动] 上述 raise 由 builder.writer_node 外层 try/except 捕获，转 `RejectionFeedback(agent="writer")` 注入 state，由 inspector should_continue 路由回 writer。

**C3 修订（profiles 全无 URL 时）**：仍按 v2 直接 raise，但错误消息指向 collector：

```python
if not discovered:
    raise RuntimeError(
        "writer phase 4: profiles 中收集到 0 个 URL，无法构造可溯源报告。"
        "建议 graph 回 collector 重新采集。"
    )
```

[v3-R02 联动] 此 raise 在 builder.writer_node 转 `RejectionFeedback(agent="collector")`。

### 3. 构 ReportMetadata（Q2=c 修订 + [v3-R13] 空 profiles 兜底 + [v3-R22] 语义说明 + [v3-R24] trace_id fallback）

```python
# [v3-R13] profiles 可能为 [] 时的 ZeroDivisionError 兜底
if profiles:
    avg_completeness = sum(p.metadata.completeness_score for p in profiles) / len(profiles)
else:
    avg_completeness = 0.0  # 但通常先在 phase 4 入口 if not discovered: raise 截胡

if avg_completeness >= 0.8:
    confidence_level = "high"
elif avg_completeness >= 0.5:
    confidence_level = "medium"
else:
    confidence_level = "low"

# [v3-R24] trace_id 空时 fallback uuid 防 report_id 碰撞
import uuid
report_id_seed = trace_id or uuid.uuid4().hex
report_id = f"r-{report_id_seed[:8]}"

metadata = ReportMetadata(
    report_id=report_id,
    trace_id=trace_id,
    scenario=scenario,
    publication_date=date.today(),
    data_sources=data_sources_models,  # [v3-R11] 全字段 DataSource
    confidence_level=confidence_level,
    contributing_agents=["collector", "analyzer", "writer"],
    warnings=warnings,
    quality_score_calculation_note="confidence_level 由采集 completeness 平均值派生（writer 阶段一次性）",
)
```

**[v3-R22] confidence_level 与 quality_score 语义边界**：

两者**独立、不交叉限制**（Cooper 决策 a）。语义定义：

| 字段 | 谁写 | 维度 | 取值范围 | 示例 |
|---|---|---|---|---|
| `metadata.confidence_level` | writer phase 4 一次性 | 数据采集面 | high/medium/low | 采集了 2 家竞品官网 + 4 家媒体页 → completeness=0.85 → high |
| `metadata.quality_score` | inspector 一次性回填 | 报告内容面 | 0.0-1.0 | inspector 发现 1 critical issue → 0.6；3 critical → 0.0 |

允许并存的情况：
- `confidence_level=high + quality_score=0.3`：采集很完整，但 writer 把 SWOT 全填了占位 + recommendations 全空 → 数据多但报告烂
- `confidence_level=low + quality_score=0.8`：只采集到 1 家竞品但报告写得严谨、所有 evidence 都有溯源、SWOT 完整 → 数据少但报告稳

inspector 不修改 confidence_level；writer 不修改 quality_score（plan A+B+C 已确认 quality_score 默认 None，由 inspector 一次性回填）。

注意：`confidence_level` 由 writer 派生后，inspector 不再回填该字段（避免双重写入语义混乱）；inspector 只回填 `quality_score`。

**[v3-R16] 同步：清理 builder.py 旧的 data_sources 覆盖代码**：

master `src/graph/builder.py:53-60`（v2 spec 没注意到）writer_node 之后还有一段：

```python
# 旧代码（必须删）
if state.get("profiles"):
    sources = []
    for p in state["profiles"]:
        sources.extend(p.metadata.data_sources)
    if "report" in state:
        state["report"].metadata.data_sources = sources  # 覆盖成 list[str]！
```

这段在 writer 写完 BaseReport（其中 metadata.data_sources 是 list[DataSource]）后，又把字段强行覆盖回 `list[str]`，破坏 schema 类型契约。Task 21.0 必须删除这段。重新接通在 builder.writer_node 内（见 [v3-R02] 路由）。

### 4. scope.competitors 兜底（C1 修订 + [v3-R19] S2 union 全部）

Cooper 决策 a：S2 场景 union 全部（用户填的 + recommender 推的），去重 by name，用户填的在前。

```python
# [v3-R19] S2 union；其他场景按 input
if scenario == "S2":
    user_names = [c.name for c in scenario_input.competitors]
    rec_names = (
        [r.name for r in competitor_recommendations.recommended_competitors]
        if competitor_recommendations else []
    )
    # 用户填的在前，recommender 补充，去重保留首次出现顺序
    seen: set[str] = set()
    scope_competitors: list[str] = []
    for name in user_names + rec_names:
        if name and name not in seen:
            seen.add(name)
            scope_competitors.append(name)
    if not scope_competitors:
        raise RuntimeError("S2 scope.competitors 空：用户未填且 recommender 也未产出")
elif scenario_input.competitors:
    scope_competitors = [c.name for c in scenario_input.competitors]
else:
    # S1/S3/S4/S5 ScenarioInput 校验已强制 competitors 非空
    raise RuntimeError(
        f"scope.competitors 无法构造：scenario={scenario}, competitors=[]，"
        f"ScenarioInput model_validator 应该先一步 raise"
    )
```

**[v3-R19 联动] scenario 参数与 scenario_input.scenario 一致性校验**：

`WriterOrchestrator.write` 入口必须 assert：

```python
async def write(self, *, scenario, scenario_input, ...):
    if scenario != scenario_input.scenario:
        raise ValueError(
            f"scenario={scenario} 与 scenario_input.scenario={scenario_input.scenario} 不一致；"
            f"调用方（应是 builder.writer_node）应只传单一权威源"
        )
    # 后续推荐：去掉冗余 scenario 参数，全用 scenario_input.scenario
    ...
```

**简化建议**：本次直接去掉 `scenario` 参数，所有引用改为 `scenario_input.scenario`（Task 21.1 实现时）。

### 5. 构 BaseReport
（同 v1）BaseReport 实例化时若 model_validator 失败 raise，graph 重试 writer。

## WriterOrchestrator 完整骨架（[v3-R04] [v3-R05] [v3-R19] 修订后）

```python
from src.utils.config import settings


class WriterOrchestrator:
    def __init__(self, llm: LLMClient):
        self.llm = llm
        self._call_counter = 0  # M2 熔断计数
        # [v3-R18] phase 3 并发限速
        self._narrative_sem = asyncio.Semaphore(settings.WRITER_NARRATIVE_CONCURRENCY)

    async def write(self, *, scenario_input: ScenarioInput, analysis, profiles,
                    analysis_goal=None, competitor_recommendations=None,
                    prior_report_data=None, trace_id: str = "") -> BaseReport:
        """
        [v3-R19] 去掉冗余 scenario 参数，权威源仅 scenario_input.scenario。
        builder.writer_node 调用此函数时不应再传 scenario=...。
        """
        scenario = scenario_input.scenario
        self._call_counter = 0

        competitor_names = [c.name for c in scenario_input.competitors]
        # [v3-R01] 用 collect_profile_urls，不是 p.source_urls
        discovered_urls = sorted({u for p in profiles for u in collect_profile_urls(p)})

        if not discovered_urls:
            raise RuntimeError(
                "writer phase 4: profiles 中收集到 0 个 URL，无法构造可溯源报告。"
                "建议 graph 回 collector 重新采集。"
            )

        outline = await self._phase1_outline(
            scenario, scenario_input, analysis, profiles,
            competitor_names, discovered_urls,
        )
        payload_dict = await self._phase2_payload(
            scenario, scenario_input, analysis, profiles,
            competitor_recommendations, prior_report_data,
            competitor_names, discovered_urls,
        )

        # [v3-R09] S4 prior diff 必须在 _build_payload_model 之前
        if scenario == "S4":
            payload_dict = self._inject_s4_prior_diff(payload_dict, prior_report_data)
        # [v3-R10] S2 recommender 必填字段强制覆盖
        if scenario == "S2" and competitor_recommendations is not None:
            payload_dict["competitor_recommendations"] = competitor_recommendations.model_dump()

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
        """
        [v3-R04] 所有 LLM 调用必须走这里（包括 _call_with_validation 重试）。
        [v3-R05] 上限 18：phase1(1+1) + phase2(1+1) + phase3(6×2) = 16 + 2 安全荧丝
        """
        self._call_counter += 1
        if self._call_counter > settings.WRITER_MAX_LLM_CALLS:  # default 18
            raise RuntimeError(
                f"writer LLM 调用超限 {self._call_counter} 次"
                f"（上限 {settings.WRITER_MAX_LLM_CALLS}），疑似无限重试"
            )
        return await self.llm.call_json(*args, **kwargs)
```

**配置项**（`src/utils/config.py` 新增）：
- `WRITER_MAX_LLM_CALLS: int = 18`（[v3-R05]）
- `WRITER_NARRATIVE_CONCURRENCY: int = 3`（[v3-R18]）

## Pre-flight: master 适配（v3 新增 — Task 21 启动前必须完成）

v2 spec 假定 master 已经"writer 接口干净、graph 路由就位"，但 v3 复查发现以下 5 个 master 现状问题。**这些必须在 Task 21.0 实现前一次性修齐**，否则 writer_orchestrator 写完了也无法接通到 graph。

### [v3-R03] LLMClient.call_json 加 max_tokens 参数（Task 20.0）

见前文 "LLMClient.call_json 签名扩展" 段。

### [v3-R02] graph builder.writer_node 加异常路由（Task 21.0a）

master `src/graph/builder.py` 当前 writer_node 抛异常会直接 abort 整个 langgraph 流，绕开 should_continue。Task 21.0a 必须改造：

```python
async def writer_node(state):
    logger.info("[graph] → writer")
    node_trace.append("writer")
    try:
        # [v3-R09] S4 时由 builder 读盘 prior_report_data
        prior_data = None
        ui = state["user_input"]
        if ui.scenario == "S4" and ui.prior_trace_id:
            prior_data = _load_prior_report_data(ui.prior_trace_id, trace_writer)

        report = await writer_orchestrator.write(
            scenario_input=ui,
            analysis=state["analysis"],
            profiles=state["profiles"],
            analysis_goal=state.get("analysis_goal"),
            competitor_recommendations=state.get("competitor_recommendations"),
            prior_report_data=prior_data,
            trace_id=state.get("trace_id", ""),
        )
        _save("03_report", report)
        return {"report": report, "current_node": "writer"}
    except RuntimeError as e:
        # [v3-R02] writer raise 转 RejectionFeedback 注入 state
        msg = str(e)
        if "回 collector" in msg:
            agent = "collector"
        elif "回 writer" in msg:
            agent = "writer"
        else:
            agent = "writer"  # 默认 writer
        feedback = RejectionFeedback(
            passed=False,
            issues=[Issue(severity="critical", agent=agent, description=msg)],
        )
        logger.warning("[graph] writer raised → 转 feedback agent=%s", agent)
        return {
            "feedback": feedback,
            "current_node": "writer",
            "retry_count": state.get("retry_count", 0) + 1,
        }
```

`_load_prior_report_data` 实现（builder 内部辅助函数）：

```python
def _load_prior_report_data(prior_trace_id: str, trace_writer):
    """读上轮 BaseReport JSON。校验 scenario==S4 + schema_version==2.0，否则返回 None"""
    from src.utils.paths import RUNS_DIR
    from pathlib import Path
    import json

    prior_path = Path(RUNS_DIR) / prior_trace_id / "03_report.json"
    if not prior_path.exists():
        logger.warning("prior_trace_id=%s 报告不存在，降级为首次监控", prior_trace_id)
        return None
    try:
        with open(prior_path, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("prior_trace_id 读取失败 %s，降级为首次监控", e)
        return None
    if data.get("metadata", {}).get("scenario") != "S4":
        logger.warning("prior 报告 scenario != S4，降级为首次监控")
        return None
    if data.get("metadata", {}).get("schema_version") != "2.0":
        logger.warning("prior 报告 schema_version != 2.0，降级为首次监控")
        return None
    return data
```

`should_continue` 已有的"按 issue.agent 路由回 collector/writer/analyzer" 逻辑直接复用，不动。

### [v3-R03 联动 + master 现状清理] AnalysisState / writer.py / inspector.py FinalReport import 一次清理（Task 21.0b）

master 当前：
- `src/graph/state.py:5` `from src.schemas.report import FinalReport`（已废）
- `src/graph/state.py:23` `report: FinalReport`
- `src/agents/writer.py:6` `from src.schemas.report import FinalReport`（旧 WriterAgent 用）
- `src/agents/inspector.py:2` 类似

Task 21.0b 一次修齐：
- `state.py`：FinalReport → BaseReport；CompetitorInput → ScenarioInput；新增 `competitor_recommendations: Optional[CompetitorRecommendations]` / `prior_report_data: Optional[dict]` 字段
- `writer.py`：整文件重写为 `from src.agents.writer_orchestrator import WriterOrchestrator` + 保留 `class WriterAgent` 薄封装（避免下游 import 全改）
- `inspector.py`：暂留旧实现（F 大类 Task 23 会重写）；但必须把 import 路径修对，能跑（即使逻辑还旧）

### [v3-R16] graph builder 旧 data_sources 覆盖逻辑删除（Task 21.0c）

见前文 "[v3-R16] 同步：清理 builder.py 旧的 data_sources 覆盖代码" 段。

### [v3-R17] inspector 承接 placeholder warnings（Task 23 范围，但本 spec 标记依赖）

writer 在 `metadata.warnings` 写 `placeholder_section:` / `placeholder_swot` / `dropped_unverified_entries:` 等前缀，inspector 必须读这些前缀降 quality_score。当前（master）inspector 只读 issues，不读 warnings——**这是 F 大类 Task 23 的工作，Task 21 实现时不能依赖它已就位**。

Task 21 测试时 mock inspector 验"writer 正确写入了 warnings 前缀"，不验"inspector 是否降分"（那是 Task 23 测试）。

### [v3-R25] prompts 目录迁移与旧 import 兼容（Task 20.1 顺序）

master 当前 `src/agents/writer.py:7,77,83` 仍依赖 `from src.agents.prompts import WRITER_SYSTEM`（旧 WriterAgent）。Task 20.1 迁移目录顺序：

1. **第一步**：`src/agents/prompts.py` → `src/agents/prompts/__init__.py`（保留所有现有常量包括 `WRITER_SYSTEM`）。此时 `from src.agents.prompts import WRITER_SYSTEM` 仍能 work。
2. **第二步**：建子目录 `src/agents/prompts/writer/{outline,payload,narrative}/`，加新常量。
3. **第三步**：[v3-R03 联动] Task 21.0b 重写 writer.py 后，旧 `WRITER_SYSTEM` 不再被任何代码 import。
4. **第四步**：从 `src/agents/prompts/__init__.py` 删除 `WRITER_SYSTEM`（git grep 验证零引用后）。

不能跳过第一步直接拆子目录 + 删 `WRITER_SYSTEM`，会导致 master 半途破裂（旧 WriterAgent import 失败但新 orchestrator 还没接通）。

---

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

## 测试策略（M8 修订 + v3 加 3 个用例 + 修订 #13 时间断言）

### Task 21（WriterOrchestrator）单测（共 16 个）

1. **phase 1 outline 调用 + Pydantic 失败重试**：mock LLM 第 1 次返回缺字段，第 2 次 OK → 总调用 2 次
2. **phase 2 payload normalize 工作**：mock LLM 返回带 `weighted_scores` 的 S1 payload → normalize 删掉后实例化成功
3. **phase 3 narrative 单 section 失败局部降级**：mock 让第 3 个 section 抛错 → 返回 placeholder narrative **≥350 字**（[v3-R12]） + warning 含 `placeholder_section:` 前缀
4. **phase 3 半数失败硬闸门 raise**：5 个 section 中 3 个抛错 → raise RuntimeError；6 个 section 中 3 个抛错 → raise RuntimeError（[v3-R05] 阈值统一）
5. **phase 4 SWOT 透传**：传入有 SWOT 的 analysis → `report.swot == analysis.swot`
6. **phase 4 SWOT 占位字符数**：analysis.swot=None → placeholder swot 4 象限各 1 条且 point/evidence ≥25 字（[v3-R12]）
7. **phase 4 confidence_level 派生**：profiles completeness=[0.9,0.85] → high；=[0.6,0.5] → medium；=[0.3,0.2] → low
8. **phase 4 source_refs 聚合 + 幻觉过滤 + 全字段保留**（[v3-R07] [v3-R11]）：
   - payload 含 1 个 profiles 外的 url → 不进 metadata.data_sources
   - payload 含 SourceRef(title="X", source_type="news") → metadata.data_sources 中对应 entry 保留 title/source_type
   - payload 含 FeatureScore(evidence_url="...") + 无对应 SourceRef → 该 URL 仍进 metadata.data_sources（裸 url 字段通道）
9. **phase 4 profiles 全无 url → raise**（错误消息含"回 collector"）
10. **phase 4 scope.competitors S2 兜底 + union**（[v3-R19]）：
    - competitors=[user]，recommender=[A,B,C] → scope=[user,A,B,C]（用户在前）
    - competitors=[]，recommender=[A,B,C] → scope=[A,B,C]
    - competitors=[A]，recommender=[A,B] → scope=[A,B]（去重）
11. **`_serialize_validation_error` ≤ 1500 字符**：嵌套 5 层 ValidationError 序列化 ≤ 1500
12. **调用次数熔断**：mock LLM 全失败 → 超 18 次 raise（[v3-R05]）
13. **phase 3 并行验证**（[v3-R28] 修订）：mock LLM 每次 sleep 0.5s，5 个 section → 断言 `mock.call_count == 5 and total_time < sleep_time * 3`（即非串行；不用绝对时长 < 3s 防 Windows 抖动）

### v3 新增 3 个测试

14. **[v3-R10] phase 2 S2 recommender 强制覆盖**：
    - mock LLM phase 2 返回 `competitor_recommendations={"recommended_competitors":[改写后的]}` → 实际 payload_dict 中 competitor_recommendations 被代码覆盖回 input 的 recommender 数据，不被 LLM 改动
15. **[v3-R09] phase 2 S4 prior diff 前置注入**：
    - prior_report_data 含 monitored_competitors=["A","B"]，current_input.competitors=["A","C"]
    - 断言 payload_model.review_period.dropped_competitors==["B"], newly_added_competitors==["C"]
    - 且 payload model_validator `_check_first_review_baseline` 不触发"全 baseline" 报错
16. **[v3-R02] builder.writer_node 异常路由**（属于 Task 21.0a 但放本组）：
    - mock orchestrator.write 抛 `RuntimeError("回 collector")` → state.feedback.issues[0].agent == "collector" + retry_count +1
    - mock orchestrator.write 抛 `RuntimeError("回 writer")` → agent == "writer"

### Task 20（prompts）lint 测试（[v3-R27] 加 prompt 合约测试）

- 5 个 OUTLINE/PAYLOAD/NARRATIVE prompt 文件都存在且 import 不报错
- `_SECTION_CONTEXT_MAP.keys()` == `set(AnalysisSection.model_fields["section_type"].annotation.__args__)`（28 项全覆盖）
- **[v3-R27]** 5 场景最小 payload prompt 合约 fixture：每场景准备 1 份"满足所有 model_validator 的最小合法 payload JSON" → 用 `S{N}Payload(**fixture)` 实例化成功，并断言关键 model_validator（如 S1 `_check_competitor_consistency` / S3 `_check_recommended_tier` / S5 `_check_axes_and_scores`）能正向通过

## 落地拆分（v3 修订）

v3 在 Task 20/21 之前新增了一组 master 适配前置任务，并扩充了 normalizer 升级范围。

```
# Task 20: prompts 与 LLMClient 改动
Task 20.0: src/tools/llm_client.py 加可选 max_tokens 参数（[v3-R03]）
Task 20.1: src/agents/prompts.py → src/agents/prompts/__init__.py（保留旧常量 + 子目录新建）
Task 20.2: src/agents/prompts/writer/outline/ 5 套（[v3-R21] 全字段约束）
Task 20.3: src/agents/prompts/writer/payload/ 5 套（[v3-R10] [v3-R14] 等约束嵌入）
Task 20.4: src/agents/prompts/writer/narrative/ 模板 + sections 字典（[v3-R20] 28 项全覆盖）

# Task 21.0: master 现状适配前置（v3 新增）
Task 21.0a: builder.writer_node 加异常路由（[v3-R02]）+ _load_prior_report_data
Task 21.0b: state.py / writer.py / inspector.py 修复 FinalReport import + 加 ScenarioInput 字段
Task 21.0c: builder.py 删除旧 data_sources 覆盖逻辑（[v3-R16]）
Task 21.0d: src/utils/config.py 加 WRITER_MAX_LLM_CALLS=18 + WRITER_NARRATIVE_CONCURRENCY=3
Task 21.0e: src/agents/normalizers/ 5 套升级（[v3-R14]）：
  - s1: FeatureScore evidence_url 不在 discovered 时降 score=1
  - s3: WTP method=proxy 强制 confidence=low（[v3-R15]）+ 删除空 source_refs 的 ObservedCompetitorTier/CompetitorPricing
  - s4: 删除空 source_refs 的 changes
  - s5: PerceptualMap x/y 同 attribute 时不兜底（让 ValidationError 走重试）
  - s2: 无强校验问题，仅审视

# Task 21.1: WriterOrchestrator 主体
Task 21.1: writer_orchestrator.py 骨架 + _call_with_validation + _serialize_validation_error + _llm_call_with_quota
Task 21.2: phase 1 outline 实现（[v3-R21] 全字段）
Task 21.3: phase 2 payload 实现（含 normalize 接通 + [v3-R09] [v3-R10] 前置注入）
Task 21.4: phase 3 narrative 实现（[v3-R18] Semaphore + [v3-R05] 半数闸门统一 + [v3-R12] 占位 ≥350 字）
Task 21.5: phase 4 assemble 实现（SWOT 透传 + [v3-R07] 双通道 url 收集 + [v3-R11] 全字段 DataSource + [v3-R06] 空 final_urls raise + [v3-R13] ZeroDivisionError 兜底 + [v3-R19] S2 union scope）
Task 21.6: 16 个单测全绿（v3 加 3 个）+ ruff
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

## v3 修订日志（v2 → v3，28 条 reconciled）

第二轮 doubt-driven：单模型 Explore agent 18 条 + 跨模型 Codex (gpt-5.5) 22 条，去重合并后 28 条。  
🔴 = CRITICAL（不修必出运行时 bug） / 🟡 = MAJOR（不修会埋雷） / 🟢 = MINOR（清晰度问题）

| 编号 | 严重度 | 标题 | 落点章节 | Cooper 决策 |
|---|---|---|---|---|
| **R-01** | 🔴 | `CompetitorProfile.source_urls` 字段不存在 → 改 `collect_profile_urls` 走 metadata.data_sources + nested source_url | Phase 1 输入预处理 | 技术 |
| **R-02** | 🔴 | builder.writer_node 没有 raise→graph 回边机制；spec 多处假设的 C3/M2/phase3 闸门路径全部不存在 | Pre-flight Task 21.0a | a (writer 内部 raise，builder 外层 try/except 转 feedback) |
| **R-03** | 🔴 | LLMClient.call_json 不收 max_tokens；state.py / writer.py 还 import 已删的 FinalReport | Pre-flight Task 21.0b + LLMClient.call_json 段 | 技术 |
| **R-04** | 🔴 | `_call_with_validation` 直接调 self.llm.call_json 绕开 `_llm_call_with_quota` 熔断 | Phase 1 失败处理段 | 技术 |
| **R-05** | 🔴 | WRITER_MAX_LLM_CALLS=15 上限太紧（最坏 16 次）+ phase 3 半数闸门数学错（v2 自相矛盾） | Phase 3 + Orchestrator skeleton | a (上限调 18) |
| **R-06** | 🔴 | `final_urls = collected & discovered` 可空，违反 ReportMetadata.data_sources min_length=1 | Phase 4 第 2 步 | 技术 |
| **R-07** | 🔴 | `_collect_urls_recursive` 只识别 SourceRef，漏掉 evidence_url / pricing_page_url / source_url 等裸 url 字段 | Phase 4 第 2 步 | 技术 |
| **R-08** | 🟡 | `_collect_urls_recursive` 把 DataSource 误识别为 SourceRef（同形 dict） | Phase 4 第 2 步 | 技术 |
| **R-09** | 🔴 | S4 prior diff 放 phase 4 太晚；payload model_validator 已先触发 | Phase 2 + Orchestrator skeleton | 技术 |
| **R-10** | 🔴 | S2 `competitor_recommendations` 必填字段，"只读使用"不可靠，必须代码强制覆盖 | Phase 2 + Orchestrator skeleton | 技术 |
| **R-11** | 🔴 | DataSource 全字段保留（title/accessed_at/source_type），不丢成 url-only | Phase 4 第 2 步 | 技术 |
| **R-12** | 🟡 | placeholder swot/narrative 字符数缓冲不够 → SWOT ≥25 字 + narrative ≥350 字 + 模板字符核算 | Phase 3 占位 + Phase 4 SWOT 占位 | 技术 |
| **R-13** | 🟡 | profiles=[] 时 ZeroDivisionError | Phase 4 第 3 步 | 技术 |
| **R-14** | 🔴 | S3 ObservedCompetitorTier / S4 _BaseChange 的 source_refs min=1 与"找不到来源 []"策略冲突 | Phase 2 + normalizer s3/s4 | a (无来源则不生成该条目) |
| **R-15** | 🟡 | s3 normalizer method=proxy 时**强制** confidence=low（不只是补 limitations） | Phase 2 + Task 21.0e | 技术 |
| **R-16** | 🟡 | builder.py:53-60 旧 data_sources 覆盖逻辑会把 list[DataSource] 改成 list[str] | Pre-flight Task 21.0c | 技术 |
| **R-17** | 🟡 | placeholder warning 降分机制需要 inspector 承接，但当前 inspector 不读 warnings | Pre-flight 标记依赖 + F 大类 | 技术 |
| **R-18** | 🟡 | phase 3 asyncio.gather 没限速 → 加 `asyncio.Semaphore(3)` 防 Doubao RPM | Phase 3 + 配置 | 技术 |
| **R-19** | 🟡 | scope.competitors S2 union（用户填+recommender 推荐）+ scenario 参数与 scenario_input 一致性校验 | Phase 4 第 4 步 + Orchestrator skeleton | a (S2 union 全部，去重 by name，用户在前) |
| **R-20** | 🟡 | `_SECTION_CONTEXT_MAP` 漏 4 项（executive_overview/background/conclusions_summary/consumer_segments_analysis） | Phase 3 _SECTION_CONTEXT_MAP | 技术 |
| **R-21** | 🟡 | Phase 1 outline prompt 漏约束 title/at_a_glance/background/methodology/conclusions 等必填字段 | Phase 1 输出 JSON 结构 | a (保持单次调用，prompt 补全) |
| **R-22** | 🟢 | confidence_level (writer) vs quality_score (inspector) 语义边界文档说明 | Phase 4 第 3 步 | a (不交叉限制，仅加语义说明) |
| **R-23** | 🟡 | prior_report_data 来源没说清 → builder 通过 trace_writer 读上轮 BaseReport | Pre-flight Task 21.0a | 技术 |
| **R-24** | 🟢 | trace_id="" 时 report_id="r-" 碰撞 → uuid fallback | Phase 4 第 3 步 | 技术 |
| **R-25** | 🟡 | prompts 目录迁移 + 删 WRITER_SYSTEM 必须分四步走，否则 master 半途破裂 | Pre-flight | 技术 |
| **R-26** | 🟢 | "只传 competitor_names" 丢失 company/category/url 等结构信息 | Phase 1 输入预处理 | 技术 |
| **R-27** | 🟢 | Task 20 prompt 单测应加 5 场景最小 payload fixture 合约校验 | 测试策略 | 技术 |
| **R-28** | 🟢 | 测试 #13 用绝对时长 < 3s 对 Windows 抖动敏感 → call_count + 相对时长 | 测试策略 | 技术 |

### 双轮自相印证 vs 独占发现

- 两轮都抓到（10 条）：R-02 / R-03 / R-04 / R-05 / R-09（部分）/ R-13 / R-18 / R-19 / R-20 / R-24
- 仅 Codex 抓到（10 条）：**R-01 (字段名 source_urls 根本不存在)** / R-06 / R-07 / R-09 / R-10 / R-11 / R-15 / R-16 / R-17 / R-21 / R-25 / R-27
- 仅 Explore 抓到（5 条）：R-08 (DataSource 同形误识别) / R-12 (字符数缓冲) / R-22 / R-26 / R-28

跨模型独占发现（特别是 R-01 和 R-15/R-16/R-17 这组对 master 现状的精确断言）证明了二次 doubt-driven 的价值——单模型走完仍漏关键证据链。

### 不进 v3 的可疑点（Codex 自审已证伪）

- S5 `_check_competitor_consistency` "is_self exactly-one"当前只在 >1 时 raise，0 个 self 不会失败：底层 schema 小瑕疵，不属本 spec 修订范围
- max_tokens 兼容修改本身合理：v2 已列入修订计划，v3 R-04 也只是确保它真接通到 `_llm_call_with_quota`，不是推翻原决策
