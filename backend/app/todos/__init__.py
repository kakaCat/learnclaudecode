from backend.app.todos.manager import TodoManager

_TODO = TodoManager()


def get_todo() -> TodoManager:
    return _TODO
