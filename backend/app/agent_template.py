"""
Agent 模板方法模式重构

核心思想：
1. run() 只定义流程骨架，不包含具体实现
2. 每个步骤抽取为独立方法，职责单一
3. 复杂逻辑封装到专门的类中
"""
import json
import logging
import time
import asyncio
from typing import List, Dict, Any, Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langchain.agents import create_agent

from backend.app.config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL
from backend.app.prompts import get_system_prompt
from backend.app.tools_manager import tools_manager
import backend.app.tools  # noqa: F401
from backend.app.compact import was_compact_requested
from backend.app.background import drain_notifications
from backend.app.team import get_bus
from backend.app.team import state as _team_state
from backend.app.context.compaction import estimate_tokens, micro_compact, auto_compact
from backend.app.session import new_session_key, set_session_key, get_store
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


# ============================================================================
# Context 管理器 - 负责 history 的压缩和消息注入
# ============================================================================

class ContextManager:
    """管理对话上下文：压缩、消息注入"""

    def __init__(self, llm):
        self.llm = llm

    def prepare_context(self, history: List[BaseMessage]) -> List[BaseMessage]:
        """准备上下文：压缩 + 注入消息"""
        self._micro_compact(history)
        self._auto_compact_if_needed(history)
        self._inject_inbox_messages(history)
        self._inject_background_notifications(history)
        return history

    def _micro_compact(self, history: List[BaseMessage]):
        """Layer 1: 微压缩"""
        before = len(history)
        micro_compact(history)
        if len(history) < before:
            get_store().save_compaction("main", "micro", before, len(history))

    def _auto_compact_if_needed(self, history: List[BaseMessage]):
        """Layer 2: 自动压缩（超过阈值）"""
        if estimate_tokens(history, self.llm) > THRESHOLD:
            _log("🗜️", "[auto_compact triggered]")
            tracer.emit("compaction", kind="auto", note=f"tokens>{THRESHOLD}")
            before = len(history)
            new_history = auto_compact(history, self.llm)
            history.clear()
            history.extend(new_history)
            get_store().save_compaction("main", "auto", before, len(history))

    def _inject_inbox_messages(self, history: List[BaseMessage]):
        """注入 team inbox 消息"""
        if not history:
            return
        inbox = get_bus().read_inbox("lead") if _team_state._bus is not None else []
        if inbox:
            history.append(HumanMessage(content=f"<inbox>{json.dumps(inbox, indent=2)}</inbox>"))
            history.append(AIMessage(content="Noted inbox messages."))
            _log("📬", f"注入 {len(inbox)} 条 inbox 消息")

    def _inject_background_notifications(self, history: List[BaseMessage]):
        """注入后台任务通知"""
        if not history:
            return
        notifs = drain_notifications()
        if notifs:
            notif_text = "\n".join(f"[bg:{n['task_id']}] {n['status']}: {n['result']}" for n in notifs)
            history.append(HumanMessage(content=f"<background-results>\n{notif_text}\n</background-results>"))
            history.append(AIMessage(content="Noted background results."))
            _log("📡", f"注入 {len(notifs)} 条后台任务通知")

    def manual_compact_if_requested(self, history: List[BaseMessage]):
        """Layer 3: 手动压缩（工具触发）"""
        if was_compact_requested():
            _log("🗜️", "[manual compact]")
            tracer.emit("compaction", kind="manual")
            before = len(history)
            new_history = auto_compact(history, self.llm)
            history.clear()
            history.extend(new_history)
            get_store().save_compaction("main", "manual", before, len(history))


# ============================================================================
# Agent 执行器 - 负责 LLM 调用和工具执行的流程
# ============================================================================

