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
            text = (
                f"应用：{app.get('trackName', '')}\n"
                f"价格：{app.get('formattedPrice', '')}\n"
                f"评分：{app.get('averageUserRating', '')}（{app.get('userRatingCount', 0)} 条评价）\n"
                f"开发商：{app.get('sellerName', '')}\n"
                f"描述：{desc[:1000]}"
            )
            results.append(SourceResult(url=app.get("trackViewUrl", ""), text=text))
        return results
