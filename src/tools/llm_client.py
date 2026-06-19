import json
import logging
import re
from openai import AsyncOpenAI
from src.utils.config import settings

logger = logging.getLogger(__name__)

# 合法的 JSON 转义起始字符：\\ \" \/ \b \f \n \r \t \uXXXX
# 凡是反斜杠后接非这些字符的，均视为 LLM 输出的"裸反斜杠"，需自动转义为 \\
_BARE_BACKSLASH_PATTERN = re.compile(r'\\(?!["\\/bfnrtu])')


def _fix_unescaped_quotes_in_values(text: str) -> str:
    """修复 JSON 字符串值内未转义的 ASCII 双引号。

    LLM 常输出类似 {"rationale": "从"设计画布"扩展到"产品原型""} 的内容，
    其中"设计画布"的双引号是中文引用而非 JSON 结构性引号，导致解析失败。

    策略：用状态机扫描，在字符串值内部遇到的 " 若后跟非 JSON 结构字符
    （即不是 , : } ] 或空白），则认定为内容引号，替换为中文引号 “/”。
    """
    result = []
    i = 0
    n = len(text)
    in_string = False

    while i < n:
        ch = text[i]

        if not in_string:
            result.append(ch)
            if ch == '”':
                in_string = True
            i += 1
        else:
            if ch == '\\' and i + 1 < n:
                result.append(ch)
                result.append(text[i + 1])
                i += 2
            elif ch == '”':
                after = i + 1
                while after < n and text[after] in ' \t\r\n':
                    after += 1
                if after >= n or text[after] in ',:]}\n\r':
                    result.append(ch)
                    in_string = False
                else:
                    result.append('“')
                i += 1
            else:
                result.append(ch)
                i += 1

    return ''.join(result)


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
                # [2026-06-19] 记录 finish_reason + 输出 token 数，便于判定撞 max_tokens 上限（机制 A）
                # vs LLM 自身抽风（机制 B）。finish_reason="length" → 机制 A；"stop" → 机制 B 或正常
                finish_reason = getattr(response.choices[0], "finish_reason", None)
                usage = getattr(response, "usage", None)
                completion_tokens = getattr(usage, "completion_tokens", None) if usage else None
                req_max_tokens = extra_kwargs.get("max_tokens")
                logger.info(
                    "[llm] call_json finish_reason=%s completion_tokens=%s max_tokens=%s",
                    finish_reason, completion_tokens, req_max_tokens,
                )
                if finish_reason == "length":
                    logger.warning(
                        "[llm] 输出撞 max_tokens 上限（机制 A）: completion_tokens=%s, max_tokens=%s",
                        completion_tokens, req_max_tokens,
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
                    except json.JSONDecodeError:
                        pass

                    # 三次兜底：修复字符串值内未转义的 ASCII 双引号
                    # LLM 常输出 "从"设计"到"开发"" 这类中文引用，导致 Expecting ',' delimiter
                    fixed2 = _fix_unescaped_quotes_in_values(fixed)
                    try:
                        return json.loads(fixed2, strict=False)
                    except json.JSONDecodeError as fallback_err:
                        pos = fallback_err.pos
                        ctx = fixed2[max(0, pos - 100):pos + 100]
                        logger.warning(
                            "[llm] 三次兜底也失败 char=%d, 原始/修复后报错均存在; 上下文片段: %r",
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
        # [2026-06-19] 同 call_json：记录 finish_reason + completion_tokens 便于判定撞上限
        finish_reason = getattr(response.choices[0], "finish_reason", None)
        usage = getattr(response, "usage", None)
        completion_tokens = getattr(usage, "completion_tokens", None) if usage else None
        logger.info(
            "[llm] call_text finish_reason=%s completion_tokens=%s",
            finish_reason, completion_tokens,
        )
        if finish_reason == "length":
            logger.warning(
                "[llm] 输出撞 max_tokens 上限（机制 A）: completion_tokens=%s",
                completion_tokens,
            )
        return response.choices[0].message.content
