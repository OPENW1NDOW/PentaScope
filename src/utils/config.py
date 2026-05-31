import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    DOUBAO_API_KEY: str = os.getenv("DOUBAO_API_KEY", "")
    DOUBAO_BASE_URL: str = os.getenv("DOUBAO_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
    DOUBAO_MODEL_EP: str = os.getenv("DOUBAO_MODEL_EP", "ep-20260514111325-xjmj7")
    LLM_TIMEOUT: int = 30
    LLM_MAX_RETRIES: int = 2
    HTTP_TIMEOUT: int = 30
    COLLECT_INTERVAL: float = 2.0  # 同域名请求间隔（秒）
    MAX_RETRIES_INSPECTOR: int = 2


settings = Settings()
