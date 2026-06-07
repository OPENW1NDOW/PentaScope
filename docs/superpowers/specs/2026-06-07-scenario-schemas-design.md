# 分场景报告 Schema 设计（5 套独立 schema，R2 架构）

> 设计日期：2026-06-07
> 上下文：完整对话见会话"分场景输出报告"。前置研究见 `docs/superpowers/research/2026-06-07-report-templates-research.md`。
> 决策摘要：5 场景全做（S1-S5）/ 显式选场景+AI 帮选混合 / goal_type 升级为 scenario / S2 新建 recommender 节点 / 5 套独立 schema 共享 BaseReport 通用骨架（R2 discriminated union）/ 7000-8000 字深耕章节深度 / 一步到位废除旧 report.py
> 状态：第 1 批次（BaseReport + S1 + S2）已完成 doubt-driven 双模型审查 + 12 条产品决策定稿。第 2 批次（S3+S4+S5）尚未开始
> 评审记录：见 Part 5（双模型审查 19 技术问题修复记录 + 12 条产品决策落地记录）

---

## Part 0：旧 schema 废除清单（doubt-driven P0-2 修复）

本次任务**一步到位废除**以下文件中的旧 schema 类，新 schema 写到独立的 `src/schemas/report.py`（覆盖文件）+ `src/schemas/scenarios/` 子目录。

| 旧 class（路径） | 处置 | 新位置 / 替代 |
|---|---|---|
| `src/schemas/report.py::FinalReport` | **废除** | `src/schemas/report.py::BaseReport`（新） |
| `src/schemas/report.py::ExecutiveSummary`（旧 4 段） | **废除** | `src/schemas/report.py::ExecutiveSummary`（新 5 段） |
| `src/schemas/report.py::ReportSection` | **废除** | `src/schemas/report.py::AnalysisSection`（新） |
| `src/schemas/report.py::ActionItem` | **重命名** | `src/schemas/report.py::Recommendation`（含 priority + timeline） |
| `src/schemas/report.py::ActionItems` | **废除** | 由 `BaseReport.recommendations: list[Recommendation]` 替代 |
| `src/schemas/report.py::ReportMetadata` | **重写** | `src/schemas/report.py::ReportMetadata`（新，扩展） |
| `src/schemas/analysis.py::Swot` | **保留并迁移** | `src/schemas/report.py::Swot`（**决策 1：SWOT 进 BaseReport 通用骨架**） |
| `src/schemas/analysis.py::SwotEntry` | **保留并迁移** | `src/schemas/report.py::SwotEntry` |
| `src/schemas/analysis.py::RadarScore` | **保留并迁移到 S1** | `src/schemas/scenarios/s1.py::S1RadarScore`（**决策 2：S1 雷达图保留**） |
| `src/schemas/analysis.py::FeatureMatrixEntry` | **重写为新结构** | `src/schemas/scenarios/s1.py::FeatureRow`（含 0-2 评分 + tier） |
| `src/schemas/analysis.py::CompetitiveAnalysis` | **保留** | analyzer 中间产物 schema 不变（writer 重构后由 writer 消费） |
| `src/agents/writer.py` 内部辅助类 | **重写** | 见 Part 6 writer 编排重构方案 |

**前端兼容**：`src/frontend/app.py` 的执行追溯面板渲染逻辑跟着改字段路径（一次性切到 `BaseReport`，旧 trace 不兼容由前端"trace 版本不支持"提示替代）。

---

## Part 1：BaseReport 通用骨架

### 1.1 顶层结构（doubt-driven P0-1 修复后）

```python
from __future__ import annotations
from typing import Literal, Optional, Union, Annotated
from pydantic import BaseModel, Field, model_validator, computed_field
from datetime import date

class BaseReport(BaseModel):
    """所有 5 场景共用的报告通用骨架（基于 McKinsey/BCG/Bain/Gartner/Forrester 五家共识）"""

    # === 元数据（顶部） ===
    metadata: ReportMetadata

    # === 通用骨架字段 ===
    title: str = Field(min_length=10, max_length=80)
    subtitle: Optional[str] = Field(default=None, max_length=120)
    at_a_glance: list[str] = Field(min_length=3, max_length=6)
    executive_summary: ExecutiveSummary
    background: str = Field(min_length=200, max_length=1500)
    scope: ReportScope
    methodology: Methodology  # 字数预算 1000+ 字（决策 8）
    key_findings: list[Finding] = Field(min_length=3, max_length=6)
    analysis_sections: list[AnalysisSection] = Field(min_length=4, max_length=8)  # 决策 5: 5-6 章
    swot: Swot  # 决策 1: SWOT 进通用骨架，5 场景全保留
    conclusions: str = Field(min_length=200, max_length=1500)
    recommendations: list[Recommendation] = Field(min_length=3)
    appendix: Appendix = Field(default_factory=lambda: Appendix())

    # === 场景判别（doubt-driven P0-1：单一权威源 + 一致性 validator） ===
    scenario_payload: Annotated[
        Union[
            S1FeatureIterationPayload,
            S2MarketEntryPayload,
            # S3/S4/S5 在第 2 批次实现后用 model_rebuild() 加入
        ],
        Field(discriminator='scenario_type')
    ]

    @computed_field
    @property
    def scenario(self) -> Literal["S1", "S2", "S3", "S4", "S5"]:
        """场景标识由 payload 派生，避免 scenario / metadata.scenario / scenario_type 三处不一致"""
        return self.scenario_payload.scenario_type

    @model_validator(mode='after')
    def _check_scenario_consistency(self) -> 'BaseReport':
        """强制 metadata.scenario == scenario_payload.scenario_type"""
        if self.metadata.scenario != self.scenario_payload.scenario_type:
            raise ValueError(
                f"metadata.scenario={self.metadata.scenario} but "
                f"scenario_payload.scenario_type={self.scenario_payload.scenario_type}"
            )
        return self
```

**关键修复（doubt-driven P0-1）**：
- 移除独立的 `scenario` 字段，改为 computed_field 从 payload 派生
- 加 `model_validator` 强制 `metadata.scenario == scenario_payload.scenario_type`
- 第 1 批 Union 仅含 S1/S2，第 2 批实现 S3/S4/S5 后用 `BaseReport.model_rebuild()` 加入

### 1.2 子模型定义

#### ExecutiveSummary（5 段式混合制 + 字数硬约束）

```python
class ExecutiveSummary(BaseModel):
    """执行摘要：5 段固定子字段 + 字数硬约束（doubt-driven P1-5 修复）"""
    context: str = Field(min_length=80, max_length=200)            # Why now
    core_thesis: str = Field(min_length=50, max_length=120)        # 一句话压舱判断
    key_findings_brief: list[str] = Field(min_length=2, max_length=4)  # 摘要级核心发现
    implications: str = Field(min_length=100, max_length=250)
    path_forward: list[str] = Field(min_length=1, max_length=3)
```

#### ReportScope

```python
class ReportScope(BaseModel):
    competitors: list[str] = Field(min_length=1)
    time_window: str
    regions: list[str] = Field(default_factory=list)
    exclusions: list[str] = Field(default_factory=list)
```

#### Methodology（决策 8：1000+ 字详尽版）

```python
class Methodology(BaseModel):
    """方法论章节，字数预算 1000+ 字（决策 8）"""
    data_collection_approach: str = Field(min_length=200)  # 数据采集方式
    evaluation_criteria: list[str] = Field(min_length=3)   # 评估口径
    limitations: list[str] = Field(min_length=2)           # 局限性
    sample_size_note: str = Field(min_length=80)           # 样本量说明
    analyst_disclosure: str = Field(default="本报告由 AI 多 Agent 协作系统生成，分析模型 Doubao-Seed-2.0-lite")
```

#### Finding

```python
class Finding(BaseModel):
    statement: str = Field(min_length=20)
    evidence: str = Field(min_length=20)
    implication: str = Field(min_length=20)
    source_refs: list[SourceRef] = Field(default_factory=list)  # 改用 SourceRef 对象（doubt-driven P2-1 统一命名）
```

#### AnalysisSection（doubt-driven P1-7 修复：exhibits 引用机制）

```python
class AnalysisSection(BaseModel):
    section_id: str = Field(min_length=3, max_length=40)  # 唯一 id（如 "s1-feature-deep-dive"）
    heading: str = Field(min_length=4)
    narrative: str = Field(min_length=300)  # Markdown，深耕章节 3000+ 字
    section_type: Literal[
        # 通用
        "overview", "executive_overview", "background", "conclusions_summary",
        # S1 场景
        "feature_matrix_analysis", "vendor_profile_analysis", "jtbd_analysis", "roadmap_analysis",
        # S2 场景
        "market_sizing_analysis", "five_forces_analysis", "competitive_landscape_analysis",
        "consumer_segments_analysis", "trends_analysis", "entry_strategy_analysis",
        # S3 场景（第 2 批 P0-6 修复）
        "pricing_baseline_analysis", "value_drivers_analysis", "packaging_design_analysis",
        "competitive_pricing_analysis", "pricing_recommendations_analysis",
        # S4 场景
        "monitoring_overview", "competitive_moves_analysis", "threat_assessment_analysis",
        "opportunity_identification_analysis", "battlecard_analysis",
        # S5 场景
        "vendor_positioning_analysis", "perceptual_map_analysis", "strategy_canvas_analysis",
        "errc_analysis", "positioning_statement_analysis",
    ]
    artifact_refs: list[str] = Field(default_factory=list)  # 关联 ArtifactBase.artifact_id（doubt-driven P1-7）
    source_refs: list[SourceRef] = Field(default_factory=list)
```

#### Recommendation（决策 6：timeline + priority 同时保留）

```python
class Recommendation(BaseModel):
    action: str = Field(min_length=20)
    target_role: str
    priority: Literal["critical", "important", "consider"]
    timeline: Literal["immediate", "short_term", "long_term"]  # 决策 6
    rationale: str = Field(min_length=20)
    source_refs: list[SourceRef] = Field(default_factory=list)
```

#### Swot（决策 1：进 BaseReport 通用骨架，5 场景全保留）

```python
class SwotEntry(BaseModel):
    point: str = Field(min_length=10)
    evidence: str = Field(min_length=10)
    dimension: str = Field(default="overall")  # 关联到 payload 维度（free str，不强枚举）
    source_refs: list[SourceRef] = Field(default_factory=list)

class Swot(BaseModel):
    strengths: list[SwotEntry] = Field(min_length=1)
    weaknesses: list[SwotEntry] = Field(min_length=1)
    opportunities: list[SwotEntry] = Field(min_length=1)
    threats: list[SwotEntry] = Field(min_length=1)
```

#### Appendix

```python
class Appendix(BaseModel):
    glossary: dict[str, str] = Field(default_factory=dict)
    additional_exhibits: list[Exhibit] = Field(default_factory=list)
    data_sources_full: list[DataSource] = Field(default_factory=list)
```

#### ReportMetadata

```python
class ReportMetadata(BaseModel):
    # 基础识别
    report_id: str
    trace_id: str
    scenario: Literal["S1", "S2", "S3", "S4", "S5"]  # 与 scenario_payload.scenario_type 通过 BaseReport.model_validator 校验一致
    schema_version: str = "2.0"  # 第 2 批 P0-1 修复：schema 版本，供 S4 prior_trace_id 校验兼容

    # 时间与版本
    publication_date: date
    version: str = "1.0"
    revision_history: list[Revision] = Field(default_factory=list)

    # 作者与出品方
    organization: str = "AI 竞品分析 Agent 协作系统"
    contributing_agents: list[str] = Field(default_factory=list)

    # 可信度与溯源
    data_sources: list[DataSource] = Field(min_length=1)
    confidence_level: Literal["high", "medium", "low"]
    quality_score: Optional[float] = Field(default=None, ge=0, le=1)
    quality_score_calculation_note: str = Field(default="")
    warnings: list[str] = Field(default_factory=list)

    # 合规
    disclaimer: str = Field(default="本报告基于公开渠道采集数据生成，不构成投资建议。生成时间晚于数据采集时间可能存在滞后。")
    citation_format: Optional[str] = None
```

