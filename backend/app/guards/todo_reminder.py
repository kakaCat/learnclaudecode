"""
TodoWrite 提醒守卫 - 督促定期更新待办事项
"""


class TodoReminderGuard:
    """追踪 TodoWrite 调用频率，超过阈值时提醒"""

    def __init__(self, threshold: int = 3):
        self.rounds_without_todo = 0
        self.threshold = threshold

    def on_tool_call(self, tool_name: str):
        """工具调用后更新状态"""
        if tool_name == "TodoWrite":
            self.rounds_without_todo = 0
        else:
            self.rounds_without_todo += 1

    def should_remind(self) -> bool:
        """是否需要提醒"""
        return self.rounds_without_todo >= self.threshold

    def get_reminder_message(self) -> str:
        """获取提醒消息"""
        return "<reminder>请更新你的 TodoWrite 待办事项。</reminder>"

    def reset(self):
        """重置状态（切换 session 时使用）"""
        self.rounds_without_todo = 0
