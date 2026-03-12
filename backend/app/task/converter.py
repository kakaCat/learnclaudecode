"""
Task Converter - 数据转换层
负责任务数据的格式转换和展示
"""
import json
from typing import List, Dict, Any
from datetime import datetime

from backend.app.task.models import Task, TaskStatus, TaskPriority


class TaskConverter:
    """任务数据转换器"""

    @staticmethod
    def to_json(task: Task, pretty: bool = True) -> str:
        """
        将任务转换为JSON字符串

        Args:
            task: 任务对象
            pretty: 是否格式化输出

        Returns:
            JSON字符串
        """
        data = TaskConverter.to_dict(task)
        if pretty:
            return json.dumps(data, indent=2, ensure_ascii=False)
        return json.dumps(data, ensure_ascii=False)

    @staticmethod
    def to_dict(task: Task) -> Dict[str, Any]:
        """
        将任务转换为字典

        Args:
            task: 任务对象

        Returns:
            字典
        """
        return {
            "id": task.id,
            "subject": task.subject,
            "description": task.description,
            "status": task.status.value,
            "priority": task.priority.value,
            "blocked_by": task.blocked_by,
            "blocks": task.blocks,
            "owner": task.owner,
            "worktree": task.worktree,
            "tags": task.tags,
            "created_at": task.created_at.isoformat(),
            "updated_at": task.updated_at.isoformat(),
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            "is_blocked": task.is_blocked(),
            "can_start": task.can_start()
        }

    @staticmethod
    def to_display_line(task: Task, show_details: bool = False) -> str:
        """
        将任务转换为单行显示格式

        Args:
            task: 任务对象
            show_details: 是否显示详细信息

        Returns:
            格式化的显示字符串
        """
        # 状态标记
        status_markers = {
            TaskStatus.PENDING: "[ ]",
            TaskStatus.IN_PROGRESS: "[>]",
            TaskStatus.COMPLETED: "[✓]",
            TaskStatus.BLOCKED: "[!]",
            TaskStatus.CANCELLED: "[✗]"
        }
        marker = status_markers.get(task.status, "[?]")

        # 优先级标记
        priority_markers = {
            TaskPriority.LOW: "",
            TaskPriority.MEDIUM: "",
            TaskPriority.HIGH: "⚡",
            TaskPriority.URGENT: "🔥"
        }
        priority_mark = priority_markers.get(task.priority, "")

        # 基本信息
        line = f"{marker} #{task.id}: {task.subject}"

        if priority_mark:
            line += f" {priority_mark}"

        # 负责人
        if task.owner:
            line += f" @{task.owner}"

        # 阻塞信息
        if task.blocked_by:
            line += f" (blocked by: {', '.join(f'#{id}' for id in task.blocked_by)})"

        # 工作树信息
        if task.worktree:
            line += f" [wt: {task.worktree}]"

        # 标签
        if task.tags:
            line += f" {' '.join(f'#{tag}' for tag in task.tags)}"

        # 详细信息
        if show_details:
            line += f"\n  Created: {TaskConverter._format_datetime(task.created_at)}"
            if task.completed_at:
                line += f"\n  Completed: {TaskConverter._format_datetime(task.completed_at)}"

        return line

    @staticmethod
    def to_summary(task: Task) -> str:
        """
        将任务转换为摘要格式

        Args:
            task: 任务对象

        Returns:
            摘要字符串
        """
        lines = [
            f"Task #{task.id}: {task.subject}",
            f"Status: {task.status.value}",
            f"Priority: {task.priority.value}",
        ]

        if task.description:
            lines.append(f"Description: {task.description[:100]}...")

        if task.owner:
            lines.append(f"Owner: {task.owner}")

        if task.blocked_by:
            lines.append(f"Blocked by: {', '.join(f'#{id}' for id in task.blocked_by)}")

        if task.blocks:
            lines.append(f"Blocks: {', '.join(f'#{id}' for id in task.blocks)}")

        if task.tags:
            lines.append(f"Tags: {', '.join(task.tags)}")

        lines.append(f"Created: {TaskConverter._format_datetime(task.created_at)}")
        lines.append(f"Updated: {TaskConverter._format_datetime(task.updated_at)}")

        if task.completed_at:
            lines.append(f"Completed: {TaskConverter._format_datetime(task.completed_at)}")

        return "\n".join(lines)

    @staticmethod
    def tasks_to_list_display(
        tasks: List[Task],
        group_by: str = "status",
        show_details: bool = False
    ) -> str:
        """
        将任务列表转换为显示格式

        Args:
            tasks: 任务列表
            group_by: 分组方式 (status, priority, owner)
            show_details: 是否显示详细信息

        Returns:
            格式化的列表字符串
        """
        if not tasks:
            return "No tasks."

        if group_by == "status":
            return TaskConverter._group_by_status(tasks, show_details)
        elif group_by == "priority":
            return TaskConverter._group_by_priority(tasks, show_details)
        elif group_by == "owner":
            return TaskConverter._group_by_owner(tasks, show_details)
        else:
            # 默认不分组
            lines = [TaskConverter.to_display_line(task, show_details) for task in tasks]
            return "\n".join(lines)

    @staticmethod
    def _group_by_status(tasks: List[Task], show_details: bool) -> str:
        """按状态分组"""
        groups = {
            TaskStatus.IN_PROGRESS: [],
            TaskStatus.PENDING: [],
            TaskStatus.BLOCKED: [],
            TaskStatus.COMPLETED: [],
            TaskStatus.CANCELLED: []
        }

        for task in tasks:
            groups[task.status].append(task)

        lines = []
        status_names = {
            TaskStatus.IN_PROGRESS: "🔄 In Progress",
            TaskStatus.PENDING: "⏳ Pending",
            TaskStatus.BLOCKED: "🚫 Blocked",
            TaskStatus.COMPLETED: "✅ Completed",
            TaskStatus.CANCELLED: "❌ Cancelled"
        }

        for status, status_tasks in groups.items():
            if status_tasks:
                lines.append(f"\n{status_names[status]} ({len(status_tasks)})")
                lines.append("-" * 50)
                for task in status_tasks:
                    lines.append(TaskConverter.to_display_line(task, show_details))

        return "\n".join(lines)

    @staticmethod
    def _group_by_priority(tasks: List[Task], show_details: bool) -> str:
        """按优先级分组"""
        groups = {
            TaskPriority.URGENT: [],
            TaskPriority.HIGH: [],
            TaskPriority.MEDIUM: [],
            TaskPriority.LOW: []
        }

        for task in tasks:
            groups[task.priority].append(task)

        lines = []
        priority_names = {
            TaskPriority.URGENT: "🔥 Urgent",
            TaskPriority.HIGH: "⚡ High",
            TaskPriority.MEDIUM: "📌 Medium",
            TaskPriority.LOW: "📋 Low"
        }

        for priority, priority_tasks in groups.items():
            if priority_tasks:
                lines.append(f"\n{priority_names[priority]} ({len(priority_tasks)})")
                lines.append("-" * 50)
                for task in priority_tasks:
                    lines.append(TaskConverter.to_display_line(task, show_details))

        return "\n".join(lines)

    @staticmethod
    def _group_by_owner(tasks: List[Task], show_details: bool) -> str:
        """按负责人分组"""
        groups: Dict[str, List[Task]] = {}

        for task in tasks:
            owner = task.owner or "Unassigned"
            if owner not in groups:
                groups[owner] = []
            groups[owner].append(task)

        lines = []
        for owner, owner_tasks in sorted(groups.items()):
            lines.append(f"\n👤 {owner} ({len(owner_tasks)})")
            lines.append("-" * 50)
            for task in owner_tasks:
                lines.append(TaskConverter.to_display_line(task, show_details))

        return "\n".join(lines)

    @staticmethod
    def _format_datetime(dt: datetime) -> str:
        """格式化日期时间"""
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def tasks_to_csv(tasks: List[Task]) -> str:
        """
        将任务列表转换为CSV格式

        Args:
            tasks: 任务列表

        Returns:
            CSV字符串
        """
        if not tasks:
            return ""

        lines = [
            "ID,Subject,Status,Priority,Owner,Blocked By,Tags,Created At,Updated At,Completed At"
        ]

        for task in tasks:
            blocked_by = ";".join(str(id) for id in task.blocked_by)
            tags = ";".join(task.tags)
            completed = task.completed_at.isoformat() if task.completed_at else ""

            lines.append(
                f"{task.id},"
                f'"{task.subject}",'
                f"{task.status.value},"
                f"{task.priority.value},"
                f"{task.owner},"
                f'"{blocked_by}",'
                f'"{tags}",'
                f"{task.created_at.isoformat()},"
                f"{task.updated_at.isoformat()},"
                f"{completed}"
            )

        return "\n".join(lines)
