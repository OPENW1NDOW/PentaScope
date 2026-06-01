# Competitive Analysis Agent System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a multi-agent competitive analysis system that takes competitor names + analysis intent as input, collects public data, performs structured analysis across 4 dimensions, generates a report with sourcing, and validates quality via a feedback loop.

**Architecture:** 4 hand-written agents (collector, analyzer, writer, inspector) orchestrated by LangGraph StateGraph. Collector agent internally runs 3 steps: goal parsing → competitor classification → differentiated data collection. Inspector can reject and route back to collector/analyzer. FastAPI backend exposes the graph as API endpoints. Streamlit frontend calls the API and displays results with streaming progress.

**Tech Stack:** Python 3.11+, LangGraph, Doubao-Seed-2.0-lite (OpenAI-compatible API), FastAPI, Streamlit, httpx, BeautifulSoup4, Pydantic, pytest

---

## File Structure

```
src/
├── __init__.py
├── schemas/
│   ├── __init__.py
│   ├── input.py              # CompetitorBasic, AnalysisGoal, CompetitorInput
│   ├── profile.py            # CompetitorProfile (collector output)
│   ├── analysis.py           # CompetitiveAnalysis (analyzer output)
│   ├── report.py             # FinalReport (writer output)
│   └── feedback.py           # RejectionFeedback, AgentMessage
├── tools/
│   ├── __init__.py
│   ├── llm_client.py         # Doubao API client (OpenAI-compatible)
│   ├── http_client.py        # Async HTTP with timeout/retry
│   ├── html_parser.py        # BeautifulSoup wrapper
│   └── validators.py         # Schema + URL validators
├── agents/
│   ├── __init__.py
│   ├── collector.py          # Goal parsing + classification + collection
│   ├── analyzer.py           # 4-dimension analysis + SWOT + radar
│   ├── writer.py             # Report assembly + action items
│   ├── inspector.py          # Quality check + rejection logic
│   └── prompts.py            # All prompt templates
├── graph/
│   ├── __init__.py
│   ├── state.py              # AnalysisState TypedDict
│   └── builder.py            # StateGraph construction
├── api/
│   ├── __init__.py
│   ├── main.py               # FastAPI app
│   ├── routes.py             # API endpoints
│   └── schemas.py            # Request/response models
├── frontend/
│   ├── __init__.py
│   └── app.py                # Streamlit app
└── utils/
    ├── __init__.py
    ├── config.py             # Settings from env vars
    └── logger.py             # Structured logging

tests/
├── __init__.py
├── conftest.py               # Shared fixtures
├── unit/
│   ├── test_schemas.py
│   ├── test_llm_client.py
│   ├── test_http_client.py
│   ├── test_html_parser.py
│   ├── test_validators.py
│   ├── test_collector.py
│   ├── test_analyzer.py
│   ├── test_writer.py
│   └── test_inspector.py
└── integration/
    ├── test_graph.py
    └── test_api.py
```

---

## Task 1: Project Scaffolding

**Files:**
- Create: `requirements.txt`, `.gitignore`, `.env.example`, `src/__init__.py`, `tests/__init__.py`, `tests/conftest.py`

- [ ] **Step 1: Create requirements.txt**

```
langgraph>=0.2.0
openai>=1.30.0
fastapi>=0.111.0
uvicorn>=0.30.0
streamlit>=1.35.0
httpx>=0.27.0
beautifulsoup4>=4.12.0
pydantic>=2.7.0
python-dotenv>=1.0.0
pytest>=8.2.0
pytest-asyncio>=0.23.0
pytest-httpx>=0.30.0
ruff>=0.4.0
```

- [ ] **Step 2: Create .gitignore**

```
.venv/
__pycache__/
*.pyc
.env
logs/
.pytest_cache/
.ruff_cache/
*.egg-info/
dist/
build/
```

- [ ] **Step 3: Create .env.example**

```
DOUBAO_API_KEY=your_api_key_here
DOUBAO_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
DOUBAO_MODEL_EP=ep-20260514111325-xjmj7
```

- [ ] **Step 4: Create package __init__.py files**

Create empty `__init__.py` in: `src/`, `src/schemas/`, `src/tools/`, `src/agents/`, `src/graph/`, `src/api/`, `src/frontend/`, `src/utils/`, `tests/`, `tests/unit/`, `tests/integration/`

- [ ] **Step 5: Create tests/conftest.py**

```python
import pytest
import json

@pytest.fixture
def sample_competitor_basic():
    return {"name": "支付宝", "company": "蚂蚁集团", "category": "金融科技"}

@pytest.fixture
def sample_analysis_context():
    return "分析支付宝最近的新功能，我们准备做一个类似的功能"

@pytest.fixture
def sample_competitor_profile():
    return {
        "classification": {"competitor_type": "核心竞品", "reason": "目标用户相同，核心功能高度相似"},
        "basic_info": {
            "name": "支付宝", "company": "蚂蚁集团", "version": "10.5.0",
            "release_date": "2026-05-20", "platform": ["iOS", "Android"]
        },
        "feature_tree": [
            {"module": "支付", "features": [
                {"name": "扫码支付", "description": "支持二维码和条形码支付", "is_new": False, "source_url": "https://example.com"}
            ]}
        ],
        "pricing": {"model": "免费", "tiers": [], "source_url": "https://example.com"},
        "user_reviews": {
            "rating": 4.5, "total_reviews": 100000,
            "positive_summary": "支付便捷", "negative_summary": "广告较多",
            "sample_reviews": [{"content": "很好用", "rating": 5, "source": "App Store", "source_url": "https://example.com"}]
        },
        "recent_updates": [{"date": "2026-05-20", "title": "新增功能", "summary": "更新了支付功能", "source_url": "https://example.com"}],
        "metadata": {"collected_at": "2026-05-31T10:00:00", "data_sources": ["App Store", "官网"], "completeness_score": 0.85}
    }

@pytest.fixture
def sample_competitive_analysis():
    return {
        "positioning": {
            "per_competitor": [{"name": "支付宝", "target_users": "大众消费者", "core_scenario": "移动支付", "pain_points": "现金携带不便", "value_proposition": "便捷支付"}],
            "source_urls": ["https://example.com"]
        },
        "feature_matrix": [
            {"feature": "扫码支付", "our_product": "无", "competitors": {"支付宝": "有"}, "gap_level": "落后", "evidence": "支付宝已支持", "source_urls": ["https://example.com"]}
        ],
        "business_model": {
            "per_competitor": [{"name": "支付宝", "revenue_model": "交易佣金+广告", "pricing_details": "免费使用", "free_vs_paid": "核心功能免费"}],
            "source_urls": ["https://example.com"]
        },
        "operations": {
            "per_competitor": [{"name": "支付宝", "growth_strategy": "生态绑定", "marketing_channels": "线下商户", "content_strategy": "生活服务内容"}],
            "source_urls": ["https://example.com"]
        },
        "user_sentiment": {"summary": "整体正面", "per_competitor": {"支付宝": "好评为主"}, "source_urls": ["https://example.com"]},
        "swot": {
            "strengths": [{"point": "用户基数大", "evidence": "10亿用户", "dimension": "positioning", "source_urls": ["https://example.com"]}],
            "weaknesses": [{"point": "广告多", "evidence": "用户反馈", "dimension": "operations", "source_urls": ["https://example.com"]}],
            "opportunities": [{"point": "海外市场", "evidence": "全球化趋势", "dimension": "operations", "source_urls": ["https://example.com"]}],
            "threats": [{"point": "微信支付竞争", "evidence": "市场份额", "dimension": "positioning", "source_urls": ["https://example.com"]}]
        },
        "radar_scores": [{"competitor": "支付宝", "dimensions": {"feature_breadth": 4.5, "usability": 4.0, "cost_effectiveness": 3.5, "stability": 4.5, "design_quality": 4.0}}]
    }

@pytest.fixture
def sample_final_report():
    return {
        "title": "支付宝竞品分析报告",
        "executive_summary": {
            "what_competitors_did_right": "支付宝在移动支付领域建立了完整的生态体系",
            "what_competitors_did_wrong": "广告过多影响用户体验",
            "our_opportunities": "可以聚焦无广告的纯净支付体验",
            "next_steps_summary": "优先开发扫码支付功能"
        },
        "sections": [{"title": "功能对比", "content": "## 功能对比\n支付宝功能齐全", "source_refs": ["[1]"]}],
        "action_items": {
            "immediate": [{"priority": "高", "description": "开发扫码支付", "rationale": "核心功能缺失", "source_urls": ["https://example.com"]}],
            "short_term": [{"priority": "中", "description": "接入商户体系", "rationale": "扩大使用场景", "source_urls": ["https://example.com"]}],
            "long_term": [{"priority": "低", "description": "探索海外市场", "rationale": "增长空间", "source_urls": ["https://example.com"]}]
        },
        "metadata": {
            "competitors_analyzed": ["支付宝"],
            "analysis_goal": {"goal_type": "feature_iteration", "product_stage": "growing", "focus_area": "支付功能", "output_expectation": "action"},
            "generated_at": "2026-05-31T10:30:00",
            "data_sources": ["https://example.com"],
            "quality_score": 0.85,
            "warnings": []
        }
    }
```

- [ ] **Step 6: Install dependencies and verify**

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

- [ ] **Step 7: Commit**

```bash
git add requirements.txt .gitignore .env.example src/__init__.py tests/__init__.py tests/conftest.py
git commit -m "feat: project scaffolding with dependencies and test fixtures"
```

---

## Task 2: Input Schemas

**Files:**
- Create: `src/schemas/__init__.py`, `src/schemas/input.py`
- Create: `tests/unit/test_schemas.py`

- [ ] **Step 1: Write failing tests for input schemas**

