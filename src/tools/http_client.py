import asyncio
import logging
import re
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

_KEY_QUERY_RE = re.compile(r"(api_key|apikey|key|token)=([^&\s]+)", re.IGNORECASE)


def _redact_key(url: str) -> str:
    """脱敏 URL 中的 key/token query 参数，用于安全日志。"""
    return _KEY_QUERY_RE.sub(r"\1=***", url)


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
        self._domain_locks: dict[str, asyncio.Lock] = {}
        self._ua_lock = asyncio.Lock()

    async def _rotate_ua(self):
        async with self._ua_lock:
            self._ua_index = (self._ua_index + 1) % len(USER_AGENTS)
            self.client.headers["User-Agent"] = USER_AGENTS[self._ua_index]

    async def _rate_limit(self, url: str):
        """同域名频率控制（per-domain 锁串行化 读-睡-写，避免并发击穿）"""
        domain = urlparse(url).netloc
        lock = self._domain_locks.setdefault(domain, asyncio.Lock())
        async with lock:
            if domain in self._last_request:
                elapsed = time.time() - self._last_request[domain]
                if elapsed < settings.COLLECT_INTERVAL:
                    await asyncio.sleep(settings.COLLECT_INTERVAL - elapsed)
            self._last_request[domain] = time.time()

    async def get(self, url: str) -> str | None:
        """GET 请求，失败返回 None"""
        try:
            await self._rate_limit(url)
            await self._rotate_ua()
            response = await self.client.get(url)
            if response.status_code == 200:
                return response.text
            logger.warning("[http] %s 返回状态码 %d", _redact_key(url), response.status_code)
            return None
        except httpx.TimeoutException:
            logger.warning("[http] %s 请求超时", _redact_key(url))
            return None
        except httpx.RequestError as e:
            logger.warning("[http] %s 请求失败: %s", _redact_key(url), _redact_key(str(e)))
            return None

    async def get_json(self, url: str, headers: dict | None = None) -> dict | list | None:
        """GET 请求并解析 JSON；header 局部传参不污染共享客户端；失败返回 None。

        与 get() 不同，本方法不轮换 User-Agent —— API 端点用 auth header 标识身份，无需伪装。
        """
        try:
            await self._rate_limit(url)
            response = await self.client.get(url, headers=headers)
            if response.status_code == 200:
                return response.json()
            logger.warning("[http] %s 返回状态码 %d", _redact_key(url), response.status_code)
            return None
        except httpx.TimeoutException:
            logger.warning("[http] %s 请求超时", _redact_key(url))
            return None
        except (httpx.RequestError, ValueError) as e:
            logger.warning("[http] %s 请求/解析失败: %s", _redact_key(url), _redact_key(str(e)))
            return None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def close(self):
        await self.client.aclose()
