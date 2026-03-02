import json
import logging
import time
import asyncio

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage
from langchain.agents import create_agent
from backend.app.config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL
from backend.app.prompts import get_system_prompt
from backend.app.tools_manager import tools_manager
import backend.app.tools  # noqa: F401 — triggers tool registration
from backend.app.compact import was_compact_requested
from backend.app.background import drain_notifications
from backend.app.team import get_bus
from backend.app.team import state as _team_state
from backend.app.compaction import estimate_tokens, micro_compact, auto_compact
from backend.app.session import new_session_key, set_session_key, save_session
from backend.app import tracer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

G = "\033[90m"
R = "\033[0m"

THRESHOLD = 50000

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


def _build_agent(session_key: str = ""):
    llm = ChatOpenAI(
        model=DEEPSEEK_MODEL,
        api_key=DEEPSEEK_API_KEY,
        base_url=DEEPSEEK_BASE_URL,
    )
    return create_agent(llm, tools_manager.get_tools(), system_prompt=get_system_prompt(session_key)), llm


class AgentService:
    def __init__(self):
        self.session_key = new_session_key()
        set_session_key(self.session_key)

        # 异步加载 MCP 工具
        asyncio.run(tools_manager.load_mcp_tools())

        self.agent, self.llm = _build_agent(self.session_key)
        self.rounds_without_todo = 0
        self.file_writes_since_reflect = 0  # 文件写入后未反思的次数
        self.reflect_retry_count = 0        # 当前反思重试次数
        _log("🤖", f"Agent 就绪 | 模型={DEEPSEEK_MODEL} | session={self.session_key}")

    async def run(self, prompt: str, history: list = None) -> str:
        if history is None:
            history = []

        # Layer 1: micro_compact
        micro_compact(history)
        # Layer 2: auto_compact
        if estimate_tokens(history, self.llm) > THRESHOLD:
            _log("🗜️", "[auto_compact triggered]")
            tracer.emit("compaction", kind="auto", note=f"tokens>{THRESHOLD}")
            new_history = auto_compact(history, self.llm)
            history.clear()
            history.extend(new_history)

        # 注入 lead inbox 消息（仅当 team 已初始化时，避免提前创建 team 目录）
        inbox = get_bus().read_inbox("lead") if _team_state._bus is not None else []
        if inbox and history:
            history.append(HumanMessage(content=f"<inbox>{json.dumps(inbox, indent=2)}</inbox>"))
            history.append(AIMessage(content="Noted inbox messages."))
            _log("📬", f"注入 {len(inbox)} 条 inbox 消息")

        # 注入后台任务完成通知
        notifs = drain_notifications()
        if notifs and history:
            notif_text = "\n".join(
                f"[bg:{n['task_id']}] {n['status']}: {n['result']}" for n in notifs
            )
            history.append(HumanMessage(content=f"<background-results>\n{notif_text}\n</background-results>"))
            history.append(AIMessage(content="Noted background results."))
            _log("📡", f"注入 {len(notifs)} 条后台任务通知")

        _log("👤", f"用户输入: {prompt}")
        run_start = time.time()
        rid = tracer.new_run_id()
        tracer.set_run_id(rid)
        tracer.emit("run.start", prompt=prompt, session=self.session_key)

        messages = history + [HumanMessage(content=prompt)]
        if self.rounds_without_todo >= 3:
            messages.append(HumanMessage(content="<reminder>请更新你的 TodoWrite 待办事项。</reminder>"))
        if self.file_writes_since_reflect >= 1:
            retry_hint = f"（已重试 {self.reflect_retry_count} 次，若仍 NEEDS_REVISION 请升级为 Reflexion）" if self.reflect_retry_count >= 1 else ""
            messages.append(HumanMessage(
                content=f"<reflection-gate>你刚写入了文件，必须先调用 Task(subagent_type='Reflect') 校验后才能继续。{retry_hint}</reflection-gate>"
            ))
        output = ""
        turn = 0
        total_tools = 0
        last_state_messages = messages
        tool_results_summary = []
        # track pending tool calls so we can match results with call_ids
        _pending_calls: dict[str, dict] = {}  # call_id -> {tool, t_start}

        async for step in self.agent.astream({"messages": messages}, stream_mode="updates"):
            for node, state in step.items():
                last = state["messages"][-1]
                if node == "agent":
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
                    content_str = last.content if isinstance(last.content, str) else str(last.content)

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
                    if last.name == "TodoWrite":
                        self.rounds_without_todo = 0
                    else:
                        self.rounds_without_todo += 1
                    # 文件写入计数器
                    if last.name in ("write_file", "edit_file"):
                        self.file_writes_since_reflect += 1
                    # Reflect/Reflexion 调用后重置计数器
                    if last.name == "Task":
                        task_args = _pending_calls.get(call_id, {})
                        subagent = ""
                        # 从 tool call args 里取 subagent_type
                        for tc in (last_state_messages[-1].tool_calls if getattr(last_state_messages[-1], "tool_calls", None) else []):
                            if tc.get("id") == call_id or tc.get("name") == "Task":
                                subagent = tc.get("args", {}).get("subagent_type", "")
                                break
                        if subagent in ("Reflect", "Reflexion"):
                            if "NEEDS_REVISION" in content_str:
                                self.reflect_retry_count += 1
                            else:
                                self.file_writes_since_reflect = 0
                                self.reflect_retry_count = 0
                        # 超过 2 次重试强制升级提示（重置计数避免死循环）
                        if self.reflect_retry_count >= 2:
                            self.reflect_retry_count = 0
                            self.file_writes_since_reflect = 0
                    # drain after each tool batch (mirrors v7: drain before each LLM call)
                    notifs = drain_notifications()
                    if notifs:
                        notif_text = "\n".join(
                            f"[bg:{n['task_id']}] {n['status']}: {n['result']}" for n in notifs
                        )
                        messages = last_state_messages + [
                            HumanMessage(content=f"<background-results>\n{notif_text}\n</background-results>"),
                            AIMessage(content="Noted background results."),
                        ]
                        _log("📡", f"  同轮注入 {len(notifs)} 条后台任务通知")

        # DeepSeek sometimes returns empty content after tool use — call LLM once more
        if not output:
            _log("🧠", "  [补充调用] 获取最终回答")
            tool_context = "\n".join(f"- {r}" for r in tool_results_summary)
            fallback_messages = last_state_messages + [
                HumanMessage(content=f"工具调用结果如下：\n{tool_context}\n\n请根据以上结果，用中文简洁地回答用户的问题，直接引用工具返回的原始数据，不要编造任何ID或数值。")
            ]
            t_fallback = time.time()
            resp = self.llm.invoke(fallback_messages)
            output = resp.content
            tracer.emit("llm.fallback", duration_ms=round((time.time() - t_fallback) * 1000),
                        output_preview=output[:200])

        history.append(HumanMessage(content=prompt))
        history.append(AIMessage(content=output))

        # Layer 3: manual compact triggered by compact tool
        if was_compact_requested():
            _log("🗜️", "[manual compact]")
            tracer.emit("compaction", kind="manual")
            new_history = auto_compact(history, self.llm)
            history.clear()
            history.extend(new_history)

        duration_ms = round((time.time() - run_start) * 1000)
        tracer.emit("run.end", output=output[:300], turns=turn,
                    total_tools=total_tools, duration_ms=duration_ms)
        _log("✅", f"AI 最终回答 → {output[:120]}")
        save_session("main", history)
        return output
