# 报告质量提升（方案 C：溯源为脉）实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让多 Agent 竞品分析报告从「简陋、溯源断链」变「丰满、结构完整、每条结论挂载来源 URL」，沿事实-URL 绑定链贯穿采集→分析→撰写→质检全链路。

**Architecture:** 核心原则「能用代码保证的结构与溯源不赌 LLM」。采集层保留 per-source 的 (text,url) 分段供 LLM 抽取时绑定来源；analyzer 补 source_urls 输出槽并由代码从 profile 兜底回填；writer 用代码机械透传 SWOT/雷达/功能矩阵、按 dimension 机械下沉 source_refs；inspector 加程序化硬查并按 severity 分级 pass/fail、修复 analyzer 反馈路由假闭环。

**Tech Stack:** Python 3.14 / Pydantic v2 / LangGraph StateGraph / Doubao-Seed-2.0-lite (256K context, OpenAI SDK) / pytest + pytest-asyncio / Streamlit 前端。

设计依据：`docs/superpowers/specs/2026-06-04-report-quality-design.md`（经两轮 doubt-driven 审查定稿）。

---

## 文件结构（改动地图）

| 文件 | 责任 | 改动类型 |
|---|---|---|
| `src/agents/collection_pipeline.py` | 采集管线 | 新增 `labeled_text` 返回（带来源标记分段） |
| `src/agents/collector.py` | 采集 Agent | 用 labeled_text 抽取；解包改 4 元组 |
| `src/agents/prompts.py` | 所有 prompt | COLLECTOR_EXTRACT/ANALYZER/WRITER 改写 |
| `src/schemas/report.py` | 报告 schema | FinalReport 加 swot/radar_scores/feature_matrix；ReportSection 加 dimension |
| `src/agents/analyzer.py` | 分析 Agent | 代码兜底回填维度 source_urls |
| `src/agents/writer.py` | 撰写 Agent | 机械透传结构化字段 + 机械下沉 source_refs + 过滤幻觉 URL；删截断 |
| `src/agents/inspector.py` | 质检 Agent | 补程序化硬查；inspect 接收竞品名单；删截断 |
| `src/graph/state.py` | 共享状态 | 加 `analysis_goal` 字段 |
| `src/graph/builder.py` | 图编排 | focus_area 回填；inspect 传竞品名单；should_continue 认 analyzer；加 analyzer 回边 |
| `src/frontend/app.py` | 前端 | 渲染 SWOT/雷达/功能矩阵/溯源链接 |

---

## Task 1: report schema 加结构化字段

**Files:**
- Modify: `src/schemas/report.py`
- Test: `tests/unit/test_schemas.py`

`FinalReport` 复用 `analysis` 的 `Swot`/`RadarScore`/`FeatureMatrixEntry` 类型，全部带默认值（避免 LLM 漏填致 `FinalReport(**result)` 先 ValidationError）。`ReportSection` 加 `dimension` 字段，默认 `"overview"`，枚举对齐 analysis 真实字段名。

- [ ] **Step 1: 写失败测试**

在 `tests/unit/test_schemas.py` 末尾追加：

```python
def test_final_report_has_structured_fields_with_defaults():
    from src.schemas.report import FinalReport
    # 不传 swot/radar_scores/feature_matrix 也能构造（默认值）
    report = FinalReport(title="t")
    assert report.swot.strengths == []
    assert report.radar_scores == []
    assert report.feature_matrix == []


def test_report_section_dimension_defaults_overview():
    from src.schemas.report import ReportSection
    sec = ReportSection(title="概览")
    assert sec.dimension == "overview"


def test_report_section_dimension_accepts_analysis_keys():
    from src.schemas.report import ReportSection
    for d in ["positioning", "feature_matrix", "business_model",
              "operations", "user_sentiment", "swot", "overview"]:
        assert ReportSection(title="x", dimension=d).dimension == d
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/unit/test_schemas.py::test_final_report_has_structured_fields_with_defaults tests/unit/test_schemas.py::test_report_section_dimension_defaults_overview tests/unit/test_schemas.py::test_report_section_dimension_accepts_analysis_keys -v`
Expected: FAIL（`swot` 等属性不存在 / `dimension` 不存在）

- [ ] **Step 3: 改 report.py**

在 `src/schemas/report.py` 顶部 import 区，从 analysis 导入复用类型：

```python
from src.schemas.analysis import Swot, RadarScore, FeatureMatrixEntry
```

修改 `ReportSection`，加 `dimension` 字段：

```python
class ReportSection(BaseModel):
    """报告章节"""
    title: str
    content: str = ""
    dimension: Literal[
        "positioning", "feature_matrix", "business_model",
        "operations", "user_sentiment", "swot", "overview"
    ] = "overview"
    source_refs: list[str] = Field(default_factory=list)
```

修改 `FinalReport`，加三个结构化字段：

```python
class FinalReport(BaseModel):
    """撰写 Agent 输出：最终竞品分析报告"""
    title: str
    executive_summary: ExecutiveSummary = Field(default_factory=ExecutiveSummary)
    sections: list[ReportSection] = Field(default_factory=list)
    swot: Swot = Field(default_factory=Swot)
    radar_scores: list[RadarScore] = Field(default_factory=list)
    feature_matrix: list[FeatureMatrixEntry] = Field(default_factory=list)
    action_items: ActionItems = Field(default_factory=ActionItems)
    metadata: ReportMetadata = Field(default_factory=ReportMetadata)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/unit/test_schemas.py -v`
Expected: PASS（含新增 3 个用例 + 原有用例不回归）

- [ ] **Step 5: 提交**

```bash
git add src/schemas/report.py tests/unit/test_schemas.py
git commit -m "feat: FinalReport 承接 SWOT/雷达/功能矩阵 + ReportSection 加 dimension 外键"
```

---

## Task 2: collection_pipeline 输出带来源标记的分段文本

**Files:**
- Modify: `src/agents/collection_pipeline.py:105-148`
- Test: `tests/unit/test_collection_pipeline.py`

`collect` 当前返回 `(merged_text, sources, trace)`，`texts[i]` 与 `sources[i]` 下标对应。新增第 4 个返回值 `labeled_text`：把每段正文用 `【来源: url】` 标记拼接，供 collector 抽取时绑定来源。保留 `merged_text` 不动（降低 blast radius）。注意：搜索主线抓取的页（有 url）和专源结果都进 `texts`/`sources`，但专源里 iTunes 可能 `url=""`（sources.py:47），此时标记用 `【来源: 未知】`。

