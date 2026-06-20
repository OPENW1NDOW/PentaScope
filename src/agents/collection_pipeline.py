"""采集管线：scenario 化 query × N 并发 → 质量闸门 → 单 query 全空 fallback。

collector 的 tool 依赖。collect() 返回 (merged_text, sources, pipeline_trace, labeled_text)。

设计原则（[doubt-driven 06-09]）：
- (b) Query 按 scenario 分化：不同分析场景关注点不同（功能 / 定价 / 定位）
- (c) 失败兜底：每场景 N 条主 query 都全空时，再追加 1 条最稳的 "{name} 官网" 兜底
"""
import asyncio
import logging

from src.tools.quality_gate import is_low_quality

logger = logging.getLogger(__name__)


# scenario → query 模板列表（每个 scenario 1 条聚合 query）
# 每条 query 用 {name} 占位，运行时替换为竞品名
# 每场景 3 条 query 并发搜索，覆盖不同角度（产品对比/官网/评价）
# 输入量由 _EXTRACT_TEXT_MAX_CHARS 截断兜底，不受 LLM 上下文窗口限制
_SCENARIO_QUERIES = {
    "S1": [  # 功能迭代：功能矩阵 + 对比评测 + 用户评价
        "{name} 产品功能 特性 核心能力",
        "{name} vs 竞品 对比评测",
        "{name} 用户评价 优缺点 体验",
    ],
    "S2": [  # 市场进入：公司概况 + 市场份额 + 行业排名
        "{name} 产品介绍 公司 融资",
        "{name} 市场份额 用户量 增长",
        "{name} vs 竞品 行业排名",
    ],
    "S3": [  # 定价策略：定价页 + 套餐对比 + 免费付费区别
        "{name} 定价 价格 套餐",
        "{name} pricing plans 收费",
        "{name} 免费版 付费版 区别",
    ],
    "S4": [  # 持续监控：最新动态 + changelog + 融资新闻
        "{name} 最新动态 发布 更新 2024 2025",
        "{name} 新功能 changelog 版本更新",
        "{name} 新闻 融资 收购",
    ],
    "S5": [  # 战略定位：产品定位 + 竞品对比 + 官网介绍
        "{name} 产品定位 目标用户 使用场景",
        "{name} vs 竞品 优势 差异",
        "{name} 官网 产品介绍 slogan",
    ],
}

# 兜底 query（所有 scenario 主 query 都失败时启用）
_FALLBACK_QUERY = "{name} 官网 产品"


class CollectionPipeline:
    def __init__(self, search_source):
        self.search_source = search_source

    async def collect(
        self,
        competitor_name: str,
        category: str | None = None,
        scenario: str | None = None,
    ):
        """采集一个竞品的正文 + 来源 + 管线追踪。

        scenario: S1-S5 决定主 query 选择；None 时走默认（兼容旧调用）。

        Returns:
            (merged_text, sources, trace, labeled_text)
        """
        texts: list[str] = []
        labeled_parts: list[str] = []
        sources: list[str] = []
        seen_urls: set[str] = set()
        trace: list[dict] = []

        def _add(text: str, url: str) -> None:
            texts.append(text)
            labeled_parts.append(f"【来源: {url}】\n{text}")

        if not self.search_source.available():
            trace.append({"step": "search_skipped", "reason": "no_api_key"})
            return "", [], trace, ""

        # 步骤 1：scenario 化主 query 并发
        queries = _SCENARIO_QUERIES.get(
            scenario or "",
            ["{name} 产品 功能 定价"],  # 未识别 scenario 用旧默认 query 兜底
        )
        main_queries = [q.format(name=competitor_name) for q in queries]
        trace.append({
            "step": "search",
            "provider": self.search_source.name,
            "scenario": scenario,
            "queries": main_queries,
        })

        results_per_query = await asyncio.gather(
            *[self.search_source.search(q) for q in main_queries],
            return_exceptions=True,
        )

        valid_total = 0
        for q, results in zip(main_queries, results_per_query):
            if isinstance(results, Exception):
                logger.warning("[pipeline] query=%r 异常: %s", q, results)
                trace.append({"step": "tavily_query", "query": q, "results": 0, "error": str(results)})
                continue
            valid = 0
            for r in results:
                if r.url and r.url not in seen_urls and not is_low_quality(r.text):
                    _add(r.text, r.url)
                    sources.append(r.url)
                    seen_urls.add(r.url)
                    valid += 1
            valid_total += valid
            trace.append({"step": "tavily_query", "query": q, "results": valid})

        # 步骤 2：(c) fallback——所有主 query 都全空时追加兜底 query
        if valid_total == 0:
            fallback_q = _FALLBACK_QUERY.format(name=competitor_name)
            logger.info("[pipeline] %s 主 query 全空，兜底 query: %s", competitor_name, fallback_q)
            try:
                fb_results = await self.search_source.search(fallback_q)
            except Exception as e:  # noqa: BLE001
                logger.warning("[pipeline] fallback query 异常: %s", e)
                fb_results = []
            fb_valid = 0
            for r in fb_results:
                if r.url and r.url not in seen_urls and not is_low_quality(r.text):
                    _add(r.text, r.url)
                    sources.append(r.url)
                    seen_urls.add(r.url)
                    fb_valid += 1
            trace.append({"step": "tavily_fallback", "query": fallback_q, "results": fb_valid})

        merged_text = "\n\n".join(texts)
        labeled_text = "\n\n".join(labeled_parts)
        return merged_text, sources, trace, labeled_text
