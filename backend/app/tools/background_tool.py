from langchain_core.tools import tool

from backend.app.background import run, check, drain_notifications, run_agent


@tool
def background_run(command: str) -> str:
    """Run a shell command in a background thread. Returns task_id immediately without blocking.
    Use for long-running commands (builds, tests, installs). Check results with check_background."""
    task_id = run(command)
    return f"Background task {task_id} started: {command[:80]}"


@tool
def background_agent(description: str, prompt: str, subagent_type: str) -> str:
    """Run a subagent task in a background thread. Returns task_id immediately without blocking.
    Use for long-running agent tasks (exploration, implementation). Check results with check_background.
    subagent_type: Explore | general-purpose | Plan"""
    from backend.app.tools_manager import tools_manager
    base_tools = [t for t in tools_manager.get_tools() if t.name not in ("Task", "background_agent")]
    task_id = run_agent(description, prompt, subagent_type, base_tools)
    return f"Background agent task {task_id} started: [{subagent_type}] {description[:60]}"


@tool
def check_background(task_id: str = None) -> str:
    """Check background task status. Omit task_id to list all tasks."""
    return check(task_id)
