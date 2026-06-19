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
from datetime import date

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


def _make_minimal_metadata(scenario="S1"):
    """构造最小合法 ReportMetadata。"""
    from src.schemas.report import ReportMetadata
    from src.schemas.common import DataSource
    return ReportMetadata(
        report_id="eval-test",
        trace_id="eval-trace",
        scenario=scenario,
        publication_date=date.today(),
        confidence_level="medium",
        data_sources=[DataSource(url="https://example.com", title="test", source_type="other")],
    )


def _ph(base: str, n: int) -> str:
    """生成 ≥n 字符的占位文本（重复 base 直到够长）。"""
    while len(base) < n:
        base += "，" + base[:min(len(base), n - len(base))]
    return base[:max(n, len(base))]


def _make_swot_entry(point, evidence):
    from src.schemas.report import SwotEntry
    return SwotEntry.model_construct(point=point, evidence=evidence, dimension="overall", source_refs=[])

def _make_finding(statement, evidence, implication):
    from src.schemas.report import Finding
    return Finding.model_construct(statement=statement, evidence=evidence, implication=implication, source_refs=[])

def _make_section(sid, heading, narrative, section_type):
    from src.schemas.report import AnalysisSection
    return AnalysisSection.model_construct(section_id=sid, heading=heading, narrative=narrative, section_type=section_type, artifact_refs=[], source_refs=[])

def _make_recommendation(action, target_role, priority, timeline, rationale):
    from src.schemas.report import Recommendation
    return Recommendation.model_construct(action=action, target_role=target_role, priority=priority, timeline=timeline, rationale=rationale, source_refs=[])

def _make_scope(competitors):
    from src.schemas.report import ReportScope
    return ReportScope.model_construct(competitors=competitors, time_window="2025-2026", regions=[], exclusions=[])

def _make_methodology():
    from src.schemas.report import Methodology
    return Methodology.model_construct(
        data_collection_approach="占位数据收集方法",
        evaluation_criteria=["功能完整度", "用户体验", "市场表现"],
        limitations=["数据来源有限", "可能存在时效性偏差"],
        sample_size_note="占位样本说明",
        analyst_disclosure="AI 竞品分析系统",
    )

def _make_exec_summary():
    from src.schemas.report import ExecutiveSummary
    return ExecutiveSummary.model_construct(
        context="占位背景",
        core_thesis="占位核心论点",
        key_findings_brief=["占位发现一", "占位发现二", "占位发现三"],
        implications="占位启示",
        path_forward=["占位路径一", "占位路径二"],
    )


def make_report_all_placeholder():
    """全章节 placeholder 的报告 — 期望 specificity ≤ 2。

    使用 model_construct() 绕过 Pydantic min_length 验证，
    因为 eval 测试只需要报告内容给 critic 评分，不需要严格 schema 校验。
    """
    from src.schemas.report import BaseReport, Swot

    return BaseReport.model_construct(
        metadata=_make_minimal_metadata("S1"),
        title="竞品分析报告占位版本",
        at_a_glance=["占位要点一", "占位要点二", "占位要点三"],
        executive_summary=_make_exec_summary(),
        background="本报告旨在分析相关竞品的竞争态势。",
        scope=_make_scope(["竞品A", "竞品B"]),
        methodology=_make_methodology(),
        key_findings=[
            _make_finding("竞品在核心功能上各有侧重", "通过对比分析发现各竞品表现不一", "建议选择差异化功能方向"),
            _make_finding("市场价格区间跨度较大", "各竞品定价从免费到企业版不等", "定价策略需综合考量"),
            _make_finding("用户对产品易用性和稳定性要求较高", "从用户评价数据中可以观察到", "产品打磨应聚焦核心场景"),
        ],
        analysis_sections=[
            _make_section("overview", "市场概览分析", "本章节对市场整体竞争态势进行了全面分析。行业整体呈增长趋势，各竞品在不同细分领域各有优势。市场仍存在较大的创新空间和机会。综合来看，市场格局较为分散。", "overview"),
            _make_section("feature", "功能对比分析", "在功能维度上，各竞品覆盖了基础功能模块，但在深度和广度上存在差异。部分竞品在特定功能上表现突出，而整体功能完整度参差不齐。", "feature_matrix_analysis"),
            _make_section("vendor", "竞品画像分析", "各竞品在目标用户定位、核心场景和价值主张上呈现出不同策略。头部竞品注重品牌和生态建设，新兴竞品则聚焦细分场景的深度打磨。", "vendor_profile_analysis"),
            _make_section("conclusions", "综合结论", "综合以上分析，市场呈现多元化竞争态势。各竞品在不同维度上各有优势，建议结合自身资源和目标市场特点制定差异化竞争策略。", "conclusions_summary"),
        ],
        swot=Swot.model_construct(
            strengths=[_make_swot_entry("产品功能覆盖较全面", "在核心功能模块上具备基本竞争力")],
            weaknesses=[_make_swot_entry("品牌知名度有待提升", "市场认知度相对有限")],
            opportunities=[_make_swot_entry("市场增长空间较大", "行业整体呈上升趋势")],
            threats=[_make_swot_entry("竞品持续迭代升级", "头部竞品不断推出新功能")],
        ),
        conclusions="综合以上多维度分析，市场呈现多元化竞争格局。建议团队结合自身优势和市场机会，制定差异化的产品和市场策略。",
        recommendations=[
            _make_recommendation("加强核心功能打磨", "产品经理", "important", "short_term", "核心功能是用户留存的关键"),
            _make_recommendation("拓展市场渠道", "市场负责人", "important", "short_term", "品牌建设需要持续投入"),
            _make_recommendation("关注竞品动态", "战略负责人", "consider", "long_term", "市场变化需要持续跟踪"),
        ],
        scenario_payload=_make_s1_payload_with_vendors(),
    )


