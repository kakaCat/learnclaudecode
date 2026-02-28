import logging
from langchain_core.tools import tool
from backend.app.search_agent.lead_agent import SearchLeadAgent

logger = logging.getLogger(__name__)

_lead_agent = SearchLeadAgent()

@tool
def search_lead(topic: str) -> str:
    """Research a topic by decomposing it into sub-queries and searching in parallel.
    Saves full results to a file and returns the file path.

    Use this instead of web_search when:
    - The topic is broad or complex (needs multiple angles)
    - You want parallel search without polluting main context
    - You need a synthesized research report saved to disk

    Use web_search for simple, single-shot lookups.

    Args:
        topic: Research topic or question (passed as-is, this tool handles decomposition)

    Returns:
        File path to the saved research report with citation verification appended (e.g. scripts/research/xxx.md)
    """
    logger.info("search_lead: %s", topic)
    return _lead_agent.run(topic)


