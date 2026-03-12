"""
MainContext - 重构后的主 Agent 上下文

改进：
1. 使用 ToolRegistry 获取工具（解决循环依赖）
2. 通过依赖注入初始化
3. 只负责资源管理，不包含业务逻辑
"""
from typing import List
from langchain_core.tools import BaseTool

from backend.app.core.base_context import BaseContext
from backend.app.core.tool_registry import get_registry


class MainContext(BaseContext):
    """主 Agent 上下文"""

    def __init__(self, session_key: str, llm, session_store, tracer):
        super().__init__(session_key, llm, session_store, tracer)
        self.agent_name = "main"

    def get_tools(self) -> List[BaseTool]:
        """获取主 Agent 工具（包含 Task）"""
        registry = get_registry()
        return registry.get("main")

    def get_system_prompt(self) -> str:
        """获取系统提示词"""
        from backend.app.prompts import get_system_prompt
        return get_system_prompt(self.session_key)
