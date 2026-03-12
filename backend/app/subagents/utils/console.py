"""
控制台输出工具
"""
from enum import Enum
from typing import Optional


class ConsoleColor(Enum):
    """控制台颜色枚举"""
    GRAY = "\033[90m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    RESET = "\033[0m"


class ConsoleLogger:
    """控制台日志输出器"""

    def __init__(self, enabled: bool = True):
        self.enabled = enabled

    def _format(self, message: str, color: Optional[ConsoleColor] = None) -> str:
        """格式化消息"""
        if not color or not self.enabled:
            return message
        return f"{color.value}{message}{ConsoleColor.RESET.value}"

    def gray(self, message: str) -> None:
        """灰色输出（调试信息）"""
        if self.enabled:
            print(self._format(message, ConsoleColor.GRAY))

    def red(self, message: str) -> None:
        """红色输出（错误）"""
        if self.enabled:
            print(self._format(message, ConsoleColor.RED))

    def green(self, message: str) -> None:
        """绿色输出（成功）"""
        if self.enabled:
            print(self._format(message, ConsoleColor.GREEN))

    def yellow(self, message: str) -> None:
        """黄色输出（警告）"""
        if self.enabled:
            print(self._format(message, ConsoleColor.YELLOW))

    def blue(self, message: str) -> None:
        """蓝色输出（信息）"""
        if self.enabled:
            print(self._format(message, ConsoleColor.BLUE))

    def subagent_start(self, agent_type: str, description: str, tools: list) -> None:
        """Subagent 启动日志"""
        tool_names = [t.name for t in tools] if tools else []
        label = tool_names if tool_names else "(none, direct llm)"
        self.gray(f"🤖 [subagent:{agent_type}] {description}")
        self.gray(f"   tools: {label}")

    def subagent_end(self, agent_type: str, tool_count: int, elapsed: float) -> None:
        """Subagent 完成日志"""
        self.gray(f"   ✅ [{agent_type}] done ({tool_count} tools, {elapsed:.1f}s)")

    def tool_call(self, agent_type: str, tool_name: str, args: dict) -> None:
        """工具调用日志"""
        args_str = str(args)[:120]
        self.gray(f"   🔀 [{agent_type}] → {tool_name}({args_str})")

    def tool_result(self, agent_type: str, result: str) -> None:
        """工具结果日志"""
        preview = result[:120]
        self.gray(f"   📥 [{agent_type}] ← {preview}")

    def compression(self, agent_type: str, before: int, after: int,
                   before_tokens: int, after_tokens: int) -> None:
        """压缩日志"""
        self.gray(f"   🗜️ [{agent_type}] 压缩前: {before} 消息, ~{before_tokens} tokens")
        self.gray(f"   ✅ [{agent_type}] 压缩后: {after} 消息, ~{after_tokens} tokens")

    def ooda_cycle(self, cycle: int, max_cycles: int) -> None:
        """OODA 循环日志"""
        self.gray(f"   🔄 [OODA] cycle {cycle}/{max_cycles}")

    def ooda_decision(self, choice: str, confidence: float) -> None:
        """OODA 决策日志"""
        self.gray(f"   🎯 [OODA] decision={choice}, confidence={confidence:.2f}")

    def fallback(self, agent_type: str, output: str) -> None:
        """Fallback 日志"""
        preview = output[:80]
        self.gray(f"   🔁 [{agent_type}] fallback: {preview}")


# 全局实例
console = ConsoleLogger()
