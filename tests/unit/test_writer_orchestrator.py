"""WriterOrchestrator C1 单测：骨架 + Phase 1 outline。

覆盖 5 项：
1. collect_profile_urls 收集 3 个来源 URL
2. write 全无 URL 时 raise（含 "回 collector"）
3. _llm_call_with_quota 超 18 次熔断 raise
4. _call_with_validation 校验失败重试一次后成功（共调 2 次）
5. _serialize_validation_error 输出 ≤ 1500 字符
"""
import asyncio

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


def _make_valid_outline_dict(title: str = "测试 outline") -> dict:
    """构造能通过 phase 1 即时校验的 outline dict（含合规 executive_summary）。

    [2026-06-18] phase 1 现在对 ExecutiveSummary 做即时 Pydantic 校验，
    mock LLM 返回的 outline 必须含合规 executive_summary 子结构。
    所有字符串重复多次确保超过 schema 最低字符数约束（context ≥80 / core_thesis ≥50 /
    implications ≥100），不要凭语感估字数。
    """
    return {
        "title": title,
        "subtitle": "",
        "at_a_glance": ["关键发现一条", "关键发现二条", "关键发现三条"],
        "executive_summary": {
            "context": "测试场景的行业竞争背景描述，必须达到至少八十字符的长度才能通过 schema 校验。" * 2,
            "core_thesis": "核心判断：测试场景的总论一句话表述要满足五十至一百二十字符约束。" * 2,
            "key_findings_brief": [
                "测试关键发现摘要第一条达到三十字符长度的描述内容。",
                "测试关键发现摘要第二条达到三十字符长度的描述内容。",
            ],
            "implications": "对我方的影响与意义描述要至少有一百个字符的长度才能通过 ExecutiveSummary.implications 字段的最低长度约束，这段文字仅为单元测试用途的占位文本，不代表真实业务洞察。" * 2,
            "path_forward": ["测试下一步行动方向描述"],
        },
    }


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
    # 闸门顺序验证：discovered_urls 空时应在 phase 1 LLM 调用之前 raise
    mock_llm.call_json.assert_not_called()


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


# ---------- 测试 10b：Phase 1 S4 mode_hint 注入 ----------


@pytest.mark.asyncio
async def test_phase1_s4_prior_trace_id_injects_incremental_mode_hint():
    """[v3-R09 prove-it] S4 + prior_trace_id 存在时，Phase 1 user_prompt 应含 '增量监控' 而非 '首次监控'。

    现象：Phase 1 outline prompt 未收到 prior 监控信息，LLM 照抄 analysis_context 里的
    '首次监控' 生成 title，即使这是第二轮增量分析。
    修：_phase1_outline 构建 user_prompt 时注入 mode_hint。
    """
    from src.schemas.input import CompetitorBasic, ScenarioInput

    captured_prompts: list[str] = []

    async def _capture_llm(system_prompt, user_prompt, *, max_tokens=None):
        captured_prompts.append(user_prompt)
        return _make_valid_outline_dict()

    mock_llm = MagicMock(spec=LLMClient)
    mock_llm.call_json = AsyncMock(side_effect=_capture_llm)
    orch = WriterOrchestrator(llm=mock_llm)

    scenario_input = ScenarioInput(
        scenario="S4",
        prior_trace_id="prior-abc-123",
        competitors=[CompetitorBasic(name="Mixpanel")],
        analysis_context="这是首次监控基线",
        our_product_name="MyAnalytics",
    )
    profile = _make_profile(data_sources=["https://example.com"])

    await orch._phase1_outline(
        scenario="S4",
        scenario_input=scenario_input,
        analysis=MagicMock(model_dump_json=MagicMock(return_value="{}")),
        profiles=[profile],
        competitor_names=["Mixpanel"],
        competitor_basics=[{"name": "Mixpanel"}],
        our_product_brief={"name": "MyAnalytics"},
        discovered_urls=["https://example.com"],
    )

    assert len(captured_prompts) == 1
    user_prompt = captured_prompts[0]
    assert "增量监控" in user_prompt, (
        "prior_trace_id=prior-abc-123 时 user_prompt 应含 '增量监控'，实际不含"
    )
    assert "prior-abc-123" in user_prompt, (
        "user_prompt 应包含 prior_trace_id 值，实际不含"
    )


@pytest.mark.asyncio
async def test_phase1_s4_no_prior_trace_id_injects_baseline_mode_hint():
    """[v3-R09 prove-it] S4 + prior_trace_id=None 时，Phase 1 user_prompt 应含 '首次监控'。"""
    from src.schemas.input import CompetitorBasic, ScenarioInput

    captured_prompts: list[str] = []

    async def _capture_llm(system_prompt, user_prompt, *, max_tokens=None):
        captured_prompts.append(user_prompt)
        return _make_valid_outline_dict()

    mock_llm = MagicMock(spec=LLMClient)
    mock_llm.call_json = AsyncMock(side_effect=_capture_llm)
    orch = WriterOrchestrator(llm=mock_llm)

    scenario_input = ScenarioInput(
        scenario="S4",
        prior_trace_id=None,
        competitors=[CompetitorBasic(name="Mixpanel")],
        analysis_context="首次监控",
        our_product_name="MyAnalytics",
    )
    profile = _make_profile(data_sources=["https://example.com"])

    await orch._phase1_outline(
        scenario="S4",
        scenario_input=scenario_input,
        analysis=MagicMock(model_dump_json=MagicMock(return_value="{}")),
        profiles=[profile],
        competitor_names=["Mixpanel"],
        competitor_basics=[{"name": "Mixpanel"}],
        our_product_brief={"name": "MyAnalytics"},
        discovered_urls=["https://example.com"],
    )

    assert len(captured_prompts) == 1
    user_prompt = captured_prompts[0]
    assert "首次监控" in user_prompt, (
        "prior_trace_id=None 时 user_prompt 应含 '首次监控'，实际不含"
    )


# ---------- 测试 11：I2——Phase 2 ValidationError 重试后仍失败抛出 ----------

