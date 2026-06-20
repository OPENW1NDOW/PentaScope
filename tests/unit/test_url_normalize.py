from src.utils.url_normalize import normalize_url


def test_strip_trailing_slash():
    assert normalize_url("https://example.com/path/") == "https://example.com/path"


def test_http_to_https():
    assert normalize_url("http://example.com/page") == "https://example.com/page"


def test_strip_fragment():
    assert normalize_url("https://example.com/page#section") == "https://example.com/page"


def test_preserve_query():
    assert normalize_url("https://example.com/page?id=1") == "https://example.com/page?id=1"


def test_identity_for_clean_url():
    assert normalize_url("https://example.com/path") == "https://example.com/path"


def test_combined():
    assert normalize_url("http://example.com/path/#frag") == "https://example.com/path"
