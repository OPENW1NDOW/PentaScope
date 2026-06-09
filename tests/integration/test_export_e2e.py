"""E2E：5 场景 fixture trace → 调 export api → 验证 md/html 内容。"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.utils.paths import runs_dir


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def real_trace_id() -> str:
    """选一个真实存在的 trace_id（PROGRESS.md 中 happy path）。

    若该 trace 已被清理，跳过该测试。
    """
    candidates = [
        "20260609-203430-a4aab7",  # S2 happy path
        "20260609-220309-e58ee9",  # S3 happy path
    ]
    for tid in candidates:
        if (runs_dir() / tid / "03_report.json").is_file():
            return tid
    pytest.skip("no real trace fixture available")


def test_export_md_e2e(client, real_trace_id):
    """E2E：调 export markdown，下载到的内容含关键字段。"""
    response = client.get(f"/api/v1/trace/{real_trace_id}/export?format=md")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    body = response.content.decode("utf-8")
    assert real_trace_id in body
    assert "# " in body  # 有 markdown 标题
    assert len(body) > 500


def test_export_html_e2e(client, real_trace_id):
    """E2E：调 export html，验证字节大小符合 PD-4 全内嵌预期 + 含字体 base64。"""
    response = client.get(f"/api/v1/trace/{real_trace_id}/export?format=html")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    body = response.content
    # PD-4 全内嵌预期：单 HTML > 100KB（plotly.min.js + 字体 + 内容）
    # 上限 15MB 防失控
    assert 100_000 < len(body) < 15_000_000, (
        f"HTML size {len(body)} out of expected range"
    )
    text = body.decode("utf-8")
    assert "data:font/woff2;base64," in text
    assert real_trace_id in text


def test_export_html_offline_safe(client, real_trace_id):
    """模拟离线：HTML 不应有 fonts.googleapis.com 等外网 CDN 引用。"""
    response = client.get(f"/api/v1/trace/{real_trace_id}/export?format=html")
    text = response.content.decode("utf-8")
    # PD-4 离线 100%：不应有外部 CDN 引用
    assert "fonts.googleapis.com" not in text
    assert "fonts.gstatic.com" not in text
    assert 'src="https://cdn.plot.ly' not in text


def test_export_404_for_missing_trace(client):
    """格式合法但不存在的 trace 应 404。"""
    response = client.get("/api/v1/trace/29990101-000000-deadbe/export?format=md")
    assert response.status_code == 404


def test_export_404_for_missing_report(client):
    """trace 目录存在但 03_report.json 缺失应 404 'report not found'。"""
    fake_trace = "29990101-000000-faaaaa"
    fake_dir = runs_dir() / fake_trace
    fake_dir.mkdir(parents=True, exist_ok=True)
    (fake_dir / "meta.json").write_text("{}", encoding="utf-8")
    try:
        response = client.get(f"/api/v1/trace/{fake_trace}/export?format=md")
        assert response.status_code == 404
        detail = response.json()["detail"]
        assert "未产出" in detail or "report" in detail.lower() or "not found" in detail.lower()
    finally:
        (fake_dir / "meta.json").unlink()
        fake_dir.rmdir()