@pytest.mark.asyncio
async def test_phase2_validation_error_propagates_after_retry():
    """[v3-R02] LLM 两次都返回非法 phase 2 dict → phase 2 retry 仍失败 → ValidationError 抛出。

    给 graph builder.writer_node 外层捕获转 RejectionFeedback。
    """
    from src.schemas.input import CompetitorBasic, ScenarioInput

    mock_llm = MagicMock(spec=LLMClient)
    # 序列：phase 1 outline 一次（任意 dict）+ phase 2 三次（都非法）
    # [fix5] phase 2 max_retries 从 1 提到 2：首次 + 2 次重试 = 3 次
    mock_llm.call_json = AsyncMock(side_effect=[
        _make_valid_outline_dict(),  # phase 1 outline（含合规 executive_summary 通过即时校验）
        {"scenario_type": "S1"},  # phase 2 第 1 次
        {"scenario_type": "S1"},  # phase 2 第 2 次（重试 1）
        {"scenario_type": "S1"},  # phase 2 第 3 次（重试 2）
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
    # phase 1 占 1 次 + phase 2 max_retries=2（首次 + 2 次重试）= 4 次 LLM call
    assert mock_llm.call_json.call_count == 4


@pytest.mark.asyncio
async def test_phase2_default_max_retries_is_2():
    """[fix5 prove-it] _call_phase2_with_validation 默认 max_retries=2，
    给 LLM 多次修字段错位机会（每次只能修一两个字段）。
    """
    import inspect
    sig = inspect.signature(WriterOrchestrator._call_phase2_with_validation)
    default = sig.parameters["max_retries"].default
    assert default == 2, f"phase 2 默认 max_retries 应为 2，当前 {default}"


# ---------- Phase 3 narrative 测试辅助 ----------

def _make_valid_narrative_json(section_type: str, scenario: str = "s1") -> dict:
    """构造一个能通过 AnalysisSection 校验的 narrative dict（narrative ≥300 字）。"""
    return {
        "section_id": f"{scenario}-{section_type[:30]}",
        "heading": f"测试章节-{section_type}",
        "narrative": (
            f"这是 {section_type} 的测试 narrative 文本，"
            "满足 schema 校验所需的最小字符数约束（300 字）。"
            * 8  # 重复 8 次，每次 ~50 字 → ~400 字
        ),
        "section_type": section_type,
        "artifact_refs": [],
        "source_refs": [],
    }


def _make_phase3_full_run_inputs():
    """phase 1 outline + phase 2 payload + phase 3 narrative 全链路的辅助 fixture。

    返回 (orch, scenario_input, analysis, profiles, phase1_dict, phase2_dict)。
    LLM 调用顺序由测试自行 set side_effect。
    """
    from src.schemas.input import CompetitorBasic, ScenarioInput

    profile = _make_profile(data_sources=["https://example.com/a"])
    scenario_input = ScenarioInput(
        scenario="S1",
        competitors=[CompetitorBasic(name="AA"), CompetitorBasic(name="BB")],
        analysis_context="测试上下文",
        our_product_name="我方产品",
    )
    analysis = MagicMock()
    analysis.model_dump_json = MagicMock(return_value="{}")
    return scenario_input, analysis, [profile]


# ---------- 测试 12：phase 3 单 section 失败 → 占位降级 ----------

@pytest.mark.asyncio
async def test_phase3_single_failure_uses_placeholder():
    """单 section LLM 调用失败 + 重试仍失败 → 占位降级 + warnings 加 'placeholder_section:' 前缀。"""
    scenario_input, analysis, profiles = _make_phase3_full_run_inputs()

    phase1_outline = _make_valid_outline_dict("测试 outline")
    phase2_payload = _s1_payload_dict_with_weighted_scores()
    s1_section_types = [
        "overview",
        "vendor_profile_analysis",
        "feature_matrix_analysis",
        "jtbd_analysis",
        "roadmap_analysis",
    ]

    side_effects = [
        phase1_outline,         # phase 1
        phase2_payload,         # phase 2
        _make_valid_narrative_json(s1_section_types[0]),   # narrative 1 ok
        _make_valid_narrative_json(s1_section_types[1]),   # narrative 2 ok
        RuntimeError("LLM 模拟故障"),                       # narrative 3 首次失败
        _make_valid_narrative_json(s1_section_types[3]),   # narrative 4 ok
        _make_valid_narrative_json(s1_section_types[4]),   # narrative 5 ok
        RuntimeError("LLM 重试也失败"),                     # narrative 3 重试失败
    ]

    mock_llm = MagicMock(spec=LLMClient)
    mock_llm.call_json = AsyncMock(side_effect=side_effects)
    orch = WriterOrchestrator(llm=mock_llm)

    with pytest.raises(Exception):
        await orch.write(
            scenario_input=scenario_input,
            analysis=analysis,
            profiles=profiles,
        )

    # 总 LLM 调用次数 = 1 (outline) + 1 (payload) + 5 (首跑) + 1 (重试) = 8
    assert mock_llm.call_json.call_count == 8


# ---------- 测试 13：phase 3 半数失败硬闸门 raise ----------

@pytest.mark.asyncio
async def test_phase3_half_failure_raises():
    """5 个 section 中 3 个首次+重试都失败 → 触发半数闸门 raise 含 '触发半数闸门'。"""
    scenario_input, analysis, profiles = _make_phase3_full_run_inputs()

    phase1_outline = _make_valid_outline_dict("测试 outline")
    phase2_payload = _s1_payload_dict_with_weighted_scores()
    s1_section_types = [
        "overview",
        "vendor_profile_analysis",
        "feature_matrix_analysis",
        "jtbd_analysis",
        "roadmap_analysis",
    ]

    side_effects = [
        phase1_outline,
        phase2_payload,
        RuntimeError("LLM 故障 1"),                          # narrative 1 首次失败
        RuntimeError("LLM 故障 2"),                          # narrative 2 首次失败
        _make_valid_narrative_json(s1_section_types[2]),    # narrative 3 ok
        RuntimeError("LLM 故障 3"),                          # narrative 4 首次失败
        _make_valid_narrative_json(s1_section_types[4]),    # narrative 5 ok
        # 3 个重试也全失败
        RuntimeError("LLM 重试故障 1"),
        RuntimeError("LLM 重试故障 2"),
        RuntimeError("LLM 重试故障 3"),
    ]

    mock_llm = MagicMock(spec=LLMClient)
    mock_llm.call_json = AsyncMock(side_effect=side_effects)
    orch = WriterOrchestrator(llm=mock_llm)

    # 3 个 section 首次+重试都失败 → 阈值 ⌈5/2⌉=3，failed_n=3 ≥ 3 → raise
    with pytest.raises(RuntimeError, match="触发半数闸门"):
        await orch.write(
            scenario_input=scenario_input,
            analysis=analysis,
            profiles=profiles,
        )


# ---------- 测试 14：phase 3 占位 narrative 字符数 ≥350 ----------

def test_phase3_placeholder_narrative_min_length():
    """[v3-R12] 占位 narrative 字符数 ≥350（schema min=300 + 50 字硬缓冲）。"""
    from src.agents.writer_orchestrator import _build_placeholder_section

    # 测多种长度的 section_type；opportunity_identification_analysis 是最长 case（35 字），
    # 用它验证 section_id 不越界（"placeholder-"+28 = 40 ≤ schema 上限 40）
    for st in ["overview", "feature_matrix_analysis", "opportunity_identification_analysis"]:
        sec = _build_placeholder_section(st, {})
        assert len(sec.narrative) >= 350, (
            f"占位 narrative section_type={st} 字符数 {len(sec.narrative)} < 350"
        )
        assert len(sec.heading) >= 4
        assert 3 <= len(sec.section_id) <= 40, (
            f"{st}: section_id 长度 {len(sec.section_id)} 越界 (3-40)"
        )
        assert sec.section_type == st


# ---------- 测试 15：phase 3 并行（不串行）----------

@pytest.mark.asyncio
async def test_phase3_parallel_not_serial():
    """[v3-R18] 5 个 section LLM mock sleep 0.1s，并发 3 → 总耗时 < 串行（5 * 0.1 = 0.5s）。"""
    import time

    scenario_input, analysis, profiles = _make_phase3_full_run_inputs()

    phase1_outline = _make_valid_outline_dict("测试 outline")
    phase2_payload = _s1_payload_dict_with_weighted_scores()
    s1_section_types = [
        "overview",
        "vendor_profile_analysis",
        "feature_matrix_analysis",
        "jtbd_analysis",
        "roadmap_analysis",
    ]

    # phase 1 / phase 2 立即返回；phase 3 5 个 LLM 调用 sleep 0.1s 后返回对应 narrative
    call_counter = {"n": 0}
    lock = asyncio.Lock()

    async def _next_call(*_args, **_kwargs):
        async with lock:
            idx = call_counter["n"]
            call_counter["n"] += 1
        if idx == 0:
            return phase1_outline
        if idx == 1:
            return phase2_payload
        await asyncio.sleep(0.1)
        # idx 2,3,4,5,6 → section 0,1,2,3,4
        return _make_valid_narrative_json(s1_section_types[idx - 2])

    mock_llm = MagicMock(spec=LLMClient)
    mock_llm.call_json = AsyncMock(side_effect=_next_call)
    orch = WriterOrchestrator(llm=mock_llm)

    t0 = time.perf_counter()
    # phase 4 实现后 outline 不合法会 raise ValidationError；本测试焦点是 phase 3 并行
    with pytest.raises(Exception):
        await orch.write(
            scenario_input=scenario_input,
            analysis=analysis,
            profiles=profiles,
        )
    elapsed = time.perf_counter() - t0

    # 总 LLM 调用 = 1 (outline) + 1 (payload) + 5 (narrative) = 7
    assert mock_llm.call_json.call_count == 7
    # 串行 = 5 * 0.1 = 0.5s；semaphore=3 并发 → 第 1 批 3 个 + 第 2 批 2 个 ≈ 0.2s
    # 防 Windows 抖动 + phase 4 实例化少量开销，留 0.45s 上限（仍远低于 0.5s 串行）
    assert elapsed < 0.45, f"phase 3 总耗时 {elapsed:.3f}s 接近串行（0.5s），可能没并行"


# ---------- Phase 4 测试 fixture ----------


def _make_minimal_outline_dict() -> dict:
    """构造一个最小合法 outline dict（满足 BaseReport 19 字段所有 min_length 约束）。

    用于 phase 4 _phase4_assemble 直接调时的 outline 入参。
    """
    long_enough_200 = "这是一个测试用的足够长字符串，用于满足 schema min_length=200 的硬性要求。" * 5  # ~250 字
    long_enough_100 = "implications 字段需要至少 100 字符来满足 schema 约束的硬要求条款。" * 4  # ~120 字
    long_enough_80 = "sample_size_note 字段需要至少 80 字符的最低描述说明。" * 3  # ~90 字
    long_enough_50 = "core_thesis 字段需要 50-120 字符的核心论点描述内容。" * 2  # ~60 字
    long_enough_20 = "至少 20 字符的描述内容用于满足约束。"
    return {
        "title": "测试报告标题不少于十字符",
        "subtitle": "副标题",
        "at_a_glance": ["要点 1 至少几个字", "要点 2 至少几个字", "要点 3 至少几个字"],
        "executive_summary": {
            "context": "执行摘要的 context 字段需要 80-200 字符的背景描述内容。" * 3,  # ~120
            "core_thesis": long_enough_50,
            "key_findings_brief": ["发现 1", "发现 2"],
            "implications": long_enough_100,
            "path_forward": ["前进路径 1"],
        },
        "background": long_enough_200,
        "scope": {
            "time_window": "2024-2026",
            "regions": ["中国"],
            "exclusions": [],
        },
        "methodology": {
            "data_collection_approach": long_enough_200,
            "evaluation_criteria": ["标准 1", "标准 2", "标准 3"],
            "limitations": ["局限 1", "局限 2"],
            "sample_size_note": long_enough_80,
        },
        "key_findings": [
            {
                "statement": long_enough_20,
                "evidence": long_enough_20,
                "implication": long_enough_20,
            },
            {
                "statement": long_enough_20,
                "evidence": long_enough_20,
                "implication": long_enough_20,
            },
            {
                "statement": long_enough_20,
                "evidence": long_enough_20,
                "implication": long_enough_20,
            },
        ],
        "conclusions": long_enough_200,
        "recommendations": [
            {
                "action": long_enough_20,
                "target_role": "PM",
                "priority": "critical",
                "timeline": "immediate",
                "rationale": long_enough_20,
            },
            {
                "action": long_enough_20,
                "target_role": "PM",
                "priority": "important",
                "timeline": "short_term",
                "rationale": long_enough_20,
            },
            {
                "action": long_enough_20,
                "target_role": "PM",
                "priority": "consider",
                "timeline": "long_term",
                "rationale": long_enough_20,
            },
        ],
    }


def _make_s1_payload_model_for_phase4(discovered_url: str = "https://a.example.com/feature"):
    """通过 _build_payload_model 构造一个真实合法的 S1FeatureIterationPayload（供 phase 4 走通）。"""
    from src.schemas.input import CompetitorBasic, ScenarioInput

    mock_llm = MagicMock(spec=LLMClient)
    mock_llm.call_json = AsyncMock(return_value={})
    orch = WriterOrchestrator(llm=mock_llm)

    scenario_input = ScenarioInput(
        scenario="S1",
        competitors=[CompetitorBasic(name="竞品A"), CompetitorBasic(name="竞品B")],
        analysis_context="测试上下文",
        our_product_name="我方",
    )
    payload_dict = _s1_payload_dict_with_weighted_scores()
    payload_model = orch._build_payload_model(
        "S1",
        payload_dict,
        discovered_urls=[discovered_url],
        competitor_recommendations=None,
        prior_report_data=None,
        scenario_input=scenario_input,
        warnings=[],
    )
    return payload_model


def _make_phase4_sections(scenario: str = "s1") -> list:
    """构造 4 个合法 AnalysisSection（满足 BaseReport.analysis_sections min=4）。"""
    from src.schemas.report import AnalysisSection
    types = ["overview", "vendor_profile_analysis", "feature_matrix_analysis", "jtbd_analysis"]
    return [
        AnalysisSection(**_make_valid_narrative_json(t, scenario))
        for t in types
    ]


# ---------- 测试 16: phase 4 SWOT 透传 ----------


def test_phase4_data_collection_approach_synthesized_by_code():
    """[fix11 prove-it] data_collection_approach 由代码合成，不依赖 LLM 输出。

    现象（trace 20260609-184652-f07f60 / 20260609-194204-efeba1）：
    LLM 在 phase 1 outline 反复写不够 200 字符，每次 graph 重试后依然栽。
    修：phase 4 用模板覆盖 outline.methodology.data_collection_approach，
    无论 LLM 输出什么，最终报告该字段一定 ≥200 字符。
    """
    from src.schemas.input import CompetitorBasic, ScenarioInput
    from src.schemas.report import Swot, SwotEntry

    mock_llm = MagicMock(spec=LLMClient)
    mock_llm.call_json = AsyncMock(return_value={})
    orch = WriterOrchestrator(llm=mock_llm)

    swot_real = Swot(
        strengths=[SwotEntry(point="占位优势点内容至少十字符", evidence="占位证据内容至少十字符", dimension="overall")],
        weaknesses=[SwotEntry(point="占位劣势点内容至少十字符", evidence="占位证据内容至少十字符", dimension="overall")],
        opportunities=[SwotEntry(point="占位机会点内容至少十字符", evidence="占位证据内容至少十字符", dimension="overall")],
        threats=[SwotEntry(point="占位威胁点内容至少十字符", evidence="占位证据内容至少十字符", dimension="overall")],
    )
    analysis = MagicMock()
    analysis.swot = swot_real

    scenario_input = ScenarioInput(
        scenario="S1",
        competitors=[CompetitorBasic(name="竞品A"), CompetitorBasic(name="竞品B")],
        analysis_context="测试",
        our_product_name="我方",
    )
    profile = _make_profile(data_sources=["https://a.example.com/feature"])

    # 关键：构造 outline 时 data_collection_approach 故意写成短字符串（模拟 LLM 偷懒）
    outline = _make_minimal_outline_dict()
    outline["methodology"]["data_collection_approach"] = "短"  # 1 字符，远低于 200

    report = orch._phase4_assemble(
        scenario="S1",
        scenario_input=scenario_input,
        outline=outline,
        payload_model=_make_s1_payload_model_for_phase4(),
        sections=_make_phase4_sections(),
        profiles=[profile],
        analysis=analysis,
        trace_id="trace-fix11",
        warnings=[],
        competitor_recommendations=None,
        discovered_urls=["https://a.example.com/feature"],
        competitor_names=["竞品A", "竞品B"],
    )
    # data_collection_approach 必须 ≥200 字符（schema 强制）
    assert len(report.methodology.data_collection_approach) >= 200, (
        f"data_collection_approach 长度 {len(report.methodology.data_collection_approach)} < 200，代码合成未生效"
    )
    # 模板内容应包含关键信息
    text = report.methodology.data_collection_approach
    assert "竞品" in text  # 提到竞品数量
    assert "S1" in text or "功能迭代" in text  # 提到场景


def test_phase4_appendix_glossary_prefilled():
    """[fix9 prove-it] Appendix.glossary 应预填常用术语，不再是空 dict。

    现象（trace 20260609-184652-f07f60 inspector issue 3）：
    报告正文出现 JTBD / Tier1 / Tier2 等专业术语但 glossary={} 没解释。
    phase 4 应预置一组常用术语字典，让普通读者也能理解报告。
    """
    from src.schemas.input import CompetitorBasic, ScenarioInput
    from src.schemas.report import Swot, SwotEntry

    mock_llm = MagicMock(spec=LLMClient)
    mock_llm.call_json = AsyncMock(return_value={})
    orch = WriterOrchestrator(llm=mock_llm)

    swot_real = Swot(
        strengths=[SwotEntry(point="占位优势点内容至少十字符", evidence="占位证据内容至少十字符", dimension="overall")],
        weaknesses=[SwotEntry(point="占位劣势点内容至少十字符", evidence="占位证据内容至少十字符", dimension="overall")],
        opportunities=[SwotEntry(point="占位机会点内容至少十字符", evidence="占位证据内容至少十字符", dimension="overall")],
        threats=[SwotEntry(point="占位威胁点内容至少十字符", evidence="占位证据内容至少十字符", dimension="overall")],
    )
    analysis = MagicMock()
    analysis.swot = swot_real

    scenario_input = ScenarioInput(
        scenario="S1",
        competitors=[CompetitorBasic(name="竞品A"), CompetitorBasic(name="竞品B")],
        analysis_context="测试",
        our_product_name="我方",
    )
    profile = _make_profile(data_sources=["https://a.example.com/feature"])

    report = orch._phase4_assemble(
        scenario="S1",
        scenario_input=scenario_input,
        outline=_make_minimal_outline_dict(),
        payload_model=_make_s1_payload_model_for_phase4(),
        sections=_make_phase4_sections(),
        profiles=[profile],
        analysis=analysis,
        trace_id="trace-fix9",
        warnings=[],
        competitor_recommendations=None,
        discovered_urls=["https://a.example.com/feature"],
        competitor_names=["竞品A", "竞品B"],
    )
    glossary = report.appendix.glossary
    assert isinstance(glossary, dict)
    assert len(glossary) >= 5, f"glossary 应预填 ≥5 条常用术语，当前 {len(glossary)} 条"
    # 高频术语必须存在
    for term in ["JTBD", "Tier1", "SWOT"]:
        assert term in glossary, f"glossary 缺常用术语 {term}"
        assert len(glossary[term]) >= 5, f"{term} 解释不应过短"


def test_phase4_data_sources_accessed_at_falls_back_to_collected_at():
    """[fix8 prove-it] DataSource.accessed_at 在 LLM 没填时用 profile.metadata.collected_at 兜底。

    现象（trace 20260609-184652-f07f60 inspector issue 2）：
    所有 data_sources.accessed_at 全 None → 数据时效性无法判断。
    profile.metadata.collected_at 已经有 ISO 时间，phase 4 应取其日期部分兜底。
    """
    from datetime import date

    from src.schemas.input import CompetitorBasic, ScenarioInput
    from src.schemas.report import Swot, SwotEntry

    mock_llm = MagicMock(spec=LLMClient)
    mock_llm.call_json = AsyncMock(return_value={})
    orch = WriterOrchestrator(llm=mock_llm)

    swot_real = Swot(
        strengths=[SwotEntry(point="占位优势点内容至少十字符", evidence="占位证据内容至少十字符", dimension="overall")],
        weaknesses=[SwotEntry(point="占位劣势点内容至少十字符", evidence="占位证据内容至少十字符", dimension="overall")],
        opportunities=[SwotEntry(point="占位机会点内容至少十字符", evidence="占位证据内容至少十字符", dimension="overall")],
        threats=[SwotEntry(point="占位威胁点内容至少十字符", evidence="占位证据内容至少十字符", dimension="overall")],
    )
    analysis = MagicMock()
    analysis.swot = swot_real

    scenario_input = ScenarioInput(
        scenario="S1",
        competitors=[CompetitorBasic(name="竞品A"), CompetitorBasic(name="竞品B")],
        analysis_context="测试",
        our_product_name="我方",
    )
    # _make_profile 默认 collected_at="2026-06-08T00:00:00"
    profile = _make_profile(data_sources=["https://a.example.com/feature"])

    report = orch._phase4_assemble(
        scenario="S1",
        scenario_input=scenario_input,
        outline=_make_minimal_outline_dict(),
        payload_model=_make_s1_payload_model_for_phase4(),
        sections=_make_phase4_sections(),
        profiles=[profile],
        analysis=analysis,
        trace_id="trace-fix8",
        warnings=[],
        competitor_recommendations=None,
        discovered_urls=["https://a.example.com/feature"],
        competitor_names=["竞品A", "竞品B"],
    )
    # 应该至少有 1 条 data_source（在 metadata 上）
    assert len(report.metadata.data_sources) >= 1
    # 全部 data_sources 的 accessed_at 都不应该是 None（用 collected_at=2026-06-08 兜底）
    for ds in report.metadata.data_sources:
        assert ds.accessed_at is not None, f"data_source {ds.url} accessed_at 应被 collected_at 兜底"
        assert ds.accessed_at == date(2026, 6, 8), \
            f"应取 collected_at 的日期部分 2026-06-08，实际 {ds.accessed_at}"


def test_phase4_swot_passthrough():
    """[Q1=C] analysis.swot 非 None 时 phase 4 透传，不构造 placeholder。"""
    from src.schemas.report import Swot, SwotEntry
    from src.schemas.input import CompetitorBasic, ScenarioInput

    mock_llm = MagicMock(spec=LLMClient)
    mock_llm.call_json = AsyncMock(return_value={})
    orch = WriterOrchestrator(llm=mock_llm)

    swot_real = Swot(
        strengths=[SwotEntry(point="优势点至少十字符长度内容", evidence="证据至少十字符长度内容", dimension="overall")],
        weaknesses=[SwotEntry(point="劣势点至少十字符长度内容", evidence="证据至少十字符长度内容", dimension="overall")],
        opportunities=[SwotEntry(point="机会点至少十字符长度内容", evidence="证据至少十字符长度内容", dimension="overall")],
        threats=[SwotEntry(point="威胁点至少十字符长度内容", evidence="证据至少十字符长度内容", dimension="overall")],
    )
    analysis = MagicMock()
    analysis.swot = swot_real

    scenario_input = ScenarioInput(
        scenario="S1",
        competitors=[CompetitorBasic(name="竞品A"), CompetitorBasic(name="竞品B")],
        analysis_context="测试",
        our_product_name="我方",
    )
    profile = _make_profile(data_sources=["https://a.example.com/feature"])
    payload_model = _make_s1_payload_model_for_phase4()
    outline = _make_minimal_outline_dict()
    sections = _make_phase4_sections()
    warnings: list[str] = []

    report = orch._phase4_assemble(
        scenario="S1",
        scenario_input=scenario_input,
        outline=outline,
        payload_model=payload_model,
        sections=sections,
        profiles=[profile],
        analysis=analysis,
        trace_id="trace-test-1",
        warnings=warnings,
        competitor_recommendations=None,
        discovered_urls=["https://a.example.com/feature"],
        competitor_names=["竞品A", "竞品B"],
    )

    # SWOT 是同一对象（透传，不重建）
    assert report.swot is swot_real
    # warnings 不应包含 placeholder_swot
    assert "placeholder_swot" not in warnings


# ---------- 测试 17: phase 4 SWOT placeholder ----------


def test_phase4_swot_placeholder_when_none():
    """[v3-R12] _build_placeholder_swot 4 象限各 1 条，point/evidence ≥25 字。"""
    from src.agents.writer_orchestrator import _build_placeholder_swot

    sw = _build_placeholder_swot()
    for quadrant in [sw.strengths, sw.weaknesses, sw.opportunities, sw.threats]:
        assert len(quadrant) == 1
        entry = quadrant[0]
        assert len(entry.point) >= 25, f"point 字符数 {len(entry.point)} < 25"
        assert len(entry.evidence) >= 25, f"evidence 字符数 {len(entry.evidence)} < 25"
        assert entry.dimension == "overall"


# ---------- 测试 18: phase 4 confidence_level 派生 ----------


def test_phase4_confidence_level_derivation():
    """[v3-R13] completeness 平均值映射 high/medium/low；空 profiles → low（无 ZeroDivisionError）。"""
    from src.schemas.input import CompetitorBasic, ScenarioInput

    mock_llm = MagicMock(spec=LLMClient)
    mock_llm.call_json = AsyncMock(return_value={})
    orch = WriterOrchestrator(llm=mock_llm)
    scenario_input = ScenarioInput(
        scenario="S1",
        competitors=[CompetitorBasic(name="竞品A"), CompetitorBasic(name="竞品B")],
        analysis_context="测试",
        our_product_name="我方",
    )
    payload_model = _make_s1_payload_model_for_phase4()
    outline = _make_minimal_outline_dict()
    sections = _make_phase4_sections()
    discovered = ["https://a.example.com/feature"]

    # high: avg = (0.9 + 0.85) / 2 = 0.875 ≥ 0.8
    p1 = _make_profile(data_sources=discovered, name="竞品A")
    p1.metadata.completeness_score = 0.9
    p2 = _make_profile(data_sources=discovered, name="竞品B")
    p2.metadata.completeness_score = 0.85
    report_high = orch._phase4_assemble(
        scenario="S1", scenario_input=scenario_input, outline=outline,
        payload_model=payload_model, sections=sections, profiles=[p1, p2],
        analysis=MagicMock(swot=None), trace_id="t1", warnings=[],
        competitor_recommendations=None, discovered_urls=discovered,
        competitor_names=["竞品A", "竞品B"],
    )
    assert report_high.metadata.confidence_level == "high"

    # medium: avg = 0.55 ≥ 0.5
    p1.metadata.completeness_score = 0.6
    p2.metadata.completeness_score = 0.5
    report_med = orch._phase4_assemble(
        scenario="S1", scenario_input=scenario_input, outline=outline,
        payload_model=payload_model, sections=sections, profiles=[p1, p2],
        analysis=MagicMock(swot=None), trace_id="t2", warnings=[],
        competitor_recommendations=None, discovered_urls=discovered,
        competitor_names=["竞品A", "竞品B"],
    )
    assert report_med.metadata.confidence_level == "medium"

    # low: avg = 0.25 < 0.5
    p1.metadata.completeness_score = 0.3
    p2.metadata.completeness_score = 0.2
    report_low = orch._phase4_assemble(
        scenario="S1", scenario_input=scenario_input, outline=outline,
        payload_model=payload_model, sections=sections, profiles=[p1, p2],
        analysis=MagicMock(swot=None), trace_id="t3", warnings=[],
        competitor_recommendations=None, discovered_urls=discovered,
        competitor_names=["竞品A", "竞品B"],
    )
    assert report_low.metadata.confidence_level == "low"


# ---------- 测试 19: phase 4 URL 双通道聚合 ----------


def test_phase4_url_dual_channel_aggregation():
    """[v3-R07/R08] _collect_source_refs_recursive 区分 SourceRef vs DataSource，裸 url 字段单独收集。"""
    from src.agents.writer_orchestrator import _collect_source_refs_recursive

    dump = {
        # SourceRef-like（无 confidence）
        "ref1": {"url": "https://a.com/x", "title": "A", "source_type": "official_website"},
        # DataSource-like（含 confidence）→ 不应被回收
        "ref2": {
            "url": "https://b.com/x", "title": "B", "source_type": "news",
            "confidence": "high",
        },
        # 裸 url 字段
        "evidence_url": "https://c.com/y",
        "pricing_page_url": "https://d.com/z",
        # 嵌套 list 中的 SourceRef
        "list_field": [
            {"url": "https://e.com/p", "source_type": "user_review"},
        ],
        # 非白名单字段名的裸 url（不被收集）
        "random_link": "https://ignored.com/q",
        # 非 http 开头（不被收集）
        "url": "ftp://x.com/y",
    }
    refs, bare = _collect_source_refs_recursive(dump)

    ref_urls = {r["url"] for r in refs}
    # SourceRef-like 进 refs（含嵌套）
    assert "https://a.com/x" in ref_urls
    assert "https://e.com/p" in ref_urls
    # DataSource-like 不进 refs
    assert "https://b.com/x" not in ref_urls
    # 裸 url 字段进 bare（不进 refs）
    assert "https://c.com/y" in bare
    assert "https://d.com/z" in bare
    assert "https://c.com/y" not in ref_urls
    # 非白名单字段名不进 bare
    assert "https://ignored.com/q" not in bare
    # 非 http 不进 bare（白名单 url 字段但 ftp:// 开头）
    assert "ftp://x.com/y" not in bare


# ---------- 测试 20: phase 4 final_urls 空 raise ----------


def test_phase4_empty_final_urls_raises():
    """[v3-R06] profiles 有 URL（discovered 非空）但报告内 0 个引用 → raise RuntimeError 含 '回 writer'。"""
    from src.schemas.input import CompetitorBasic, ScenarioInput

    mock_llm = MagicMock(spec=LLMClient)
    mock_llm.call_json = AsyncMock(return_value={})
    orch = WriterOrchestrator(llm=mock_llm)

    scenario_input = ScenarioInput(
        scenario="S1",
        competitors=[CompetitorBasic(name="竞品A"), CompetitorBasic(name="竞品B")],
        analysis_context="测试",
        our_product_name="我方",
    )
    # discovered_urls 非空（profile 有 URL）
    discovered = ["https://only.example.com/page"]
    profile = _make_profile(data_sources=discovered, name="竞品A")
    # payload 用一个不引用 discovered URL 的（构造时给的 evidence_url 是不同 URL）
    payload_model = _make_s1_payload_model_for_phase4(discovered_url="https://other.example.com/feat")
    outline = _make_minimal_outline_dict()  # outline 不含任何 URL
    sections = _make_phase4_sections()  # sections.source_refs=[]
    warnings: list[str] = []

    # 关键：discovered 给 only.example.com，但报告内（payload/outline/sections/swot）都不引用这个 URL
    # final_urls 必为空，应 raise
    with pytest.raises(RuntimeError, match="回 writer"):
        orch._phase4_assemble(
            scenario="S1", scenario_input=scenario_input, outline=outline,
            payload_model=payload_model, sections=sections, profiles=[profile],
            analysis=MagicMock(swot=None), trace_id="t-empty", warnings=warnings,
            competitor_recommendations=None, discovered_urls=discovered,
            competitor_names=["竞品A", "竞品B"],
        )


# ---------- 测试 21: phase 4 S2 scope.competitors union ----------


def test_phase4_s2_scope_union(monkeypatch):
    """[v3-R19] S2 union（用户在前去重）；recommender=None 时仅用户；用户/recommender 都空 → raise。

    注意：S2 真实 BaseReport 实例化需要完整 S2MarketEntryPayload（market_sizing/five_forces 等子 schema 复杂），
    本测试 monkey-patch BaseReport 类绕开实例化，聚焦 S2 union 计算逻辑。
    """
    from src.schemas.scenarios.s2 import CompetitorRecommendations, RecommendedCompetitor
    from src.schemas.input import CompetitorBasic, ScenarioInput
    from src.agents import writer_orchestrator as wo

    mock_llm = MagicMock(spec=LLMClient)
    mock_llm.call_json = AsyncMock(return_value={})
    orch = WriterOrchestrator(llm=mock_llm)

    # monkeypatch BaseReport 为接受任意字段的 fake，仅暴露 scope 和 metadata
    captured: dict = {}

    class _FakeBaseReport:
        def __init__(self, **kwargs):
            captured.update(kwargs)
            self.metadata = kwargs.get("metadata")
            self.scope = kwargs.get("scope")
            self.swot = kwargs.get("swot")
            self.title = kwargs.get("title", "")

    monkeypatch.setattr(wo, "BaseReport", _FakeBaseReport)

    discovered = ["https://a.example.com/feature"]
    profile = _make_profile(data_sources=discovered, name="A")
    payload_model = _make_s1_payload_model_for_phase4()  # S1 payload 也行——_FakeBaseReport 不校验
    outline = _make_minimal_outline_dict()
    sections = _make_phase4_sections()

    # 案例 1: S2 + competitors=[A] + recommender=[B,C,D] → union=[A,B,C,D]，A 在前
    scenario_input_1 = ScenarioInput(
        scenario="S2",
        competitors=[CompetitorBasic(name="AA")],
        industry="测试行业",
        analysis_context="测试",
    )
    rec_1 = CompetitorRecommendations(
        user_provided_industry="测试行业",
        user_provided_competitors=["A"],
        recommended_competitors=[
            RecommendedCompetitor(name=n, why_recommended="推荐理由满足十字符约束", confidence="high")
            for n in ["B", "C", "D"]
        ],
        selection_method="hybrid",
        selection_rationale="测试推荐理由不少于三十字符的描述内容来满足该字段最低长度约束的要求",
    )
    report_1 = orch._phase4_assemble(
        scenario="S2", scenario_input=scenario_input_1, outline=outline,
        payload_model=payload_model, sections=sections, profiles=[profile],
        analysis=MagicMock(swot=None), trace_id="ts2-1", warnings=[],
        competitor_recommendations=rec_1, discovered_urls=discovered,
        competitor_names=["A"],
    )
    assert report_1.scope.competitors == ["AA", "B", "C", "D"]

    # 案例 2: S2 + competitors=[] + recommender=[A,B,C] → union=[A,B,C]
    scenario_input_2 = ScenarioInput(
        scenario="S2",
        competitors=[],
        industry="测试行业",
        analysis_context="测试",
    )
    rec_2 = CompetitorRecommendations(
        user_provided_industry="测试行业",
        user_provided_competitors=[],
        recommended_competitors=[
            RecommendedCompetitor(name=n, why_recommended="推荐理由满足十字符约束", confidence="high")
            for n in ["A", "B", "C"]
        ],
        selection_method="search_api_top_n",
        selection_rationale="测试推荐理由不少于三十字符的描述内容来满足该字段最低长度约束的要求",
    )
    report_2 = orch._phase4_assemble(
        scenario="S2", scenario_input=scenario_input_2, outline=outline,
        payload_model=payload_model, sections=sections, profiles=[profile],
        analysis=MagicMock(swot=None), trace_id="ts2-2", warnings=[],
        competitor_recommendations=rec_2, discovered_urls=discovered,
        competitor_names=[],
    )
    assert report_2.scope.competitors == ["A", "B", "C"]

    # 案例 3: S2 + competitors=[] + recommender=None → raise
    with pytest.raises(RuntimeError, match="S2 scope.competitors 空"):
        orch._phase4_assemble(
            scenario="S2", scenario_input=scenario_input_2, outline=outline,
            payload_model=payload_model, sections=sections, profiles=[profile],
            analysis=MagicMock(swot=None), trace_id="ts2-3", warnings=[],
            competitor_recommendations=None, discovered_urls=discovered,
            competitor_names=[],
        )


# ============================================================
# S5 Payload 拆分优化（2026-06-16）
# ============================================================


def test_serialize_validation_error_enhanced_s5():
    """S5 增强错误反馈：human-readable 字段路径 + 期望值描述。"""
    from src.schemas.scenarios.s5 import S5PositioningPayload

    # 构造一个会触发多个 errors 的 raw dict（多种错误类型组合）
    raw = {
        "scenario_type": "S5",
        "vendor_profiles": [{
            "competitor_name": "A",
            "is_self": False,
            "ability_to_execute_score": 3.0,
            "ability_to_execute_rationale": "短",  # < 50 字
            "completeness_of_vision_score": 3.0,
            "completeness_of_vision_rationale": "短",  # < 50 字
            "overview": "短",  # < 20 字
            "strengths": [],  # < 2 条
            "cautions": [],  # < 1 条
            "source_refs": [],
        }],
        "perceptual_map": {
            "artifact_id": "pm1",
            "artifact_type": "perceptual_map",
            "title": "t",
            "x_axis": {"attribute": "ab", "low_label": "低", "high_label": "高", "rationale": "test rationale long enough"},
            "y_axis": {"attribute": "cd", "low_label": "低", "high_label": "高", "rationale": "test rationale long enough"},
            "plotted_brands": [],
        },
        "strategy_canvas": {
            "artifact_id": "sc1",
            "artifact_type": "strategy_canvas",
            "title": "t",
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
        # 应包含人类可读的字段路径（点号分隔）
        assert "vendor_profiles" in result or "strengths" in result
        # 应包含期望值描述（中文长度提示或具体数字）
        assert "≥" in result or "至少" in result or "条" in result or "字符" in result
        # 应有序号
        assert "1." in result


@pytest.mark.asyncio
async def test_s5_phase2a_produces_data_layer(monkeypatch):
    """S5 phase 2a 产出 vendor_profiles + perceptual_map + strategy_canvas，且通过逐模块校验。"""
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
                {
                    "point": "优势一条要写得足够长才行",
                    "evidence": "证据一条要写得足够长才行",
                    "source_refs": [{"url": "https://a.com", "title": "t", "source_type": "other"}],
                },
                {
                    "point": "优势二条要写得足够长才行",
                    "evidence": "证据二条要写得足够长才行",
                    "source_refs": [{"url": "https://a.com", "title": "t", "source_type": "other"}],
                },
            ],
            "cautions": [{
                "point": "风险一条要写得足够长才行",
                "evidence": "证据一条要写得足够长才行",
                "source_refs": [{"url": "https://a.com", "title": "t", "source_type": "other"}],
            }],
            "source_refs": [{"url": "https://a.com", "title": "t", "source_type": "other"}],
        }],
        "perceptual_map": {
            "artifact_id": "pm1",
            "artifact_type": "perceptual_map",
            "title": "感知地图",
            "x_axis": {
                "attribute": "易用性等级",
                "low_label": "低端",
                "high_label": "高端",
                "rationale": "这是 x 轴 rationale 要至少二十个字符的描述",
            },
            "y_axis": {
                "attribute": "功能深度",
                "low_label": "基础",
                "high_label": "全面",
                "rationale": "这是 y 轴 rationale 要至少二十个字符的描述",
            },
            "plotted_brands": [
                {
                    "competitor_name": "TestComp",
                    "is_self": False,
                    "x_score": 3.5,
                    "y_score": 4.0,
                    "confidence": "medium",
                    "score_rationale": "这是评分理由的详细描述至少要二十个字符以上",
                },
                {
                    "competitor_name": "BrandB",
                    "is_self": False,
                    "x_score": 2.0,
                    "y_score": 3.0,
                    "confidence": "low",
                    "score_rationale": "这是 BrandB 的评分理由至少要二十个字符以上",
                },
                {
                    "competitor_name": "BrandC",
                    "is_self": True,
                    "x_score": 4.0,
                    "y_score": 4.5,
                    "confidence": "high",
                    "score_rationale": "这是 BrandC 的评分理由至少要二十个字符以上",
                },
            ],
        },
        "strategy_canvas": {
            "artifact_id": "sc1",
            "artifact_type": "strategy_canvas",
            "title": "战略画布",
            "competitive_factors": [
                {"name": "易用性能力", "industry_avg_level": 5.0},
                {"name": "功能深度模块", "industry_avg_level": 6.0},
                {"name": "价格竞争力", "industry_avg_level": 4.0},
                {"name": "生态整合度", "industry_avg_level": 3.0},
                {"name": "品牌影响力", "industry_avg_level": 7.0},
            ],
            "value_curves": [
                {
                    "competitor_name": "TestComp",
                    "is_self": False,
                    "factor_levels": {
                        "易用性能力": 3.5,
                        "功能深度模块": 4.0,
                        "价格竞争力": 5.0,
                        "生态整合度": 2.0,
                        "品牌影响力": 6.0,
                    },
                },
                {
                    "competitor_name": "BrandB",
                    "is_self": False,
                    "factor_levels": {
                        "易用性能力": 2.0,
                        "功能深度模块": 3.0,
                        "价格竞争力": 4.0,
                        "生态整合度": 1.0,
                        "品牌影响力": 5.0,
                    },
                },
            ],
        },
    }

    orchestrator = WriterOrchestrator(llm=MagicMock())
    monkeypatch.setattr(
        orchestrator, "_llm_call_with_quota", AsyncMock(return_value=mock_raw)
    )

    scenario_input = MagicMock()
    scenario_input.our_product_name = "MyProd"
    scenario_input.our_product_brief = "brief"
    scenario_input.industry = "test"
    scenario_input.analysis_context = "ctx"
    scenario_input.prior_trace_id = None

    # analysis 用 dict 即可（_build_phase2_user_prompt 走 json.dumps 分支）
    result = await orchestrator._call_s5_phase2a(
        scenario_input=scenario_input,
        analysis={"summary": "test analysis"},
        profiles=[],
        competitor_names=["TestComp"],
        competitor_basics=[{"name": "TestComp"}],
        discovered_urls=["https://a.com"],
    )

    assert "vendor_profiles" in result
    assert "perceptual_map" in result
    assert "strategy_canvas" in result
    assert len(result["vendor_profiles"]) == 1


