"""
Task 相关异常定义
"""


class TaskError(Exception):
    """任务操作基础异常"""
    pass


class TaskNotFoundError(TaskError):
    """任务不存在异常"""
    def __init__(self, task_id: int):
        self.task_id = task_id
        super().__init__(f"Task {task_id} not found")


class InvalidTaskStatusError(TaskError):
    """无效的任务状态异常"""
    def __init__(self, status: str):
        self.status = status
        super().__init__(f"Invalid task status: {status}")


class TaskValidationError(TaskError):
    """任务验证异常"""
    pass
