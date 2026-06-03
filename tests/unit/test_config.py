import importlib
import os


def test_search_config_defaults_when_absent(monkeypatch):
    for k in ("SEARCH_API_KEY", "SEARCH_TOP_N", "PICK_LLM_TIMEOUT", "MAX_FETCH_CONCURRENCY"):
        monkeypatch.delenv(k, raising=False)
    import src.utils.config as cfg
    importlib.reload(cfg)
    assert cfg.settings.SEARCH_API_KEY == ""
    assert cfg.settings.SEARCH_TOP_N == 3
    assert cfg.settings.PICK_LLM_TIMEOUT == 20
    assert cfg.settings.MAX_FETCH_CONCURRENCY == 5


def test_invalid_int_env_does_not_crash_import(monkeypatch):
    monkeypatch.setenv("SEARCH_TOP_N", "not-a-number")
    import src.utils.config as cfg
    importlib.reload(cfg)
    assert cfg.settings.SEARCH_TOP_N == 3
