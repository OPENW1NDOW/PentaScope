"""采集管线：Tavily 搜索 → 质量闸门 → 全空兜底。

collector 的 tool 依赖。collect() 返回 (merged_text, sources, pipeline_trace, labeled_text)。
Tavily 一次调用直返带正文 SourceResult，跳过传统选页/抓取步骤。
"""
import logging

from src.tools.quality_gate import is_low_quality

logger = logging.getLogger(__name__)


class CollectionPipeline:
    def __init__(self, search_source):
        self.search_source = search_source

    async def collect(self, competitor_name: str, category: str | None = None):
        """采集一个竞品的正文 + 来源 + 管线追踪。

        Returns:
            (merged_text, sources, trace, labeled_text)
        """
        texts: list[str] = []
        labeled_parts: list[str] = []
        sources: list[str] = []
        seen_urls: set[str] = set()
        trace: list[dict] = []

        def _add(text: str, url: str) -> None:
            texts.append(text)
            labeled_parts.append(f"【来源: {url}】\n{text}")

        # 搜索主线：仅在搜索源可用时
        if self.search_source.available():
            trace.append({"step": "search", "provider": self.search_source.name})
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
            trace.append({"step": "search_skipped", "reason": "no_api_key"})

        merged_text = "\n\n".join(texts)
        labeled_text = "\n\n".join(labeled_parts)
        return merged_text, sources, trace, labeled_text
