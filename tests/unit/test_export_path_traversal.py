"""验证 GET /trace/{id}/export 路径穿越防护（M7 修入）。

复用 GET /trace/{id} 已有 fullmatch + resolve 双层校验，
攻击 trace_id 应一律返 404 / 422。
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.mark.parametrize("bad_trace_id", [
    "../../etc/passwd",
    "20260610-203430-../etc",
    "20260610-203430-aaaaaa\\..\\windows",  # Windows 反斜杠
    "..\\..\\windows\\system32",
    "0000",                                 # 不符合 \d{8}-\d{6}-[0-9a-f]{6} 格式
    "abcdef",
    ".",
    "..",
    "20260610-203430-XYZWQR",               # 大写 + 非 hex
])
def test_export_path_traversal_returns_404(client, bad_trace_id):
    """非法 trace_id 应返回 404 / 422，不访问磁盘内容。"""
    response = client.get(f"/api/v1/trace/{bad_trace_id}/export?format=md")
    # 路径中含 .. 或 \ 时 starlette 可能 422；正则不匹配时业务逻辑 404
    assert response.status_code in (404, 422), (
        f"trace_id={bad_trace_id!r} got {response.status_code}, expected 404/422"
    )


def test_export_unknown_format_returns_422(client):
    """非法 format 参数应 422（pydantic Literal 校验）。"""
    response = client.get(
        "/api/v1/trace/20260610-203430-aaaaaa/export?format=docx"
    )
    assert response.status_code == 422


def test_export_legit_trace_id_format_passes_validation(client):
    """格式合法但 trace 不存在的 trace_id 应 404 'trace not found'（业务层）。"""
    response = client.get(
        "/api/v1/trace/29990101-000000-deadbe/export?format=md"
    )
    assert response.status_code == 404