@pytest.mark.asyncio
async def test_s5_phase2b_produces_strategy_layer(monkeypatch):
    """S5 phase 2b 产出 errc_grid + positioning_statement + category_strategy，blue_ocean_move 可省略。"""
    mock_raw = {
        "errc_grid": {
            "artifact_id": "errc1",
            "artifact_type": "errc_grid",
            "title": "ERRC",
            "eliminate": [{"factor": "低效冗余功能", "rationale": "这是消除理由要至少有二十个字符的详细描述说明"}],
            "reduce": [{"factor": "冗余审批流程", "rationale": "这是减少理由要至少有二十个字符的详细描述说明"}],
            "raise_level": [{"factor": "易用性体验", "rationale": "这是提升理由要至少有二十个字符的详细描述说明"}],
            "create": [{"factor": "智能辅助助手", "rationale": "这是创造理由要至少有二十个字符的详细描述说明"}],
        },
        "positioning_statement": {
            "target_customer": "目标客户群体的描述要足够长",
            "need_or_opportunity": "需求场景的描述要足够长",
            "product_name": "产品",
            "product_category": "智能协作平台",
            "key_benefit": "关键利益点的描述要足够长",
            "primary_alternative": "替代竞品",
            "primary_differentiation": "差异化点的描述要足够长",
            "confidence": "llm_inferred",
        },
        "category_strategy": {
            "chosen_category": "智能协作工具",
            "why_this_category": "选择此品类的理由要至少有三十个字符的详细描述说明这个品类的合理性",
            "competitors_implied": ["竞品A"],
        },
    }

    orchestrator = WriterOrchestrator(llm=MagicMock())
    monkeypatch.setattr(
        orchestrator, "_llm_call_with_quota", AsyncMock(return_value=mock_raw)
    )

    scenario_input = MagicMock()
    scenario_input.our_product_name = "MyProd"
    scenario_input.our_product_brief = "brief"
    scenario_input.industry = "test"
    scenario_input.analysis_context = "ctx"
    scenario_input.prior_trace_id = None

    phase2a_output = {
        "strategy_canvas": {
            "competitive_factors": [
                {"name": "易用性能力"},
                {"name": "功能深度"},
            ],
        },
        "vendor_profiles": [{"competitor_name": "TestComp"}],
    }

    result = await orchestrator._call_s5_phase2b(
        phase2a_output=phase2a_output,
        scenario_input=scenario_input,
        analysis={"summary": "test"},
        discovered_urls=["https://a.com"],
    )

    assert "errc_grid" in result
    assert "positioning_statement" in result
    assert "category_strategy" in result


