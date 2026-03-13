"""
GuardManager - 守卫管理器

职责：
1. 统一管理所有守卫检查
2. 注入守卫消息
3. 更新守卫状态
"""
from typing import List
from langchain_core.messages import BaseMessage, HumanMessage


class GuardManager:
    """守卫管理器"""

    def __init__(self):
        from backend.app.guards.todo_reminder import TodoReminderGuard
        from backend.app.guards.reflection_gate import ReflectionGatekeeper
        from backend.app.guards.action_commitment_guard import ActionCommitmentGuard

        self.todo_reminder = TodoReminderGuard()
        self.reflection_gate = ReflectionGatekeeper()
        self.action_commitment = ActionCommitmentGuard()

    def inject_messages(self, messages: List[BaseMessage]) -> List[BaseMessage]:
        """
        注入守卫消息

        Args:
            messages: 原始消息列表

        Returns:
            注入守卫消息后的列表
        """
        result = messages.copy()

        # Todo 提醒
        if self.todo_reminder.should_remind():
            result.append(
                HumanMessage(content=self.todo_reminder.get_reminder_message())
            )

        # Reflection 门禁
        if self.reflection_gate.should_gate():
            result.append(
                HumanMessage(content=self.reflection_gate.get_gate_message())
            )

        return result

    def on_tool_call(self, tool_name: str, subagent_type: str = "", result: str = ""):
        """
        工具调用后更新守卫状态

        Args:
            tool_name: 工具名称
            subagent_type: Subagent 类型（如果是 Task 工具）
            result: 工具结果
        """
        self.todo_reminder.on_tool_call(tool_name)
        self.reflection_gate.on_tool_call(tool_name, subagent_type, result)

    def check_commitment(self, message) -> str:
        """
        检查是否违反 "先做后说" 原则

        Args:
            message: AI 消息

        Returns:
            警告信息（如果有违规）
        """
        return self.action_commitment.inject_warning_if_needed(message)

    def reset(self):
        """重置所有守卫状态"""
        self.todo_reminder.reset()
        self.reflection_gate.reset()