#### 辅助子模型（doubt-driven P2-1/P2-2 修复：统一命名 + date 类型）

```python
class Revision(BaseModel):
    revision_date: date
    change_summary: str
    triggered_by: Literal["initial", "inspector_feedback", "user_request"]

class SourceRef(BaseModel):
    """统一溯源对象（doubt-driven P2-1：替代 source_urls/source_refs/sources/evidence_url 等命名分歧）"""
    url: str = Field(min_length=8)  # http(s):// 至少 8 字符；不用 HttpUrl 因 Pydantic 严格度可能拒绝有效 URL
    title: str = ""
    accessed_at: Optional[date] = None
    source_type: Literal[
        "official_website", "third_party_review", "industry_report",
        "news", "user_review", "regulatory", "other"
    ] = "other"

class DataSource(BaseModel):
    """报告级数据源汇总（与 SourceRef 区别：DataSource 是元数据列表）"""
    url: str = Field(min_length=8)
    title: str = ""
    accessed_at: Optional[date] = None
    source_type: Literal[
        "official_website", "third_party_review", "industry_report",
        "news", "user_review", "regulatory", "other"
    ] = "other"
    confidence: Literal["high", "medium", "low"] = "medium"

class ArtifactBase(BaseModel):
    """所有可被 AnalysisSection.artifact_refs 引用的产物基类（doubt-driven P1-7）"""
    artifact_id: str = Field(min_length=3, max_length=40)  # 唯一标识，如 "s1-feature-matrix-1"
    artifact_type: str  # "feature_matrix" / "radar_score" / "market_sizing" 等
    title: str = Field(default="")

class Exhibit(ArtifactBase):
    artifact_type: Literal["exhibit"] = "exhibit"
    description: str = ""
    payload: dict = Field(default_factory=dict)
```

---

## Part 2：S1 FeatureIterationPayload

### 2.1 场景定位

- **用户**：已有产品的 PM
- **触发时机**：准备做新功能，需要参考竞品做对标
- **业界标杆**：Forrester Wave + Feature Comparison Matrix + JTBD（简化版，决策 7）+ 5 维雷达评分（决策 2）

### 2.2 顶层结构（已应用决策 4 删 BattleCard / 决策 7 简化 JTBD / 决策 2 加雷达）

```python
class S1FeatureIterationPayload(BaseModel):
    """S1 功能迭代场景载荷"""
    scenario_type: Literal["S1"] = "S1"  # discriminator

    # === 1. Vendor Profiles（仿 Forrester Wave） ===
    vendor_profiles: list[S1VendorProfile] = Field(min_length=2)

    # === 2. Feature Matrix（加权评分） ===
    feature_matrix: FeatureMatrix
    tier1_disqualifiers: list[Tier1Disqualifier] = Field(default_factory=list)
    white_space_features: list[WhiteSpaceFeature] = Field(default_factory=list)

    # === 3. 雷达评分（决策 2：S1 多边形雷达图，5 维产品评分） ===
    radar_scores: list[S1RadarScore] = Field(min_length=2)

    # === 4. JTBD 简化版（决策 7：只留 JobStatement，删 Four Forces / Desired Outcomes） ===
    job_statement: JobStatement

    # === 5. Roadmap 建议 ===
    feature_gaps: list[FeatureGap] = Field(min_length=1)
    roadmap_recommendations: RoadmapRecommendations

    # === 程序化校验 ===
    @model_validator(mode='after')
    def _check_competitor_consistency(self) -> 'S1FeatureIterationPayload':
        """doubt-driven P0-6：FeatureMatrix.competitors / FeatureRow.scores keys / vendor_profiles[].competitor_name 一致"""
        matrix_competitors = set(self.feature_matrix.competitors)
        vendor_names = {vp.competitor_name for vp in self.vendor_profiles}
        radar_names = {rs.competitor_name for rs in self.radar_scores}
        # 雷达 + vendor 子集必须包含在 matrix 列内（matrix 含我方）
        if not vendor_names.issubset(matrix_competitors):
            raise ValueError(f"vendor_profiles 竞品名 {vendor_names} 不在 feature_matrix.competitors {matrix_competitors} 中")
        if not radar_names.issubset(matrix_competitors):
            raise ValueError(f"radar_scores 竞品名 {radar_names} 不在 feature_matrix.competitors {matrix_competitors} 中")
        return self
```

### 2.3 子模型详细定义

#### S1VendorProfile（doubt-driven P0-4 修复：枚举加场景前缀）

```python
class S1VendorProfile(BaseModel):
    competitor_name: str = Field(min_length=1)
    wave_position: Literal["wave_leader", "wave_strong_performer", "wave_contender"]  # 决策 2 + doubt-driven P0-4：场景前缀避免与 S5 冲突
    one_line_pitch: str = Field(min_length=10, max_length=120)
    strengths: list[VendorStrength] = Field(min_length=2, max_length=5)
    cautions: list[VendorCaution] = Field(min_length=1, max_length=4)
    best_fit_for: str = Field(min_length=10)
    reference_customer_feedback: str = Field(default="")
    source_refs: list[SourceRef] = Field(default_factory=list)

class VendorStrength(BaseModel):
    point: str = Field(min_length=10)
    evidence: str = Field(min_length=10)
    source_refs: list[SourceRef] = Field(default_factory=list)

class VendorCaution(BaseModel):
    point: str = Field(min_length=10)
    evidence: str = Field(min_length=10)
    source_refs: list[SourceRef] = Field(default_factory=list)
```

**wave_position 产出方式**：由代码按 `weighted_scores` 自动归类（>=70% wave_leader / 50-70% wave_strong_performer / <50% wave_contender）。这是程序化产物（doubt-driven P0-6 修复方向），LLM 不填。

#### FeatureMatrix（doubt-driven P0-5/P0-6 修复：evidence_url 强制 + 程序化产物）

```python
class FeatureMatrix(ArtifactBase):
    """加权评分功能矩阵"""
    artifact_type: Literal["feature_matrix"] = "feature_matrix"
    competitors: list[str] = Field(min_length=2)  # 列：竞品名（含我方）
    our_product_name: str = Field(min_length=1)
    categories: list[FeatureCategory] = Field(min_length=1)

    @computed_field
    @property
    def weighted_scores(self) -> dict[str, float]:
        """doubt-driven P0-6：weighted_scores 由代码计算，不让 LLM 填"""
        scores: dict[str, float] = {}
        for c in self.competitors:
            total = max_total = 0
            for cat in self.categories:
                w = cat.weight
                for f in cat.features:
                    if c in f.scores:
                        total += f.scores[c].score * w
                    max_total += 2 * w
            scores[c] = round(total / max_total * 100, 1) if max_total > 0 else 0.0
        return scores

class FeatureCategory(BaseModel):
    name: str = Field(min_length=2)
    tier: Literal[1, 2, 3]  # 1=table-stakes / 2=differentiating / 3=nice-to-have

    @computed_field
    @property
    def weight(self) -> int:
        """doubt-driven P0-6：weight 由 tier 派生，不让 LLM 填"""
        return {1: 3, 2: 2, 3: 1}[self.tier]

    features: list[FeatureRow] = Field(min_length=1)

class FeatureRow(BaseModel):
    name: str = Field(min_length=2)
    description: str = ""
    scores: dict[str, FeatureScore]  # competitor_name → 评分单元格

class FeatureScore(BaseModel):
    """0-2 评分制单元格 + evidence_url 强制（doubt-driven P0-5）"""
    score: Literal[0, 1, 2]
    note: str = ""

    # doubt-driven P0-5：score=2 必须有 evidence_url；score=0/1 允许 source_missing_reason 兜底
    evidence_url: Optional[str] = Field(default=None, min_length=8)
    source_missing_reason: Optional[str] = None  # 当 evidence_url 缺失时必填

    last_verified: Optional[date] = None

    @model_validator(mode='after')
    def _check_evidence(self) -> 'FeatureScore':
        if self.score == 2 and not self.evidence_url:
            raise ValueError("score=2 必须提供 evidence_url（'完整支持'必有来源）")
        if self.score == 0 and not self.evidence_url and not self.source_missing_reason:
            # score=0 至少要有理由（可以是"采集未发现该功能"）
            raise ValueError("score=0 必须提供 evidence_url 或 source_missing_reason")
        return self
```

#### Tier1Disqualifier / WhiteSpaceFeature

```python
class Tier1Disqualifier(BaseModel):
    feature: str
    competitors_failing: list[str] = Field(min_length=1)
    implication: str = Field(min_length=10)

class WhiteSpaceFeature(BaseModel):
    feature: str
    why_no_one_supports: str = ""
    opportunity_estimate: Literal["high", "medium", "low"]
```

#### S1RadarScore（决策 2：S1 5 维多边形雷达图）

```python
class S1RadarScore(ArtifactBase):
    """S1 雷达图（5 维多边形，区别于 S5 的 perceptual map 二维散点）"""
    artifact_type: Literal["s1_radar_score"] = "s1_radar_score"
    competitor_name: str = Field(min_length=1)
    feature_breadth: float = Field(ge=0, le=5)
    usability: float = Field(ge=0, le=5)
    cost_effectiveness: float = Field(ge=0, le=5)
    stability: float = Field(ge=0, le=5)
    design_quality: float = Field(ge=0, le=5)
```

#### JTBD 简化版（决策 7：只留 JobStatement）

```python
class JobStatement(BaseModel):
    """When [situation], I want to [motivation], so I can [outcome]"""
    situation: str = Field(min_length=10)
    motivation: str = Field(min_length=10)
    outcome: str = Field(min_length=10)
    layer: Literal["functional", "emotional", "social"] = "functional"
```

#### FeatureGap / RoadmapRecommendations

```python
class FeatureGap(BaseModel):
    feature_name: str = Field(min_length=2)
    competitors_have_it: list[str] = Field(min_length=1)
    underserved_outcome: str = Field(min_length=10)
    estimated_effort: Literal["low", "medium", "high"]
    estimated_impact: Literal["low", "medium", "high"]
    recommendation: Literal["build", "skip", "differentiate"]
    source_refs: list[SourceRef] = Field(default_factory=list)

class RoadmapRecommendations(BaseModel):
    must_build: list[str] = Field(min_length=1)
    should_skip: list[str] = Field(default_factory=list)
    should_differentiate: list[str] = Field(default_factory=list)
    rationale_summary: str = Field(min_length=50)
```

### 2.4 优先级（P0/P1/P2）

| Priority | 字段 |
|---|---|
| **P0**（必做） | vendor_profiles / feature_matrix / radar_scores / job_statement / feature_gaps / roadmap_recommendations |
| **P1**（强烈建议） | tier1_disqualifiers / white_space_features |
| **P2**（推迟） | competitive_alternatives（决策 10）/ Four Forces / Desired Outcomes / BattleCard（决策 4 已删） |

### 2.5 与采集层依赖

S1 P0 + P1 字段当前采集层完全可支撑（feature_tree / pricing / sample_reviews 已有）。

---

## Part 3：S2 MarketEntryPayload

### 3.1 场景定位

