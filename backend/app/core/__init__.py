"""
Core infrastructure layer - 核心基础设施层

提供独立的、可复用的基础组件：
- ToolRegistry: 工具注册中心
- HistoryManager: 历史管理
- GuardManager: 守卫管理
- AgentRunner: 核心执行器
- BaseContext: 基础上下文
- MainContext/SubContext/TeamContext: 具体上下文实现
"""

from backend.app.core.tools.tool_registry import ToolRegistry, get_registry
from backend.app.core.context.base_context import BaseContext
from backend.app.core.context.main_context import MainContext
from backend.app.core.context.sub_context import SubContext
from backend.app.core.context.team_context import TeamContext
from backend.app.core.tools.history_manager import HistoryManager
from backend.app.core.guards import GuardManager
from backend.app.core.execution.agent_runner import AgentRunner

__all__ = [
    "ToolRegistry",
    "get_registry",
    "BaseContext",
    "MainContext",
    "SubContext",
    "TeamContext",
    "HistoryManager",
    "GuardManager",
    "AgentRunner",
]