- [ ] **Step 1: 写失败测试**

在 `tests/unit/test_collection_pipeline.py` 末尾追加（参照该文件已有的 fixture/mock 风格——若已有 pipeline 构造 helper 复用之；以下为自包含写法）：

```python
import pytest
from src.agents.collection_pipeline import CollectionPipeline


class _NoSearch:
    name = "nosearch"
    def available(self): return False
    async def search(self, q): return []


@pytest.mark.asyncio
async def test_collect_returns_labeled_text(monkeypatch):
    pipe = CollectionPipeline(
        llm=None, http=None, parser=None, search_source=_NoSearch(),
    )

    # 伪造专源：返回两条带 url 的结果
    from src.tools.sources import SourceResult

    class _Src:
        name = "fake"
        async def collect(self, name):
            return [
                SourceResult(url="https://a.com", text="正文A"),
                SourceResult(url="", text="正文B无源"),
            ]

    monkeypatch.setattr(
        "src.agents.collection_pipeline.build_pro_sources",
        lambda category, http: [_Src()],
    )

    merged, sources, trace, labeled = await pipe.collect("X", "saas")
    assert "正文A" in merged and "正文B无源" in merged  # merged 不变
    assert "【来源: https://a.com】" in labeled
    assert "正文A" in labeled
    assert "【来源: 未知】" in labeled  # 空 url 占位
    assert sources == ["https://a.com"]  # 空 url 不进 sources（既有行为）
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/unit/test_collection_pipeline.py::test_collect_returns_labeled_text -v`
Expected: FAIL（`collect` 只返回 3 元组，解包 4 个报 ValueError）

- [ ] **Step 3: 改 collection_pipeline.py**

把 `collect` 方法体改为同时累积带标记分段。完整替换 `src/agents/collection_pipeline.py:105-148` 的 `collect` 方法：

```python
    async def collect(self, competitor_name: str, category: str):
        """返回 (merged_text, sources, pipeline_trace, labeled_text)。

        labeled_text 在每段正文前加【来源: url】标记，供 collector 抽取时绑定来源。
        merged_text 保持原样（无标记），向后兼容既有消费方。
        """
        trace: list[dict] = []
        texts: list[str] = []
        labeled_parts: list[str] = []
        sources: list[str] = []
        seen_urls: set[str] = set()

        def _add(text: str, url: str):
            texts.append(text)
            labeled_parts.append(f"【来源: {url or '未知'}】\n{text}")

        pro_sources = build_pro_sources(category, self.http)
        trace.append({"step": "route", "category": category, "pro_sources": [s.name for s in pro_sources]})

        if self.search_source.available():
            trace.append({"step": "search", "provider": self.search_source.name})
            candidates = await self.search_source.search(f"{competitor_name} 产品 功能 定价")
            picked = await self._llm_pick(candidates, competitor_name, self.max_top_n)
            if picked is not None:
                trace.append({"step": "pick", "method": "llm", "picked": [c["url"] for c in picked]})
            else:
                picked = self._rule_pick(candidates, competitor_name, self.max_top_n)
                trace.append({"step": "pick", "method": "rule_fallback", "picked": [c["url"] for c in picked]})
            fetched = await asyncio.gather(
                *[self._fetch_clean(c["url"]) for c in picked], return_exceptions=True
            )
            for c, t in zip(picked, fetched):
                if isinstance(t, str) and t and c["url"] not in seen_urls:
                    _add(t, c["url"])
                    sources.append(c["url"])
                    seen_urls.add(c["url"])
        else:
            trace.append({"step": "search_skipped", "reason": "no_api_key"})

        results_per_source = await asyncio.gather(*[self._run_source(s, competitor_name) for s in pro_sources])
        for src, results in zip(pro_sources, results_per_source):
            for r in results:
                if r.url not in seen_urls:
                    _add(r.text, r.url)
                    if r.url:
                        sources.append(r.url)
                        seen_urls.add(r.url)
            trace.append({"step": "pro_source", "name": src.name, "results": len(results)})

        merged_text = "\n\n".join(texts)
        labeled_text = "\n\n".join(labeled_parts)
        return merged_text, sources, trace, labeled_text
```

