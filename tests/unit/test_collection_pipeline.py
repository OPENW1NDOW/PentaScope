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
async def test_no_key_skips_search_uses_pro_sources(monkeypatch):
    from src.tools.sources import SourceResult
    fake_source = MagicMock()
    fake_source.name = "itunes"
    fake_source.collect = AsyncMock(return_value=[SourceResult(url="https://x.com/app", text="支付宝介绍" * 30)])
    monkeypatch.setattr("src.agents.collection_pipeline.build_pro_sources",
                        lambda category, http: [fake_source])

    pipe = _pipeline(search_available=False)
    text, sources, trace = await pipe.collect("支付宝", "saas")
    assert "支付宝介绍" in text
    assert "https://x.com/app" in sources
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
async def test_concurrent_collect_no_name_crosstalk(monkeypatch):
    # 同一 pipeline 实例并发 collect 两个竞品，专源必须各收各的名字，不串
    from src.tools.sources import SourceResult

    received = []

    class RecordingSource:
        name = "rec"
        def __init__(self, http):
            pass
        async def collect(self, competitor_name):
            import asyncio
            await asyncio.sleep(0.01)  # 制造交错
            received.append(competitor_name)
            return [SourceResult(url=f"https://x/{competitor_name}", text=f"{competitor_name} 正文" * 30)]

    monkeypatch.setattr("src.agents.collection_pipeline.build_pro_sources",
                        lambda category, http: [RecordingSource(http)])
    search = MagicMock()
    search.available.return_value = False
    pipe = CollectionPipeline(llm=MagicMock(), http=MagicMock(), parser=MagicMock(),
                              search_source=search, max_top_n=3, pick_timeout=20, max_concurrency=5)
    import asyncio
    (textA, srcA, _), (textB, srcB, _) = await asyncio.gather(
        pipe.collect("竞品甲", "saas"),
        pipe.collect("竞品乙", "saas"),
    )
    # 各自的源 URL 必须只含自己的名字，不串
    assert "竞品甲" in textA and "竞品乙" not in textA
    assert "竞品乙" in textB and "竞品甲" not in textB


@pytest.mark.asyncio
async def test_llm_pick_used_when_key_present(monkeypatch):
    monkeypatch.setattr("src.agents.collection_pipeline.build_pro_sources", lambda category, http: [])
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
    text, sources, trace = await pipe.collect("X", "default")
    assert sources == ["https://b.com/y"]
    assert any(t.get("step") == "pick" and t.get("method") == "llm" for t in trace)


@pytest.mark.asyncio
async def test_llm_pick_timeout_falls_back_to_rule(monkeypatch):
    monkeypatch.setattr("src.agents.collection_pipeline.build_pro_sources", lambda category, http: [])
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
    text, sources, trace = await pipe.collect("X", "default")
    assert sources == ["https://a.com/pricing"]
    assert any(t.get("step") == "pick" and t.get("method") == "rule_fallback" for t in trace)


@pytest.mark.asyncio
async def test_no_key_makes_no_llm_call(monkeypatch):
    # 无 key 路径绝不调用 LLM 选页（保护集成测试 6 步序列）
    monkeypatch.setattr("src.agents.collection_pipeline.build_pro_sources", lambda category, http: [])
    search = MagicMock()
    search.available.return_value = False
    llm = MagicMock()
    llm.call_json = AsyncMock(return_value={"urls": []})
    pipe = CollectionPipeline(llm=llm, http=MagicMock(), parser=MagicMock(), search_source=search,
                              max_top_n=3, pick_timeout=20, max_concurrency=5)
    await pipe.collect("X", "default")
    llm.call_json.assert_not_called()
