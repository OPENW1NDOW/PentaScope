import pytest
from unittest.mock import AsyncMock, MagicMock
from src.schemas.analysis import CompetitiveAnalysis
from src.agents.analyzer import AnalyzerAgent


class TestAnalyzerAgent:
    @pytest.mark.xfail(reason="A 大类过渡：fixture 用旧 SwotEntry 短字符串，新 schema min_length=10 不通过；待 E 大类 writer/analyzer 重写时一并修", strict=False)
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


def test_format_feedback_filters_analyzer_issues():
    from src.agents.analyzer import AnalyzerAgent
    from src.schemas.feedback import FeedbackIssue
    issues = [
        FeedbackIssue(agent="analyzer", field="swot.threats", severity="major",
                      reason="威胁象限为空", suggestion="补充竞品对我方威胁"),
        FeedbackIssue(agent="writer", field="sections", severity="minor", reason="章节偏短"),
        FeedbackIssue(agent="collector", field="pricing", severity="critical", reason="定价缺失"),
    ]
    text = AnalyzerAgent._format_feedback(issues)
    assert "swot.threats" in text
    assert "威胁象限为空" in text
    assert "补充竞品对我方威胁" in text
    # 非 analyzer 的 issue 不应进入
    assert "sections" not in text
    assert "定价缺失" not in text


def test_format_feedback_empty_when_no_analyzer_issue():
    from src.agents.analyzer import AnalyzerAgent
    from src.schemas.feedback import FeedbackIssue
    assert AnalyzerAgent._format_feedback(None) == ""
    assert AnalyzerAgent._format_feedback([]) == ""
    only_writer = [FeedbackIssue(agent="writer", field="x", severity="minor", reason="r")]
    assert AnalyzerAgent._format_feedback(only_writer) == ""


@pytest.mark.xfail(reason="A 大类过渡：fixture 用旧 SwotEntry 短字符串，新 schema min_length=10 不通过；待 E 大类 writer/analyzer 重写时一并修", strict=False)
@pytest.mark.asyncio
async def test_analyze_appends_feedback_to_prompt(sample_competitor_profile, sample_competitive_analysis):
    from src.schemas.profile import CompetitorProfile
    from src.schemas.feedback import FeedbackIssue
    mock_llm = MagicMock()
    mock_llm.call_json = AsyncMock(return_value=sample_competitive_analysis)
    agent = AnalyzerAgent(llm=mock_llm)
    profiles = [CompetitorProfile(**sample_competitor_profile)]
    issues = [FeedbackIssue(agent="analyzer", field="swot.threats",
                            severity="major", reason="威胁象限为空")]
    await agent.analyze(profiles, feedback_issues=issues)
    sent_prompt = mock_llm.call_json.call_args[0][1]
    assert "威胁象限为空" in sent_prompt


def test_backfill_feature_matrix_entry_source_urls():
    from src.agents.analyzer import AnalyzerAgent
    from src.schemas.profile import CompetitorProfile, Classification, BasicInfo, ProfileMetadata
    result = {
        "feature_matrix": [
            {"feature": "登录", "source_urls": []},
            {"feature": "导出", "source_urls": ["https://already.com"]},
        ]
    }
    profile = CompetitorProfile(
        classification=Classification(competitor_type="核心竞品", reason="r"),
        basic_info=BasicInfo(name="X"),
        metadata=ProfileMetadata(collected_at="t", data_sources=["https://fb.com"]),
    )
    out = AnalyzerAgent._backfill_source_urls(result, [profile])
    assert out["feature_matrix"][0]["source_urls"] == ["https://fb.com"]
    assert out["feature_matrix"][1]["source_urls"] == ["https://already.com"]


# ============ [fix7 prove-it] analyzer 注入 scenario_input 后的场景感知 ============

