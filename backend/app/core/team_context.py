"""
TeamContext - 重构后的团队 Agent 上下文

改进：
1. 使用 ToolRegistry 获取工具
2. 通信工具静态注册，通过参数绑定
3. 简化初始化逻辑
"""
from typing import List
from langchain_core.tools import BaseTool

from backend.app.core.base_context import BaseContext
from backend.app.core.tool_registry import get_registry


class TeamContext(BaseContext):
    """团队 Agent 上下文"""

    def __init__(
        self,
        session_key: str,
        name: str,
        role: str,
        llm,
        session_store,
        tracer
    ):
        super().__init__(session_key, llm, session_store, tracer)
        self.name = name
        self.role = role
        self.agent_name = name

    def get_tools(self) -> List[BaseTool]:
        """获取团队 Agent 工具"""
        registry = get_registry()
        tools = registry.get("team")

        # TODO: 绑定通信工具的 from_name 参数
        # 使用 functools.partial 或工具包装器

        return tools

    def get_system_prompt(self) -> str:
        """获取系统提示词"""
        from backend.app.prompts import get_teammate_system_prompt
        return get_teammate_system_prompt(self.name, self.role, self.session_key)