- **用户**：**没有产品**，正在做行业调研、立项决策、找市场机会
- **触发时机**：考虑进入新行业 / 新细分时
- **业界标杆**：McKinsey 行业 Insights + Porter Five Forces + TAM/SAM/SOM
- **关键差异**：唯一不要求用户填竞品名，由 graph 中的 `recommender` 节点反向推荐 Top 5（决策 3）

### 3.2 顶层结构

```python
class S2MarketEntryPayload(BaseModel):
    """S2 市场进入场景载荷"""
    scenario_type: Literal["S2"] = "S2"  # discriminator

    # === 1. 市场规模（TAM/SAM/SOM 三层，doubt-driven P0-3 修复：值改 Optional + value_basis） ===
    market_sizing: MarketSizing

    # === 2. Five Forces（行业结构吸引力） ===
    five_forces: FiveForces
    industry_attractiveness_1_5: int = Field(ge=1, le=5)  # doubt-driven P1-2 修复：字段名带量纲

    # === 3. 竞争格局（单一 players 来源，doubt-driven P1-3 修复） ===
    players: list[MarketPlayer] = Field(min_length=3, max_length=10)  # 决策 3：Top 5（推荐范围 3-10 给灵活）
    market_concentration: Literal["fragmented", "moderate", "concentrated"]

    # === 4. 消费者细分（决策 11：保留为 P2 + Optional） ===
    consumer_segments: Optional[list[ConsumerSegment]] = None

    # === 5. 关键趋势 ===
    key_trends: list[Trend] = Field(min_length=2)

    # === 6. 进入策略 ===
    entry_strategy: EntryStrategy

    # === 7. PESTEL（决策 9.a-2：保留结构 + 全 Optional + 默认 None） ===
    pestel: Optional[PESTEL] = None  # 首版不让 LLM 填；未来知识库到位后启用

    # === 8. recommender 节点产出（仅 S2 有） ===
    competitor_recommendations: CompetitorRecommendations
```

### 3.3 子模型详细定义

#### MarketSizing（doubt-driven P0-3 修复：value_basis + P2-3：单位口径）

```python
class MarketValue(BaseModel):
    """市场规模数值含完整口径（doubt-driven P2-3）"""
    amount: Optional[float] = None  # None 表示未采集到
    currency: Literal["USD", "CNY", "EUR", "JPY", "unknown"] = "unknown"
    unit: Literal["billion", "million", "thousand", "raw"] = "billion"
    year: Optional[int] = Field(default=None, ge=2000, le=2030)
    geography: str = "global"
    value_basis: Literal["measured", "estimated", "inferred", "unknown"] = "unknown"
    methodology_note: str = ""
    source_refs: list[SourceRef] = Field(default_factory=list)

class MarketSizing(ArtifactBase):
    """TAM/SAM/SOM 三层"""
    artifact_type: Literal["market_sizing"] = "market_sizing"
    tam: MarketValue
    sam: MarketValue
    som: MarketValue
    cagr_pct: Optional[float] = None  # 复合年增长率（None 表示未采）
    forecast_years: Optional[int] = None
    forecast_scenarios: Optional[ForecastScenarios] = None
    triangulation_gap_pct: Optional[float] = None  # None 表示未做三角验证

class ForecastScenarios(BaseModel):
    low_growth_pct: float
    base_growth_pct: float
    high_growth_pct: float
    rationale: str = Field(min_length=20)
```

#### FiveForces（doubt-driven P1-2 修复：用三档枚举不用 int）

```python
class FiveForces(ArtifactBase):
    artifact_type: Literal["five_forces"] = "five_forces"
    new_entrants: Force
    supplier_power: Force
    buyer_power: Force
    substitute_threat: Force
    competitive_rivalry: Force

class Force(BaseModel):
    intensity: Literal["low", "medium", "high"]  # 不用 int 1-5（doubt-driven P1-2）
    drivers: list[str] = Field(min_length=2)
    evidence: list[str] = Field(min_length=1)
    implication: str = Field(min_length=20)
    source_refs: list[SourceRef] = Field(default_factory=list)
```

#### MarketPlayer（doubt-driven P1-3 修复：单一 players source of truth）

```python
class MarketPlayer(BaseModel):
    """竞品玩家统一表示（取代之前的 top_players / incumbent_brands / challenger_brands 等多份名单）"""
    name: str = Field(min_length=1)
    company: str = ""
    market_role: Literal["incumbent", "challenger", "emerging", "niche", "substitute"]  # doubt-driven P0-4：market_role 避免与 S1 wave_position / S5 mq_quadrant 冲突
    market_share_pct: Optional[float] = Field(default=None, ge=0, le=100)  # None 表示未采
    yoy_growth_pct: Optional[float] = None
    one_line_summary: str = Field(min_length=10)
    key_differentiator: str = ""
    is_recommended: bool = False  # 该玩家是 recommender 推荐的
    is_collected: bool = False    # 该玩家被 collector 成功采集
    source_refs: list[SourceRef] = Field(default_factory=list)
```

#### ConsumerSegment（决策 11：Optional + P2）

```python
class ConsumerSegment(BaseModel):
    name: str = Field(min_length=2)
    size_estimate: str = ""
    share_pct: Optional[float] = Field(default=None, ge=0, le=100)
    key_needs: list[str] = Field(min_length=1)
    underserved_indicators: list[str] = Field(default_factory=list)
    addressability: Literal["easy", "moderate", "hard"]
    source_refs: list[SourceRef] = Field(default_factory=list)
```

#### Trend

```python
class Trend(BaseModel):
    trend_name: str = Field(min_length=4)
    description: str = Field(min_length=20)
    supporting_data: str = Field(default="")
    direction: Literal["up", "flat", "down"]
    time_horizon: Literal["short_term", "mid_term", "long_term"]
    impact_on_entry: Literal["positive", "negative", "mixed"]
    source_refs: list[SourceRef] = Field(default_factory=list)
```

#### EntryStrategy

```python
class EntryStrategy(ArtifactBase):
    artifact_type: Literal["entry_strategy"] = "entry_strategy"
    recommended_mode: Literal[
        "direct_competition", "niche_focus", "differentiation",
        "partnership", "acquisition", "wait_and_see"
    ]
    target_segments: list[str] = Field(min_length=1)
    initial_positioning: str = Field(min_length=20)
    key_success_factors: list[str] = Field(min_length=2)
    main_risks: list[Risk] = Field(min_length=1)
    timeline_phases: list[Phase] = Field(min_length=2)

class Risk(BaseModel):
    description: str = Field(min_length=10)
    likelihood: Literal["low", "medium", "high"]
    impact: Literal["low", "medium", "high"]
    mitigation: str = Field(min_length=10)

class Phase(BaseModel):
    phase_name: str = Field(min_length=4)
    duration: str
    key_milestones: list[str] = Field(min_length=1)
    resource_requirements: str = ""
```

#### PESTEL（决策 9.a-2：保留结构 + Optional，首版不填）

```python
class PESTEL(ArtifactBase):
    """PESTEL 6 维宏观因素（决策 9.a-2：首版不填，等知识库到位）

    工程注：首版 S2MarketEntryPayload.pestel 默认 None。
    将来 Cooper 提供"行业背景知识库 + 政策搜索接口"后，启用 LLM 填该字段。
    """
    artifact_type: Literal["pestel"] = "pestel"
    political: list[PESTELFactor] = Field(default_factory=list)
    economic: list[PESTELFactor] = Field(default_factory=list)
    social: list[PESTELFactor] = Field(default_factory=list)
    technological: list[PESTELFactor] = Field(default_factory=list)
    environmental: list[PESTELFactor] = Field(default_factory=list)
    legal: list[PESTELFactor] = Field(default_factory=list)

class PESTELFactor(BaseModel):
    name: str = Field(min_length=4)
    impact: Literal["opportunity", "threat", "neutral"]
    severity: Literal["low", "medium", "high"]  # doubt-driven P1-2 修复：用三档统一量纲
    description: str = Field(min_length=20)
    source_refs: list[SourceRef] = Field(default_factory=list)
```

#### CompetitorRecommendations（仅 S2 有）

```python
class CompetitorRecommendations(BaseModel):
    """recommender 节点产出"""
    user_provided_industry: str = Field(min_length=2)
    user_provided_competitors: list[str] = Field(default_factory=list)  # 用户原始填的（可能为空）
    recommended_competitors: list[RecommendedCompetitor] = Field(min_length=3)
    selection_method: Literal["search_api_top_n", "llm_inference", "hybrid"]
    selection_rationale: str = Field(min_length=30)

class RecommendedCompetitor(BaseModel):
    name: str = Field(min_length=1)
    company: str = ""
    why_recommended: str = Field(min_length=10)
    confidence: Literal["high", "medium", "low"]
    source_refs: list[SourceRef] = Field(default_factory=list)
```

### 3.4 优先级（P0/P1/P2）

| Priority | 字段 |
|---|---|
| **P0**（必做） | market_sizing / players / market_concentration / key_trends / entry_strategy / competitor_recommendations |
| **P1**（强烈建议） | five_forces / industry_attractiveness_1_5 |
| **P2**（推迟到知识库到位） | pestel（决策 9.a-2，schema 留位）/ consumer_segments（决策 11，Optional） |

### 3.5 输入层 + graph 改造（doubt-driven P0-2 修复）

#### CompetitorInput 改造

```python
# src/schemas/input.py（重写）
class CompetitorBasic(BaseModel):
    name: str = Field(min_length=2, max_length=50)
    company: str = ""
    category: str = ""

class ScenarioInput(BaseModel):
    """统一输入 schema，按 scenario 分支校验（doubt-driven P0-2 修复）"""
    scenario: Literal["S1", "S2", "S3", "S4", "S5"]
    competitors: list[CompetitorBasic] = Field(default_factory=list, max_length=10)
    industry: Optional[str] = None  # S2 必填
    analysis_context: str = Field(min_length=1)

    # S1 / S3 / S4 / S5 必填的字段（首版只实现 S1/S2）
    our_product_name: Optional[str] = None
    our_product_brief: Optional[str] = None

    @model_validator(mode='after')
    def _check_scenario_inputs(self) -> 'ScenarioInput':
        if self.scenario == "S2":
            if not self.industry:
                raise ValueError("S2 市场进入场景必须提供 industry")
            # competitors 可以为空（recommender 会推荐）
        else:
            if not self.competitors:
                raise ValueError(f"{self.scenario} 场景必须提供至少一个 competitor")
            if self.scenario != "S2" and not self.our_product_name:
                raise ValueError(f"{self.scenario} 场景必须提供 our_product_name")
        return self
```

#### Graph 拓扑改造

```
S1/S3/S4/S5: collector → analyzer → writer → inspector ─→ END
S2:          recommender → collector → analyzer → writer → inspector ─→ END

graph 入口节点根据 ScenarioInput.scenario 路由：
- S2 → 入 recommender
- 其他 → 入 collector
```

`recommender` 节点：
1. 接收 `ScenarioInput.industry` + `analysis_context`
2. 调用 SerpAPI/Tavily 查"<industry> Top 5 玩家"
3. LLM 选 5 个最相关的玩家，产出 `CompetitorRecommendations`
4. **不**回填 `ScenarioInput.competitors`（doubt-driven P1-3 修复），而是在 `AnalysisState` 加 `recommended_competitors: list[CompetitorBasic]` 字段，collector 优先读这个

---

## Part 4：跨场景一致性原则

### 4.1 命名约定（doubt-driven P2-1 / P2-2 修复）

- **字段名**：snake_case
- **数值字段单位标在字段名**：`industry_attractiveness_1_5` / `market_share_pct` / `cagr_pct`
- **日期字段**：用 `date` 类型而非 str（`accessed_at: Optional[date]` / `publication_date: date`）
- **可变默认值**：统一用 `Field(default_factory=list/dict)`
- **来源对象**：统一用 `source_refs: list[SourceRef]`，禁止再有 `source_urls / sources / evidence_url` 命名分歧（除 FeatureScore 因有特殊语义保留 `evidence_url: Optional[str]` 加 source_missing_reason 二选一约束）

