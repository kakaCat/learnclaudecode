"""
REPL class for agent interaction.
Wraps the session-based REPL loop into a reusable class.
"""

from datetime import datetime, timezone
from pathlib import Path

from anthropic import Anthropic


class AgentREPL:
    """Minimal REPL wrapper for agent interaction with session management."""

    def __init__(
        self,
        client: Anthropic,
        session_store,
        model: str,
        system_prompt: str,
        tools: list,
        agent_loop_fn,
    ):
        self.client = client
        self.session_store = session_store
        self.model = model
        self.system_prompt = system_prompt
        self.tools = tools
        self.agent_loop_fn = agent_loop_fn
        self.current_key = self._generate_session_key()

    def _generate_session_key(
        self, agent_id: str = "main", channel: str = "cli", peer: str = "user"
    ) -> str:
        """Generate session key in format: <agent_id>:<channel>:<peer>"""
        return f"{agent_id}:{channel}:{peer}"

    def _format_session_summary(self, meta: dict) -> str:
        """Format session summary for display."""
        key = meta.get("session_key", "?")
        updated = meta.get("updated_at", "?")[:19]
        count = meta.get("message_count", 0)
        return f"  {key}  ({count} msgs, last: {updated})"

    def _print_history(self, session_key: str) -> None:
        """Print session history."""
        session_data = self.session_store.load_session(session_key)
        messages = session_data["history"]
        if not messages:
            print("  (empty session)")
            return
        for msg in messages:
            role = msg.get("role", "?")
            content = msg.get("content", "")
            if isinstance(content, str):
                display = content[:200] + "..." if len(content) > 200 else content
                print(f"  [{role}] {display}")
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict):
                        btype = block.get("type", "?")
                        if btype == "tool_use":
                            print(f"  [{role}:tool_use] {block.get('name', '?')}(...)")
                        elif btype == "tool_result":
                            output = block.get("content", "")
                            display = output[:100] + "..." if len(output) > 100 else output
                            print(f"  [{role}:tool_result] {display}")

    def _handle_command(self, user_input: str) -> bool:
        """Handle REPL commands. Returns True if should continue loop."""
        if user_input == "/quit":
            print("Bye.")
            return False

        if user_input == "/new":
            ts_suffix = datetime.now(timezone.utc).strftime("%H%M%S")
            self.current_key = self._generate_session_key(peer=f"user_{ts_suffix}")
            self.session_store.create_session(self.current_key)
            print(f"  New session: {self.current_key}")
            return True

        if user_input == "/sessions":
            sessions = self.session_store.list_sessions()
            if not sessions:
                print("  (no sessions)")
            else:
                print(f"  {len(sessions)} session(s):")
                for meta in sessions:
                    marker = " *" if meta["session_key"] == self.current_key else ""
                    print(self._format_session_summary(meta) + marker)
            return True

        if user_input.startswith("/switch"):
            parts = user_input.split(maxsplit=1)
            if len(parts) < 2:
                print("  Usage: /switch <session_key>")
                return True
            target_key = parts[1].strip()
            if not self.session_store.session_exists(target_key):
                print(f"  Session not found: {target_key}")
                return True
            self.current_key = target_key
            meta = self.session_store.load_session(self.current_key)["metadata"]
            print(f"  Switched to: {self.current_key} ({meta.get('message_count', 0)} msgs)")
            return True

        if user_input == "/history":
            print(f"  Session: {self.current_key}")
            self._print_history(self.current_key)
            return True

        if user_input.startswith("/delete"):
            parts = user_input.split(maxsplit=1)
            if len(parts) < 2:
                print("  Usage: /delete <session_key>")
                return True
            target_key = parts[1].strip()
            if target_key == self.current_key:
                print("  Cannot delete the current session. Switch first.")
                return True
            if self.session_store.delete_session(target_key):
                print(f"  Deleted: {target_key}")
            else:
                print(f"  Session not found: {target_key}")
            return True

        if user_input.startswith("/"):
            print(f"  Unknown command: {user_input}")
            return True

        return None  # Not a command

    def run(self) -> None:
        """Run the REPL loop."""
        session_data = self.session_store.load_session(self.current_key)
        msg_count = session_data["metadata"].get("message_count", 0)

        print("=" * 60)
        print("  Agent REPL")
        print("  Model:", self.model)
        print("  Session:", self.current_key)
        if msg_count > 0:
            print(f"  Restored: {msg_count} previous turns")
        print()
        print("  Commands: /new /sessions /switch /history /delete /quit")
        print("=" * 60)
        print()

        while True:
            try:
                user_input = input(f"[{self.current_key}] > ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nBye.")
                break

            if not user_input:
                continue

            # Handle commands
            cmd_result = self._handle_command(user_input)
            if cmd_result is False:
                break
            if cmd_result is True:
                continue

            # Call agent loop
            try:
                response = self.agent_loop_fn(
                    user_input, self.current_key, self.session_store, self.client
                )
                print()
                print(response)
                print()
            except Exception as exc:
                print(f"\n  Error: {exc}\n")
