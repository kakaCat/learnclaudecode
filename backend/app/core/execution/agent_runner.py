"""
AgentRunner - 核心执行器

职责：
1. 执行 LLM + Tools 循环
2. 协调 HistoryManager、GuardManager、NotificationManager
3. 处理工具调用和结果

核心改进：
- 单一职责：只负责执行逻辑
- 依赖注入：通过构造函数注入依赖
- 无状态：每次 run 都是独立的
- 使用 LangChain Callbacks 自动追踪
"""
import time
import json
from typing import List, Optional
from langchain_core.messages import HumanMessage, AIMessage

from backend.app.core.context.base_context import BaseContext
from backend.app.core.tools.history_manager import HistoryManager
from backend.app.core.guards.guard_manager import GuardManager
from backend.app.core.execution.observability import ObservabilityCollector
from backend.app.core.execution.langchain_callback import ObservabilityCallback


class AgentRunner:
    """Agent 核心执行器"""

    def __init__(
        self,
        history_manager: HistoryManager = None,
        guard_manager: GuardManager = None,
        observer: ObservabilityCollector = None
    ):
        """
        初始化执行器

        Args:
            history_manager: 历史管理器
            guard_manager: 守卫管理器
            observer: 可观测性收集器
        """
        self.history_manager = history_manager or HistoryManager()
        self.guard_manager = guard_manager or GuardManager()
        self.observer = observer or ObservabilityCollector()

    async def run(
        self,
        context: BaseContext,
        prompt: str,
        history: List = None
    ) -> str:
        """
        运行 Agent

        Args:
            context: Agent 上下文
            prompt: 用户输入
            history: 历史消息

        Returns:
            AI 输出
        """
        if history is None:
            history = []

        # 0. 开始追踪
        run_id = self.observer.start(prompt, len(history))

        try:
            # 1. 准备历史（压缩 + 召回）
            prepared_history = self.history_manager.prepare(context, prompt, history)

            # 2. 构建消息（添加用户输入 + 守卫消息）
            messages = prepared_history + [HumanMessage(content=prompt)]
            messages = self.guard_manager.inject_messages(messages)

            # 3. 创建 LangChain Callback
            langchain_callback = ObservabilityCallback(
                agent_type="main_agent",
                enable_console=True,
                enable_tracer=True
            )

            # 4. 获取 Agent 并执行（传入 callback）
            from langchain.agents import create_agent
            agent = create_agent(
                context.llm,
                context.get_tools(),
                system_prompt=context.get_system_prompt()
            )

            # 5. 执行循环（带追踪）
            output, tool_calls = await self._execute_loop_with_trace(
                context, agent, messages, langchain_callback
            )

            # 6. 保存历史
            self.history_manager.save(context, prompt, output, tool_calls)

            # 7. 更新原始 history
            history.append(HumanMessage(content=prompt))
            history.append(AIMessage(content=output))

            # 8. 更新所有统计数据（从 LangChain Callback 获取）
            self.observer.metrics.llm_calls = langchain_callback.llm_calls
            self.observer.metrics.tool_calls = langchain_callback.tool_calls
            self.observer.metrics.subagent_calls = langchain_callback.subagent_calls
            self.observer.metrics.total_input_tokens = langchain_callback.total_input_tokens
            self.observer.metrics.total_output_tokens = langchain_callback.total_output_tokens
            self.observer.metrics.total_cost = langchain_callback.total_cost
            self.observer.metrics.total_steps = langchain_callback.llm_calls + langchain_callback.tool_calls

            # 9. 结束追踪
            self.observer.end(output=output)

            return output

        except Exception as e:
            # 追踪错误
            self.observer.on_error(str(e))
            raise

    async def _execute_loop_with_trace(self, context, agent, messages, langchain_callback):
        """
        执行 Agent 循环（带追踪）

        循环会一直执行，直到 agent 决定停止（不再调用工具，返回最终答案）

        完全信任 Agent 的自主判断，不设置任何步数限制

        Args:
            context: Agent 上下文
            agent: LangGraph agent
            messages: 消息列表
            langchain_callback: LangChain Callback Handler

        Returns:
            (output, tool_calls)
        """
        output = ""
        tool_calls_data = []
        tool_results = []
        step_counter = 0

        try:
            # 传入 callback 到 agent 执行配置
            async for step in agent.astream(
                {"messages": messages},
                stream_mode="updates",
                config={
                    "recursion_limit": context.recursion_limit,
                    "callbacks": [langchain_callback]
                }
            ):
                for node, state in step.items():
                    last = state["messages"][-1]

                    # LLM 节点
                    if node in ("agent", "call_model", "llm", "model"):
                        step_counter += 1

                        # LangChain Callback 已自动追踪 LLM 调用
                        # 这里只需要处理业务逻辑

                        if getattr(last, "tool_calls", None):
                            # 记录工具调用
                            for tc in last.tool_calls:
                                tool_calls_data.append({"name": tc["name"], "args": tc["args"]})
                        else:
                            output = last.content or ""

                            # 检查承诺违规
                            warning = self.guard_manager.check_commitment(last)
                            if warning:
                                print(f"⚠️  {warning}")

                    # 工具节点
                    elif node == "tools":
                        step_counter += 1

                        # LangChain Callback 已自动追踪工具调用
                        # 这里只需要处理业务逻辑

                        tool_name = getattr(last, "name", "unknown")
                        content = last.content if isinstance(last.content, str) else json.dumps(last.content)
                        tool_results.append(content[:500])

                        # 更新守卫状态
                        self.guard_manager.on_tool_call(tool_name)

        except Exception as e:
            print(f"❌ Agent 执行出错: {e}")
            import traceback
            traceback.print_exc()
            raise

        # 如果没有输出，生成补充回答
        if not output and tool_results:
            output = await self._generate_fallback(context, tool_results)

        return output, tool_calls_data

    async def _generate_fallback(self, context, tool_results: List[str]) -> str:
        """生成补充回答"""
        tool_context = "\n".join(f"- {r}" for r in tool_results)
        resp = context.llm.invoke([
            HumanMessage(content=f"工具结果：\n{tool_context}\n\n请简洁总结。")
        ])
        return resp.content
