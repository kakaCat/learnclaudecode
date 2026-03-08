import json
import logging
import time

from langchain_core.messages import HumanMessage, AIMessage
from backend.app.context import AgentContext
from backend.app.config import DEEPSEEK_MODEL
from backend.app.notifications import NotificationService
from backend.app.guards import TodoReminderGuard, ReflectionGatekeeper

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

G = "\033[90m"
R = "\033[0m"

TOOL_ICONS = {
    "bash": "💻", "read_file": "📖", "write_file": "✍️", "edit_file": "✏️",
    "glob": "🔍", "grep": "🔎", "list_dir": "📂",
    "Task": "🤖", "load_skill": "📚", "compact": "🗜️",
    "task_create": "📌", "task_get": "🔖", "task_update": "🔄", "task_list": "📝",
    "task_bind_worktree": "🔗",
    "background_run": "⚡", "background_agent": "🤖⚡", "check_background": "📡",
    "worktree_create": "🌿", "worktree_list": "🌳", "worktree_status": "📊",
    "worktree_run": "▶️", "worktree_remove": "🗑️", "worktree_keep": "📎",
    "worktree_events": "📜",
}


def _log(icon: str, msg: str):
    print(f"{G}{icon} {msg}{R}")


def _fmt_args(name: str, args: dict) -> str:
    if name == "Task":
        return f"subagent={args.get('subagent_type')} | {args.get('description', '')[:60]}"
    if name == "TodoWrite":
        todos = args.get("todos", [])
        summary = ", ".join(f"{t.get('status','?')}:{t.get('content','')[:20]}" for t in todos[:4])
        return f"{len(todos)} todos [{summary}{'...' if len(todos)>4 else ''}]"
    if name == "spawn_teammate":
        return f"name={args.get('name')} role={args.get('role')}"
    if name in ("worktree_create", "worktree_run", "worktree_remove", "worktree_keep", "worktree_status"):
        return f"name={args.get('name')} task_id={args.get('task_id','-')}"
    if name == "background_run":
        return str(args.get("command", ""))[:80]
    if name == "background_agent":
        return f"subagent={args.get('subagent_type')} | {args.get('description', '')[:60]}"
    if name in ("task_create", "task_update"):
        return f"subject={args.get('subject','')} status={args.get('status','')}"
    return str(args)[:80]