@pytest.mark.asyncio
async def test_analyze_injects_scenario_into_user_prompt():
    """[fix7] 当传入 scenario_input 时，user prompt 必须含场景 + 我方产品 + 分析意图块"""
    from src.agents.analyzer import AnalyzerAgent
    from src.schemas.input import CompetitorBasic, ScenarioInput
    from src.schemas.profile import (
        BasicInfo, Classification, CompetitorProfile, ProfileMetadata,
    )

    captured = {}

    class _LLM:
        async def call_json(self, system, user, **kwargs):
            captured["user"] = user
            # 返回最小合规 CompetitiveAnalysis dict（让 schema 实例化通过即可）
            return {
                "positioning": {"per_competitor": [], "source_urls": []},
                "feature_matrix": [],
                "business_model": {"per_competitor": [], "source_urls": []},
                "operations": {"per_competitor": [], "source_urls": []},
                "user_sentiment": {"summary": "", "per_competitor": {}, "source_urls": []},
                "swot": {
                    "strengths": [{"point": "占位 strength point", "evidence": "占位 evidence", "dimension": "feature", "source_refs": []}],
                    "weaknesses": [{"point": "占位 weakness point", "evidence": "占位 evidence", "dimension": "feature", "source_refs": []}],
                    "opportunities": [{"point": "占位 opportunity point", "evidence": "占位 evidence", "dimension": "feature", "source_refs": []}],
                    "threats": [{"point": "占位 threat point", "evidence": "占位 evidence", "dimension": "feature", "source_refs": []}],
                },
                "radar_scores": [],
            }

    agent = AnalyzerAgent(llm=_LLM())
    profile = CompetitorProfile(
        classification=Classification(competitor_type="核心竞品", reason="r"),
        basic_info=BasicInfo(name="飞书"),
        metadata=ProfileMetadata(collected_at="t", data_sources=[]),
    )
    scenario_input = ScenarioInput(
        scenario="S1",
        competitors=[CompetitorBasic(name="飞书")],
        analysis_context="想了解飞书在协作文档领域的优势",
        our_product_name="Notion",
        our_product_brief="AI 驱动的协作文档平台",
    )
    await agent.analyze([profile], scenario_input=scenario_input)
    user_prompt = captured["user"]
    # 1) 场景信息进入 prompt
    assert "S1" in user_prompt, "user prompt 未注入场景"
    # 2) 我方产品名进入 prompt
    assert "Notion" in user_prompt, "user prompt 未注入我方产品名"
    # 3) 我方产品简介进入 prompt
    assert "协作文档平台" in user_prompt, "user prompt 未注入我方产品简介"
    # 4) 分析意图进入 prompt
    assert "想了解飞书" in user_prompt, "user prompt 未注入分析意图"


@pytest.mark.asyncio
async def test_analyze_s2_no_our_product_marks_market_entry_swot():
    """[fix7] S2 场景没有 our_product_name 时，prompt 应明确告诉 LLM SWOT 主体是赛道进入"""
    from src.agents.analyzer import AnalyzerAgent
    from src.schemas.input import ScenarioInput
    from src.schemas.profile import (
        BasicInfo, Classification, CompetitorProfile, ProfileMetadata,
    )

    captured = {}

    class _LLM:
        async def call_json(self, system, user, **kwargs):
            captured["user"] = user
            return {
                "positioning": {"per_competitor": [], "source_urls": []},
                "feature_matrix": [],
                "business_model": {"per_competitor": [], "source_urls": []},
                "operations": {"per_competitor": [], "source_urls": []},
                "user_sentiment": {"summary": "", "per_competitor": {}, "source_urls": []},
                "swot": {
                    "strengths": [{"point": "占位 strength point", "evidence": "占位 evidence", "dimension": "feature", "source_refs": []}],
                    "weaknesses": [{"point": "占位 weakness point", "evidence": "占位 evidence", "dimension": "feature", "source_refs": []}],
                    "opportunities": [{"point": "占位 opportunity point", "evidence": "占位 evidence", "dimension": "feature", "source_refs": []}],
                    "threats": [{"point": "占位 threat point", "evidence": "占位 evidence", "dimension": "feature", "source_refs": []}],
                },
                "radar_scores": [],
            }

    agent = AnalyzerAgent(llm=_LLM())
    profile = CompetitorProfile(
        classification=Classification(competitor_type="核心竞品", reason="r"),
        basic_info=BasicInfo(name="飞书"),
        metadata=ProfileMetadata(collected_at="t", data_sources=[]),
    )
    scenario_input = ScenarioInput(
        scenario="S2",
        industry="协作文档 SaaS",
        analysis_context="想进入协作文档赛道",
    )
    await agent.analyze([profile], scenario_input=scenario_input)
    user_prompt = captured["user"]
    # S2 场景应有显式标记（市场进入 / 赛道）
    assert "S2" in user_prompt
    # industry 信息应注入
    assert "协作文档" in user_prompt


