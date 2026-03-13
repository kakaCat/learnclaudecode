import logging
import re

from backend.app.tools.base import tool
from backend.app.task import get_task_service, TaskConverter

logger = logging.getLogger(__name__)


@tool(tags=["main", "team"])
def task_create_from_plan(subject: str, plan: str) -> str:
    """从Plan自动创建任务树：解析Plan的步骤，创建父任务和子任务，建立依赖关系。

    使用场景：
    - 收到Plan Agent的输出后，自动创建任务结构
    - 一次调用完成所有任务创建和依赖关系设置

    参数：
    - subject: 父任务主题
    - plan: Plan Agent的完整输出（markdown格式）

    返回：父任务的JSON + 所有子任务的ID列表
    """
    try:
        service = get_task_service()

        # 1. 创建父任务
        parent_task = service.create_task(subject, plan=plan)

        # 2. 解析Plan中的步骤
        steps = _parse_plan_steps(plan)

        # 3. 为每个步骤创建子任务
        subtask_ids = []
        prev_task_id = None

        for i, step in enumerate(steps, 1):
            step_subject = f"Step {i}: {step['name']}"
            step_desc = f"What: {step.get('what', '')}\nWhy: {step.get('why', '')}"

            subtask = service.create_task(
                subject=step_subject,
                description=step_desc
            )

            # 建立依赖：当前步骤依赖前一个步骤
            if prev_task_id:
                service.add_dependency(subtask.id, prev_task_id)

            # 父任务阻塞所有子任务
            service.add_dependency(parent_task.id, subtask.id)

            subtask_ids.append(subtask.id)
            prev_task_id = subtask.id

        logger.info(f"Created task tree: parent={parent_task.id}, subtasks={subtask_ids}")

        return f"""✅ 任务树创建成功

父任务: {parent_task.id} - {subject}
子任务: {len(subtask_ids)}个步骤
- {', '.join(f'Task {tid}' for tid in subtask_ids)}

使用 task_list 查看所有任务
使用 task_get {subtask_ids[0]} 查看第一个步骤"""

    except Exception as e:
        logger.error(f"task_create_from_plan failed: {e}", exc_info=True)
        return f"Error: {e}"


def _parse_plan_steps(plan: str) -> list:
    """解析Plan的步骤结构"""
    steps = []

    # 匹配 ### Step N: 标题
    step_pattern = r'### Step \d+: (.+?)(?=\n|$)'
    step_matches = re.finditer(step_pattern, plan)

    for match in step_matches:
        step_name = match.group(1).strip()
        step_start = match.end()

        # 提取What和Why
        what_match = re.search(r'- \*\*What\*\*: (.+?)(?=\n|$)', plan[step_start:])
        why_match = re.search(r'- \*\*Why\*\*: (.+?)(?=\n|$)', plan[step_start:])

        steps.append({
            'name': step_name,
            'what': what_match.group(1).strip() if what_match else '',
            'why': why_match.group(1).strip() if why_match else ''
        })

    return steps


@tool(tags=["main", "team"])
def task_create(subject: str, description: str = "", plan: str = "") -> str:
    """创建持久化任务，跨会话保留。以 JSON 格式存储在 .tasks/ 目录中。

    使用场景：
    - 需要跨会话持久化的任务
    - 复杂项目的任务管理
    - 需要并行处理多个任务
    - 需要任务依赖关系管理

    参数：
    - subject: 任务主题
    - description: 任务描述
    - plan: 任务执行计划（可选，来自Plan Agent的输出）

    如果只是当前会话的临时任务跟踪，使用 TodoWrite 更简单。
    """
    try:
        service = get_task_service()
        task = service.create_task(subject, description, plan)
        logger.info("task_create: %s", subject)
        return TaskConverter.to_json(task)
    except Exception as e:
        return f"Error: {e}"


@tool(tags=["main", "team"])
def task_get(task_id: int) -> str:
    """根据 ID 获取持久化任务的完整详情。"""
    try:
        service = get_task_service()
        task = service.get_task(task_id)
        return TaskConverter.to_json(task)
    except Exception as e:
        return f"Error: {e}"


@tool(tags=["main", "team"])
def task_update(task_id: int, status: str = None,
                addBlockedBy: list = None, addBlocks: list = None) -> str:
    """更新持久化任务的状态（pending|in_progress|completed）或依赖关系。

    支持多个任务同时为 in_progress 状态，适合并行任务场景。
    """
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


@tool(tags=["main", "team"])
def task_list() -> str:
    """列出所有持久化任务及其状态摘要。"""
    try:
        service = get_task_service()
        tasks = service.list_all_tasks()
        return TaskConverter.tasks_to_list_display(tasks)
    except Exception as e:
        return f"Error: {e}"

