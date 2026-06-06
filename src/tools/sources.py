"""数据源插件：DataSource 基类 + iTunes 专源 + SerpAPI 搜索源 + 按 category 路由。

只实现 SerpAPI 一个搜索 provider（换 provider 各家响应格式不同需各写 parser，列入未来扩展）。
结构化专源（iTunes）结果不经过 quality_gate。
"""
import logging
from dataclasses import dataclass
from urllib.parse import quote

logger = logging.getLogger(__name__)

ITUNES_API_URL = "https://itunes.apple.com/search?term={name}&country=cn&entity=software&limit=3"


@dataclass
class SourceResult:
    """单条数据源结果：内容页 URL + 已抽取正文。"""
    url: str
    text: str


class ItunesSource:
    """iTunes Search API 专源（结构化，不过质量闸门）。"""

    name = "itunes"

    def __init__(self, http):
        self.http = http

    async def collect(self, competitor_name: str) -> list[SourceResult]:
        url = ITUNES_API_URL.format(name=quote(competitor_name))
        data = await self.http.get_json(url)
        if not data or not isinstance(data, dict):
            return []
        results = []
        for app in data.get("results", []):
            desc = app.get("description") or ""
            if not desc and not app.get("trackName"):
                continue
            text = (
                f"应用：{app.get('trackName', '')}\n"
                f"价格：{app.get('formattedPrice', '')}\n"
                f"评分：{app.get('averageUserRating', '')}（{app.get('userRatingCount', 0)} 条评价）\n"
                f"开发商：{app.get('sellerName', '')}\n"
                f"描述：{desc[:1000]}"
            )
            results.append(SourceResult(url=app.get("trackViewUrl", ""), text=text))
        return results


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


TAVILY_URL = "https://api.tavily.com/search?query={query}&search_depth=advanced&include_raw_content=true&max_results=5"


class TavilySource:
    """Tavily 搜索源：一次调用返回结果 + 每条清洗正文，吃掉搜索+选页+抓取+清洗。

    与 SerpApiSource 不同：search() 直接返回带正文的 SourceResult（非候选 dict）。
    key 走 api_key query 参数，日志由 HttpClient._redact_key 脱敏。
    """

    name = "tavily"

    def __init__(self, http, api_key: str):
        self.http = http
        self.api_key = api_key

    def available(self) -> bool:
        return bool(self.api_key)

    async def search(self, query: str) -> list[SourceResult]:
        if not self.available():
            return []
        url = TAVILY_URL.format(query=quote(query)) + f"&api_key={quote(self.api_key)}"
        data = await self.http.get_json(url)
        if not data or not isinstance(data, dict):
            return []
        results = []
        for item in data.get("results", []):
            text = item.get("raw_content") or item.get("content") or ""
            link = item.get("url", "")
            if text and link:
                results.append(SourceResult(url=link, text=text))
        return results


_SAAS_KEYWORDS = ("软件", "saas", "app", "应用", "工具", "平台", "service")


def normalize_category(category: str) -> str:
    """自由文本 category 规范化到路由键：saas / default。"""
    if not category:
        return "default"
    lowered = category.lower()
    if any(k in lowered for k in _SAAS_KEYWORDS):
        return "saas"
    return "default"


def build_pro_sources(category: str, http) -> list:
    """按规范化 category 返回结构化专源列表。硬件电商源列入未来扩展。"""
    key = normalize_category(category)
    if key == "saas":
        return [ItunesSource(http)]
    return []
