"""
Subagent module - independent from tools.

Architecture:
    Main Agent (create_agent + ALL_TOOLS including Task)
        └── Task tool calls run_subagent()
              └── Subagent (create_agent + filtered tools, NO Task)

Registry defines agent types and their allowed tools.
Subagents use LangChain create_agent, same as main agent.
"""
import logging
import time

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, AIMessage
from langchain_openai import ChatOpenAI

from backend.app.config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL
from backend.app.session import get_session_key, save_session

logger = logging.getLogger(__name__)

# =============================================================================
# Agent Registry
# =============================================================================

AGENT_TYPES = {
    "Explore": {
        "description": "Read-only agent for exploring code, finding files, searching",
        "tools": ["bash", "read_file", "glob", "grep", "list_dir"],
        "prompt": "You are an exploration agent. Search and analyze, but never modify files. Return a concise summary.",
    },
    "general-purpose": {
        "description": "Full agent for implementing features and fixing bugs",
        "tools": "*",  # all BASE_TOOLS, Task excluded automatically
        "prompt": "You are a coding agent. Implement the requested changes efficiently.",
    },
    "Plan": {
        "description": "Planning agent for designing implementation strategies",
        "tools": ["bash", "read_file", "glob", "grep", "list_dir"],
        "prompt": "You are a planning agent. Analyze the codebase and output a numbered implementation plan. Do NOT make changes.",
    },
}


def get_descriptions() -> str:
    return "\n".join(f"- {name}: {cfg['description']}" for name, cfg in AGENT_TYPES.items())


def _filter_tools(agent_type: str, base_tools: list) -> list:
    """Return tools for this agent type. Task is never included (no recursion)."""
    allowed = AGENT_TYPES[agent_type]["tools"]
    if allowed == "*":
        return [t for t in base_tools if t.name != "Task"]
    return [t for t in base_tools if t.name in allowed]


# =============================================================================
# Subagent Runner
# =============================================================================

def run_subagent(description: str, prompt: str, subagent_type: str, base_tools: list) -> str:
    """
    Spawn a subagent using create_agent with isolated context.

    Uses the same LangChain create_agent as the main agent, but:
    - Fresh message history (no parent context)
    - Filtered tools based on agent type
    - Task tool excluded (prevents infinite recursion)
    """
    if subagent_type not in AGENT_TYPES:
        return f"Error: Unknown agent type '{subagent_type}'"

    config = AGENT_TYPES[subagent_type]
    sub_tools = _filter_tools(subagent_type, base_tools)

    from backend.app.tools.base import WORKDIR
    sub_system = f"You are a {subagent_type} subagent at {WORKDIR}.\n\n{config['prompt']}\n\nComplete the task and return a clear, concise summary."

    llm = ChatOpenAI(model=DEEPSEEK_MODEL, api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
    agent = create_agent(llm, sub_tools, system_prompt=sub_system)

    G = "\033[90m"
    R = "\033[0m"
    print(f"{G}🤖 [subagent:{subagent_type}] {description}{R}")
    print(f"{G}   tools: {[t.name for t in sub_tools]}{R}")
    start = time.time()
    tool_count = 0
    output = ""

    for step in agent.stream({"messages": [HumanMessage(content=prompt)]}, stream_mode="updates"):
        for node, state in step.items():
            last = state["messages"][-1]
            if node == "agent":
                if getattr(last, "tool_calls", None):
                    for tc in last.tool_calls:
                        print(f"{G}   🔀 [{subagent_type}] → {tc['name']}({tc['args']}){R}")
                else:
                    output = last.content
            elif node == "tools":
                tool_count += 1
                print(f"{G}   📥 [{subagent_type}] ← {last.content[:120]}{R}")

    elapsed = time.time() - start
    print(f"{G}   ✅ [{subagent_type}] done ({tool_count} tools, {elapsed:.1f}s){R}")

    save_session(subagent_type, [
        HumanMessage(content=prompt),
        AIMessage(content=output),
    ])
    return output or "(subagent returned no text)"