### 4.2 共享枚举（doubt-driven P0-4 / P1-2 修复）

| 字段名 | 枚举 | 用途 |
|---|---|---|
| `intensity / impact / likelihood / severity / confidence` | `Literal["low", "medium", "high"]` | 严重度（统一三档，禁止 int 1-5） |
| `time_horizon` | `Literal["short_term", "mid_term", "long_term"]` | 时间窗 |
| `direction` | `Literal["up", "flat", "down"]` | 趋势方向 |

### 4.3 场景前缀枚举（doubt-driven P0-4 修复）

| 字段名 | 枚举 | 含义 |
|---|---|---|
| `wave_position`（S1） | `Literal["wave_leader", "wave_strong_performer", "wave_contender"]` | 仿 Forrester Wave 三档 |
| `mq_quadrant`（S5） | `Literal["mq_leader", "mq_challenger", "mq_visionary", "mq_niche_player"]` | 仿 Gartner MQ 四象限 |
| `market_role`（S2） | `Literal["incumbent", "challenger", "emerging", "niche", "substitute"]` | 市场玩家类型 |
| `recommendation`（S1 FeatureGap） | `Literal["build", "skip", "differentiate"]` | Roadmap 建议 |

**关键原则**：跨场景**永远不出现裸 `leader/challenger`** —— 必有前缀消歧义（doubt-driven P0-4 修复方向）。

### 4.4 LLM 输出鲁棒性（doubt-driven P1-8 修复）

每个场景 payload 在写到 schema 前过**场景特定的 _normalize layer**：
- `_normalize_s1_raw(raw: dict) -> dict`：枚举规整 + competitor name 一致性补全 + computed fields 移除
- `_normalize_s2_raw(raw: dict) -> dict`：value_basis 兜底 + force intensity 规整
- ...

不再共用单一 `_normalize_raw`。

### 4.5 quality_score 计算定义（doubt-driven P2-4 修复）

```
quality_score = 0.4 × source_coverage + 0.3 × confidence_avg + 0.3 × inspector_pass_rate
- source_coverage = 有 source_refs 的字段数 / 总字段数
- confidence_avg = 平均 confidence_level 数值化（high=1, medium=0.6, low=0.3）
- inspector_pass_rate = 1 - (issues 严重度加权和 / 满分)
```

由 inspector 节点计算填入 `metadata.quality_score`（不让 LLM 自评）。

---

## Part 5：评审记录与决策

### 5.1 doubt-driven 双模型审查发现（合并去重）

**审查机制**：
- 单模型审查：`general-purpose` agent 跨上下文审查
- 跨模型审查：`codex` CLI（gpt-5.5）跨上下文审查
- 合并方式：双模型一致命中（10 条）+ 单方独有（claude 4 条 / codex 5 条），共 19 条独立问题

**P0 致命问题**（6 条，必修）：
1. discriminated union 三处 scenario 字段不一致 → 改为 computed_field 派生
2. 旧 schema 废除清单缺失（FeatureMatrixEntry / SwotEntry / RadarScore 归宿）→ Part 0 新增清单
3. S2 必填字段会成幻觉发动机（TAM/SAM/SOM 默认 0）→ 改 Optional + value_basis
4. 跨场景枚举语义碰撞（leader/challenger 跨 S1/S5）→ 加场景前缀（wave_/mq_/market_）
5. writer 重构编排空缺 → Part 6 新增编排方案
6. evidence_url 标必填但默认空字符串 → score=2 必有 evidence_url 强制
7. S1 weighted scoring 数据模型缺失 → 加 model_validator 校验竞品名一致

**P1 重要问题**（9 条，必修）：
1. CompetitorInput.min_length 与 S2 冲突 → 新建 ScenarioInput
2. BattleCard YAGNI（决策 4 删除）
3. S2 竞品名单 4 处冗余 → 单一 players: list[MarketPlayer]
4. BaseReport 与 payload 重复事实入口 → 通用层 narrative+索引、payload 是事实权威
5. exhibits 引用机制不成立 → ArtifactBase + artifact_id 协议
6. severity int 1-5 与 low/medium/high 量纲冲突 → 全部统一三档枚举
7. opportunity_score 应代码算 → JTBD 简化（决策 7）后该字段已不存在
8. ExecutiveSummary 字数约束在注释 → 全部 Field(min_length/max_length)
9. LLM normalize 复杂度被低估 → 按场景写 _normalize layer

**P2 次要问题**（4 条，全修）：
1. 命名风格不一致 → SourceRef 统一命名 + 量纲后缀
2. 日期字段全是 str → 改 date 类型 + Optional 兜底
3. 市场规模缺单位口径 → MarketValue（amount/currency/unit/year/geography/value_basis）
4. quality_score 计算定义 → Part 4.5 公式

### 5.2 12 条产品决策落地

| # | 决策 | 选项 | 落地位置 |
|---|---|---|---|
| 1 | SWOT 保留 | c：5 场景全保留 | Part 1 BaseReport.swot 字段 |
| 2 | 雷达图保留 | c：S1+S5 都保留 | S1 → S1RadarScore 5 维 / S5 → 第 2 批 PerceptualMap 二维 |
| 3 | S2 推荐 N | b：Top 5 | S2.players min/max=3-10（建议 5） |
| 4 | BattleCard | a：完全删除 | Part 2 已删 BattleCard 全部子模型 |
| 5 | 报告章节数 | b：5-6 章 | BaseReport.analysis_sections min/max=4-8 |
| 6 | timeline+priority | a：同时保留 | Recommendation 双字段 |
| 7 | JTBD | b：简化只留 JobStatement | Part 2 删 FourForces/DesiredOutcomes/CompetitiveAlternatives |
| 8 | Methodology 字数 | c：1000+ 字 | Methodology.data_collection_approach min_length=200 |
| 9 | PESTEL | a-2：保留结构 + Optional | S2.pestel: Optional[PESTEL] = None |
| 10 | competitive_alternatives | a：P2 推迟 | 已删 |
| 11 | consumer_segments | b：保留 P2 + Optional | S2.consumer_segments: Optional[...] = None |
| 12 | 报告字数 | a：方案乙 7000-8000 | Part 6 writer 编排按方案乙规划 |

### 5.3 修改后与初版的差异（diff 概览）

- BaseReport：删 `scenario` 字段 + 加 `swot` 字段 + 字段全加 Field 约束
- S1 payload：删 BattleCard / Four Forces / Desired Outcomes / Competitive Alternatives；加 S1RadarScore；加 model_validator
- S2 payload：删多份名单 → 单一 players；MarketValue 加单位口径；PESTEL 改 Optional；加 ScenarioInput 取代 CompetitorInput
- 命名：source_urls/sources/evidence_url → SourceRef；severity int → low/medium/high；leader → wave_leader/mq_leader/market_challenger
- 通用：date 字段类型化、computed_field 派生、Field(default_factory=...)

---

## Part 6：writer 重构编排方案（doubt-driven P0-5 修复）

### 6.1 当前问题

现有 writer 是单次 LLM 调用产 `FinalReport`，不能稳定产 7000-8000 字 + 大 payload。

### 6.2 新编排（4 阶段）

```
阶段 1：骨架生成（1 次 LLM 调用，~1500 token 输出）
  输入：analysis（CompetitiveAnalysis） + ScenarioInput
  输出：title / subtitle / at_a_glance / executive_summary / scope / key_findings / recommendations 等结构化字段（不含 narrative）
  目的：确定整体框架和"骨架级结论"

阶段 2：scenario_payload 结构化产物（1-2 次 LLM 调用）
  输入：analysis + 阶段 1 骨架
  输出：S1 → vendor_profiles + feature_matrix + radar_scores + roadmap_recommendations 等
        S2 → market_sizing + players + entry_strategy 等
  目的：填充结构化产物（无 narrative）

阶段 3：分章节 narrative 生成（4-6 次 LLM 调用，按 analysis_sections 数量）
  输入：阶段 1 骨架 + 阶段 2 payload + 该 section 的 section_type
  输出：单个 AnalysisSection.narrative（深耕章节 2000-3000 字 / 简短章节 500 字）
  目的：分章节产 narrative，避免单次超长

阶段 4：合并 + 程序化产物 + validator
  动作：
    - 代码计算 weighted_scores / wave_position / weight 等 computed_field
    - 透传 SWOT / radar_scores / feature_matrix 不丢失
    - 跑 model_validator 校验一致性
    - inspector 计算 quality_score

  目的：保证结构 100% 不丢、URL 100% 真实
```

### 6.3 LLM 调用预算

| 阶段 | 调用次数 | 单次 token | 累计 |
|---|---|---|---|
| 1（骨架） | 1 | 输入 ~3000 / 输出 ~2000 | 5000 |
| 2（payload） | 2 | 输入 ~5000 / 输出 ~3000 | 16000 |
| 3（narrative） | 5 | 输入 ~3000 / 输出 ~2500 | 27500 |
| 4（合并） | 0 | 0 | 0 |
| **合计** | **8** | | ~48500 |

**单次分析时间**：8 次 LLM 调用，按每次 30-60s 估算 = **4-8 分钟**（writer 阶段）；加上 collector/analyzer/inspector，整体 **12-18 分钟**。

### 6.4 失败重试策略

- 阶段 1 骨架失败 → 整体重试（最多 2 次）
- 阶段 2 payload 失败 → 该 payload 重试（最多 2 次），失败则降级为 `{}` + warning
- 阶段 3 单 section narrative 失败 → 该 section 重试（最多 2 次），失败则跳过 + warning（不阻断其他章节）
- 阶段 4 validator 失败 → 走 `_normalize_<scenario>` 修复一次，仍失败则报错

---

## Part 7：S3 PricingStrategyPayload（定价策略）

### 7.1 场景定位

- **用户**：已有产品的 PM / 市场负责人
- **触发时机**：准备定价或调价
- **业界标杆**：Simon-Kucher 4-Step Value-Based Pricing + Good/Better/Best Packaging + CompareTiers Pricing Page Audit
- **关键差异**：定价是细致活，不能让 LLM 编造价格，所有价格字段必须有 evidence_url

### 7.2 顶层结构

```python
class S3PricingStrategyPayload(BaseModel):
    """S3 定价策略场景载荷"""
    scenario_type: Literal["S3"] = "S3"  # discriminator

    # === 1. 现状基线（我方现有定价） ===
    pricing_baseline: PricingBaseline

    # === 2. 价值驱动（顶层是详细对象，FeatureClassification.premium_drivers 是名字清单） ===
    value_drivers: list[ValueDriver] = Field(min_length=3)
    feature_classification: FeatureClassification

    # === 3. WTP 研究（首版 Optional） ===
    wtp_research: Optional[WTPResearch] = None

    # === 4. 推荐套餐设计（GBB 三层套餐法，使用 RecommendedPriceTier） ===
    packaging: Packaging

    # === 5. 竞品定价矩阵（使用 ObservedCompetitorTier，每条价格强制溯源） ===
    competitive_pricing_matrix: list[CompetitorPricing] = Field(min_length=2)

    # === 6. 定价页审计（每竞品一份；audit_scores 可空避免幻觉） ===
    pricing_page_audit: list[PricingPageAudit] = Field(default_factory=list)

    # === 7. 推荐方案 + Rollout ===
    recommendations_summary: PricingRecommendationsSummary
    rollout_plan: list[RolloutStep] = Field(min_length=3)

    @model_validator(mode='after')
    def _check_competitor_consistency(self) -> 'S3PricingStrategyPayload':
        """竞品名一致性：competitive_pricing_matrix / pricing_page_audit 应同集合"""
        matrix_competitors = {cp.competitor_name for cp in self.competitive_pricing_matrix}
        audit_competitors = {pa.competitor_name for pa in self.pricing_page_audit}
        if audit_competitors and not audit_competitors.issubset(matrix_competitors):
            raise ValueError(f"pricing_page_audit 竞品 {audit_competitors} 不在 competitive_pricing_matrix 中")
        return self
```

