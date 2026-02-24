import json
import logging

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage
from langchain.agents import create_agent
from backend.app.config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL
from backend.app.prompts import SYSTEM_PROMPT
from backend.app.tools import TOOLS
from backend.app.compact import was_compact_requested
from backend.app.background import drain_notifications
from backend.app.team import get_bus
from backend.app.team import state as _team_state
from backend.app.compaction import estimate_tokens, micro_compact, auto_compact
from backend.app.session import new_session_key, set_session_key, save_session

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
    "background_run": "⚡", "check_background": "📡",
    "worktree_create": "🌿", "worktree_list": "🌳", "worktree_status": "📊",
    "worktree_run": "▶️", "worktree_remove": "🗑️", "worktree_keep": "📎",
    "worktree_events": "📜",
}


def _log(icon: str, msg: str):
    print(f"{G}{icon} {msg}{R}")


def _build_agent():
    llm = ChatOpenAI(
        model=DEEPSEEK_MODEL,
        api_key=DEEPSEEK_API_KEY,
        base_url=DEEPSEEK_BASE_URL,
    )
    return create_agent(llm, TOOLS, system_prompt=SYSTEM_PROMPT), llm


class AgentService:
    def __init__(self):
        self.agent, self.llm = _build_agent()
        self.session_key = new_session_key()
        set_session_key(self.session_key)
        self.rounds_without_todo = 0
        _log("🤖", f"Agent 就绪 | 模型={DEEPSEEK_MODEL} | session={self.session_key}")

    def run(self, prompt: str, history: list = None) -> str:
        if history is None:
            history = []

        # Layer 1: micro_compact
        micro_compact(history)
        # Layer 2: auto_compact
        if estimate_tokens(history, self.llm) > THRESHOLD:
            _log("🗜️", "[auto_compact triggered]")
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

        messages = history + [HumanMessage(content=prompt)]
        if self.rounds_without_todo >= 3:
            messages.append(HumanMessage(content="<reminder>请更新你的 TodoWrite 待办事项。</reminder>"))
        output = ""
        turn = 0
        last_state_messages = messages
        tool_results_summary = []

        for step in self.agent.stream({"messages": messages}, stream_mode="updates"):
            for node, state in step.items():
                last = state["messages"][-1]
                if node == "agent":
                    turn += 1
                    last_state_messages = state["messages"]
                    _log("🧠", f"[第 {turn} 次调用 LLM] 上下文消息数={len(state['messages'])}")
                    if getattr(last, "tool_calls", None):
                        for tc in last.tool_calls:
                            icon = TOOL_ICONS.get(tc["name"], "🔧")
                            _log("🔀", f"  AI 决策: 调用工具 {icon}[{tc['name']}] 参数={tc['args']}")
                    else:
                        output = last.content or output
                        _log("🧠", f"  AI 决策: 直接回答，无需工具")
                elif node == "tools":
                    _log("📥", f"  工具返回: {last.content[:80]}")
                    tool_results_summary.append(last.content[:500])
                    if last.name == "TodoWrite":
                        self.rounds_without_todo = 0
                    else:
                        self.rounds_without_todo += 1
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
            resp = self.llm.invoke(fallback_messages)
            output = resp.content

        history.append(HumanMessage(content=prompt))
        history.append(AIMessage(content=output))

        # Layer 3: manual compact triggered by compact tool
        if was_compact_requested():
            _log("🗜️", "[manual compact]")
            new_history = auto_compact(history, self.llm)
            history.clear()
            history.extend(new_history)

        _log("✅", f"AI 最终回答 → {output[:120]}")
        save_session("main", history)
        return output
