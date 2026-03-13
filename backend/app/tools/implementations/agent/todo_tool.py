from backend.app.tools.base import tool

from backend.app.todos import get_todo


@tool(tags=["both"])
def TodoWrite(items: list) -> str:
    """更新当前会话的临时任务列表（会话结束后消失）。每个条目需要：content（内容字符串）、status（pending|in_progress|completed）、activeForm（进行时，如"正在读取文件"）。同一时间只能有一个 in_progress 条目（串行执行），最多 20 条。

    使用场景：
    - 单个会话内的临时任务跟踪
    - 简单的顺序任务流程（串行执行）
    - 不需要持久化的任务

    如果需要：
    - 跨会话持久化任务
    - 并行处理多个任务
    - 任务依赖关系管理
    请使用 task_create/task_update/task_list 工具。
    """
    try:
        return get_todo().update(items)
    except Exception as e:
        return f"Error: {e}"

