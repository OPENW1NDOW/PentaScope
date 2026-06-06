import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from src.api.main import app


class TestAPI:
    @pytest.mark.asyncio
    async def test_health(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health")
            assert response.status_code == 200
            assert response.json()["status"] == "ok"

    @pytest.mark.asyncio
    async def test_analyze_returns_report(self, monkeypatch, tmp_path, sample_competitor_profile, sample_competitive_analysis, sample_final_report):
        monkeypatch.setattr("src.graph.builder.settings.SEARCH_API_KEY", "K", raising=False)
        llm_responses = [
            {"goal_type": "competitive_monitoring", "product_stage": "growing", "focus_area": "", "output_expectation": "action"},
            {"competitor_type": "核心竞品", "reason": "test"},
            {"urls": ["https://alipay.com/pricing"]},
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
        mock_http.get_json = AsyncMock(return_value={
            "organic_results": [{"link": "https://alipay.com/pricing", "title": "支付宝定价", "snippet": "定价"}]
        })
        mock_http.close = AsyncMock()

        mock_parser = MagicMock()
        mock_parser.extract_text.return_value = "支付宝是蚂蚁集团旗下的移动支付平台，提供扫码支付、转账、生活服务等功能，覆盖中国主流消费群体的日常支付场景。" * 2
        mock_parser.extract_meta.return_value = {}

        with patch("src.api.routes.LLMClient", return_value=mock_llm), \
             patch("src.api.routes.HttpClient", return_value=mock_http), \
             patch("src.api.routes.HtmlParser", return_value=mock_parser), \
             patch("src.api.routes.runs_dir", lambda: tmp_path):

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post("/api/v1/analyze", json={
                    "competitors": [{"name": "支付宝", "category": "金融软件"}],
                    "analysis_context": "分析支付宝"
                })

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["report"] is not None
