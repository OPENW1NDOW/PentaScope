import json
import logging
import re
from openai import AsyncOpenAI
from src.utils.config import settings

logger = logging.getLogger(__name__)

# 合法的 JSON 转义起始字符：\\ \" \/ \b \f \n \r \t \uXXXX
# 凡是反斜杠后接非这些字符的，均视为 LLM 输出的"裸反斜杠"，需自动转义为 \\
_BARE_BACKSLASH_PATTERN = re.compile(r'\\(?!["\\/bfnrtu])')


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
            # 关掉内部 retry：OpenAI SDK 默认 max_retries=2 会与外层 LLM_MAX_RETRIES 嵌套
            # 形成 3×3=9 次 × 120s ≈ 18 分钟最坏耗时（trace 20260609-150301-df17ff 实证）
            max_retries=0,
        )

    async def call_json(
        self, system_prompt: str, user_prompt: str, *, max_tokens: int | None = None
    ) -> dict:
        """调用 LLM 并要求返回 JSON，自动重试解析失败的情况"""
        extra_kwargs: dict = {}
        if max_tokens is not None:
            extra_kwargs["max_tokens"] = max_tokens
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
                    **extra_kwargs,
                )
                content = response.choices[0].message.content
                stripped = self._strip_json_fence(content)
                # strict=False 允许字符串值内的裸控制字符（LLM 常在内容里直接输出换行）
                try:
                    return json.loads(stripped, strict=False)
                except json.JSONDecodeError as inner:
                    # 二次兜底：转义所有"非法"裸反斜杠（LLM 常在 path/regex/markdown 里漏转义 \）
                    fixed = _BARE_BACKSLASH_PATTERN.sub(r'\\\\', stripped)
                    try:
                        return json.loads(fixed, strict=False)
                    except json.JSONDecodeError as fallback_err:
                        # 二次兜底也失败：把失败位置前后 200 字符 dump 出来便于定位
                        pos = fallback_err.pos
                        ctx = fixed[max(0, pos - 100):pos + 100]
                        logger.warning(
                            "[llm] 反斜杠兜底也失败 char=%d, 原始/修复后报错均存在; 上下文片段: %r",
                            pos, ctx,
                        )
                        raise inner  # 抛原始错误，让外层 catch 走 attempt 重试
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
