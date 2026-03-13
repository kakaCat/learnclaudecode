"""
Command handlers for CLI
"""
import json
from typing import Optional

from backend.app.memory.compaction import auto_compact
from backend.app.task import get_task_service
from backend.app.task.converter import TaskConverter
from backend.app.team.state import get_bus, get_team
from backend.app.cli.session import SessionSelector


class CommandHandler:
    """Handle CLI commands"""

    def __init__(self, agent_holder, history: list):
        """
        Initialize command handler

        Args:
            agent_holder: Dict containing agent instance (may be None initially)
            history: Conversation history list
        """
        self.agent_holder = agent_holder
        self.history = history
        self.task_service = get_task_service()

        # Command registry
        self.handlers = {
            '/compact': self._handle_compact,
            '/tasks': self._handle_tasks,
            '/team': self._handle_team,
            '/inbox': self._handle_inbox,
            '/sessions': self._handle_sessions,
            '/insight': self._handle_insight,
            '/insight-llm': self._handle_insight_llm,
        }

    async def handle(self, query: str) -> bool:
        """
        Handle a command

        Args:
            query: Command string

        Returns:
            True if command was handled, False otherwise
        """
        handler = self.handlers.get(query)
        if handler:
            await handler()
            return True
        return False

    async def _handle_compact(self):
        """Handle /compact command"""
        agent = self.agent_holder["agent"]
        if not agent:
            print("⚠️  No active session yet")
            return

        if self.history:
            print("[manual compact]")
            new_history = auto_compact(self.history, agent.llm)
            self.history.clear()
            self.history.extend(new_history)
        else:
            print("No history to compact.")

    async def _handle_tasks(self):
        """Handle /tasks command"""
        tasks = self.task_service.list_all_tasks()
        print(TaskConverter.tasks_to_list_display(tasks, group_by="status"))

    async def _handle_team(self):
        """Handle /team command"""
        print(get_team().list_all())

    async def _handle_inbox(self):
        """Handle /inbox command"""
        msgs = get_bus().read_inbox("lead")
        print(json.dumps(msgs, indent=2, ensure_ascii=False) if msgs else "Inbox empty.")

    async def _handle_sessions(self):
        """Handle /sessions command"""
        selected = SessionSelector.select_session(
            title="Sessions",
            text="Select a session to resume (↑↓ to move, Enter to confirm, Esc to cancel):"
        )

        if selected:
            agent = self.agent_holder["agent"]
            if not agent:
                print("⚠️  No active session yet")
                return

            self.history.clear()
            self.history.extend(SessionSelector.load_session_history(selected))
            agent.switch_session(selected)
            print(f"Resumed session '{selected}' ({len(self.history)} messages)\n")

    async def _handle_insight(self):
        """Handle /insight command"""
        from backend.app.insight import analyze_trace

        selected = SessionSelector.select_session(
            title="选择 Session 进行性能分析",
            text="选择要分析的 session (↑↓ 移动, Enter 确认, Esc 取消):"
        )

        if not selected:
            print("已取消")
            return

        trace_file = SessionSelector.get_trace_file(selected)
        if not trace_file:
            print(f"⚠️  Session '{selected}' 没有 trace 数据")
            return

        print()
        print(f"📊 分析 session: {selected}")
        print()
        analyze_trace(trace_file)
        print()

    async def _handle_insight_llm(self):
        """Handle /insight-llm command"""
        from backend.app.llm_insight import analyze_llm_quality

        agent = self.agent_holder["agent"]
        if not agent:
            print("⚠️  No active session yet")
            return

        selected = SessionSelector.select_session(
            title="选择 Session 进行质量分析",
            text="选择要分析的 session (↑↓ 移动, Enter 确认, Esc 取消):"
        )

        if not selected:
            print("已取消")
            return

        trace_file = SessionSelector.get_trace_file(selected)
        if not trace_file:
            print(f"⚠️  Session '{selected}' 没有 trace 数据")
            return

        print()
        print(f"🧠 分析 session: {selected}")
        print("   使用 LLM 分析调用质量（这会消耗一些 API token）...")
        print()
        analyze_llm_quality(trace_file, agent.llm)
        print()
