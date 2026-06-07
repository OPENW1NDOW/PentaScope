import pytest
from unittest.mock import AsyncMock, MagicMock
from src.schemas.input import CompetitorInput, CompetitorBasic
from src.graph.builder import build_graph
from src.tools.trace_writer import TraceWriter


_TAVILY_RESULTS = {
    "results": [
        {"url": "https://alipay.com/pricing",
         "raw_content": "支付宝定价方案介绍" * 60,
         "content": ""},
        {"url": "https://alipay.com/features",
         "raw_content": "支付宝功能模块说明" * 60,
         "content": ""},
        {"url": "https://alipay.com/help",
         "raw_content": "支付宝帮助中心文档" * 60,
         "content": ""},
    ]
}


class TestGraphIntegration:
    @pytest.mark.asyncio
    async def test_full_graph_run(self, monkeypatch, sample_competitor_profile, sample_competitive_analysis, sample_final_report):
        """端到端：完整图能跑通并返回 report，feedback.passed=True"""
        monkeypatch.setattr("src.graph.builder.settings.SEARCH_PROVIDER", "tavily", raising=False)
        monkeypatch.setattr("src.graph.builder.settings.TAVILY_API_KEY", "K", raising=False)
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
        mock_http.get = AsyncMock(return_value="<html>支付宝</html>")
        mock_http.get_json = AsyncMock(return_value={
            "organic_results": [{"link": "https://alipay.com/pricing", "title": "支付宝定价", "snippet": "定价"}]
        })
        mock_http.post_json = AsyncMock(return_value=_TAVILY_RESULTS)

        mock_parser = MagicMock()
        mock_parser.extract_text.return_value = "支付宝是蚂蚁集团旗下的移动支付平台，提供扫码支付、转账、生活服务等功能，覆盖中国主流消费群体的日常支付场景。" * 2
        mock_parser.extract_meta.return_value = {}

        graph, _ = build_graph(llm=mock_llm, http=mock_http, parser=mock_parser)

        user_input = CompetitorInput(
            competitors=[CompetitorBasic(name="支付宝", category="金融软件")],
            analysis_context="分析支付宝"
        )

        result = await graph.ainvoke({
            "user_input": user_input,
            "retry_count": 0,
            "max_retries": 2,
            "trace_id": "test-001",
        })

        assert "report" in result
        assert result["report"].title != ""
        assert result["feedback"].passed is True
        # 6 步 LLM 调用全部消费（parse_goal / classify / extract_profile / analyzer / writer / inspector）
        assert call_index[0] == 6

    @pytest.mark.asyncio
    async def test_rejection_triggers_retry(self, monkeypatch, sample_competitor_profile, sample_competitive_analysis, sample_final_report):
        """质检不通过时打回 writer 后重试，retry_count 至少 +1 且最终 passed=True"""
        monkeypatch.setattr("src.graph.builder.settings.SEARCH_PROVIDER", "tavily", raising=False)
        monkeypatch.setattr("src.graph.builder.settings.TAVILY_API_KEY", "K", raising=False)
        llm_responses = [
            {"goal_type": "competitive_monitoring", "product_stage": "growing", "focus_area": "", "output_expectation": "action"},
            {"competitor_type": "核心竞品", "reason": "test"},
            {k: v for k, v in sample_competitor_profile.items() if k not in ("classification", "metadata")},
            sample_competitive_analysis,
            sample_final_report,
            {"passed": False, "issues": [{"agent": "writer", "field": "executive_summary.what_competitors_did_right", "severity": "critical", "reason": "为空", "suggestion": "补充"}]},
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
        mock_http.get = AsyncMock(return_value="<html>支付宝</html>")
        mock_http.get_json = AsyncMock(return_value={
            "organic_results": [{"link": "https://alipay.com/pricing", "title": "支付宝定价", "snippet": "定价"}]
        })
        mock_http.post_json = AsyncMock(return_value=_TAVILY_RESULTS)

        mock_parser = MagicMock()
        mock_parser.extract_text.return_value = "支付宝是蚂蚁集团旗下的移动支付平台，提供扫码支付、转账、生活服务等功能，覆盖中国主流消费群体的日常支付场景。" * 2
        mock_parser.extract_meta.return_value = {}

        graph, _ = build_graph(llm=mock_llm, http=mock_http, parser=mock_parser)

        user_input = CompetitorInput(
            competitors=[CompetitorBasic(name="支付宝", category="金融软件")],
            analysis_context="分析支付宝"
        )

        result = await graph.ainvoke({
            "user_input": user_input,
            "retry_count": 0,
            "max_retries": 2,
            "trace_id": "test-002",
        })

        assert result["feedback"].passed is True
        assert result["retry_count"] >= 1

    @pytest.mark.asyncio
    async def test_graph_persists_stage_artifacts(self, monkeypatch, tmp_path, sample_competitor_profile, sample_competitive_analysis, sample_final_report):
        """各节点产出落盘：四个 stage 文件都应存在"""
        monkeypatch.setattr("src.graph.builder.settings.SEARCH_PROVIDER", "tavily", raising=False)
        monkeypatch.setattr("src.graph.builder.settings.TAVILY_API_KEY", "K", raising=False)
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
        mock_http.get = AsyncMock(return_value="<html>支付宝</html>")
        mock_http.get_json = AsyncMock(return_value={
            "organic_results": [{"link": "https://alipay.com/pricing", "title": "支付宝定价", "snippet": "定价"}]
        })
        mock_http.post_json = AsyncMock(return_value=_TAVILY_RESULTS)

        mock_parser = MagicMock()
        mock_parser.extract_text.return_value = "支付宝是蚂蚁集团旗下的移动支付平台，提供扫码支付、转账、生活服务等功能，覆盖中国主流消费群体的日常支付场景。" * 2
        mock_parser.extract_meta.return_value = {}

        trace_writer = TraceWriter("graph-1", base_dir=tmp_path)
        graph, _ = build_graph(llm=mock_llm, http=mock_http, parser=mock_parser, trace_writer=trace_writer)

        user_input = CompetitorInput(
            competitors=[CompetitorBasic(name="支付宝", category="金融软件")],
            analysis_context="分析支付宝"
        )

        await graph.ainvoke({
            "user_input": user_input,
            "retry_count": 0,
            "max_retries": 2,
            "trace_id": "graph-1",
        })

        trace_dir = tmp_path / "graph-1"
        for fname in ("01_profiles.json", "02_analysis.json", "03_report.json", "04_feedback.json"):
            assert (trace_dir / fname).exists(), f"缺失落盘文件: {fname}"

    @pytest.mark.asyncio
    async def test_build_graph_returns_node_trace(self, monkeypatch, sample_competitor_profile, sample_competitive_analysis, sample_final_report):
        """build_graph 返回 node_trace，记录路由决策序列"""
        monkeypatch.setattr("src.graph.builder.settings.SEARCH_PROVIDER", "tavily", raising=False)
        monkeypatch.setattr("src.graph.builder.settings.TAVILY_API_KEY", "K", raising=False)
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
        mock_http.get = AsyncMock(return_value="<html>支付宝</html>")
        mock_http.get_json = AsyncMock(return_value={
            "organic_results": [{"link": "https://alipay.com/pricing", "title": "支付宝定价", "snippet": "定价"}]
        })
        mock_http.post_json = AsyncMock(return_value=_TAVILY_RESULTS)

        mock_parser = MagicMock()
        mock_parser.extract_text.return_value = "支付宝是蚂蚁集团旗下的移动支付平台，提供扫码支付、转账、生活服务等功能，覆盖中国主流消费群体的日常支付场景。" * 2
        mock_parser.extract_meta.return_value = {}

        graph, node_trace = build_graph(llm=mock_llm, http=mock_http, parser=mock_parser)

        user_input = CompetitorInput(
            competitors=[CompetitorBasic(name="支付宝", category="金融软件")],
            analysis_context="分析支付宝"
        )

        await graph.ainvoke({
            "user_input": user_input,
            "retry_count": 0,
            "max_retries": 2,
            "trace_id": "test-003",
        })

        assert node_trace[:4] == ["collector", "analyzer", "writer", "inspector"]