def _build_phase2a_payload_for_merge() -> dict:
    """构造 merge 测试用合法 phase 2a output，含 2 个 vendor_profiles 满足 cross-check。"""
    return {
        "vendor_profiles": [
            {
                "competitor_name": "CompA",
                "is_self": False,
                "ability_to_execute_score": 3.0,
                "ability_to_execute_rationale": "这是 CompA 的执行能力评分理由的详细描述要至少有五十个字符的长度才能满足 schema 校验的最低要求",
                "completeness_of_vision_score": 3.0,
                "completeness_of_vision_rationale": "这是 CompA 的愿景完整度评分理由的详细描述要至少有五十个字符的长度才能满足 schema 校验的最低要求",
                "overview": "CompA 概述描述要至少有二十个字符以上的内容",
                "strengths": [
                    {"point": "优势一条要写得足够长才行", "evidence": "证据一条要写得足够长才行", "source_refs": [{"url": "https://a.com", "title": "t", "source_type": "other"}]},
                    {"point": "优势二条要写得足够长才行", "evidence": "证据二条要写得足够长才行", "source_refs": [{"url": "https://a.com", "title": "t", "source_type": "other"}]},
                ],
                "cautions": [{"point": "风险一条要写得足够长才行", "evidence": "证据一条要写得足够长才行", "source_refs": [{"url": "https://a.com", "title": "t", "source_type": "other"}]}],
                "source_refs": [{"url": "https://a.com", "title": "t", "source_type": "other"}],
            },
            {
                "competitor_name": "CompB",
                "is_self": True,
                "ability_to_execute_score": 4.0,
                "ability_to_execute_rationale": "这是 CompB 的执行能力评分理由的详细描述要至少有五十个字符的长度才能满足 schema 校验的最低要求",
                "completeness_of_vision_score": 4.0,
                "completeness_of_vision_rationale": "这是 CompB 的愿景完整度评分理由的详细描述要至少有五十个字符的长度才能满足 schema 校验的最低要求",
                "overview": "CompB 概述描述要至少有二十个字符以上的内容",
                "strengths": [
                    {"point": "优势一条要写得足够长才行", "evidence": "证据一条要写得足够长才行", "source_refs": [{"url": "https://a.com", "title": "t", "source_type": "other"}]},
                    {"point": "优势二条要写得足够长才行", "evidence": "证据二条要写得足够长才行", "source_refs": [{"url": "https://a.com", "title": "t", "source_type": "other"}]},
                ],
                "cautions": [{"point": "风险一条要写得足够长才行", "evidence": "证据一条要写得足够长才行", "source_refs": [{"url": "https://a.com", "title": "t", "source_type": "other"}]}],
                "source_refs": [{"url": "https://a.com", "title": "t", "source_type": "other"}],
            },
        ],
        "perceptual_map": {
            "artifact_id": "pm1",
            "artifact_type": "perceptual_map",
            "title": "感知地图",
            "x_axis": {"attribute": "易用性等级", "low_label": "低端", "high_label": "高端", "rationale": "x 轴 rationale 要至少二十个字符的描述"},
            "y_axis": {"attribute": "功能深度等级", "low_label": "基础", "high_label": "全面", "rationale": "y 轴 rationale 要至少二十个字符的描述"},
            "plotted_brands": [
                {"competitor_name": "CompA", "is_self": False, "x_score": 3.0, "y_score": 3.0, "confidence": "medium", "score_rationale": "CompA 评分理由要至少二十个字符的描述"},
                {"competitor_name": "CompB", "is_self": True, "x_score": 4.0, "y_score": 4.0, "confidence": "high", "score_rationale": "CompB 评分理由要至少二十个字符的描述"},
                {"competitor_name": "CompC", "is_self": False, "x_score": 2.0, "y_score": 2.0, "confidence": "low", "score_rationale": "CompC 评分理由要至少二十个字符的描述"},
            ],
        },
        "strategy_canvas": {
            "artifact_id": "sc1",
            "artifact_type": "strategy_canvas",
            "title": "战略画布",
            "competitive_factors": [
                {"name": "易用性能力", "industry_avg_level": 5.0},
                {"name": "功能深度模块", "industry_avg_level": 5.0},
                {"name": "价格竞争力", "industry_avg_level": 5.0},
                {"name": "生态整合度", "industry_avg_level": 5.0},
                {"name": "品牌影响力", "industry_avg_level": 5.0},
            ],
            "value_curves": [
                {"competitor_name": "CompA", "is_self": False, "factor_levels": {"易用性能力": 3.0, "功能深度模块": 3.0, "价格竞争力": 3.0, "生态整合度": 3.0, "品牌影响力": 3.0}},
                {"competitor_name": "CompB", "is_self": True, "factor_levels": {"易用性能力": 4.0, "功能深度模块": 4.0, "价格竞争力": 4.0, "生态整合度": 4.0, "品牌影响力": 4.0}},
            ],
        },
    }


