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
    assert any(t.get("step") == "tavily" and t.get("results") == 1 for t in trace)
