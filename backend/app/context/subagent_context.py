"""
SubagentContext - 子 Agent 上下文

继承 BaseContext，添加 Subagent 独有资源：
- subagent_type: Subagent 类型
- tools: 过滤后的工具列表（不包含 Task tool）
- agent: LangChain Agent 实例
"""
from typing import List
from langchain_core.tools import BaseTool
from langchain.agents import create_agent

from backend.app.context.base_context import BaseContext
from backend.app.subagents import AGENT_TYPES
from backend.app.tools.manager import tool_manager


class SubagentContext(BaseContext):
    """
    子 Agent 上下文

    继承 BaseContext 的共享资源，添加 Subagent 独有资源
    """

    def __init__(self, session_key: str, subagent_type: str):
        """
        初始化子上下文

        Args:
            session_key: 会话标识符（与 MainContext 相同）
            subagent_type: Subagent 类型（如 "Explore", "Plan"）
        """
        if subagent_type not in AGENT_TYPES:
            raise ValueError(f"Unknown subagent type: {subagent_type}")

        # 调用父类初始化（共享资源）
        super().__init__(session_key)

        # ============================================================
        # Subagent 独有资源
        # ============================================================

        self.subagent_type: str = subagent_type

        # 1. 过滤工具列表
        self.tools: List[BaseTool] = self._filter_tools()

        # 更新父类的 tools
        self.overflow_guard.tools = self.tools
        self.conversation_history.tools = self.tools

        # 2. 获取 Subagent 的 system prompt
        agent_config = AGENT_TYPES[subagent_type]
        self.system_prompt: str = agent_config["prompt"]

        # 3. 创建 Agent（使用继承的 LLM）
        self.agent = create_agent(
            self.llm,  # 继承自 BaseContext
            self.tools,
            system_prompt=self.system_prompt
        )

    def _filter_tools(self) -> List[BaseTool]:
        """
        根据 Subagent 类型过滤工具列表

        Returns:
            过滤后的工具列表
        """
        agent_config = AGENT_TYPES[self.subagent_type]
        allowed_tool_names = agent_config["tools"]

        # 获取所有工具（不包含 Task）
        all_tools = tool_manager.get_subagent_tools()

        # 如果是 "*"，返回所有工具
        if allowed_tool_names == "*":
            return all_tools

        # 否则，只返回允许的工具
        allowed_set = set(allowed_tool_names)
        return [
            tool for tool in all_tools
            if tool.name in allowed_set
        ]