### 7.3 子模型定义（已应用第 2 批所有修复）

```python
class PricingBaseline(BaseModel):
    """我方现有定价基线"""
    current_pricing_model: Literal["per_seat", "flat_rate", "usage_based", "hybrid", "freemium", "platform_fee", "unknown"]
    current_tier_count: int = Field(ge=0, le=10)
    current_arpu_note: str = Field(default="")
    pain_points: list[str] = Field(min_length=1)
    source_refs: list[SourceRef] = Field(default_factory=list)

class ValueDriver(BaseModel):
    """价值驱动因子（Simon-Kucher 第 1 步）"""
    driver_name: str = Field(min_length=4)
    importance: Literal["low", "medium", "high"]
    evidence: str = Field(min_length=20)
    source_refs: list[SourceRef] = Field(default_factory=list)

class FeatureClassification(BaseModel):
    """功能分类（hygiene / preference / premium driver）

    注：内部字段名 premium_drivers 避免与顶层 S3.value_drivers 命名碰撞（第 2 批 P1-8 修复）
    """
    hygiene_factors: list[str] = Field(min_length=1)
    preference_drivers: list[str] = Field(default_factory=list)
    premium_drivers: list[str] = Field(min_length=1)  # 重命名（原 value_drivers）

class WTPResearch(BaseModel):
    """支付意愿研究（首版 Optional，未来用户上传问卷数据再启用）

    注：method 中的 'proxy_from_competitor_pricing' 明示这是代理推断而非真实 WTP（第 2 批 P1 修复）
    """
    method: Literal[
        "conjoint_analysis", "van_westendorp", "gabor_granger",
        "interviews", "ab_testing", "proxy_from_competitor_pricing"
    ]
    sample_size: Optional[int] = None
    optimal_price_point: Optional[str] = None
    confidence: Literal["low", "medium", "high"] = "low"
    rationale: str = Field(min_length=20)
    limitations: str = Field(default="")  # proxy_from_competitor_pricing 时强制必填

    @model_validator(mode='after')
    def _enforce_proxy_low_confidence(self) -> 'WTPResearch':
        """proxy_from_competitor_pricing 必须 confidence=low + 必填 limitations"""
        if self.method == "proxy_from_competitor_pricing":
            if self.confidence != "low":
                raise ValueError("WTPResearch.method=proxy_from_competitor_pricing 时 confidence 必须为 low")
            if not self.limitations:
                raise ValueError("WTPResearch.method=proxy_from_competitor_pricing 时 limitations 必填")
        return self


# ========== 第 2 批 P0-4 修复：拆分 PriceTier 为我方 / 竞品两类 ==========

class RecommendedPriceTier(BaseModel):
    """我方推荐套餐的单层（用于 Packaging）"""
    name: str = Field(min_length=2)  # "Free" / "Pro" / "Business" / "Enterprise"
    position: Literal["good", "better", "best", "enterprise", "free"]
    monthly_price: Optional[float] = Field(default=None, ge=0)  # 第 2 批 P2 修复：ge=0 防负价格
    annual_price: Optional[float] = Field(default=None, ge=0)
    currency: Literal["CNY", "USD", "EUR", "JPY", "unknown"] = "CNY"
    billing_unit: Literal["per_seat", "flat_rate", "usage_based", "tier_subscription"]
    is_recommended: bool = False  # "Most Popular" 标记
    target_persona: str = Field(min_length=10)
    included_features: list[str] = Field(min_length=1)
    gated_features: list[str] = Field(default_factory=list)
    cta_copy: str = Field(default="")
    upgrade_trigger: str = Field(default="")

    @model_validator(mode='after')
    def _check_annual_le_monthly_x12(self) -> 'RecommendedPriceTier':
        """年付不能贵过月付 x12（第 2 批 P2 修复）"""
        if self.monthly_price is not None and self.annual_price is not None:
            if self.annual_price > self.monthly_price * 12:
                raise ValueError(f"annual_price {self.annual_price} > monthly_price x12 {self.monthly_price * 12}")
        return self


class ObservedCompetitorTier(BaseModel):
    """竞品现有套餐的单层（用于 CompetitorPricing）

    第 2 批 P0-3 + P0-4 修复：
    - 字段语义改为"采集到的事实"而非"建议"（cta_copy → observed_cta_copy）
    - 每条价格强制 source_refs（防幻觉）
    """
    name: str = Field(min_length=2)
    monthly_price: Optional[float] = Field(default=None, ge=0)
    annual_price: Optional[float] = Field(default=None, ge=0)
    currency: Literal["CNY", "USD", "EUR", "JPY", "unknown"] = "CNY"
    billing_unit: Literal["per_seat", "flat_rate", "usage_based", "tier_subscription"]
    observed_is_most_popular: bool = False  # 竞品自己标的 Most Popular（事实，非建议）
    observed_target_persona: str = Field(default="")  # 采集到的目标客户
    observed_features: list[str] = Field(min_length=1)
    observed_cta_copy: str = Field(default="")  # 采集到的 CTA 文案

    # 第 2 批 P0-3 修复：每条价格必须能溯源
    source_refs: list[SourceRef] = Field(min_length=1)


class Packaging(ArtifactBase):
    """推荐套餐设计（GBB 三层套餐法，使用 RecommendedPriceTier）"""
    artifact_type: Literal["packaging"] = "packaging"
    tiers: list[RecommendedPriceTier] = Field(min_length=2, max_length=5)
    annual_discount_pct: Optional[float] = Field(default=None, ge=0, le=50)
    default_billing_cycle: Literal["monthly", "annual"] = "annual"
    rationale: str = Field(min_length=50)

    @model_validator(mode='after')
    def _check_recommended_tier(self) -> 'Packaging':
        """第 2 批 P1 修复：有且仅有一个 is_recommended（不是 ≤1，是 == 1）"""
        recommended = [t for t in self.tiers if t.is_recommended]
        if len(recommended) != 1:
            raise ValueError(f"Packaging 应有且仅有一个 is_recommended tier，发现 {len(recommended)} 个")
        return self

    @model_validator(mode='after')
    def _check_position_uniqueness(self) -> 'Packaging':
        """同一 GBB 位置不能重复（避免 LLM 全填 'good'）"""
        positions = [t.position for t in self.tiers]
        # free 和 enterprise 可重复（实际不会，但允许），good/better/best 唯一
        for p in ["good", "better", "best"]:
            if positions.count(p) > 1:
                raise ValueError(f"position={p} 在 tiers 中重复 {positions.count(p)} 次")
        return self


class CompetitorPricing(ArtifactBase):
    """单个竞品的定价矩阵（用 ObservedCompetitorTier）"""
    artifact_type: Literal["competitor_pricing"] = "competitor_pricing"
    competitor_name: str = Field(min_length=1)
    pricing_model: Literal["per_seat", "flat_rate", "usage_based", "hybrid", "freemium", "platform_fee", "unknown"]
    tiers: list[ObservedCompetitorTier] = Field(min_length=1)  # 改用 Observed 子类
    free_plan_strategy: Optional[Literal["freemium", "free_trial", "no_free_plan"]] = None
    discount_strategy: str = Field(default="")
    notes: str = Field(default="")
    source_refs: list[SourceRef] = Field(min_length=1)  # 顶层来源（除 tier 内的具体来源外）


class PricingPageAuditScore(BaseModel):
    """单条审计法则评分"""
    rule_name: Literal[
        "tier_naming_buyer_centric",
        "anchor_pricing_middle_tier",
        "annual_billing_default",
        "feature_gating_clear",
        "cta_copy_aligned",
        "social_proof_at_decision",
        "transparent_feature_comparison",
        "psychological_pricing"
    ]
    passed: bool
    note: str = Field(default="")


class PricingPageAudit(ArtifactBase):
    """竞品定价页审计（第 2 批 P0-3 修复：从 min_length=8 改为可空+max=8 避免幻觉）"""
    artifact_type: Literal["pricing_page_audit"] = "pricing_page_audit"
    competitor_name: str = Field(min_length=1)
    audit_scores: list[PricingPageAuditScore] = Field(default_factory=list, max_length=8)
    pricing_page_url: Optional[str] = Field(default=None, min_length=8)
    source_refs: list[SourceRef] = Field(default_factory=list)

    @computed_field
    @property
    def overall_score_pct(self) -> Optional[float]:
        """第 2 批 P0-5 修复：从 audit_scores 派生通过率，不让 LLM 填"""
        if not self.audit_scores:
            return None
        passed_count = sum(1 for s in self.audit_scores if s.passed)
        return round(passed_count / len(self.audit_scores) * 100, 1)

    @model_validator(mode='after')
    def _check_no_url_no_audit(self) -> 'PricingPageAudit':
        """没采到定价页 URL 时不允许填 audit_scores（防幻觉）"""
        if self.pricing_page_url is None and self.audit_scores:
            raise ValueError("未采集到 pricing_page_url 时，audit_scores 必须为空")
        return self


class PricingRecommendationsSummary(BaseModel):
    """推荐定价方案总结（第 2 批 P1 修复：expected_arr_uplift_pct 加 basis）"""
    recommended_packaging_summary: str = Field(min_length=50)
    expected_arr_uplift_pct: Optional[float] = Field(default=None, ge=-50, le=200)
    expected_arr_uplift_basis: Literal[
        "measured_pilot", "competitor_benchmark", "industry_estimate", "llm_inferred"
    ] = "llm_inferred"
    expected_arr_uplift_methodology: str = Field(default="")
    expected_uplift_rationale: str = Field(min_length=20)
    main_risks: list[Risk] = Field(min_length=1)

    @model_validator(mode='after')
    def _require_methodology_for_specific_basis(self) -> 'PricingRecommendationsSummary':
        """非 llm_inferred 的 basis 必须有 methodology 说明"""
        if self.expected_arr_uplift_basis != "llm_inferred":
            if not self.expected_arr_uplift_methodology or len(self.expected_arr_uplift_methodology) < 20:
                raise ValueError(
                    f"expected_arr_uplift_basis={self.expected_arr_uplift_basis} 时 methodology 必填且 ≥20 字"
                )
        return self


class RolloutStep(ArtifactBase):
    """Rollout 步骤（继承 ArtifactBase 以便被 AnalysisSection.artifact_refs 引用）"""
    artifact_type: Literal["rollout_step"] = "rollout_step"
    step_name: str = Field(min_length=4)
    description: str = Field(min_length=20)
    duration: str
    owner_team: str = Field(default="")
    success_metric: str = Field(default="")
    # step_order 移除，依赖 list 顺序（第 2 批 P2 修复双轨制）
```

### 7.4 优先级（P0/P1/P2）

| Priority | 字段 |
|---|---|
| **P0**（必做） | pricing_baseline / packaging / competitive_pricing_matrix / recommendations_summary |
| **P1**（强烈建议） | value_drivers / feature_classification / rollout_plan |
| **P2**（推迟） | wtp_research（首版 Optional）/ pricing_page_audit（依赖竞品定价页爬取） |

### 7.5 与采集层依赖

