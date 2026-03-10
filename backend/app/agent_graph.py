"""
LangGraph 版本的 Agent 实现

使用 StateGraph 管理 Agent 运行流程，替代手动的 async for 循环
"""
import time
from typing import TypedDict, Annotated, Literal
from dataclasses import dataclass, field

from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage

from backend.app.context import AgentContext
from backend.app.config import DEEPSEEK_MODEL
from backend.app.notifications import NotificationService
from backend.app.guards.todo_reminder import TodoReminderGuard
from backend.app.guards.reflection_gate import ReflectionGatekeeper


# ============================================================================
# State 定义
# ============================================================================

class AgentState(TypedDict):
    """Agent 运行状态"""
    # 输入
    prompt: str
    history: list

    # 上下文
    session_key: str
    messages: list

    # 运行状态
    output: str
    turn: int
    total_tools: int

    # 追踪信息
    last_state_messages: list
    tool_results_summary: list
    pending_calls: dict

    # 元数据
    start_time: float
    tracer: object


# ============================================================================
# 节点函数
# ============================================================================

def prepare_context_node(state: AgentState, context: AgentContext,
                         notification_service: NotificationService) -> AgentState:
    """准备上下文：压缩、记忆召回、通知注入"""
    history = state["history"]
    prompt = state["prompt"]

    # 应用压缩策略
    conversation_history = context.get_conversation_history()
    conversation_history.set_messages(history)
    conversation_history.apply_strategies()
    history = conversation_history.get_messages()

    # 召回记忆
    from backend.app.prompts import auto_recall_memory
    recalled = auto_recall_memory(state["session_key"], prompt)
    if recalled:
        memory_msg = HumanMessage(content=f"<recalled-memory>\n{recalled}\n</recalled-memory>")
        history.insert(0, memory_msg)
        print(f"🧠 召回 {len(recalled.split(chr(10)))} 行记忆")

    # 注入通知
    pending_msgs = notification_service.get_pending_messages()
    if pending_msgs and history:
        history.extend(pending_msgs)
        print(f"📬 注入 {len(pending_msgs)//2} 条通知消息")

    state["history"] = history
    return state


def build_messages_node(state: AgentState, todo_reminder: TodoReminderGuard,
                       reflection_gate: ReflectionGatekeeper) -> AgentState:
    """构建消息列表"""
    messages = state["history"] + [HumanMessage(content=state["prompt"])]

    # 添加守卫提醒
    if todo_reminder.should_remind():
        messages.append(HumanMessage(content=todo_reminder.get_reminder_message()))

    if reflection_gate.should_gate():
        messages.append(HumanMessage(content=reflection_gate.get_gate_message()))

    state["messages"] = messages
    state["last_state_messages"] = messages
    return state


def call_llm_node(state: AgentState, context: AgentContext) -> AgentState:
    """调用 LLM"""
    state["turn"] += 1

    # 这里调用实际的 LLM
    # 简化版：直接使用 context.get_agent()
    # 实际需要处理流式输出和工具调用

    print(f"🧠 [第 {state['turn']} 次调用 LLM]")

    # TODO: 实现 LLM 调用逻辑
    # 这里需要判断是否有工具调用

    return state


def should_use_tools(state: AgentState) -> Literal["tools", "response"]:
    """判断是否需要使用工具"""
    # 检查最后一条消息是否包含工具调用
    last_msg = state["last_state_messages"][-1] if state["last_state_messages"] else None

    if last_msg and hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
        return "tools"
    return "response"


def execute_tools_node(state: AgentState, context: AgentContext) -> AgentState:
    """执行工具"""
    print(f"🔧 执行工具")

    # TODO: 实现工具执行逻辑
    state["total_tools"] += 1

    return state


def generate_response_node(state: AgentState) -> AgentState:
    """生成最终响应"""
    if not state["output"]:
        print("🧠 [补充调用] 获取最终回答")
        # TODO: 实现补充调用逻辑
        state["output"] = "响应内容"

    return state


def save_conversation_node(state: AgentState, context: AgentContext) -> AgentState:
    """保存对话"""
    history = state["history"]
    prompt = state["prompt"]
    output = state["output"]

    history.append(HumanMessage(content=prompt))
    history.append(AIMessage(content=output))

    # 保存到 transcript
    context.get_store().save_turn("main", prompt, output, [])

    print(f"✅ AI 最终回答 → {output[:120]}")

    return state


# ============================================================================
# Graph 构建
# ============================================================================

def create_agent_graph(context: AgentContext,
                       notification_service: NotificationService,
                       todo_reminder: TodoReminderGuard,
                       reflection_gate: ReflectionGatekeeper):
    """创建 Agent StateGraph"""

    # 创建图
    workflow = StateGraph(AgentState)

    # 添加节点（使用 lambda 绑定依赖）
    workflow.add_node("prepare_context",
                     lambda s: prepare_context_node(s, context, notification_service))
    workflow.add_node("build_messages",
                     lambda s: build_messages_node(s, todo_reminder, reflection_gate))
    workflow.add_node("call_llm",
                     lambda s: call_llm_node(s, context))
    workflow.add_node("execute_tools",
                     lambda s: execute_tools_node(s, context))
    workflow.add_node("generate_response",
                     lambda s: generate_response_node(s))
    workflow.add_node("save_conversation",
                     lambda s: save_conversation_node(s, context))

    # 设置入口
    workflow.set_entry_point("prepare_context")

    # 添加边
    workflow.add_edge("prepare_context", "build_messages")
    workflow.add_edge("build_messages", "call_llm")

    # 条件路由：LLM 后决定是否使用工具
    workflow.add_conditional_edges(
        "call_llm",
        should_use_tools,
        {
            "tools": "execute_tools",
            "response": "generate_response"
        }
    )

    # 工具执行后回到 LLM（循环）
    workflow.add_edge("execute_tools", "call_llm")

    # 生成响应后保存对话
    workflow.add_edge("generate_response", "save_conversation")

    # 保存后结束
    workflow.add_edge("save_conversation", END)

    # 编译图
    return workflow.compile()


# ============================================================================
# 使用示例
# ============================================================================

async def run_with_graph(prompt: str, history: list, context: AgentContext,
                        notification_service: NotificationService,
                        todo_reminder: TodoReminderGuard,
                        reflection_gate: ReflectionGatekeeper) -> str:
    """使用 LangGraph 运行 Agent"""

    # 创建图
    graph = create_agent_graph(context, notification_service, todo_reminder, reflection_gate)

    # 初始化状态
    initial_state: AgentState = {
        "prompt": prompt,
        "history": history or [],
        "session_key": context.get_session_key(),
        "messages": [],
        "output": "",
        "turn": 0,
        "total_tools": 0,
        "last_state_messages": [],
        "tool_results_summary": [],
        "pending_calls": {},
        "start_time": time.time(),
        "tracer": context.get_tracer()
    }

    # 运行图
    final_state = await graph.ainvoke(initial_state)

    return final_state["output"]