注意：原代码对空 url 的专源结果（`r.url=""`）不加入 seen_urls 去重（既有行为，sources.py:47 的 iTunes 可能空 url）。这里保留：空 url 走 `if r.url not in seen_urls`（`"" not in seen_urls` 为真）→ `_add` 进 texts/labeled，但不进 sources、不进 seen_urls。

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/unit/test_collection_pipeline.py -v`
Expected: PASS（新用例通过；既有 pipeline 测试若解包 3 元组会 FAIL → 见 Step 5）

- [ ] **Step 5: 修既有测试的解包 + collector 调用点**

既有测试和 collector 都按 3 元组解包 `collect`。先查所有调用点：

Run: `grep -rn "\.collect(" tests/unit/test_collection_pipeline.py src/agents/collector.py`

对 `tests/unit/test_collection_pipeline.py` 中每个 `merged, sources, trace = await pipe.collect(...)` 改为 `merged, sources, trace, _ = await pipe.collect(...)`（多解一个忽略值）。collector 的调用点在 Task 3 改，本步只修测试。

Run: `pytest tests/unit/test_collection_pipeline.py -v`
Expected: PASS（全绿）

- [ ] **Step 6: 提交**

```bash
git add src/agents/collection_pipeline.py tests/unit/test_collection_pipeline.py
git commit -m "feat: collection_pipeline 输出带来源标记的分段文本（labeled_text）"
```

---

## Task 3: collector 用 labeled_text 抽取并绑定每个 fact 的 source_url

**Files:**
- Modify: `src/agents/collector.py:86-128`（`_extract_profile` 和 `_collect_single`）
- Modify: `src/agents/prompts.py`（`COLLECTOR_EXTRACT_SYSTEM`）
- Test: `tests/unit/test_collector.py`

`_collect_single` 解包改 4 元组，把 `labeled_text` 喂给 `_extract_profile`；prompt 要求 LLM 给每个 feature/pricing tier/review/update 填来自的【来源】URL。

- [ ] **Step 1: 写失败测试**

在 `tests/unit/test_collector.py` 末尾追加：

```python
@pytest.mark.asyncio
async def test_extract_uses_labeled_text_and_binds_source_url():
    """_extract_profile 把 labeled_text 传给 LLM，LLM 填的 feature source_url 被保留。"""
    captured = {}

    class _LLM:
        async def call_json(self, system, user):
            captured["user"] = user
            return {
                "basic_info": {"name": "X", "company": ""},
                "feature_tree": [{"module": "M", "features": [
                    {"name": "f1", "description": "d", "source_url": "https://a.com"}
                ]}],
                "pricing": {"model": "免费", "tiers": []},
                "user_reviews": {"rating": 0, "total_reviews": 0, "sample_reviews": []},
                "recent_updates": [],
            }

    from src.agents.collector import CollectorAgent
    agent = CollectorAgent(llm=_LLM(), pipeline=None)
    profile = await agent._extract_profile(
        "X", "【来源: https://a.com】\n正文", {"competitor_type": "核心竞品", "reason": "r"},
        ["https://a.com"], [],
    )
    assert "【来源: https://a.com】" in captured["user"]  # labeled 文本入 prompt
    assert profile.feature_tree[0].features[0].source_url == "https://a.com"  # source_url 绑定保留
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/unit/test_collector.py::test_extract_uses_labeled_text_and_binds_source_url -v`
Expected: PASS 或 FAIL——若当前 `_extract_profile` 的 prompt 用 `text[:8000]` 且测试传的是 labeled 文本，prompt 断言可能已过（因为是直接传入参数）。真正会失败的是若 source_url 未保留。先跑确认基线，FAIL 点应在 prompt 未含完整 labeled 标记（当前 `text[:8000]` 截断不影响短文本，故此用例主要锁定行为不回归）。若全过，说明 schema 已支持 source_url（profile.py:25 确有），则本测试作为回归保护。

- [ ] **Step 3: 改 prompts.py 的 COLLECTOR_EXTRACT_SYSTEM**

完整替换 `src/agents/prompts.py` 中 `COLLECTOR_EXTRACT_SYSTEM`：

```python
COLLECTOR_EXTRACT_SYSTEM = """你是一个竞品信息抽取助手。从给定的网页文本中提取结构化的竞品信息。

输入文本中每段正文前有【来源: URL】标记，标识该段内容来自哪个网页。提取每条信息时，必须把它所在段落的来源 URL 填入对应的 source_url 字段——这是信息溯源的依据，不可编造、不可留空（除非该信息确实跨多段无法定位）。

必须返回 JSON 格式（无法提取的字段留空字符串或空列表）：
{
  "basic_info": {"name": "", "company": "", "version": "", "release_date": "", "platform": []},
  "feature_tree": [{"module": "", "features": [{"name": "", "description": "", "is_new": false, "source_url": "该功能所在段落的【来源】URL"}]}],
  "pricing": {"model": "", "tiers": [{"name": "", "price": "", "features": []}], "source_url": "定价信息所在段落的【来源】URL"},
  "user_reviews": {"rating": 0, "total_reviews": 0, "positive_summary": "", "negative_summary": "", "sample_reviews": [{"content": "", "rating": 3, "source": "", "source_url": "该评论所在段落的【来源】URL"}]},
  "recent_updates": [{"date": "", "title": "", "summary": "", "source_url": "该更新所在段落的【来源】URL"}]
}

注意：sample_reviews 的每个元素必须是对象，含 content、rating（1-5 整数）、source、source_url 字段，不能是纯字符串。每条信息的 source_url 必须来自输入文本里出现过的【来源】URL，禁止编造未出现的链接。"""
```

- [ ] **Step 4: 改 collector.py**

改 `_extract_profile` 用全量 labeled 文本（删 8000 截断），改 `_collect_single` 解包 4 元组。

`src/agents/collector.py:86-89`（`_extract_profile` 开头）改为：

```python
    async def _extract_profile(self, name: str, text: str, classification: dict,
                               sources: list[str], pipeline_trace: list[dict]) -> CompetitorProfile:
        """从带来源标记的文本中抽取结构化竞品画像（不截断，依赖 256K 上下文）"""
        prompt = f"竞品名称：{name}\n\n网页文本内容（每段前有【来源: URL】标记）：\n{text}"
```

（即把原 `text[:8000]` 改为 `text`，并更新 docstring 与提示语。其余 `_extract_profile` 主体不变。）

`src/agents/collector.py:118-128`（`_collect_single`）改为：

```python
    async def _collect_single(self, comp: CompetitorBasic, goal: AnalysisGoal) -> CompetitorProfile:
        """采集单个竞品：分类 → 类别路由 → 管线采集 → 抽取/占位。"""
        classification = await self.classify_competitor(comp.name, goal)
        category = self.detect_category(comp)
        merged_text, sources, trace, labeled_text = await self.pipeline.collect(comp.name, category)
        if not merged_text.strip():
            logger.info("[collector] %s 全空, 产占位 profile", comp.name)
            return self._build_placeholder_profile(comp, classification, trace)
        profile = await self._extract_profile(comp.name, labeled_text, classification, sources, trace)
        logger.info("[collector] %s 采集完成, completeness=%.2f", comp.name, profile.metadata.completeness_score)
        return profile