class AgentService:
    def __init__(self):
        # 核心依赖
        self.context = AgentContext.create_default("")
        self.notification_service = NotificationService()
        # 功能守卫
        self.todo_reminder = TodoReminderGuard()
        self.reflection_gate = ReflectionGatekeeper()
        # UI 状态
        self._first_run = True

    def switch_session(self, session_key: str):
        """切换到指定 session，重置所有状态"""
        self.context.set_session_key(session_key)
        self.todo_reminder.reset()
        self.reflection_gate.reset()
        self._first_run = True

    async def run(self, prompt: str, history: list = None) -> str:
        if history is None:
            history = []

        # 第一次对话时创建 session（如果还没有）
        if not self.context.get_session_key():
            session_key = self.context.new_session_key()
            self.context.set_session_key(session_key)  # 自动同步到全局
            _log("🆕", f"创建新 session: {session_key}")

        # 第一次 run 时打印 Agent 就绪信息
        if self._first_run:
            _log("🤖", f"Agent 就绪 | session={self.context.get_session_key()} | 模型={DEEPSEEK_MODEL}")
            self._first_run = False

        # Apply compaction strategies via conversation history
        conversation_history = self.context.get_conversation_history()
        conversation_history.set_messages(history)
        conversation_history.apply_strategies()
        history = conversation_history.get_messages()

        # 注入所有待处理通知（inbox、后台任务等）
        pending_msgs = self.notification_service.get_pending_messages()
        if pending_msgs and history:
            history.extend(pending_msgs)
            _log("📬", f"注入 {len(pending_msgs)//2} 条通知消息")

        _log("👤", f"用户输入: {prompt}")
        run_start = time.time()
        tracer = self.context.get_tracer()
        rid = tracer.new_run_id()
        tracer.set_run_id(rid)
        tracer.emit("run.start", prompt=prompt, session=self.context.get_session_key())

        messages = history + [HumanMessage(content=prompt)]
        if self.todo_reminder.should_remind():
            messages.append(HumanMessage(content=self.todo_reminder.get_reminder_message()))
        if self.reflection_gate.should_gate():
            messages.append(HumanMessage(content=self.reflection_gate.get_gate_message()))
        output = ""
        turn = 0
        total_tools = 0
        last_state_messages = messages
        tool_results_summary = []
        # track pending tool calls so we can match results with call_ids
        _pending_calls: dict[str, dict] = {}  # call_id -> {tool, t_start}

        async for step in self.context.get_agent().astream({"messages": messages}, stream_mode="updates"):
            for node, state in step.items():
                # DEBUG: 记录所有节点名称，帮助诊断为什么 llm.prompt 没有被记录
                _log("🔍", f"DEBUG: node={node}, has_messages={len(state.get('messages', []))}")

                # 记录所有节点到 trace，帮助调试
                tracer.emit("debug.node", node=node, msg_count=len(state.get('messages', [])))

                last = state["messages"][-1]

                # 尝试匹配多种可能的 LLM 节点名称
                if node in ("agent", "call_model", "llm", "__start__", "model"):
                    turn += 1
                    last_state_messages = state["messages"]
                    _log("🧠", f"[第 {turn} 次调用 LLM] 上下文消息数={len(state['messages'])}")

                    # 记录发送给 LLM 的完整 prompt
                    prompt_messages = []
                    for msg in state["messages"]:
                        msg_dict = {"role": msg.__class__.__name__}
                        if hasattr(msg, "content"):
                            msg_dict["content"] = msg.content[:500] if isinstance(msg.content, str) else str(msg.content)[:500]
                        if hasattr(msg, "name"):
                            msg_dict["name"] = msg.name
                        prompt_messages.append(msg_dict)
                    tracer.emit("llm.prompt", turn=turn, messages=prompt_messages)

                    # 记录 LLM 的完整响应
                    response_data = {"content": last.content[:500] if last.content else ""}
                    if getattr(last, "tool_calls", None):
                        response_data["tool_calls"] = [
                            {"name": tc["name"], "args": tc["args"], "id": tc.get("id", "")}
                            for tc in last.tool_calls
                        ]
                    tracer.emit("llm.response", turn=turn, **response_data)

                    if getattr(last, "tool_calls", None):
                        tcs = last.tool_calls
                        mode = "并行" if len(tcs) > 1 else "串行"
                        _log("🔀", f"  AI 决策: {mode}调用 {len(tcs)} 个工具")
                        decisions = []
                        for tc in tcs:
                            icon = TOOL_ICONS.get(tc["name"], "🔧")
                            _log("🔀", f"    {icon}[{tc['name']}] {_fmt_args(tc['name'], tc['args'])}")
                            decisions.append({"tool": tc["name"], "args": _fmt_args(tc["name"], tc["args"])})
                            call_id = tc.get("id") or tc["name"]
                            _pending_calls[call_id] = {"tool": tc["name"], "t_start": time.time()}
                            tracer.emit("tool.call", turn=turn, tool=tc["name"],
                                        args=tc["args"], call_id=call_id)
                        tracer.emit("llm.turn", turn=turn, msg_count=len(state["messages"]),
                                    decisions=decisions)
                    else:
                        output = last.content or output
                        _log("🧠", f"  AI 决策: 直接回答，无需工具")
                        tracer.emit("llm.turn", turn=turn, msg_count=len(state["messages"]),
                                    direct_answer=True, output_preview=output[:200])
                elif node == "tools":
                    # 处理 content 可能是列表的情况
                    if isinstance(last.content, str):
                        content_str = last.content
                    else:
                        # 使用 json.dumps 保持中文可读性
                        content_str = json.dumps(last.content, ensure_ascii=False)

                    icon = TOOL_ICONS.get(last.name, "🔧")
                    _log("📥", f"  {icon}[{last.name}] 返回: {content_str[:80]}")
                    tool_results_summary.append(content_str[:500])
                    total_tools += 1
                    # match call_id
                    call_id = getattr(last, "tool_call_id", last.name)
                    pending = _pending_calls.pop(call_id, _pending_calls.pop(last.name, None))
                    duration_ms = round((time.time() - pending["t_start"]) * 1000) if pending else None

                    tracer.emit("tool.result", turn=turn, tool=last.name, call_id=call_id,
                                duration_ms=duration_ms,
                                ok=not content_str.startswith("Error:"),
                                output=content_str[:500])

                    # Save tool result to transcript
                    self.context.get_store().save_tool_result("main", last.name, call_id, content_str)

                    # 更新守卫状态
                    self.todo_reminder.on_tool_call(last.name)

                    # 提取 subagent_type（用于 Reflection 门禁）
                    subagent = ""
                    if last.name == "Task":
                        for tc in (last_state_messages[-1].tool_calls if getattr(last_state_messages[-1], "tool_calls", None) else []):
                            if tc.get("id") == call_id or tc.get("name") == "Task":
                                subagent = tc.get("args", {}).get("subagent_type", "")
                                break
                    self.reflection_gate.on_tool_call(last.name, subagent, content_str)

                    # drain after each tool batch (mirrors v7: drain before each LLM call)
                    pending_msgs = self.notification_service.get_pending_messages()
                    if pending_msgs:
                        messages = last_state_messages + pending_msgs
                        _log("📡", f"  同轮注入 {len(pending_msgs)//2} 条通知消息")

        # DeepSeek sometimes returns empty content after tool use — call LLM once more
        if not output:
            _log("🧠", "  [补充调用] 获取最终回答")
            tool_context = "\n".join(f"- {r}" for r in tool_results_summary)
            fallback_messages = last_state_messages + [
                HumanMessage(content=f"工具调用结果如下：\n{tool_context}\n\n请根据以上结果，用中文简洁地回答用户的问题，直接引用工具返回的原始数据，不要编造任何ID或数值。")
            ]
            t_fallback = time.time()
            resp = self.context.get_overflow_guard().guard_invoke(messages=fallback_messages)
            output = resp.content
            tracer.emit("llm.fallback", duration_ms=round((time.time() - t_fallback) * 1000),
                        output_preview=output[:200])

        history.append(HumanMessage(content=prompt))
        history.append(AIMessage(content=output))

        # Save turn to transcript
        tool_calls_data = []
        for msg in last_state_messages:
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                tool_calls_data = [{"name": tc["name"], "args": tc["args"]} for tc in msg.tool_calls]
                break
        self.context.get_store().save_turn("main", prompt, output, tool_calls_data)

        # Manual compact is now handled by ManualCompactionStrategy in guard
        # No need for separate manual compact logic here

        duration_ms = round((time.time() - run_start) * 1000)
        tracer.emit("run.end", output=output[:300], turns=turn,
                    total_tools=total_tools, duration_ms=duration_ms)
        _log("✅", f"AI 最终回答 → {output[:120]}")
        return output
