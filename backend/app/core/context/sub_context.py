"""
SubContext - 重构后的子 Agent 上下文

改进：
1. 使用 ToolRegistry 获取工具
2. 从 registry 获取 agent 配置
3. 简化初始化逻辑
"""
from typing import List
from langchain_core.tools import BaseTool

from backend.app.core.context.base_context import BaseContext
from backend.app.core.tools.tool_registry import get_registry


class SubContext(BaseContext):
    """子 Agent 上下文"""

    def __init__(self, session_key: str, subagent_type: str, llm, session_store, tracer, recursion_limit: int = 100):
        super().__init__(session_key, llm, session_store, tracer, recursion_limit)

        # 从 registry 获取配置
        from backend.app.core.registry import registry
        self.agent_config = registry.get(subagent_type)
        self.subagent_type = subagent_type
        self.agent_name = subagent_type

    def get_tools(self) -> List[BaseTool]:
        """获取子 Agent 工具（根据配置过滤）"""
        registry = get_registry()
        all_tools = registry.get("sub")

        # 如果配置是 "*"，返回所有
        if self.agent_config.tools == "*":
            return all_tools

        # 否则过滤
        allowed = set(self.agent_config.tools)
        return [t for t in all_tools if t.name in allowed]

    def get_system_prompt(self) -> str:
        """获取系统提示词"""
        return self.agent_config.prompt