```

- [ ] **Step 5: 跑测试确认通过**

Run: `pytest tests/unit/test_collector.py -v`
Expected: PASS（含新用例；若既有 collector 测试 mock 了 `pipeline.collect` 返回 3 元组，需改 mock 返回 4 元组——见下）

- [ ] **Step 6: 修既有 collector 测试的 pipeline mock**

Run: `grep -rn "collect" tests/unit/test_collector.py`

把所有 mock `pipeline.collect` 返回 `(merged, sources, trace)` 的地方，改为返回 `(merged, sources, trace, labeled)`（labeled 用 merged 同值或带标记的等价文本即可）。

Run: `pytest tests/unit/test_collector.py -v`
Expected: PASS

- [ ] **Step 7: 提交**

```bash
git add src/agents/collector.py src/agents/prompts.py tests/unit/test_collector.py
git commit -m "feat: collector 用 labeled_text 抽取并绑定每条信息的 source_url（删 8000 截断）"
```

---

## Task 4: analyzer 补 source_urls 输出槽 + 代码兜底回填

**Files:**
- Modify: `src/agents/prompts.py`（`ANALYZER_SYSTEM`）
- Modify: `src/agents/analyzer.py`（`_backfill_source_urls` + `analyze` 调用）
- Test: `tests/unit/test_analyzer.py`

prompt 给各维度补 source_urls 槽。代码兜底：从 profiles 聚合 fact 的 source_url，若 LLM 输出某维度 source_urls 为空，用全量 URL 集合兜底回填（维度+竞品级粒度）。

- [ ] **Step 1: 写失败测试**

在 `tests/unit/test_analyzer.py` 末尾追加：

```python
def test_backfill_dimension_source_urls_from_profiles():
    from src.agents.analyzer import AnalyzerAgent
    from src.schemas.profile import (
        CompetitorProfile, Classification, BasicInfo, ProfileMetadata,
        FeatureTree, Feature, Pricing,
    )
    profile = CompetitorProfile(
        classification=Classification(competitor_type="核心竞品", reason="r"),
        basic_info=BasicInfo(name="X"),
        feature_tree=[FeatureTree(module="M", features=[
            Feature(name="f", source_url="https://a.com")])],
        pricing=Pricing(model="免费", source_url="https://b.com"),
        metadata=ProfileMetadata(collected_at="t", data_sources=["https://a.com", "https://b.com"]),
    )
    result = {
        "positioning": {"per_competitor": [], "source_urls": []},
        "feature_matrix": [],
        "business_model": {"per_competitor": [], "source_urls": []},
        "operations": {"per_competitor": [], "source_urls": []},
        "user_sentiment": {"summary": "", "per_competitor": {}, "source_urls": []},
        "swot": {"strengths": [], "weaknesses": [], "opportunities": [], "threats": []},
        "radar_scores": [],
    }
    out = AnalyzerAgent._backfill_source_urls(result, [profile])
    assert set(out["positioning"]["source_urls"]) == {"https://a.com", "https://b.com"}
    assert set(out["business_model"]["source_urls"]) == {"https://a.com", "https://b.com"}


def test_backfill_does_not_overwrite_nonempty():
    from src.agents.analyzer import AnalyzerAgent
    from src.schemas.profile import CompetitorProfile, Classification, BasicInfo, ProfileMetadata
    profile = CompetitorProfile(
        classification=Classification(competitor_type="核心竞品", reason="r"),
        basic_info=BasicInfo(name="X"),
        metadata=ProfileMetadata(collected_at="t", data_sources=["https://fallback.com"]),
    )
    result = {"positioning": {"per_competitor": [], "source_urls": ["https://llm-picked.com"]}}
    out = AnalyzerAgent._backfill_source_urls(result, [profile])
    assert out["positioning"]["source_urls"] == ["https://llm-picked.com"]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/unit/test_analyzer.py::test_backfill_dimension_source_urls_from_profiles tests/unit/test_analyzer.py::test_backfill_does_not_overwrite_nonempty -v`
Expected: FAIL（`_backfill_source_urls` 不存在）

- [ ] **Step 3: 改 analyzer.py 加兜底方法**

在 `src/agents/analyzer.py` 的 `AnalyzerAgent` 类内（`_normalize` 之后）加静态方法：

```python
    @staticmethod
    def _backfill_source_urls(result: dict, profiles: list) -> dict:
        """维度级 source_urls 兜底：LLM 漏填则用所有 profile 的 data_sources 回填。"""
        all_urls = sorted({
            u for p in profiles
            for u in (p.metadata.data_sources if hasattr(p, "metadata") else [])
        })
        if not all_urls:
            return result
        for dim_key in ("positioning", "business_model", "operations", "user_sentiment"):
            dim = result.get(dim_key)
            if isinstance(dim, dict) and not dim.get("source_urls"):
                dim["source_urls"] = list(all_urls)
        for entry in result.get("feature_matrix", []):
            if isinstance(entry, dict) and not entry.get("source_urls"):
                entry["source_urls"] = list(all_urls)
        return result
```

- [ ] **Step 4: 在 analyze 里调用兜底**

`src/agents/analyzer.py` 的 `analyze` 方法，首次构造（约 :67）改为先 normalize 再 backfill：

```python
        result = self._backfill_source_urls(
            self._normalize(await self.llm.call_json(ANALYZER_SYSTEM, prompt)),
            profiles,
        )
```

重试分支（约 :73）同样改：

```python
            result = self._backfill_source_urls(
                self._normalize(await self.llm.call_json(ANALYZER_SYSTEM, prompt)),
                profiles,
            )
