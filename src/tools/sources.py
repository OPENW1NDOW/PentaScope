"""数据源插件：Tavily 搜索源（唯一）。

06-07 弃用 SerpAPI 后单 provider 收敛。
"""
import logging
from dataclasses import dataclass

from src.utils.config import settings

logger = logging.getLogger(__name__)


class TavilyAuthError(Exception):
    """[#13] Tavily 鉴权失败（401/403，key 错误/失效），需与「合法无结果」区分。"""


@dataclass
class SourceResult:
    """单条数据源结果：内容页 URL + 已抽取正文。"""
    url: str
    text: str
    title: str = ""
    snippet: str = ""


TAVILY_URL = "https://api.tavily.com/search"


class TavilySource:
    """Tavily 搜索源：一次调用返回结果 + 每条清洗正文，吃掉搜索+选页+抓取+清洗。

    search() 直接返回带正文的 SourceResult。
    按 Tavily 官方契约：POST + JSON body，key 走 Authorization: Bearer header。
    key 在 header 中、不进 URL，日志不会明文打出。

    [#13] 401/403（key 错误/失效）抛 TavilyAuthError，让 pipeline/collector 感知，
    而非静默返回 [] 与「合法无结果」混淆。
    """

    name = "tavily"
    returns_bodies = True  # 占位标记：当前仅 Tavily 走带正文路径，未来若有不带正文 provider 需引入条件分支

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
        data, status = await self.http.post_json_with_status(TAVILY_URL, body, headers=headers)
        # [#13] 401/403 → 鉴权失败，抛异常让上层感知（避免配错 key 却产全占位报告无信号）
        if status in (401, 403):
            raise TavilyAuthError(
                f"Tavily 鉴权失败（HTTP {status}），请检查 TAVILY_API_KEY 是否正确/有效"
            )
        if not data or not isinstance(data, dict):
            return []
        results = []
        for item in data.get("results", []):
            text = item.get("raw_content") or item.get("content") or ""
            link = item.get("url", "")
            if text and link:
                results.append(SourceResult(
                    url=link,
                    text=text,
                    title=item.get("title", ""),
                    snippet=item.get("content", ""),
                ))
        return results