```python
# tests/unit/test_schemas.py
import pytest
from pydantic import ValidationError
from src.schemas.input import CompetitorBasic, AnalysisGoal, CompetitorInput


class TestCompetitorBasic:
    def test_valid_minimal(self):
        c = CompetitorBasic(name="支付宝")
        assert c.name == "支付宝"
        assert c.company == ""
        assert c.category == ""

    def test_valid_full(self):
        c = CompetitorBasic(name="支付宝", company="蚂蚁集团", category="金融科技")
        assert c.company == "蚂蚁集团"

    def test_name_too_short(self):
        with pytest.raises(ValidationError):
            CompetitorBasic(name="支")

    def test_name_too_long(self):
        with pytest.raises(ValidationError):
            CompetitorBasic(name="a" * 51)

    def test_name_empty(self):
        with pytest.raises(ValidationError):
            CompetitorBasic(name="")


class TestAnalysisGoal:
    def test_defaults(self):
        g = AnalysisGoal()
        assert g.goal_type == "competitive_monitoring"
        assert g.product_stage == "growing"
        assert g.output_expectation == "action"

    def test_valid_types(self):
        g = AnalysisGoal(goal_type="feature_iteration", product_stage="entering", output_expectation="info")
        assert g.goal_type == "feature_iteration"

    def test_invalid_goal_type(self):
        with pytest.raises(ValidationError):
            AnalysisGoal(goal_type="invalid_type")


class TestCompetitorInput:
    def test_valid(self):
        ci = CompetitorInput(
            competitors=[CompetitorBasic(name="支付宝"), CompetitorBasic(name="微信支付")],
            analysis_context="分析移动支付竞品"
        )
        assert len(ci.competitors) == 2

    def test_empty_competitors(self):
        with pytest.raises(ValidationError):
            CompetitorInput(competitors=[], analysis_context="test")

    def test_too_many_competitors(self):
        with pytest.raises(ValidationError):
            CompetitorInput(
                competitors=[CompetitorBasic(name=f"竞品{i}") for i in range(6)],
                analysis_context="test"
            )
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/unit/test_schemas.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'src.schemas.input'`

- [ ] **Step 3: Implement input schemas**

```python
# src/schemas/__init__.py
from src.schemas.input import CompetitorBasic, AnalysisGoal, CompetitorInput

__all__ = ["CompetitorBasic", "AnalysisGoal", "CompetitorInput"]
```

```python
# src/schemas/input.py
from pydantic import BaseModel, Field
from typing import Literal


class CompetitorBasic(BaseModel):
    """竞品基础信息（用户输入）"""
    name: str = Field(..., min_length=2, max_length=50, description="竞品名称")
    company: str = Field(default="", description="所属公司（选填，系统可推断）")
    category: str = Field(default="", description="行业分类（选填，系统可推断）")


class AnalysisGoal(BaseModel):
    """解析后的分析目标"""
    goal_type: Literal[
        "feature_iteration", "pricing_strategy",
        "market_entry", "competitive_monitoring"
    ] = "competitive_monitoring"
    product_stage: Literal["entering", "growing", "mature"] = "growing"
    focus_area: str = Field(default="", description="用户关注的具体领域")
    output_expectation: Literal["info", "knowledge", "action"] = "action"


class CompetitorInput(BaseModel):
    """完整的用户输入"""
    competitors: list[CompetitorBasic] = Field(..., min_length=1, max_length=5, description="竞品列表")
    analysis_context: str = Field(..., min_length=1, description="自然语言描述分析意图")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/unit/test_schemas.py -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/schemas/ tests/unit/test_schemas.py
git commit -m "feat: input schemas (CompetitorBasic, AnalysisGoal, CompetitorInput)"
```

---

## Task 3: Profile Schema

**Files:**
- Create: `src/schemas/profile.py`
- Modify: `src/schemas/__init__.py`
- Modify: `tests/unit/test_schemas.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/unit/test_schemas.py`:

```python
from src.schemas.profile import CompetitorProfile, Classification, BasicInfo, FeatureTree, Feature, Pricing, PricingTier, UserReviews, SampleReview, RecentUpdate, ProfileMetadata


class TestCompetitorProfile:
    def test_valid_full(self, sample_competitor_profile):
        p = CompetitorProfile(**sample_competitor_profile)
        assert p.classification.competitor_type == "核心竞品"
        assert p.basic_info.name == "支付宝"
        assert len(p.feature_tree) == 1
        assert p.metadata.completeness_score == 0.85

    def test_completeness_score_range(self, sample_competitor_profile):
        sample_competitor_profile["metadata"]["completeness_score"] = 1.5
        with pytest.raises(ValidationError):
            CompetitorProfile(**sample_competitor_profile)

    def test_empty_feature_tree(self, sample_competitor_profile):
        sample_competitor_profile["feature_tree"] = []
        p = CompetitorProfile(**sample_competitor_profile)
        assert p.feature_tree == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/unit/test_schemas.py::TestCompetitorProfile -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement profile schema**

```python
# src/schemas/profile.py
from pydantic import BaseModel, Field
from typing import Literal


class Classification(BaseModel):
    """竞品分类"""
    competitor_type: Literal["核心竞品", "标杆竞品", "间接竞品", "潜力竞品", "替代竞品", "翘楚竞品", "避坑竞品"]
    reason: str = Field(..., description="分类理由")


class BasicInfo(BaseModel):
    """竞品基本信息"""
    name: str
    company: str = ""
    version: str = "unknown"
    release_date: str = ""
    platform: list[str] = Field(default_factory=list)


class Feature(BaseModel):
    """单个功能"""
    name: str
    description: str = Field(default="", max_length=200)
    is_new: bool = False
    source_url: str = ""


class FeatureTree(BaseModel):
    """功能模块"""
    module: str
    features: list[Feature] = Field(default_factory=list)


class PricingTier(BaseModel):
    """价格档位"""
    name: str
    price: str = ""
    features: list[str] = Field(default_factory=list)


class Pricing(BaseModel):
    """定价信息"""
    model: str = "unknown"
    tiers: list[PricingTier] = Field(default_factory=list)
    source_url: str = ""


class SampleReview(BaseModel):
    """代表性评论"""
    content: str
    rating: int = Field(ge=1, le=5)
    source: str = ""
    source_url: str = ""


class UserReviews(BaseModel):
    """用户评价"""
    rating: float = Field(ge=0, le=5, default=0)
    total_reviews: int = Field(ge=0, default=0)
    positive_summary: str = ""
    negative_summary: str = ""
    sample_reviews: list[SampleReview] = Field(default_factory=list)


class RecentUpdate(BaseModel):
    """近期更新"""
    date: str
    title: str
    summary: str = ""
    source_url: str = ""


class ProfileMetadata(BaseModel):
    """采集元数据"""
    collected_at: str
    data_sources: list[str] = Field(default_factory=list)
    completeness_score: float = Field(ge=0, le=1, default=0)


class CompetitorProfile(BaseModel):
    """采集 Agent 输出：单个竞品的完整画像"""
    classification: Classification
    basic_info: BasicInfo
    feature_tree: list[FeatureTree] = Field(default_factory=list)
    pricing: Pricing = Field(default_factory=Pricing)
    user_reviews: UserReviews = Field(default_factory=UserReviews)
    recent_updates: list[RecentUpdate] = Field(default_factory=list)
    metadata: ProfileMetadata
```

- [ ] **Step 4: Update __init__.py**

```python
# src/schemas/__init__.py
from src.schemas.input import CompetitorBasic, AnalysisGoal, CompetitorInput
from src.schemas.profile import CompetitorProfile

__all__ = ["CompetitorBasic", "AnalysisGoal", "CompetitorInput", "CompetitorProfile"]
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/unit/test_schemas.py -v
```

Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add src/schemas/profile.py src/schemas/__init__.py tests/unit/test_schemas.py
git commit -m "feat: profile schema (CompetitorProfile and nested models)"
```

---

## Task 4: Analysis Schema

**Files:**
- Create: `src/schemas/analysis.py`
- Modify: `src/schemas/__init__.py`
- Modify: `tests/unit/test_schemas.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/unit/test_schemas.py`:

```python
from src.schemas.analysis import (
    CompetitiveAnalysis, PositioningEntry, Positioning,
    FeatureMatrixEntry, BusinessModelEntry, BusinessModel,
    OperationsEntry, Operations, UserSentiment, SwotEntry, Swot,
    RadarDimensions, RadarScore,
)


class TestCompetitiveAnalysis:
    def test_valid_full(self, sample_competitive_analysis):
        a = CompetitiveAnalysis(**sample_competitive_analysis)
        assert len(a.positioning.per_competitor) == 1
        assert len(a.feature_matrix) == 1
        assert a.feature_matrix[0].gap_level == "落后"
        assert len(a.radar_scores) == 1
        assert a.radar_scores[0].dimensions.feature_breadth == 4.5

    def test_swot_has_dimension(self, sample_competitive_analysis):
        a = CompetitiveAnalysis(**sample_competitive_analysis)
        assert a.swot.strengths[0].dimension == "positioning"

    def test_radar_score_range(self, sample_competitive_analysis):
        sample_competitive_analysis["radar_scores"][0]["dimensions"]["feature_breadth"] = 6.0
        with pytest.raises(ValidationError):
            CompetitiveAnalysis(**sample_competitive_analysis)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/unit/test_schemas.py::TestCompetitiveAnalysis -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement analysis schema**

```python
# src/schemas/analysis.py
from pydantic import BaseModel, Field
from typing import Literal


class PositioningEntry(BaseModel):
    """单个竞品的定位分析"""
    name: str
    target_users: str = ""
    core_scenario: str = ""
    pain_points: str = ""
    value_proposition: str = ""


class Positioning(BaseModel):
    """维度一：产品定位与目标用户"""
    per_competitor: list[PositioningEntry] = Field(default_factory=list)
    source_urls: list[str] = Field(default_factory=list)


class FeatureMatrixEntry(BaseModel):
    """功能矩阵中的单条记录"""
    feature: str
    our_product: Literal["有", "无", "计划中", "不适用"] = "无"
    competitors: dict[str, Literal["有", "无", "部分支持"]] = Field(default_factory=dict)
    gap_level: Literal["领先", "持平", "落后", "差异化"] = "持平"
    evidence: str = ""
    source_urls: list[str] = Field(default_factory=list)


class BusinessModelEntry(BaseModel):
    """单个竞品的商业模式"""
    name: str
    revenue_model: str = ""
    pricing_details: str = ""
    free_vs_paid: str = ""


class BusinessModel(BaseModel):
    """维度三：商业模式"""
    per_competitor: list[BusinessModelEntry] = Field(default_factory=list)
    source_urls: list[str] = Field(default_factory=list)


class OperationsEntry(BaseModel):
    """单个竞品的运营策略"""
    name: str
    growth_strategy: str = ""
    marketing_channels: str = ""
    content_strategy: str = ""


class Operations(BaseModel):
    """维度四：运营与增长"""
    per_competitor: list[OperationsEntry] = Field(default_factory=list)
    source_urls: list[str] = Field(default_factory=list)