class AgentExecutor:
    """执行 Agent 流程：LLM 调用 + 工具执行"""

    def __init__(self, agent, llm):
        self.agent = agent
        self.llm = llm
        self.rounds_without_todo = 0
        self.file_writes_since_reflect = 0
        self.reflect_retry_count = 0

    async def execute(self, messages: List[BaseMessage]) -> tuple[str, List[BaseMessage], List[str]]:
        """
        执行 Agent 流程

        Returns:
            (output, last_state_messages, tool_results_summary)
        """
        output = ""
        turn = 0
        total_tools = 0
        last_state_messages = messages
        tool_results_summary = []
        _pending_calls: Dict[str, Dict] = {}

        async for step in self.agent.astream({"messages": messages}, stream_mode="updates"):
            for node, state in step.items():
                _log("🔍", f"DEBUG: node={node}, has_messages={len(state.get('messages', []))}")
                tracer.emit("debug.node", node=node, msg_count=len(state.get('messages', [])))

                last = state["messages"][-1]

                if node in ("agent", "call_model", "llm", "__start__", "model"):
                    turn += 1
                    last_state_messages = state["messages"]
                    self._handle_llm_call(turn, state, last, _pending_calls)

                elif node == "tools":
                    total_tools += 1
                    self._handle_tool_result(turn, last, last_state_messages, tool_results_summary, _pending_calls)

                    # 同轮注入后台通知
                    notifs = drain_notifications()
                    if notifs:
                        notif_text = "\n".join(f"[bg:{n['task_id']}] {n['status']}: {n['result']}" for n in notifs)
                        messages = last_state_messages + [
                            HumanMessage(content=f"<background-results>\n{notif_text}\n</background-results>"),
                            AIMessage(content="Noted background results."),
                        ]
                        _log("📡", f"  同轮注入 {len(notifs)} 条后台任务通知")

        # DeepSeek 补充调用
        if not output:
            output = await self._fallback_call(last_state_messages, tool_results_summary)

        return output, last_state_messages, tool_results_summary

    def _handle_llm_call(self, turn: int, state: Dict, last: BaseMessage, pending_calls: Dict):
        """处理 LLM 调用"""
        _log("🧠", f"[第 {turn} 次调用 LLM] 上下文消息数={len(state['messages'])}")

        # 记录 prompt
        prompt_messages = []
        for msg in state["messages"]:
            msg_dict = {"role": msg.__class__.__name__}
            if hasattr(msg, "content"):
                msg_dict["content"] = msg.content[:500] if isinstance(msg.content, str) else str(msg.content)[:500]
            if hasattr(msg, "name"):
                msg_dict["name"] = msg.name
            prompt_messages.append(msg_dict)
        tracer.emit("llm.prompt", turn=turn, messages=prompt_messages)

        # 记录 response
        response_data = {"content": last.content[:500] if last.content else ""}
        if getattr(last, "tool_calls", None):
            response_data["tool_calls"] = [
                {"name": tc["name"], "args": tc["args"], "id": tc.get("id", "")}
                for tc in last.tool_calls
            ]
        tracer.emit("llm.response", turn=turn, **response_data)

        # 处理工具调用
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
                pending_calls[call_id] = {"tool": tc["name"], "t_start": time.time()}
                tracer.emit("tool.call", turn=turn, tool=tc["name"], args=tc["args"], call_id=call_id)
            tracer.emit("llm.turn", turn=turn, msg_count=len(state["messages"]), decisions=decisions)
        else:
            _log("🧠", f"  AI 决策: 直接回答，无需工具")
            tracer.emit("llm.turn", turn=turn, msg_count=len(state["messages"]),
                        direct_answer=True, output_preview=last.content[:200] if last.content else "")

    def _handle_tool_result(self, turn: int, last: BaseMessage, last_state_messages: List[BaseMessage],
                            tool_results_summary: List[str], pending_calls: Dict):
        """处理工具执行结果"""
        content_str = last.content if isinstance(last.content, str) else str(last.content)
        icon = TOOL_ICONS.get(last.name, "🔧")
        _log("📥", f"  {icon}[{last.name}] 返回: {content_str[:80]}")
        tool_results_summary.append(content_str[:500])

        # 匹配 call_id
        call_id = getattr(last, "tool_call_id", last.name)
        pending = pending_calls.pop(call_id, pending_calls.pop(last.name, None))
        duration_ms = round((time.time() - pending["t_start"]) * 1000) if pending else None

        tracer.emit("tool.result", turn=turn, tool=last.name, call_id=call_id,
                    duration_ms=duration_ms, ok=not content_str.startswith("Error:"),
                    output=content_str[:500])

        # 保存工具结果
        get_store().save_tool_result("main", last.name, call_id, content_str)

        # 更新计数器
        if last.name == "TodoWrite":
            self.rounds_without_todo = 0
        else:
            self.rounds_without_todo += 1

        if last.name in ("write_file", "edit_file"):
            self.file_writes_since_reflect += 1

        # Reflect/Reflexion 处理
        if last.name == "Task":
            subagent = ""
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
            if self.reflect_retry_count >= 2:
                self.reflect_retry_count = 0
                self.file_writes_since_reflect = 0

    async def _fallback_call(self, last_state_messages: List[BaseMessage], tool_results_summary: List[str]) -> str:
        """DeepSeek 补充调用获取最终回答"""
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
        return output

    def build_messages_with_reminders(self, history: List[BaseMessage], prompt: str) -> List[BaseMessage]:
        """构建带提醒的消息列表"""
        messages = history + [HumanMessage(content=prompt)]

        if self.rounds_without_todo >= 3:
            messages.append(HumanMessage(content="<reminder>请更新你的 TodoWrite 待办事项。</reminder>"))

        if self.file_writes_since_reflect >= 1:
            retry_hint = f"（已重试 {self.reflect_retry_count} 次，若仍 NEEDS_REVISION 请升级为 Reflexion）" if self.reflect_retry_count >= 1 else ""
            messages.append(HumanMessage(
                content=f"<reflection-gate>你刚写入了文件，必须先调用 Task(subagent_type='Reflect') 校验后才能继续。{retry_hint}</reflection-gate>"
            ))

        return messages


