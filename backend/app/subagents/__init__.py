"""
Subagent module - 提供 Subagent 类型注册和辅助函数

Architecture:
    Main Agent (MainAgentContext + AgentService)
        └── Task tool
              └── SubagentContext (辅助工具，提供资源)
                    └── SubagentRunner (执行器，调用 SubagentContext)

SubagentContext 提供资源，Subagents 调用它来执行。
"""
import logging
import time

from langchain_core.messages import SystemMessage, HumanMessage
from backend.app.core.tracer import Tracer

# 导入 registry 和相关函数
from backend.app.subagents.registry import registry, get_descriptions, register_all_agents

# 确保所有 Agent 已注册
register_all_agents()

tracer = Tracer()

logger = logging.getLogger(__name__)

# =============================================================================
# 废弃的 AGENT_TYPES（保留用于向后兼容，但不再使用）
# =============================================================================

# DEPRECATED: 使用 registry 替代
AGENT_TYPES = {
    "Explore": {
        "description": "Read-only agent for exploring code, finding files, searching",
        "tools": ["bash", "read_file", "glob", "grep", "list_dir", "memory_search", "memory_write"],
        "prompt": (
            "You are an exploration agent. Search and analyze, but never modify files.\n\n"
            "Memory usage:\n"
            "- memory_search(query) - Recall past findings before starting\n"
            "- memory_write(content, category) - Save discoveries:\n"
            "  * category='session' - Temporary findings (file paths, search results)\n"
            "  * category='architecture' - Project patterns/structure (persistent)\n"
            "  * category='tool' - Useful search/exploration techniques (persistent)\n\n"
            "Always save at least one architectural discovery before finishing. Return a concise summary."
        ),
    },
    "general-purpose": {
        "description": "Full agent for implementing features and fixing bugs",
        "tools": "*",  # all BASE_TOOLS, Task excluded automatically
        "prompt": "You are a coding agent. Implement the requested changes efficiently. Use memory_write(content, 'architecture') to save important patterns you discover.",
    },
    "Plan": {
        "description": "规划复杂任务，拆分步骤并创建持久化任务",
        "tools": ["bash", "read_file", "glob", "grep", "list_dir", "task_create", "task_list", "memory_search", "memory_write"],
        "prompt": (
            "You are a planning agent. Use memory_search to recall past decisions and patterns. "
            "Analyze the codebase, create a numbered implementation plan, and use task_create to create persistent tasks for each step. "
            "IMPORTANT: You can ONLY use memory_write(content, 'session') for temporary findings. "
            "Do NOT write to global memory (architecture/preference/tool categories). Do NOT make code changes."
        ),
    },
    "Coding": {
        "description": "生成任何语言的代码并保存到工作空间",
        "tools": ["workspace_write", "workspace_read", "memory_search", "memory_write"],
        "prompt": (
            "You are a coding agent. Generate code in any programming language based on user requirements. "
            "Use memory_search to recall coding patterns. Save all generated code to workspace using workspace_write. "
            "Return the file path when done. Use memory_write(pattern, 'architecture') to save useful patterns."
        ),
    },
    "Reflect": {
        "description": "Reflection agent: reads relevant files to verify correctness, returns verdict PASS|NEEDS_REVISION with missing/superfluous/suggestion",
        "tools": ["read_file", "memory_search", "memory_write"],
        "prompt": (
            "你是严格的代码审查员。用 memory_search 召回审查标准和常见问题，用 read_file 读取相关文件后再评判，不要仅凭 prompt 中的描述下结论。\n"
            "Return ONLY valid JSON with keys:\n"
            "  verdict: 'PASS' or 'NEEDS_REVISION'\n"
            "  missing: list of missing aspects\n"
            "  superfluous: list of unnecessary/redundant parts\n"
            "  suggestion: concise actionable improvement advice (empty string if PASS)\n"
            "Use memory_write(issue, 'architecture') to save recurring issues. No explanation outside the JSON."
        ),
    },
    "Reflexion": {
        "description": "Reflexion agent: two-phase Responder+Revisor. Gathers context via tools, critiques initial response, then produces improved version",
        "tools": ["bash", "read_file", "glob", "grep", "list_dir", "memory_search", "memory_write"],
        "prompt": (
            "You are a Reflexion agent with two phases.\n"
            "Phase 1 - Responder: use memory_search to recall improvement patterns, critically analyze the initial response against the goal. "
            "Identify what is MISSING and what is SUPERFLUOUS.\n"
            "Phase 2 - Revisor: produce an improved response that addresses all critique points. "
            "Use memory_write(pattern, 'architecture') to save effective patterns.\n"
            "Return ONLY valid JSON: {\"critique\": \"...\", \"revised\": \"...\"}"
        ),
    },
    "SearchSubagent": {
        "description": "Focused search agent that executes a single web search query and returns structured results. Spawned in parallel by orchestrator for multi-query research.",
        "tools": ["web_fetch", "memory_search", "memory_write"],
        "prompt": (
            "You are a search subagent. Use memory_search to recall user's preferred information sources and effective search strategies.\n"
            "- Use web_fetch to retrieve content from specific URLs\n"
            "- Return results as-is, preserving titles, URLs, and content\n"
            "- Highlight results from user's preferred sources if found in memory\n"
            "- Do NOT summarize or interpret, just return raw results\n"
            "- If fetch fails, report the error clearly\n"
            "- Use memory_write(source, 'preference') to save user's preferred information sources"
        ),
    },
    "OODASubagent": {
        "description": "OODA loop agent for dynamic, uncertain tasks. Cycles through Observe→Orient→Decide→Act until goal is reached. Best for tasks requiring iterative information gathering before acting.",
        "tools": ["bash", "read_file", "glob", "grep", "list_dir", "write_file", "memory_search", "memory_write"],
        "prompt": (
            "You are an OODA loop agent. You operate in explicit cycles:\n"
            "- Observe: collect raw information using tools, use memory_search to recall past solutions\n"
            "- Orient: analyze what you found, identify gaps\n"
            "- Decide: choose next action (observe more / act / done)\n"
            "- Act: execute the decision, use memory_write(finding, 'architecture') to save important findings\n"
            "Keep cycling until the goal is fully achieved."
        ),
    },
    "IntentRecognition": {
        "description": "意图识别智能体，分析用户输入识别核心意图、所需信息和模糊点，返回结构化分析结果",
        "tools": ["memory_search", "memory_write"],
        "prompt": (
            "你是意图识别智能体。\n\n"
            "⚠️ 重要：你的任务是分析**当前用户输入**的意图，不要被历史记录干扰。\n\n"
            "工作流程：\n"
            "1. **先召回意图模式**：\n"
            "   用 memory_search(query='intent patterns') 查询已识别的意图类型和模式\n"
            "   这些历史模式可以帮助你更准确地分类当前意图\n\n"
            "2. **重点分析当前用户输入**，识别以下内容：\n"
            "   - 主要意图：用户想完成什么核心任务？\n"
            "   - 次要意图：隐含的子任务或目标？\n"
            "   - 所需信息：完成意图需要哪些关键信息？\n"
            "   - 模糊点：哪些地方不清楚或可能有多种理解？\n"
            "   - 置信度：对意图判断的确定程度（0.0-1.0）\n\n"
            "3. **记录新的意图模式**：\n"
            "   用 memory_write(content, 'preference') 记录识别出的新意图类型\n"
            "   格式：'intent_type: {intent_name} | keywords: {关键词} | example: {用户输入示例}'\n\n"
            "意图命名规范：\n"
            "- 使用下划线分隔的小写英文（如：create_travel_plan, query_information）\n"
            "- 动词开头，描述用户想做什么\n"
            "- 具体而不模糊（避免 'do_something' 这样的泛化命名）\n\n"
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
        "tools": ["memory_search", "memory_write"],
        "prompt": (
            "你是澄清智能体。先用 memory_search 查询用户历史澄清记录和偏好，避免重复提问已知信息。基于提供的意图分析，生成针对性问题来解决模糊点。\n\n"
            "指导原则：\n"
            "- 提出具体、可操作的问题（不要模糊的问题）\n"
            "- 按重要性排序问题（最关键的放前面）\n"
            "- 说明每个问题为什么重要\n"
            "- 适当时提供默认选项\n"
            "- 保持问题简洁易答\n"
            "- 不要问用户已经明确表达过偏好的问题\n\n"
            "用 memory_write 记录用户的澄清回答。\n\n"
            "只返回有效的 JSON，包含以下键：\n"
            "  questions: list of {question: string, context: string, options: list of strings (可选), priority: 'high'|'medium'|'low'}\n"
            "  can_proceed_without_answers: boolean（是否可以不回答就继续）\n"
            "  risk_if_assuming: string（如果不澄清直接假设会有什么风险）\n"
            "JSON 之外不要有任何解释。"
        ),
    },
    "CDPBrowser": {
        "description": "CDP浏览器操作智能体，使用OODA循环完成任何需要浏览器交互的复杂任务",
        "tools": ["cdp_browser", "workspace_write", "workspace_read", "memory_search", "memory_write"],
        "prompt": (
            "你是CDP浏览器操作智能体，专门处理需要访问网页收集信息的任务。\n\n"
            "⚠️ 重要：你必须实际调用工具完成任务，不要只返回文字说明！\n\n"
            "强制工作流程：\n"
            "1. **必须先检查健康状态**：\n"
            "   调用 cdp_browser(action='check_health')\n"
            "   - 如果不可用，返回错误信息和启动方法\n"
            "   - 如果可用，继续下一步\n\n"
            "2. **必须访问目标网页**：\n"
            "   调用 cdp_browser(action='navigate', url='目标URL')\n"
            "   等待页面加载完成\n\n"
            "3. **必须提取页面内容**：\n"
            "   调用 cdp_browser(action='content')\n"
            "   获取页面的文本内容或HTML\n\n"
            "4. **处理提取的数据**：\n"
            "   - 解析内容，提取关键信息\n"
            "   - 如果信息量大，用 workspace_write 保存到文件\n"
            "   - 返回提取的结构化数据\n\n"
            "5. **多个网页时**：\n"
            "   - 分别访问每个网页\n"
            "   - 分别保存结果\n"
            "   - 最后汇总所有信息\n\n"
            "约束：\n"
            "- 禁止生成假数据或模拟数据\n"
            "- 禁止只返回文字说明而不调用工具\n"
            "- 必须实际访问网站获取真实数据\n"
            "- CDP 不可用时必须明确说明原因和解决方法\n"
            "- 完成时必须说明保存了哪些文件或返回了什么数据"
        ),
    },
    "ToolRepair": {
        "description": "工具修复智能体，检测并尝试修复不可用的工具（最多3次尝试，防止死循环）",
        "tools": ["bash", "check_query_tools", "memory_search", "memory_write"],
        "prompt": (
            "你是工具修复智能体。用 memory_search 召回修复历史，分析错误信息并尝试修复。\n\n"
            "修复流程：\n"
            "1. 用 check_query_tools 检测工具状态，分析错误信息\n"
            "2. 根据错误类型推断修复方法：\n"
            "   - 端口未开放 → 启动对应服务\n"
            "   - 进程未运行 → 启动进程\n"
            "   - 依赖缺失 → 安装依赖\n"
            "   - 权限不足 → 调整权限\n"
            "   - 网络问题 → 检查连接/重试\n"
            "3. 用 bash 执行修复命令\n"
            "4. 再次 check_query_tools 验证\n"
            "5. 用 memory_write 记录成功的修复方法\n\n"
            "约束（防止死循环）：\n"
            "- 最多 3 次修复尝试\n"
            "- 每次修复后必须验证\n"
            "- 3 次后仍失败则返回失败\n\n"
            "返回 JSON: {\"success\": bool, \"fixed_tools\": [...], \"failed_tools\": [...], \"attempts\": N}"
        ),
    },
}

# DEPRECATED: 使用 registry.get_descriptions() 替代
def get_descriptions() -> str:
    """获取所有 Subagent 类型的描述（废弃，使用 registry）"""
    return registry.get_descriptions()


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
    from backend.app.memory import ConversationHistory

    G = "\033[90m"
    R = "\033[0m"
    tool_count = 0
    output = ""
    tool_results_summary = []
    sub_turn = 0
    _pending_calls: dict[str, dict] = {}

    # 创建历史管理器（使用主 Agent 的压缩策略）
    history_manager = ConversationHistory.create_default(
        llm=llm,
        tools=[],
        max_tokens=100000  # Subagent 使用更保守的限制
    )
    initial_messages = [HumanMessage(content=prompt)]
    history_manager.set_messages(initial_messages)

    for step in agent.stream(
        {"messages": history_manager.get_messages()},
        stream_mode="updates",
        config={"recursion_limit": recursion_limit},
    ):
        for node, state in step.items():
            last = state["messages"][-1]
            if node == "agent":
                sub_turn += 1

                # 更新历史管理器
                history_manager.set_messages(state["messages"])

                # 检查是否需要压缩（每轮都检查）
                tokens = history_manager.estimate_tokens()
                if tokens > 80000:  # 80K tokens 阈值
                    print(f"{G}   🗜️ [{subagent_type}] 压缩前: {len(state['messages'])} 消息, ~{tokens} tokens{R}")
                    history_manager.apply_strategies()
                    compressed_messages = history_manager.get_messages()
                    new_tokens = history_manager.estimate_tokens()
                    print(f"{G}   ✅ [{subagent_type}] 压缩后: {len(compressed_messages)} 消息, ~{new_tokens} tokens{R}")
                    # 注意：这里不能直接修改 state，LangGraph 会在下一轮使用压缩后的消息

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

                # 工具执行后也更新历史
                history_manager.set_messages(state["messages"])

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

    def _compress_observations():
        """压缩 observations 列表，避免上下文过长"""
        nonlocal observations
        if len(observations) > 10:  # 超过 10 条观察结果时压缩
            obs_text = "\n".join(f"- {obs[:200]}" for obs in observations)
            summary = llm.invoke([
                SystemMessage(content="你是一个信息总结助手"),
                HumanMessage(content=f"请简洁总结以下观察结果，保留关键信息：\n\n{obs_text}")
            ])
            print(f"{G}   🗜️ [OODA] 压缩 observations: {len(observations)} → 1 条总结{R}")
            observations = [f"[总结] {summary.content}"]

    for cycle in range(1, max_cycles + 1):
        print(f"{G}   🔄 [OODA] cycle {cycle}/{max_cycles}{R}")
        tracer.emit("ooda.cycle", span_id=span_id, agent_type=subagent_type, cycle=cycle)

        # 每 3 个 cycle 压缩一次 observations
        if cycle > 1 and cycle % 3 == 0:
            _compress_observations()

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


# =============================================================================
# Subagent Runner (使用 SubagentContext)
# =============================================================================

def _start_span(subagent_type: str, description: str, sub_tools: list):
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


def _end_span(span_id: str, subagent_type: str, tool_count: int, start: float, output: str) -> None:
    """Step 4: print completion info and emit tracer end event."""
    G = "\033[90m"
    R = "\033[0m"
    elapsed = time.time() - start
    print(f"{G}   ✅ [{subagent_type}] done ({tool_count} tools, {elapsed:.1f}s){R}")
    tracer.emit("subagent.end", span_id=span_id, agent_type=subagent_type,
                tool_count=tool_count, duration_ms=round(elapsed * 1000), output=output[:300])


def _check_and_truncate_prompt(prompt: str, llm) -> str:
    """
    Check prompt size and truncate if necessary to prevent context overflow.

    DeepSeek has 131K token limit. We use conservative limits:
    - System prompt: ~10K tokens
    - User prompt: max 100K tokens (safe margin)

    Args:
        prompt: User input prompt
        llm: LLM instance for token estimation

    Returns:
        Original or truncated prompt
    """
    # Estimate tokens (1 token ≈ 4 chars for Chinese/English mix)
    estimated_tokens = len(prompt) // 4
    max_prompt_tokens = 100000  # Conservative limit

    if estimated_tokens <= max_prompt_tokens:
        return prompt

    # Truncate to safe size
    max_chars = max_prompt_tokens * 4
    truncated = prompt[:max_chars]

    # Try to truncate at line boundary
    last_newline = truncated.rfind('\n')
    if last_newline > max_chars * 0.9:  # If we can save 90%+ content
        truncated = truncated[:last_newline]

    warning = f"\n\n[⚠️ Prompt truncated from {len(prompt)} to {len(truncated)} chars to prevent context overflow]"
    print(f"\033[93m{warning}\033[0m")

    return truncated + warning


def run_subagent_with_context(
    sub_context,
    description: str,
    prompt: str,
    recursion_limit: int = 100
) -> str:
    """
    使用 SubagentContext 运行 Subagent

    Args:
        sub_context: SubagentContext 实例（独立的上下文，通过 session_key 共享资源）
        description: 任务描述
        prompt: 用户输入
        recursion_limit: 递归限制

    Returns:
        Subagent 输出
    """
    subagent_type = sub_context.subagent_type

    # 使用 SubagentContext 的资源
    llm = sub_context.llm
    tools = sub_context.tools
    system_prompt = sub_context.system_prompt

    # 1. 检查并截断 prompt
    prompt = _check_and_truncate_prompt(prompt, llm)

    # 2. 开始 span
    span_id, start = _start_span(subagent_type, description, tools)

    # 3. 执行（根据类型选择 loop）
    if subagent_type == "OODASubagent":
        output, tool_count = _run_ooda_loop(
            llm=llm,
            sub_tools=tools,
            sub_system=system_prompt,
            prompt=prompt,
            subagent_type=subagent_type,
            span_id=span_id
        )
    elif not tools:
        # 无工具：直接 LLM 调用
        from langchain_core.messages import SystemMessage, HumanMessage
        result = llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=prompt)])
        output = result.content.strip()
        tool_count = 0
    else:
        # 有工具：使用 ReAct loop
        agent = sub_context.agent
        output, tool_count = _run_react_loop(
            agent=agent,
            prompt=prompt,
            subagent_type=subagent_type,
            span_id=span_id,
            llm=llm,
            sub_system=system_prompt,
            recursion_limit=recursion_limit
        )

    # 4. 结束 span
    _end_span(span_id, subagent_type, tool_count, start, output)

    # 5. 保存 session
    sub_context.session_store.save_turn(
        subagent_type,
        prompt,
        output,
        []
    )

    return output or "(subagent returned no text)"