class UserSentiment(BaseModel):
    """用户情感对比"""
    summary: str = ""
    per_competitor: dict[str, str] = Field(default_factory=dict)
    source_urls: list[str] = Field(default_factory=list)


class SwotEntry(BaseModel):
    """SWOT 单条"""
    point: str
    evidence: str = ""
    dimension: Literal["positioning", "feature", "business", "operations"] = "feature"
    source_urls: list[str] = Field(default_factory=list)


class Swot(BaseModel):
    """SWOT 分析"""
    strengths: list[SwotEntry] = Field(default_factory=list)
    weaknesses: list[SwotEntry] = Field(default_factory=list)
    opportunities: list[SwotEntry] = Field(default_factory=list)
    threats: list[SwotEntry] = Field(default_factory=list)


class RadarDimensions(BaseModel):
    """雷达图五维评分"""
    feature_breadth: float = Field(ge=0, le=5)
    usability: float = Field(ge=0, le=5)
    cost_effectiveness: float = Field(ge=0, le=5)
    stability: float = Field(ge=0, le=5)
    design_quality: float = Field(ge=0, le=5)


class RadarScore(BaseModel):
    """单个竞品的雷达评分"""
    competitor: str
    dimensions: RadarDimensions


class CompetitiveAnalysis(BaseModel):
    """分析 Agent 输出：四维竞品分析"""
    positioning: Positioning = Field(default_factory=Positioning)
    feature_matrix: list[FeatureMatrixEntry] = Field(default_factory=list)
    business_model: BusinessModel = Field(default_factory=BusinessModel)
    operations: Operations = Field(default_factory=Operations)
    user_sentiment: UserSentiment = Field(default_factory=UserSentiment)
    swot: Swot = Field(default_factory=Swot)
    radar_scores: list[RadarScore] = Field(default_factory=list)
```

- [ ] **Step 4: Update __init__.py and run tests**

```bash
pytest tests/unit/test_schemas.py -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/schemas/analysis.py src/schemas/__init__.py tests/unit/test_schemas.py
git commit -m "feat: analysis schema (4-dimension competitive analysis)"
```

---

## Task 5: Report + Feedback Schemas

**Files:**
- Create: `src/schemas/report.py`, `src/schemas/feedback.py`
- Modify: `src/schemas/__init__.py`
- Modify: `tests/unit/test_schemas.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/unit/test_schemas.py`:

```python
from src.schemas.report import FinalReport, ExecutiveSummary, ReportSection, ActionItem, ActionItems, ReportMetadata
from src.schemas.feedback import RejectionFeedback, FeedbackIssue, AgentMessage


class TestFinalReport:
    def test_valid_full(self, sample_final_report):
        r = FinalReport(**sample_final_report)
        assert r.title == "支付宝竞品分析报告"
        assert len(r.action_items.immediate) == 1
        assert r.metadata.quality_score == 0.85

    def test_action_items_time_layers(self, sample_final_report):
        r = FinalReport(**sample_final_report)
        assert r.action_items.immediate[0].priority == "高"
        assert r.action_items.short_term[0].priority == "中"
        assert r.action_items.long_term[0].priority == "低"


class TestRejectionFeedback:
    def test_valid(self):
        f = RejectionFeedback(
            passed=False,
            issues=[FeedbackIssue(agent="collector", field="feature_tree", severity="critical", reason="为空", suggestion="补充功能数据")],
            retry_count=0, max_retries=2
        )
        assert f.passed is False
        assert f.issues[0].agent == "collector"

    def test_passed_no_issues(self):
        f = RejectionFeedback(passed=True, issues=[], retry_count=0, max_retries=2)
        assert f.passed is True


class TestAgentMessage:
    def test_valid(self):
        m = AgentMessage(
            from_agent="collector", to_agent="analyzer",
            message_type="result", payload={"profiles": []},
            timestamp="2026-05-31T10:00:00", trace_id="abc-123"
        )
        assert m.from_agent == "collector"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/unit/test_schemas.py::TestFinalReport tests/unit/test_schemas.py::TestRejectionFeedback tests/unit/test_schemas.py::TestAgentMessage -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement report and feedback schemas**

```python
# src/schemas/report.py
from pydantic import BaseModel, Field
from typing import Literal
from src.schemas.input import AnalysisGoal


class ExecutiveSummary(BaseModel):
    """四段式执行摘要"""
    what_competitors_did_right: str = ""
    what_competitors_did_wrong: str = ""
    our_opportunities: str = ""
    next_steps_summary: str = ""


class ReportSection(BaseModel):
    """报告章节"""
    title: str
    content: str = ""
    source_refs: list[str] = Field(default_factory=list)


class ActionItem(BaseModel):
    """单条行动建议"""
    priority: Literal["高", "中", "低"]
    description: str
    rationale: str = ""
    source_urls: list[str] = Field(default_factory=list)


class ActionItems(BaseModel):
    """时间分层行动建议"""
    immediate: list[ActionItem] = Field(default_factory=list, description="1个月内")
    short_term: list[ActionItem] = Field(default_factory=list, description="3个月内")
    long_term: list[ActionItem] = Field(default_factory=list, description="6个月内")


class ReportMetadata(BaseModel):
    """报告元数据"""
    competitors_analyzed: list[str] = Field(default_factory=list)
    analysis_goal: AnalysisGoal = Field(default_factory=AnalysisGoal)
    generated_at: str = ""
    data_sources: list[str] = Field(default_factory=list)
    quality_score: float = Field(ge=0, le=1, default=0)
    warnings: list[str] = Field(default_factory=list)


class FinalReport(BaseModel):
    """撰写 Agent 输出：最终竞品分析报告"""
    title: str
    executive_summary: ExecutiveSummary = Field(default_factory=ExecutiveSummary)
    sections: list[ReportSection] = Field(default_factory=list)
    action_items: ActionItems = Field(default_factory=ActionItems)
    metadata: ReportMetadata = Field(default_factory=ReportMetadata)
```

```python
# src/schemas/feedback.py
from pydantic import BaseModel, Field
from typing import Literal, Any


class FeedbackIssue(BaseModel):
    """质检发现的单个问题"""
    agent: Literal["collector", "analyzer", "writer"]
    field: str
    severity: Literal["critical", "major", "minor"]
    reason: str
    suggestion: str = ""


class RejectionFeedback(BaseModel):
    """质检 Agent 输出：打回反馈"""
    passed: bool
    issues: list[FeedbackIssue] = Field(default_factory=list)
    retry_count: int = Field(ge=0, default=0)
    max_retries: int = Field(ge=0, default=2)


class AgentMessage(BaseModel):
    """Agent 间消息"""
    from_agent: str
    to_agent: str
    message_type: Literal["task", "result", "feedback", "retry"]
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: str
    trace_id: str
```

- [ ] **Step 4: Update __init__.py and run tests**

```bash
pytest tests/unit/test_schemas.py -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/schemas/report.py src/schemas/feedback.py src/schemas/__init__.py tests/unit/test_schemas.py
git commit -m "feat: report and feedback schemas (FinalReport, RejectionFeedback)"
```

---

## Task 6: Utils (Config + Logger)

**Files:**
- Create: `src/utils/config.py`, `src/utils/logger.py`

- [ ] **Step 1: Implement config**

```python
# src/utils/config.py
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    DOUBAO_API_KEY: str = os.getenv("DOUBAO_API_KEY", "")
    DOUBAO_BASE_URL: str = os.getenv("DOUBAO_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
    DOUBAO_MODEL_EP: str = os.getenv("DOUBAO_MODEL_EP", "ep-20260514111325-xjmj7")
    LLM_TIMEOUT: int = 30
    LLM_MAX_RETRIES: int = 2
    HTTP_TIMEOUT: int = 30
    COLLECT_INTERVAL: float = 2.0  # 同域名请求间隔（秒）
    MAX_RETRIES_INSPECTOR: int = 2


settings = Settings()
```

- [ ] **Step 2: Implement logger**

```python
# src/utils/logger.py
import logging
import sys
from pathlib import Path


def setup_logger(name: str, log_dir: str = "logs") -> logging.Logger:
    """创建结构化日志器，同时输出到控制台和文件"""
    Path(log_dir).mkdir(exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        formatter = logging.Formatter(
            "[%(asctime)s] %(levelname)s %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        file_handler = logging.FileHandler(f"{log_dir}/app.log", encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger
```

- [ ] **Step 3: Commit**

```bash
git add src/utils/
git commit -m "feat: config and logger utilities"
```

---

## Task 7: LLM Client

**Files:**
- Create: `src/tools/llm_client.py`, `src/tools/__init__.py`
- Create: `tests/unit/test_llm_client.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_llm_client.py
import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from src.tools.llm_client import LLMClient


class TestLLMClient:
    @pytest.mark.asyncio
    async def test_call_json_returns_parsed_dict(self):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({"key": "value"})

        client = LLMClient(api_key="test", base_url="https://test.com", model_ep="ep-test")
        with patch.object(client.client.chat.completions, "create", new_callable=AsyncMock, return_value=mock_response):
            result = await client.call_json("system prompt", "user prompt")
            assert result == {"key": "value"}

    @pytest.mark.asyncio
    async def test_call_json_retries_on_invalid_json(self):
        mock_bad = MagicMock()
        mock_bad.choices = [MagicMock()]
        mock_bad.choices[0].message.content = "not json"

        mock_good = MagicMock()
        mock_good.choices = [MagicMock()]
        mock_good.choices[0].message.content = json.dumps({"ok": True})

        client = LLMClient(api_key="test", base_url="https://test.com", model_ep="ep-test")
        with patch.object(client.client.chat.completions, "create", new_callable=AsyncMock, side_effect=[mock_bad, mock_good]):
            result = await client.call_json("sys", "usr")
            assert result == {"ok": True}

    @pytest.mark.asyncio
    async def test_call_json_raises_after_max_retries(self):
        mock_bad = MagicMock()
        mock_bad.choices = [MagicMock()]
        mock_bad.choices[0].message.content = "not json"

        client = LLMClient(api_key="test", base_url="https://test.com", model_ep="ep-test")
        with patch.object(client.client.chat.completions, "create", new_callable=AsyncMock, return_value=mock_bad):
            with pytest.raises(ValueError, match="Failed to parse"):
                await client.call_json("sys", "usr")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/unit/test_llm_client.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement LLM client**

```python
# src/tools/__init__.py
```

```python
# src/tools/llm_client.py
import json
import logging
from openai import AsyncOpenAI
from src.utils.config import settings

