"""采集管线：搜索→选页→抓正文→质量闸门 + 专源并行 + 去重 + 全空兜底。

collector 的 tool 依赖。collect() 返回 (merged_text, sources, pipeline_trace)。
LLM 选页仅在有 key 且走搜索主线时发生——无 key 路径零新增 LLM 调用。
"""
import asyncio
import logging

from src.tools.quality_gate import is_low_quality

logger = logging.getLogger(__name__)

# 规则选页加分关键词（域名/路径）
_PATH_KEYWORDS = ("pricing", "price", "feature", "product", "docs", "help", "定价", "功能", "产品")

PICK_SYSTEM = (
    "你是竞品资料筛选助手。给定候选网页列表（url/title/snippet），"
    "选出最可能含目标竞品官方产品/功能/定价信息的页面。"
    '只返回 JSON：{"urls": ["选中的url", ...]}，最多选 N 个，按相关度排序。'
)


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

    async def _llm_pick(self, candidates: list[dict], name: str, top_n: int) -> list[dict] | None:
        """LLM 选页，外层超时；超时/异常/解析失败返回 None（调用方退回规则）。"""
        listing = "\n".join(
            f"{i}. {c.get('url')} | {c.get('title', '')} | {c.get('snippet', '')}"
            for i, c in enumerate(candidates)
        )
        user = f"竞品：{name}\n最多选 {top_n} 个。候选：\n{listing}"
        try:
            result = await asyncio.wait_for(
                self.llm.call_json(PICK_SYSTEM, user), timeout=self.pick_timeout
            )
        except Exception as e:  # noqa: BLE001 — 含 TimeoutError；任何失败都退回规则选页
            logger.warning("[pipeline] LLM 选页失败/超时, 退回规则: %s", e)
            return None
        urls = result.get("urls") if isinstance(result, dict) else None
        if not isinstance(urls, list):
            return None
        by_url = {c.get("url"): c for c in candidates}
        picked = [by_url[u] for u in urls if u in by_url][:top_n]
        return picked or None

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

    async def _fetch_with_backfill(self, picked: list[dict], candidates: list[dict], seen_urls: set):
        """抓 picked；其中抓挂的用未选中候选（原序）顶替，直到补回 len(picked) 个有效正文或候选耗尽。
        返回 [(url, text), ...]，上限 len(picked)（不硬凑、不超过 LLM 选的数量）。"""
        target = len(picked)
        if target == 0:
            return []
        picked_urls = {c.get("url") for c in picked}
        backfill = [c for c in candidates if c.get("url") not in picked_urls]
        bf_idx = 0
        collected: list[tuple[str, str]] = []
        queue = list(picked)
        while queue and len(collected) < target:
            batch = queue
            queue = []
            fetched = await asyncio.gather(
                *[self._fetch_clean(c["url"]) for c in batch], return_exceptions=True
            )
            for c, t in zip(batch, fetched):
                if isinstance(t, str) and t and c["url"] not in seen_urls:
                    collected.append((c["url"], t))
                    seen_urls.add(c["url"])
                else:
                    while bf_idx < len(backfill):
                        cand = backfill[bf_idx]
                        bf_idx += 1
                        if cand.get("url") not in seen_urls:
                            queue.append(cand)
                            break
        return collected[:target]

    async def collect(self, competitor_name: str):
        """返回 (merged_text, sources, pipeline_trace, labeled_text)。

        labeled_text 在每段正文前加【来源: url】标记，供 collector 抽取时绑定来源。
        merged_text 保持原样（无标记），向后兼容既有消费方。
        """
        trace: list[dict] = []
        texts: list[str] = []
        labeled_parts: list[str] = []
        sources: list[str] = []
        seen_urls: set[str] = set()

        def _add(text: str, url: str):
            texts.append(text)
            labeled_parts.append(f"【来源: {url or '未知'}】\n{text}")

        # 搜索主线：仅在搜索源可用时
        if self.search_source.available():
            trace.append({"step": "search", "provider": self.search_source.name})
            if getattr(self.search_source, "returns_bodies", False) is True:
                # Tavily 路径：直接拿带正文结果，跳过选页+抓取，仍过质量闸门 + 去重
                tav_results = await self.search_source.search(
                    f"{competitor_name} 产品 功能 定价")
                valid = 0
                for r in tav_results:
                    if r.url and r.url not in seen_urls and not is_low_quality(r.text):
                        _add(r.text, r.url)
                        sources.append(r.url)
                        seen_urls.add(r.url)
                        valid += 1
                trace.append({"step": "tavily", "results": valid})
            else:
                # SerpAPI 路径：搜索→选页（失败退规则）→ 抓挂才补
                candidates = await self.search_source.search(f"{competitor_name} 产品 功能 定价")
                picked = await self._llm_pick(candidates, competitor_name, self.max_top_n)
                if picked is not None:
                    trace.append({"step": "pick", "method": "llm", "picked": [c["url"] for c in picked]})
                else:
                    picked = self._rule_pick(candidates, competitor_name, self.max_top_n)
                    trace.append({"step": "pick", "method": "rule_fallback", "picked": [c["url"] for c in picked]})
                fetched = await self._fetch_with_backfill(picked, candidates, seen_urls)
                for url, t in fetched:
                    _add(t, url)
                    sources.append(url)
                trace.append({"step": "fetch", "valid": len(fetched), "picked": len(picked)})
        else:
            trace.append({"step": "search_skipped", "reason": "no_api_key"})

        merged_text = "\n\n".join(texts)
        labeled_text = "\n\n".join(labeled_parts)
        return merged_text, sources, trace, labeled_text
