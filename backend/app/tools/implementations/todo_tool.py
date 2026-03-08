from langchain_core.tools import tool

from backend.app.todo import get_todo


@tool
def TodoWrite(items: list) -> str:
    """更新任务列表。每个条目需要：content（内容字符串）、status（pending|in_progress|completed）、activeForm（进行时，如"正在读取文件"）。同一时间只能有一个 in_progress 条目，最多 20 条。"""
    try:
        return get_todo().update(items)
    except Exception as e:
        return f"Error: {e}"
