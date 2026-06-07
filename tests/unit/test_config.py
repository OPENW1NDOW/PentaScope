import importlib


def test_search_config_defaults_when_absent(monkeypatch):
    for k in ("SEARCH_TOP_N", "TAVILY_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    # 屏蔽 load_dotenv，避免 reload 时从 .env 重新读入真实 key（测试隔离）
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: False)
    import src.utils.config as cfg
    importlib.reload(cfg)
    assert cfg.settings.SEARCH_TOP_N == 5
    assert cfg.settings.TAVILY_API_KEY == ""


def test_invalid_int_env_does_not_crash_import(monkeypatch):
    monkeypatch.setenv("SEARCH_TOP_N", "not-a-number")
    import src.utils.config as cfg
    importlib.reload(cfg)
    assert cfg.settings.SEARCH_TOP_N == 5
