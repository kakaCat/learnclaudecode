"""
LangChain Callback Handler - 集成现有的 Tracer 和 Console

使用 LangChain 的 Callbacks 系统自动追踪：
1. LLM 调用（输入、输出、token 使用）
2. 工具调用（工具名、参数、结果、耗时）
3. Agent 行为（决策、动作）
4. Chain 执行流程
"""
import time
from typing import Any, Dict, List, Optional
from uuid import UUID
from langchain_core.callbacks.base import BaseCallbackHandler
from langchain_core.outputs import LLMResult

from backend.app.core.guards.tracer import Tracer
from backend.app.core.execution.utils.console import console
from backend.app.config import DEEPSEEK_MODEL


class ObservabilityCallback(BaseCallbackHandler):
    """
    可观测性 Callback Handler

    集成现有的 Tracer 和 Console 系统，自动追踪所有 LangChain 组件的执行。
    """

    def __init__(
        self,
        agent_type: str = "main_agent",
        enable_console: bool = True,
        enable_tracer: bool = True,
        span_id: Optional[str] = None
    ):
        """
        初始化 Callback Handler

        Args:
            agent_type: Agent 类型（main_agent, subagent, teamagent）
            enable_console: 是否启用控制台输出
            enable_tracer: 是否启用 Tracer 日志
            span_id: Span ID（用于 subagent）
        """
        super().__init__()
        self.agent_type = agent_type
        self.enable_console = enable_console
        self.enable_tracer = enable_tracer
        self.span_id = span_id
        self.tracer = Tracer()

        # 统计指标
        self.llm_calls = 0
        self.tool_calls = 0
        self.subagent_calls = 0  # 添加 subagent 调用统计
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost = 0.0

        # 用于计算耗时
        self._start_times: Dict[UUID, float] = {}

        # 用于追踪工具调用（关联 tool_call_id）
        self._pending_tool_calls: Dict[str, Dict[str, Any]] = {}

    # ==================== LLM 回调 ====================

    def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: List[str],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: List[str] | None = None,
        metadata: Dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        """LLM 开始调用"""
        self._start_times[run_id] = time.time()
        self.llm_calls += 1

        # Console 输出
        if self.enable_console:
            # 直接使用配置文件中的模型名称
            console.gray(f"[{self.agent_type}] LLM call #{self.llm_calls} | model={DEEPSEEK_MODEL}")

        # Tracer 日志
        if self.enable_tracer:
            event_name = f"{self.agent_type}.llm_start"
            self.tracer.emit(
                event_name,
                run_id=str(run_id),
                parent_run_id=str(parent_run_id) if parent_run_id else None,
                model=serialized.get("name"),
                prompt_count=len(prompts),
                span_id=self.span_id
            )

    def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> Any:
        """LLM 调用结束"""
        # 计算耗时
        duration_ms = None
        if run_id in self._start_times:
            duration_ms = round((time.time() - self._start_times[run_id]) * 1000)
            del self._start_times[run_id]

        # 提取 token 使用信息
        llm_output = response.llm_output or {}
        token_usage = llm_output.get("token_usage", {})

        input_tokens = token_usage.get("prompt_tokens", 0)
        output_tokens = token_usage.get("completion_tokens", 0)

        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens

        # 计算成本（假设使用 DeepSeek 价格）
        # Input: $0.27/M tokens, Output: $1.10/M tokens
        cost = (input_tokens * 0.27 / 1_000_000) + (output_tokens * 1.10 / 1_000_000)
        self.total_cost += cost

        # 提取输出内容
        output_text = ""
        if response.generations and response.generations[0]:
            output_text = response.generations[0][0].text

        # Console 输出
        if self.enable_console:
            console.gray(
                f"[{self.agent_type}] LLM end | "
                f"tokens={input_tokens}+{output_tokens} | "
                f"cost=${cost:.6f} | "
                f"duration={duration_ms}ms"
            )

        # Tracer 日志
        if self.enable_tracer:
            event_name = f"{self.agent_type}.llm_end"
            self.tracer.emit(
                event_name,
                run_id=str(run_id),
                parent_run_id=str(parent_run_id) if parent_run_id else None,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
                cost=cost,
                duration_ms=duration_ms,
                output_preview=output_text[:200] if output_text else None,
                span_id=self.span_id
            )

    def on_llm_error(
        self,
        error: Exception,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> Any:
        """LLM 调用出错"""
        # Console 输出
        if self.enable_console:
            console.red(f"[{self.agent_type}] LLM error: {error}")

        # Tracer 日志
        if self.enable_tracer:
            event_name = f"{self.agent_type}.llm_error"
            self.tracer.emit(
                event_name,
                run_id=str(run_id),
                error_type=type(error).__name__,
                error_message=str(error),
                span_id=self.span_id
            )

    # ==================== 工具回调 ====================

    def on_tool_start(
        self,
        serialized: Dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: List[str] | None = None,
        metadata: Dict[str, Any] | None = None,
        inputs: Dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        """工具开始执行"""
        self._start_times[run_id] = time.time()
        self.tool_calls += 1

        tool_name = serialized.get("name", "unknown")

        # 保存待处理的工具调用
        self._pending_tool_calls[str(run_id)] = {
            "tool_name": tool_name,
            "start_time": time.time()
        }

        # Console 输出
        if self.enable_console:
            console.tool_call(self.agent_type, tool_name, inputs or {})

        # Tracer 日志
        if self.enable_tracer:
            event_name = f"{self.agent_type}.tool_start"
            self.tracer.emit(
                event_name,
                run_id=str(run_id),
                parent_run_id=str(parent_run_id) if parent_run_id else None,
                tool=tool_name,
                input_str=input_str[:500] if input_str else None,
                inputs=inputs,
                span_id=self.span_id
            )

    def on_tool_end(
        self,
        output: Any,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> Any:
        """工具执行结束"""
        # 计算耗时
        duration_ms = None
        if run_id in self._start_times:
            duration_ms = round((time.time() - self._start_times[run_id]) * 1000)
            del self._start_times[run_id]

        # 获取工具信息
        tool_info = self._pending_tool_calls.pop(str(run_id), {})
        tool_name = tool_info.get("tool_name", "unknown")

        # 输出结果
        output_str = str(output) if output else ""

        # Console 输出
        if self.enable_console:
            console.tool_result(self.agent_type, output_str)

        # Tracer 日志
        if self.enable_tracer:
            event_name = f"{self.agent_type}.tool_end"
            self.tracer.emit(
                event_name,
                run_id=str(run_id),
                parent_run_id=str(parent_run_id) if parent_run_id else None,
                tool=tool_name,
                output=output_str[:500] if output_str else None,
                duration_ms=duration_ms,
                ok=not output_str.startswith("Error:"),
                span_id=self.span_id
            )

    def on_tool_error(
        self,
        error: Exception,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> Any:
        """工具执行出错"""
        # Console 输出
        if self.enable_console:
            console.red(f"[{self.agent_type}] Tool error: {error}")

        # Tracer 日志
        if self.enable_tracer:
            event_name = f"{self.agent_type}.tool_error"
            self.tracer.emit(
                event_name,
                run_id=str(run_id),
                error_type=type(error).__name__,
                error_message=str(error),
                span_id=self.span_id
            )

    # ==================== Agent 回调 ====================

    def on_agent_action(
        self,
        action,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> Any:
        """Agent 决策动作"""
        # Console 输出
        if self.enable_console:
            tool_name = action.tool
            tool_input = action.tool_input
            console.gray(f"[{self.agent_type}] Agent action: {tool_name}({tool_input})")

        # Tracer 日志
        if self.enable_tracer:
            event_name = f"{self.agent_type}.agent_action"
            self.tracer.emit(
                event_name,
                run_id=str(run_id),
                tool=action.tool,
                tool_input=str(action.tool_input)[:200],
                log=action.log[:200] if hasattr(action, 'log') else None,
                span_id=self.span_id
            )

    def on_agent_finish(
        self,
        finish,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> Any:
        """Agent 完成任务"""
        # Console 输出
        if self.enable_console:
            output = finish.return_values.get("output", "")
            console.gray(f"[{self.agent_type}] Agent finish: {output[:100]}")

        # Tracer 日志
        if self.enable_tracer:
            event_name = f"{self.agent_type}.agent_finish"
            self.tracer.emit(
                event_name,
                run_id=str(run_id),
                output=str(finish.return_values)[:500],
                span_id=self.span_id
            )

    # ==================== Chain 回调 ====================

    def on_chain_start(
        self,
        serialized: Dict[str, Any],
        inputs: Dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: List[str] | None = None,
        metadata: Dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        """Chain 开始执行"""
        self._start_times[run_id] = time.time()

        # Tracer 日志
        if self.enable_tracer:
            event_name = f"{self.agent_type}.chain_start"
            # 处理 serialized 可能为 None 的情况
            chain_type = "unknown"
            if serialized and isinstance(serialized, dict):
                chain_type = serialized.get("name", "unknown")

            self.tracer.emit(
                event_name,
                run_id=str(run_id),
                parent_run_id=str(parent_run_id) if parent_run_id else None,
                chain_type=chain_type,
                span_id=self.span_id
            )

    def on_chain_end(
        self,
        outputs: Dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> Any:
        """Chain 执行结束"""
        # 计算耗时
        duration_ms = None
        if run_id in self._start_times:
            duration_ms = round((time.time() - self._start_times[run_id]) * 1000)
            del self._start_times[run_id]

        # Tracer 日志
        if self.enable_tracer:
            event_name = f"{self.agent_type}.chain_end"
            self.tracer.emit(
                event_name,
                run_id=str(run_id),
                parent_run_id=str(parent_run_id) if parent_run_id else None,
                duration_ms=duration_ms,
                span_id=self.span_id
            )

    # ==================== 统计方法 ====================

    def get_metrics(self) -> Dict[str, Any]:
        """获取统计指标"""
        return {
            "llm_calls": self.llm_calls,
            "tool_calls": self.tool_calls,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_input_tokens + self.total_output_tokens,
            "total_cost": self.total_cost
        }