def _build_phase2b_payload_for_merge() -> dict:
    """构造 merge 测试用合法 phase 2b output。"""
    return {
        "errc_grid": {
            "artifact_id": "errc1",
            "artifact_type": "errc_grid",
            "title": "ERRC",
            "eliminate": [{"factor": "低效冗余功能", "rationale": "消除理由要至少有二十个字符的详细描述说明"}],
            "reduce": [{"factor": "冗余审批流程", "rationale": "减少理由要至少有二十个字符的详细描述说明"}],
            "raise_level": [{"factor": "易用性体验", "rationale": "提升理由要至少有二十个字符的详细描述说明"}],
            "create": [{"factor": "智能辅助助手", "rationale": "创造理由要至少有二十个字符的详细描述说明"}],
        },
        "positioning_statement": {
            "target_customer": "目标客户群体的描述要足够长",
            "need_or_opportunity": "需求场景的描述要足够长",
            "product_name": "产品",
            "product_category": "智能协作平台",
            "key_benefit": "关键利益点的描述要足够长",
            "primary_alternative": "替代竞品",
            "primary_differentiation": "差异化点的描述要足够长",
            "confidence": "llm_inferred",
        },
        "category_strategy": {
            "chosen_category": "智能协作工具",
            "why_this_category": "选择此品类的理由要至少有三十个字符的详细描述说明这个品类的合理性",
            "competitors_implied": ["CompA"],
        },
    }


