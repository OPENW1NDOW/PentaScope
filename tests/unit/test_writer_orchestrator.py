"""WriterOrchestrator C1 单测：骨架 + Phase 1 outline。

覆盖 5 项：
1. collect_profile_urls 收集 3 个来源 URL
2. write 全无 URL 时 raise（含 "回 collector"）
3. _llm_call_with_quota 超 18 次熔断 raise
4. _call_with_validation 校验失败重试一次后成功（共调 2 次）
5. _serialize_validation_error 输出 ≤ 1500 字符
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from pydantic import BaseModel, Field, ValidationError

from src.agents.writer_orchestrator import WriterOrchestrator, collect_profile_urls
from src.schemas.profile import (
    BasicInfo,
    Classification,
    CompetitorProfile,
    ProfileMetadata,
    RecentUpdate,
    SampleReview,
    UserReviews,
)
from src.tools.llm_client import LLMClient


def _make_profile(
    *,
    data_sources: list[str] | None = None,
    recent_urls: list[str] | None = None,
    review_urls: list[str] | None = None,
    name: str = "竞品A",
) -> CompetitorProfile:
    """构造最小合法 CompetitorProfile，3 个来源可分别注入 URL（默认空列表）。"""
    data_sources = data_sources if data_sources is not None else []
    recent_urls = recent_urls if recent_urls is not None else []
    review_urls = review_urls if review_urls is not None else []
    return CompetitorProfile(
        classification=Classification(competitor_type="核心竞品", reason="测试"),
        basic_info=BasicInfo(name=name),
        recent_updates=[
            RecentUpdate(date="2026-01-01", title=f"更新 {i}", source_url=u)
            for i, u in enumerate(recent_urls)
        ],
        user_reviews=UserReviews(
            sample_reviews=[
                SampleReview(content=f"评论 {i}", rating=4, source_url=u)
                for i, u in enumerate(review_urls)
            ]
        ),
        metadata=ProfileMetadata(
            collected_at="2026-06-08T00:00:00",
            data_sources=data_sources,
            completeness_score=0.8,
        ),
    )


# ---------- 测试 1：collect_profile_urls ----------

def test_collect_profile_urls_three_sources():
    """构造一个 CompetitorProfile，验证 3 个来源的 URL 都被收集。"""
    profile = _make_profile(
        data_sources=["https://meta.example.com/a", "https://meta.example.com/b", ""],
        recent_urls=["https://news.example.com/x"],
        review_urls=["https://review.example.com/y"],
    )
    urls = collect_profile_urls(profile)
    assert urls == {
        "https://meta.example.com/a",
        "https://meta.example.com/b",
        "https://news.example.com/x",
        "https://review.example.com/y",
    }


# ---------- 测试 2：write 全无 URL 时 raise ----------

@pytest.mark.asyncio
async def test_write_raises_when_no_discovered_urls():
    """profiles 列表非空但 3 个来源都无 url → write 抛 RuntimeError 含 '回 collector'。"""
    profile = _make_profile(data_sources=[], recent_urls=[], review_urls=[])
    mock_llm = MagicMock(spec=LLMClient)
    mock_llm.call_json = AsyncMock(return_value={})
    orch = WriterOrchestrator(llm=mock_llm)

    # 构造最小 ScenarioInput
    from src.schemas.input import CompetitorBasic, ScenarioInput
    scenario_input = ScenarioInput(
        scenario="S1",
        competitors=[CompetitorBasic(name="竞品A")],
        analysis_context="测试上下文",
        our_product_name="我方产品",
        our_product_brief="测试简介",
    )
    with pytest.raises(RuntimeError, match="回 collector"):
        await orch.write(
            scenario_input=scenario_input,
            analysis=MagicMock(),
            profiles=[profile],
        )


# ---------- 测试 3：调用次数熔断 ----------

@pytest.mark.asyncio
async def test_llm_quota_breached_raises():
    """连续调用 19 次 _llm_call_with_quota（mock LLM 返回任意 dict），第 19 次抛 RuntimeError。"""
    mock_llm = MagicMock(spec=LLMClient)
    mock_llm.call_json = AsyncMock(return_value={"ok": 1})
    orch = WriterOrchestrator(llm=mock_llm)

    # 前 18 次正常
    for _ in range(18):
        result = await orch._llm_call_with_quota("sys", "user")
        assert result == {"ok": 1}

    # 第 19 次（_call_counter 升到 19，> 18）触发熔断
    with pytest.raises(RuntimeError, match="LLM 调用超限"):
        await orch._llm_call_with_quota("sys", "user")


# ---------- 测试 4：_call_with_validation 重试 ----------

class _DummySchema(BaseModel):
    field: str = Field(min_length=5)


@pytest.mark.asyncio
async def test_call_with_validation_retries_on_validation_error():
    """第 1 次返回 {} → ValidationError；第 2 次返回 {field:"valid"} → 成功。LLM 共调 2 次。"""
    mock_llm = MagicMock(spec=LLMClient)
    mock_llm.call_json = AsyncMock(side_effect=[{}, {"field": "valid_value"}])
    orch = WriterOrchestrator(llm=mock_llm)

    result = await orch._call_with_validation(
        "sys", "user", _DummySchema, max_retries=1
    )
    assert isinstance(result, _DummySchema)
    assert result.field == "valid_value"
    assert mock_llm.call_json.call_count == 2

    # [I2] 验证第 2 次调用的 user_prompt 含错误回灌（防误改回灌逻辑而测试无感）
    second_call_args = mock_llm.call_json.call_args_list[1]
    second_user_prompt = (
        second_call_args.args[1]
        if len(second_call_args.args) >= 2
        else second_call_args.kwargs.get("user_prompt", "")
    )
    assert "上次校验失败" in second_user_prompt


# ---------- 测试 5：_serialize_validation_error 长度 ----------

class _NestedItem(BaseModel):
    a: str = Field(min_length=1)
    b: str = Field(min_length=1)
    c: str = Field(min_length=1)


class _Big(BaseModel):
    items: list[_NestedItem]


def test_serialize_validation_error_under_1500_chars():
    """构造 ≥10 个 error 的 ValidationError，验证序列化结果 ≤ 1500 字符。"""
    try:
        # 5 个空 _NestedItem，每个缺 a/b/c 三字段 → 15 个 error
        _Big(items=[{} for _ in range(5)])
    except ValidationError as e:
        assert len(e.errors()) >= 10
        text = WriterOrchestrator._serialize_validation_error(e, max_chars=1500)
        assert len(text) <= 1500
    else:
        pytest.fail("应抛 ValidationError")


# ---------- Phase 2 测试 fixture ----------

def _s1_payload_dict_with_weighted_scores() -> dict:
    """构造一个 LLM "返回"的最小合法 S1 payload dict，故意带 LLM 误填的 weighted_scores。

    对应 tests/unit/test_schemas_s1.py 的 _ok_xxx 风格，所有竞品名一致，evidence_url 可被 normalize。
    """
    discovered = "https://a.example.com/feature"
    return {
        "scenario_type": "S1",
        "vendor_profiles": [
            {
                "competitor_name": "A",
                "wave_position": "wave_leader",
                "one_line_pitch": "A 的一句话定位描述足够长",
                "strengths": [
                    {"point": "某项核心优势描述至少十字", "evidence": "官网功能页有详细的截图说明"},
                    {"point": "另一项核心优势描述十字", "evidence": "官网功能页有详细的截图说明"},
                ],
                "cautions": [
                    {"point": "某项需注意点描述至少十字", "evidence": "用户论坛有大量差评汇总记录"},
                ],
                "best_fit_for": "中小团队场景适配最好",
            },
            {
                "competitor_name": "B",
                "wave_position": "wave_contender",
                "one_line_pitch": "B 的一句话定位描述足够长",
                "strengths": [
                    {"point": "某项核心优势描述至少十字", "evidence": "官网功能页有详细的截图说明"},
                    {"point": "另一项核心优势描述十字", "evidence": "官网功能页有详细的截图说明"},
                ],
                "cautions": [
                    {"point": "某项需注意点描述至少十字", "evidence": "用户论坛有大量差评汇总记录"},
                ],
                "best_fit_for": "中小团队场景适配最好",
            },
        ],
        "feature_matrix": {
            "artifact_id": "s1-fm",
            "competitors": ["A", "B", "我方"],
            "our_product_name": "我方",
            "categories": [
                {
                    "name": "核心",
                    "tier": 1,
                    "features": [
                        {
                            "name": "f1",
                            "scores": {
                                "A": {"score": 2, "evidence_url": discovered},
                                "B": {"score": 1},
                                "我方": {"score": 1},
                            },
                        }
                    ],
                }
            ],
            # LLM 误填的 computed_field（normalize 应删掉）
            "weighted_scores": {"A": 999.9, "B": 0.1, "我方": 0.0},
        },
        "radar_scores": [
            {
                "artifact_id": "r-A",
                "competitor_name": "A",
                "feature_breadth": 4, "usability": 4, "cost_effectiveness": 4,
                "stability": 4, "design_quality": 4,
            },
            {
                "artifact_id": "r-B",
                "competitor_name": "B",
                "feature_breadth": 3, "usability": 3, "cost_effectiveness": 3,
                "stability": 3, "design_quality": 3,
            },
        ],
        "job_statement": {
            "situation": "跨部门协作场景下处理文档",
            "motivation": "希望减少沟通成本提升效率",
            "outcome": "最终减少跨部门同步会议次数",
        },
        "feature_gaps": [
            {
                "feature_name": "移动端",
                "competitors_have_it": ["A"],
                "underserved_outcome": "出差场景下无法编辑文档",
                "estimated_effort": "medium",
                "estimated_impact": "high",
                "recommendation": "build",
            }
        ],
        "roadmap_recommendations": {
            "must_build": ["移动端"],
            "rationale_summary": "必须补移动端，理由如下" * 5,
        },
    }


# ---------- 测试 6：Phase 2 normalize 删 computed_field ----------

def test_phase2_normalize_drops_computed_field():
    """LLM 误填 weighted_scores → normalize 删除 → S1 payload 实例化成功。"""
    from src.schemas.scenarios.s1 import S1FeatureIterationPayload

    from src.schemas.input import CompetitorBasic, ScenarioInput

    mock_llm = MagicMock(spec=LLMClient)
    mock_llm.call_json = AsyncMock(return_value={})
    orch = WriterOrchestrator(llm=mock_llm)

    payload_dict = _s1_payload_dict_with_weighted_scores()
    scenario_input = ScenarioInput(
        scenario="S1",
        competitors=[CompetitorBasic(name="竞品A"), CompetitorBasic(name="竞品B")],
        analysis_context="测试上下文",
        our_product_name="我方",
    )
    warnings: list[str] = []
    payload_model = orch._build_payload_model(
        "S1",
        payload_dict,
        discovered_urls=["https://a.example.com/feature"],
        competitor_recommendations=None,
        prior_report_data=None,
        scenario_input=scenario_input,
        warnings=warnings,
    )
    assert isinstance(payload_model, S1FeatureIterationPayload)
    # weighted_scores 是 computed_field，重算后不应是 LLM 误填的 999.9
    assert payload_model.feature_matrix.weighted_scores["A"] != 999.9


# ---------- 测试 7：Phase 2 S2 recommender 强制覆盖 ----------

def test_phase2_s2_recommender_force_override(monkeypatch):
    """[v3-R10] LLM 改写 competitor_recommendations，_build_payload_model 强制覆盖回 input recommender。

    通过 monkey-patch _PAYLOAD_CLASSES["S2"] 为一个最小 BaseModel（仅接收 competitor_recommendations 字段），
    避免构造完整 S2MarketEntryPayload fixture（market_sizing/five_forces/players 等子 schema 太复杂）。
    """
    from src.schemas.scenarios.s2 import (
        CompetitorRecommendations, RecommendedCompetitor,
    )
    from src.schemas.input import ScenarioInput
    from src.agents import writer_orchestrator as wo

    mock_llm = MagicMock(spec=LLMClient)
    mock_llm.call_json = AsyncMock(return_value={})
    orch = WriterOrchestrator(llm=mock_llm)

    # 输入 recommender（原始数据，用户/recommender 真实产出）
    input_recommender = CompetitorRecommendations(
        user_provided_industry="协作工具",
        user_provided_competitors=["A"],
        recommended_competitors=[
            RecommendedCompetitor(
                name=f"R{i}",
                why_recommended="测试理由不少于十字符",
                confidence="high",
            )
            for i in range(3)
        ],
        selection_method="hybrid",
        selection_rationale="测试推荐理由不少于三十字符的描述内容来满足该字段最低长度约束的硬性要求",
    )

    # 临时把 S2 schema 替换成只接收 competitor_recommendations 字段的最小 BaseModel
    class _FakeS2Payload(BaseModel):
        competitor_recommendations: dict
        # Pydantic v2 默认拒绝 extra；显式 ignore 让 normalize 后的其他字段不报错
        model_config = {"extra": "ignore"}

    monkeypatch.setitem(wo._PAYLOAD_CLASSES, "S2", _FakeS2Payload)

    # LLM 返回的 payload 中 competitor_recommendations 被 LLM 改写
    llm_payload = {
        "competitor_recommendations": {
            "user_provided_industry": "被LLM改写的行业",
            "user_provided_competitors": [],
            "recommended_competitors": [],
            "selection_method": "llm_inference",
            "selection_rationale": "被LLM改写后的理由不少于三十字符以满足约束",
        },
    }

    scenario_input = ScenarioInput(
        scenario="S2",
        industry="协作工具",
        analysis_context="测试上下文",
    )
    warnings: list[str] = []
    payload_model = orch._build_payload_model(
        "S2",
        llm_payload,
        discovered_urls=[],
        competitor_recommendations=input_recommender,
        prior_report_data=None,
        scenario_input=scenario_input,
        warnings=warnings,
    )

    # competitor_recommendations 应被代码强制覆盖回 input recommender，不是 LLM 改写后的值
    assert payload_model.competitor_recommendations["user_provided_industry"] == "协作工具"
    assert payload_model.competitor_recommendations["user_provided_industry"] != "被LLM改写的行业"
    assert len(payload_model.competitor_recommendations["recommended_competitors"]) == 3


# ---------- 测试 8：Phase 2 S4 prior diff 注入 ----------

def test_phase2_s4_prior_diff_injects_newly_added_dropped():
    """[v3-R09] prior monitored=[A,B], current=[A,C] → newly_added=[C], dropped=[B], prior_trace_id 被注入。"""
    from src.schemas.input import CompetitorBasic, ScenarioInput

    mock_llm = MagicMock(spec=LLMClient)
    mock_llm.call_json = AsyncMock(return_value={})
    orch = WriterOrchestrator(llm=mock_llm)

    payload_dict = {
        "review_period": {
            "monitored_competitors": ["A", "C"],
        }
    }
    prior_report_data = {
        "metadata": {"scenario": "S4", "schema_version": "2.0"},
        "scenario_payload": {
            "review_period": {"monitored_competitors": ["A", "B"]}
        },
    }
    scenario_input = ScenarioInput(
        scenario="S4",
        prior_trace_id="abc123",
        competitors=[CompetitorBasic(name="竞品A"), CompetitorBasic(name="竞品C")],
        analysis_context="测试上下文",
        our_product_name="我方产品",
    )

    result = orch._inject_s4_prior_diff(payload_dict, prior_report_data, scenario_input)

    assert result["review_period"]["newly_added_competitors"] == ["C"]
    assert result["review_period"]["dropped_competitors"] == ["B"]
    assert result["review_period"]["prior_trace_id"] == "abc123"


# ---------- 测试 9：C1 修复——prior_report_data=None 时不注入 prior_trace_id ----------

def test_phase2_s4_prior_data_none_does_not_inject_trace_id():
    """C1 修复：prior_report_data=None（builder 读盘失败）→ 不注入 prior_trace_id。

    避免「prior_trace_id 已写但 newly/dropped 没算」造成的伪溯源
    （schema validator 用 prior_trace_id is None 判定首次模式）。
    """
    from src.schemas.input import CompetitorBasic, ScenarioInput

    mock_llm = MagicMock(spec=LLMClient)
    mock_llm.call_json = AsyncMock(return_value={})
    orch = WriterOrchestrator(llm=mock_llm)

    scenario_input = ScenarioInput(
        scenario="S4",
        prior_trace_id="abc123",
        competitors=[CompetitorBasic(name="AA")],
        analysis_context="测试上下文",
        our_product_name="MyProduct",
    )
    payload_dict = {"review_period": {"monitored_competitors": ["AA", "CC"]}}
    result = orch._inject_s4_prior_diff(payload_dict, None, scenario_input)

    # 不写 prior_trace_id（prior 缺失时 schema 走首次模式）
    assert result["review_period"].get("prior_trace_id") is None
    assert "newly_added_competitors" not in result["review_period"]
    assert "dropped_competitors" not in result["review_period"]


# ---------- 测试 10：C1 修复——prior schema 不匹配时不注入 prior_trace_id ----------

def test_phase2_s4_prior_schema_mismatch_does_not_inject_trace_id():
    """C1 修复：prior 报告 scenario/schema_version 不匹配 → logger.warning 降级且不注入 prior_trace_id。"""
    from src.schemas.input import CompetitorBasic, ScenarioInput

    mock_llm = MagicMock(spec=LLMClient)
    mock_llm.call_json = AsyncMock(return_value={})
    orch = WriterOrchestrator(llm=mock_llm)

    scenario_input = ScenarioInput(
        scenario="S4",
        prior_trace_id="abc123",
        competitors=[CompetitorBasic(name="AA")],
        analysis_context="测试上下文",
        our_product_name="MyProduct",
    )
    payload_dict = {"review_period": {"monitored_competitors": ["AA", "CC"]}}
    # prior 报告是 S2（不是 S4），schema_version 是 1.0（不是 2.0）—— 两种降级触发条件
    bad_prior = {
        "metadata": {"scenario": "S2", "schema_version": "1.0"},
        "scenario_payload": {"review_period": {"monitored_competitors": ["AA", "BB"]}},
    }
    result = orch._inject_s4_prior_diff(payload_dict, bad_prior, scenario_input)

    assert result["review_period"].get("prior_trace_id") is None
    assert "newly_added_competitors" not in result["review_period"]
    assert "dropped_competitors" not in result["review_period"]


# ---------- 测试 11：I2——Phase 2 ValidationError 重试后仍失败抛出 ----------

@pytest.mark.asyncio
async def test_phase2_validation_error_propagates_after_retry():
    """[v3-R02] LLM 两次都返回非法 phase 2 dict → phase 2 retry 仍失败 → ValidationError 抛出。

    给 graph builder.writer_node 外层捕获转 RejectionFeedback。
    """
    from src.schemas.input import CompetitorBasic, ScenarioInput

    mock_llm = MagicMock(spec=LLMClient)
    # 序列：phase 1 outline 一次（任意 dict）+ phase 2 两次（都非法）
    mock_llm.call_json = AsyncMock(side_effect=[
        {"title": "ok"},  # phase 1 outline（不实例化 schema，任意 dict 即可）
        {"scenario_type": "S1"},  # phase 2 第 1 次：严重漏字段（vendor_profiles 等）
        {"scenario_type": "S1"},  # phase 2 第 2 次：仍漏
    ])
    orch = WriterOrchestrator(llm=mock_llm)
    profile = _make_profile(data_sources=["https://example.com"])
    scenario_input = ScenarioInput(
        scenario="S1",
        competitors=[CompetitorBasic(name="AA")],
        analysis_context="测试",
        our_product_name="MyProduct",
    )
    # 用 MagicMock 即可，反正只走 phase 1 + phase 2 的 LLM 调用，不到 phase 4
    analysis = MagicMock()
    analysis.model_dump_json = MagicMock(return_value="{}")

    with pytest.raises(ValidationError):
        await orch.write(
            scenario_input=scenario_input,
            analysis=analysis,
            profiles=[profile],
        )
    # 验证 phase 2 真的被调了 2 次（重试 1 次后仍失败）
    # phase 1 占 1 次 + phase 2 重试 2 次 = 3 次 LLM call
    assert mock_llm.call_json.call_count == 3
