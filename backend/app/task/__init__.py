"""
Task 模块导出

企业级任务管理模块，采用分层架构：
- models: 数据模型（Pydantic）
- exceptions: 自定义异常
- repository: 数据访问层
- service: 业务逻辑层
- converter: 数据转换层
"""

from backend.app.task.models import Task, TaskStatus, TaskPriority
from backend.app.task.exceptions import (
    TaskError,
    TaskNotFoundError,
    InvalidTaskStatusError,
    TaskValidationError
)
from backend.app.task.repository import TaskRepository
from backend.app.task.service import TaskService
from backend.app.task.converter import TaskConverter

__all__ = [
    # Models
    "Task",
    "TaskStatus",
    "TaskPriority",
    # Exceptions
    "TaskError",
    "TaskNotFoundError",
    "InvalidTaskStatusError",
    "TaskValidationError",
    # Layers
    "TaskRepository",
    "TaskService",
    "TaskConverter",
]

# 全局单例实例
_service_instance: TaskService = None


def get_task_service() -> TaskService:
    """
    获取全局TaskService单例

    Returns:
        TaskService实例
    """
    global _service_instance
    if _service_instance is None:
        _service_instance = TaskService()
    return _service_instance
