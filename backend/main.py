#!/usr/bin/env python3
"""
backend/main.py - REPL entry point for AgentService

Usage:
    python -m backend.main                    # New session
    python -m backend.main --resume           # Resume latest session
    python -m backend.main --resume <key>     # Resume specific session
    python -m backend.main "task"             # Subagent mode (single run)

Commands:
  /compact  - manually compress conversation history
  /tasks    - list all persistent tasks
  /team     - list all teammates and their status
  /inbox    - read and drain lead's inbox
  /sessions - list all saved sessions
"""
import json
import sys

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.styles import Style

COMMANDS = ["/compact", "/tasks", "/team", "/inbox", "/sessions"]

from backend.app.agent import AgentService, _build_agent
from backend.app.compaction import auto_compact
from backend.app.task.task_manager import TaskManager
from backend.app.team.state import get_bus, get_team
from backend.app.session import list_sessions, load_session, set_session_key

STYLE = Style.from_dict({"prompt": "ansicyan bold"})
PROMPT = [("class:prompt", "agent >> ")]


def interactive(agent: AgentService, history: list):
    session = PromptSession(
        history=InMemoryHistory(),
        mouse_support=True,
        style=STYLE,
        completer=WordCompleter(COMMANDS, sentence=True),
    )
    task_mgr = TaskManager()
    print("Ctrl+C / Ctrl+D / 'exit' to quit. ↑↓ for history.\n")

    while True:
        try:
            query = session.prompt(PROMPT).strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            break

        if not query or query in ("q", "exit", "quit"):
            break

        if query == "/compact":
            if history:
                print("[manual compact]")
                new_history = auto_compact(history, agent.llm)
                history.clear()
                history.extend(new_history)
            else:
                print("No history to compact.")
            continue

        if query == "/tasks":
            print(task_mgr.list_all())
            continue

        if query == "/team":
            print(get_team().list_all())
            continue

        if query == "/inbox":
            msgs = get_bus().read_inbox("lead")
            print(json.dumps(msgs, indent=2, ensure_ascii=False) if msgs else "Inbox empty.")
            continue

        if query == "/sessions":
            keys = list_sessions()
            if not keys:
                print("No saved sessions.")
                continue
            from prompt_toolkit.shortcuts import radiolist_dialog
            selected = radiolist_dialog(
                title="Sessions",
                text="Select a session to resume (↑↓ to move, Enter to confirm, Esc to cancel):",
                values=[(k, k) for k in keys],
            ).run()
            if selected:
                set_session_key(selected)
                history.clear()
                history.extend(load_session("main", selected))
                agent.session_key = selected
                agent.agent, _ = _build_agent(selected)
                print(f"Resumed session '{selected}' ({len(history)} messages)\n")
            continue

        print(agent.run(query, history))
        print()


if __name__ == "__main__":
    args = sys.argv[1:]
    resume_key = None

    if args and args[0] == "--resume":
        keys = list_sessions()
        if not keys:
            print("No saved sessions found.")
            sys.exit(1)
        resume_key = args[1] if len(args) > 1 else keys[0]
        if resume_key not in keys:
            print(f"Session '{resume_key}' not found. Available:\n" + "\n".join(keys))
            sys.exit(1)
        args = args[2:] if len(args) > 1 else []

    agent = AgentService()
    history = []

    if resume_key:
        set_session_key(resume_key)
        history = load_session("main", resume_key)
        agent.session_key = resume_key
        agent.agent, _ = _build_agent(resume_key)
        print(f"Resumed session '{resume_key}' ({len(history)} messages)\n")

    if args:
        # Subagent mode: single run
        print(agent.run(args[0], history))
    else:
        interactive(agent, history)