logger = logging.getLogger(__name__)


class LLMClient:
    """Doubao LLM 客户端（OpenAI 兼容格式）"""

    def __init__(self, api_key: str = "", base_url: str = "", model_ep: str = ""):
        self.api_key = api_key or settings.DOUBAO_API_KEY
        self.base_url = base_url or settings.DOUBAO_BASE_URL
        self.model_ep = model_ep or settings.DOUBAO_MODEL_EP
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=settings.LLM_TIMEOUT,
        )

    async def call_json(self, system_prompt: str, user_prompt: str) -> dict:
        """调用 LLM 并要求返回 JSON，自动重试解析失败的情况"""
        last_error = None
        for attempt in range(settings.LLM_MAX_RETRIES + 1):
            try:
                response = await self.client.chat.completions.create(
                    model=self.model_ep,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    response_format={"type": "json_object"},
                    timeout=settings.LLM_TIMEOUT,
                )
                content = response.choices[0].message.content
                return json.loads(content)
            except (json.JSONDecodeError, KeyError, IndexError) as e:
                last_error = e
                logger.warning("[llm] JSON 解析失败 (attempt %d/%d): %s", attempt + 1, settings.LLM_MAX_RETRIES + 1, e)
                continue

        raise ValueError(f"Failed to parse LLM response as JSON after {settings.LLM_MAX_RETRIES + 1} attempts: {last_error}")

    async def call_text(self, system_prompt: str, user_prompt: str) -> str:
        """调用 LLM 返回纯文本"""
        response = await self.client.chat.completions.create(
            model=self.model_ep,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            timeout=settings.LLM_TIMEOUT,
        )
        return response.choices[0].message.content
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/unit/test_llm_client.py -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/tools/llm_client.py src/tools/__init__.py tests/unit/test_llm_client.py
git commit -m "feat: LLM client with JSON mode and retry logic"
```

---

## Task 8: HTTP Client + HTML Parser

**Files:**
- Create: `src/tools/http_client.py`, `src/tools/html_parser.py`
- Create: `tests/unit/test_http_client.py`, `tests/unit/test_html_parser.py`

- [ ] **Step 1: Write failing tests for http_client**

```python
# tests/unit/test_http_client.py
import pytest
import httpx
from unittest.mock import AsyncMock, patch
from src.tools.http_client import HttpClient


class TestHttpClient:
    @pytest.mark.asyncio
    async def test_get_returns_text(self):
        mock_response = httpx.Response(200, text="<html>ok</html>")
        client = HttpClient()
        with patch.object(client.client, "get", new_callable=AsyncMock, return_value=mock_response):
            result = await client.get("https://example.com")
            assert result == "<html>ok</html>"

    @pytest.mark.asyncio
    async def test_get_returns_none_on_timeout(self):
        client = HttpClient()
        with patch.object(client.client, "get", new_callable=AsyncMock, side_effect=httpx.TimeoutException("timeout")):
            result = await client.get("https://example.com")
            assert result is None

    @pytest.mark.asyncio
    async def test_get_returns_none_on_404(self):
        mock_response = httpx.Response(404)
        client = HttpClient()
        with patch.object(client.client, "get", new_callable=AsyncMock, return_value=mock_response):
            result = await client.get("https://example.com")
            assert result is None
```

- [ ] **Step 2: Write failing tests for html_parser**

```python
# tests/unit/test_html_parser.py
import pytest
from src.tools.html_parser import HtmlParser


class TestHtmlParser:
    def test_extract_text(self):
        html = "<html><body><h1>Title</h1><p>Content</p></body></html>"
        parser = HtmlParser()
        text = parser.extract_text(html)
        assert "Title" in text
        assert "Content" in text

    def test_extract_links(self):
        html = '<html><body><a href="https://a.com">A</a><a href="https://b.com">B</a></body></html>'
        parser = HtmlParser()
        links = parser.extract_links(html, base_url="https://example.com")
        assert len(links) == 2
        assert links[0]["url"] == "https://a.com"

    def test_extract_meta(self):
        html = '<html><head><meta name="description" content="test desc"></head></html>'
        parser = HtmlParser()
        meta = parser.extract_meta(html)
        assert meta.get("description") == "test desc"

    def test_empty_html(self):
        parser = HtmlParser()
        assert parser.extract_text("") == ""
        assert parser.extract_links("") == []
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
pytest tests/unit/test_http_client.py tests/unit/test_html_parser.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: Implement http_client**

```python
# src/tools/http_client.py
import logging
import httpx
from src.utils.config import settings

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36",
]


class HttpClient:
    """异步 HTTP 客户端，带超时和 User-Agent 轮换"""

    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=settings.HTTP_TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENTS[0]},
        )
        self._ua_index = 0

    def _rotate_ua(self):
        self._ua_index = (self._ua_index + 1) % len(USER_AGENTS)
        self.client.headers["User-Agent"] = USER_AGENTS[self._ua_index]

    async def get(self, url: str) -> str | None:
        """GET 请求，失败返回 None"""
        try:
            self._rotate_ua()
            response = await self.client.get(url)
            if response.status_code == 200:
                return response.text
            logger.warning("[http] %s 返回状态码 %d", url, response.status_code)
            return None
        except httpx.TimeoutException:
            logger.warning("[http] %s 请求超时", url)
            return None
        except httpx.RequestError as e:
            logger.warning("[http] %s 请求失败: %s", url, e)
            return None

    async def close(self):
        await self.client.aclose()
```

- [ ] **Step 5: Implement html_parser**

```python
# src/tools/html_parser.py
import logging
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class HtmlParser:
    """HTML 解析器，基于 BeautifulSoup"""

    def extract_text(self, html: str) -> str:
        """提取页面纯文本"""
        if not html:
            return ""
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        return soup.get_text(separator="\n", strip=True)

    def extract_links(self, html: str, base_url: str = "") -> list[dict[str, str]]:
        """提取所有链接"""
        if not html:
            return []
        soup = BeautifulSoup(html, "html.parser")
        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith(("http://", "https://")):
                links.append({"url": href, "text": a.get_text(strip=True)})
        return links

    def extract_meta(self, html: str) -> dict[str, str]:
        """提取 meta 标签"""
        if not html:
            return {}
        soup = BeautifulSoup(html, "html.parser")
        meta = {}
        for tag in soup.find_all("meta"):
            name = tag.get("name", tag.get("property", ""))
            content = tag.get("content", "")
            if name and content:
                meta[name] = content
        return meta

    def extract_elements(self, html: str, selector: str) -> list[str]:
        """按 CSS 选择器提取元素文本"""
        if not html:
            return []
        soup = BeautifulSoup(html, "html.parser")
        return [el.get_text(strip=True) for el in soup.select(selector)]
```

- [ ] **Step 6: Run tests**

```bash
pytest tests/unit/test_http_client.py tests/unit/test_html_parser.py -v
```

Expected: all PASS

- [ ] **Step 7: Commit**

```bash
git add src/tools/http_client.py src/tools/html_parser.py tests/unit/test_http_client.py tests/unit/test_html_parser.py
git commit -m "feat: HTTP client and HTML parser tools"
```

---

## Task 9: Validators

**Files:**
- Create: `src/tools/validators.py`
- Create: `tests/unit/test_validators.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_validators.py
import pytest
from pydantic import BaseModel, Field
from src.tools.validators import SchemaValidator, UrlValidator


class DummySchema(BaseModel):
    name: str
    value: int = Field(ge=0)


class TestSchemaValidator:
    def test_validate_valid(self):
        result = SchemaValidator.validate(DummySchema, {"name": "test", "value": 1})
        assert result.name == "test"

    def test_validate_invalid(self):
        with pytest.raises(ValueError):
            SchemaValidator.validate(DummySchema, {"name": "test", "value": -1})

    def test_validate_missing_field(self):
        with pytest.raises(ValueError):
            SchemaValidator.validate(DummySchema, {"name": "test"})

    def test_validate_dict(self):
        result = SchemaValidator.validate_dict({"name": "test", "value": 1}, DummySchema)
        assert result.name == "test"


class TestUrlValidator:
    @pytest.mark.asyncio
    async def test_valid_url(self):
        import httpx
        from unittest.mock import AsyncMock, patch
        mock_response = httpx.Response(200)
        with patch("httpx.AsyncClient.head", new_callable=AsyncMock, return_value=mock_response):
            result = await UrlValidator.check_url("https://example.com")
            assert result is True

    @pytest.mark.asyncio
    async def test_invalid_url(self):
        import httpx
        from unittest.mock import AsyncMock, patch
        with patch("httpx.AsyncClient.head", new_callable=AsyncMock, side_effect=httpx.RequestError("fail")):
            result = await UrlValidator.check_url("https://invalid.example.com")
            assert result is False

    def test_is_valid_url_format(self):
        assert UrlValidator.is_valid_format("https://example.com") is True
        assert UrlValidator.is_valid_format("not a url") is False
        assert UrlValidator.is_valid_format("") is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/unit/test_validators.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement validators**

```python
# src/tools/validators.py
import logging
import httpx
from pydantic import BaseModel, ValidationError
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class SchemaValidator:
    """Pydantic Schema 校验器"""

    @staticmethod
    def validate(schema_class: type[BaseModel], data: dict) -> BaseModel:
        """校验数据是否符合 Schema，失败抛出 ValueError"""
        try:
            return schema_class(**data)
        except ValidationError as e:
            logger.error("[validator] Schema 校验失败: %s", e)
            raise ValueError(f"Schema validation failed: {e}") from e

    @staticmethod
    def validate_dict(data: dict, schema_class: type[BaseModel]) -> BaseModel:
        """同 validate，参数顺序不同"""
        return SchemaValidator.validate(schema_class, data)


class UrlValidator:
    """URL 校验器"""

    @staticmethod
    def is_valid_format(url: str) -> bool:
        """检查 URL 格式是否合法"""
        if not url:
            return False
        try:
            result = urlparse(url)
            return all([result.scheme in ("http", "https"), result.netloc])
        except Exception:
            return False

    @staticmethod
    async def check_url(url: str, timeout: int = 10) -> bool:
        """检查 URL 是否可访问"""
        if not UrlValidator.is_valid_format(url):
            return False
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                response = await client.head(url)
                return response.status_code < 400
        except (httpx.RequestError, httpx.TimeoutException):
            return False
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/unit/test_validators.py -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/tools/validators.py tests/unit/test_validators.py
git commit -m "feat: schema and URL validators"
```

---

## Task 10: Agent Prompts

**Files:**
- Create: `src/agents/prompts.py`, `src/agents/__init__.py`

- [ ] **Step 1: Implement prompts**

```python
# src/agents/__init__.py
```

```python
# src/agents/prompts.py

