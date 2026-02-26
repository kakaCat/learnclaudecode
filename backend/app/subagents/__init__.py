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
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI

from backend.app.config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL
from backend.app.session import get_session_key, save_session
from backend.app import tracer

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
    "ScriptWriter": {
        "description": "Script writing agent that creates Python scripts and saves them to the scripts/ folder",
        "tools": ["read_file", "write_file", "glob", "grep", "list_dir"],
        "prompt": "You are a script writing agent. Write Python scripts and save them to the scripts/ directory using write_file. Always use paths like 'scripts/<name>.py'. Return the file path when done.",
    },
    "Reflect": {
        "description": "Reflection agent: reads relevant files to verify correctness, returns verdict PASS|NEEDS_REVISION with missing/superfluous/suggestion",
        "tools": ["read_file"],
        "prompt": (
            "你是严格的代码审查员。用 read_file 读取相关文件后再评判，不要仅凭 prompt 中的描述下结论。\n"
            "Return ONLY valid JSON with keys:\n"
            "  verdict: 'PASS' or 'NEEDS_REVISION'\n"
            "  missing: list of missing aspects\n"
            "  superfluous: list of unnecessary/redundant parts\n"
            "  suggestion: concise actionable improvement advice (empty string if PASS)\n"
            "No explanation outside the JSON."
        ),
    },
    "Reflexion": {
        "description": "Reflexion agent: two-phase Responder+Revisor. Gathers context via tools, critiques initial response, then produces improved version",
        "tools": ["bash", "read_file", "glob", "grep", "list_dir"],
        "prompt": (
            "You are a Reflexion agent with two phases.\n"
            "Phase 1 - Responder: critically analyze the initial response against the goal. "
            "Identify what is MISSING and what is SUPERFLUOUS.\n"
            "Phase 2 - Revisor: produce an improved response that addresses all critique points.\n"
            "Return ONLY valid JSON: {\"critique\": \"...\", \"revised\": \"...\"}"
        ),
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

def run_subagent(description: str, prompt: str, subagent_type: str, base_tools: list, recursion_limit: int = 100) -> str:
    """
    Spawn a subagent using create_agent with isolated context.

    Uses the same LangChain create_agent as the main agent, but:
    - Fresh message history (no parent context)
    - Filtered tools based on agent type
    - Task tool excluded (prevents infinite recursion)
    - No-tool agents (Reflect, Reflexion) use direct llm.invoke instead of create_agent
    """
    if subagent_type not in AGENT_TYPES:
        return f"Error: Unknown agent type '{subagent_type}'"

    config = AGENT_TYPES[subagent_type]
    sub_tools = _filter_tools(subagent_type, base_tools)

    from backend.app.tools.base import WORKDIR
    sub_system = f"You are a {subagent_type} subagent at {WORKDIR}.\n\n{config['prompt']}\n\nComplete the task and return a clear, concise summary."

    llm = ChatOpenAI(model=DEEPSEEK_MODEL, api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)

    # No-tool agents: skip create_agent, use direct llm.invoke
    if not sub_tools:
        G = "\033[90m"
        R = "\033[0m"
        print(f"{G}🤖 [subagent:{subagent_type}] {description}{R}")
        print(f"{G}   tools: (none, direct llm){R}")
        start = time.time()
        span_id = tracer.new_run_id()
        tracer.emit("subagent.start", span_id=span_id, agent_type=subagent_type,
                    description=description, tools=[])
        result = llm.invoke([SystemMessage(content=sub_system), HumanMessage(content=prompt)])
        output = result.content.strip()
        elapsed = time.time() - start
        print(f"{G}   ✅ [{subagent_type}] done (0 tools, {elapsed:.1f}s){R}")
        tracer.emit("subagent.end", span_id=span_id, agent_type=subagent_type,
                    tool_count=0, duration_ms=round(elapsed * 1000), output=output[:300])
        save_session(subagent_type, [HumanMessage(content=prompt), AIMessage(content=output)])
        return output or "(subagent returned no text)"

    agent = create_agent(llm, sub_tools, system_prompt=sub_system)

    G = "\033[90m"
    R = "\033[0m"
    print(f"{G}🤖 [subagent:{subagent_type}] {description}{R}")
    print(f"{G}   tools: {[t.name for t in sub_tools]}{R}")
    start = time.time()
    tool_count = 0
    output = ""
    tool_results_summary = []
    span_id = tracer.new_run_id()
    tracer.emit("subagent.start", span_id=span_id, agent_type=subagent_type,
                description=description, tools=[t.name for t in sub_tools])
    sub_turn = 0
    _pending_calls: dict[str, dict] = {}

    for step in agent.stream({"messages": [HumanMessage(content=prompt)]}, stream_mode="updates", config={"recursion_limit": recursion_limit}):
        for node, state in step.items():
            last = state["messages"][-1]
            if node == "agent":
                sub_turn += 1
                if getattr(last, "tool_calls", None):
                    decisions = []
                    for tc in last.tool_calls:
                        print(f"{G}   🔀 [{subagent_type}] → {tc['name']}({tc['args']}){R}")
                        decisions.append({"tool": tc["name"], "args": str(tc["args"])[:120]})
                        call_id = tc.get("id") or tc["name"]
                        _pending_calls[call_id] = {"tool": tc["name"], "t_start": time.time()}
                        tracer.emit("subagent.tool.call", span_id=span_id, agent_type=subagent_type,
                                    turn=sub_turn, tool=tc["name"], args=tc["args"], call_id=call_id)
                    tracer.emit("subagent.llm.turn", span_id=span_id, agent_type=subagent_type,
                                turn=sub_turn, decisions=decisions)
                else:
                    output = last.content
                    tracer.emit("subagent.llm.turn", span_id=span_id, agent_type=subagent_type,
                                turn=sub_turn, direct_answer=True, output_preview=output[:200])
            elif node == "tools":
                tool_count += 1
                tool_results_summary.append(last.content[:500])
                print(f"{G}   📥 [{subagent_type}] ← {last.content[:120]}{R}")
                call_id = getattr(last, "tool_call_id", last.name)
                pending = _pending_calls.pop(call_id, _pending_calls.pop(last.name, None))
                duration_ms = round((time.time() - pending["t_start"]) * 1000) if pending else None
                tracer.emit("subagent.tool.result", span_id=span_id, agent_type=subagent_type,
                            turn=sub_turn, tool=last.name, call_id=call_id,
                            duration_ms=duration_ms,
                            ok=not last.content.startswith("Error:"),
                            output=last.content[:500])

    # DeepSeek sometimes returns empty content after tool use — call LLM once more
    if not output and tool_count > 0:
        tool_context = "\n".join(f"- {r}" for r in tool_results_summary)
        fallback = llm.invoke([
            SystemMessage(content=sub_system),
            HumanMessage(content=f"工具调用结果如下：\n{tool_context}\n\n请简洁地总结你完成的工作，直接引用工具返回的原始数据。")
        ])
        output = fallback.content.strip()
        print(f"{G}   🔁 [{subagent_type}] fallback: {output[:80]}{R}")

    elapsed = time.time() - start
    print(f"{G}   ✅ [{subagent_type}] done ({tool_count} tools, {elapsed:.1f}s){R}")
    tracer.emit("subagent.end", span_id=span_id, agent_type=subagent_type,
                tool_count=tool_count, duration_ms=round(elapsed * 1000),
                output=output[:300])

    save_session(subagent_type, [
        HumanMessage(content=prompt),
        AIMessage(content=output),
    ])
    return output or "(subagent returned no text)"
