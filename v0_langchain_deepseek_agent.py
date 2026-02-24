#!/usr/bin/env python
"""
v0_langchain_deepseek_agent.py - Mini Agent: LangChain + DeepSeek

Same philosophy as s01_agent_loop.py: ONE tool (bash) + ONE loop = full agent.

Key differences from s01_agent_loop.py (Anthropic SDK):
- Uses LangChain ChatOpenAI (pointing to DeepSeek) instead of Anthropic SDK
- Uses @tool decorator + .bind_tools() instead of raw tool schema
- Uses LangChain message types (HumanMessage, AIMessage, ToolMessage)
- stop_reason != "tool_use"  →  not response.tool_calls


Usage:
    python v0_langchain_deepseek_agent.py
"""

from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, ToolMessage, SystemMessage
from dotenv import load_dotenv
import subprocess
import os

load_dotenv(override=True)

MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

llm = ChatOpenAI(
    model=MODEL,
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
)

SYSTEM = SystemMessage(content=f"You are a coding agent at {os.getcwd()}. Use bash to solve tasks. Act, don't explain.")


def run_bash(command: str) -> str:
    dangerous = ["rm -rf /", "sudo", "shutdown", "reboot", "> /dev/"]
    if any(d in command for d in dangerous):
        return "Error: Dangerous command blocked"
    try:
        r = subprocess.run(command, shell=True, cwd=os.getcwd(),
                           capture_output=True, text=True, timeout=120)
        out = (r.stdout + r.stderr).strip()
        return out[:50000] if out else "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: Timeout (120s)"


@tool
def bash(command: str) -> str:
    """Run a shell command."""
    print(f"\033[33m$ {command}\033[0m")
    output = run_bash(command)
    print(output[:200])
    return output


llm_with_tools = llm.bind_tools([bash])
TOOLS = {"bash": bash}


# -- The core pattern: a while loop that calls tools until the model stops --
def agent_loop(messages: list):
    while True:
        response = llm_with_tools.invoke([SYSTEM] + messages)
        messages.append(response)

        if not response.tool_calls:
            return

        for tc in response.tool_calls:
            result = TOOLS[tc["name"]].invoke(tc["args"])
            messages.append(ToolMessage(content=result, tool_call_id=tc["id"]))


if __name__ == "__main__":
    history = []
    while True:
        try:
            query = input("\033[36ms01-deepseek >> \033[0m")
        except (EOFError, KeyboardInterrupt):
            break
        if query.strip().lower() in ("q", "exit", ""):
            break
        history.append(HumanMessage(content=query))
        agent_loop(history)
        last = history[-1]
        if hasattr(last, "content") and isinstance(last.content, str):
            print(last.content)
        print()
