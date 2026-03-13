"""
Task 数据模型定义
"""
from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class TaskStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class TaskPriority(str, Enum):
    """任务优先级"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class Task(BaseModel):
    """任务数据模型"""
    id: int = Field(..., description="任务ID", gt=0)
    subject: str = Field(..., min_length=1, max_length=200, description="任务主题")
    description: str = Field(default="", max_length=2000, description="任务描述")
    status: TaskStatus = Field(default=TaskStatus.PENDING, description="任务状态")
    priority: TaskPriority = Field(default=TaskPriority.MEDIUM, description="任务优先级")
    blocked_by: List[int] = Field(default_factory=list, description="被哪些任务阻塞")
    blocks: List[int] = Field(default_factory=list, description="阻塞哪些任务")
    owner: str = Field(default="", max_length=100, description="任务负责人")
    worktree: str = Field(default="", max_length=100, description="关联的工作树")
    tags: List[str] = Field(default_factory=list, description="任务标签")
    plan: str = Field(default="", description="任务执行计划")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    completed_at: Optional[datetime] = Field(default=None, description="完成时间")

    class Config:
        # 移除 use_enum_values = True，保持 Enum 类型安全
        # 序列化时手动调用 .value（在 Converter 中处理）
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

    @field_validator('blocked_by', 'blocks')
    @classmethod
    def validate_task_ids(cls, v: List[int]) -> List[int]:
        """验证任务ID列表"""
        if not all(isinstance(i, int) and i > 0 for i in v):
            raise ValueError("Task IDs must be positive integers")
        return list(set(v))  # 去重

    @field_validator('tags')
    @classmethod
    def validate_tags(cls, v: List[str]) -> List[str]:
        """验证标签"""
        return [tag.strip().lower() for tag in v if tag.strip()]

    def is_blocked(self) -> bool:
        """检查任务是否被阻塞"""
        return len(self.blocked_by) > 0

    def can_start(self) -> bool:
        """检查任务是否可以开始"""
        return self.status == TaskStatus.PENDING and not self.is_blocked()

    def mark_completed(self) -> None:
        """标记任务为完成"""
        self.status = TaskStatus.COMPLETED
        self.completed_at = datetime.now()
        self.updated_at = datetime.now()

    def add_blocker(self, task_id: int) -> None:
        """添加阻塞任务"""
        if task_id not in self.blocked_by:
            self.blocked_by.append(task_id)
            self.updated_at = datetime.now()

    def remove_blocker(self, task_id: int) -> None:
        """移除阻塞任务"""
        if task_id in self.blocked_by:
            self.blocked_by.remove(task_id)
            self.updated_at = datetime.now()

    def add_tag(self, tag: str) -> None:
        """添加标签"""
        tag = tag.strip().lower()
        if tag and tag not in self.tags:
            self.tags.append(tag)
            self.updated_at = datetime.now()

    def remove_tag(self, tag: str) -> None:
        """移除标签"""
        tag = tag.strip().lower()
        if tag in self.tags:
            self.tags.remove(tag)
            self.updated_at = datetime.now()
