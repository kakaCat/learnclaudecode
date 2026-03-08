"""
Notification Service - 聚合所有通知源，解耦 agent 与具体通知系统
"""
import json
from langchain_core.messages import HumanMessage, AIMessage


class NotificationService:
    """聚合来自后台任务、团队消息等通知源"""

    def get_pending_messages(self) -> list:
        """
        获取所有待注入的通知消息

        Returns:
            list: 格式化好的 LangChain 消息列表 [HumanMessage, AIMessage, ...]
        """
        messages = []

        # 1. 团队 inbox 消息
        inbox_msgs = self._get_inbox_messages()
        if inbox_msgs:
            messages.extend(inbox_msgs)

        # 2. 后台任务完成通知
        bg_msgs = self._get_background_notifications()
        if bg_msgs:
            messages.extend(bg_msgs)

        return messages

    def _get_inbox_messages(self) -> list:
        """获取团队 inbox 消息（如果 team 已初始化）"""
        try:
            from backend.app.team import get_bus, state as _team_state

            # 只在 team 已初始化时读取
            if _team_state._bus is None:
                return []

            inbox = get_bus().read_inbox("lead")
            if not inbox:
                return []

            return [
                HumanMessage(content=f"<inbox>{json.dumps(inbox, indent=2)}</inbox>"),
                AIMessage(content="Noted inbox messages.")
            ]
        except ImportError:
            return []

    def _get_background_notifications(self) -> list:
        """获取后台任务完成通知"""
        try:
            from backend.app.background import drain_notifications

            notifs = drain_notifications()
            if not notifs:
                return []

            notif_text = "\n".join(
                f"[bg:{n['task_id']}] {n['status']}: {n['result']}"
                for n in notifs
            )

            return [
                HumanMessage(content=f"<background-results>\n{notif_text}\n</background-results>"),
                AIMessage(content="Noted background results.")
            ]
        except ImportError:
            return []
