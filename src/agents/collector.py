import asyncio
import json
import logging
from datetime import datetime, timezone
from pydantic import ValidationError
from src.schemas.input import CompetitorInput, CompetitorBasic, AnalysisGoal
from src.schemas.profile import CompetitorProfile
from src.agents.prompts import COLLECTOR_GOAL_SYSTEM, COLLECTOR_CLASSIFY_SYSTEM, COLLECTOR_EXTRACT_SYSTEM

logger = logging.getLogger(__name__)

ITUNES_API_URL = "https://itunes.apple.com/search?term={name}&country=cn&entity=software&limit=3"
BING_SEARCH_URL = "https://www.bing.com/search?q={name}+产品功能+定价"
SOGOU_SEARCH_URL = "https://www.sogou.com/web?query={name}+功能+价格"

URL_TEMPLATES = [
    ("itunes_api", ITUNES_API_URL),
    ("bing_search", BING_SEARCH_URL),
    ("sogou_search", SOGOU_SEARCH_URL),
]


class CollectorAgent:
    """采集 Agent：目标解析 → 竞品分类 → 差异化采集"""

    def __init__(self, llm, http, parser):
        self.llm = llm
        self.http = http
        self.parser = parser

    async def parse_goal(self, context: str) -> AnalysisGoal:
        """从自然语言描述中解析分析目标"""
        logger.info("[collector] 解析分析目标: %s", context[:50])
        result = await self.llm.call_json(COLLECTOR_GOAL_SYSTEM, f"用户输入：{context}")
        try:
            return AnalysisGoal(**result)
        except ValidationError as e:
            logger.warning("[collector] parse_goal 校验失败, 重试: %s", e)
            result = await self.llm.call_json(COLLECTOR_GOAL_SYSTEM, f"用户输入：{context}")
            try:
                return AnalysisGoal(**result)
            except ValidationError as e2:
                logger.error("[collector] parse_goal 重试后仍然失败: %s, raw=%s", e2, result)
                raise ValueError(f"Collector parse_goal validation failed after retry: {e2}") from e2

    async def classify_competitor(self, name: str, goal: AnalysisGoal) -> dict:
        """判断竞品类型"""
        prompt = f"竞品名称：{name}\n分析目标：{goal.goal_type}，关注领域：{goal.focus_area or '未指定'}"
        result = await self.llm.call_json(COLLECTOR_CLASSIFY_SYSTEM, prompt)
        # 校验必要字段
        if "competitor_type" not in result or "reason" not in result:
            logger.warning("[collector] classify_competitor 返回缺少字段, 重试: %s", result)
            result = await self.llm.call_json(COLLECTOR_CLASSIFY_SYSTEM, prompt)
            if "competitor_type" not in result or "reason" not in result:
                logger.error("[collector] classify_competitor 重试后仍缺少字段: %s", result)
                result.setdefault("competitor_type", "核心竞品")
                result.setdefault("reason", "无法判断，默认归类")
        return result

    async def _fetch_and_parse(self, url: str) -> str:
        """抓取网页并提取文本；iTunes API 返回 JSON，单独解析"""
        raw = await self.http.get(url)
        if raw is None:
            return ""
        if "itunes.apple.com" in url:
            return self._parse_itunes(raw)
        return self.parser.extract_text(raw)

    @staticmethod
    def _parse_itunes(raw: str) -> str:
        """从 iTunes Search API 的 JSON 中提取应用名/价格/评分/描述"""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return ""
        parts = []
        for app in data.get("results", []):
            parts.append(
                f"应用：{app.get('trackName', '')}\n"
                f"价格：{app.get('formattedPrice', '')}\n"
                f"评分：{app.get('averageUserRating', '')}（{app.get('userRatingCount', 0)} 条评价）\n"
                f"开发商：{app.get('sellerName', '')}\n"
                f"描述：{app.get('description', '')[:1000]}"
            )
        return "\n\n".join(parts)

    async def _extract_profile(self, name: str, text: str, classification: dict, sources: list[str]) -> CompetitorProfile:
        """从文本中抽取结构化竞品画像"""
        prompt = f"竞品名称：{name}\n\n网页文本内容：\n{text[:8000]}"
        raw = await self.llm.call_json(COLLECTOR_EXTRACT_SYSTEM, prompt)

        # 补充 classification 和 metadata
        raw["classification"] = classification
        raw["metadata"] = {
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "data_sources": sources,
            "completeness_score": self._calc_completeness(raw),
        }
        try:
            return CompetitorProfile(**raw)
        except ValidationError as e:
            logger.warning("[collector] _extract_profile 校验失败, 重试: %s", e)
            raw = await self.llm.call_json(COLLECTOR_EXTRACT_SYSTEM, prompt)
            raw["classification"] = classification
            raw["metadata"] = {
                "collected_at": datetime.now(timezone.utc).isoformat(),
                "data_sources": sources,
                "completeness_score": self._calc_completeness(raw),
            }
            try:
                return CompetitorProfile(**raw)
            except ValidationError as e2:
                logger.error("[collector] _extract_profile 重试后仍然失败: %s, raw=%s", e2, raw)
                raise ValueError(f"Collector _extract_profile validation failed after retry: {e2}") from e2

    def _calc_completeness(self, data: dict) -> float:
        """计算数据完整度"""
        score = 1.0
        if not data.get("feature_tree"):
            score -= 0.3
        if not data.get("pricing", {}).get("model") or data.get("pricing", {}).get("model") == "unknown":
            score -= 0.15
        if not data.get("user_reviews", {}).get("rating"):
            score -= 0.15
        if not data.get("recent_updates"):
            score -= 0.1
        return max(0, round(score, 2))

    async def _collect_single(self, comp: CompetitorBasic, goal: AnalysisGoal) -> CompetitorProfile:
        """采集单个竞品：分类 → 并行多源采集 → 结构化抽取"""
        classification = await self.classify_competitor(comp.name, goal)

        # 并行采集多个数据源
        source_tasks = []
        for _, url_template in URL_TEMPLATES:
            url = url_template.format(name=comp.name)
            source_tasks.append(self._fetch_and_parse(url))

        texts = await asyncio.gather(*source_tasks, return_exceptions=True)

        sources = []
        valid_texts = []
        for i, text in enumerate(texts):
            if isinstance(text, str) and text:
                url = URL_TEMPLATES[i][1].format(name=comp.name)
                valid_texts.append(text)
                sources.append(url)

        combined_text = "\n\n".join(valid_texts) if valid_texts else f"竞品名称：{comp.name}，公司：{comp.company or '未知'}"

        profile = await self._extract_profile(comp.name, combined_text, classification, sources)
        logger.info("[collector] %s 采集完成, completeness=%.2f", comp.name, profile.metadata.completeness_score)
        return profile

    async def collect(self, user_input: CompetitorInput) -> list[CompetitorProfile]:
        """完整的采集流程：目标解析 → 并行采集所有竞品"""
        goal = await self.parse_goal(user_input.analysis_context)

        # 并行采集所有竞品
        tasks = [self._collect_single(comp, goal) for comp in user_input.competitors]
        profiles = await asyncio.gather(*tasks)

        return list(profiles)
