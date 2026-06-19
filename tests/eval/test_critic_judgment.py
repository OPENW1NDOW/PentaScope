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


def make_report_all_placeholder():
    """全章节 placeholder 的报告 — 期望 specificity ≤ 2。

    所有 narrative 都是模板化占位文本，无具体数据。
    """
    from src.schemas.report import (
        BaseReport, ExecutiveSummary, ReportScope, Methodology,
        Finding, AnalysisSection, Recommendation, Swot, SwotEntry,
    )
    from src.schemas.scenarios.s1 import S1FeatureIterationPayload

    return BaseReport(
        metadata=_make_minimal_metadata("S1"),
        title="竞品分析报告占位版本",
        at_a_glance=["占位要点一", "占位要点二", "占位要点三"],
        executive_summary=ExecutiveSummary(
            context="本报告对相关竞品进行了分析，覆盖了多个维度，旨在提供全面的竞争情报支持。" * 2,
            core_thesis="通过对比分析发现各竞品在功能和定位上存在差异，需要进一步深入调研以形成明确结论。",
            key_findings_brief=["竞品功能丰富", "市场格局复杂", "用户需求多样"],
            implications="综合以上分析，建议团队持续关注竞品动态，结合自身优势制定差异化策略，以在竞争中占据有利位置。" * 2,
            path_forward=["持续关注竞品动态", "加强产品差异化建设"],
        ),
        background="本报告旨在分析相关竞品的竞争态势，通过多维度对比为产品决策提供参考依据。" * 5,
        scope=ReportScope(competitors=["竞品A", "竞品B"], time_window="2025-2026"),
        methodology=Methodology(
            data_collection_approach="通过公开渠道收集竞品信息，包括官方网站、行业报告、用户评价等多维度数据源。" * 5,
            evaluation_criteria=["功能完整度", "用户体验", "市场表现"],
            limitations=["数据来源有限", "可能存在时效性偏差"],
            sample_size_note="本次分析覆盖了多个竞品的核心功能模块和用户反馈数据，样本量满足基本分析需求。",
        ),
        key_findings=[
            Finding(
                statement="竞品在核心功能上各有侧重，整体竞争格局较为分散",
                evidence="通过对比分析发现各竞品在功能覆盖度和用户评价方面表现不一",
                implication="建议根据目标用户需求选择差异化功能方向进行重点投入",
            ),
            Finding(
                statement="市场价格区间跨度较大，定价策略差异明显",
                evidence="各竞品定价从免费到企业版不等，反映了不同的商业模式选择",
                implication="定价策略需结合目标市场和产品定位综合考量",
            ),
            Finding(
                statement="用户对产品易用性和稳定性要求较高",
                evidence="从用户评价数据中可以观察到对核心体验的重视",
                implication="产品打磨应聚焦核心场景的流畅度和可靠性",
            ),
        ],
        analysis_sections=[
            AnalysisSection(
                section_id="overview",
                heading="市场概览分析",
                narrative="本章节对市场整体竞争态势进行了全面分析。从市场规模来看，行业整体呈增长趋势，各竞品在不同细分领域各有优势。综合来看，市场仍存在较大的创新空间和机会。" * 3,
                section_type="overview",
            ),
            AnalysisSection(
                section_id="feature",
                heading="功能对比分析",
                narrative="在功能维度上，各竞品覆盖了基础功能模块，但在深度和广度上存在差异。部分竞品在特定功能上表现突出，而整体功能完整度参差不齐。" * 3,
                section_type="feature_matrix_analysis",
            ),
            AnalysisSection(
                section_id="vendor",
                heading="竞品画像分析",
                narrative="各竞品在目标用户定位、核心场景和价值主张上呈现出不同策略。头部竞品注重品牌和生态建设，新兴竞品则聚焦细分场景的深度打磨。" * 3,
                section_type="vendor_profile_analysis",
            ),
            AnalysisSection(
                section_id="conclusions",
                heading="综合结论",
                narrative="综合以上分析，市场呈现多元化竞争态势。各竞品在不同维度上各有优势，建议结合自身资源和目标市场特点制定差异化竞争策略。" * 3,
                section_type="conclusions_summary",
            ),
        ],
        swot=Swot(
            strengths=[SwotEntry(point="产品功能覆盖较全面", evidence="在核心功能模块上具备基本竞争力", dimension="feature")],
            weaknesses=[SwotEntry(point="品牌知名度有待提升", evidence="市场认知度相对有限", dimension="marketing")],
            opportunities=[SwotEntry(point="市场增长空间较大", evidence="行业整体呈上升趋势", dimension="market")],
            threats=[SwotEntry(point="竞品持续迭代升级", evidence="头部竞品不断推出新功能", dimension="competitive")],
        ),
        conclusions="综合以上多维度分析，市场呈现多元化竞争格局。建议团队结合自身优势和市场机会，制定差异化的产品和市场策略。" * 3,
        recommendations=[
            Recommendation(action="加强核心功能打磨，提升用户体验", target_role="产品经理", priority="important", timeline="short_term", rationale="核心功能是用户留存的关键因素"),
            Recommendation(action="拓展市场渠道，提升品牌认知", target_role="市场负责人", priority="important", timeline="short_term", rationale="品牌建设需要持续投入"),
            Recommendation(action="关注竞品动态，及时调整策略", target_role="战略负责人", priority="consider", timeline="long_term", rationale="市场变化需要持续跟踪"),
        ],
        scenario_payload=S1FeatureIterationPayload(
            vendor_profiles=[],
            feature_matrix=[],
            radar_scores=[],
            job_to_be_done={"jobs": [], "summary": "占位"},
            roadmap=[],
        ),
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
    report.recommendations = [
        type(rec)(**{**rec.model_dump(), "action": "加强 AI 能力建设", "rationale": "AI 是趋势"})
        for rec in report.recommendations
    ]
    # 简化所有 action 和 rationale
    vague = [
        ("加强 AI 能力建设", "AI 是未来方向"),
        ("持续关注市场动态", "市场变化快"),
        ("优化产品体验", "体验是核心竞争力"),
    ]
    from src.schemas.report import Recommendation
    report.recommendations = [
        Recommendation(action=a, target_role="团队", priority="consider", timeline="long_term", rationale=r)
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