COLLECTOR_GOAL_SYSTEM = """你是一个竞品分析目标解析助手。根据用户的分析意图描述，解析出结构化的目标信息。

必须返回 JSON 格式：
{
  "goal_type": "feature_iteration" | "pricing_strategy" | "market_entry" | "competitive_monitoring",
  "product_stage": "entering" | "growing" | "mature",
  "focus_area": "用户关注的具体领域（可为空字符串）",
  "output_expectation": "info" | "knowledge" | "action"
}

如果用户描述中信息不足，使用默认值：goal_type=competitive_monitoring, product_stage=growing, output_expectation=action。"""

COLLECTOR_CLASSIFY_SYSTEM = """你是一个竞品分类助手。给定目标产品和竞品信息，判断竞品类型。

竞品类型定义：
- 核心竞品：目标用户相同，核心功能高度相似
- 标杆竞品：体量更大、品牌力更强，引领行业趋势
- 间接竞品：用户群体高度重合，但解决方式不同
- 潜力竞品：体量不如我们，但策略打法有亮点
- 替代竞品：不同细分行业，但解决同一层面需求
- 翘楚竞品：无直接竞争关系，但产品理念/技术前瞻
- 避坑竞品：反面教材

必须返回 JSON 格式：
{
  "competitor_type": "核心竞品" | "标杆竞品" | "间接竞品" | "潜力竞品" | "替代竞品" | "翘楚竞品" | "避坑竞品",
  "reason": "分类理由"
}"""

COLLECTOR_EXTRACT_SYSTEM = """你是一个竞品信息抽取助手。从给定的网页文本中提取结构化的竞品信息。

必须返回 JSON 格式，包含以下字段（无法提取的字段留空字符串或空列表）：
{
  "basic_info": {"name": "", "company": "", "version": "", "release_date": "", "platform": []},
  "feature_tree": [{"module": "", "features": [{"name": "", "description": "", "is_new": false}]}],
  "pricing": {"model": "", "tiers": [{"name": "", "price": "", "features": []}]},
  "user_reviews": {"rating": 0, "total_reviews": 0, "positive_summary": "", "negative_summary": "", "sample_reviews": []},
  "recent_updates": [{"date": "", "title": "", "summary": ""}]
}"""

ANALYZER_SYSTEM = """你是一个竞品分析师。基于提供的竞品画像数据，进行四维度结构化分析。

必须返回 JSON 格式：
{
  "positioning": {"per_competitor": [{"name": "", "target_users": "", "core_scenario": "", "pain_points": "", "value_proposition": ""}]},
  "feature_matrix": [{"feature": "", "our_product": "无", "competitors": {"竞品名": "有/无/部分支持"}, "gap_level": "领先/持平/落后/差异化", "evidence": ""}],
  "business_model": {"per_competitor": [{"name": "", "revenue_model": "", "pricing_details": "", "free_vs_paid": ""}]},
  "operations": {"per_competitor": [{"name": "", "growth_strategy": "", "marketing_channels": "", "content_strategy": ""}]},
  "user_sentiment": {"summary": "", "per_competitor": {"竞品名": ""}},
  "swot": {
    "strengths": [{"point": "", "evidence": "", "dimension": "positioning/feature/business/operations"}],
    "weaknesses": [...], "opportunities": [...], "threats": [...]
  },
  "radar_scores": [{"competitor": "", "dimensions": {"feature_breadth": 0, "usability": 0, "cost_effectiveness": 0, "stability": 0, "design_quality": 0}}]
}

每条结论的 evidence 字段必须引用具体数据。radar_scores 的 dimensions 每项 0-5 分。"""

WRITER_SYSTEM = """你是一个竞品报告撰写助手。基于竞品分析数据，撰写结构化的竞品分析报告。

必须返回 JSON 格式：
{
  "title": "报告标题",
  "executive_summary": {
    "what_competitors_did_right": "竞品做对了什么？哪些值得借鉴？（50-150字）",
    "what_competitors_did_wrong": "竞品的短板在哪里？（50-150字）",
    "our_opportunities": "我们的差异化机会是什么？（50-150字）",
    "next_steps_summary": "接下来优先做什么？（50-150字）"
  },
  "sections": [{"title": "", "content": "Markdown 格式内容"}],
  "action_items": {
    "immediate": [{"priority": "高/中/低", "description": "", "rationale": ""}],
    "short_term": [...],
    "long_term": [...]
  }
}

executive_summary 的四个字段必须全部填写，不可留空。action_items 每个时间层至少 1 条建议。"""

INSPECTOR_SYSTEM = """你是一个竞品报告质检助手。检查报告的完整性和数据支撑情况。

检查项：
1. Schema 完整性：必填字段是否为空
2. 数据支撑：每条结论是否有 evidence 和 source_urls
3. 执行摘要：四段是否都填写，长度是否合理（50-500字）
4. 行动建议：每个时间层是否至少 1 条
5. SWOT：每个维度是否至少 1 条

必须返回 JSON 格式：
{
  "passed": true/false,
  "issues": [
    {"agent": "collector/analyzer/writer", "field": "字段路径", "severity": "critical/major/minor", "reason": "问题描述", "suggestion": "修改建议"}
  ]
}"""
```

- [ ] **Step 2: Commit**

```bash
git add src/agents/
git commit -m "feat: agent prompt templates"
```

---

## Task 11: Collector Agent

**Files:**
- Create: `src/agents/collector.py`
- Create: `tests/unit/test_collector.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_collector.py
import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from src.schemas.input import CompetitorInput, CompetitorBasic, AnalysisGoal
from src.schemas.profile import CompetitorProfile
from src.agents.collector import CollectorAgent


class TestCollectorAgent:
    @pytest.mark.asyncio
    async def test_parse_goal_returns_analysis_goal(self):
        mock_llm = MagicMock()
        mock_llm.call_json = AsyncMock(return_value={
            "goal_type": "feature_iteration", "product_stage": "growing",
            "focus_area": "支付", "output_expectation": "action"
        })

        agent = CollectorAgent(llm=mock_llm, http=MagicMock(), parser=MagicMock())
        goal = await agent.parse_goal("分析支付宝的支付功能")
        assert goal.goal_type == "feature_iteration"
        assert goal.focus_area == "支付"

    @pytest.mark.asyncio
    async def test_classify_competitor_returns_type(self):
        mock_llm = MagicMock()
        mock_llm.call_json = AsyncMock(return_value={
            "competitor_type": "核心竞品", "reason": "目标用户相同"
        })

        agent = CollectorAgent(llm=mock_llm, http=MagicMock(), parser=MagicMock())
        result = await agent.classify_competitor("支付宝", AnalysisGoal())
        assert result["competitor_type"] == "核心竞品"

    @pytest.mark.asyncio
    async def test_collect_returns_profiles(self, sample_competitor_profile):
        mock_llm = MagicMock()
        mock_llm.call_json = AsyncMock(side_effect=[
            {"goal_type": "competitive_monitoring", "product_stage": "growing", "focus_area": "", "output_expectation": "action"},
            {"competitor_type": "核心竞品", "reason": "test"},
            {k: v for k, v in sample_competitor_profile.items() if k not in ("classification", "metadata")},
        ])

        mock_http = MagicMock()
        mock_http.get = AsyncMock(return_value="<html><body>支付宝</body></html>")

        mock_parser = MagicMock()
        mock_parser.extract_text.return_value = "支付宝 移动支付"
        mock_parser.extract_meta.return_value = {}

        agent = CollectorAgent(llm=mock_llm, http=mock_http, parser=mock_parser)
        user_input = CompetitorInput(
            competitors=[CompetitorBasic(name="支付宝")],
            analysis_context="分析支付宝"
        )
        profiles = await agent.collect(user_input)
        assert len(profiles) == 1
        assert isinstance(profiles[0], CompetitorProfile)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/unit/test_collector.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement collector agent**

```python
# src/agents/collector.py
import logging
from datetime import datetime, timezone
from src.schemas.input import CompetitorInput, CompetitorBasic, AnalysisGoal
from src.schemas.profile import CompetitorProfile
from src.agents.prompts import COLLECTOR_GOAL_SYSTEM, COLLECTOR_CLASSIFY_SYSTEM, COLLECTOR_EXTRACT_SYSTEM

logger = logging.getLogger(__name__)

APP_STORE_SEARCH_URL = "https://apps.apple.com/cn/search?term={name}"
YINGYONGBAO_SEARCH_URL = "https://sj.qq.com/search?q={name}"


class CollectorAgent:
    """采集 Agent：目标解析 → 竞品分类 → 差异化采集"""

    def __init__(self, llm, http, parser):
        self.llm = llm
        self.http = http
        self.parser = parser

    async def parse_goal(self, context: str) -> AnalysisGoal:
        """从自然语言描述中解析分析目标"""
        logger.info("[collector] 解析分析目标: %s", context[:50])
        result = await self.llm.call_json(COLLECTOR_GOAL_SYSTEM, f"用户输入：{context}")
        return AnalysisGoal(**result)

    async def classify_competitor(self, name: str, goal: AnalysisGoal) -> dict:
        """判断竞品类型"""
        prompt = f"竞品名称：{name}\n分析目标：{goal.goal_type}，关注领域：{goal.focus_area or '未指定'}"
        result = await self.llm.call_json(COLLECTOR_CLASSIFY_SYSTEM, prompt)
        return result

    async def _fetch_and_parse(self, url: str) -> str:
        """抓取网页并提取文本"""
        html = await self.http.get(url)
        if html is None:
            return ""
        return self.parser.extract_text(html)

    async def _extract_profile(self, name: str, text: str, classification: dict, sources: list[str]) -> CompetitorProfile:
        """从文本中抽取结构化竞品画像"""
        prompt = f"竞品名称：{name}\n\n网页文本内容：\n{text[:8000]}"
        raw = await self.llm.call_json(COLLECTOR_EXTRACT_SYSTEM, prompt)

        # 补充 classification 和 metadata
        raw["classification"] = classification
        raw["metadata"] = {
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "data_sources": sources,
            "completeness_score": self._calc_completeness(raw),
        }
        return CompetitorProfile(**raw)

    def _calc_completeness(self, data: dict) -> float:
        """计算数据完整度"""
        score = 1.0
        if not data.get("feature_tree"):
            score -= 0.3
        if not data.get("pricing", {}).get("model") or data.get("pricing", {}).get("model") == "unknown":
            score -= 0.15
        if not data.get("user_reviews", {}).get("rating"):
            score -= 0.15
        if not data.get("recent_updates"):
            score -= 0.1
        return max(0, round(score, 2))

    async def collect(self, user_input: CompetitorInput) -> list[CompetitorProfile]:
        """完整的采集流程：目标解析 → 分类 → 差异化采集"""
        # Step 1: 解析目标
        goal = await self.parse_goal(user_input.analysis_context)

        profiles = []
        for comp in user_input.competitors:
            # Step 2: 分类
            classification = await self.classify_competitor(comp.name, goal)

            # Step 3: 差异化采集
            sources = []
            texts = []

            # 应用商店采集
            for url_template in [APP_STORE_SEARCH_URL, YINGYONGBAO_SEARCH_URL]:
                url = url_template.format(name=comp.name)
                text = await self._fetch_and_parse(url)
                if text:
                    texts.append(text)
                    sources.append(url)

            # 合并所有采集文本
            combined_text = "\n\n".join(texts) if texts else f"竞品名称：{comp.name}，公司：{comp.company or '未知'}"

            # LLM 抽取结构化数据
            profile = await self._extract_profile(comp.name, combined_text, classification, sources)
            profiles.append(profile)

            logger.info("[collector] %s 采集完成, completeness=%.2f", comp.name, profile.metadata.completeness_score)

        return profiles
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/unit/test_collector.py -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/agents/collector.py tests/unit/test_collector.py
git commit -m "feat: collector agent (goal parsing + classification + collection)"
```

