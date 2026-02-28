from __future__ import annotations
import logging
from typing import Optional
from duckduckgo_search import DDGS

logger = logging.getLogger(__name__)


class DuckDuckGoSearch:
    """
    DuckDuckGo 搜索封装。

    使用 duckduckgo-search 库，无需 API key。
    """

    def __init__(self, max_results: int = 5, region: str = "wt-wt", safesearch: str = "moderate"):
        self.max_results = max_results
        self.region = region
        self.safesearch = safesearch

    def search(self, query: str, max_results: Optional[int] = None) -> list[dict]:
        """
        搜索网页，返回结果列表。

        Args:
            query: 搜索关键词
            max_results: 最大结果数，默认使用实例配置

        Returns:
            list of {"title": str, "url": str, "snippet": str}
        """
        n = max_results or self.max_results
        logger.info("DuckDuckGo search: %s (max=%d)", query, n)
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(
                    query,
                    region=self.region,
                    safesearch=self.safesearch,
                    max_results=n,
                ))
            return [
                {
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", ""),
                }
                for r in results
            ]
        except Exception as e:
            logger.error("DuckDuckGo search error: %s", e)
            return [{"title": "Error", "url": "", "snippet": str(e)}]

    def format_results(self, results: list[dict]) -> str:
        """将结果格式化为可读字符串，供 LLM 消费。"""
        if not results:
            return "No results found."
        lines = []
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. {r['title']}")
            lines.append(f"   URL: {r['url']}")
            lines.append(f"   {r['snippet']}")
            lines.append("")
        return "\n".join(lines).strip()
