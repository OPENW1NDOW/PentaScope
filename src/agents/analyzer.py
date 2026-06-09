import json
import logging
from typing import Optional
from pydantic import ValidationError
from src.schemas.profile import CompetitorProfile
from src.schemas.analysis import CompetitiveAnalysis
from src.schemas.feedback import FeedbackIssue
from src.schemas.input import ScenarioInput
from src.agents.prompts import ANALYZER_SYSTEM

logger = logging.getLogger(__name__)


class AnalyzerAgent:
    """分析 Agent：四维框架对比 + SWOT + 雷达评分"""

    def __init__(self, llm):
        self.llm = llm

    @staticmethod
    def _coerce_enum(value: str, allowed: list[str], default: str) -> str:
        """把 LLM 填的枚举值规整到合法集合：精确→包含匹配→默认"""
        if value in allowed:
            return value
        for a in allowed:
            if a in value:  # LLM 常加主语，如 "小米领先" → "领先"
                return a
        return default

    @classmethod
    def _normalize(cls, result: dict) -> dict:
        """规整 LLM 输出中的 Literal 枚举字段，避免主语污染导致校验失败"""
        for entry in result.get("feature_matrix", []):
            if not isinstance(entry, dict):
                continue
            if "gap_level" in entry:
                entry["gap_level"] = cls._coerce_enum(
                    str(entry["gap_level"]), ["领先", "持平", "落后", "差异化"], "持平"
                )
            if "our_product" in entry:
                entry["our_product"] = cls._coerce_enum(
                    str(entry["our_product"]), ["有", "无", "计划中", "不适用"], "无"
                )
            comp = entry.get("competitors")
            if isinstance(comp, dict):
                entry["competitors"] = {
                    k: cls._coerce_enum(str(v), ["有", "无", "部分支持"], "无")
                    for k, v in comp.items()
                }
        for key in ("strengths", "weaknesses", "opportunities", "threats"):
            for item in result.get("swot", {}).get(key, []):
                if isinstance(item, dict) and "dimension" in item:
                    item["dimension"] = cls._coerce_enum(
                        str(item["dimension"]),
                        ["positioning", "feature", "business", "operations"], "feature"
                    )
        return result

    @staticmethod
    def _backfill_source_urls(result: dict, profiles: list) -> dict:
        """维度级 source_urls 兜底：LLM 漏填则用所有 profile 的 data_sources 回填。"""
        all_urls = sorted({
            u for p in profiles
            for u in p.metadata.data_sources
        })
        if not all_urls:
            return result
        for dim_key in ("positioning", "business_model", "operations", "user_sentiment"):
            dim = result.get(dim_key)
            if isinstance(dim, dict) and not dim.get("source_urls"):
                dim["source_urls"] = list(all_urls)
        for entry in result.get("feature_matrix", []):
            if isinstance(entry, dict) and not entry.get("source_urls"):
                entry["source_urls"] = list(all_urls)
        # swot 各 entry 的 source_urls 不做粗粒度兜底（推断性结论，留给 LLM 按需填）
        return result

    @staticmethod
    def _format_feedback(issues: list[FeedbackIssue] | None) -> str:
        """把上一轮质检中归属 analyzer 的 issue 格式化为定向修正指令；无则返回空串。"""
        if not issues:
            return ""
        analyzer_issues = [i for i in issues if i.agent == "analyzer"]
        if not analyzer_issues:
            return ""
        lines = []
        for i in analyzer_issues:
            line = f"- [{i.severity}] {i.field}: {i.reason}"
            if i.suggestion:
                line += f"（建议：{i.suggestion}）"
            lines.append(line)
        return (
            "\n\n【上一轮质检发现的本环节问题，请在本次分析中针对性修正】\n"
            + "\n".join(lines)
        )

    @staticmethod
    def _format_scenario_context(scenario_input: Optional[ScenarioInput]) -> str:
        """[fix7] 拼装场景信息块：让 LLM 知道场景 / 我方产品 / 分析意图。

        关键效果：
        - SWOT 主体能正确选定（S1/3/4/5 → 我方产品；S2 → 进入此赛道这件事）
        - feature_matrix.our_product 字段能填准（之前 LLM 不知我方是谁，常填空或"无"）
        - positioning / business_model 等维度能聚焦用户分析意图
        """
        if scenario_input is None:
            return ""

        scenario = scenario_input.scenario
        # SWOT 主体说明
        if scenario == "S2":
            swot_subject = (
                f"赛道进入（围绕『进入 {scenario_input.industry or '该赛道'} 这件事』展开 "
                "S/W/O/T 四维分析，禁止写成竞品各自的优劣势罗列）"
            )
            our_block = f"我方状态：尚无产品（S2 市场进入场景，industry={scenario_input.industry}）"
        else:
            our_name = scenario_input.our_product_name or "（未填写我方产品名）"
            our_brief = scenario_input.our_product_brief or ""
            swot_subject = (
                f"我方产品『{our_name}』（围绕该产品展开 S/W/O/T，"
                "禁止写成竞品各自的优劣势罗列）"
            )
            our_block = f"我方产品名：{our_name}\n我方产品简介：{our_brief}"

        return (
            "\n\n=== 本次分析的场景上下文（必读）===\n"
            f"场景：{scenario}\n"
            f"{our_block}\n"
            f"分析意图：{scenario_input.analysis_context}\n"
            f"\nSWOT 主体：{swot_subject}\n"
            "feature_matrix.our_product 字段：必须按上述我方信息真实填写有/无/部分支持，"
            "未知时填『未知』而非『无』，禁止留空。\n"
        )

    async def analyze(
        self,
        profiles: list[CompetitorProfile],
        scenario_input: Optional[ScenarioInput] = None,
        feedback_issues: list[FeedbackIssue] | None = None,
    ) -> CompetitiveAnalysis:
        """对采集数据进行结构化分析。

        [fix7] scenario_input 注入：让 analyzer 能感知场景 + 我方产品 + 分析意图，
        修正 SWOT 主体写偏 / feature_matrix.our_product 不准等场景失明问题。
        feedback_issues 非空时附加定向修正指令（回边重跑）。
        """
        logger.info("[analyzer] 开始分析 %d 个竞品", len(profiles))

        # 序列化完整 profile 数据（不截断，依赖 256K 上下文）
        profiles_data = [p.model_dump() for p in profiles]
        profiles_text = json.dumps(profiles_data, ensure_ascii=False, indent=2)

        prompt = (
            f"请基于以下竞品数据进行四维度分析：\n\n{profiles_text}"
            + self._format_scenario_context(scenario_input)
            + self._format_feedback(feedback_issues)
        )
        result = self._backfill_source_urls(
            self._normalize(await self.llm.call_json(ANALYZER_SYSTEM, prompt, max_tokens=8192)),
            profiles,
        )

        try:
            analysis = CompetitiveAnalysis(**result)
        except ValidationError as e:
            logger.warning("[analyzer] Pydantic 校验失败, 重试: %s", e)
            result = self._backfill_source_urls(
                self._normalize(await self.llm.call_json(ANALYZER_SYSTEM, prompt, max_tokens=8192)),
                profiles,
            )
            try:
                analysis = CompetitiveAnalysis(**result)
            except ValidationError as e2:
                logger.error("[analyzer] 重试后仍然失败: %s, raw=%s", e2, result)
                raise ValueError(f"Analyzer output validation failed after retry: {e2}") from e2

        logger.info("[analyzer] 分析完成, 功能矩阵 %d 条, SWOT %d/%d/%d/%d",
                    len(analysis.feature_matrix),
                    len(analysis.swot.strengths), len(analysis.swot.weaknesses),
                    len(analysis.swot.opportunities), len(analysis.swot.threats))
        return analysis
