import logging
from langchain_core.tools import tool
from backend.app.search.duckduckgo import DuckDuckGoSearch

logger = logging.getLogger(__name__)

_search = DuckDuckGoSearch(max_results=5)


@tool
def web_search(query: str, max_results: int = 5) -> str:
    """Search the web using DuckDuckGo. Use this to find current information, news, documentation, or any topic that requires up-to-date data from the internet.

    Args:
        query: Search query string
        max_results: Number of results to return (default 5, max 10)

    Returns:
        Formatted search results with title, URL, and snippet for each result.
    """
    logger.info("web_search: %s", query)
    max_results = min(max_results, 10)
    results = _search.search(query, max_results=max_results)
    return _search.format_results(results)
