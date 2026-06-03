import os
from dotenv import load_dotenv

load_dotenv()


def _int_env(name: str, default: int) -> int:
    """读取整数环境变量，非法值回落默认，绝不在 import 时抛错"""
    try:
        return int(os.getenv(name) or default)
    except (TypeError, ValueError):
        return default


class Settings:
    DOUBAO_API_KEY: str = os.getenv("DOUBAO_API_KEY", "")
    DOUBAO_BASE_URL: str = os.getenv("DOUBAO_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
    DOUBAO_MODEL_EP: str = os.getenv("DOUBAO_MODEL_EP", "ep-20260514111325-xjmj7")
    LLM_TIMEOUT: int = 120
    LLM_MAX_RETRIES: int = 2
    HTTP_TIMEOUT: int = 30
    COLLECT_INTERVAL: float = 2.0  # 同域名请求间隔（秒）
    MAX_RETRIES_INSPECTOR: int = 2
    # 数据源拓展
    SEARCH_API_KEY: str = os.getenv("SEARCH_API_KEY", "")
    SEARCH_TOP_N: int = _int_env("SEARCH_TOP_N", 3)
    PICK_LLM_TIMEOUT: int = _int_env("PICK_LLM_TIMEOUT", 20)
    MAX_FETCH_CONCURRENCY: int = _int_env("MAX_FETCH_CONCURRENCY", 5)


settings = Settings()