```

- [ ] **Step 5: 改 ANALYZER_SYSTEM prompt**

完整替换 `src/agents/prompts.py` 的 `ANALYZER_SYSTEM`：

```python
ANALYZER_SYSTEM = """你是一个资深竞品分析师。基于提供的竞品画像数据，进行四维度结构化深度分析。

要求：每个维度的结论必须做横向对比（竞品之间、竞品与"我方"之间），用画像里的具体数据/功能/评分举证，不要泛泛而谈。每个维度填写 source_urls：把你引用的画像信息对应的 source_url 收集进去（画像各 fact 带 source_url）。

必须返回 JSON 格式：
{
  "positioning": {"per_competitor": [{"name": "", "target_users": "", "core_scenario": "", "pain_points": "", "value_proposition": ""}], "source_urls": []},
  "feature_matrix": [{"feature": "", "our_product": "无", "competitors": {"竞品名": "有/无/部分支持"}, "gap_level": "领先/持平/落后/差异化", "evidence": "引用具体数据", "source_urls": []}],
  "business_model": {"per_competitor": [{"name": "", "revenue_model": "", "pricing_details": "", "free_vs_paid": ""}], "source_urls": []},
  "operations": {"per_competitor": [{"name": "", "growth_strategy": "", "marketing_channels": "", "content_strategy": ""}], "source_urls": []},
  "user_sentiment": {"summary": "", "per_competitor": {"竞品名": ""}, "source_urls": []},
  "swot": {
    "strengths": [{"point": "", "evidence": "", "dimension": "positioning/feature/business/operations", "source_urls": []}],
    "weaknesses": [...], "opportunities": [...], "threats": [...]
  },
  "radar_scores": [{"competitor": "", "dimensions": {"feature_breadth": 0, "usability": 0, "cost_effectiveness": 0, "stability": 0, "design_quality": 0}}]
}

每条结论的 evidence 必须引用具体数据，不可空泛。radar_scores 的 dimensions 每项必须填 0-5 之间的数字，每个竞品都要有一条 radar_score。source_urls 只填画像里实际出现过的 URL。"""
```

- [ ] **Step 6: 跑测试确认通过**

Run: `pytest tests/unit/test_analyzer.py -v`
Expected: PASS（2 个新用例 + 原有不回归）

- [ ] **Step 7: 提交**

```bash
git add src/agents/analyzer.py src/agents/prompts.py tests/unit/test_analyzer.py
git commit -m "feat: analyzer 补 source_urls 输出槽 + 代码兜底回填维度溯源"
```

---

## Task 5: writer 机械透传结构化字段 + 删截断

**Files:**
- Modify: `src/agents/writer.py`（`write` 方法）
- Test: `tests/unit/test_writer.py`

writer 在 `FinalReport(**result)` 之后、return 之前，用代码把 analysis 的 swot/radar_scores/feature_matrix 直接搬进 report（不靠 LLM）。删 8000 截断。

- [ ] **Step 1: 写失败测试**

在 `tests/unit/test_writer.py` 末尾追加：

```python
@pytest.mark.asyncio
async def test_writer_mechanically_transfers_structured_fields():
    from src.agents.writer import WriterAgent
    from src.schemas.analysis import (
        CompetitiveAnalysis, Swot, SwotEntry, RadarScore, RadarDimensions,
        FeatureMatrixEntry,
    )
    analysis = CompetitiveAnalysis(
        swot=Swot(strengths=[SwotEntry(point="强")]),
        radar_scores=[RadarScore(competitor="X", dimensions=RadarDimensions(
            feature_breadth=4, usability=4, cost_effectiveness=3, stability=4, design_quality=5))],
        feature_matrix=[FeatureMatrixEntry(feature="f")],
    )

    class _LLM:
        async def call_json(self, system, user):
            return {
                "title": "报告",
                "executive_summary": {
                    "what_competitors_did_right": "x" * 20,
                    "what_competitors_did_wrong": "x" * 20,
                    "our_opportunities": "x" * 20,
                    "next_steps_summary": "x" * 20,
                },
                "sections": [{"title": "概览", "content": "c"}],
                "action_items": {"immediate": [{"priority": "高", "description": "d"}],
                                 "short_term": [{"priority": "中", "description": "d"}],
                                 "long_term": [{"priority": "低", "description": "d"}]},
            }

    report = await WriterAgent(llm=_LLM()).write(analysis, ["X"])
    assert report.swot.strengths[0].point == "强"
    assert report.radar_scores[0].competitor == "X"
    assert report.feature_matrix[0].feature == "f"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/unit/test_writer.py::test_writer_mechanically_transfers_structured_fields -v`
Expected: FAIL（report.swot 为空默认，未透传）

- [ ] **Step 3: 改 writer.py 的 write 方法**

完整替换 `src/agents/writer.py` 的 `write` 方法（删 8000 截断 + 透传）：

```python
    async def write(self, analysis: CompetitiveAnalysis, competitors: list[str]) -> FinalReport:
        """基于分析结果生成最终报告（结构化字段由代码透传，不赌 LLM）"""
        logger.info("[writer] 开始撰写报告, 竞品: %s", competitors)

        analysis_data = analysis.model_dump()
        analysis_text = json.dumps(analysis_data, ensure_ascii=False, indent=2)

        prompt = f"请基于以下分析数据撰写竞品报告：\n\n竞品列表：{competitors}\n\n分析数据：\n{analysis_text}"
        result = self._normalize(await self.llm.call_json(WRITER_SYSTEM, prompt), competitors)

        try:
            report = FinalReport(**result)
        except ValidationError as e:
            logger.warning("[writer] Pydantic 校验失败, 重试: %s", e)
            result = self._normalize(await self.llm.call_json(WRITER_SYSTEM, prompt), competitors)
            try:
                report = FinalReport(**result)
            except ValidationError as e2:
                logger.error("[writer] 重试后仍然失败: %s, raw=%s", e2, result)
                raise ValueError(f"Writer output validation failed after retry: {e2}") from e2

        # 结构化产物由代码直接透传，100% 不丢（不依赖 LLM 输出）
        report.swot = analysis.swot
        report.radar_scores = analysis.radar_scores
        report.feature_matrix = analysis.feature_matrix

        logger.info("[writer] 报告撰写完成: %s", report.title)
        return report
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/unit/test_writer.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/agents/writer.py tests/unit/test_writer.py
git commit -m "feat: writer 机械透传 SWOT/雷达/功能矩阵 + 删 8000 截断"
```

---

## Task 6: writer 按 dimension 机械下沉 source_refs + 过滤幻觉 URL

**Files:**
- Modify: `src/agents/writer.py`（加 `_collect_analysis_urls`/`_downpour_source_refs` + write 调用）
- Modify: `src/agents/prompts.py`（`WRITER_SYSTEM`）
- Test: `tests/unit/test_writer.py`

- [ ] **Step 1: 写失败测试**

在 `tests/unit/test_writer.py` 末尾追加：

```python
def test_downpour_maps_dimension_to_source_refs():
    from src.agents.writer import WriterAgent
    from src.schemas.analysis import CompetitiveAnalysis, Positioning, BusinessModel
    from src.schemas.report import FinalReport, ReportSection
    analysis = CompetitiveAnalysis(
        positioning=Positioning(source_urls=["https://pos.com"]),
        business_model=BusinessModel(source_urls=["https://biz.com"]),
    )
    report = FinalReport(title="t", sections=[
        ReportSection(title="定位", dimension="positioning"),
        ReportSection(title="商业", dimension="business_model"),
        ReportSection(title="综述", dimension="overview"),
    ])
    WriterAgent._downpour_source_refs(report, analysis)
    assert report.sections[0].source_refs == ["https://pos.com"]
    assert report.sections[1].source_refs == ["https://biz.com"]
    assert set(report.sections[2].source_refs) == {"https://pos.com", "https://biz.com"}


