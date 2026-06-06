import importlib


def test_search_config_defaults_when_absent(monkeypatch):
    for k in ("SEARCH_API_KEY", "SEARCH_TOP_N", "PICK_LLM_TIMEOUT",
              "MAX_FETCH_CONCURRENCY", "SEARCH_PROVIDER", "TAVILY_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: False)
    import src.utils.config as cfg
    importlib.reload(cfg)
    assert cfg.settings.SEARCH_API_KEY == ""
    assert cfg.settings.SEARCH_TOP_N == 5
    assert cfg.settings.PICK_LLM_TIMEOUT == 45
    assert cfg.settings.MAX_FETCH_CONCURRENCY == 5
    assert cfg.settings.SEARCH_PROVIDER == "serpapi"
    assert cfg.settings.TAVILY_API_KEY == ""


def test_invalid_int_env_does_not_crash_import(monkeypatch):
    monkeypatch.setenv("SEARCH_TOP_N", "not-a-number")
    import src.utils.config as cfg
    importlib.reload(cfg)
    assert cfg.settings.SEARCH_TOP_N == 5


def test_invalid_search_provider_falls_back_to_serpapi(monkeypatch):
    monkeypatch.setenv("SEARCH_PROVIDER", "FooBar")
    import src.utils.config as cfg
    importlib.reload(cfg)
    assert cfg.settings.SEARCH_PROVIDER == "serpapi"
