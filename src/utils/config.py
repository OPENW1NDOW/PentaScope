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
    # LLM 配置（兼容旧 DOUBAO_* 环境变量名）
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "") or os.getenv("DOUBAO_API_KEY", "")
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "") or os.getenv("DOUBAO_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "") or os.getenv("DOUBAO_MODEL_EP", "ep-20260514111325-xjmj7")
    # 分层模型：FAST 用于 collector/recommender，PRO 用于 analyzer/writer/critic
    MODEL_FAST: str = os.getenv("MODEL_FAST", "") or os.getenv("LLM_MODEL", "") or os.getenv("DOUBAO_MODEL_EP", "ep-20260514111325-xjmj7")
    MODEL_PRO: str = os.getenv("MODEL_PRO", "") or os.getenv("LLM_MODEL", "") or os.getenv("DOUBAO_MODEL_EP", "ep-20260514111325-xjmj7")
    LLM_TIMEOUT: int = 360
    LLM_MAX_RETRIES: int = 2
    HTTP_TIMEOUT: int = 120
    COLLECT_INTERVAL: float = 2.0  # 同域名请求间隔（秒）
    MAX_RETRIES_INSPECTOR: int = 2
    # 数据源拓展
    SEARCH_TOP_N: int = _int_env("SEARCH_TOP_N", 5)
    TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")
    # Writer 4 阶段编排（v3 spec）
    WRITER_MAX_LLM_CALLS: int = _int_env("WRITER_MAX_LLM_CALLS", 18)
    WRITER_NARRATIVE_CONCURRENCY: int = _int_env("WRITER_NARRATIVE_CONCURRENCY", 3)


settings = Settings()
