"""
可观测性收集器 - MainAgent 执行追踪

职责：
1. 收集 MainAgent 执行过程中的所有事件
2. 统计执行指标（步数、工具调用、耗时等）
3. 输出到 Console 和 Tracer
"""
import time
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

from backend.app.core.guards.tracer import Tracer
from backend.app.core.execution.utils.console import console


@dataclass
class ExecutionMetrics:
    """执行指标"""
    total_steps: int = 0
    llm_calls: int = 0
    tool_calls: int = 0
    subagent_calls: int = 0
    start_time: float = 0.0
    end_time: float = 0.0

    # Token 统计
    total_input_tokens: int = 0
    total_output_tokens: int = 0

    # 成本统计（美元）
    total_cost: float = 0.0

    @property
    def duration_ms(self) -> int:
        """执行耗时（毫秒）"""
        if self.end_time > 0:
            return round((self.end_time - self.start_time) * 1000)
        return 0

    @property
    def total_tokens(self) -> int:
        """总 token 数"""
        return self.total_input_tokens + self.total_output_tokens


@dataclass
class StepInfo:
    """单步执行信息"""
    step: int
    type: str  # llm_call, tool_call, subagent_call
    timestamp: float
    data: Dict[str, Any] = field(default_factory=dict)


class ObservabilityCollector:
    """
    可观测性收集器

    收集 MainAgent 执行过程中的所有事件，并输出到：
    1. Console - 实时控制台输出（开发调试）
    2. Tracer - JSONL 日志（持久化分析）
    """

    def __init__(self, enable_console: bool = True, enable_tracer: bool = True):
        """
        初始化收集器

        Args:
            enable_console: 是否启用控制台输出
            enable_tracer: 是否启用 Tracer 日志
        """
        self.enable_console = enable_console
        self.enable_tracer = enable_tracer
        self.tracer = Tracer()

        # 当前执行状态
        self.run_id: Optional[str] = None
        self.metrics = ExecutionMetrics()
        self.steps: List[StepInfo] = []

    def start(self, prompt: str, history_length: int = 0) -> str:
        """
        开始追踪

        Args:
            prompt: 用户输入
            history_length: 历史消息数量

        Returns:
            run_id
        """
        # 生成 run_id
        self.run_id = self.tracer.new_run_id()
        self.tracer.set_run_id(self.run_id)

        # 初始化指标
        self.metrics = ExecutionMetrics(start_time=time.time())
        self.steps = []

        # Console 输出
        if self.enable_console:
            console.main_agent_start(prompt, history_length)

        # Tracer 日志
        if self.enable_tracer:
            self.tracer.emit(
                "main_agent.start",
                prompt=prompt[:200],  # 限制长度
                history_length=history_length
            )

        return self.run_id

    def on_llm_call(
        self,
        step: int,
        content: str,
        tool_calls: Optional[List[Dict]] = None,
        input_tokens: int = 0,
        output_tokens: int = 0
    ) -> None:
        """
        记录 LLM 调用

        Args:
            step: 步骤编号
            content: LLM 输出内容
            tool_calls: 工具调用列表
            input_tokens: 输入 token 数
            output_tokens: 输出 token 数
        """
        self.metrics.total_steps = max(self.metrics.total_steps, step)
        self.metrics.llm_calls += 1

        # 更新 token 统计
        self.metrics.total_input_tokens += input_tokens
        self.metrics.total_output_tokens += output_tokens

        # 计算成本（DeepSeek 价格：输入 $0.14/M tokens，输出 $0.28/M tokens）
        input_cost = (input_tokens / 1_000_000) * 0.14
        output_cost = (output_tokens / 1_000_000) * 0.28
        self.metrics.total_cost += input_cost + output_cost

        # 记录步骤
        step_info = StepInfo(
            step=step,
            type="llm_call",
            timestamp=time.time(),
            data={
                "content": content[:200] if content else "",
                "tool_calls": tool_calls or [],
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost": round(input_cost + output_cost, 6)
            }
        )
        self.steps.append(step_info)

        # Console 输出
        if self.enable_console:
            console.main_agent_llm_call(step, content, tool_calls or [])

        # Tracer 日志
        if self.enable_tracer:
            self.tracer.emit(
                "main_agent.llm_call",
                step=step,
                content=content[:200] if content else "",
                tool_calls=[
                    {"name": tc.get("name"), "args": list(tc.get("args", {}).keys())}
                    for tc in (tool_calls or [])
                ],
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost=round(input_cost + output_cost, 6)
            )

    def on_tool_call(
        self,
        step: int,
        tool_name: str,
        tool_args: Dict[str, Any],
        result: str,
        duration_ms: Optional[int] = None
    ) -> None:
        """
        记录工具调用

        Args:
            step: 步骤编号
            tool_name: 工具名称
            tool_args: 工具参数
            result: 执行结果
            duration_ms: 执行耗时（毫秒）
        """
        self.metrics.total_steps = max(self.metrics.total_steps, step)
        self.metrics.tool_calls += 1

        # 记录步骤
        step_info = StepInfo(
            step=step,
            type="tool_call",
            timestamp=time.time(),
            data={
                "tool": tool_name,
                "args": tool_args,
                "result": result[:200],
                "duration_ms": duration_ms
            }
        )
        self.steps.append(step_info)

        # Console 输出
        if self.enable_console:
            console.main_agent_tool_call(step, tool_name, result, duration_ms)

        # Tracer 日志
        if self.enable_tracer:
            self.tracer.emit(
                "main_agent.tool_call",
                step=step,
                tool=tool_name,
                args=list(tool_args.keys()),
                result=result[:200],
                duration_ms=duration_ms
            )

    def on_subagent_call(
        self,
        step: int,
        subagent_type: str,
        description: str,
        span_id: str,
        duration_ms: Optional[int] = None,
        tool_count: Optional[int] = None
    ) -> None:
        """
        记录 Subagent 调用

        Args:
            step: 步骤编号
            subagent_type: Subagent 类型
            description: 任务描述
            span_id: Subagent span ID
            duration_ms: 执行耗时（毫秒）
            tool_count: 工具调用次数
        """
        self.metrics.total_steps = max(self.metrics.total_steps, step)
        self.metrics.subagent_calls += 1

        # 记录步骤
        step_info = StepInfo(
            step=step,
            type="subagent_call",
            timestamp=time.time(),
            data={
                "subagent_type": subagent_type,
                "description": description,
                "span_id": span_id,
                "duration_ms": duration_ms,
                "tool_count": tool_count
            }
        )
        self.steps.append(step_info)

        # Console 输出
        if self.enable_console:
            console.main_agent_subagent_call(
                step, subagent_type, description, duration_ms, tool_count
            )

        # Tracer 日志
        if self.enable_tracer:
            self.tracer.emit(
                "main_agent.subagent_call",
                step=step,
                subagent_type=subagent_type,
                description=description[:100],
                span_id=span_id,
                duration_ms=duration_ms,
                tool_count=tool_count
            )

    def end(self, output: str, tool_calls: int = 0, subagent_calls: int = 0) -> Dict[str, Any]:
        """
        结束追踪

        Args:
            output: 最终输出
            tool_calls: 工具调用次数
            subagent_calls: Subagent 调用次数

        Returns:
            执行指标字典
        """
        self.metrics.end_time = time.time()

        # 更新指标
        if tool_calls > 0:
            self.metrics.tool_calls = tool_calls
        if subagent_calls > 0:
            self.metrics.subagent_calls = subagent_calls

        # 构建指标字典
        metrics_dict = {
            "total_steps": self.metrics.total_steps,
            "llm_calls": self.metrics.llm_calls,
            "tool_calls": self.metrics.tool_calls,
            "subagent_calls": self.metrics.subagent_calls,
            "duration_ms": self.metrics.duration_ms,
            "total_tokens": self.metrics.total_tokens,
            "input_tokens": self.metrics.total_input_tokens,
            "output_tokens": self.metrics.total_output_tokens,
            "total_cost": round(self.metrics.total_cost, 6)
        }

        # Console 输出
        if self.enable_console:
            console.main_agent_end(output, metrics_dict)

        # Tracer 日志
        if self.enable_tracer:
            self.tracer.emit(
                "main_agent.end",
                output=output[:200],
                output_length=len(output),
                **metrics_dict
            )

        return metrics_dict

    def on_error(self, error: str) -> None:
        """
        记录错误

        Args:
            error: 错误信息
        """
        # Console 输出
        if self.enable_console:
            console.red(f"❌ MainAgent 执行出错: {error}")

        # Tracer 日志
        if self.enable_tracer:
            self.tracer.emit(
                "main_agent.error",
                error_type=type(error).__name__,
                error_message=str(error)
            )
