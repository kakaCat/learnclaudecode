from typing import Callable, Optional
from backend.app.tools.base import tool
from backend.app.background import run, check, run_agent

# 全局回调（由 agent 注入）
_get_tools_callback: Optional[Callable] = None


def set_get_tools_callback(callback: Callable):
    """注入获取工具列表的回调函数"""
    global _get_tools_callback
    _get_tools_callback = callback


@tool(tags=["both"])
def background_run(command: str) -> str:
    """Run a shell command in a background thread. Returns task_id immediately without blocking.
    Use for long-running commands (builds, tests, installs). Check results with check_background."""
    task_id = run(command)
    return f"Background task {task_id} started: {command[:80]}"


@tool(tags=["both"])
def background_agent(description: str, prompt: str, subagent_type: str) -> str:
    """Run a subagent task in a background thread. Returns task_id immediately without blocking.
    Use for long-running agent tasks (exploration, implementation). Check results with check_background.
    subagent_type: Explore | general-purpose | Plan"""
    if _get_tools_callback is None:
        return "Error: background_agent not initialized (missing tools callback)"

    base_tools = _get_tools_callback()
    task_id = run_agent(description, prompt, subagent_type, base_tools)
    return f"Background agent task {task_id} started: [{subagent_type}] {description[:60]}"


@tool(tags=["both"])
def check_background(task_id: str = None) -> str:
    """Check background task status. Omit task_id to list all tasks."""
    return check(task_id)
