from langchain_core.tools import tool

from backend.app.task import get_tasks


@tool
def task_create(subject: str, description: str = "") -> str:
    """创建持久化任务，在上下文压缩后仍然保留。以 JSON 格式存储在 .tasks/ 目录中。"""
    try:
        return get_tasks().create(subject, description)
    except Exception as e:
        return f"Error: {e}"


@tool
def task_get(task_id: int) -> str:
    """根据 ID 获取持久化任务的完整详情。"""
    try:
        return get_tasks().get(task_id)
    except Exception as e:
        return f"Error: {e}"


@tool
def task_update(task_id: int, status: str = None,
                addBlockedBy: list = None, addBlocks: list = None) -> str:
    """更新持久化任务的状态（pending|in_progress|completed）或依赖关系。"""
    try:
        return get_tasks().update(task_id, status, addBlockedBy, addBlocks)
    except Exception as e:
        return f"Error: {e}"


@tool
def task_list() -> str:
    """列出所有持久化任务及其状态摘要。"""
    try:
        return get_tasks().list_all()
    except Exception as e:
        return f"Error: {e}"
