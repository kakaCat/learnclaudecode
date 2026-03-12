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
"""
import time
import json
from typing import List
from langchain_core.messages import HumanMessage, AIMessage

from backend.app.core.base_context import BaseContext
from backend.app.core.history_manager import HistoryManager
from backend.app.core.guard_manager import GuardManager


class AgentRunner:
    """Agent 核心执行器"""

    def __init__(
        self,
        history_manager: HistoryManager = None,
        guard_manager: GuardManager = None
    ):
        """
        初始化执行器

        Args:
            history_manager: 历史管理器
            guard_manager: 守卫管理器
        """
        self.history_manager = history_manager or HistoryManager()
        self.guard_manager = guard_manager or GuardManager()

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

        # 1. 准备历史（压缩 + 召回）
        prepared_history = self.history_manager.prepare(context, prompt, history)

        # 2. 构建消息（添加用户输入 + 守卫消息）
        messages = prepared_history + [HumanMessage(content=prompt)]
        messages = self.guard_manager.inject_messages(messages)

        # 3. 获取 Agent 并执行
        from langchain.agents import create_agent
        agent = create_agent(
            context.llm,
            context.get_tools(),
            system_prompt=context.get_system_prompt()
        )

        # 4. 执行循环
        output, tool_calls = await self._execute_loop(context, agent, messages)

        # 5. 保存历史
        self.history_manager.save(context, prompt, output, tool_calls)

        # 6. 更新原始 history
        history.append(HumanMessage(content=prompt))
        history.append(AIMessage(content=output))

        return output

    async def _execute_loop(self, context, agent, messages):
        """
        执行 Agent 循环

        Returns:
            (output, tool_calls)
        """
        output = ""
        tool_calls_data = []
        tool_results = []

        async for step in agent.astream({"messages": messages}, stream_mode="updates"):
            for node, state in step.items():
                last = state["messages"][-1]

                # LLM 节点
                if node in ("agent", "call_model", "llm", "model"):
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
                    content = last.content if isinstance(last.content, str) else json.dumps(last.content)
                    tool_results.append(content[:500])
                    # 更新守卫状态
                    self.guard_manager.on_tool_call(last.name)

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
