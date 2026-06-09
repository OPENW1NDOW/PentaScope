"""报告导出模块：BaseReport → markdown / html。

启动时校验字体文件存在（PD-4 全内嵌）。失败 raise 让导出立即报错而非运行时再炸。
"""
from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_FONTS_DIR = Path(__file__).parent / "fonts"
_REQUIRED_FONTS = [
    # Plus Jakarta Sans 为可变字体 latin 子集，单文件涵盖 400/500/600/700 weight
    # 浏览器渲染 bold 时由该单文件自动选 weight，不需要单独 Bold 文件
    "PlusJakartaSans-Regular.woff2",
    "FiraCode-Regular.woff2",
]


def check_fonts() -> None:
    """校验必需字体文件存在。开发阶段下载到 fonts/ 目录后调用。"""
    missing = [f for f in _REQUIRED_FONTS if not (_FONTS_DIR / f).is_file()]
    if missing:
        raise FileNotFoundError(
            f"导出 HTML 需要字体文件 {missing}，"
            f"请下载 woff2 放到 {_FONTS_DIR}。"
            f"下载源：https://fonts.google.com/specimen/Plus+Jakarta+Sans + Fira+Code"
        )
    logger.debug("[exporters] 字体文件全部就绪：%s", _REQUIRED_FONTS)
