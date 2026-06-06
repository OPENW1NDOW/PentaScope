import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock
from src.agents.collection_pipeline import CollectionPipeline


def _pipeline(search_available=False, **kw):
    search = MagicMock()
    search.available.return_value = search_available
    search.search = AsyncMock(return_value=[])
    search.name = "serpapi"
    return CollectionPipeline(
        llm=MagicMock(), http=MagicMock(), parser=MagicMock(),
        search_source=search, max_top_n=3, pick_timeout=20, max_concurrency=5, **kw,
    )


@pytest.mark.asyncio
async def test_no_key_skips_search():
    # 无搜索 key 时跳过搜索主线，trace 标记 search_skipped
    pipe = _pipeline(search_available=False)
    text, sources, trace, _ = await pipe.collect("支付宝")
    assert sources == []
    assert any(t.get("step") == "search_skipped" for t in trace)


def test_rule_pick_prefers_official_and_pricing_paths():
    pipe = _pipeline()
    cands = [
        {"url": "https://random-blog.com/post", "title": "blog", "snippet": ""},
        {"url": "https://alipay.com/pricing", "title": "定价", "snippet": ""},
        {"url": "https://alipay.com/features", "title": "功能", "snippet": ""},
    ]
    picked = pipe._rule_pick(cands, "支付宝", top_n=2)
    urls = [c["url"] for c in picked]
    assert "https://alipay.com/pricing" in urls
    assert "https://alipay.com/features" in urls
    assert "https://random-blog.com/post" not in urls


@pytest.mark.asyncio
async def test_llm_pick_used_when_key_present():
    search = MagicMock()
    search.available.return_value = True
    search.name = "serpapi"
    search.search = AsyncMock(return_value=[
        {"url": "https://a.com/x", "title": "A", "snippet": ""},
        {"url": "https://b.com/y", "title": "B", "snippet": ""},
    ])
    llm = MagicMock()
    llm.call_json = AsyncMock(return_value={"urls": ["https://b.com/y"]})
    parser = MagicMock()
    parser.extract_text.return_value = "有效正文" * 40
    http = MagicMock()
    http.get = AsyncMock(return_value="<html>x</html>")
    pipe = CollectionPipeline(llm=llm, http=http, parser=parser, search_source=search,
                              max_top_n=3, pick_timeout=20, max_concurrency=5)
    text, sources, trace, _ = await pipe.collect("X")
    assert sources == ["https://b.com/y"]
    assert any(t.get("step") == "pick" and t.get("method") == "llm" for t in trace)


@pytest.mark.asyncio
async def test_llm_pick_timeout_falls_back_to_rule():
    search = MagicMock()
    search.available.return_value = True
    search.name = "serpapi"
    search.search = AsyncMock(return_value=[{"url": "https://a.com/pricing", "title": "", "snippet": ""}])

    async def hang(*a, **k):
        await asyncio.sleep(10)

    llm = MagicMock()
    llm.call_json = AsyncMock(side_effect=hang)
    parser = MagicMock()
    parser.extract_text.return_value = "有效正文" * 40
    http = MagicMock()
    http.get = AsyncMock(return_value="<html>x</html>")
    pipe = CollectionPipeline(llm=llm, http=http, parser=parser, search_source=search,
                              max_top_n=3, pick_timeout=0.05, max_concurrency=5)
    text, sources, trace, _ = await pipe.collect("X")
    assert sources == ["https://a.com/pricing"]
    assert any(t.get("step") == "pick" and t.get("method") == "rule_fallback" for t in trace)


@pytest.mark.asyncio
async def test_no_key_makes_no_llm_call():
    # 无 key 路径绝不调用 LLM 选页（保护集成测试 6 步序列）
    search = MagicMock()
    search.available.return_value = False
    llm = MagicMock()
    llm.call_json = AsyncMock(return_value={"urls": []})
    pipe = CollectionPipeline(llm=llm, http=MagicMock(), parser=MagicMock(), search_source=search,
                              max_top_n=3, pick_timeout=20, max_concurrency=5)
    await pipe.collect("X")
    llm.call_json.assert_not_called()


@pytest.mark.asyncio
async def test_llm_pick_malformed_result_falls_back_to_rule():
    # LLM 返回畸形结果（urls 不是 list）→ 退回规则选页
    search = MagicMock()
    search.available.return_value = True
    search.name = "serpapi"
    search.search = AsyncMock(return_value=[{"url": "https://a.com/pricing", "title": "", "snippet": ""}])
    llm = MagicMock()
    llm.call_json = AsyncMock(return_value={"urls": "notalist"})  # 畸形
    parser = MagicMock()
    parser.extract_text.return_value = "有效正文" * 40
    http = MagicMock()
    http.get = AsyncMock(return_value="<html>x</html>")
    pipe = CollectionPipeline(llm=llm, http=http, parser=parser, search_source=search,
                              max_top_n=3, pick_timeout=20, max_concurrency=5)
    text, sources, trace, _ = await pipe.collect("X")
    assert sources == ["https://a.com/pricing"]
    assert any(t.get("step") == "pick" and t.get("method") == "rule_fallback" for t in trace)


