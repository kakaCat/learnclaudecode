"""
Tool implementations module - 工具实现模块

目录结构：
- core/: 核心工具（file）
- agent/: Agent 相关（spawn、task）
- storage/: 存储相关（memory、workspace）
- execution/: 执行相关（background、skill）
- integration/: 集成工具（mcp、cdp、curl、explore）
- system/: 系统工具（compact、worktree、team）
"""

# 核心工具 - 文件操作
from backend.app.tools.implementations.core import file_tool

# Agent 相关工具 - Agent 协作和任务管理
from backend.app.tools.implementations.agent import spawn_tool, task_tool

# 存储工具 - 数据持久化和工作空间
from backend.app.tools.implementations.storage import memory_tools, workspace_tool

# 执行工具 - 后台执行和技能调用
from backend.app.tools.implementations.execution import background_tool, skill_tool

# 集成工具 - 外部服务和协议
from backend.app.tools.implementations.integration import cdp_tool, curl_tool, explore_tool
from backend.app.tools.mcp import mcp_tool

# 系统工具 - 系统级操作
from backend.app.tools.implementations.system import compact_tool, worktree_tool, team_tool

__all__ = [
    # core
    "file_tool",
    # agent
    "spawn_tool",
    "task_tool",
    # storage
    "memory_tools",
    "workspace_tool",
    # execution
    "background_tool",
    "skill_tool",
    # integration
    "mcp_tool",
    "cdp_tool",
    "curl_tool",
    "explore_tool",
    # system
    "compact_tool",
    "worktree_tool",
    "team_tool",
]
