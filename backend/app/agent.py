import json
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Union

from langchain_core.messages import HumanMessage, AIMessage
from backend.app.context.main_context import MainContext
from backend.app.context.subagent_context import SubagentContext
from backend.app.config import DEEPSEEK_MODEL
from backend.app.notifications import NotificationService
from backend.app.guards.todo_reminder import TodoReminderGuard
from backend.app.guards.reflection_gate import ReflectionGatekeeper
from backend.app.reliability import get_global_lifecycle, start_lifecycle, get_lifecycle_status

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


@dataclass
class AgentRun:
    """封装单次 Agent 运行的状态"""

    prompt: str
    history: List = field(default_factory=list)

    # 运行时状态
    output: str = ""
    turn: int = 0
    total_tools: int = 0
    start_time: float = field(default_factory=time.time)

    # 消息和调用追踪
    messages: List = field(default_factory=list)
    last_state_messages: List = field(default_factory=list)
    tool_results_summary: List[str] = field(default_factory=list)
    pending_calls: Dict[str, dict] = field(default_factory=dict)  # call_id -> {tool, t_start}

    @property
    def duration_ms(self) -> int:
        """运行时长（毫秒）"""
        return round((time.time() - self.start_time) * 1000)

    def add_tool_result(self, result: str):
        """添加工具结果摘要"""
        self.tool_results_summary.append(result[:500])

    def register_tool_call(self, call_id: str, tool_name: str):
        """注册工具调用"""
        self.pending_calls[call_id] = {"tool": tool_name, "t_start": time.time()}

    def pop_tool_call(self, call_id: str, fallback_name: str = None) -> Optional[dict]:
        """获取并移除工具调用记录"""
        pending = self.pending_calls.pop(call_id, None)
        if not pending and fallback_name:
            pending = self.pending_calls.pop(fallback_name, None)
        return pending




