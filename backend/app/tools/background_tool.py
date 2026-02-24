from langchain_core.tools import tool

from backend.app.background import run, check, drain_notifications


@tool
def background_run(command: str) -> str:
    """Run a shell command in a background thread. Returns task_id immediately without blocking.
    Use for long-running commands (builds, tests, installs). Check results with check_background."""
    task_id = run(command)
    return f"Background task {task_id} started: {command[:80]}"


@tool
def check_background(task_id: str = None) -> str:
    """Check background task status. Omit task_id to list all tasks."""
    return check(task_id)
