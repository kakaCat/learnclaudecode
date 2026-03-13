"""
Session management for CLI
"""
from typing import Optional
from prompt_toolkit.shortcuts import radiolist_dialog

from backend.app.session import list_sessions, load_session, SESSIONS_DIR


class SessionSelector:
    """Handle session selection and loading"""

    @staticmethod
    def select_session(title: str, text: str) -> Optional[str]:
        """
        Show session selection dialog

        Args:
            title: Dialog title
            text: Dialog description text

        Returns:
            Selected session key or None if cancelled
        """
        keys = list_sessions()
        if not keys:
            print("No saved sessions.")
            return None

        selected = radiolist_dialog(
            title=title,
            text=text,
            values=[(k, k) for k in keys],
        ).run()

        return selected

    @staticmethod
    def load_session_history(session_key: str, role: str = "main") -> list:
        """
        Load session history

        Args:
            session_key: Session identifier
            role: Role name (default: "main")

        Returns:
            List of history messages
        """
        return load_session(role, session_key)

    @staticmethod
    def get_trace_file(session_key: str):
        """
        Get trace file path for a session

        Args:
            session_key: Session identifier

        Returns:
            Path object or None if not exists
        """
        trace_file = SESSIONS_DIR / session_key / "trace.jsonl"
        return trace_file if trace_file.exists() else None
