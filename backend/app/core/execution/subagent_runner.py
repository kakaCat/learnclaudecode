"""
Subagent 运行器

统一的 Subagent 执行入口
"""
import logging
from typing import Any, Optional

from langchain_core.messages import SystemMessage, HumanMessage

from backend.app.core.execution.config import CONFIG
from backend.app.core.registry import registry
from backend.app.core.execution.loops import ReActLoop, OODALoop
from backend.app.core.execution.exceptions import AgentNotFoundError, LoopExecutionError
from backend.app.core.execution.span_manager import SpanManager
from backend.app.core.execution.prompt_validator import PromptValidator

logger = logging.getLogger(__name__)


class SubagentRunner:
    """
    Subagent 运行器

    负责执行 Subagent，根据配置选择合适的执行循环。

    Example:
        >>> runner = SubagentRunner()
        >>> output = runner.run(
        ...     sub_context=context,
        ...     description="探索代码库",
        ...     prompt="查找所有 API 端点"
        ... )
    """

    def __init__(self):
        self.span_manager = SpanManager()
        self.prompt_validator = PromptValidator()
        self.react_loop = ReActLoop()
        self.ooda_loop = OODALoop()

    def run(
        self,
        sub_context: Any,
        description: str,
        prompt: str,
        recursion_limit: Optional[int] = None
    ) -> str:
        """
        运行 Subagent

        Args:
            sub_context: SubagentContext 实例
            description: 任务描述
            prompt: 用户输入
            recursion_limit: 递归限制（可选）

        Returns:
            Subagent 输出

        Raises:
            AgentNotFoundError: Agent 类型不存在
            LoopExecutionError: 执行失败
        """
        subagent_type = sub_context.subagent_type

        # 获取 Agent 配置
        try:
            agent_config = registry.get(subagent_type)
        except AgentNotFoundError:
            logger.error(f"Unknown agent type: {subagent_type}")
            raise

        # 获取资源
        llm = sub_context.llm
        tools = sub_context.tools
        system_prompt = sub_context.system_prompt

        # 1. 验证并截断 prompt
        prompt = self.prompt_validator.validate_and_truncate(prompt, llm)

        # 2. 开始 span
        span_id, start_time = self.span_manager.start_span(
            subagent_type, description, tools
        )

        # 3. 根据 loop_type 选择执行循环
        try:
            if agent_config.loop_type == "ooda":
                output, tool_count = self._run_ooda(
                    llm=llm,
                    tools=tools,
                    system_prompt=system_prompt,
                    prompt=prompt,
                    span_id=span_id,
                    subagent_type=subagent_type,
                    max_cycles=agent_config.max_cycles,
                )
            elif agent_config.loop_type == "direct":
                output, tool_count = self._run_direct(
                    llm=llm,
                    system_prompt=system_prompt,
                    prompt=prompt,
                )
            else:  # react (default)
                output, tool_count = self._run_react(
                    agent=sub_context.agent,
                    llm=llm,
                    system_prompt=system_prompt,
                    prompt=prompt,
                    span_id=span_id,
                    subagent_type=subagent_type,
                    recursion_limit=recursion_limit or agent_config.max_recursion,
                )

        except Exception as e:
            logger.error(f"Subagent execution failed: {e}", exc_info=True)
            raise LoopExecutionError(subagent_type, str(e)) from e

        # 4. 结束 span
        self.span_manager.end_span(
            span_id, subagent_type, tool_count, start_time, output
        )

        # 5. 保存 session
        sub_context.session_store.save_turn(
            subagent_type,
            prompt,
            output,
            []
        )

        return output or "(subagent returned no text)"

    def _run_react(
        self,
        agent: Any,
        llm: Any,
        system_prompt: str,
        prompt: str,
        span_id: str,
        subagent_type: str,
        recursion_limit: int,
    ) -> tuple[str, int]:
        """执行 ReAct 循环"""
        return self.react_loop.run(
            llm=llm,
            tools=[],  # tools 已经绑定到 agent
            system_prompt=system_prompt,
            user_prompt=prompt,
            span_id=span_id,
            subagent_type=subagent_type,
            agent=agent,
            recursion_limit=recursion_limit,
        )

    def _run_ooda(
        self,
        llm: Any,
        tools: list,
        system_prompt: str,
        prompt: str,
        span_id: str,
        subagent_type: str,
        max_cycles: int,
    ) -> tuple[str, int]:
        """执行 OODA 循环"""
        return self.ooda_loop.run(
            llm=llm,
            tools=tools,
            system_prompt=system_prompt,
            user_prompt=prompt,
            span_id=span_id,
            subagent_type=subagent_type,
            max_cycles=max_cycles,
        )

    def _run_direct(
        self,
        llm: Any,
        system_prompt: str,
        prompt: str,
    ) -> tuple[str, int]:
        """直接调用 LLM（无工具）"""
        result = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=prompt)
        ])
        output = result.content.strip()
        return output, 0


# 全局运行器实例
runner = SubagentRunner()


def run_subagent_with_context(
    sub_context: Any,
    description: str,
    prompt: str,
    recursion_limit: int = 100
) -> str:
    """
    使用 SubagentContext 运行 Subagent（兼容旧接口）

    Args:
        sub_context: SubagentContext 实例
        description: 任务描述
        prompt: 用户输入
        recursion_limit: 递归限制

    Returns:
        Subagent 输出
    """
    return runner.run(sub_context, description, prompt, recursion_limit)
