"""URL 归一化：用于 coverage 计算时的 URL 比较。"""
from urllib.parse import urlparse, urlunparse


def normalize_url(url: str) -> str:
    """归一化 URL：统一 https / 去尾 slash / 去 fragment。"""
    parsed = urlparse(url)
    scheme = "https"
    path = parsed.path.rstrip("/")
    return urlunparse((scheme, parsed.netloc, path, parsed.params, parsed.query, ""))