---

## Task 12: Analyzer Agent

**Files:**
- Create: `src/agents/analyzer.py`
- Create: `tests/unit/test_analyzer.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_analyzer.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from src.schemas.analysis import CompetitiveAnalysis
from src.agents.analyzer import AnalyzerAgent


class TestAnalyzerAgent:
    @pytest.mark.asyncio
    async def test_analyze_returns_competitive_analysis(self, sample_competitor_profile, sample_competitive_analysis):
        mock_llm = MagicMock()
        mock_llm.call_json = AsyncMock(return_value=sample_competitive_analysis)

        agent = AnalyzerAgent(llm=mock_llm)
        from src.schemas.profile import CompetitorProfile
        profiles = [CompetitorProfile(**sample_competitor_profile)]

        result = await agent.analyze(profiles)
        assert isinstance(result, CompetitiveAnalysis)
        assert len(result.feature_matrix) == 1
        assert len(result.radar_scores) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/unit/test_analyzer.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement analyzer agent**

```python
# src/agents/analyzer.py
import logging
from src.schemas.profile import CompetitorProfile
from src.schemas.analysis import CompetitiveAnalysis
from src.agents.prompts import ANALYZER_SYSTEM

logger = logging.getLogger(__name__)


class AnalyzerAgent:
    """分析 Agent：四维框架对比 + SWOT + 雷达评分"""

    def __init__(self, llm):
        self.llm = llm

    async def analyze(self, profiles: list[CompetitorProfile]) -> CompetitiveAnalysis:
        """对采集数据进行结构化分析"""
        logger.info("[analyzer] 开始分析 %d 个竞品", len(profiles))

        # 将 profiles 序列化为文本传给 LLM
        profiles_text = "\n\n".join([
            f"=== {p.basic_info.name} ===\n"
            f"分类: {p.classification.competitor_type}\n"
            f"基本信息: 公司={p.basic_info.company}, 版本={p.basic_info.version}, 平台={p.basic_info.platform}\n"
            f"功能模块: {[m.module for m in p.feature_tree]}\n"
            f"定价模式: {p.pricing.model}\n"
            f"用户评分: {p.user_reviews.rating} ({p.user_reviews.total_reviews}条评论)\n"
            f"好评: {p.user_reviews.positive_summary}\n"
            f"差评: {p.user_reviews.negative_summary}\n"
            f"近期更新: {[(u.title, u.summary) for u in p.recent_updates]}"
            for p in profiles
        ])

        prompt = f"请基于以下竞品数据进行四维度分析：\n\n{profiles_text}"
        result = await self.llm.call_json(ANALYZER_SYSTEM, prompt)

        analysis = CompetitiveAnalysis(**result)
        logger.info("[analyzer] 分析完成, 功能矩阵 %d 条, SWOT %d/%d/%d/%d",
                    len(analysis.feature_matrix),
                    len(analysis.swot.strengths), len(analysis.swot.weaknesses),
                    len(analysis.swot.opportunities), len(analysis.swot.threats))
        return analysis
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/unit/test_analyzer.py -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/agents/analyzer.py tests/unit/test_analyzer.py
git commit -m "feat: analyzer agent (4-dimension analysis)"
```

---

## Task 13: Writer Agent

**Files:**
- Create: `src/agents/writer.py`
- Create: `tests/unit/test_writer.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_writer.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from src.schemas.report import FinalReport
from src.agents.writer import WriterAgent


class TestWriterAgent:
    @pytest.mark.asyncio
    async def test_write_returns_final_report(self, sample_competitive_analysis, sample_final_report):
        mock_llm = MagicMock()
        mock_llm.call_json = AsyncMock(return_value=sample_final_report)

        agent = WriterAgent(llm=mock_llm)
        from src.schemas.analysis import CompetitiveAnalysis
        analysis = CompetitiveAnalysis(**sample_competitive_analysis)

        result = await agent.write(analysis, ["支付宝"])
        assert isinstance(result, FinalReport)
        assert result.executive_summary.what_competitors_did_right != ""
        assert len(result.action_items.immediate) >= 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/unit/test_writer.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement writer agent**

```python
# src/agents/writer.py
import logging
from datetime import datetime, timezone
from src.schemas.analysis import CompetitiveAnalysis
from src.schemas.report import FinalReport
from src.agents.prompts import WRITER_SYSTEM

logger = logging.getLogger(__name__)


class WriterAgent:
    """撰写 Agent：四段式执行摘要 + 时间分层行动建议"""

    def __init__(self, llm):
        self.llm = llm

    async def write(self, analysis: CompetitiveAnalysis, competitors: list[str]) -> FinalReport:
        """基于分析结果生成最终报告"""
        logger.info("[writer] 开始撰写报告, 竞品: %s", competitors)

        # 序列化分析数据
        analysis_text = (
            f"功能矩阵: {len(analysis.feature_matrix)} 条\n"
            f"定位分析: {len(analysis.positioning.per_competitor)} 个竞品\n"
            f"商业模式: {len(analysis.business_model.per_competitor)} 个竞品\n"
            f"运营策略: {len(analysis.operations.per_competitor)} 个竞品\n"
            f"用户情感: {analysis.user_sentiment.summary}\n"
            f"SWOT: 优势{len(analysis.swot.strengths)}/劣势{len(analysis.swot.weaknesses)}/机会{len(analysis.swot.opportunities)}/威胁{len(analysis.swot.threats)}\n"
        )

        prompt = f"请基于以下分析数据撰写竞品报告：\n\n竞品列表：{competitors}\n\n{analysis_text}"
        result = await self.llm.call_json(WRITER_SYSTEM, prompt)

        # 补充 metadata
        result.setdefault("metadata", {})
        result["metadata"]["competitors_analyzed"] = competitors
        result["metadata"]["generated_at"] = datetime.now(timezone.utc).isoformat()

        report = FinalReport(**result)
        logger.info("[writer] 报告撰写完成: %s", report.title)
        return report
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/unit/test_writer.py -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/agents/writer.py tests/unit/test_writer.py
git commit -m "feat: writer agent (report generation)"
```

---

## Task 14: Inspector Agent

**Files:**
- Create: `src/agents/inspector.py`
- Create: `tests/unit/test_inspector.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_inspector.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from src.schemas.report import FinalReport
from src.schemas.feedback import RejectionFeedback
from src.agents.inspector import InspectorAgent


class TestInspectorAgent:
    @pytest.mark.asyncio
    async def test_pass_good_report(self, sample_final_report):
        mock_llm = MagicMock()
        mock_llm.call_json = AsyncMock(return_value={"passed": True, "issues": []})

        agent = InspectorAgent(llm=mock_llm)
        report = FinalReport(**sample_final_report)

        result = await agent.inspect(report)
        assert result.passed is True
        assert len(result.issues) == 0

    @pytest.mark.asyncio
    async def test_reject_bad_report(self, sample_final_report):
        mock_llm = MagicMock()
        mock_llm.call_json = AsyncMock(return_value={
            "passed": False,
            "issues": [
                {"agent": "writer", "field": "executive_summary", "severity": "critical", "reason": "摘要为空", "suggestion": "补充摘要"}
            ]
        })

        agent = InspectorAgent(llm=mock_llm)
        report = FinalReport(**sample_final_report)

        result = await agent.inspect(report)
        assert result.passed is False
        assert result.issues[0].agent == "writer"

    @pytest.mark.asyncio
    async def test_programmatic_checks_catch_empty_summary(self):
        """即使 LLM 说通过，程序化检查也应捕获空摘要"""
        mock_llm = MagicMock()
        mock_llm.call_json = AsyncMock(return_value={"passed": True, "issues": []})

        agent = InspectorAgent(llm=mock_llm)
        from src.schemas.report import ExecutiveSummary, ActionItems
        report = FinalReport(
            title="测试报告",
            executive_summary=ExecutiveSummary(
                what_competitors_did_right="",  # 空！
                what_competitors_did_wrong="test",
                our_opportunities="test",
                next_steps_summary="test"
            ),
            action_items=ActionItems(immediate=[], short_term=[], long_term=[])  # 空！
        )

        result = await agent.inspect(report)
        assert result.passed is False
        severity_critical = [i for i in result.issues if i.severity == "critical"]
        assert len(severity_critical) >= 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/unit/test_inspector.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement inspector agent**

```python
# src/agents/inspector.py
import logging
from src.schemas.report import FinalReport
from src.schemas.feedback import RejectionFeedback, FeedbackIssue
from src.agents.prompts import INSPECTOR_SYSTEM

logger = logging.getLogger(__name__)


