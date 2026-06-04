import logging
import os
import sys
from pathlib import Path


def setup_logger(name: str, log_dir: str = "logs") -> logging.Logger:
    """创建结构化日志器，同时输出到控制台和文件"""
    Path(log_dir).mkdir(exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        formatter = logging.Formatter(
            "[%(asctime)s] %(levelname)s %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        file_handler = logging.FileHandler(f"{log_dir}/app.log", encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def init_logging(log_file=None, level: int = logging.INFO) -> None:
    """初始化 root logger：控制台 + 文件。API 启动时调用一次。"""
    from src.utils.paths import logs_dir

    if log_file is None:
        logs_dir().mkdir(exist_ok=True)
        log_file = logs_dir() / "app.log"

    root = logging.getLogger()
    root.setLevel(level)

    # httpx/httpcore 的 INFO 会打完整请求 URL（含 api_key 等敏感 query），压到 WARNING 防泄漏
    for noisy in ("httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    target = os.path.abspath(str(log_file))
    has_file = any(
        isinstance(h, logging.FileHandler)
        and getattr(h, "baseFilename", None) == target
        for h in root.handlers
    )
    if not has_file:
        fh = logging.FileHandler(str(log_file), encoding="utf-8")
        fh.setFormatter(formatter)
        root.addHandler(fh)

    has_console = any(
        isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
        for h in root.handlers
    )
    if not has_console:
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(formatter)
        root.addHandler(ch)
