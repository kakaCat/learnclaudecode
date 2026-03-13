"""
OODA Agent 配置 - 观察-定向-决策-行动循环

设计模式：OODA (Observe-Orient-Decide-Act)
- 使用 OODA 循环
- 支持工具调用
- 迭代式探索和决策
- 适合：信息搜索、反思改进、质量审查等需要多轮迭代的任务
"""
from dataclasses import dataclass
from backend.app.core.registry.base import AgentConfig


@dataclass
class ReflexionAgentConfig(AgentConfig):
    """
    Reflexion Agent - 反思改进

    设计模式：OODA (两阶段)
    用途：收集上下文 → 批评初始响应 → 产生改进版本
    """

    def __init__(self):
        super().__init__(
            name="Reflexion",
            description="Reflexion agent: two-phase Responder+Revisor. Gathers context via tools, critiques initial response, then produces improved version",
            tools=[
                "bash",
                "read_file",
                "glob",
                "grep",
                "list_dir",
                "memory_search",
                "memory_write"
            ],
            prompt=(
                "You are a Reflexion agent using OODA loop with two phases.\n\n"
                "OODA 循环流程：\n"
                "- **Observe（观察）**: 用 memory_search 召回改进模式，收集上下文信息\n"
                "- **Orient（定向）**: Phase 1 - Responder，分析初始响应的缺失和冗余\n"
                "- **Decide（决策）**: Phase 2 - Revisor，决定如何改进\n"
                "- **Act（行动）**: 产生改进版本，用 memory_write 保存有效模式\n\n"
                'Return ONLY valid JSON: {"critique": "...", "revised": "..."}'
            ),
            loop_type="ooda",
            max_cycles=20,
            enable_memory=True,
        )