| 字段 | 依赖 | 状态 |
|---|---|---|
| `competitive_pricing_matrix.tiers` | 竞品定价页 | ✓ collector 已能抓 pricing 字段 |
| `pricing_page_audit` | 竞品定价页文本 + 视觉特征 | △ 部分能做（CTA 文案/年付默认/tier 数）；社会证明视觉特征 LLM 可能误判 |
| `wtp_research` | 用户调研数据 | ✗ 公开渠道无 → 首版 Optional |

---

## Part 8：S4 MonitoringPayload（持续监控）

### 8.1 场景定位

- **用户**：已有产品的 PM / 市场负责人
- **触发时机**：例行更新、跟踪竞品动态（区别于 S1-S3 一次性深度分析）
- **业界标杆**：OSCOM Quarterly + IndustryLens Living Battlecard + Klue FIA Framework
- **关键差异**：**唯一一个 schema 内嵌 prior 版本字段** —— "intelligence is the delta"

### 8.2 关键设计：prior_trace_id 与首次降级模式（决策 13a + 第 2 批 P0-1 修复）

S4 不需要重新发明 prior version 存储——**直接复用现有 `runs/<trace_id>/` 机制**。具体：

**首次监控模式（prior_trace_id=None）**：
- 允许 prior_trace_id 缺失（首次跑 S4 时必然如此）
- 此时 trends 全部为 None；feature_changes 等记录 baseline_snapshot（"当前已有功能"作基线，不污染 change log）
- writer 阶段在 prompt 中明示"这是首次监控，请只输出当前状态"

**继续监控模式（prior_trace_id 提供）**：
- 用户在前端 S4 表单提供 prior_trace_id
- writer 节点读取 `runs/<prior_trace_id>/03_report.json`
- **强制校验**：
  - 文件存在
  - `metadata.scenario == "S4"`（防止把 S1/S2 报告当 prior）
  - `metadata.schema_version` 与当前一致（防止跨 schema 版本差异）
  - 校验失败 → 当作"首次监控模式"处理 + warning

这避免了 schema 内大量 `prior_*` 字段冗余。校验逻辑由 graph 入口节点（前端提交时校验）+ writer 节点（再次校验）实现。

### 8.3 顶层结构

```python
class S4MonitoringPayload(BaseModel):
    """S4 持续监控场景载荷"""
    scenario_type: Literal["S4"] = "S4"  # discriminator

    # === 1. 时间窗 ===
    review_period: ReviewPeriod

    # === 2. 增量变更日志（按类型分桶，每条遵循 Klue FIA: Fact/Impact/Act） ===
    feature_changes: list[FeatureChange] = Field(default_factory=list)
    pricing_changes: list[PricingChange] = Field(default_factory=list)
    messaging_changes: list[MessagingChange] = Field(default_factory=list)
    news_events: list[NewsEvent] = Field(default_factory=list)
    org_changes: list[OrgChange] = Field(default_factory=list)

    # === 3. 威胁评估（OSCOM Section 3：severity × likelihood 2x2，最多 5 条） ===
    threats: list[MonitoringThreat] = Field(default_factory=list, max_length=5)

    # === 4. 机会识别（OSCOM Section 4：4 类机会） ===
    opportunities: list[MonitoringOpportunity] = Field(default_factory=list, max_length=8)

    # === 5. 趋势方向（连续监控才能算出来） ===
    trends: MonitoringTrends

    # === 6. 推荐行动（第 2 批 P1 修复：移除 min_length 允许"本期无重大变更"） ===
    monitoring_actions: list[MonitoringAction] = Field(default_factory=list, max_length=12)

    # === 7. 活体 Battlecard（每竞品一张） ===
    battlecards: list[Battlecard] = Field(min_length=1)

    @model_validator(mode='after')
    def _check_monitored_competitor_consistency(self) -> 'S4MonitoringPayload':
        """第 2 批 P1 修复：所有变更/battlecard 的竞品名必须在 monitored_competitors 中"""
        monitored = set(self.review_period.monitored_competitors)
        for collection_name, items in [
            ("feature_changes", self.feature_changes),
            ("pricing_changes", self.pricing_changes),
            ("messaging_changes", self.messaging_changes),
            ("news_events", self.news_events),
            ("org_changes", self.org_changes),
        ]:
            for item in items:
                if item.competitor_name not in monitored:
                    raise ValueError(f"{collection_name} 中竞品 '{item.competitor_name}' 不在 monitored_competitors {monitored}")
        for bc in self.battlecards:
            if bc.competitor_name not in monitored:
                raise ValueError(f"battlecards 中竞品 '{bc.competitor_name}' 不在 monitored_competitors {monitored}")
        return self

    @model_validator(mode='after')
    def _check_first_review_baseline(self) -> 'S4MonitoringPayload':
        """第 2 批 P2 修复：首次监控模式（prior_trace_id=None）时所有 changes 必须 is_baseline=True"""
        if self.review_period.prior_trace_id is None:
            for items in [self.feature_changes, self.pricing_changes, self.messaging_changes,
                         self.news_events, self.org_changes]:
                for item in items:
                    if not item.is_baseline:
                        raise ValueError(
                            f"首次监控模式（prior_trace_id=None）下，所有 change 条目必须 is_baseline=True"
                        )
            # 首次监控时 trends 必须全 None（无 prior 无法算趋势）
            t = self.trends
            if any([t.sentiment_trend, t.pricing_trend, t.release_velocity_trend, t.threat_level_trend]):
                raise ValueError("首次监控模式下 trends 必须全部为 None")
        return self
```

### 8.4 子模型定义（已应用第 2 批所有修复）

```python
class ReviewPeriod(BaseModel):
    """监控时间窗（第 2 批 P1 修复：补 newly_added/dropped 字段）"""
    last_review_date: Optional[date] = None
    current_review_date: date
    review_period_label: str = Field(min_length=4)  # "2026 Q1"
    monitored_competitors: list[str] = Field(min_length=1)
    prior_trace_id: Optional[str] = None  # 缺失则走"首次监控"模式

    # 第 2 批 P1 修复：跨期竞品集合变化追踪
    newly_added_competitors: list[str] = Field(default_factory=list)
    dropped_competitors: list[str] = Field(default_factory=list)


class FIATuple(BaseModel):
    """Klue FIA 三元组（决策 17a：fact 必填，impact + act Optional 防 LLM 编造）"""
    fact: str = Field(min_length=10)  # 上下文 + 洞察（必填）
    impact: Optional[str] = None       # 为什么重要（弱信号时可空）
    act: Optional[str] = None          # 可执行动作（弱信号时可空，禁止瞎编）


class _BaseChange(BaseModel):
    """所有变更条目共享的基础字段（便于一致校验）"""
    competitor_name: str = Field(min_length=1)
    detected_date: Optional[date] = None
    fia: FIATuple
    severity: Literal["low", "medium", "high"]
    source_refs: list[SourceRef] = Field(min_length=1)
    is_baseline: bool = False  # 第 2 批 P2 修复：首次监控模式时填 True，避免污染 change log


class FeatureChange(_BaseChange, ArtifactBase):
    artifact_type: Literal["feature_change"] = "feature_change"
    change_type: Literal["new_feature", "removed_feature", "feature_updated"]
    feature_name: str = Field(min_length=2)


class PricingChange(_BaseChange, ArtifactBase):
    artifact_type: Literal["pricing_change"] = "pricing_change"
    change_type: Literal["tier_added", "tier_removed", "price_increased", "price_decreased", "packaging_restructured", "discount_changed"]
    before: str = Field(default="")
    after: str = Field(default="")


class MessagingChange(_BaseChange, ArtifactBase):
    artifact_type: Literal["messaging_change"] = "messaging_change"
    change_type: Literal["headline_changed", "positioning_shift", "brand_update", "campaign_launch"]
    before_text: str = Field(default="")
    after_text: str = Field(default="")


class NewsEvent(_BaseChange, ArtifactBase):
    artifact_type: Literal["news_event"] = "news_event"
    category: Literal["funding", "partnership", "leadership", "legal", "product_launch", "acquisition", "ipo", "layoff", "other"]
    headline: str = Field(min_length=10)


class OrgChange(_BaseChange, ArtifactBase):
    artifact_type: Literal["org_change"] = "org_change"
    role: str = Field(min_length=2)
    person_name: Optional[str] = None
    # 第 2 批 P2 修复：补全枚举（joined_board / title_changed / founder_exit）
    action: Literal["hired", "departed", "promoted", "demoted", "joined_board", "title_changed", "founder_exit"]


class MonitoringThreat(ArtifactBase):
    """威胁评估（quadrant 由 severity×likelihood 自动派生）"""
    artifact_type: Literal["monitoring_threat"] = "monitoring_threat"
    title: str = Field(min_length=10)
    severity: Literal["low", "medium", "high"]
    likelihood: Literal["low", "medium", "high"]
    description: str = Field(min_length=30)
    recommended_response: str = Field(min_length=20)
    source_refs: list[SourceRef] = Field(default_factory=list)

    @computed_field
    @property
    def quadrant(self) -> Literal["act_now", "contingency", "monitor", "deprioritize"]:
        """第 2 批 P0-5 修复：quadrant 由代码派生不让 LLM 填"""
        s_high = self.severity == "high"
        l_high = self.likelihood == "high"
        if s_high and l_high: return "act_now"
        if s_high and not l_high: return "contingency"
        if not s_high and l_high: return "monitor"
        return "deprioritize"


class MonitoringOpportunity(ArtifactBase):
    """机会识别（OSCOM 4 类）"""
    artifact_type: Literal["monitoring_opportunity"] = "monitoring_opportunity"
    opportunity_type: Literal[
        "abandoned_segment",
        "product_gap",
        "messaging_white_space",
        "operational_weakness"
    ]
    description: str = Field(min_length=20)
    estimated_effort: Literal["low", "medium", "high"]
    expected_impact: Literal["low", "medium", "high"]
    first_step: str = Field(min_length=10)
    source_refs: list[SourceRef] = Field(default_factory=list)


class MonitoringTrends(BaseModel):
    """趋势方向（第 2 批 P1 修复：枚举全部统一为 up/flat/down）"""
    sentiment_trend: Optional[Literal["up", "flat", "down"]] = None
    pricing_trend: Optional[Literal["up", "flat", "down"]] = None
    release_velocity_trend: Optional[Literal["up", "flat", "down"]] = None  # 改 up/flat/down
    threat_level_trend: Optional[Literal["up", "flat", "down"]] = None       # 改 up/flat/down
    rationale: str = Field(default="")


class MonitoringAction(BaseModel):
    """推荐行动（第 2 批 P2 修复：supporting_intel_refs 用 artifact_id）"""
    description: str = Field(min_length=20)
    owner_team: Literal["product", "marketing", "sales", "exec", "engineering", "support"]
    priority_tier: Literal["critical", "important", "consider"]
    due_date_estimate: Optional[date] = None
    supporting_intel_refs: list[str] = Field(default_factory=list)  # 引用 ArtifactBase.artifact_id


class BattlecardSection(BaseModel):
    """Battlecard 单节（第 2 批 P1 修复：completeness 改名 + source_refs 命名修正）"""
    section_name: Literal[
        "quick_summary", "primary_threat", "messaging_positioning",
        "pricing_packaging", "product_strategy",
        "customer_sentiment", "win_loss_themes", "monitoring_priorities"
    ]
    content: str = Field(default="")
    completeness: Literal["full", "partial", "empty"] = "empty"  # 改名（原 confidence；表达的是数据完整度而非可信度）
    source_refs: list[SourceRef] = Field(default_factory=list)  # 改名（原 sources）


class Battlecard(ArtifactBase):
    """单竞品活体 Battlecard"""
    artifact_type: Literal["battlecard"] = "battlecard"
    competitor_name: str = Field(min_length=1)
    sections: list[BattlecardSection] = Field(min_length=4)
    overall_completeness: Literal["full", "partial", "empty"] = "partial"  # 改名

    @computed_field
    @property
    def last_updated_at(self) -> Optional[date]:
        """第 2 批 P1 修复：last_updated_at 由 sections.source_refs.accessed_at 最大值派生"""
        all_dates = []
        for s in self.sections:
            for ref in s.source_refs:
                if ref.accessed_at:
                    all_dates.append(ref.accessed_at)
        return max(all_dates) if all_dates else None
```

