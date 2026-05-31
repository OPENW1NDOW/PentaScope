import pytest
import json
from unittest.mock import AsyncMock, MagicMock
from src.schemas.input import CompetitorInput, CompetitorBasic
from src.graph.builder import build_graph


class TestGraphIntegration:
    @pytest.mark.asyncio
    async def test_full_graph_run(self, sample_competitor_profile, sample_competitive_analysis, sample_final_report):
        """端到端测试：Mock LLM，验证完整图运行"""
        # 构造 LLM 返回序列
        llm_responses = [
            # collector: parse_goal
            {"goal_type": "competitive_monitoring", "product_stage": "growing", "focus_area": "", "output_expectation": "action"},
            # collector: classify
            {"competitor_type": "核心竞品", "reason": "test"},
            # collector: extract_profile (对每个竞品)
            {k: v for k, v in sample_competitor_profile.items() if k not in ("classification", "metadata")},
            # analyzer
            sample_competitive_analysis,
            # writer
            sample_final_report,
            # inspector
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

        mock_parser = MagicMock()
        mock_parser.extract_text.return_value = "支付宝 移动支付"
        mock_parser.extract_meta.return_value = {}

        graph = build_graph(llm=mock_llm, http=mock_http, parser=mock_parser)

        user_input = CompetitorInput(
            competitors=[CompetitorBasic(name="支付宝")],
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

    @pytest.mark.asyncio
    async def test_rejection_triggers_retry(self, sample_competitor_profile, sample_competitive_analysis, sample_final_report):
        """测试质检打回后重新执行"""
        llm_responses = [
            # collector: parse_goal
            {"goal_type": "competitive_monitoring", "product_stage": "growing", "focus_area": "", "output_expectation": "action"},
            # collector: classify
            {"competitor_type": "核心竞品", "reason": "test"},
            # collector: extract_profile
            {k: v for k, v in sample_competitor_profile.items() if k not in ("classification", "metadata")},
            # analyzer
            sample_competitive_analysis,
            # writer (第一次)
            sample_final_report,
            # inspector (第一次: 不通过)
            {"passed": False, "issues": [{"agent": "writer", "field": "executive_summary.what_competitors_did_right", "severity": "critical", "reason": "为空", "suggestion": "补充"}]},
            # writer (修正后)
            sample_final_report,
            # inspector (第二次: 通过)
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

        mock_parser = MagicMock()
        mock_parser.extract_text.return_value = "支付宝 移动支付"
        mock_parser.extract_meta.return_value = {}

        graph = build_graph(llm=mock_llm, http=mock_http, parser=mock_parser)

        user_input = CompetitorInput(
            competitors=[CompetitorBasic(name="支付宝")],
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
