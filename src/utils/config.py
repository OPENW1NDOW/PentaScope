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
    # 分层模型：FAST 用于 collector/outline 等简单任务，PRO 用于 analyzer/writer/critic 等强推理任务
    MODEL_FAST: str = os.getenv("MODEL_FAST", os.getenv("DOUBAO_MODEL_EP", "ep-20260514111325-xjmj7"))
    MODEL_PRO: str = os.getenv("MODEL_PRO", os.getenv("DOUBAO_MODEL_EP", "ep-20260514111325-xjmj7"))
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
