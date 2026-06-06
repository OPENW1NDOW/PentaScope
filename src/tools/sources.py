"""数据源插件：SerpAPI 搜索源 + Tavily 搜索源。

搜索 provider 由 SEARCH_PROVIDER 配置选择；换 provider 各家响应格式不同需各写 parser。
"""
import logging
from dataclasses import dataclass
from urllib.parse import quote

from src.utils.config import settings

logger = logging.getLogger(__name__)


@dataclass
class SourceResult:
    """单条数据源结果：内容页 URL + 已抽取正文。"""
    url: str
    text: str


SERPAPI_URL = "https://serpapi.com/search?engine=google&q={query}&num=20"


class SerpApiSource:
    """SerpAPI 搜索源：search(query) -> 候选 [{url,title,snippet}]。

    key 走 api_key query 参数（SerpAPI 标准用法；Bearer header 遇非 ASCII query 会 401）。
    日志由 HttpClient._redact_key 脱敏 api_key，不明文泄漏。
    """

    name = "serpapi"

    def __init__(self, http, api_key: str):
        self.http = http
        self.api_key = api_key

    def available(self) -> bool:
        return bool(self.api_key)

    async def search(self, query: str) -> list[dict]:
        if not self.available():
            return []
        url = SERPAPI_URL.format(query=quote(query)) + f"&api_key={quote(self.api_key)}"
        data = await self.http.get_json(url)
        if not data or not isinstance(data, dict):
            return []
        candidates = []
        for item in data.get("organic_results", []):
            link = item.get("link")
            if link:
                candidates.append({
                    "url": link,
                    "title": item.get("title", ""),
                    "snippet": item.get("snippet", ""),
                })
        return candidates


TAVILY_URL = "https://api.tavily.com/search"


class TavilySource:
    """Tavily 搜索源：一次调用返回结果 + 每条清洗正文，吃掉搜索+选页+抓取+清洗。

    与 SerpApiSource 不同：search() 直接返回带正文的 SourceResult（非候选 dict）。
    按 Tavily 官方契约：POST + JSON body，key 走 Authorization: Bearer header。
    key 在 header 中、不进 URL，日志不会明文打出。
    """

    name = "tavily"
    returns_bodies = True  # search() 直接返回带正文 SourceResult，collect 据此跳过选页+抓取

    def __init__(self, http, api_key: str):
        self.http = http
        self.api_key = api_key

    def available(self) -> bool:
        return bool(self.api_key)

    async def search(self, query: str) -> list[SourceResult]:
        if not self.available():
            return []
        body = {
            "query": query,
            "search_depth": "advanced",
            "include_raw_content": True,
            "max_results": settings.SEARCH_TOP_N,
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}
        data = await self.http.post_json(TAVILY_URL, body, headers=headers)
        if not data or not isinstance(data, dict):
            return []
        results = []
        for item in data.get("results", []):
            text = item.get("raw_content") or item.get("content") or ""
            link = item.get("url", "")
            if text and link:
                results.append(SourceResult(url=link, text=text))
        return results
