"""
系统工具模块

包含系统级操作和管理工具：
- compact_tool: 上下文压缩工具
- worktree_tool: Git worktree 管理
- team_tool: 团队协作工具
"""

from .compact_tool import compact
from .worktree_tool import (
    worktree_create,
    worktree_list,
    worktree_remove,
    worktree_status,
    worktree_run,
    worktree_keep,
    worktree_events,
    task_bind_worktree,
)
from .team_tool import (
    spawn_teammate,
    list_teammates,
    send_message,
    read_inbox,
    broadcast,
    claim_task,
    idle,
    shutdown_request,
    check_shutdown_status,
    plan_approval,
)

__all__ = [
    "compact",
    "worktree_create",
    "worktree_list",
    "worktree_remove",
    "worktree_status",
    "worktree_run",
    "worktree_keep",
    "worktree_events",
    "task_bind_worktree",
    "spawn_teammate",
    "list_teammates",
    "send_message",
    "read_inbox",
    "broadcast",
    "claim_task",
    "idle",
    "shutdown_request",
    "check_shutdown_status",
    "plan_approval",
]
