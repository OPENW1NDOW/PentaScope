import asyncio
import json
import logging
import time
from typing import Optional
from pydantic import ValidationError
from src.schemas.profile import CompetitorProfile
from src.schemas.analysis import (
    BusinessModel, CompetitiveAnalysis, Operations, Positioning, UserSentiment,
)
from src.schemas.feedback import FeedbackIssue
from src.schemas.input import ScenarioInput
from src.schemas.report import Swot
from src.agents.prompts import ANALYZER_SYSTEM
from src.utils.config import settings

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

    @staticmethod
    def _serialize_validation_error(e: ValidationError, max_chars: int = 1500) -> str:
        errs = e.errors()[:5]
        simplified = [{"loc": list(err["loc"]), "msg": err["msg"], "type": err["type"]} for err in errs]
        text = json.dumps(simplified, ensure_ascii=False)
        return text[:max_chars]

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

    async def _analyze_group(
        self,
        profiles: list[CompetitorProfile],
        scenario_input: Optional[ScenarioInput],
        feedback_issues: list[FeedbackIssue] | None,
        group_idx: int,
    ) -> CompetitiveAnalysis:
        """单组分析：复用原有 LLM 调用 + normalize + backfill + Pydantic 校验 + 重试逻辑。

        用于并行拆分场景下的一组竞品；逻辑与原串行 analyze 完全一致，仅少了顶层拆分/合并。
        """
        logger.info("[analyzer] 组 %d 开始分析 %d 个竞品", group_idx, len(profiles))
        t0 = time.monotonic()

        profiles_data = [p.model_dump() for p in profiles]
        profiles_text = json.dumps(profiles_data, ensure_ascii=False, indent=2)

        prompt = (
            f"请基于以下竞品数据进行四维度分析：\n\n{profiles_text}"
            + self._format_scenario_context(scenario_input)
            + self._format_feedback(feedback_issues)
        )
        result = self._backfill_source_urls(
            self._normalize(await self.llm.call_json(ANALYZER_SYSTEM, prompt, max_tokens=16384)),
            profiles,
        )

        try:
            analysis = CompetitiveAnalysis(**result)
        except ValidationError as e:
            logger.warning("[analyzer] 组 %d Pydantic 校验失败, 重试: %s", group_idx, e)
            error_summary = self._serialize_validation_error(e)
            retry_prompt = f"{prompt}\n\n【上次校验失败，请逐条修复】\n{error_summary}"
            result = self._backfill_source_urls(
                self._normalize(await self.llm.call_json(ANALYZER_SYSTEM, retry_prompt, max_tokens=16384)),
                profiles,
            )
            try:
                analysis = CompetitiveAnalysis(**result)
            except ValidationError as e2:
                logger.error("[analyzer] 组 %d 重试后仍然失败: %s, raw=%s", group_idx, e2, result)
                raise ValueError(f"Analyzer group {group_idx} validation failed after retry: {e2}") from e2

        elapsed = time.monotonic() - t0
        logger.info(
            "[analyzer] 组 %d 完成, 耗时 %.1fs, 功能矩阵 %d 条, SWOT %d/%d/%d/%d",
            group_idx, elapsed, len(analysis.feature_matrix),
            len(analysis.swot.strengths), len(analysis.swot.weaknesses),
            len(analysis.swot.opportunities), len(analysis.swot.threats),
        )
        return analysis

    @staticmethod
    def _split_profiles(profiles: list[CompetitorProfile], groups: int) -> list[list[CompetitorProfile]]:
        """简单平分：前 N//groups 个一组，剩余一组，组数固定为 2（与任务要求一致）。"""
        if groups < 2:
            return [list(profiles)]
        mid = len(profiles) // 2
        return [profiles[:mid], profiles[mid:]]

    @staticmethod
    def _dedup_swot_entries(entries: list) -> list:
        """SWOT 条目按 point 去重（point 相同保留先出现的），保持原顺序。"""
        seen = set()
        out = []
        for entry in entries:
            key = entry.point if hasattr(entry, "point") else None
            if key is not None:
                if key in seen:
                    continue
                seen.add(key)
            out.append(entry)
        return out

    @staticmethod
    def _merge_analyses(analyses: list[CompetitiveAnalysis]) -> CompetitiveAnalysis:
        """合并多组分析结果为一个完整 CompetitiveAnalysis。

        - per_competitor / feature_matrix / radar_scores：列表直接拼接
        - user_sentiment.per_competitor：dict 合并；summary 取较长者
        - swot：四维按 point 去重后拼接
        - 各维度 source_urls：拼接去重保序
        """
        if len(analyses) == 1:
            return analyses[0]

        def _merge_urls(*url_lists: list[str]) -> list[str]:
            seen = set()
            out = []
            for urls in url_lists:
                for u in urls or []:
                    if u not in seen:
                        seen.add(u)
                        out.append(u)
            return out

        merged = CompetitiveAnalysis(
            positioning=Positioning(
                per_competitor=[e for a in analyses for e in a.positioning.per_competitor],
                source_urls=_merge_urls(*[a.positioning.source_urls for a in analyses]),
            ),
            business_model=BusinessModel(
                per_competitor=[e for a in analyses for e in a.business_model.per_competitor],
                source_urls=_merge_urls(*[a.business_model.source_urls for a in analyses]),
            ),
            operations=Operations(
                per_competitor=[e for a in analyses for e in a.operations.per_competitor],
                source_urls=_merge_urls(*[a.operations.source_urls for a in analyses]),
            ),
            user_sentiment=UserSentiment(
                summary=max(
                    [a.user_sentiment.summary for a in analyses if a.user_sentiment.summary],
                    key=len, default="",
                ),
                per_competitor={k: v for a in analyses for k, v in a.user_sentiment.per_competitor.items()},
                source_urls=_merge_urls(*[a.user_sentiment.source_urls for a in analyses]),
            ),
            feature_matrix=[e for a in analyses for e in a.feature_matrix],
            radar_scores=[e for a in analyses for e in a.radar_scores],
        )

        if any(a.swot for a in analyses):
            merged.swot = Swot(
                strengths=AnalyzerAgent._dedup_swot_entries(
                    [e for a in analyses if a.swot for e in a.swot.strengths]),
                weaknesses=AnalyzerAgent._dedup_swot_entries(
                    [e for a in analyses if a.swot for e in a.swot.weaknesses]),
                opportunities=AnalyzerAgent._dedup_swot_entries(
                    [e for a in analyses if a.swot for e in a.swot.opportunities]),
                threats=AnalyzerAgent._dedup_swot_entries(
                    [e for a in analyses if a.swot for e in a.swot.threats]),
            )

        return merged

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

        并行拆分：竞品 ≥3 且 ANALYZER_CONCURRENCY ≥2 时拆成 2 组并发调用 LLM，
        合并结果后返回；<3 时保持原有单次调用路径。
        """
        logger.info("[analyzer] 开始分析 %d 个竞品", len(profiles))

        concurrency = max(settings.ANALYZER_CONCURRENCY, 1)
        if len(profiles) < 3 or concurrency < 2:
            analysis = await self._analyze_group(
                profiles, scenario_input, feedback_issues, group_idx=0
            )
            logger.info(
                "[analyzer] 分析完成（单组）, 功能矩阵 %d 条, SWOT %d/%d/%d/%d",
                len(analysis.feature_matrix),
                len(analysis.swot.strengths), len(analysis.swot.weaknesses),
                len(analysis.swot.opportunities), len(analysis.swot.threats),
            )
            return analysis

        groups = self._split_profiles(profiles, concurrency)
        logger.info("[analyzer] 并行拆分 %d 组: %s", len(groups),
                    [len(g) for g in groups])

        results = await asyncio.gather(
            *[self._analyze_group(g, scenario_input, feedback_issues, i + 1)
              for i, g in enumerate(groups)],
            return_exceptions=True,
        )

        ok = [r for r in results if isinstance(r, CompetitiveAnalysis)]
        failed = [r for r in results if isinstance(r, BaseException)]

        if failed:
            for f in failed:
                logger.warning("[analyzer] 一组失败, 降级跳过: %s: %s",
                               type(f).__name__, str(f)[:200])

        if not ok:
            # 两组都失败：取第一个异常向上抛 ValueError，保持与原失败语义一致
            first = failed[0] if failed else ValueError("Analyzer produced no groups")
            raise ValueError(f"Analyzer all groups failed: {first}") from first

        if len(ok) < len(groups):
            logger.warning("[analyzer] 部分组失败, 用成功的 %d/%d 组结果降级返回",
                           len(ok), len(groups))

        analysis = self._merge_analyses(ok)
        logger.info(
            "[analyzer] 分析完成（并行合并 %d 组）, 功能矩阵 %d 条, SWOT %d/%d/%d/%d",
            len(ok), len(analysis.feature_matrix),
            len(analysis.swot.strengths), len(analysis.swot.weaknesses),
            len(analysis.swot.opportunities), len(analysis.swot.threats),
        )
        return analysis