class InspectorAgent:
    """质检 Agent：Schema 校验 + 溯源检查 + LLM 质量评估"""

    def __init__(self, llm):
        self.llm = llm

    def _programmatic_checks(self, report: FinalReport) -> list[FeedbackIssue]:
        """程序化检查：不依赖 LLM 的硬性规则"""
        issues = []

        # 检查执行摘要四段是否填写
        es = report.executive_summary
        for field_name, field_value in [
            ("what_competitors_did_right", es.what_competitors_did_right),
            ("what_competitors_did_wrong", es.what_competitors_did_wrong),
            ("our_opportunities", es.our_opportunities),
            ("next_steps_summary", es.next_steps_summary),
        ]:
            if not field_value or len(field_value.strip()) < 10:
                issues.append(FeedbackIssue(
                    agent="writer", field=f"executive_summary.{field_name}",
                    severity="critical", reason="执行摘要该段为空或过短",
                    suggestion="补充 50-150 字的内容"
                ))

        # 检查行动建议每个时间层至少 1 条
        ai = report.action_items
        for layer_name, layer_items in [
            ("immediate", ai.immediate), ("short_term", ai.short_term), ("long_term", ai.long_term)
        ]:
            if len(layer_items) == 0:
                issues.append(FeedbackIssue(
                    agent="writer", field=f"action_items.{layer_name}",
                    severity="major", reason=f"行动建议 {layer_name} 层为空",
                    suggestion="至少添加 1 条行动建议"
                ))

        # 检查功能矩阵是否为空
        if not report.sections:
            issues.append(FeedbackIssue(
                agent="writer", field="sections",
                severity="major", reason="报告无章节内容",
                suggestion="至少添加 1 个章节"
            ))

        return issues

    async def inspect(self, report: FinalReport, retry_count: int = 0, max_retries: int = 2) -> RejectionFeedback:
        """执行质量检查"""
        logger.info("[inspector] 开始质检, retry_count=%d", retry_count)

        # 程序化检查
        programmatic_issues = self._programmatic_checks(report)

        # LLM 质量评估
        report_text = report.model_dump_json()
        llm_result = await self.llm.call_json(INSPECTOR_SYSTEM, f"请检查以下报告：\n\n{report_text[:6000]}")

        # 合并结果
        llm_issues = [
            FeedbackIssue(**issue) for issue in llm_result.get("issues", [])
        ]
        all_issues = programmatic_issues + llm_issues

        # 去重（同一 agent+field 的 critical 优先）
        seen = set()
        unique_issues = []
        for issue in sorted(all_issues, key=lambda i: {"critical": 0, "major": 1, "minor": 2}[i.severity]):
            key = (issue.agent, issue.field)
            if key not in seen:
                seen.add(key)
                unique_issues.append(issue)

        passed = len(unique_issues) == 0

        feedback = RejectionFeedback(
            passed=passed,
            issues=unique_issues,
            retry_count=retry_count,
            max_retries=max_retries,
        )

        logger.info("[inspector] 质检完成, passed=%s, issues=%d", passed, len(unique_issues))
        return feedback
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/unit/test_inspector.py -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/agents/inspector.py tests/unit/test_inspector.py
git commit -m "feat: inspector agent (quality check with programmatic + LLM validation)"
```

---

## Task 15: LangGraph State

**Files:**
- Create: `src/graph/state.py`, `src/graph/__init__.py`

- [ ] **Step 1: Implement state**

```python
# src/graph/__init__.py
```

```python
# src/graph/state.py
from typing import TypedDict, Annotated
from src.schemas.input import CompetitorInput
from src.schemas.profile import CompetitorProfile
from src.schemas.analysis import CompetitiveAnalysis
from src.schemas.report import FinalReport
from src.schemas.feedback import RejectionFeedback


class AnalysisState(TypedDict, total=False):
    """LangGraph 状态定义：所有 Agent 共享的数据结构"""
    # 输入
    user_input: CompetitorInput

    # 采集 Agent 输出
    profiles: list[CompetitorProfile]

    # 分析 Agent 输出
    analysis: CompetitiveAnalysis

    # 撰写 Agent 输出
    report: FinalReport

    # 质检 Agent 输出
    feedback: RejectionFeedback

    # 控制流
    retry_count: int
    max_retries: int
    trace_id: str
    current_node: str  # 当前执行到的节点名称
```

- [ ] **Step 2: Commit**

```bash
git add src/graph/
git commit -m "feat: LangGraph state definition"
```

---

## Task 16: LangGraph Builder

**Files:**
- Create: `src/graph/builder.py`
- Create: `tests/integration/test_graph.py`

- [ ] **Step 1: Write failing integration test**

```python
# tests/integration/test_graph.py
import pytest
import json
from unittest.mock import AsyncMock, MagicMock
from src.schemas.input import CompetitorInput, CompetitorBasic
from src.graph.builder import build_graph


class TestGraphIntegration:
    @pytest.mark.asyncio
    async def test_full_graph_run(self, sample_competitor_profile, sample_competitive_analysis, sample_final_report):
        """端到端测试：Mock LLM，验证完整图运行"""
        # 构造 LLM 返回序列
        llm_responses = [
            # collector: parse_goal
            {"goal_type": "competitive_monitoring", "product_stage": "growing", "focus_area": "", "output_expectation": "action"},
            # collector: classify
            {"competitor_type": "核心竞品", "reason": "test"},
            # collector: extract_profile (对每个竞品)
            {k: v for k, v in sample_competitor_profile.items() if k not in ("classification", "metadata")},
            # analyzer
            sample_competitive_analysis,
            # writer
            sample_final_report,
            # inspector
            {"passed": True, "issues": []},
        ]
        call_index = [0]

        async def mock_call_json(system_prompt, user_prompt):
            idx = call_index[0]
            call_index[0] += 1
            return llm_responses[idx]

        mock_llm = MagicMock()
        mock_llm.call_json = AsyncMock(side_effect=mock_call_json)

        mock_http = MagicMock()
        mock_http.get = AsyncMock(return_value="<html>支付宝</html>")

        mock_parser = MagicMock()
        mock_parser.extract_text.return_value = "支付宝 移动支付"
        mock_parser.extract_meta.return_value = {}

        graph = build_graph(llm=mock_llm, http=mock_http, parser=mock_parser)

        user_input = CompetitorInput(
            competitors=[CompetitorBasic(name="支付宝")],
            analysis_context="分析支付宝"
        )

        result = await graph.ainvoke({
            "user_input": user_input,
            "retry_count": 0,
            "max_retries": 2,
            "trace_id": "test-001",
        })

        assert "report" in result
        assert result["report"].title != ""
        assert result["feedback"].passed is True

    @pytest.mark.asyncio
    async def test_rejection_triggers_retry(self, sample_competitor_profile, sample_competitive_analysis, sample_final_report):
        """测试质检打回后重新执行"""
        llm_responses = [
            # collector: parse_goal
            {"goal_type": "competitive_monitoring", "product_stage": "growing", "focus_area": "", "output_expectation": "action"},
            # collector: classify
            {"competitor_type": "核心竞品", "reason": "test"},
            # collector: extract_profile
            {k: v for k, v in sample_competitor_profile.items() if k not in ("classification", "metadata")},
            # analyzer
            sample_competitive_analysis,
            # writer (第一次)
            sample_final_report,
            # inspector (第一次: 不通过)
            {"passed": False, "issues": [{"agent": "writer", "field": "executive_summary.what_competitors_did_right", "severity": "critical", "reason": "为空", "suggestion": "补充"}]},
            # writer (修正后)
            sample_final_report,
            # inspector (第二次: 通过)
            {"passed": True, "issues": []},
        ]
        call_index = [0]

        async def mock_call_json(system_prompt, user_prompt):
            idx = call_index[0]
            call_index[0] += 1
            return llm_responses[idx]

        mock_llm = MagicMock()
        mock_llm.call_json = AsyncMock(side_effect=mock_call_json)

        mock_http = MagicMock()
        mock_http.get = AsyncMock(return_value="<html>支付宝</html>")

        mock_parser = MagicMock()
        mock_parser.extract_text.return_value = "支付宝 移动支付"
        mock_parser.extract_meta.return_value = {}

        graph = build_graph(llm=mock_llm, http=mock_http, parser=mock_parser)

        user_input = CompetitorInput(
            competitors=[CompetitorBasic(name="支付宝")],
            analysis_context="分析支付宝"
        )

        result = await graph.ainvoke({
            "user_input": user_input,
            "retry_count": 0,
            "max_retries": 2,
            "trace_id": "test-002",
        })

        assert result["feedback"].passed is True
        assert result["retry_count"] >= 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/integration/test_graph.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement graph builder**

```python
# src/graph/builder.py
import logging
from langgraph.graph import StateGraph, END
from src.graph.state import AnalysisState
from src.agents.collector import CollectorAgent
from src.agents.analyzer import AnalyzerAgent
from src.agents.writer import WriterAgent
from src.agents.inspector import InspectorAgent

logger = logging.getLogger(__name__)


def build_graph(llm, http, parser) -> StateGraph:
    """构建 LangGraph 状态图"""
    collector = CollectorAgent(llm=llm, http=http, parser=parser)
    analyzer = AnalyzerAgent(llm=llm)
    writer = WriterAgent(llm=llm)
    inspector = InspectorAgent(llm=llm)

    async def collector_node(state: AnalysisState) -> dict:
        logger.info("[graph] → collector")
        profiles = await collector.collect(state["user_input"])
        return {"profiles": profiles, "current_node": "collector"}

    async def analyzer_node(state: AnalysisState) -> dict:
        logger.info("[graph] → analyzer")
        analysis = await analyzer.analyze(state["profiles"])
        return {"analysis": analysis, "current_node": "analyzer"}

    async def writer_node(state: AnalysisState) -> dict:
        logger.info("[graph] → writer")
        competitors = [c.name for c in state["user_input"].competitors]
        report = await writer.write(state["analysis"], competitors)
        return {"report": report, "current_node": "writer"}

    async def inspector_node(state: AnalysisState) -> dict:
        logger.info("[graph] → inspector")
        feedback = await inspector.inspect(
            state["report"],
            retry_count=state.get("retry_count", 0),
            max_retries=state.get("max_retries", 2),
        )
        return {
            "feedback": feedback,
            "retry_count": state.get("retry_count", 0) + (0 if feedback.passed else 1),
            "current_node": "inspector",
        }

    def should_continue(state: AnalysisState) -> str:
        """质检通过→结束，不通过且未超限→回到 writer，超限→强制结束"""
        feedback = state.get("feedback")
        if feedback is None or feedback.passed:
            return "end"

        retry_count = state.get("retry_count", 0)
        max_retries = state.get("max_retries", 2)

        if retry_count >= max_retries:
            logger.warning("[graph] 质检打回超限 (%d/%d), 强制结束", retry_count, max_retries)
            return "end"

        # 根据 issues 中的 agent 字段决定回到哪个节点
        target_agents = {issue.agent for issue in feedback.issues}
        if "collector" in target_agents:
            return "collector"
        return "writer"

    # 构建图
    graph = StateGraph(AnalysisState)

    graph.add_node("collector", collector_node)
    graph.add_node("analyzer", analyzer_node)
    graph.add_node("writer", writer_node)
    graph.add_node("inspector", inspector_node)

    graph.set_entry_point("collector")

    graph.add_edge("collector", "analyzer")
    graph.add_edge("analyzer", "writer")
    graph.add_edge("writer", "inspector")

    graph.add_conditional_edges("inspector", should_continue, {
        "end": END,
        "collector": "collector",
        "writer": "writer",
    })

    return graph.compile()
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/integration/test_graph.py -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/graph/builder.py tests/integration/test_graph.py
git commit -m "feat: LangGraph builder with feedback loop"
```