class AgentService:
    """
    Agent 服务 - 负责运行 Agent 并处理对话流程

    支持两种 Context：
    - MainContext: 主 Agent（默认）
    - SubagentContext: 子 Agent
    """

    def __init__(self, context: Union[MainContext, SubagentContext] = None, enable_lifecycle: bool = True):
        """
        初始化 Agent 服务

        Args:
            context: Agent 上下文（MainContext 或 SubagentContext）
                    如果为 None，则创建默认的 MainContext
            enable_lifecycle: 是否启用生命周期管理
        """
        # 核心依赖
        if context is None:
            # 默认创建 MainContext（向后兼容）
            self.context = MainContext("")
        else:
            self.context = context

        self.notification_service = NotificationService()

        # 功能守卫
        self.todo_reminder = TodoReminderGuard()
        self.reflection_gate = ReflectionGatekeeper()

        # 智能化组件
        from backend.app.reliability import get_retry_strategy, get_monitor
        self.retry_strategy = get_retry_strategy()
        self.monitor = get_monitor()

        # 生命周期管理
        self.enable_lifecycle = enable_lifecycle
        self.lifecycle_manager = None
        if enable_lifecycle:
            self.lifecycle_manager = get_global_lifecycle()

        # UI 状态
        self._first_run = True

        # 配置参数
        self.monitor_check_interval = 3  # 监控检查间隔

        # 判断是 Main 还是 Subagent
        self.is_subagent = isinstance(context, SubagentContext)
        self.agent_name = context.subagent_type if self.is_subagent else "main"

    def switch_session(self, session_key: str):
        """切换到指定 session，重置所有状态"""
        if isinstance(self.context, MainContext):
            self.context.set_session_key(session_key)
        else:
            # Subagent 通过 main_context 切换
            self.context.main_context.set_session_key(session_key)

        self.todo_reminder.reset()
        self.reflection_gate.reset()
        self._first_run = True

    def _build_messages(self, history: list, prompt: str) -> list:
        """
        统一的消息构建逻辑

        Args:
            history: 历史消息列表
            prompt: 用户输入

        Returns:
            构建好的消息列表
        """
        messages = history + [HumanMessage(content=prompt)]

        if self.todo_reminder.should_remind():
            messages.append(HumanMessage(content=self.todo_reminder.get_reminder_message()))

        if self.reflection_gate.should_gate():
            messages.append(HumanMessage(content=self.reflection_gate.get_gate_message()))

        return messages

    def _prepare_context(self, history: list, prompt: str) -> list:
        """
        准备上下文：应用压缩策略、召回记忆、注入通知

        Args:
            history: 历史消息列表
            prompt: 用户输入

        Returns:
            准备好的历史消息列表
        """
        # 应用对话历史压缩策略
        conversation_history = self.context.conversation_history
        conversation_history.set_messages(history)
        conversation_history.apply_strategies()
        history = conversation_history.get_messages()

        # 自动召回相关记忆（优先级最高，作为上下文基础）
        from backend.app.prompts import auto_recall_memory
        recalled = auto_recall_memory(self.context.session_key, prompt)
        if recalled:
            memory_msg = HumanMessage(content=f"<recalled-memory>\n{recalled}\n</recalled-memory>")
            history.insert(0, memory_msg)
            _log("🧠", f"召回 {len(recalled.split(chr(10)))} 行记忆")

        # 注入所有待处理通知（inbox、后台任务等）
        pending_msgs = self.notification_service.get_pending_messages()
        if pending_msgs and history:
            history.extend(pending_msgs)
            _log("📬", f"注入 {len(pending_msgs)//2} 条通知消息")

        return history

    def _handle_llm_node(self, state: dict, turn: int, tracer, _pending_calls: dict) -> tuple:
        """
        处理 LLM 节点：记录 prompt、响应和工具调用决策

        Args:
            state: 节点状态
            turn: 当前轮次
            tracer: 追踪器
            _pending_calls: 待处理的工具调用字典

        Returns:
            (last_message, output_text)
        """
        last = state["messages"][-1]
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

        output = ""
        if getattr(last, "tool_calls", None):
            tcs = last.tool_calls
            mode = "并行" if len(tcs) > 1 else "串行"
            _log("🔀", f"  AI 决策: {mode}调用 {len(tcs)} 个工具")
            decisions = []
            for tc in tcs:
                icon = TOOL_ICONS.get(tc["name"], "🔧")
                _log("🔀", f"    {icon}[{tc['name']}] {_fmt_args(tc['name'], tc['args'])}")
                decisions.append({"tool": tc["name"], "args": _fmt_args(tc["name"], tc["args"])})
                # 使用更明确的 call_id
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

        return last, output

    async def _handle_tools_node(self, last, turn: int, total_tools: int, tracer,
                                  _pending_calls: dict, tool_results_summary: list,
                                  last_state_messages: list) -> tuple:
        """
        处理工具节点：记录工具结果、更新守卫、检查偏离

        Args:
            last: 最后一条消息
            turn: 当前轮次
            total_tools: 已执行工具数
            tracer: 追踪器
            _pending_calls: 待处理的工具调用字典
            tool_results_summary: 工具结果摘要列表
            last_state_messages: 最后状态的消息列表

        Returns:
            (total_tools, pending_msgs)
        """
        # 处理 content 可能是列表的情况
        if isinstance(last.content, str):
            content_str = last.content
        else:
            content_str = json.dumps(last.content, ensure_ascii=False)

        icon = TOOL_ICONS.get(last.name, "🔧")
        _log("📥", f"  {icon}[{last.name}] 返回: {content_str[:80]}")
        tool_results_summary.append(content_str[:500])
        total_tools += 1

        # 标记进度
        self.monitor.mark_step_done()

        # 定期检查是否偏离目标
        if self.monitor.should_check(total_tools, check_interval=self.monitor_check_interval):
            try:
                check = await self.monitor.check_on_track(self.context.llm)
                if not check.get("on_track", True):
                    _log("⚠️", f"偏离检测: {check.get('reason', 'unknown')}")
                    _log("💡", f"建议: {check.get('suggestion', 'continue')}")
            except Exception as e:
                _log("⚠️", f"监控检查失败: {e}")

        # 匹配 call_id（优先使用 tool_call_id，否则使用 name）
        call_id = getattr(last, "tool_call_id", None) or last.name
        pending = _pending_calls.pop(call_id, None)
        # 如果没找到，尝试用 name 再找一次
        if not pending:
            pending = _pending_calls.pop(last.name, None)
        duration_ms = round((time.time() - pending["t_start"]) * 1000) if pending else None

        tracer.emit("tool.result", turn=turn, tool=last.name, call_id=call_id,
                    duration_ms=duration_ms,
                    ok=not content_str.startswith("Error:"),
                    output=content_str[:500])

        # Save tool result to transcript
        self.context.session_store.save_tool_result(self.agent_name, last.name, call_id, content_str)

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

        return total_tools, pending_msgs

    def _generate_fallback_response(self, last_state_messages: list, tool_results_summary: list, tracer) -> str:
        """
        生成补充回答（当 DeepSeek 返回空响应时）

        Args:
            last_state_messages: 最后状态的消息列表
            tool_results_summary: 工具结果摘要列表
            tracer: 追踪器

        Returns:
            生成的回答文本
        """
        _log("🧠", "  [补充调用] 获取最终回答")
        tool_context = "\n".join(f"- {r}" for r in tool_results_summary)

        # Filter out AIMessages with tool_calls to avoid API validation error
        clean_messages = []
        skip_tool_messages = False
        for msg in last_state_messages:
            if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
                skip_tool_messages = True
                continue
            if isinstance(msg, ToolMessage):
                if skip_tool_messages:
                    continue
            else:
                skip_tool_messages = False
            clean_messages.append(msg)

        fallback_messages = clean_messages + [
            HumanMessage(content=f"工具调用结果如下：\n{tool_context}\n\n请根据以上结果，用中文简洁地回答用户的问题，直接引用工具返回的原始数据，不要编造任何ID或数值。")
        ]
        t_fallback = time.time()
        resp = self.context.overflow_guard.guard_invoke(messages=fallback_messages)
        output = resp.content
        tracer.emit("llm.fallback", duration_ms=round((time.time() - t_fallback) * 1000),
                    output_preview=output[:200])
        return output

    def _save_conversation(self, history: list, prompt: str, output: str, last_state_messages: list):
        """
        保存对话历史和 transcript

        Args:
            history: 历史消息列表
            prompt: 用户输入
            output: AI 回答
            last_state_messages: 最后状态的消息列表
        """
        history.append(HumanMessage(content=prompt))
        history.append(AIMessage(content=output))

        # Save turn to transcript
        tool_calls_data = []
        for msg in last_state_messages:
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                tool_calls_data = [{"name": tc["name"], "args": tc["args"]} for tc in msg.tool_calls]
                break
        self.context.session_store.save_turn(self.agent_name, prompt, output, tool_calls_data)

    async def run(self, prompt: str, history: list = None) -> str:
        if history is None:
            history = []

        # 第一次对话时创建 session（如果还没有）
        if not self.context.session_key:
            session_key = self.context.new_session_key()
            self.context.set_session_key(session_key)  # 自动同步到全局
            _log("🆕", f"创建新 session: {session_key}")

        # 第一次 run 时打印 Agent 就绪信息
        if self._first_run:
            _log("🤖", f"Agent 就绪 | session={self.context.session_key} | 模型={DEEPSEEK_MODEL}")
            self._first_run = False

        # Apply compaction strategies via conversation history
        conversation_history = self.context.conversation_history
        conversation_history.set_messages(history)
        conversation_history.apply_strategies()
        history = conversation_history.get_messages()

        # 自动召回相关记忆（优先级最高，作为上下文基础）
        from backend.app.prompts import auto_recall_memory
        recalled = auto_recall_memory(self.context.session_key, prompt)
        if recalled:
            memory_msg = HumanMessage(content=f"<recalled-memory>\n{recalled}\n</recalled-memory>")
            history.insert(0, memory_msg)
            _log("🧠", f"召回 {len(recalled.split(chr(10)))} 行记忆")

        # 注入所有待处理通知（inbox、后台任务等）
        pending_msgs = self.notification_service.get_pending_messages()
        if pending_msgs and history:
            history.extend(pending_msgs)
            _log("📬", f"注入 {len(pending_msgs)//2} 条通知消息")

        _log("👤", f"用户输入: {prompt}")
        run_start = time.time()
        tracer = self.context.tracer
        rid = tracer.new_run_id()
        tracer.set_run_id(rid)
        tracer.emit("run.start", prompt=prompt, session=self.context.session_key)

        # 记录系统提示词（每次 run 开始时记录一次）
        system_prompt = self.context.system_prompt
        tracer.emit("system.prompt", content=system_prompt[:5000], full_length=len(system_prompt))

        # 设置监控目标
        self.monitor.set_goal(prompt, estimated_steps=5)

        # 创建 AgentRun 对象封装运行状态
        run = AgentRun(prompt=prompt, history=history)
        run.messages = self._build_messages(history, prompt)
        run.last_state_messages = run.messages

        async for step in self.context.agent.astream({"messages": run.messages}, stream_mode="updates"):
            for node, state in step.items():
                last = state["messages"][-1]

                # 处理 LLM 节点
                if node in ("agent", "call_model", "llm", "__start__", "model"):
                    run.turn += 1
                    run.last_state_messages = state["messages"]
                    last, node_output = self._handle_llm_node(state, run.turn, tracer, run.pending_calls)
                    if node_output:
                        run.output = node_output

                # 处理工具节点
                elif node == "tools":
                    run.total_tools, pending_msgs = await self._handle_tools_node(
                        last, run.turn, run.total_tools, tracer, run.pending_calls,
                        run.tool_results_summary, run.last_state_messages
                    )
                    # 同轮注入通知消息
                    if pending_msgs:
                        run.messages = run.last_state_messages + pending_msgs
                        _log("📡", f"  同轮注入 {len(pending_msgs)//2} 条通知消息")

        # DeepSeek sometimes returns empty content after tool use — call LLM once more
        if not run.output:
            run.output = self._generate_fallback_response(run.last_state_messages, run.tool_results_summary, tracer)

        # 保存对话历史和 transcript
        self._save_conversation(history, prompt, run.output, run.last_state_messages)

        # Manual compact is now handled by ManualCompactionStrategy in guard
        # No need for separate manual compact logic here

        duration_ms = round((time.time() - run_start) * 1000)
        tracer.emit("run.end", output=run.output[:300], turns=run.turn,
                    total_tools=run.total_tools, duration_ms=duration_ms)

        # 输出监控状态
        status = self.monitor.get_status()
        _log("📊", f"进度: {status['progress']} ({status['current_step']}/{status['total_steps']})")

        _log("✅", f"AI 最终回答 → {run.output[:120]}")
        return run.output
