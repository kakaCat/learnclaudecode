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
from typing import List
from langchain_core.messages import HumanMessage, AIMessage

from backend.app.core.context.base_context import BaseContext
from backend.app.core.tools.history_manager import HistoryManager
from backend.app.core.guards import GuardManager
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
            agent_name = getattr(context, 'agent_name', 'unnamed_agent')
            langchain_callback = ObservabilityCallback(
                agent_type=agent_name,
                enable_console=True,
                enable_tracer=True
            )

            # 4. 执行直接循环（不使用 LangGraph）
            output, tool_calls = await self._execute_react_loop(
                context, messages, langchain_callback
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

    

    async def _execute_react_loop(self, context, messages, langchain_callback, retry_count=0, max_retries=10):
        """
        执行 ReAct 循环（使用 LangGraph）

        使用新的 create_agent API（LangGraph v1.0+）
        支持守卫违规后重试

        Args:
            context: Agent 上下文
            messages: 消息列表
            langchain_callback: LangChain Callback Handler
            retry_count: 当前重试次数
            max_retries: 最大重试次数
        """
        from langchain.agents import create_agent

        # 外层循环：处理截断恢复（不占用重试次数）
        truncation_retry = 0
        max_truncation_retries = 3

        while truncation_retry <= max_truncation_retries:
            # 🔍 调试：检查工具
            tools = context.get_tools()
            print(f"\n🔍 调试: 工具数={len(tools)}, 工具名={[t.name for t in tools]}")

            # 获取 system prompt
            system_prompt = context.get_system_prompt()

            # 创建 LangGraph ReAct Agent（使用新 API）
            agent = create_agent(context.llm, tools, system_prompt=system_prompt)

            output = ""
            tool_calls_data = []
            loop_count = 0
            guard_violation_detected = False
            truncation_detected = False

            print(f"\n🔄 开始 ReAct 循环（LangGraph）...")
            if retry_count > 0:
                print(f"🔁 守卫重试 {retry_count}/{max_retries}")
            if truncation_retry > 0:
                print(f"🔁 截断恢复 {truncation_retry}/{max_truncation_retries}")
            print(f"📋 工具数量: {len(tools)}")
            print(f"💬 初始消息数: {len(messages)}")

            # 使用 LangGraph 的 astream 循环
            async for step in agent.astream(
                {"messages": messages},
                stream_mode="updates",
                config={"callbacks": [langchain_callback]}
            ):
                for node, state in step.items():
                    last = state["messages"][-1]

                    if node == "agent":
                        loop_count += 1
                        print(f"\n--- ReAct Loop {loop_count} ---")

                        # 🔍 调试：检查 LLM 响应
                        print(f"🔍 响应类型: {type(last)}")
                        print(f"🔍 content: {last.content[:200] if last.content else 'None'}...")
                        print(f"🔍 tool_calls: {getattr(last, 'tool_calls', None)}")

                        # 检查工具调用
                        tool_calls = getattr(last, "tool_calls", None)
                        if tool_calls:
                            print(f"🔧 LLM 请求调用 {len(tool_calls)} 个工具")
                            for tc in tool_calls:
                                print(f"  → {tc['name']}({list(tc['args'].keys())})")
                                tool_calls_data.append({"name": tc["name"], "args": tc["args"]})
                        else:
                            # 没有工具调用，获取最终输出
                            output = last.content or ""
                            print(f"✅ LLM 返回最终答案 (长度: {len(output)})")

                            # 方案2：检测输出截断（长文本但没有工具调用，可能被截断）
                            if len(output) > 3000 and truncation_retry < max_truncation_retries:
                                print(f"⚠️  检测到长输出但无工具调用，可能被截断，注入提示继续")
                                messages.append(HumanMessage(
                                    content="请直接调用工具完成任务，不要输出大段内容。"
                                ))
                                truncation_detected = True
                                break

                            # 检查守卫违规（例如：承诺要调用工具但没调用）
                            injected = self.guard_manager.check_and_inject_after_llm(last, messages)
                            if injected:
                                print(f"⚠️  守卫检测到违规，已注入警告消息")
                                guard_violation_detected = True
                                break

                    elif node == "tools":
                        # 工具执行完成
                        result = last.content
                        print(f"  ← 结果: {result[:100]}...")

                        # 更新守卫状态
                        self.guard_manager.on_tool_call(last.name)

                # 如果检测到违规，中断外层循环
                if guard_violation_detected or truncation_detected:
                    break

            # 如果检测到截断，继续外层循环（不占用守卫重试次数）
            if truncation_detected:
                truncation_retry += 1
                continue

            # 如果检测到守卫违规且未超过重试次数，递归重试
            if guard_violation_detected and retry_count < max_retries:
                print(f"🔁 守卫违规，使用更新后的消息重新执行 ReAct 循环...")
                return await self._execute_react_loop(
                    context,
                    messages,
                    langchain_callback,
                    retry_count=retry_count + 1,
                    max_retries=max_retries
                )

            # 如果超过最大重试次数
            if guard_violation_detected and retry_count >= max_retries:
                print(f"⚠️  已达到最大重试次数 ({max_retries})，停止重试")

            # 正常结束，退出外层循环
            break

        print(f"\n✅ ReAct 循环结束 (总计 {loop_count} 轮, {len(tool_calls_data)} 次工具调用)\n")
        return output, tool_calls_data
