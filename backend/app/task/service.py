"""
Task Service - 业务逻辑层
负责任务的业务操作和编排
"""
from datetime import datetime
from typing import List, Optional
import logging

from backend.app.task.models import Task, TaskStatus, TaskPriority
from backend.app.task.repository import TaskRepository
from backend.app.task.exceptions import InvalidTaskStatusError, TaskNotFoundError, TaskValidationError
from backend.app.core import tracer

logger = logging.getLogger(__name__)


class TaskService:
    """任务业务服务"""

    def __init__(self, repository: Optional[TaskRepository] = None):
        """
        初始化Service

        Args:
            repository: 任务仓储，默认创建新实例
        """
        self.repository = repository or TaskRepository()

    def create_task(
        self,
        subject: str,
        description: str = "",
        priority: TaskPriority = TaskPriority.MEDIUM,
        owner: str = "",
        tags: Optional[List[str]] = None
    ) -> Task:
        """
        创建新任务

        Args:
            subject: 任务主题
            description: 任务描述
            priority: 任务优先级
            owner: 任务负责人
            tags: 任务标签

        Returns:
            创建的任务对象

        Raises:
            TaskValidationError: 任务数据验证失败
        """
        task_id = self.repository.get_next_id()
        now = datetime.now()

        task = Task(
            id=task_id,
            subject=subject,
            description=description,
            status=TaskStatus.PENDING,
            priority=priority,
            blocked_by=[],
            blocks=[],
            owner=owner,
            worktree="",
            tags=tags or [],
            created_at=now,
            updated_at=now
        )

        self.repository.save(task)
        tracer.emit("task.create", task_id=task_id, subject=subject, priority=priority.value)
        logger.info(f"Task created: {task_id} - {subject}")

        return task

    def get_task(self, task_id: int) -> Task:
        """
        获取任务

        Args:
            task_id: 任务ID

        Returns:
            任务对象

        Raises:
            TaskNotFoundError: 任务不存在
        """
        return self.repository.get_by_id(task_id)

    def update_task(
        self,
        task_id: int,
        subject: Optional[str] = None,
        description: Optional[str] = None,
        priority: Optional[TaskPriority] = None,
        owner: Optional[str] = None
    ) -> Task:
        """
        更新任务基本信息

        Args:
            task_id: 任务ID
            subject: 新主题
            description: 新描述
            priority: 新优先级
            owner: 新负责人

        Returns:
            更新后的任务对象

        Raises:
            TaskNotFoundError: 任务不存在
        """
        task = self.repository.get_by_id(task_id)

        if subject is not None:
            task.subject = subject
        if description is not None:
            task.description = description
        if priority is not None:
            task.priority = priority
        if owner is not None:
            task.owner = owner

        task.updated_at = datetime.now()
        self.repository.save(task)

        logger.info(f"Task updated: {task_id}")
        return task

    def change_status(
        self,
        task_id: int,
        status: TaskStatus
    ) -> Task:
        """
        更改任务状态

        Args:
            task_id: 任务ID
            status: 新状态

        Returns:
            更新后的任务对象

        Raises:
            TaskNotFoundError: 任务不存在
            InvalidTaskStatusError: 无效的状态转换
        """
        task = self.repository.get_by_id(task_id)
        old_status = task.status

        # 验证状态转换
        self._validate_status_transition(old_status, status)

        task.status = status
        task.updated_at = datetime.now()

        # 如果任务完成，记录完成时间并解除阻塞
        if status == TaskStatus.COMPLETED:
            task.completed_at = datetime.now()
            self._unblock_dependent_tasks(task_id)

        self.repository.save(task)

        # 发送状态变更事件
        tracer.emit(
            "task.status_changed",
            task_id=task_id,
            subject=task.subject,
            from_status=old_status.value,
            to_status=status.value
        )

        logger.info(f"Task {task_id} status changed: {old_status.value} -> {status.value}")
        return task

    def start_task(self, task_id: int, owner: str = "") -> Task:
        """
        开始任务

        Args:
            task_id: 任务ID
            owner: 任务负责人

        Returns:
            更新后的任务对象

        Raises:
            TaskNotFoundError: 任务不存在
            TaskValidationError: 任务被阻塞，无法开始
        """
        task = self.repository.get_by_id(task_id)

        if task.is_blocked():
            raise TaskValidationError(
                f"Task {task_id} is blocked by tasks: {task.blocked_by}"
            )

        if owner:
            task.owner = owner

        task.status = TaskStatus.IN_PROGRESS
        task.updated_at = datetime.now()
        self.repository.save(task)

        tracer.emit("task.started", task_id=task_id, owner=task.owner)
        logger.info(f"Task {task_id} started by {task.owner}")

        return task

    def complete_task(self, task_id: int) -> Task:
        """
        完成任务

        Args:
            task_id: 任务ID

        Returns:
            更新后的任务对象

        Raises:
            TaskNotFoundError: 任务不存在
        """
        return self.change_status(task_id, TaskStatus.COMPLETED)

    def cancel_task(self, task_id: int) -> Task:
        """
        取消任务

        Args:
            task_id: 任务ID

        Returns:
            更新后的任务对象

        Raises:
            TaskNotFoundError: 任务不存在
        """
        task = self.change_status(task_id, TaskStatus.CANCELLED)
        # 取消任务时也解除对其他任务的阻塞
        self._unblock_dependent_tasks(task_id)
        return task

    def add_dependency(
        self,
        task_id: int,
        depends_on: int
    ) -> Task:
        """
        添加任务依赖（task_id 依赖于 depends_on）

        Args:
            task_id: 任务ID
            depends_on: 依赖的任务ID

        Returns:
            更新后的任务对象

        Raises:
            TaskNotFoundError: 任务不存在
            TaskValidationError: 循环依赖
        """
        task = self.repository.get_by_id(task_id)
        blocking_task = self.repository.get_by_id(depends_on)

        # 检查循环依赖
        if self._has_circular_dependency(task_id, depends_on):
            raise TaskValidationError(
                f"Circular dependency detected: {task_id} -> {depends_on}"
            )

        # 添加依赖关系
        task.add_blocker(depends_on)
        self.repository.save(task)

        # 更新阻塞任务的blocks列表
        if task_id not in blocking_task.blocks:
            blocking_task.blocks.append(task_id)
            blocking_task.updated_at = datetime.now()
            self.repository.save(blocking_task)

        logger.info(f"Task {task_id} now depends on task {depends_on}")
        return task

    def remove_dependency(
        self,
        task_id: int,
        depends_on: int
    ) -> Task:
        """
        移除任务依赖

        Args:
            task_id: 任务ID
            depends_on: 依赖的任务ID

        Returns:
            更新后的任务对象

        Raises:
            TaskNotFoundError: 任务不存在
        """
        task = self.repository.get_by_id(task_id)
        task.remove_blocker(depends_on)
        self.repository.save(task)

        # 更新阻塞任务的blocks列表
        try:
            blocking_task = self.repository.get_by_id(depends_on)
            if task_id in blocking_task.blocks:
                blocking_task.blocks.remove(task_id)
                blocking_task.updated_at = datetime.now()
                self.repository.save(blocking_task)
        except TaskNotFoundError:
            pass

        logger.info(f"Removed dependency: task {task_id} no longer depends on {depends_on}")
        return task

    def bind_worktree(
        self,
        task_id: int,
        worktree: str,
        owner: str = ""
    ) -> Task:
        """
        绑定工作树到任务

        Args:
            task_id: 任务ID
            worktree: 工作树名称
            owner: 任务负责人

        Returns:
            更新后的任务对象

        Raises:
            TaskNotFoundError: 任务不存在
        """
        task = self.repository.get_by_id(task_id)

        task.worktree = worktree
        if owner:
            task.owner = owner

        # 如果任务是待开始状态，自动转为进行中
        if task.status == TaskStatus.PENDING:
            task.status = TaskStatus.IN_PROGRESS

        task.updated_at = datetime.now()
        self.repository.save(task)

        tracer.emit(
            "task.worktree_bound",
            task_id=task_id,
            subject=task.subject,
            worktree=worktree,
            owner=owner or task.owner
        )

        logger.info(f"Task {task_id} bound to worktree: {worktree}")
        return task

    def unbind_worktree(self, task_id: int) -> Task:
        """
        解绑工作树

        Args:
            task_id: 任务ID

        Returns:
            更新后的任务对象

        Raises:
            TaskNotFoundError: 任务不存在
        """
        task = self.repository.get_by_id(task_id)
        task.worktree = ""
        task.updated_at = datetime.now()
        self.repository.save(task)

        logger.info(f"Task {task_id} worktree unbound")
        return task

    def add_tag(self, task_id: int, tag: str) -> Task:
        """
        添加标签

        Args:
            task_id: 任务ID
            tag: 标签

        Returns:
            更新后的任务对象

        Raises:
            TaskNotFoundError: 任务不存在
        """
        task = self.repository.get_by_id(task_id)
        task.add_tag(tag)
        self.repository.save(task)

        logger.info(f"Tag '{tag}' added to task {task_id}")
        return task

    def remove_tag(self, task_id: int, tag: str) -> Task:
        """
        移除标签

        Args:
            task_id: 任务ID
            tag: 标签

        Returns:
            更新后的任务对象

        Raises:
            TaskNotFoundError: 任务不存在
        """
        task = self.repository.get_by_id(task_id)
        task.remove_tag(tag)
        self.repository.save(task)

        logger.info(f"Tag '{tag}' removed from task {task_id}")
        return task

    def delete_task(self, task_id: int) -> None:
        """
        删除任务

        Args:
            task_id: 任务ID

        Raises:
            TaskNotFoundError: 任务不存在
        """
        # 先解除所有依赖关系
        task = self.repository.get_by_id(task_id)

        # 解除对其他任务的阻塞
        for blocked_task_id in task.blocks:
            try:
                self.remove_dependency(blocked_task_id, task_id)
            except TaskNotFoundError:
                pass

        # 从阻塞任务中移除引用
        for blocking_task_id in task.blocked_by:
            try:
                blocking_task = self.repository.get_by_id(blocking_task_id)
                if task_id in blocking_task.blocks:
                    blocking_task.blocks.remove(task_id)
                    blocking_task.updated_at = datetime.now()
                    self.repository.save(blocking_task)
            except TaskNotFoundError:
                pass

        # 删除任务
        self.repository.delete(task_id)
        tracer.emit("task.deleted", task_id=task_id)
        logger.info(f"Task {task_id} deleted")

    def list_all_tasks(self) -> List[Task]:
        """
        获取所有任务

        Returns:
            任务列表
        """
        return self.repository.find_all()

    def list_tasks_by_status(self, status: TaskStatus) -> List[Task]:
        """
        根据状态获取任务列表

        Args:
            status: 任务状态

        Returns:
            任务列表
        """
        return self.repository.find_by_status(status)

    def list_tasks_by_owner(self, owner: str) -> List[Task]:
        """
        根据负责人获取任务列表

        Args:
            owner: 负责人

        Returns:
            任务列表
        """
        return self.repository.find_by_owner(owner)

    def list_tasks_by_priority(self, priority: TaskPriority) -> List[Task]:
        """
        根据优先级获取任务列表

        Args:
            priority: 优先级

        Returns:
            任务列表
        """
        return self.repository.find_by_priority(priority)

    def list_tasks_by_tags(self, tags: List[str]) -> List[Task]:
        """
        根据标签获取任务列表

        Args:
            tags: 标签列表

        Returns:
            包含任意指定标签的任务列表
        """
        return self.repository.find_by_tags(tags)

    def list_blocked_tasks(self) -> List[Task]:
        """
        获取所有被阻塞的任务

        Returns:
            被阻塞的任务列表
        """
        return self.repository.find_blocked_tasks()

    def list_available_tasks(self) -> List[Task]:
        """
        获取所有可开始的任务

        Returns:
            可开始的任务列表
        """
        return self.repository.find_available_tasks()

    def _validate_status_transition(
        self,
        from_status: TaskStatus,
        to_status: TaskStatus
    ) -> None:
        """
        验证状态转换是否合法

        Args:
            from_status: 原状态
            to_status: 目标状态

        Raises:
            InvalidTaskStatusError: 非法的状态转换
        """
        # 定义合法的状态转换
        valid_transitions = {
            TaskStatus.PENDING: [TaskStatus.IN_PROGRESS, TaskStatus.CANCELLED],
            TaskStatus.IN_PROGRESS: [TaskStatus.COMPLETED, TaskStatus.BLOCKED, TaskStatus.CANCELLED],
            TaskStatus.BLOCKED: [TaskStatus.IN_PROGRESS, TaskStatus.CANCELLED],
            TaskStatus.COMPLETED: [],  # 完成后不能转换
            TaskStatus.CANCELLED: []   # 取消后不能转换
        }

        if to_status not in valid_transitions.get(from_status, []):
            raise InvalidTaskStatusError(
                f"Invalid status transition: {from_status.value} -> {to_status.value}"
            )

    def _unblock_dependent_tasks(self, completed_task_id: int) -> None:
        """
        解除依赖任务的阻塞状态

        Args:
            completed_task_id: 已完成的任务ID
        """
        all_tasks = self.repository.find_all()
        for task in all_tasks:
            if completed_task_id in task.blocked_by:
                task.remove_blocker(completed_task_id)
                self.repository.save(task)
                logger.info(f"Task {task.id} unblocked by completion of task {completed_task_id}")

    def _has_circular_dependency(
        self,
        task_id: int,
        depends_on: int,
        visited: Optional[set] = None
    ) -> bool:
        """
        检查是否存在循环依赖

        Args:
            task_id: 任务ID
            depends_on: 依赖的任务ID
            visited: 已访问的任务集合

        Returns:
            是否存在循环依赖
        """
        if visited is None:
            visited = set()

        if depends_on == task_id:
            return True

        if depends_on in visited:
            return False

        visited.add(depends_on)

        try:
            blocking_task = self.repository.get_by_id(depends_on)
            for blocker_id in blocking_task.blocked_by:
                if self._has_circular_dependency(task_id, blocker_id, visited):
                    return True
        except TaskNotFoundError:
            pass

        return False
