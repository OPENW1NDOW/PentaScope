"""GET /api/v1/traces scenario / status 筛选参数测试。"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.api.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def fake_runs(tmp_path, monkeypatch):
    runs = tmp_path / "runs"
    runs.mkdir()
    monkeypatch.setattr("src.api.routes.runs_dir", lambda: runs)
    return runs


def _write_trace(runs: Path, trace_id: str, scenario: str, status: str) -> None:
    d = runs / trace_id
    d.mkdir()
    meta = {
        "status": status,
        "started_at": "2026-06-10T10:00:00+00:00",
        "input": {
            "scenario": scenario,
            "competitors": [{"name": "竞品A"}],
        },
    }
    (d / "meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")


@pytest.fixture
def populated_runs(fake_runs):
    traces = [
        ("20260610-100000-aaaaaa", "S1", "completed"),
        ("20260610-100001-bbbbbb", "S2", "completed"),
        ("20260610-100002-cccccc", "S2", "failed"),
        ("20260610-100003-dddddd", "S3", "running"),
        ("20260610-100004-eeeeee", "S4", "completed"),
        ("20260610-100005-ffffff", "S5", "failed"),
    ]
    for tid, scenario, status in traces:
        _write_trace(fake_runs, tid, scenario, status)
    return traces


def test_list_traces_no_filter_returns_all(client, populated_runs):
    response = client.get("/api/v1/traces")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 6
    assert len(data["traces"]) == 6


def test_list_traces_filter_scenario_s2(client, populated_runs):
    response = client.get("/api/v1/traces?scenario=S2")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["traces"]) == 2
    assert all(t["scenario"] == "S2" for t in data["traces"])


def test_list_traces_filter_status_completed(client, populated_runs):
    response = client.get("/api/v1/traces?status=completed")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert len(data["traces"]) == 3
    assert all(t["status"] == "completed" for t in data["traces"])


def test_list_traces_filter_scenario_and_status(client, populated_runs):
    response = client.get("/api/v1/traces?scenario=S2&status=completed")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["traces"]) == 1
    t = data["traces"][0]
    assert t["scenario"] == "S2"
    assert t["status"] == "completed"
    assert t["trace_id"] == "20260610-100001-bbbbbb"


def test_list_traces_invalid_scenario_returns_422(client, populated_runs):
    response = client.get("/api/v1/traces?scenario=S6")
    assert response.status_code == 422
