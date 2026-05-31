import logging
from datetime import datetime, timezone
from src.schemas.input import CompetitorInput, CompetitorBasic, AnalysisGoal
from src.schemas.profile import CompetitorProfile
from src.agents.prompts import COLLECTOR_GOAL_SYSTEM, COLLECTOR_CLASSIFY_SYSTEM, COLLECTOR_EXTRACT_SYSTEM

logger = logging.getLogger(__name__)

APP_STORE_SEARCH_URL = "https://apps.apple.com/cn/search?term={name}"
YINGYONGBAO_SEARCH_URL = "https://sj.qq.com/search?q={name}"


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
        return AnalysisGoal(**result)

    async def classify_competitor(self, name: str, goal: AnalysisGoal) -> dict:
        """判断竞品类型"""
        prompt = f"竞品名称：{name}\n分析目标：{goal.goal_type}，关注领域：{goal.focus_area or '未指定'}"
        result = await self.llm.call_json(COLLECTOR_CLASSIFY_SYSTEM, prompt)
        return result

    async def _fetch_and_parse(self, url: str) -> str:
        """抓取网页并提取文本"""
        html = await self.http.get(url)
        if html is None:
            return ""
        return self.parser.extract_text(html)

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
        return CompetitorProfile(**raw)

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

    async def collect(self, user_input: CompetitorInput) -> list[CompetitorProfile]:
        """完整的采集流程：目标解析 → 分类 → 差异化采集"""
        # Step 1: 解析目标
        goal = await self.parse_goal(user_input.analysis_context)

        profiles = []
        for comp in user_input.competitors:
            # Step 2: 分类
            classification = await self.classify_competitor(comp.name, goal)

            # Step 3: 差异化采集
            sources = []
            texts = []

            # 应用商店采集
            for url_template in [APP_STORE_SEARCH_URL, YINGYONGBAO_SEARCH_URL]:
                url = url_template.format(name=comp.name)
                text = await self._fetch_and_parse(url)
                if text:
                    texts.append(text)
                    sources.append(url)

            # 合并所有采集文本
            combined_text = "\n\n".join(texts) if texts else f"竞品名称：{comp.name}，公司：{comp.company or '未知'}"

            # LLM 抽取结构化数据
            profile = await self._extract_profile(comp.name, combined_text, classification, sources)
            profiles.append(profile)

            logger.info("[collector] %s 采集完成, completeness=%.2f", comp.name, profile.metadata.completeness_score)

        return profiles
