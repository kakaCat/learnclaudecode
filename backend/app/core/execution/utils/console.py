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

    # ========== MainAgent 可观测性方法 ==========

    def main_agent_start(self, prompt: str, history_length: int = 0) -> None:
        """MainAgent 开始执行"""
        if self.enabled:
            print(f"\n{'='*60}")
            print(f"🤖 MainAgent 开始执行")
            print(f"📝 输入: {prompt[:100]}{'...' if len(prompt) > 100 else ''}")
            if history_length > 0:
                print(f"📚 历史: {history_length} 条消息")
            print(f"{'='*60}\n")

    def main_agent_llm_call(self, step: int, content: str, tool_calls: list) -> None:
        """MainAgent LLM 调用"""
        if self.enabled:
            print(f"\n💭 Step {step}: LLM 思考")
            if content:
                preview = content[:200]
                print(f"   {preview}{'...' if len(content) > 200 else ''}")
            if tool_calls:
                print(f"   🔧 准备调用 {len(tool_calls)} 个工具:")
                for tc in tool_calls:
                    tool_name = tc.get('name', 'unknown')
                    args_keys = list(tc.get('args', {}).keys())
                    print(f"      - {tool_name}({args_keys})")

    def main_agent_tool_call(
        self,
        step: int,
        tool_name: str,
        result: str,
        duration_ms: Optional[int] = None
    ) -> None:
        """MainAgent 工具调用"""
        if self.enabled:
            print(f"\n🔨 Step {step}: 工具执行")
            print(f"   工具: {tool_name}")
            if duration_ms is not None:
                print(f"   耗时: {duration_ms}ms")
            preview = result[:150]
            print(f"   结果: {preview}{'...' if len(result) > 150 else ''}")

    def main_agent_subagent_call(
        self,
        step: int,
        subagent_type: str,
        description: str,
        duration_ms: Optional[int] = None,
        tool_count: Optional[int] = None
    ) -> None:
        """MainAgent 调用 Subagent"""
        if self.enabled:
            print(f"\n🤝 Step {step}: 调用 Subagent")
            print(f"   类型: {subagent_type}")
            desc_preview = description[:100]
            print(f"   任务: {desc_preview}{'...' if len(description) > 100 else ''}")
            if duration_ms is not None:
                print(f"   耗时: {duration_ms}ms")
            if tool_count is not None:
                print(f"   工具调用: {tool_count} 次")

    def main_agent_end(self, output: str, metrics: dict) -> None:
        """MainAgent 执行完成"""
        if self.enabled:
            print(f"\n{'='*60}")
            print(f"✅ MainAgent 执行完成")
            print(f"📊 统计:")
            print(f"   - 总步数: {metrics.get('total_steps', 0)}")
            print(f"   - LLM调用: {metrics.get('llm_calls', 0)}")
            print(f"   - 工具调用: {metrics.get('tool_calls', 0)}")
            print(f"   - Subagent: {metrics.get('subagent_calls', 0)}")
            print(f"   - 耗时: {metrics.get('duration_ms', 0)}ms")

            # Token 和成本统计
            if metrics.get('total_tokens', 0) > 0:
                print(f"💰 Token & 成本:")
                print(f"   - 输入 tokens: {metrics.get('input_tokens', 0):,}")
                print(f"   - 输出 tokens: {metrics.get('output_tokens', 0):,}")
                print(f"   - 总 tokens: {metrics.get('total_tokens', 0):,}")
                print(f"   - 总成本: ${metrics.get('total_cost', 0):.6f}")

            preview = output[:200]
            print(f"📤 输出: {preview}{'...' if len(output) > 200 else ''}")
            print(f"{'='*60}\n")


# 全局实例
console = ConsoleLogger()