---

## Task 17: FastAPI Backend

**Files:**
- Create: `src/api/schemas.py`, `src/api/routes.py`, `src/api/main.py`
- Create: `tests/integration/test_api.py`

- [ ] **Step 1: Implement API schemas**

```python
# src/api/schemas.py
from pydantic import BaseModel, Field
from src.schemas.input import CompetitorBasic


class AnalysisRequest(BaseModel):
    """API 请求"""
    competitors: list[CompetitorBasic] = Field(..., min_length=1, max_length=5)
    analysis_context: str = Field(..., min_length=1)


class AnalysisResponse(BaseModel):
    """API 响应"""
    trace_id: str
    status: str  # "completed" | "failed"
    report: dict | None = None
    error: str | None = None
```

- [ ] **Step 2: Implement routes**

```python
# src/api/routes.py
import uuid
import logging
from fastapi import APIRouter
from src.api.schemas import AnalysisRequest, AnalysisResponse
from src.schemas.input import CompetitorInput
from src.tools.llm_client import LLMClient
from src.tools.http_client import HttpClient
from src.tools.html_parser import HtmlParser
from src.graph.builder import build_graph

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/analyze", response_model=AnalysisResponse)
async def analyze(request: AnalysisRequest):
    """执行竞品分析"""
    trace_id = str(uuid.uuid4())[:8]
    logger.info("[api] 收到分析请求, trace_id=%s, competitors=%s", trace_id, [c.name for c in request.competitors])

    try:
        user_input = CompetitorInput(
            competitors=request.competitors,
            analysis_context=request.analysis_context,
        )

        llm = LLMClient()
        http = HttpClient()
        parser = HtmlParser()

        graph = build_graph(llm=llm, http=http, parser=parser)

        result = await graph.ainvoke({
            "user_input": user_input,
            "retry_count": 0,
            "max_retries": 2,
            "trace_id": trace_id,
        })

        report = result.get("report")
        return AnalysisResponse(
            trace_id=trace_id,
            status="completed",
            report=report.model_dump() if report else None,
        )
    except Exception as e:
        logger.error("[api] 分析失败: %s", e, exc_info=True)
        return AnalysisResponse(trace_id=trace_id, status="failed", error=str(e))
    finally:
        await http.close()
```

- [ ] **Step 3: Implement main app**

```python
# src/api/main.py
from fastapi import FastAPI
from src.api.routes import router

app = FastAPI(title="竞品分析 Agent 系统", version="1.0.0")
app.include_router(router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 4: Write API test**

```python
# tests/integration/test_api.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from src.api.main import app


class TestAPI:
    @pytest.mark.asyncio
    async def test_health(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health")
            assert response.status_code == 200
            assert response.json()["status"] == "ok"

    @pytest.mark.asyncio
    async def test_analyze_returns_report(self, sample_competitor_profile, sample_competitive_analysis, sample_final_report):
        llm_responses = [
            {"goal_type": "competitive_monitoring", "product_stage": "growing", "focus_area": "", "output_expectation": "action"},
            {"competitor_type": "核心竞品", "reason": "test"},
            {k: v for k, v in sample_competitor_profile.items() if k not in ("classification", "metadata")},
            sample_competitive_analysis,
            sample_final_report,
            {"passed": True, "issues": []},
        ]
        call_index = [0]

        async def mock_call_json(system_prompt, user_prompt):
            idx = call_index[0]
            call_index[0] += 1
            return llm_responses[idx]

        mock_llm = MagicMock()
        mock_llm.call_json = AsyncMock(side_effect=mock_call_json)

        mock_http = MagicMock()
        mock_http.get = AsyncMock(return_value="<html>test</html>")
        mock_http.close = AsyncMock()

        mock_parser = MagicMock()
        mock_parser.extract_text.return_value = "test data"
        mock_parser.extract_meta.return_value = {}

        with patch("src.api.routes.LLMClient", return_value=mock_llm), \
             patch("src.api.routes.HttpClient", return_value=mock_http), \
             patch("src.api.routes.HtmlParser", return_value=mock_parser):

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post("/api/v1/analyze", json={
                    "competitors": [{"name": "支付宝"}],
                    "analysis_context": "分析支付宝"
                })

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["report"] is not None
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/integration/test_api.py -v
```

Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add src/api/ tests/integration/test_api.py
git commit -m "feat: FastAPI backend with /analyze endpoint"
```

---

## Task 18: Streamlit Frontend

**Files:**
- Create: `src/frontend/app.py`

- [ ] **Step 1: Implement Streamlit app**

```python
# src/frontend/app.py
import streamlit as st
import httpx
import json

API_BASE = "http://localhost:8000/api/v1"

st.set_page_config(page_title="竞品分析 Agent 系统", layout="wide")
st.title("竞品分析 Agent 系统")

# 输入区
st.header("输入")
col1, col2 = st.columns([1, 1])

with col1:
    competitor_names = st.text_area(
        "竞品名称（每行一个）",
        placeholder="支付宝\n微信支付",
        height=100,
    )

with col2:
    analysis_context = st.text_area(
        "分析意图描述",
        placeholder="分析支付宝最近的新功能，我们准备做一个类似的功能",
        height=100,
    )

if st.button("开始分析", type="primary"):
    if not competitor_names.strip():
        st.error("请输入至少一个竞品名称")
    elif not analysis_context.strip():
        st.error("请输入分析意图描述")
    else:
        competitors = [{"name": name.strip()} for name in competitor_names.strip().split("\n") if name.strip()]

        with st.spinner("正在分析中，请稍候..."):
            try:
                response = httpx.post(
                    f"{API_BASE}/analyze",
                    json={"competitors": competitors, "analysis_context": analysis_context},
                    timeout=600,
                )
                data = response.json()

                if data["status"] == "completed":
                    report = data["report"]
                    st.success(f"分析完成！Trace ID: {data['trace_id']}")

                    # 执行摘要
                    st.header("执行摘要")
                    es = report.get("executive_summary", {})
                    for label, key in [
                        ("竞品做对了什么", "what_competitors_did_right"),
                        ("竞品的短板", "what_competitors_did_wrong"),
                        ("我们的机会", "our_opportunities"),
                        ("下一步行动", "next_steps_summary"),
                    ]:
                        st.subheader(label)
                        st.write(es.get(key, ""))

                    # 行动建议
                    st.header("行动建议")
                    ai = report.get("action_items", {})
                    for layer_name, layer_label in [
                        ("immediate", "短期（1个月内）"),
                        ("short_term", "中期（3个月内）"),
                        ("long_term", "长期（6个月内）"),
                    ]:
                        items = ai.get(layer_name, [])
                        if items:
                            st.subheader(layer_label)
                            for item in items:
                                priority = item.get("priority", "")
                                desc = item.get("description", "")
                                rationale = item.get("rationale", "")
                                st.markdown(f"**[{priority}]** {desc}")
                                if rationale:
                                    st.caption(f"依据：{rationale}")

                    # 报告章节
                    st.header("详细报告")
                    for section in report.get("sections", []):
                        st.subheader(section.get("title", ""))
                        st.markdown(section.get("content", ""))

                    # 元数据
                    with st.expander("元数据"):
                        st.json(report.get("metadata", {}))

                else:
                    st.error(f"分析失败: {data.get('error', '未知错误')}")

            except httpx.ConnectError:
                st.error("无法连接后端服务，请确认 FastAPI 已启动 (uvicorn src.api.main:app --port 8000)")
            except Exception as e:
                st.error(f"发生错误: {e}")
```

- [ ] **Step 2: Commit**

```bash
git add src/frontend/app.py
git commit -m "feat: Streamlit frontend"
```

---

## Self-Review Checklist

**1. Spec coverage:**
- [x] Objective / Success Criteria → Task 1 (test fixtures define success), Task 17 (API endpoint)
- [x] Tech Stack → Task 1 (requirements.txt)
- [x] Commands → Task 1 (.gitignore, conftest)
- [x] Project Structure → File Structure section, all tasks follow it
- [x] Code Style → Pydantic models in Tasks 2-5, naming conventions in all code
- [x] Testing Strategy → Each task has TDD steps, conftest has fixtures, integration tests in Task 16-17
- [x] Boundaries → All schemas use Pydantic, LLM calls have timeout/retry (Task 7), logging throughout
- [x] JSON mode → LLMClient.call_json uses `response_format={"type": "json_object"}`
- [x] Streaming → Not implemented in this plan (frontend uses synchronous call; streaming is P1)
- [x] Data source strategy → App store URL templates in collector, search-based for media (P1)

**2. Placeholder scan:** No TBD/TODO/fill-in-later found.

**3. Type consistency:**
- `CompetitorProfile` used consistently in collector output and analyzer input
- `CompetitiveAnalysis` used consistently in analyzer output and writer input
- `FinalReport` used consistently in writer output and inspector input
- `RejectionFeedback` used consistently in inspector output and graph control flow
- `AnalysisState` field names match all node return dicts

**Note:** Streaming progress (LangGraph streaming → Streamlit) is not covered in this plan. It's a P1 feature and should be a separate plan after the core system works.
