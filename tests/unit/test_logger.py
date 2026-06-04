import logging
from src.utils.logger import init_logging


def test_init_logging_configures_root_with_file(tmp_path):
    log_file = tmp_path / "app.log"
    logging.getLogger().handlers.clear()  # 清掉 pytest logging 插件注入的伪 handler
    init_logging(log_file=log_file, level=logging.INFO)
    root = logging.getLogger()
    assert root.level == logging.INFO
    logging.getLogger("x").info("hello-trace")
    for h in root.handlers:
        h.flush()
    assert log_file.exists()
    assert "hello-trace" in log_file.read_text(encoding="utf-8")


def test_init_logging_silences_httpx_request_url(tmp_path):
    # httpx 的 INFO 日志会打完整 URL（含 api_key），必须压到 WARNING 防泄漏
    log_file = tmp_path / "app.log"
    logging.getLogger().handlers.clear()
    init_logging(log_file=log_file, level=logging.INFO)
    assert logging.getLogger("httpx").level >= logging.WARNING
