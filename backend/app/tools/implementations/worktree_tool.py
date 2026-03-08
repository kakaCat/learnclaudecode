from langchain_core.tools import tool

from backend.app.worktree import get_worktrees, get_events
from backend.app.task import get_tasks


@tool
def task_bind_worktree(task_id: int, worktree: str, owner: str = "") -> str:
    """将任务绑定到 worktree 名称，可选设置 owner。"""
    try:
        return get_tasks().bind_worktree(task_id, worktree, owner)
    except Exception as e:
        return f"Error: {e}"


@tool
def worktree_create(name: str, task_id: int = None, base_ref: str = "HEAD") -> str:
    """创建 git worktree，可选绑定到任务 ID。name 只能包含字母、数字、.、_、-（最多40字符）。"""
    try:
        return get_worktrees().create(name, task_id, base_ref)
    except Exception as e:
        return f"Error: {e}"


@tool
def worktree_list() -> str:
    """列出 .worktrees/index.json 中跟踪的所有 worktree。"""
    try:
        return get_worktrees().list_all()
    except Exception as e:
        return f"Error: {e}"


@tool
def worktree_status(name: str) -> str:
    """显示指定 worktree 的 git status。"""
    try:
        return get_worktrees().status(name)
    except Exception as e:
        return f"Error: {e}"


@tool
def worktree_run(name: str, command: str) -> str:
    """在指定 worktree 目录中运行 shell 命令。"""
    try:
        return get_worktrees().run(name, command)
    except Exception as e:
        return f"Error: {e}"


@tool
def worktree_remove(name: str, force: bool = False, complete_task: bool = False) -> str:
    """删除 worktree，可选将绑定任务标记为已完成。"""
    try:
        return get_worktrees().remove(name, force, complete_task)
    except Exception as e:
        return f"Error: {e}"


@tool
def worktree_keep(name: str) -> str:
    """将 worktree 标记为 kept 状态（不删除，仅更新生命周期索引）。"""
    try:
        return get_worktrees().keep(name)
    except Exception as e:
        return f"Error: {e}"


@tool
def worktree_events(limit: int = 20) -> str:
    """列出最近的 worktree/任务生命周期事件（来自 .worktrees/events.jsonl）。"""
    try:
        return get_events().list_recent(limit)
    except Exception as e:
        return f"Error: {e}"