@pytest.mark.asyncio
async def test_soft404_page_excluded_from_sources():
    search = MagicMock()
    search.available.return_value = True
    search.name = "serpapi"
    search.search = AsyncMock(return_value=[{"url": "https://a.com/404page", "title": "", "snippet": ""}])
    llm = MagicMock()
    llm.call_json = AsyncMock(return_value={"urls": ["https://a.com/404page"]})
    parser = MagicMock()
    parser.extract_text.return_value = "404 页面不存在"  # soft-404, gate drops it
    http = MagicMock()
    http.get = AsyncMock(return_value="<html>404</html>")
    pipe = CollectionPipeline(llm=llm, http=http, parser=parser, search_source=search,
                              max_top_n=3, pick_timeout=20, max_concurrency=5)
    text, sources, trace, _ = await pipe.collect("X")
    assert sources == []
    assert "页面不存在" not in text


@pytest.mark.asyncio
async def test_collect_returns_labeled_text():
    # labeled_text 给每段正文加【来源】锚点，供 collector 抽取时绑定来源。经 Tavily 主线构造。
    from src.tools.sources import SourceResult

    tav = MagicMock()
    tav.available.return_value = True
    tav.name = "tavily"
    tav.returns_bodies = True
    tav.search = AsyncMock(return_value=[
        SourceResult(url="https://a.com", text="正文A" * 30),
    ])
    pipe = CollectionPipeline(llm=MagicMock(), http=MagicMock(), parser=MagicMock(),
                              search_source=tav, max_top_n=5, pick_timeout=20, max_concurrency=5)
    merged, sources, trace, labeled = await pipe.collect("X")
    assert "正文A" in merged
    assert "【来源: https://a.com】" in labeled
    assert "正文A" in labeled
    assert sources == ["https://a.com"]


@pytest.mark.asyncio
async def test_replenish_fills_from_pool_when_picked_fail():
    search = MagicMock()
    search.available.return_value = True
    search.name = "serpapi"
    cands = [{"url": f"https://s/{i}", "title": "", "snippet": ""} for i in range(5)]
    search.search = AsyncMock(return_value=cands)

    pipe = CollectionPipeline(llm=MagicMock(), http=MagicMock(), parser=MagicMock(),
                              search_source=search, max_top_n=2, pick_timeout=20, max_concurrency=5)
    pipe._llm_pick = AsyncMock(return_value=[cands[0], cands[1]])

    async def fake_fetch(url):
        idx = int(url.rsplit("/", 1)[1])
        return None if idx < 2 else f"正文{idx}" * 30
    pipe._fetch_clean = AsyncMock(side_effect=fake_fetch)

    text, sources, trace, labeled = await pipe.collect("X")
    assert len(sources) == 2
    assert all("https://s/" in s for s in sources)


@pytest.mark.asyncio
async def test_replenish_degrades_below_n_when_pool_exhausted():
    search = MagicMock()
    search.available.return_value = True
    search.name = "serpapi"
    cands = [{"url": f"https://s/{i}", "title": "", "snippet": ""} for i in range(3)]
    search.search = AsyncMock(return_value=cands)
    pipe = CollectionPipeline(llm=MagicMock(), http=MagicMock(), parser=MagicMock(),
                              search_source=search, max_top_n=5, pick_timeout=20, max_concurrency=5)
    pipe._llm_pick = AsyncMock(return_value=cands)
    pipe._fetch_clean = AsyncMock(return_value=None)
    text, sources, trace, labeled = await pipe.collect("X")
    assert sources == []


@pytest.mark.asyncio
async def test_backfill_does_not_pad_beyond_picked():
    search = MagicMock()
    search.available.return_value = True
    search.name = "serpapi"
    cands = [{"url": f"https://s/{i}", "title": "", "snippet": ""} for i in range(6)]
    search.search = AsyncMock(return_value=cands)
    pipe = CollectionPipeline(llm=MagicMock(), http=MagicMock(), parser=MagicMock(),
                              search_source=search, max_top_n=5, pick_timeout=20, max_concurrency=5)
    pipe._llm_pick = AsyncMock(return_value=[cands[0], cands[1]])
    pipe._fetch_clean = AsyncMock(return_value="正文" * 30)
    text, sources, trace, labeled = await pipe.collect("X")
    assert sources == ["https://s/0", "https://s/1"]


@pytest.mark.asyncio
async def test_tavily_mainline_skips_pick_and_fetch():
    from src.tools.sources import SourceResult
    tav = MagicMock()
    tav.available.return_value = True
    tav.name = "tavily"
    tav.returns_bodies = True
    tav.search = AsyncMock(return_value=[
        SourceResult(url="https://feishu.cn/a", text="飞书正文" * 30),
        SourceResult(url="https://feishu.cn/b", text="短"),  # quality_gate 挡掉
    ])
    pipe = CollectionPipeline(llm=MagicMock(), http=MagicMock(), parser=MagicMock(),
                              search_source=tav, max_top_n=5, pick_timeout=20, max_concurrency=5)
    pipe._llm_pick = AsyncMock(side_effect=AssertionError("不应调用选页"))
    pipe._fetch_with_backfill = AsyncMock(side_effect=AssertionError("不应调用抓取"))
    text, sources, trace, labeled = await pipe.collect("飞书")
    assert "飞书正文" in text
    assert sources == ["https://feishu.cn/a"]
    assert any(t.get("step") == "tavily" for t in trace)
