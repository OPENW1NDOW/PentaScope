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