def _make_s1_payload_with_vendors():
    """构造带 vendor_profiles 的 S1 payload（model_construct 绕过验证）。"""
    from src.schemas.scenarios.s1 import S1FeatureIterationPayload, S1VendorProfile

    def _make_vp(name, caution_point):
        vp = S1VendorProfile.model_construct(
            competitor_name=name,
            one_line_pitch=f"{name} 的一句话介绍",
            strengths=[],
            cautions=[type("C", (), {"point": caution_point})()],
            best_fit_for="适合某类用户",
        )
        return vp

    return S1FeatureIterationPayload.model_construct(
        scenario_type="S1",
        vendor_profiles=[
            _make_vp("竞品A", "竞品A 在高级功能上存在不足"),
            _make_vp("竞品B", "竞品B 的定价策略偏高"),
        ],
        feature_matrix=None,
        radar_scores=[],
        job_statement=None,
        feature_gaps=[],
        roadmap_recommendations=None,
    )


def make_report_no_source_refs():
    """所有 finding 无 source_refs — 期望 evidence ≤ 1。"""
    report = make_report_all_placeholder()
    # 清空所有 source_refs
    for finding in report.key_findings:
        finding.source_refs = []
    for section in report.analysis_sections:
        section.source_refs = []
    for entry in report.swot.strengths + report.swot.weaknesses + report.swot.opportunities + report.swot.threats:
        entry.source_refs = []
    # 清空 data_sources
    report.metadata.data_sources = []
    return report


def make_report_third_party_only():
    """所有 source 全是聚合站 — 期望 evidence ≤ 2。"""
    from src.schemas.common import DataSource
    report = make_report_all_placeholder()
    report.metadata.data_sources = [
        DataSource(url="https://upmarket.co/report", title="Market Report", source_type="third_party_review"),
        DataSource(url="https://spyingbee.com/competitor", title="Competitor Analysis", source_type="third_party_review"),
    ]
    return report


def make_report_swot_self_contradiction():
    """SWOT.strengths 说 X 强 + weaknesses 说 X 弱 — 期望 coherence ≤ 2。"""
    report = make_report_all_placeholder()
    report.swot.strengths[0].point = "AI 功能是核心竞争力，技术壁垒高"
    report.swot.strengths[0].evidence = "自研大模型在多项 benchmark 上领先"
    report.swot.weaknesses[0].point = "AI 能力薄弱，与竞品差距明显"
    report.swot.weaknesses[0].evidence = "AI 功能用户满意度低于行业平均"
    return report


def make_report_vague_recommendations():
    """所有 recommendation 是套话 — 期望 actionability ≤ 1。"""
    report = make_report_all_placeholder()
    vague = [
        ("加强 AI 能力建设", "AI 是未来方向"),
        ("持续关注市场动态", "市场变化快"),
        ("优化产品体验", "体验是核心竞争力"),
    ]
    report.recommendations = [
        _make_recommendation(a, "团队", "consider", "long_term", r)
        for a, r in vague
    ]
    return report


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
