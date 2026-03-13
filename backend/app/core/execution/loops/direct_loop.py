"""
DirectLoop - 直接循环模式（类似 s01_agent_loop.py）

核心模式：
    while stop_reason == "tool_use":
        response = LLM(messages, tools)
        execute tools
        append results

不依赖 LangGraph，完全手动控制循环
"""
import time
import logging
from typing import Tuple, Any, List

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage

from .base import BaseLoop
from backend.app.core.execution.config import CONFIG
from backend.app.core.execution.utils.console import console

logger = logging.getLogger(__name__)


class DirectLoop(BaseLoop):
    """
    直接循环模式 - 手动控制 LLM + Tools 循环

    优点：
    - 完全控制循环逻辑
    - 不依赖 LangGraph 的路由机制
    - 更容易调试和理解
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
        执行直接循环

        Args:
            llm: LLM 实例（必须支持 bind_tools）
            tools: 工具列表
            system_prompt: 系统提示词
            user_prompt: 用户输入
            span_id: Tracer span ID
            subagent_type: Subagent 类型
            agent: 不使用（兼容接口）
            recursion_limit: 最大循环次数

        Returns:
            (output, tool_count)
        """
        self._validate_inputs(llm, tools, system_prompt, user_prompt)

        if recursion_limit is None:
            recursion_limit = CONFIG.MAX_RECURSION_LIMIT

        self._log_start(subagent_type, user_prompt)

        try:
            output, tool_count = self._execute_direct_loop(
                llm=llm,
                tools=tools,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                subagent_type=subagent_type,
                recursion_limit=recursion_limit,
            )

            self._log_end(subagent_type, tool_count, len(output))
            return output, tool_count

        except Exception as e:
            self._handle_error(e, subagent_type)

    def _execute_direct_loop(
        self,
        llm: Any,
        tools: list,
        system_prompt: str,
        user_prompt: str,
        subagent_type: str,
        recursion_limit: int,
    ) -> Tuple[str, int]:
        """执行直接循环的核心逻辑"""

        # 绑定工具到 LLM
        llm_with_tools = llm.bind_tools(tools) if tools else llm

        # 初始化消息列表
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]

        tool_count = 0
        output = ""
        loop_count = 0

        # 核心循环：while True，检查 tool_calls 决定是否继续
        while loop_count < recursion_limit:
            loop_count += 1

            # 1. 调用 LLM
            console.llm_call(subagent_type, len(messages))
            response = llm_with_tools.invoke(messages)

            # 2. 追加 AI 消息
            messages.append(response)

            # 3. 检查是否有工具调用
            tool_calls = getattr(response, "tool_calls", None)

            if not tool_calls:
                # 没有工具调用，循环结束
                output = response.content or ""
                console.llm_response(subagent_type, output[:200])
                break

            # 4. 执行工具调用
            tool_messages = []
            for tool_call in tool_calls:
                tool_count += 1
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]
                tool_id = tool_call.get("id", f"call_{tool_count}")

                console.tool_call(subagent_type, tool_name, tool_args)

                # 查找并执行工具
                tool_result = self._execute_tool(tools, tool_name, tool_args)

                console.tool_result(subagent_type, tool_result[:200])

                # 创建 ToolMessage
                tool_messages.append(
                    ToolMessage(
                        content=tool_result,
                        tool_call_id=tool_id,
                        name=tool_name
                    )
                )

            # 5. 追加工具结果
            messages.extend(tool_messages)

        # 如果达到最大循环次数仍未结束
        if loop_count >= recursion_limit and not output:
            console.warning(subagent_type, f"达到最大循环次数 {recursion_limit}")
            output = "达到最大循环次数，任务可能未完成"

        return output, tool_count

    def _execute_tool(self, tools: list, tool_name: str, tool_args: dict) -> str:
        """执行单个工具"""
        # 查找工具
        tool = None
        for t in tools:
            if t.name == tool_name:
                tool = t
                break

        if tool is None:
            return f"Error: Tool '{tool_name}' not found"

        try:
            # 执行工具
            result = tool.invoke(tool_args)

            # 转换结果为字符串
            if isinstance(result, str):
                return result
            else:
                import json
                return json.dumps(result, ensure_ascii=False)

        except Exception as e:
            return f"Error executing tool: {str(e)}"