def test_filter_hallucinated_action_item_urls():
    from src.agents.writer import WriterAgent
    from src.schemas.analysis import CompetitiveAnalysis, Positioning
    from src.schemas.report import FinalReport, ActionItems, ActionItem
    analysis = CompetitiveAnalysis(positioning=Positioning(source_urls=["https://real.com"]))
    report = FinalReport(title="t", action_items=ActionItems(
        immediate=[ActionItem(priority="高", description="d",
                              source_urls=["https://real.com", "https://fake.com"])]))
    WriterAgent._downpour_source_refs(report, analysis)
    assert report.action_items.immediate[0].source_urls == ["https://real.com"]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/unit/test_writer.py::test_downpour_maps_dimension_to_source_refs tests/unit/test_writer.py::test_filter_hallucinated_action_item_urls -v`
Expected: FAIL（`_downpour_source_refs` 不存在）

- [ ] **Step 3: 改 writer.py 加下沉方法**

在 `src/agents/writer.py` 的 `WriterAgent` 类内加：

```python
    @staticmethod
    def _collect_analysis_urls(analysis) -> dict:
        """收集 analysis 各维度的 source_urls，返回 {dimension_key: [urls]}。"""
        return {
            "positioning": list(analysis.positioning.source_urls),
            "business_model": list(analysis.business_model.source_urls),
            "operations": list(analysis.operations.source_urls),
            "user_sentiment": list(analysis.user_sentiment.source_urls),
            "feature_matrix": sorted({u for e in analysis.feature_matrix for u in e.source_urls}),
            "swot": sorted({
                u for key in ("strengths", "weaknesses", "opportunities", "threats")
                for entry in getattr(analysis.swot, key)
                for u in entry.source_urls
            }),
        }

    @classmethod
    def _downpour_source_refs(cls, report, analysis) -> None:
        """按 section.dimension 下沉 source_refs；过滤 action_item 幻觉 URL（原地修改）。"""
        dim_urls = cls._collect_analysis_urls(analysis)
        all_urls = sorted({u for urls in dim_urls.values() for u in urls})
        for sec in report.sections:
            if sec.source_refs:
                continue
            if sec.dimension == "overview":
                sec.source_refs = list(all_urls)
            else:
                sec.source_refs = list(dim_urls.get(sec.dimension, []))
        pool = set(all_urls)
        for layer in (report.action_items.immediate, report.action_items.short_term,
                      report.action_items.long_term):
            for item in layer:
                item.source_urls = [u for u in item.source_urls if u in pool]
```

- [ ] **Step 4: 在 write 里调用下沉**

`src/agents/writer.py` 的 `write` 方法，在 Task 5 的三行透传之后、`logger.info("[writer] 报告撰写完成"...)` 之前加：

```python
        self._downpour_source_refs(report, analysis)
```

- [ ] **Step 5: 改 WRITER_SYSTEM prompt**

完整替换 `src/agents/prompts.py` 的 `WRITER_SYSTEM`：

```python
WRITER_SYSTEM = """你是一个资深竞品报告撰写助手。基于竞品分析数据，撰写有深度、有洞察的结构化竞品分析报告。

撰写要求：
- 执行摘要四段要写透，给出具体判断而非套话。
- sections 每个章节要展开论证：做横向对比、引用分析数据里的具体功能/定价/评分，给出"所以呢"的洞察，不要罗列。每个章节标注它对应的分析维度（dimension）。
- action_items 每条建议给出 rationale，并在 source_urls 里列出你引用的分析数据来源 URL（只能用分析数据里出现过的 URL，禁止编造）。

必须返回 JSON 格式：
{
  "title": "报告标题",
  "executive_summary": {
    "what_competitors_did_right": "竞品做对了什么？哪些值得借鉴？",
    "what_competitors_did_wrong": "竞品的短板在哪里？",
    "our_opportunities": "我们的差异化机会是什么？",
    "next_steps_summary": "接下来优先做什么？"
  },
  "sections": [{"title": "", "content": "Markdown 深度内容", "dimension": "positioning/feature_matrix/business_model/operations/user_sentiment/swot/overview"}],
  "action_items": {
    "immediate": [{"priority": "高/中/低", "description": "", "rationale": "", "source_urls": []}],
    "short_term": [...],
    "long_term": [...]
  }
}

executive_summary 四段必须全部填写。action_items 每个时间层至少 1 条。SWOT、雷达评分、功能矩阵由系统自动从分析数据填充，你不需要输出它们。"""
```

- [ ] **Step 6: 跑测试确认通过**

Run: `pytest tests/unit/test_writer.py -v`
Expected: PASS（新用例 + Task5 用例不回归）

- [ ] **Step 7: 提交**

```bash
git add src/agents/writer.py src/agents/prompts.py tests/unit/test_writer.py
git commit -m "feat: writer 按 dimension 机械下沉 source_refs + 过滤幻觉 URL + prompt 思考式"
```

---

## Task 7: inspector 补程序化硬查 + severity 分级 pass/fail

**Files:**
- Modify: `src/agents/inspector.py`
- Modify: `src/agents/prompts.py`（`INSPECTOR_SYSTEM`）
- Test: `tests/unit/test_inspector.py`

- [ ] **Step 1: 写失败测试**

在 `tests/unit/test_inspector.py` 末尾追加：

```python
@pytest.mark.asyncio
async def test_inspector_hard_checks_swot_radar_matrix_traceability():
    from src.agents.inspector import InspectorAgent
    from src.schemas.report import FinalReport, ReportSection
    report = FinalReport(
        title="t",
        sections=[ReportSection(title="s", content="有内容", dimension="positioning")],
    )

    class _LLM:
        async def call_json(self, system, user):
            return {"passed": True, "issues": []}

    fb = await InspectorAgent(llm=_LLM()).inspect(report, competitors=["X"])
    fields = {i.field for i in fb.issues}
    assert "swot" in fields
    assert "radar_scores" in fields
    assert "feature_matrix" in fields
    assert any("source_refs" in f for f in fields)


def test_minor_issues_do_not_block_pass():
    from src.agents.inspector import _MINOR_ONLY_PASS
    from src.schemas.feedback import FeedbackIssue
    issues = [FeedbackIssue(agent="writer", field="x", severity="minor", reason="r")]
    assert _MINOR_ONLY_PASS(issues) is True
    issues2 = [FeedbackIssue(agent="writer", field="y", severity="major", reason="r")]
    assert _MINOR_ONLY_PASS(issues2) is False
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/unit/test_inspector.py::test_inspector_hard_checks_swot_radar_matrix_traceability tests/unit/test_inspector.py::test_minor_issues_do_not_block_pass -v`
Expected: FAIL（`inspect` 无 competitors 参数 / `_MINOR_ONLY_PASS` 不存在 / 硬查未实现）

- [ ] **Step 3: 改 inspector.py**

在 `src/agents/inspector.py` 顶部（import 之后、类定义之前）加模块级 helper：

```python
def _MINOR_ONLY_PASS(issues) -> bool:
    """只有 minor issue（或无 issue）时视为通过；critical/major 阻断。"""
    return all(i.severity == "minor" for i in issues)
```

把 `_programmatic_checks` 签名改为接收 competitors，并在原 `return issues` 之前插入硬查：

```python
    def _programmatic_checks(self, report: FinalReport, competitors: list[str]) -> list[FeedbackIssue]:
