import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from httpx import AsyncClient, ASGITransport


def _make_mocks(sample_competitor_profile, sample_competitive_analysis, sample_final_report):
    llm_responses = [
        {"goal_type": "competitive_monitoring", "product_stage": "growing", "focus_area": "", "output_expectation": "action"},
        {"competitor_type": "核心竞品", "reason": "test"},
        {k: v for k, v in sample_competitor_profile.items() if k not in ("classification", "metadata")},
        sample_competitive_analysis,
        sample_final_report,
        {"passed": True, "issues": []},
    ]
    call_index = [0]

    async def mock_call_json(system_prompt, user_prompt):
        idx = call_index[0]
        call_index[0] += 1
        return llm_responses[idx]

    mock_llm = MagicMock()
    mock_llm.call_json = AsyncMock(side_effect=mock_call_json)
    mock_http = MagicMock()
    mock_http.get = AsyncMock(return_value="<html>test</html>")
    mock_http.close = AsyncMock()
    mock_parser = MagicMock()
    mock_parser.extract_text.return_value = "test data"
    mock_parser.extract_meta.return_value = {}
    return mock_llm, mock_http, mock_parser


@pytest.mark.asyncio
async def test_analyze_persists_meta(tmp_path, sample_competitor_profile,
                                     sample_competitive_analysis, sample_final_report):
    mock_llm, mock_http, mock_parser = _make_mocks(
        sample_competitor_profile, sample_competitive_analysis, sample_final_report)
    from src.api.main import app
    with patch("src.api.routes.LLMClient", return_value=mock_llm), \
         patch("src.api.routes.HttpClient", return_value=mock_http), \
         patch("src.api.routes.HtmlParser", return_value=mock_parser), \
         patch("src.api.routes.runs_dir", lambda: tmp_path):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post("/api/v1/analyze", json={
                "competitors": [{"name": "支付宝"}], "analysis_context": "测试"})
    assert resp.status_code == 200
    tid = resp.json()["trace_id"]
    meta = json.loads((tmp_path / tid / "meta.json").read_text(encoding="utf-8"))
    assert meta["status"] == "completed"
    assert meta["node_trace"][:4] == ["collector", "analyzer", "writer", "inspector"]


@pytest.mark.asyncio
async def test_get_trace_returns_stages(tmp_path, sample_competitor_profile,
                                        sample_competitive_analysis, sample_final_report):
    mock_llm, mock_http, mock_parser = _make_mocks(
        sample_competitor_profile, sample_competitive_analysis, sample_final_report)
    from src.api.main import app
    with patch("src.api.routes.LLMClient", return_value=mock_llm), \
         patch("src.api.routes.HttpClient", return_value=mock_http), \
         patch("src.api.routes.HtmlParser", return_value=mock_parser), \
         patch("src.api.routes.runs_dir", lambda: tmp_path):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            post = await ac.post("/api/v1/analyze", json={
                "competitors": [{"name": "支付宝"}], "analysis_context": "测试"})
            tid = post.json()["trace_id"]
            resp = await ac.get(f"/api/v1/trace/{tid}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["trace_id"] == tid
    assert body["meta"]["status"] == "completed"
    assert "report" in body["stages"]
    assert body["stages"]["profiles"] is not None


@pytest.mark.asyncio
async def test_get_trace_404_when_missing(tmp_path):
    from src.api.main import app
    with patch("src.api.routes.runs_dir", lambda: tmp_path):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/v1/trace/20260602-143052-abcdef")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_trace_rejects_invalid_format(tmp_path):
    from src.api.main import app
    with patch("src.api.routes.runs_dir", lambda: tmp_path):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/v1/trace/not-a-valid-id")
    assert resp.status_code == 404
