import pytest
from unittest.mock import AsyncMock, MagicMock
from src.agents.collection_pipeline import CollectionPipeline
from src.tools.sources import SourceResult


@pytest.mark.asyncio
async def test_no_key_skips_search():
    # 无搜索 key 时跳过搜索主线，trace 标记 search_skipped
    search = MagicMock()
    search.available.return_value = False
    search.name = "tavily"
    pipe = CollectionPipeline(search_source=search)
    text, sources, trace, _ = await pipe.collect("支付宝")
    assert sources == []
    assert any(t.get("step") == "search_skipped" for t in trace)


@pytest.mark.asyncio
async def test_collect_returns_labeled_text():
    # labeled_text 给每段正文加【来源】锚点，供 collector 抽取时绑定来源
    tav = MagicMock()
    tav.available.return_value = True
    tav.name = "tavily"
    tav.search = AsyncMock(return_value=[
        SourceResult(url="https://a.com", text="正文A" * 30),
    ])
    pipe = CollectionPipeline(search_source=tav)
    merged, sources, trace, labeled = await pipe.collect("X")
    assert "正文A" in merged
    assert "【来源: https://a.com】" in labeled
    assert "正文A" in labeled
    assert sources == ["https://a.com"]


@pytest.mark.asyncio
async def test_low_quality_results_excluded_from_sources():
    # quality_gate 挡掉低质内容，sources 只剩有效的
    tav = MagicMock()
    tav.available.return_value = True
    tav.name = "tavily"
    tav.search = AsyncMock(return_value=[
        SourceResult(url="https://a.com/good", text="正文A" * 30),
        SourceResult(url="https://a.com/short", text="短"),  # 短内容被 is_low_quality 挡掉
    ])
    pipe = CollectionPipeline(search_source=tav)
    merged, sources, trace, _ = await pipe.collect("X")
    assert sources == ["https://a.com/good"]
    assert "正文A" in merged
    assert "短" not in merged


@pytest.mark.asyncio
async def test_dedup_same_url():
    # 同一 url 出现多次仅保留一条
    tav = MagicMock()
    tav.available.return_value = True
    tav.name = "tavily"
    tav.search = AsyncMock(return_value=[
        SourceResult(url="https://a.com", text="正文A" * 30),
        SourceResult(url="https://a.com", text="正文A 重复" * 30),
    ])
    pipe = CollectionPipeline(search_source=tav)
    _, sources, _, _ = await pipe.collect("X")
    assert sources == ["https://a.com"]


@pytest.mark.asyncio
async def test_trace_records_tavily_provider():
    # trace 应包含 search step + provider + tavily step + valid count
    tav = MagicMock()
    tav.available.return_value = True
    tav.name = "tavily"
    tav.search = AsyncMock(return_value=[
        SourceResult(url="https://a.com", text="正文A" * 30),
    ])
    pipe = CollectionPipeline(search_source=tav)
    _, _, trace, _ = await pipe.collect("X")
    assert any(t.get("step") == "search" and t.get("provider") == "tavily" for t in trace)
    # 06-09 改造：scenario 化多 query → trace step 改为 tavily_query；至少一条 results=1
    assert any(t.get("step") == "tavily_query" and t.get("results") == 1 for t in trace)


# ============ 06-09 (b) scenario 化多 query + (c) fallback 测试 ============

@pytest.mark.asyncio
async def test_scenario_picks_dedicated_queries():
    """传 scenario=S3 → 主 query 含定价相关关键词，与 S1 不同"""
    tav = MagicMock()
    tav.available.return_value = True
    tav.name = "tavily"
    tav.search = AsyncMock(return_value=[SourceResult(url="https://a.com", text="正文内容足够长" * 20)])
    pipe = CollectionPipeline(search_source=tav)
    await pipe.collect("飞书", scenario="S3")
    queries_called = [c.args[0] for c in tav.search.call_args_list]
    # S3 模板含 "定价"
    assert any("定价" in q for q in queries_called), f"S3 query 应含定价关键词，实际: {queries_called}"


@pytest.mark.asyncio
async def test_scenario_unknown_falls_back_to_default_query():
    """未知 scenario 走默认 '产品 功能 定价' query"""
    tav = MagicMock()
    tav.available.return_value = True
    tav.name = "tavily"
    tav.search = AsyncMock(return_value=[SourceResult(url="https://a.com", text="正文内容足够长" * 20)])
    pipe = CollectionPipeline(search_source=tav)
    await pipe.collect("飞书", scenario=None)
    queries_called = [c.args[0] for c in tav.search.call_args_list]
    assert any("产品 功能 定价" in q for q in queries_called)


@pytest.mark.asyncio
async def test_multi_query_results_dedup_by_url():
    """两个 query 都返回同一 URL → 去重，sources 只 1 条"""
    tav = MagicMock()
    tav.available.return_value = True
    tav.name = "tavily"
    tav.search = AsyncMock(return_value=[SourceResult(url="https://a.com", text="正文内容足够长" * 20)])
    pipe = CollectionPipeline(search_source=tav)
    _, sources, _, _ = await pipe.collect("飞书", scenario="S1")  # S1 有 2 条 query
    assert len(sources) == 1, f"去重后 sources 应=1，实际 {sources}"


@pytest.mark.asyncio
async def test_fallback_triggered_when_main_queries_empty():
    """主 query 全空 → 触发 fallback query (含 '官网')"""
    tav = MagicMock()
    tav.available.return_value = True
    tav.name = "tavily"
    # 主 query 都返空，fallback query 返回 1 条
    call_count = {"n": 0}
    async def search_side(q):
        call_count["n"] += 1
        if "官网" in q:  # fallback query
            return [SourceResult(url="https://x.com", text="兜底正文" * 30)]
        return []
    tav.search = AsyncMock(side_effect=search_side)
    pipe = CollectionPipeline(search_source=tav)
    _, sources, trace, _ = await pipe.collect("飞书", scenario="S1")
    assert sources == ["https://x.com"]
    assert any(t.get("step") == "tavily_fallback" for t in trace)


@pytest.mark.asyncio
async def test_fallback_skipped_when_main_queries_have_results():
    """主 query 已有结果 → 不走 fallback"""
    tav = MagicMock()
    tav.available.return_value = True
    tav.name = "tavily"
    tav.search = AsyncMock(return_value=[SourceResult(url="https://a.com", text="正文内容足够长" * 20)])
    pipe = CollectionPipeline(search_source=tav)
    _, _, trace, _ = await pipe.collect("飞书", scenario="S1")
    assert not any(t.get("step") == "tavily_fallback" for t in trace)


@pytest.mark.asyncio
async def test_one_query_exception_does_not_kill_others():
    """N 条主 query 中 1 条抛错 → 其他正常返回 + trace 记 error"""
    tav = MagicMock()
    tav.available.return_value = True
    tav.name = "tavily"
    async def search_side(q):
        if "用户评价" in q:
            raise RuntimeError("Tavily 临时挂")
        return [SourceResult(url=f"https://q-{q[:5]}.com", text="正文内容足够长" * 20)]
    tav.search = AsyncMock(side_effect=search_side)
    pipe = CollectionPipeline(search_source=tav)
    _, sources, trace, _ = await pipe.collect("飞书", scenario="S1")  # S1 有 "用户评价" 关键词
    assert len(sources) >= 1, "至少有一条 query 成功"
    assert any(t.get("step") == "tavily_query" and "error" in t for t in trace)
