from backend.app.task.task_manager import TaskManager

_TASKS = TaskManager()


def get_tasks() -> TaskManager:
    return _TASKS
