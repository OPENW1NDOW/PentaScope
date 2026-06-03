from src.tools.quality_gate import is_low_quality, MIN_CONTENT_LEN


def test_too_short_is_low_quality():
    assert is_low_quality("支付宝") is True


def test_captcha_page_is_low_quality():
    text = "请完成安全验证 " + "x" * 200
    assert is_low_quality(text) is True


def test_soft_404_is_low_quality():
    text = "404 页面不存在 请返回首页"
    assert is_low_quality(text) is True


def test_normal_content_kept():
    text = "支付宝是蚂蚁集团旗下的移动支付平台，提供扫码支付、转账、理财等功能。" * 5
    assert is_low_quality(text) is False


def test_empty_is_low_quality():
    assert is_low_quality("") is True
    assert is_low_quality(None) is True


def test_min_content_len_is_positive():
    assert MIN_CONTENT_LEN > 0
