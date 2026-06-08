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
    data_sources: list[str],
    recent_urls: list[str],
    review_urls: list[str],
    name: str = "竞品A",
) -> CompetitorProfile:
    """构造最小合法 CompetitorProfile，3 个来源可分别注入 URL"""
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
