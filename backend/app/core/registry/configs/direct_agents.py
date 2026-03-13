"""
Direct Agent 配置 - 直接循环模式

设计模式：Direct Loop (类似 s01_agent_loop.py)
- 使用 while True 直接循环
- 手动检查 tool_calls 决定是否继续
- 不依赖 LangGraph 路由
- 完全控制循环逻辑
"""
from dataclasses import dataclass
from backend.app.core.registry.base import AgentConfig


@dataclass
class ReflectAgentConfig(AgentConfig):
    """
    Reflect Agent - 代码审查

    设计模式：Direct Mode
    用途：审查代码质量，返回 PASS 或 NEEDS_REVISION
    """

    def __init__(self):
        super().__init__(
            name="Reflect",
            description="Reflection agent: reads relevant files to verify correctness, returns verdict PASS|NEEDS_REVISION with missing/superfluous/suggestion",
            tools=[
                "read_file",
                "memory_search",
                "memory_write"
            ],
            prompt=(
                "你是严格的代码审查员。\n\n"
                "审查流程：\n"
                "- 用 read_file 读取相关文件，用 memory_search 召回审查标准\n"
                "- 分析代码质量、识别问题（缺失/冗余/可改进）\n"
                "- 判断 PASS 或 NEEDS_REVISION\n"
                "- 返回 JSON 结果，用 memory_write 保存常见问题模式\n\n"
                "Return ONLY valid JSON with keys:\n"
                "  verdict: 'PASS' or 'NEEDS_REVISION'\n"
                "  missing: list of missing aspects\n"
                "  superfluous: list of unnecessary/redundant parts\n"
                "  suggestion: concise actionable improvement advice (empty string if PASS)\n"
                "No explanation outside the JSON."
            ),
            loop_type="direct",
            max_cycles=10,
            enable_memory=True,
        )


@dataclass
class PlanAgentConfig(AgentConfig):
    """
    Plan Agent - 任务规划

    设计模式：Direct Mode (单次调用)
    用途：规划任务，拆分步骤，不使用工具
    """

    def __init__(self):
        super().__init__(
            name="plan",
            description="Planning agent for task breakdown",
            tools=[],  # 不使用工具
            prompt=(
                "You are a planning agent. "
                "Break down tasks into clear, actionable steps. "
                "Return structured plans without executing them."
            ),
            loop_type="direct",
            max_cycles=1,  # 单次调用
            enable_memory=False,
        )
