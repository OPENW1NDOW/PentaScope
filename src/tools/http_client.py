import asyncio
import logging
import time
from urllib.parse import urlparse

import httpx

from src.utils.config import settings

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
]

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Upgrade-Insecure-Requests": "1",
}


class HttpClient:
    """异步 HTTP 客户端，带超时、User-Agent 轮换和同域名频率控制"""

    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=settings.HTTP_TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENTS[0], **DEFAULT_HEADERS},
        )
        self._ua_index = 0
        self._last_request: dict[str, float] = {}

    def _rotate_ua(self):
        self._ua_index = (self._ua_index + 1) % len(USER_AGENTS)
        self.client.headers["User-Agent"] = USER_AGENTS[self._ua_index]

    async def _rate_limit(self, url: str):
        """同域名频率控制"""
        domain = urlparse(url).netloc
        if domain in self._last_request:
            elapsed = time.time() - self._last_request[domain]
            if elapsed < settings.COLLECT_INTERVAL:
                await asyncio.sleep(settings.COLLECT_INTERVAL - elapsed)
        self._last_request[domain] = time.time()

    async def get(self, url: str) -> str | None:
        """GET 请求，失败返回 None"""
        try:
            await self._rate_limit(url)
            self._rotate_ua()
            response = await self.client.get(url)
            if response.status_code == 200:
                return response.text
            logger.warning("[http] %s 返回状态码 %d", url, response.status_code)
            return None
        except httpx.TimeoutException:
            logger.warning("[http] %s 请求超时", url)
            return None
        except httpx.RequestError as e:
            logger.warning("[http] %s 请求失败: %s", url, e)
            return None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def close(self):
        await self.client.aclose()
