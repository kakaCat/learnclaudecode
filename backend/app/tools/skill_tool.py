import logging

from langchain_core.tools import tool

from backend.app.skill import SKILL_LOADER

logger = logging.getLogger(__name__)


@tool
def load_skill(name: str) -> str:
    """Load specialized knowledge by name. Call this before tackling unfamiliar topics.
    Returns the full skill content to guide your approach."""
    logger.info("load_skill: %s", name)
    return SKILL_LOADER.get_content(name)
