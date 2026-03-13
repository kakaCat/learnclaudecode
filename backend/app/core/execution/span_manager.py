"""
Span 管理器

管理 Tracer span 的创建和结束
"""
import time
import logging
from typing import Tuple

from backend.app.core.guards.tracer import Tracer
from backend.app.core.execution.utils.console import console

logger = logging.getLogger(__name__)
tracer = Tracer()


class SpanManager:
    """
    Span 管理器

    负责创建和结束 tracer span，记录执行信息。
    """

    @staticmethod
    def start_span(
        subagent_type: str,
        description: str,
        tools: list
    ) -> Tuple[str, float]:
        """
        开始一个新的 span

        Args:
            subagent_type: Subagent 类型
            description: 任务描述
            tools: 工具列表

        Returns:
            (span_id, start_time)
        """
        tool_names = [t.name for t in tools] if tools else []

        # 控制台输出
        console.subagent_start(subagent_type, description, tools)

        # 创建 span
        span_id = tracer.new_run_id()
        start_time = time.time()

        # 发送 tracer 事件
        tracer.emit(
            "subagent.start",
            span_id=span_id,
            agent_type=subagent_type,
            description=description,
            tools=tool_names
        )

        logger.info(
            f"Started span for {subagent_type}",
            extra={
                "span_id": span_id,
                "description": description,
                "tool_count": len(tool_names)
            }
        )

        return span_id, start_time

    @staticmethod
    def end_span(
        span_id: str,
        subagent_type: str,
        tool_count: int,
        start_time: float,
        output: str
    ) -> None:
        """
        结束一个 span

        Args:
            span_id: Span ID
            subagent_type: Subagent 类型
            tool_count: 工具调用次数
            start_time: 开始时间
            output: 输出内容
        """
        elapsed = time.time() - start_time
        duration_ms = round(elapsed * 1000)

        # 控制台输出
        console.subagent_end(subagent_type, tool_count, elapsed)

        # 发送 tracer 事件
        tracer.emit(
            "subagent.end",
            span_id=span_id,
            agent_type=subagent_type,
            tool_count=tool_count,
            duration_ms=duration_ms,
            output=output[:300]  # 只记录前 300 字符
        )

        logger.info(
            f"Ended span for {subagent_type}",
            extra={
                "span_id": span_id,
                "tool_count": tool_count,
                "duration_ms": duration_ms,
                "output_length": len(output)
            }
        )
