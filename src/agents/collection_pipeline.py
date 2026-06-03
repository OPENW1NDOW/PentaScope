"""采集管线：搜索→选页→抓正文→质量闸门 + 专源并行 + 去重 + 全空兜底。

collector 的 tool 依赖。collect() 返回 (merged_text, sources, pipeline_trace)。
LLM 选页仅在有 key 且走搜索主线时发生——无 key 路径零新增 LLM 调用。
"""
import asyncio
import logging

from src.tools.quality_gate import is_low_quality
from src.tools.sources import build_pro_sources
from src.utils.config import settings

logger = logging.getLogger(__name__)

# 规则选页加分关键词（域名/路径）
_PATH_KEYWORDS = ("pricing", "price", "feature", "product", "docs", "help", "定价", "功能", "产品")


class CollectionPipeline:
    def __init__(self, llm, http, parser, search_source,
                 max_top_n: int = 3, pick_timeout: int = 20, max_concurrency: int = 5):
        self.llm = llm
        self.http = http
        self.parser = parser
        self.search_source = search_source
        self.max_top_n = max_top_n
        self.pick_timeout = pick_timeout
        self.max_concurrency = max_concurrency
        self._sem: asyncio.Semaphore | None = None

    def _semaphore(self) -> asyncio.Semaphore:
        # 实例级惰性创建，绑定首次使用时的事件循环；非 module-global
        if self._sem is None:
            self._sem = asyncio.Semaphore(self.max_concurrency)
        return self._sem

    def _rule_pick(self, candidates: list[dict], name: str, top_n: int) -> list[dict]:
        """零 LLM 规则打分选页：路径关键词 + 名称命中域名加分。"""
        def score(c: dict) -> int:
            url = (c.get("url") or "").lower()
            s = 0
            if any(k in url for k in _PATH_KEYWORDS):
                s += 2
            if name.lower() in url:
                s += 1
            return s
        ranked = sorted(candidates, key=score, reverse=True)
        picked = []
        seen = set()
        for c in ranked:
            url = c.get("url")
            if score(c) > 0 and url not in seen:
                picked.append(c)
                seen.add(url)
            if len(picked) >= top_n:
                break
        return picked

    async def _fetch_clean(self, url: str) -> str | None:
        """抓取并抽取正文，过质量闸门；低质/失败返回 None。"""
        async with self._semaphore():
            raw = await self.http.get(url)
        if raw is None:
            return None
        text = self.parser.extract_text(raw)
        if is_low_quality(text):
            return None
        return text

    async def _run_source(self, src, name):
        """运行单个专源，独立超时容错。"""
        try:
            return await asyncio.wait_for(src.collect(name), timeout=settings.HTTP_TIMEOUT)
        except Exception as e:  # noqa: BLE001
            logger.warning("[pipeline] 专源 %s 失败: %s", getattr(src, "name", "?"), e)
            return []

    async def collect(self, competitor_name: str, category: str):
        """返回 (merged_text, sources, pipeline_trace)。"""
        trace: list[dict] = []
        texts: list[str] = []
        sources: list[str] = []
        seen_urls: set[str] = set()

        pro_sources = build_pro_sources(category, self.http)
        trace.append({"step": "route", "category": category, "pro_sources": [s.name for s in pro_sources]})

        # 搜索主线：仅在 available 时（本任务用规则选页；LLM 选页在下一任务接）
        if self.search_source.available():
            trace.append({"step": "search", "provider": self.search_source.name})
            candidates = await self.search_source.search(f"{competitor_name} 产品 功能 定价")
            picked = self._rule_pick(candidates, competitor_name, self.max_top_n)
            trace.append({"step": "pick", "method": "rule", "picked": [c["url"] for c in picked]})
            fetched = await asyncio.gather(
                *[self._fetch_clean(c["url"]) for c in picked], return_exceptions=True
            )
            for c, t in zip(picked, fetched):
                if isinstance(t, str) and t and c["url"] not in seen_urls:
                    texts.append(t)
                    sources.append(c["url"])
                    seen_urls.add(c["url"])
        else:
            trace.append({"step": "search_skipped", "reason": "no_api_key"})

        # 专源并行
        results_per_source = await asyncio.gather(*[self._run_source(s, competitor_name) for s in pro_sources])
        for src, results in zip(pro_sources, results_per_source):
            for r in results:
                if r.url not in seen_urls:
                    texts.append(r.text)
                    if r.url:
                        sources.append(r.url)
                        seen_urls.add(r.url)
            trace.append({"step": "pro_source", "name": src.name, "results": len(results)})

        merged_text = "\n\n".join(texts)
        return merged_text, sources, trace
