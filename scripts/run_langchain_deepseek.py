#!/usr/bin/env python
"""
Entry point for LangChain + DeepSeek agent.

Usage:
    python scripts/run_langchain_deepseek.py           # Interactive mode
    python scripts/run_langchain_deepseek.py "task"    # Subagent mode
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.styles import Style
from prompt_toolkit.mouse_events import MouseEventType
from backend.app.agent import AgentService

STYLE = Style.from_dict({
    "prompt": "ansicyan bold",
})

PROMPT = [("class:prompt", "Mini Agent (LangChain+DeepSeek) >> ")]


def interactive(agent: AgentService):
    session = PromptSession(
        history=InMemoryHistory(),
        mouse_support=True,
        style=STYLE,
    )
    history = []
    print("Ctrl+C / Ctrl+D / 'exit' to quit. ↑↓ for history.\n")

    while True:
        try:
            query = session.prompt(PROMPT)
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            break

        query = query.strip()
        if not query:
            continue
        if query.lower() in ("exit", "quit", "q"):
            print("Bye.")
            break

        print(agent.run(query, history))
        print()


if __name__ == "__main__":
    agent = AgentService()

    if len(sys.argv) > 1:
        print(agent.run(sys.argv[1]))
    else:
        interactive(agent)
