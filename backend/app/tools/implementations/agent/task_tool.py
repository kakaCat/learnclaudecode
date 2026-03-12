import logging

from backend.app.tools.base import tool
from backend.app.task import get_task_service, TaskConverter

logger = logging.getLogger(__name__)


@tool(tags=["both"])
def task_create(subject: str, description: str = "") -> str:
    """创建持久化任务，在上下文压缩后仍然保留。以 JSON 格式存储在 .tasks/ 目录中。"""
    try:
        service = get_task_service()
        task = service.create_task(subject, description)
        logger.info("task_create: %s", subject)
        return TaskConverter.to_json(task)
    except Exception as e:
        return f"Error: {e}"


@tool(tags=["both"])
def task_get(task_id: int) -> str:
    """根据 ID 获取持久化任务的完整详情。"""
    try:
        service = get_task_service()
        task = service.get_task(task_id)
        return TaskConverter.to_json(task)
    except Exception as e:
        return f"Error: {e}"


@tool(tags=["both"])
def task_update(task_id: int, status: str = None,
                addBlockedBy: list = None, addBlocks: list = None) -> str:
    """更新持久化任务的状态（pending|in_progress|completed）或依赖关系。"""
    try:
        service = get_task_service()

        # 更新状态
        if status:
            from backend.app.task import TaskStatus
            task = service.change_status(task_id, TaskStatus(status))
        else:
            task = service.get_task(task_id)

        # 更新依赖关系
        if addBlockedBy:
            for blocker_id in addBlockedBy:
                task = service.add_dependency(task_id, blocker_id)

        if addBlocks:
            for blocked_id in addBlocks:
                service.add_dependency(blocked_id, task_id)
                task = service.get_task(task_id)

        logger.info("task_update: id=%s status=%s", task_id, status)
        return TaskConverter.to_json(task)
    except Exception as e:
        return f"Error: {e}"


@tool(tags=["both"])
def task_list() -> str:
    """列出所有持久化任务及其状态摘要。"""
    try:
        service = get_task_service()
        tasks = service.list_all_tasks()
        return TaskConverter.tasks_to_list_display(tasks)
    except Exception as e:
        return f"Error: {e}"

