from backend.app.todo.manager import TodoManager

_TODO = TodoManager()


def get_todo() -> TodoManager:
    return _TODO