```

（原方法体保留——执行摘要四段检查、行动建议每层检查、章节非空检查——在 `return issues` 之前加：）

```python
        # SWOT 四象限至少各 1 条
        sw = report.swot
        if not (sw.strengths and sw.weaknesses and sw.opportunities and sw.threats):
            issues.append(FeedbackIssue(
                agent="analyzer", field="swot",
                severity="major", reason="SWOT 四象限不完整",
                suggestion="每个象限至少 1 条"))

        # 雷达：每个竞品一条
        radar_comps = {r.competitor for r in report.radar_scores}
        if not all(c in radar_comps for c in competitors):
            issues.append(FeedbackIssue(
                agent="analyzer", field="radar_scores",
                severity="major", reason="雷达评分缺竞品",
                suggestion="每个竞品填一条 0-5 五维评分"))

        # 功能矩阵非空
        if not report.feature_matrix:
            issues.append(FeedbackIssue(
                agent="analyzer", field="feature_matrix",
                severity="major", reason="功能矩阵为空",
                suggestion="至少补充关键功能对比"))

        # 维度级溯源：有内容的 section 必须有 source_refs
        for idx, sec in enumerate(report.sections):
            if sec.content.strip() and not sec.source_refs:
                issues.append(FeedbackIssue(
                    agent="writer", field=f"sections[{idx}].source_refs",
                    severity="major", reason=f"章节「{sec.title}」无溯源",
                    suggestion="标注该章节引用的来源 URL"))

        # action_item 溯源：软查（minor，不阻断 pass）
        for layer_name, layer in [("immediate", report.action_items.immediate),
                                   ("short_term", report.action_items.short_term),
                                   ("long_term", report.action_items.long_term)]:
            for j, item in enumerate(layer):
                if not item.source_urls:
                    issues.append(FeedbackIssue(
                        agent="writer", field=f"action_items.{layer_name}[{j}].source_urls",
                        severity="minor", reason="行动建议未标注来源",
                        suggestion="补充支撑该建议的来源 URL"))
```

完整替换 `inspect` 方法（加 competitors 参数、删 15000 截断、pass 用 `_MINOR_ONLY_PASS`）：

```python
    async def inspect(self, report: FinalReport, competitors: list[str] | None = None,
                      retry_count: int = 0, max_retries: int = 2) -> RejectionFeedback:
        """执行质量检查"""
        logger.info("[inspector] 开始质检, retry_count=%d", retry_count)
        competitors = competitors or []

        programmatic_issues = self._programmatic_checks(report, competitors)

        report_text = report.model_dump_json()
        llm_result = await self.llm.call_json(INSPECTOR_SYSTEM, f"请检查以下报告：\n\n{report_text}")

        llm_issues = [FeedbackIssue(**issue) for issue in llm_result.get("issues", [])]
        all_issues = programmatic_issues + llm_issues

        seen = set()
        unique_issues = []
        for issue in sorted(all_issues, key=lambda i: {"critical": 0, "major": 1, "minor": 2}[i.severity]):
            key = (issue.agent, issue.field)
            if key not in seen:
                seen.add(key)
                unique_issues.append(issue)

        passed = _MINOR_ONLY_PASS(unique_issues)

        feedback = RejectionFeedback(
            passed=passed, issues=unique_issues,
            retry_count=retry_count, max_retries=max_retries,
        )
        logger.info("[inspector] 质检完成, passed=%s, issues=%d", passed, len(unique_issues))
        return feedback
```

- [ ] **Step 4: 改 INSPECTOR_SYSTEM prompt**

完整替换 `src/agents/prompts.py` 的 `INSPECTOR_SYSTEM`：

```python
INSPECTOR_SYSTEM = """你是一个竞品报告质检助手。检查报告的完整性、深度和数据支撑。

检查项：
1. Schema 完整性：必填字段是否为空
2. 数据支撑：每条结论是否有 evidence 和来源
3. 执行摘要：四段是否都填写、是否言之有物（过短或套话视为问题）
4. 行动建议：每个时间层是否至少 1 条、是否有依据
5. 深度：章节是否做了横向对比和洞察，而非罗列

严重度：critical=必填缺失/结构损坏；major=关键内容缺失或无溯源；minor=可改进项。
（SWOT/雷达/功能矩阵/章节溯源由程序另行硬查，你聚焦内容质量与深度。）

必须返回 JSON 格式：
{
  "passed": true/false,
  "issues": [
    {"agent": "collector/analyzer/writer", "field": "字段路径", "severity": "critical/major/minor", "reason": "问题描述", "suggestion": "修改建议"}
  ]
}"""
```

- [ ] **Step 5: 跑测试确认通过**

Run: `pytest tests/unit/test_inspector.py -v`
Expected: PASS（新用例 + 既有不回归；既有 `inspect(report, retry_count=...)` 因 competitors 默认 None 仍兼容）

- [ ] **Step 6: 提交**

```bash
git add src/agents/inspector.py src/agents/prompts.py tests/unit/test_inspector.py
git commit -m "feat: inspector 补 SWOT/雷达/矩阵/溯源硬查 + severity 分级 pass/fail + 删 15000 截断"
```

---

## Task 8: graph 打通 focus_area + 传竞品名单 + 修 analyzer 反馈路由

**Files:**
- Modify: `src/graph/state.py`
- Modify: `src/agents/collector.py`（`collect` 返回 goal）
- Modify: `src/graph/builder.py`
- Test: `tests/unit/test_collector.py`

- [ ] **Step 1: 写失败测试**

在 `tests/unit/test_collector.py` 末尾追加：

```python
@pytest.mark.asyncio
async def test_collect_returns_goal_with_profiles():
    from src.agents.collector import CollectorAgent
    from src.schemas.input import CompetitorInput, CompetitorBasic

    class _LLM:
        async def call_json(self, system, user):
            if "goal_type" in system:
                return {"goal_type": "feature_iteration", "product_stage": "growing",
                        "focus_area": "协作功能", "output_expectation": "action"}
            return {"competitor_type": "核心竞品", "reason": "r"}

    class _Pipe:
        async def collect(self, name, category):
            return ("", [], [], "")

    agent = CollectorAgent(llm=_LLM(), pipeline=_Pipe())
    user_input = CompetitorInput(competitors=[CompetitorBasic(name="X")],
                                 analysis_context="分析协作功能")
    profiles, goal = await agent.collect(user_input)
    assert goal.focus_area == "协作功能"
    assert len(profiles) == 1
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/unit/test_collector.py::test_collect_returns_goal_with_profiles -v`
Expected: FAIL（`collect` 只返回 profiles 列表，解包 2 个报 ValueError）

- [ ] **Step 3: 改 collector.collect 返回 goal**

`src/agents/collector.py` 的 `collect` 方法末尾 `return profiles` 改为：

```python
        return profiles, goal
