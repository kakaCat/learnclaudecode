import logging
from typing import Callable, Optional

from backend.app.tools.base import tool
from backend.app.core.registry import registry, get_descriptions

logger = logging.getLogger(__name__)

# 全局回调函数（由 agent 注入）
_spawn_callback: Optional[Callable] = None


def set_spawn_callback(callback: Callable):
    """注入 spawn 回调函数（由 MainAgent 调用）"""
    global _spawn_callback
    _spawn_callback = callback


@tool(tags=["main"])
def spawn_subagent(description: str, prompt: str, subagent_type: str, recursion_limit: int = 100) -> str:
    """Spawn a subagent for a focused subtask. Subagents run in ISOLATED context.

    Use for subtasks needing focused exploration or implementation without polluting main context."""
    logger.info("spawn_subagent: [%s] %s", subagent_type, description)

    if not registry.has(subagent_type):
        return f"Error: Unknown agent type '{subagent_type}'. Choose from: {registry.list_agents()}"

    if _spawn_callback is None:
        return "Error: Task tool not initialized (missing spawn callback)"

    try:
        result = _spawn_callback(
            description=description,
            prompt=prompt,
            subagent_type=subagent_type,
            recursion_limit=recursion_limit
        )
        return result
    except Exception as e:
        logger.error(f"Subagent execution failed: {e}", exc_info=True)
        return f"Error: Subagent execution failed - {str(e)}"