@pytest.mark.asyncio
async def test_s5_split_merge_produces_valid_payload():
    """S5 拆分 merge 后产出合法 S5PositioningPayload，cross-validator 通过。"""
    from src.schemas.scenarios.s5 import S5PositioningPayload

    phase2a = _build_phase2a_payload_for_merge()
    phase2b = _build_phase2b_payload_for_merge()

    orchestrator = WriterOrchestrator(llm=MagicMock())
    merged = orchestrator._merge_s5_payload(phase2a, phase2b)

    # 应能成功实例化（含 cross-validator 通过）
    model = S5PositioningPayload(**merged)
    assert model.scenario_type == "S5"
    assert len(model.vendor_profiles) == 2
    assert {vp.competitor_name for vp in model.vendor_profiles} == {"CompA", "CompB"}


@pytest.mark.asyncio
async def test_s5_phase2_split_routes_through_phase2_with_validation(monkeypatch):
    """_call_phase2_with_validation 在 scenario=S5 时应走拆分路径，返回 S5PositioningPayload。"""
    from src.schemas.scenarios.s5 import S5PositioningPayload

    phase2a = _build_phase2a_payload_for_merge()
    phase2b = _build_phase2b_payload_for_merge()

    orchestrator = WriterOrchestrator(llm=MagicMock())
    monkeypatch.setattr(
        orchestrator, "_call_s5_phase2a", AsyncMock(return_value=phase2a)
    )
    monkeypatch.setattr(
        orchestrator, "_call_s5_phase2b", AsyncMock(return_value=phase2b)
    )

    scenario_input = MagicMock()
    scenario_input.our_product_name = "MyProd"
    scenario_input.our_product_brief = "brief"
    scenario_input.industry = "test"
    scenario_input.analysis_context = "ctx"
    scenario_input.prior_trace_id = None

    result = await orchestrator._call_phase2_with_validation(
        scenario="S5",
        scenario_input=scenario_input,
        analysis={"summary": "test"},
        profiles=[],
        competitor_recommendations=None,
        prior_report_data=None,
        competitor_names=["CompA", "CompB"],
        competitor_basics=[{"name": "CompA"}, {"name": "CompB"}],
        discovered_urls=["https://a.com"],
        warnings=[],
    )

    assert isinstance(result, S5PositioningPayload)
    assert len(result.vendor_profiles) == 2
    # 拆分路径应该被调用
    orchestrator._call_s5_phase2a.assert_awaited_once()
    orchestrator._call_s5_phase2b.assert_awaited_once()


