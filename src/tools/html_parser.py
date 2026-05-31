import logging

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class HtmlParser:
    """HTML 解析器，基于 BeautifulSoup"""

    def extract_text(self, html: str) -> str:
        """提取页面纯文本"""
        if not html:
            return ""
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        return soup.get_text(separator="\n", strip=True)

    def extract_links(self, html: str, base_url: str = "") -> list[dict[str, str]]:
        """提取所有链接"""
        if not html:
            return []
        soup = BeautifulSoup(html, "html.parser")
        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith(("http://", "https://")):
                links.append({"url": href, "text": a.get_text(strip=True)})
        return links

    def extract_meta(self, html: str) -> dict[str, str]:
        """提取 meta 标签"""
        if not html:
            return {}
        soup = BeautifulSoup(html, "html.parser")
        meta = {}
        for tag in soup.find_all("meta"):
            name = tag.get("name", tag.get("property", ""))
            content = tag.get("content", "")
            if name and content:
                meta[name] = content
        return meta

    def extract_elements(self, html: str, selector: str) -> list[str]:
        """按 CSS 选择器提取元素文本"""
        if not html:
            return []
        soup = BeautifulSoup(html, "html.parser")
        return [el.get_text(strip=True) for el in soup.select(selector)]
