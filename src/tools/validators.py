import logging
import httpx
from pydantic import BaseModel, ValidationError
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class SchemaValidator:
    """Pydantic Schema 校验器"""

    @staticmethod
    def validate(schema_class: type[BaseModel], data: dict) -> BaseModel:
        """校验数据是否符合 Schema，失败抛出 ValueError"""
        try:
            return schema_class(**data)
        except ValidationError as e:
            logger.error("[validator] Schema 校验失败: %s", e)
            raise ValueError(f"Schema validation failed: {e}") from e

    @staticmethod
    def validate_dict(data: dict, schema_class: type[BaseModel]) -> BaseModel:
        """同 validate，参数顺序不同"""
        return SchemaValidator.validate(schema_class, data)


class UrlValidator:
    """URL 校验器"""

    @staticmethod
    def is_valid_format(url: str) -> bool:
        """检查 URL 格式是否合法"""
        if not url:
            return False
        try:
            result = urlparse(url)
            return all([result.scheme in ("http", "https"), result.netloc])
        except Exception:
            return False

    @staticmethod
    async def check_url(url: str, timeout: int = 10) -> bool:
        """检查 URL 是否可访问"""
        if not UrlValidator.is_valid_format(url):
            return False
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                response = await client.head(url)
                return response.status_code < 400
        except (httpx.RequestError, httpx.TimeoutException):
            return False
