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
    "SearchSubagent": {
        "description": "Focused search agent that executes a single web search query and returns structured results. Spawned in parallel by orchestrator for multi-query research.",
        "tools": ["web_search", "web_fetch"],
        "prompt": (
            "You are a search subagent. Your only job is to execute the given search query using web_search "
            "and return the results clearly.\n"
            "- Run web_search with the provided query\n"
            "- Return results as-is, preserving titles, URLs, and snippets\n"
            "- Do NOT summarize or interpret, just return raw search results\n"
            "- If search fails, report the error clearly"
        ),
    },
    "OODASubagent": {
        "description": "OODA loop agent for dynamic, uncertain tasks. Cycles through Observe→Orient→Decide→Act until goal is reached. Best for tasks requiring iterative information gathering before acting.",
        "tools": ["bash", "read_file", "glob", "grep", "list_dir", "write_file"],
        "prompt": (
            "You are an OODA loop agent. You operate in explicit cycles:\n"
            "- Observe: collect raw information using tools\n"
            "- Orient: analyze what you found, identify gaps\n"
            "- Decide: choose next action (observe more / act / done)\n"
            "- Act: execute the decision\n"
            "Keep cycling until the goal is fully achieved."
        ),
    },
    "IntentRecognition": {
        "description": "意图识别智能体，分析用户输入识别核心意图、所需信息和模糊点，返回结构化分析结果",
        "tools": [],  # 纯推理，无需工具
        "prompt": (
            "你是意图识别智能体。分析用户输入，识别以下内容：\n"
            "1. 主要意图（用户想完成什么？）\n"
            "2. 次要意图（隐含的目标或子任务？）\n"
            "3. 所需信息（完成意图需要哪些信息？）\n"
            "4. 模糊点（哪些地方不清楚或可能有多种理解？）\n"
            "5. 置信度（对意图判断的确定程度？）\n\n"
            "只返回有效的 JSON，包含以下键：\n"
            "  primary_intent: string（主要意图）\n"
            "  secondary_intents: list of strings（次要意图列表）\n"
            "  required_info: list of strings（所需信息列表）\n"
            "  ambiguities: list of strings（模糊点列表）\n"
            "  confidence: float (0.0-1.0)（置信度）\n"
            "  needs_clarification: boolean（是否需要澄清）\n"
            "JSON 之外不要有任何解释。"
        ),
    },
    "Clarification": {
        "description": "澄清智能体，基于意图分析生成针对性问题，解决用户请求中的模糊点",
        "tools": [],  # 纯推理，无需工具
        "prompt": (
            "你是澄清智能体。基于提供的意图分析，生成针对性问题来解决模糊点。\n\n"
            "指导原则：\n"
            "- 提出具体、可操作的问题（不要模糊的问题）\n"
            "- 按重要性排序问题（最关键的放前面）\n"
            "- 说明每个问题为什么重要\n"
            "- 适当时提供默认选项\n"
            "- 保持问题简洁易答\n\n"
            "只返回有效的 JSON，包含以下键：\n"
            "  questions: list of {question: string, context: string, options: list of strings (可选), priority: 'high'|'medium'|'low'}\n"
            "  can_proceed_without_answers: boolean（是否可以不回答就继续）\n"
            "  risk_if_assuming: string（如果不澄清直接假设会有什么风险）\n"
            "JSON 之外不要有任何解释。"
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
# ReAct Loop
# =============================================================================

def _run_react_loop(
    agent,
    prompt: str,
    subagent_type: str,
    span_id: str,
    llm,
    sub_system: str,
    recursion_limit: int = 100,
) -> tuple[str, int]:
    """
    Execute the ReAct loop: Reason → Act → Observe → repeat until no tool calls.

    Returns:
        (output, tool_count)
    """
    G = "\033[90m"
    R = "\033[0m"
    tool_count = 0
    output = ""
    tool_results_summary = []
    sub_turn = 0
    _pending_calls: dict[str, dict] = {}

    for step in agent.stream(
        {"messages": [HumanMessage(content=prompt)]},
        stream_mode="updates",
        config={"recursion_limit": recursion_limit},
    ):
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

    return output, tool_count


# =============================================================================
# OODA Loop
# =============================================================================

def _run_ooda_loop(
    llm,
    sub_tools: list,
    sub_system: str,
    prompt: str,
    subagent_type: str,
    span_id: str,
    max_cycles: int = 6,
) -> tuple[str, int]:
    """
    Execute the OODA loop: Observe → Orient → Decide → Act → repeat.

    Each phase is an explicit LLM call with a focused role.
    Returns (output, tool_count).
    """
    import json

    G = "\033[90m"
    R = "\033[0m"
    tool_count = 0
    tool_map = {t.name: t for t in sub_tools}

    def _invoke_tools(tool_calls: list) -> list[str]:
        """Execute a list of {name, args} tool calls, return result strings."""
        nonlocal tool_count
        results = []
        for tc in tool_calls:
            t = tool_map.get(tc.get("name"))
            if not t:
                results.append(f"Error: unknown tool {tc.get('name')}")
                continue
            try:
                result = t.invoke(tc.get("args", {}))
                tool_count += 1
                results.append(str(result)[:800])
                print(f"{G}   🔀 [OODA/{subagent_type}] {tc['name']} → {str(result)[:80]}{R}")
            except Exception as e:
                results.append(f"Error: {e}")
        return results

    observations: list[str] = []
    history: list[str] = []

    for cycle in range(1, max_cycles + 1):
        print(f"{G}   🔄 [OODA] cycle {cycle}/{max_cycles}{R}")
        tracer.emit("ooda.cycle", span_id=span_id, agent_type=subagent_type, cycle=cycle)

        # ── Observe ──────────────────────────────────────────────────────────
        obs_resp = llm.invoke([
            SystemMessage(content=sub_system),
            HumanMessage(content=(
                f"Goal: {prompt}\n"
                f"Previous observations: {observations}\n\n"
                f"Available tools: {list(tool_map.keys())}\n\n"
                "OBSERVE phase: decide which tools to call to gather information.\n"
                'Output ONLY valid JSON: {"tools": [{"name": "...", "args": {...}}]}\n'
                'If no tools needed, output: {"tools": []}'
            )),
        ])
        try:
            obs_json = json.loads(obs_resp.content.strip().strip("```json").strip("```"))
            raw = _invoke_tools(obs_json.get("tools", []))
            observations.extend(raw)
        except (json.JSONDecodeError, AttributeError):
            observations.append(obs_resp.content.strip())

        # ── Orient ───────────────────────────────────────────────────────────
        orient_resp = llm.invoke([
            SystemMessage(content=sub_system),
            HumanMessage(content=(
                f"Goal: {prompt}\n"
                f"Observations so far: {observations}\n\n"
                "ORIENT phase: analyze the observations.\n"
                'Output ONLY valid JSON: {"situation": "...", "gaps": [...], "confidence": 0.0-1.0}'
            )),
        ])
        try:
            situation = json.loads(orient_resp.content.strip().strip("```json").strip("```"))
        except (json.JSONDecodeError, AttributeError):
            situation = {"situation": orient_resp.content.strip(), "gaps": [], "confidence": 0.5}
        print(f"{G}   🧭 [OODA] confidence={situation.get('confidence', '?')}{R}")

        # ── Decide ───────────────────────────────────────────────────────────
        decide_resp = llm.invoke([
            SystemMessage(content=sub_system),
            HumanMessage(content=(
                f"Goal: {prompt}\n"
                f"Situation: {situation}\n\n"
                "DECIDE phase: choose next step.\n"
                'Output ONLY valid JSON: {"choice": "OBSERVE_MORE"|"ACT"|"DONE", "reason": "..."}'
            )),
        ])
        try:
            decision = json.loads(decide_resp.content.strip().strip("```json").strip("```"))
        except (json.JSONDecodeError, AttributeError):
            decision = {"choice": "DONE", "reason": decide_resp.content.strip()}
        print(f"{G}   🎯 [OODA] decision={decision.get('choice')}{R}")

        if decision.get("choice") == "DONE":
            break

        # ── Act ──────────────────────────────────────────────────────────────
        if decision.get("choice") == "ACT":
            act_resp = llm.invoke([
                SystemMessage(content=sub_system),
                HumanMessage(content=(
                    f"Goal: {prompt}\n"
                    f"Situation: {situation}\n\n"
                    f"Available tools: {list(tool_map.keys())}\n\n"
                    "ACT phase: execute the action using tools.\n"
                    'Output ONLY valid JSON: {"tools": [{"name": "...", "args": {...}}]}'
                )),
            ])
            try:
                act_json = json.loads(act_resp.content.strip().strip("```json").strip("```"))
                act_results = _invoke_tools(act_json.get("tools", []))
                history.extend(act_results)
            except (json.JSONDecodeError, AttributeError):
                history.append(act_resp.content.strip())

    # Final summary
    summary_resp = llm.invoke([
        SystemMessage(content=sub_system),
        HumanMessage(content=(
            f"Goal: {prompt}\n"
            f"Observations: {observations}\n"
            f"Actions taken: {history}\n\n"
            "Summarize what was accomplished concisely."
        )),
    ])
    output = summary_resp.content.strip()
    return output, tool_count

def _prepare_subagent(subagent_type: str, base_tools: list):
    """Step 1: validate, filter tools, build system prompt, create LLM."""
    from backend.app.tools.base import WORKDIR
    config = AGENT_TYPES[subagent_type]
    sub_tools = _filter_tools(subagent_type, base_tools)
    sub_system = (
        f"You are a {subagent_type} subagent at {WORKDIR}.\n\n"
        f"{config['prompt']}\n\n"
        "Complete the task and return a clear, concise summary."
    )
    llm = ChatOpenAI(model=DEEPSEEK_MODEL, api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
    return sub_tools, sub_system, llm


def _start_span(subagent_type: str, description: str, sub_tools: list) -> tuple[str, float]:
    """Step 2: print startup info and emit tracer start event."""
    G = "\033[90m"
    R = "\033[0m"
    tool_names = [t.name for t in sub_tools] if sub_tools else []
    label = tool_names if tool_names else "(none, direct llm)"
    print(f"{G}🤖 [subagent:{subagent_type}] {description}{R}")
    print(f"{G}   tools: {label}{R}")
    span_id = tracer.new_run_id()
    tracer.emit("subagent.start", span_id=span_id, agent_type=subagent_type,
                description=description, tools=tool_names)
    return span_id, time.time()


def _invoke_direct(llm, sub_system: str, prompt: str) -> tuple[str, int]:
    """Step 3a: no-tool path — single LLM call, no agent loop."""
    result = llm.invoke([SystemMessage(content=sub_system), HumanMessage(content=prompt)])
    return result.content.strip(), 0


def _invoke_with_tools(
    llm, sub_tools: list, sub_system: str, prompt: str,
    subagent_type: str, span_id: str, recursion_limit: int,
) -> tuple[str, int]:
    """Step 3b: tool-enabled path — OODA or ReAct loop depending on agent type."""
    if subagent_type == "OODASubagent":
        return _run_ooda_loop(
            llm=llm, sub_tools=sub_tools, sub_system=sub_system, prompt=prompt,
            subagent_type=subagent_type, span_id=span_id,
        )
    agent = create_agent(llm, sub_tools, system_prompt=sub_system)
    return _run_react_loop(
        agent=agent, prompt=prompt, subagent_type=subagent_type,
        span_id=span_id, llm=llm, sub_system=sub_system,
        recursion_limit=recursion_limit,
    )


def _end_span(span_id: str, subagent_type: str, tool_count: int, start: float, output: str) -> None:
    """Step 4: print completion info and emit tracer end event."""
    G = "\033[90m"
    R = "\033[0m"
    elapsed = time.time() - start
    print(f"{G}   ✅ [{subagent_type}] done ({tool_count} tools, {elapsed:.1f}s){R}")
    tracer.emit("subagent.end", span_id=span_id, agent_type=subagent_type,
                tool_count=tool_count, duration_ms=round(elapsed * 1000), output=output[:300])


def _save_subagent_session(subagent_type: str, prompt: str, output: str) -> None:
    """Step 5: persist conversation to session store."""
    save_session(subagent_type, [HumanMessage(content=prompt), AIMessage(content=output)])


# =============================================================================
# Subagent Runner
# =============================================================================

def run_subagent(description: str, prompt: str, subagent_type: str, base_tools: list, recursion_limit: int = 100) -> str:
    """Spawn a subagent with isolated context. Task tool is always excluded."""
    if subagent_type not in AGENT_TYPES:
        return f"Error: Unknown agent type '{subagent_type}'"

    # 1. prepare
    sub_tools, sub_system, llm = _prepare_subagent(subagent_type, base_tools)

    # 2. start span
    span_id, start = _start_span(subagent_type, description, sub_tools)

    # 3. execute
    if not sub_tools:
        output, tool_count = _invoke_direct(llm, sub_system, prompt)
    else:
        output, tool_count = _invoke_with_tools(llm, sub_tools, sub_system, prompt, subagent_type, span_id, recursion_limit)

    # 4. end span
    _end_span(span_id, subagent_type, tool_count, start, output)

    # 5. save session
    _save_subagent_session(subagent_type, prompt, output)

    return output or "(subagent returned no text)"
