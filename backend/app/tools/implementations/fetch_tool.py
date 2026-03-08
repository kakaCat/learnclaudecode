import logging
from langchain_core.tools import tool
from backend.app.search.fetch import WebFetch

logger = logging.getLogger(__name__)

_fetcher = WebFetch(max_chars=3000)


@tool
def fetch_url(url: str, max_chars: int = 3000) -> str:
    """Fetch the full text content of a URL. Use this when a search result URL contains critical detail that needs to be read in full.

    Args:
        url: The URL to fetch
        max_chars: Maximum characters to return (default 3000)

    Returns:
        Plain text content of the page, stripped of HTML tags.
    """
    logger.info("fetch_url: %s", url)
    return _fetcher.fetch(url, max_chars=max_chars)