# ============================================================================
# AgentService - 模板方法模式：定义流程骨架
# ============================================================================

class AgentService:
    """
    Agent 服务 - 使用模板方法模式

    run() 方法定义了执行流程的骨架，具体步骤委托给专门的管理器
    """

    def __init__(self):
        self.session_key = None
        self.agent = None
        self.llm = None
        self.context_manager = None
        self.executor = None

        # 异步加载 MCP 工具
        asyncio.run(tools_manager.load_mcp_tools())
        _log("🤖", f"Agent 就绪 | 模型={DEEPSEEK_MODEL}")

    def _ensure_initialized(self):
        """延迟初始化：第一次对话时创建 session 和相关组件"""
        if self.session_key is None:
            self.session_key = new_session_key()
            set_session_key(self.session_key)
            self.agent, self.llm = _build_agent(self.session_key)
            self.context_manager = ContextManager(self.llm)
            self.executor = AgentExecutor(self.agent, self.llm)
            _log("🆕", f"创建新 session: {self.session_key}")

    async def run(self, prompt: str, history: Optional[List[BaseMessage]] = None) -> str:
        """
        模板方法：定义执行流程骨架

        流程：
        1. 初始化 session
        2. 准备上下文（压缩 + 注入）
        3. 构建消息（添加提醒）
        4. 执行 Agent（LLM + 工具）
        5. 保存结果
        6. 后处理（手动压缩）
        """
        if history is None:
            history = []

        # Step 1: 初始化
        self._ensure_initialized()

        # Step 2: 准备上下文
        self.context_manager.prepare_context(history)

        # Step 3: 构建消息
        _log("👤", f"用户输入: {prompt}")
        run_start = time.time()
        rid = tracer.new_run_id()
        tracer.set_run_id(rid)
        tracer.emit("run.start", prompt=prompt, session=self.session_key)

        messages = self.executor.build_messages_with_reminders(history, prompt)

        # Step 4: 执行 Agent
        output, last_state_messages, tool_results_summary = await self.executor.execute(messages)

        # Step 5: 保存结果
        self._save_turn(prompt, output, last_state_messages, history)

        # Step 6: 后处理
        self.context_manager.manual_compact_if_requested(history)

        # 记录结束
        duration_ms = round((time.time() - run_start) * 1000)
        tracer.emit("run.end", output=output[:300], duration_ms=duration_ms)
        _log("✅", f"AI 最终回答 → {output[:120]}")

        return output

    def _save_turn(self, prompt: str, output: str, last_state_messages: List[BaseMessage],
                   history: List[BaseMessage]):
        """保存对话轮次"""
        history.append(HumanMessage(content=prompt))
        history.append(AIMessage(content=output))

        # 提取 tool_calls
        tool_calls_data = []
        for msg in last_state_messages:
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                tool_calls_data = [{"name": tc["name"], "args": tc["args"]} for tc in msg.tool_calls]
                break

        get_store().save_turn("main", prompt, output, tool_calls_data)
