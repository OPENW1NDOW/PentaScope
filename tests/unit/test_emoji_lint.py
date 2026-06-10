"""验证 src/frontend/*.py 中 emoji 仅出现在 PD-5 白名单内位置。

PD-5「选择性纯化」：标题/导航/剩头 emoji 全换 Material Symbols；
KPI/badge/状态点 emoji 保留（视觉一致 + 用户友好）。

白名单（保留位置）：
- src/frontend/app.py 的 pick_confidence emoji（行 49 周边）
- src/frontend/render.py 的 recommendations badge（🔴🟡🟢）
- src/frontend/render.py 的 appendix data_sources confidence（🟢🟡🟠）
- src/frontend/render.py 的 S3 packaging 推荐套餐（⭐）
- src/frontend/render.py 的 S4 trends 方向（↑↓→）
- src/frontend/render.py 的 S5 watermark（⚠️）
- src/frontend/render.py 的 KPI cap 提示（⚠）
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

# Emoji 正则
_EMOJI_RE = re.compile(
    "[\U0001F300-\U0001F6FF"
    "\U0001F900-\U0001F9FF"
    "\U0001F600-\U0001F64F"
    "\U00002600-\U000027BF"
    "\U00002B00-\U00002BFF"
    "]"
)

# 允许出现 emoji 的代码行模式（基于上下文）
# PD-5 选择性纯化范围：禁止用 emoji 当主标题 / 导航 / section 剩头；
# 表格内的"是否"标记 ✓ ✗、状态色点、警告⚠ 等小装饰允许保留
_ALLOWED_CONTEXTS = [
    # AI 推荐场景置信度
    re.compile(r'(pick_confidence|conf_emoji)'),
    re.compile(r'emoji\s*=\s*\{["\']high'),
    # recommendations / appendix priority/confidence badge
    re.compile(r'badge\s*=\s*\{["\']critical'),
    re.compile(r'badge\s*=\s*\{["\']high'),
    # S3 packaging 推荐套餐
    re.compile(r'is_recommended.*"⭐"'),
    re.compile(r'⭐.*is_recommended'),
    # S4 trends 方向
    re.compile(r'["\']up["\']\s*:\s*["\']↑'),
    re.compile(r'arrow\s*=\s*\{'),
    # S5 AI 推断水印
    re.compile(r'display_watermark|watermark.*⚠'),
    re.compile(r'AI 推断版本'),
    # KPI cap 提示
    re.compile(r'⚠ cap'),
    # 表格列内"是否"标记 ✓（dataframe row 字典内）
    re.compile(r'"\s*✓\s*"\s*if\s+'),
    # 表格列字典内的 ✓ 用法
    re.compile(r'self_mark\s*=\s*"✓"'),
    # 注释行内 emoji 允许
    re.compile(r'^\s*#'),
    re.compile(r'^\s*"""'),
]


def _is_allowed_line(line: str) -> bool:
    return any(pat.search(line) for pat in _ALLOWED_CONTEXTS)


@pytest.mark.parametrize("filename", ["app.py", "render.py", "theme.py"])
def test_no_unauthorized_emoji_in_frontend(filename):
    """src/frontend/<filename> 中 emoji 仅出现在白名单内位置。"""
    fp = Path(__file__).parent.parent.parent / "src" / "frontend" / filename
    if not fp.exists():
        pytest.skip(f"{filename} not yet created")

    violations: list[tuple[int, str]] = []
    for lineno, line in enumerate(fp.read_text(encoding="utf-8").splitlines(), 1):
        if _EMOJI_RE.search(line):
            if not _is_allowed_line(line):
                violations.append((lineno, line.strip()))

    assert not violations, (
        f"{filename} 中以下行含未授权 emoji（PD-5 选择性纯化白名单外）：\n"
        + "\n".join(f"  L{ln}: {txt}" for ln, txt in violations)
        + "\n\n如需新增 emoji 请加到 tests/unit/test_emoji_lint.py 的 _ALLOWED_CONTEXTS。"
    )
