"""
Tool implementations module - 工具实现模块

目录结构：
- core/: 核心工具（file）
- agent/: Agent 相关（spawn、task）
- storage/: 存储相关（memory、workspace）
- execution/: 执行相关（background、skill）
- integration/: 集成工具（mcp、cdp、explore、browser）
- system/: 系统工具（compact、worktree、team）
"""

# 核心工具 - 文件操作和探索
from backend.app.tools.implementations.core import (
    read_file,
    write_file,
    edit_file,
    append_file,
    bash,
    glob,
    grep,
    list_dir,
)

# Agent 相关工具 - Agent 协作和任务管理
from backend.app.tools.implementations.agent import (
    task_create,
    task_get,
    task_list,
    task_update,
)

# 存储工具 - 数据持久化和工作空间
from backend.app.tools.implementations.storage import (
    memory_write,
    memory_append,
    memory_search,
    workspace_write,
    workspace_read,
)

# 执行工具 - 后台执行和技能调用
from backend.app.tools.implementations.execution import (
    background_run,
    background_agent,
    check_background,
    load_skill,
)

# 集成工具 - 外部服务和协议
from backend.app.tools.implementations.integration import (
    cdp_browser,
    browser_navigate,
    browser_click,
    browser_input,
    browser_extract,
    browser_screenshot,
    browser_get_page_content,
)

# 系统工具 - 系统级操作
from backend.app.tools.implementations.system import (
    compact,
    worktree_create,
    worktree_list,
    worktree_remove,
    worktree_status,
    worktree_run,
    worktree_keep,
    worktree_events,
    task_bind_worktree,
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
    # core
    "read_file",
    "write_file",
    "edit_file",
    "append_file",
    "bash",
    "glob",
    "grep",
    "list_dir",
    # agent
    "task_create",
    "task_get",
    "task_list",
    "task_update",
    # storage
    "memory_write",
    "memory_append",
    "memory_search",
    "workspace_write",
    "workspace_read",
    # execution
    "background_run",
    "background_agent",
    "check_background",
    "load_skill",
    # integration
    "cdp_browser",
    "glob",
    "grep",
    "list_dir",
    "browser_navigate",
    "browser_click",
    "browser_input",
    "browser_extract",
    "browser_screenshot",
    "browser_get_page_content",
    # system
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
