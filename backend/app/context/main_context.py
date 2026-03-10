"""
MainContext - 主 Agent 上下文

继承 BaseContext，添加 Main Agent 独有资源：
- tools: 工具列表（包含 Task tool）
- agent: LangChain Agent 实例
"""
from typing import List
from langchain_core.tools import BaseTool
from langchain.agents import create_agent

from backend.app.context.base_context import BaseContext
from backend.app.tools.manager import tool_manager
from backend.app.prompts import get_system_prompt


class MainContext(BaseContext):
    """
    主 Agent 上下文

    继承 BaseContext 的共享资源，添加 Main Agent 独有资源
    """

    def __init__(self, session_key: str):
        """
        初始化主上下文

        Args:
            session_key: 会话标识符
        """
        # 调用父类初始化（共享资源）
        super().__init__(session_key)

        # ============================================================
        # Main Agent 独有资源
        # ============================================================

        # 1. Tools（包含 Task tool）
        # 注意：需要先初始化 tool_manager，并传递 self 以便 Task tool 可以访问 MainContext
        tool_manager._ensure_initialized(main_context=self)
        self.tools: List[BaseTool] = tool_manager.get_main_tools()

        # 更新父类的 tools
        self.overflow_guard.tools = self.tools
        self.conversation_history.tools = self.tools

        # 2. System Prompt
        self.system_prompt: str = get_system_prompt(session_key)

        # 3. Agent
        self.agent = create_agent(
            self.llm,
            self.tools,
            system_prompt=self.system_prompt
        )

    def set_session_key(self, session_key: str):
        """
        更新会话 key

        Args:
            session_key: 新的会话标识符
        """
        self.session_key = session_key
        self.session_store.set_current_key(session_key)

        # 重新初始化依赖 session_key 的组件
        self.system_prompt = get_system_prompt(session_key)
        self.agent = create_agent(
            self.llm,
            self.tools,
            system_prompt=self.system_prompt
        )