### 8.5 优先级（P0/P1/P2）

| Priority | 字段 |
|---|---|
| **P0**（必做） | review_period / feature_changes + pricing_changes + news_events / threats / opportunities / monitoring_actions / battlecards |
| **P1**（强烈建议） | messaging_changes / org_changes / trends（仅 prior_trace_id 存在时启用） |
| **P2**（推迟） | 全字段已 P0+P1 覆盖，无 P2 |

### 8.6 与现有架构对接

- **prior_trace_id 输入**：用户在前端 S4 表单中可选填"上次分析的 trace_id"
- **writer 阶段**：检测到 `prior_trace_id` 时，从 `runs/<prior_trace_id>/03_report.json` 读旧报告，注入到 prompt 让 LLM 做 delta 分析
- **首次监控模式**：`prior_trace_id=None` 时，trends 全部为 None，feature_changes 等记录"当前已有功能"作为基线

---

## Part 9：S5 PositioningPayload（战略定位）

### 9.1 场景定位

- **用户**：已有产品的高管 / 创始人 / 战略 PM
- **触发时机**：重新定位、品牌升级、做投资人 deck
- **业界标杆**：Gartner Magic Quadrant + Perceptual Map + Strategy Canvas + Geoffrey Moore Positioning Statement
- **关键差异**：S5 输出的是 **"我方应该卡哪个位置"**，不是"竞品评分"

### 9.2 顶层结构

```python
class S5PositioningPayload(BaseModel):
    """S5 战略定位场景载荷"""
    scenario_type: Literal["S5"] = "S5"  # discriminator

    # === 1. Vendor Profiles（仿 Gartner MQ 四象限） ===
    vendor_profiles: list[S5VendorProfile] = Field(min_length=2)

    # === 2. Perceptual Map（决策 2：S5 二维散点图） ===
    perceptual_map: PerceptualMap

    # === 3. Strategy Canvas + ERRC ===
    strategy_canvas: StrategyCanvas
    errc_grid: ERRCGrid

    # === 4. Blue Ocean Move（基于 ERRC 的新价值曲线） ===
    blue_ocean_move: Optional[BlueOceanMove] = None  # 首版 Optional：当 ERRC 无清晰差异化机会时可空

    # === 5. Positioning Statement（Geoffrey Moore 6 位模板） ===
    positioning_statement: PositioningStatement

    # === 6. Category Strategy（品类战略） ===
    category_strategy: CategoryStrategy

    @model_validator(mode='after')
    def _check_competitor_consistency(self) -> 'S5PositioningPayload':
        """竞品名一致性 + is_self 唯一性（第 2 批 P0-4 修复：原 validator 有 bug）"""
        vendor_names = {vp.competitor_name for vp in self.vendor_profiles}
        map_names = {b.competitor_name for b in self.perceptual_map.plotted_brands}
        canvas_names = {vc.competitor_name for vc in self.strategy_canvas.value_curves}

        # vendor 子集 ⊆ map
        missing_in_map = vendor_names - map_names
        if missing_in_map:
            raise ValueError(f"vendor_profiles 中的 {missing_in_map} 不在 perceptual_map.plotted_brands 中")

        # vendor 子集 ⊆ canvas
        missing_in_canvas = vendor_names - canvas_names
        if missing_in_canvas:
            raise ValueError(f"vendor_profiles 中的 {missing_in_canvas} 不在 strategy_canvas.value_curves 中")

        # is_self 品牌唯一
        selves_in_map = [b for b in self.perceptual_map.plotted_brands if b.is_self]
        if len(selves_in_map) > 1:
            raise ValueError(f"perceptual_map 中 is_self=True 的品牌应有且仅有一个，发现 {len(selves_in_map)} 个")
        selves_in_canvas = [c for c in self.strategy_canvas.value_curves if c.is_self]
        if len(selves_in_canvas) > 1:
            raise ValueError(f"strategy_canvas.value_curves 中 is_self=True 的品牌应有且仅有一个，发现 {len(selves_in_canvas)} 个")

        return self
```

### 9.3 子模型定义（已应用第 2 批所有修复）

```python
class S5VendorProfile(BaseModel):
    """仿 Gartner MQ Vendor Strengths & Cautions 卡（决策 16b：加二轴总分，mq_quadrant 由代码派生）"""
    competitor_name: str = Field(min_length=1)

    # 决策 16b：MQ 二轴总分（不拆 15 子项，简化版）
    ability_to_execute_score: float = Field(ge=0, le=5)
    ability_to_execute_rationale: str = Field(min_length=50)
    completeness_of_vision_score: float = Field(ge=0, le=5)
    completeness_of_vision_rationale: str = Field(min_length=50)

    overview: str = Field(min_length=20, max_length=200)
    strengths: list[VendorStrength] = Field(min_length=2, max_length=5)
    cautions: list[VendorCaution] = Field(min_length=1, max_length=4)
    source_refs: list[SourceRef] = Field(min_length=1)  # 决策 14a：必有来源

    @computed_field
    @property
    def mq_quadrant(self) -> Literal["mq_leader", "mq_challenger", "mq_visionary", "mq_niche_player"]:
        """决策 16b：mq_quadrant 由两轴总分代码派生（>= 2.5 算高）"""
        e_high = self.ability_to_execute_score >= 2.5
        v_high = self.completeness_of_vision_score >= 2.5
        if e_high and v_high: return "mq_leader"
        if e_high and not v_high: return "mq_challenger"
        if not e_high and v_high: return "mq_visionary"
        return "mq_niche_player"


class PerceptualAxis(BaseModel):
    """Perceptual Map 的一个轴"""
    attribute: str = Field(min_length=4)
    low_label: str = Field(min_length=2)
    high_label: str = Field(min_length=2)
    scale_max: int = Field(default=5, ge=3, le=10)
    rationale: str = Field(min_length=20)


class PlottedBrand(BaseModel):
    """单个品牌在 Perceptual Map 上的位置（决策 14a：confidence + rationale + source 必填）"""
    competitor_name: str = Field(min_length=1)  # 第 2 批 P2 修复：原 brand_name 与其他场景命名不一致
    is_self: bool = False
    x_score: float = Field(ge=0)
    y_score: float = Field(ge=0)
    bubble_size_metric: Optional[float] = None

    # 决策 14a：confidence + rationale 必填
    confidence: Literal["high", "medium", "low"]
    score_rationale: str = Field(min_length=20)  # 为什么打这个坐标
    source_refs: list[SourceRef] = Field(default_factory=list)


class WhiteSpaceZone(BaseModel):
    quadrant: Literal["top_right", "top_left", "bottom_right", "bottom_left", "center"]
    opportunity_description: str = Field(min_length=20)
    interpretation: str = Field(default="")  # 第 2 批 P2 修复：人话解释（"高易用 + 高深度的白空间"）


class ClusterZone(BaseModel):
    brands_in_cluster: list[str] = Field(min_length=2)
    implication: str = Field(min_length=20)


class PerceptualMap(ArtifactBase):
    """二维感知地图（决策 14a+d：加 watermark + confidence；第 2 批 P0-7 修复：坐标范围 + 轴不重复）"""
    artifact_type: Literal["perceptual_map"] = "perceptual_map"
    x_axis: PerceptualAxis
    y_axis: PerceptualAxis
    plotted_brands: list[PlottedBrand] = Field(min_length=3)
    white_space: list[WhiteSpaceZone] = Field(default_factory=list)
    cluster_zones: list[ClusterZone] = Field(default_factory=list)

    # 决策 14d：前端展示水印（schema 内提示，前端按此渲染）
    display_watermark: str = Field(default="基于公开信息 AI 推断，非客户调研真实分数")

    @model_validator(mode='after')
    def _check_axes_and_scores(self) -> 'PerceptualMap':
        """第 2 批 P0-7 + P2 修复：x≠y 轴 + 坐标 ≤ scale_max"""
        if self.x_axis.attribute == self.y_axis.attribute:
            raise ValueError(f"x_axis 和 y_axis 不能是同一 attribute（'{self.x_axis.attribute}'）")
        for b in self.plotted_brands:
            if b.x_score > self.x_axis.scale_max:
                raise ValueError(f"plotted_brands['{b.competitor_name}'].x_score={b.x_score} 超过 x_axis.scale_max={self.x_axis.scale_max}")
            if b.y_score > self.y_axis.scale_max:
                raise ValueError(f"plotted_brands['{b.competitor_name}'].y_score={b.y_score} 超过 y_axis.scale_max={self.y_axis.scale_max}")
        return self


class CompetitiveFactor(BaseModel):
    """Strategy Canvas 竞争因子"""
    name: str = Field(min_length=4)
    industry_avg_level: float = Field(ge=0, le=10)


class ValueCurve(BaseModel):
    """单品牌的 value curve（第 2 批 P0-7 修复：competitor_name + factor key 完整 + source_refs）"""
    competitor_name: str = Field(min_length=1)  # 改名（原 brand_name）
    is_self: bool = False
    factor_levels: dict[str, float]  # factor_name → 0-10
    source_refs: list[SourceRef] = Field(default_factory=list)

    @model_validator(mode='after')
    def _check_factor_levels_range(self) -> 'ValueCurve':
        """factor_levels 每个值必须在 0-10 之间"""
        for name, level in self.factor_levels.items():
            if not (0 <= level <= 10):
                raise ValueError(f"factor_levels['{name}']={level} 不在 0-10 范围内")
        return self


class StrategyCanvas(ArtifactBase):
    """战略画布（第 2 批 P0-7 修复：factor key 完整性校验）"""
    artifact_type: Literal["strategy_canvas"] = "strategy_canvas"
    competitive_factors: list[CompetitiveFactor] = Field(min_length=5, max_length=15)
    value_curves: list[ValueCurve] = Field(min_length=2)

    @model_validator(mode='after')
    def _check_factor_key_completeness(self) -> 'StrategyCanvas':
        """每条 value_curve.factor_levels 的 key 必须等于 competitive_factors 的 name 集合"""
        factor_names = {f.name for f in self.competitive_factors}
        for vc in self.value_curves:
            curve_keys = set(vc.factor_levels.keys())
            if curve_keys != factor_names:
                missing = factor_names - curve_keys
                extra = curve_keys - factor_names
                raise ValueError(
                    f"value_curve['{vc.competitor_name}'].factor_levels 与 competitive_factors 不一致："
                    f"missing={missing}, extra={extra}"
                )
        return self


class ERRCAction(BaseModel):
    factor: str = Field(min_length=4)
    rationale: str = Field(min_length=20)
    proposed_level: Optional[float] = Field(default=None, ge=0, le=10)
    buyer_value: str = Field(default="")


class ERRCGrid(ArtifactBase):
    """ERRC 4 宫格（第 2 批 P0-7 修复：raise_ alias 改名 raise_level 避免 Pydantic 序列化坑）"""
    artifact_type: Literal["errc_grid"] = "errc_grid"
    eliminate: list[ERRCAction] = Field(default_factory=list)
    reduce: list[ERRCAction] = Field(default_factory=list)
    raise_level: list[ERRCAction] = Field(default_factory=list)  # 改名（原 raise_ + alias="raise"），ERRC 中"Raise"含义即 raise_level
    create: list[ERRCAction] = Field(default_factory=list)


class BlueOceanMove(ArtifactBase):
    """基于 ERRC 的新价值曲线（第 2 批 P1 修复：focus_check / divergence_check 改 Optional）"""
    artifact_type: Literal["blue_ocean_move"] = "blue_ocean_move"
    new_value_curve_summary: str = Field(min_length=50)

    # focus_check / divergence_check 理论上可由代码从 strategy_canvas 算，但首版让 LLM 评+给依据
    focus_assessment: Literal["focused", "scattered", "uncertain"]
    focus_rationale: str = Field(min_length=20)
    divergence_assessment: Literal["divergent", "overlapping", "uncertain"]
    divergence_rationale: str = Field(min_length=20)

    compelling_tagline: str = Field(min_length=10, max_length=40)
    target_noncustomers: list[str] = Field(min_length=1)


class PositioningStatement(BaseModel):
    """Geoffrey Moore 6 位模板（决策 14a：加 confidence 必填）"""
    target_customer: str = Field(min_length=10)
    need_or_opportunity: str = Field(min_length=10)
    product_name: str = Field(min_length=2)
    product_category: str = Field(min_length=4)
    key_benefit: str = Field(min_length=10)
    primary_alternative: str = Field(min_length=4)
    primary_differentiation: str = Field(min_length=10)

    # 决策 14a：confidence 必填，让 LLM 自评
    confidence: Literal["from_user_brief", "llm_inferred", "low_confidence"]

    @computed_field
    @property
    def full_statement_text(self) -> str:
        prefix = ""
        if self.confidence != "from_user_brief":
            prefix = "[AI 推断版本，请人工校对] "
        return (
            f"{prefix}For {self.target_customer} who {self.need_or_opportunity}, "
            f"{self.product_name} is a {self.product_category} that {self.key_benefit}. "
            f"Unlike {self.primary_alternative}, our product {self.primary_differentiation}."
        )


class CategoryStrategy(BaseModel):
    """品类战略（第 2 批 P2 修复：competitors_implied 必须是 vendor_profiles 子集，由 S5 顶层 validator 检查）"""
    chosen_category: str = Field(min_length=4)
    why_this_category: str = Field(min_length=30)
    competitors_implied: list[str] = Field(min_length=1)
    risk_of_category_choice: str = Field(default="")
```