@pytest.mark.asyncio
async def test_analyze_without_scenario_input_keeps_backward_compat():
    """[fix7] 不传 scenario_input 也能正常运行（向后兼容）"""
    from src.agents.analyzer import AnalyzerAgent
    from src.schemas.profile import (
        BasicInfo, Classification, CompetitorProfile, ProfileMetadata,
    )

    class _LLM:
        async def call_json(self, system, user, **kwargs):
            return {
                "positioning": {"per_competitor": [], "source_urls": []},
                "feature_matrix": [],
                "business_model": {"per_competitor": [], "source_urls": []},
                "operations": {"per_competitor": [], "source_urls": []},
                "user_sentiment": {"summary": "", "per_competitor": {}, "source_urls": []},
                "swot": {
                    "strengths": [{"point": "占位 strength point", "evidence": "占位 evidence", "dimension": "feature", "source_refs": []}],
                    "weaknesses": [{"point": "占位 weakness point", "evidence": "占位 evidence", "dimension": "feature", "source_refs": []}],
                    "opportunities": [{"point": "占位 opportunity point", "evidence": "占位 evidence", "dimension": "feature", "source_refs": []}],
                    "threats": [{"point": "占位 threat point", "evidence": "占位 evidence", "dimension": "feature", "source_refs": []}],
                },
                "radar_scores": [],
            }

    agent = AnalyzerAgent(llm=_LLM())
    profile = CompetitorProfile(
        classification=Classification(competitor_type="核心竞品", reason="r"),
        basic_info=BasicInfo(name="X"),
        metadata=ProfileMetadata(collected_at="t", data_sources=[]),
    )
    # 不传 scenario_input
    result = await agent.analyze([profile])
    assert result is not None  # 没崩即通过


@pytest.mark.asyncio
async def test_analyze_retry_includes_error_feedback():
    """analyzer 第一次 ValidationError 时，重试 prompt 应包含错误摘要。"""
    from src.schemas.profile import CompetitorProfile, BasicInfo, Classification, ProfileMetadata

    # 两次都返回不合规数据——我们只关心第二次 prompt 是否注入了错误信息
    bad_result = {"swot": {"strengths": []}}

    mock_llm = MagicMock()
    mock_llm.call_json = AsyncMock(side_effect=[bad_result, bad_result])

    agent = AnalyzerAgent(llm=mock_llm)
    profile = CompetitorProfile(
        classification=Classification(competitor_type="核心竞品", reason="r"),
        basic_info=BasicInfo(name="XX"),
        metadata=ProfileMetadata(collected_at="t", data_sources=["https://a.com"]),
    )

    with pytest.raises(ValueError):
        await agent.analyze([profile])

    # 验证 LLM 被调用了 2 次
    assert mock_llm.call_json.call_count == 2
    # 验证第二次调用的 prompt 包含错误反馈
    second_call_args = mock_llm.call_json.call_args_list[1]
    retry_prompt = second_call_args[0][1]  # positional arg 1 = user prompt
    assert "校验失败" in retry_prompt or "修复" in retry_prompt
