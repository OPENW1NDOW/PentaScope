"""正文质量闸门：纯函数，判断抓取正文是否应丢弃（软404/验证页/过短）。

只作用于网页抓取正文；结构化专源（iTunes 等）结果不经过此闸门，
避免误杀短但有效的 API 结果。
"""

MIN_CONTENT_LEN = 80  # 中文正文低于此长度视为无效

_BLOCK_MARKERS = (
    "captcha", "verify you are human", "人机验证", "安全验证",
    "访问异常", "请完成验证", "滑动验证",
)
_NOT_FOUND_MARKERS = ("页面不存在", "页面已删除", "not found", "404")


def is_low_quality(text: str | None) -> bool:
    """正文是否低质应丢弃。"""
    if not text:
        return True
    stripped = text.strip()
    if len(stripped) < MIN_CONTENT_LEN:
        return True
    lowered = stripped.lower()
    if any(m in lowered for m in _BLOCK_MARKERS):
        return True
    # 软 404：含 not-found 标记且正文较短（长正文里偶含 "404" 不算）
    if len(stripped) < MIN_CONTENT_LEN * 4 and any(m in lowered for m in _NOT_FOUND_MARKERS):
        return True
    return False
