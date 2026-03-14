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

__tool_config__ = {
    "tags": ["main", "team"],
    "category": "agent",
    "enabled": False 
}

@tool()
def spawn_subagent(description: str, prompt: str, subagent_type: str, recursion_limit: int = 100) -> str:
    """Spawn a subagent for a focused subtask. Subagents run in ISOLATED context.

    Use for subtasks needing focused exploration or implementation without polluting main context.

    Returns:
        Subagent's output. For CDPBrowser, expects JSON with status/data_count/summary.
        Empty or non-JSON output indicates subagent didn't complete properly.
    """
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

        # 验证返回结果
        if not result or result.strip() == "":
            logger.warning(f"Subagent {subagent_type} returned empty result")
            return (
                "⚠️ Subagent completed but returned empty output.\n"
                "This usually means:\n"
                "1. Subagent didn't follow the output format requirement\n"
                "2. Task failed but subagent didn't report failure properly\n"
                "3. Results were saved to workspace but not returned\n\n"
                "Recommendation: Use workspace_read to check if subagent saved any files."
            )

        # 对于 CDPBrowser，检查是否包含 JSON 结果
        if subagent_type == "CDPBrowser":
            import json
            import re

            # 尝试提取 JSON
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', result, re.DOTALL)
            if not json_match:
                json_match = re.search(r'(\{[^{}]*"status"[^{}]*\})', result, re.DOTALL)

            if json_match:
                try:
                    result_json = json.loads(json_match.group(1))
                    status = result_json.get("status", "unknown")
                    data_count = result_json.get("data_count", 0)
                    summary = result_json.get("summary", "")

                    logger.info(f"CDPBrowser result: status={status}, data_count={data_count}")

                    # 返回格式化的结果
                    return (
                        f"Subagent completed with status: {status}\n"
                        f"Data extracted: {data_count} items\n"
                        f"Summary: {summary}\n\n"
                        f"Full result:\n{result}"
                    )
                except json.JSONDecodeError:
                    logger.warning("Failed to parse CDPBrowser JSON result")
            else:
                logger.warning("CDPBrowser didn't return expected JSON format")
                return (
                    f"⚠️ CDPBrowser completed but didn't return structured result.\n\n"
                    f"Raw output:\n{result}\n\n"
                    f"Recommendation: Check workspace files or ask subagent to retry with proper format."
                )

        return result

    except Exception as e:
        logger.error(f"Subagent execution failed: {e}", exc_info=True)
        return f"Error: Subagent execution failed - {str(e)}"
