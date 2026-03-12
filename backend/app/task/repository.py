"""
Task Repository - 数据访问层
负责任务的持久化操作
"""
import json
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
from contextlib import contextmanager
import logging

from backend.app.task.models import Task, TaskStatus, TaskPriority
from backend.app.task.exceptions import TaskNotFoundError, TaskValidationError
from backend.app.session import get_tasks_dir, get_task_file_path

logger = logging.getLogger(__name__)


def _slug(text: str) -> str:
    """生成文件名slug"""
    return re.sub(r"[^a-z0-9]+", "-", text.lower())[:40].strip("-")


class TaskRepository:
    """任务数据访问层 - 使用文件系统存储"""

    def __init__(self, tasks_dir: Optional[Path] = None):
        """
        初始化Repository

        Args:
            tasks_dir: 任务存储目录，默认使用session配置
        """
        self._tasks_dir = tasks_dir or get_tasks_dir()
        self._ensure_directory()

    @property
    def tasks_dir(self) -> Path:
        """获取任务目录"""
        return self._tasks_dir

    def _ensure_directory(self) -> None:
        """确保任务目录存在"""
        self.tasks_dir.mkdir(parents=True, exist_ok=True)

    def get_next_id(self) -> int:
        """获取下一个可用的任务ID"""
        ids = [
            int(f.stem.split("_")[1])
            for f in self.tasks_dir.glob("task_*.json")
            if f.stem.split("_")[1].isdigit()
        ]
        return max(ids) + 1 if ids else 1

    def _find_file(self, task_id: int) -> Path:
        """
        查找任务文件

        Args:
            task_id: 任务ID

        Returns:
            任务文件路径

        Raises:
            TaskNotFoundError: 任务不存在
        """
        matches = list(self.tasks_dir.glob(f"task_{task_id}_*.json"))
        if not matches:
            raise TaskNotFoundError(task_id)
        return matches[0]

    def exists(self, task_id: int) -> bool:
        """检查任务是否存在"""
        return bool(list(self.tasks_dir.glob(f"task_{task_id}_*.json")))

    def get_by_id(self, task_id: int) -> Task:
        """
        根据ID获取任务

        Args:
            task_id: 任务ID

        Returns:
            任务对象

        Raises:
            TaskNotFoundError: 任务不存在
        """
        file_path = self._find_file(task_id)
        return self._load_from_file(file_path)

    def save(self, task: Task) -> None:
        """
        保存任务

        Args:
            task: 任务对象

        Raises:
            TaskValidationError: 任务数据验证失败
        """
        try:
            # 删除旧文件
            for old_file in self.tasks_dir.glob(f"task_{task.id}_*.json"):
                old_file.unlink()

            # 保存新文件
            slug = _slug(task.subject)
            file_path = get_task_file_path(task.id, slug)
            self._save_to_file(task, file_path)

            logger.info(f"Task {task.id} saved successfully")
        except Exception as e:
            logger.error(f"Failed to save task {task.id}: {e}")
            raise TaskValidationError(f"Failed to save task: {e}")

    def delete(self, task_id: int) -> None:
        """
        删除任务

        Args:
            task_id: 任务ID

        Raises:
            TaskNotFoundError: 任务不存在
        """
        file_path = self._find_file(task_id)
        file_path.unlink()
        logger.info(f"Task {task_id} deleted")

    def find_all(self) -> List[Task]:
        """
        获取所有任务

        Returns:
            任务列表
        """
        tasks = []
        for file_path in sorted(self.tasks_dir.glob("task_*.json")):
            try:
                task = self._load_from_file(file_path)
                tasks.append(task)
            except Exception as e:
                logger.warning(f"Failed to load task from {file_path}: {e}")
        return tasks

    def find_by_status(self, status: TaskStatus) -> List[Task]:
        """
        根据状态查询任务

        Args:
            status: 任务状态

        Returns:
            任务列表
        """
        return [task for task in self.find_all() if task.status == status]

    def find_by_owner(self, owner: str) -> List[Task]:
        """
        根据负责人查询任务

        Args:
            owner: 负责人

        Returns:
            任务列表
        """
        return [task for task in self.find_all() if task.owner == owner]

    def find_by_priority(self, priority: TaskPriority) -> List[Task]:
        """
        根据优先级查询任务

        Args:
            priority: 优先级

        Returns:
            任务列表
        """
        return [task for task in self.find_all() if task.priority == priority]

    def find_by_tags(self, tags: List[str]) -> List[Task]:
        """
        根据标签查询任务

        Args:
            tags: 标签列表

        Returns:
            包含任意指定标签的任务列表
        """
        tags_lower = [tag.lower() for tag in tags]
        return [
            task for task in self.find_all()
            if any(tag in task.tags for tag in tags_lower)
        ]

    def find_blocked_tasks(self) -> List[Task]:
        """
        查询所有被阻塞的任务

        Returns:
            被阻塞的任务列表
        """
        return [task for task in self.find_all() if task.is_blocked()]

    def find_available_tasks(self) -> List[Task]:
        """
        查询所有可开始的任务

        Returns:
            可开始的任务列表
        """
        return [task for task in self.find_all() if task.can_start()]

    def _load_from_file(self, file_path: Path) -> Task:
        """从文件加载任务"""
        data = json.loads(file_path.read_text(encoding='utf-8'))
        return self._deserialize(data)

    def _save_to_file(self, task: Task, file_path: Path) -> None:
        """保存任务到文件"""
        data = self._serialize(task)
        file_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding='utf-8'
        )

    def _serialize(self, task: Task) -> Dict[str, Any]:
        """序列化任务对象"""
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
            "completed_at": task.completed_at.isoformat() if task.completed_at else None
        }

    def _deserialize(self, data: Dict[str, Any]) -> Task:
        """反序列化任务对象"""
        return Task(
            id=data["id"],
            subject=data["subject"],
            description=data.get("description", ""),
            status=TaskStatus(data.get("status", "pending")),
            priority=TaskPriority(data.get("priority", "medium")),
            blocked_by=data.get("blocked_by", []),
            blocks=data.get("blocks", []),
            owner=data.get("owner", ""),
            worktree=data.get("worktree", ""),
            tags=data.get("tags", []),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None
        )

    @contextmanager
    def transaction(self):
        """
        事务上下文管理器（简单实现）

        在实际数据库实现中，这里会处理真正的事务
        """
        try:
            yield self
        except Exception as e:
            logger.error(f"Transaction failed: {e}")
            raise