# ---------- 测试：phase 3 narrative 轻重试 ----------

@pytest.mark.asyncio
async def test_phase3_retry_once_then_succeed():
    """单 section 首次失败 + 重试成功 → 不出现 placeholder，总调用 = 2(p1+p2) + 5(首跑) + 1(重试) = 8。"""
    scenario_input, analysis, profiles = _make_phase3_full_run_inputs()

    phase1_outline = _make_valid_outline_dict("测试 outline")
    phase2_payload = _s1_payload_dict_with_weighted_scores()
    s1_section_types = [
        "overview",
        "vendor_profile_analysis",
        "feature_matrix_analysis",
        "jtbd_analysis",
        "roadmap_analysis",
    ]

    # 第 3 个 section 首次失败，重试时成功
    side_effects = [
        phase1_outline,                                         # phase 1
        phase2_payload,                                         # phase 2
        _make_valid_narrative_json(s1_section_types[0]),        # narrative 1 ok
        _make_valid_narrative_json(s1_section_types[1]),        # narrative 2 ok
        RuntimeError("LLM 偶发故障"),                            # narrative 3 首次失败
        _make_valid_narrative_json(s1_section_types[3]),        # narrative 4 ok
        _make_valid_narrative_json(s1_section_types[4]),        # narrative 5 ok
        _make_valid_narrative_json(s1_section_types[2]),        # narrative 3 重试成功
    ]

    mock_llm = MagicMock(spec=LLMClient)
    mock_llm.call_json = AsyncMock(side_effect=side_effects)
    orch = WriterOrchestrator(llm=mock_llm)

    # phase 4 会因 outline fixture 不完整而 raise，但 phase 3 应该 8 次调用
    with pytest.raises(Exception):
        await orch.write(
            scenario_input=scenario_input,
            analysis=analysis,
            profiles=profiles,
        )

    # 1(outline) + 1(payload) + 5(首跑) + 1(重试) = 8
    assert mock_llm.call_json.call_count == 8