```

- [ ] **Step 4: 改 state.py 加 analysis_goal**

`src/graph/state.py` 顶部 import 改为：

```python
from src.schemas.input import CompetitorInput, AnalysisGoal
```

在 `AnalysisState` 的 `profiles` 字段之后加：

```python
    # 采集阶段解析的分析目标（供 focus_area 回填报告）
    analysis_goal: AnalysisGoal
```

- [ ] **Step 5: 改 builder.py 各节点**

`collector_node` 改为存 goal：

```python
    async def collector_node(state: AnalysisState) -> dict:
        logger.info("[graph] → collector")
        node_trace.append("collector")
        profiles, goal = await collector.collect(state["user_input"])
        _save("01_profiles", profiles)
        return {"profiles": profiles, "analysis_goal": goal, "current_node": "collector"}
```

`writer_node` 在 sources 回填之后加 focus_area 回填：

```python
        if sources:
            report.metadata.data_sources = sources
        goal = state.get("analysis_goal")
        if goal is not None:
            report.metadata.analysis_goal = goal
        _save("03_report", report)
        return {"report": report, "current_node": "writer"}
```

`inspector_node` 传竞品名单：

```python
        competitors = [c.name for c in state["user_input"].competitors]
        feedback = await inspector.inspect(
            report,
            competitors=competitors,
            retry_count=state.get("retry_count", 0),
            max_retries=state.get("max_retries", 2),
        )
```

`should_continue` 认 analyzer：

```python
        target_agents = {issue.agent for issue in feedback.issues}
        issues_summary = [f"{i.agent}:{i.severity}:{i.field}" for i in feedback.issues]
        if "collector" in target_agents:
            target = "collector"
        elif "analyzer" in target_agents:
            target = "analyzer"
        else:
            target = "writer"
        node_trace.append(f"reject->{target} issues={issues_summary}")
        return target
```

conditional_edges 加 analyzer 分支：

```python
    graph.add_conditional_edges("inspector", should_continue, {
        "end": END,
        "collector": "collector",
        "analyzer": "analyzer",
        "writer": "writer",
    })
```

- [ ] **Step 6: 跑测试确认通过**

Run: `pytest tests/unit/test_collector.py -v`
Expected: PASS

- [ ] **Step 7: 跑全量测试确认无回归**

Run: `pytest -q`
Expected: PASS（若别处旧用例解包 `collector.collect` 为单值，按报错同步改为 `profiles, goal = ...`）

- [ ] **Step 8: 提交**

```bash
git add src/graph/state.py src/graph/builder.py src/agents/collector.py tests/unit/test_collector.py
git commit -m "feat: graph 打通 focus_area 回填 + inspector 传竞品名单 + should_continue 认 analyzer 回边"
```

---

## Task 9: 前端渲染 SWOT/雷达/功能矩阵/溯源链接

**Files:**
- Modify: `src/frontend/app.py`

前端是手动验证、无单测。

- [ ] **Step 1: 改 app.py 报告渲染**

把「详细报告」section 循环（约 :88-91）改为加溯源链接：

```python
                    # 报告章节
                    st.header("详细报告")
                    for section in report.get("sections", []):
                        st.subheader(section.get("title", ""))
                        st.markdown(section.get("content", ""))
                        refs = section.get("source_refs", [])
                        if refs:
                            st.caption("来源：" + " ".join(f"[{i+1}]({u})" for i, u in enumerate(refs)))
```

在「详细报告」之后、「元数据」expander 之前加结构化区块：

```python
                    # 功能矩阵
                    fm = report.get("feature_matrix", [])
                    if fm:
                        st.header("功能矩阵")
                        st.dataframe([
                            {"功能": e.get("feature", ""), "我方": e.get("our_product", ""),
                             "差距": e.get("gap_level", ""),
                             **{k: v for k, v in (e.get("competitors") or {}).items()}}
                            for e in fm
                        ])

                    # SWOT
                    swot = report.get("swot", {})
                    if any(swot.get(k) for k in ("strengths", "weaknesses", "opportunities", "threats")):
                        st.header("SWOT 分析")
                        sc1, sc2 = st.columns(2)
                        for col, key, label in [
                            (sc1, "strengths", "优势 S"), (sc2, "weaknesses", "劣势 W"),
                            (sc1, "opportunities", "机会 O"), (sc2, "threats", "威胁 T"),
                        ]:
                            with col:
                                st.subheader(label)
                                for entry in swot.get(key, []):
                                    st.markdown(f"- {entry.get('point', '')}")

                    # 雷达评分
                    radar = report.get("radar_scores", [])
                    if radar:
                        st.header("雷达评分（0-5）")
                        st.dataframe([
                            {"竞品": r.get("competitor", ""), **r.get("dimensions", {})}
                            for r in radar
                        ])
```

- [ ] **Step 2: 手动验证**

```bash
# 终端1
uvicorn src.api.main:app --reload
# 终端2
streamlit run src/frontend/app.py
```

浏览器跑一次分析（推荐 SaaS：语雀 vs 飞书，配 SEARCH_API_KEY 走搜索主线）。验证：
- 详细报告各章节下有「来源：[1][2]」可点击链接
- 功能矩阵表非空
- SWOT 四象限有内容
- 雷达评分表每竞品一行、五维 0-5
- 元数据里 analysis_goal.focus_area 非空（若分析意图提了关注领域）
- 执行追溯面板看 04_feedback：issues 不再是三类老问题、quality_score ≥ 0.7

- [ ] **Step 3: 提交**

```bash
git add src/frontend/app.py
git commit -m "feat: 前端渲染 SWOT/雷达/功能矩阵 + 章节溯源链接"
```

---

## 收尾：全量验证 + 文档

- [ ] 全量测试：`pytest -q` → 全绿
- [ ] lint：`ruff check src tests` → 全清（必要时 `ruff check --fix src tests`）
- [ ] 真实跑通一次（SaaS 竞品），对照设计文档第 6 节验收表逐项确认
- [ ] 更新 `PROGRESS.md` + `DECISIONS.md`，`git add` → commit → `git push origin master`
