import json
import logging
from openai import AsyncOpenAI
from src.utils.config import settings

logger = logging.getLogger(__name__)


class LLMClient:
    """Doubao LLM 客户端（OpenAI 兼容格式）"""

    def __init__(self, api_key: str = "", base_url: str = "", model_ep: str = ""):
        self.api_key = api_key or settings.DOUBAO_API_KEY
        self.base_url = base_url or settings.DOUBAO_BASE_URL
        self.model_ep = model_ep or settings.DOUBAO_MODEL_EP
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=settings.LLM_TIMEOUT,
        )

    async def call_json(self, system_prompt: str, user_prompt: str) -> dict:
        """调用 LLM 并要求返回 JSON，自动重试解析失败的情况"""
        last_error = None
        for attempt in range(settings.LLM_MAX_RETRIES + 1):
            try:
                response = await self.client.chat.completions.create(
                    model=self.model_ep,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    timeout=settings.LLM_TIMEOUT,
                )
                content = response.choices[0].message.content
                # strict=False 允许字符串值内的裸控制字符（LLM 常在内容里直接输出换行）
                return json.loads(self._strip_json_fence(content), strict=False)
            except (json.JSONDecodeError, KeyError, IndexError) as e:
                last_error = e
                logger.warning(
                    "[llm] JSON 解析失败 (attempt %d/%d): %s",
                    attempt + 1,
                    settings.LLM_MAX_RETRIES + 1,
                    e,
                )
                continue

        raise ValueError(
            f"Failed to parse LLM response as JSON after {settings.LLM_MAX_RETRIES + 1} attempts: {last_error}"
        )

    @staticmethod
    def _strip_json_fence(content: str) -> str:
        """剥离模型可能输出的 ```json ... ``` 代码块包裹"""
        text = content.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
        return text.strip()

    async def call_text(self, system_prompt: str, user_prompt: str) -> str:
        """调用 LLM 返回纯文本"""
        response = await self.client.chat.completions.create(
            model=self.model_ep,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            timeout=settings.LLM_TIMEOUT,
        )
        return response.choices[0].message.content
