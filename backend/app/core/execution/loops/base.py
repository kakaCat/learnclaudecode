"""
执行循环抽象基类
"""
from abc import ABC, abstractmethod
from typing import Tuple, Any
import logging

from backend.app.core.execution.config import CONFIG
from backend.app.core.execution.exceptions import LoopExecutionError

logger = logging.getLogger(__name__)


class BaseLoop(ABC):
    """
    执行循环抽象基类

    所有执行循环（ReAct, OODA 等）的基类，定义统一接口。
    """

    def __init__(self):
        self.config = CONFIG

    @abstractmethod
    def run(
        self,
        llm: Any,
        tools: list,
        system_prompt: str,
        user_prompt: str,
        span_id: str,
        subagent_type: str,
    ) -> Tuple[str, int]:
        """
        执行循环

        Args:
            llm: LLM 实例
            tools: 工具列表
            system_prompt: 系统提示词
            user_prompt: 用户输入
            span_id: Tracer span ID
            subagent_type: Subagent 类型名称

        Returns:
            (output, tool_count) - 输出文本和工具调用次数

        Raises:
            LoopExecutionError: 执行失败时抛出
        """
        pass

    def _validate_inputs(
        self,
        llm: Any,
        tools: list,
        system_prompt: str,
        user_prompt: str
    ) -> None:
        """
        验证输入参数

        Args:
            llm: LLM 实例
            tools: 工具列表
            system_prompt: 系统提示词
            user_prompt: 用户输入

        Raises:
            LoopExecutionError: 参数无效时抛出
        """
        if llm is None:
            raise LoopExecutionError(
                self.__class__.__name__,
                "LLM instance cannot be None"
            )

        if not system_prompt:
            raise LoopExecutionError(
                self.__class__.__name__,
                "System prompt cannot be empty"
            )

        if not user_prompt:
            raise LoopExecutionError(
                self.__class__.__name__,
                "User prompt cannot be empty"
            )

        if tools is None:
            raise LoopExecutionError(
                self.__class__.__name__,
                "Tools list cannot be None (use empty list for no tools)"
            )

    def _log_start(self, subagent_type: str, user_prompt: str) -> None:
        """记录循环开始"""
        logger.info(
            f"[{self.__class__.__name__}] Starting loop for {subagent_type}",
            extra={"prompt_length": len(user_prompt)}
        )

    def _log_end(self, subagent_type: str, tool_count: int, output_length: int) -> None:
        """记录循环结束"""
        logger.info(
            f"[{self.__class__.__name__}] Loop completed for {subagent_type}",
            extra={"tool_count": tool_count, "output_length": output_length}
        )

    def _handle_error(self, error: Exception, subagent_type: str) -> None:
        """
        处理循环执行错误

        Args:
            error: 原始异常
            subagent_type: Subagent 类型

        Raises:
            LoopExecutionError: 包装后的异常
        """
        logger.error(
            f"[{self.__class__.__name__}] Loop failed for {subagent_type}: {error}",
            exc_info=True
        )
        raise LoopExecutionError(
            self.__class__.__name__,
            f"Execution failed: {error}"
        ) from error