@pytest.mark.asyncio
async def test_phase3_retry_once_then_still_fail_uses_placeholder():
    """单 section 首次失败 + 重试仍失败 → 占位降级，总调用 = 2 + 5 + 1(重试) = 8。"""
    scenario_input, analysis, profiles = _make_phase3_full_run_inputs()

    phase1_outline = _make_valid_outline_dict("测试 outline")
    phase2_payload = _s1_payload_dict_with_weighted_scores()
    s1_section_types = [
        "overview",
        "vendor_profile_analysis",
        "feature_matrix_analysis",
        "jtbd_analysis",
        "roadmap_analysis",
    ]

    # 第 3 个 section 首次失败，重试也失败
    side_effects = [
        phase1_outline,
        phase2_payload,
        _make_valid_narrative_json(s1_section_types[0]),
        _make_valid_narrative_json(s1_section_types[1]),
        RuntimeError("LLM 故障"),                               # narrative 3 首次失败
        _make_valid_narrative_json(s1_section_types[3]),
        _make_valid_narrative_json(s1_section_types[4]),
        RuntimeError("LLM 重试也失败"),                           # narrative 3 重试失败
    ]

    mock_llm = MagicMock(spec=LLMClient)
    mock_llm.call_json = AsyncMock(side_effect=side_effects)
    orch = WriterOrchestrator(llm=mock_llm)

    with pytest.raises(Exception):
        await orch.write(
            scenario_input=scenario_input,
            analysis=analysis,
            profiles=profiles,
        )

    # 总调用 = 2 + 5 + 1 = 8
    assert mock_llm.call_json.call_count == 8