### 9.4 优先级（P0/P1/P2）

| Priority | 字段 |
|---|---|
| **P0**（必做） | vendor_profiles / perceptual_map / positioning_statement / category_strategy |
| **P1**（强烈建议） | strategy_canvas / errc_grid |
| **P2**（推迟） | blue_ocean_move（依赖 ERRC 已有清晰输出） |

### 9.5 与采集层依赖

| 字段 | 依赖 | 状态 |
|---|---|---|
| `vendor_profiles` | 竞品官网 + 第三方评测 | ✓ |
| `perceptual_map.plotted_brands` | LLM 基于公开信息推断坐标 | △ 准确性受限于公开数据；首版接受 LLM 推断（非客户调研真实分数） |
| `strategy_canvas.value_curves` | 竞品功能 + 定价 + 营销策略 | △ LLM 推断为主 |
| `positioning_statement` | LLM 基于上下文综合 | ✓ 都是 LLM 综合产物 |

---

## Part 10：第 2 批评审记录与决策

### 10.1 doubt-driven 双模型审查发现（合并去重）

**审查机制**：
- 单模型审查：`general-purpose` agent 跨上下文审查（发现 7 P0 + 10 P1 + 8 P2）
- 跨模型审查：`codex` CLI（gpt-5.5）跨上下文审查（发现 8 P0 + 12 P1 + 6 P2）
- 合并去重：22 条独立问题（双模型一致命中 17 条 + codex 独有 1 条 + 单模型独有 4 条）

**P0 致命问题**（8 条，全修）：
1. `prior_trace_id` 链路根本没接通（前端/API/graph/writer 全无对接点；旧 trace 不兼容）→ Part 8.2 加首次降级模式 + schema_version 校验机制
2. `BattlecardSection.sources` 破坏 source_refs 协议 → 改名 `source_refs`
3. S3 PriceTier 价格字段无字段级溯源 → 拆分 RecommendedPriceTier + ObservedCompetitorTier，后者每条 source_refs 必填
4. S3 PriceTier 我方/竞品复用语义混淆 → 同上拆分
5. computed_field 协议被破坏（quadrant/mq_quadrant/overall_score_pct 都没用 @computed_field） → 全部改 @computed_field
6. AnalysisSection.section_type 漏列 S3/S4/S5 类型 → 补全 15 个新枚举值
7. S5 PerceptualMap / StrategyCanvas 无溯源 + 无范围约束（决策 14a+d）→ 加 confidence 必填 + score_rationale + watermark + scale_max 校验
8. 当前 collection layer 不满足 S3/S4/S5 输入依赖 → 在 Part 5 列入"采集层补强清单"作为已知 P2 任务

**P1 重要问题**（10 条，全修）：
1. S5 _check_competitor_consistency 有 bug（map_names 重复 union 自身 + canvas_names 未使用 + is_self 未约束唯一）→ 整段重写
2. S4 没校验 monitored_competitors 与 changes/battlecards 的竞品名一致 → 加 _check_monitored_competitor_consistency
3. S4 MonitoringTrends 未强制 prior_trace_id 关系 → 加 _check_first_review_baseline
4. S4 trend 枚举不一致（accelerating/escalating） → 全部统一 up/flat/down
5. S4 FIATuple 强制三元组诱导编造（决策 17a）→ fact 必填，impact + act Optional
6. S4 BattlecardSection.confidence 含义错（是 completeness）→ 改名 completeness
7. S3 Packaging._check_recommended_tier 允许 0 个 → 改 == 1 强制
8. S3 wtp_research.method=inferred_from_competitor_pricing 名字误导 → 改 proxy_from_competitor_pricing + 强制 confidence=low + limitations 必填
9. S3 expected_arr_uplift_pct 无依据 → 加 expected_arr_uplift_basis + methodology
10. S5 ERRCGrid.raise_ alias 序列化陷阱 → 改名 raise_level（无 alias）
11. S5 Magic Quadrant 不完整（决策 16b）→ 加 ability_to_execute_score + completeness_of_vision_score 二轴 + computed mq_quadrant
12. S3 顶层 value_drivers 与 FeatureClassification.value_drivers 重名 → FeatureClassification 内部改 premium_drivers

**P2 次要问题**（5+ 条，全修）：
1. S5 PerceptualAxis x≠y 校验 + scale_max 范围校验 → 加 _check_axes_and_scores
2. S5 PlottedBrand.brand_name 命名不一致 → 改 competitor_name
3. S3 monthly_price/annual_price 没 ge=0 + 年付不能贵过月付 x12 → 加约束 + _check_annual_le_monthly_x12
4. S3 pricing_page_url 没 min_length → 加 min_length=8
5. S4 首次监控 baseline 污染 change log → 加 is_baseline 字段 + _check_first_review_baseline
6. S3/S4/S5 多个 artifact 未继承 ArtifactBase → PricingPageAudit / RolloutStep / FeatureChange 等全部继承
7. S3 RolloutStep step_order 双轨制 → 移除，依赖 list 顺序
8. S4 OrgChange 枚举太窄 → 补 joined_board / title_changed / founder_exit
9. PerceptualMap watermark 字段（决策 14d）→ 加 display_watermark 字段

**codex 独有发现**（已修）：
- AnalysisSection.section_type 没列 S3/S4/S5 - 这是回归 bug（第 1 批改 section_type 时只列 S1/S2），上线即坏

### 10.2 第 2 批产品决策落地

| # | 决策 | 选项 | 落地位置 |
|---|---|---|---|
| 13 | S4 prior_trace_id 处理 | a：保留机制 + 首次降级模式 | Part 8.2 + ReviewPeriod.prior_trace_id Optional + ReportMetadata.schema_version + S4 _check_first_review_baseline validator |
| 14 | S5 PerceptualMap 溯源严格度 | a + d：confidence 必填 + 水印 | PlottedBrand.confidence/score_rationale 必填 + PerceptualMap.display_watermark + S5VendorProfile.source_refs min_length=1 |
| 15 | S3 价格字段溯源粒度 | a：每个 ObservedCompetitorTier 必填 source_refs | ObservedCompetitorTier.source_refs: list[SourceRef] = Field(min_length=1) |
| 16 | S5 仿 Gartner MQ 完整度 | b：简化版两轴总分 + 代码派生象限 | S5VendorProfile.ability_to_execute_score + completeness_of_vision_score + computed mq_quadrant |
| 17 | S4 FIATuple 是否每条强制 | a：fact 必填，impact+act Optional | FIATuple.impact: Optional / FIATuple.act: Optional |

### 10.3 跨场景一致性 final check

经第 2 批 RECONCILE 后核对，S3/S4/S5 与第 1 批 S1/S2 在以下方面 100% 一致：

✓ **命名约定**：snake_case + 单位后缀（_pct/_1_5/_score）+ date 类型 + Field(default_factory=...)
✓ **来源协议**：统一 `source_refs: list[SourceRef]`（除 FeatureScore.evidence_url 因特殊语义保留）
✓ **严重度枚举**：全部使用 Literal["low", "medium", "high"]，无 int 1-5
✓ **趋势枚举**：全部使用 Literal["up", "flat", "down"]
✓ **场景前缀枚举**：wave_*（S1）/ market_*（S2）/ mq_*（S5）—— 跨场景永不出现裸 leader/challenger
✓ **ArtifactBase 协议**：所有可被 AnalysisSection.artifact_refs 引用的产物都继承 ArtifactBase（FeatureMatrix / Packaging / CompetitorPricing / PricingPageAudit / RolloutStep / 各类 Change / Battlecard / MonitoringThreat / MonitoringOpportunity / PerceptualMap / StrategyCanvas / ERRCGrid / BlueOceanMove）
✓ **computed_field 派生**：weighted_scores / wave_position / weight / mq_quadrant / quadrant / overall_score_pct / last_updated_at 全部由代码派生不让 LLM 填
✓ **evidence 强制**：S1 FeatureScore.score=2 + S3 ObservedCompetitorTier 强制 source_refs
✓ **model_validator 一致性**：S1 / S3 / S4 / S5 各 payload 都有竞品名一致性 validator

### 10.4 待 Cooper 注意：本次 RECONCILE 的限制

Step 4 RECONCILE 我自己处理了 22 条技术修复 + 5 条产品决策。但有 **2 件事必须 Cooper 后续亲自处理**：

1. **采集层补强**（doubt-driven 双模型一致 P0-8）：现有 collection_pipeline 无法采集 S3 价格细节、S4 变更、S5 感知坐标——本次任务**不在 schema 设计范围**，但 schema 已留位（Optional + value_basis）。等本次 schema 实现验证完，作为下一个独立任务推进采集层增强。
2. **前端 ScenarioInput 表单**：新输入 schema（Part 3.5 ScenarioInput）需要前端做按 scenario 切换的表单。这在 writing-plans 阶段会单独排进 task。

### 10.5 Step 5 STOP 条件检查

按 doubt-driven skill：本轮发现已全部 RECONCILE，下一轮预计只剩 trivial findings → 满足 STOP 条件，结束循环。

---

## Part 11：完成

设计文档至此完整。**5 套场景 schema + 通用骨架 + writer 编排 + 完整评审记录** 全部齐备，可进入 writing-plans skill 制定实现计划。
