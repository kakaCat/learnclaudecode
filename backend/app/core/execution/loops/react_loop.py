"""
ReAct 执行循环
"""
import time
import logging
from typing import Tuple, Any

from langchain_core.messages import SystemMessage, HumanMessage

from .base import BaseLoop
from backend.app.core.guards.tracer import Tracer
from backend.app.core.execution.langchain_callback import ObservabilityCallback
from backend.app.memory import ConversationHistory

logger = logging.getLogger(__name__)
tracer = Tracer()


class ReActLoop(BaseLoop):
    """
    ReAct (Reasoning + Acting) 执行循环

    循环执行: Reason → Act → Observe → repeat，直到没有工具调用。
    """

    def run(
        self,
        llm: Any,
        tools: list,
        system_prompt: str,
        user_prompt: str,
        span_id: str,
        subagent_type: str,
        agent: Any = None,
        recursion_limit: int = None,
    ) -> Tuple[str, int]:
        """
        执行 ReAct 循环

        Args:
            llm: LLM 实例
            tools: 工具列表
            system_prompt: 系统提示词
            user_prompt: 用户输入
            span_id: Tracer span ID
            subagent_type: Subagent 类型
            agent: LangGraph agent 实例（必需）
            recursion_limit: 递归限制（可选，默认使用配置）

        Returns:
            (output, tool_count)
        """
        # 验证输入
        self._validate_inputs(llm, tools, system_prompt, user_prompt)

        if agent is None:
            raise LoopExecutionError("ReActLoop", "Agent instance is required")

        if recursion_limit is None:
            recursion_limit = CONFIG.MAX_RECURSION_LIMIT

        self._log_start(subagent_type, user_prompt)

        # 创建 LangChain Callback
        langchain_callback = ObservabilityCallback(
            agent_type=f"subagent.{subagent_type}",
            enable_console=True,
            enable_tracer=True,
            span_id=span_id
        )

        try:
            output, tool_count = self._execute_loop(
                agent=agent,
                llm=llm,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                span_id=span_id,
                subagent_type=subagent_type,
                recursion_limit=recursion_limit,
                langchain_callback=langchain_callback,
            )

            self._log_end(subagent_type, tool_count, len(output))
            return output, tool_count

        except Exception as e:
            self._handle_error(e, subagent_type)

    def _execute_loop(
        self,
        agent: Any,
        llm: Any,
        system_prompt: str,
        user_prompt: str,
        span_id: str,
        subagent_type: str,
        recursion_limit: int,
        langchain_callback: ObservabilityCallback,
    ) -> Tuple[str, int]:
        """执行 ReAct 循环的核心逻辑"""
        tool_count = 0
        output = ""
        tool_results_summary = []
        sub_turn = 0
        _pending_calls: dict[str, dict] = {}

        # 创建历史管理器（使用配置的压缩阈值）
        history_manager = ConversationHistory.create_default(
            llm=llm,
            tools=[],
            max_tokens=CONFIG.MAX_CONTEXT_TOKENS,
            compression_threshold=CONFIG.COMPRESSION_THRESHOLD
        )
        initial_messages = [HumanMessage(content=user_prompt)]
        history_manager.set_messages(initial_messages)

        # 流式执行 agent（传入 LangChain Callback）
        for step in agent.stream(
            {"messages": history_manager.get_messages()},
            stream_mode="updates",
            config={
                "recursion_limit": recursion_limit,
                "callbacks": [langchain_callback]
            },
        ):
            for node, state in step.items():
                last = state["messages"][-1]

                if node == "agent":
                    sub_turn += 1

                    # 更新历史管理器
                    history_manager.set_messages(state["messages"])

                    # 检查是否需要压缩
                    tokens = history_manager.estimate_tokens()
                    if tokens > CONFIG.COMPRESSION_THRESHOLD:
                        console.compression(
                            subagent_type,
                            len(state["messages"]),
                            0,  # 压缩后数量稍后更新
                            tokens,
                            0
                        )
                        history_manager.apply_strategies()
                        compressed_messages = history_manager.get_messages()
                        new_tokens = history_manager.estimate_tokens()
                        console.compression(
                            subagent_type,
                            len(state["messages"]),
                            len(compressed_messages),
                            tokens,
                            new_tokens
                        )

                    # 处理工具调用
                    if getattr(last, "tool_calls", None):
                        # LangChain Callback 已自动追踪工具调用
                        # 这里只保留 Console 输出
                        for tc in last.tool_calls:
                            console.tool_call(subagent_type, tc["name"], tc["args"])
                            call_id = tc.get("id") or tc["name"]
                            _pending_calls[call_id] = {
                                "tool": tc["name"],
                                "t_start": time.time()
                            }
                    else:
                        # 没有工具调用，直接返回
                        output = last.content

                elif node == "tools":
                    tool_count += 1
                    tool_results_summary.append(
                        last.content[:CONFIG.TOOL_SUMMARY_MAX_LENGTH]
                    )
                    # LangChain Callback 已自动追踪工具结果
                    # 这里只保留 Console 输出
                    console.tool_result(subagent_type, last.content)

                    # 工具执行后也更新历史
                    history_manager.set_messages(state["messages"])

        # DeepSeek 有时在工具调用后返回空内容 - 再调用一次 LLM
        if not output and tool_count > 0:
            output = self._fallback_summary(
                llm,
                system_prompt,
                tool_results_summary,
                subagent_type
            )

        return output, tool_count

    def _fallback_summary(
        self,
        llm: Any,
        system_prompt: str,
        tool_results: list,
        subagent_type: str
    ) -> str:
        """当 LLM 返回空内容时，生成 fallback 总结"""
        tool_context = "\n".join(f"- {r}" for r in tool_results)
        fallback = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(
                content=f"工具调用结果如下：\n{tool_context}\n\n"
                        f"请简洁地总结你完成的工作，直接引用工具返回的原始数据。"
            )
        ])
        output = fallback.content.strip()
        console.fallback(subagent_type, output)
        return output
