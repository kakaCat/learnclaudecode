"""
Agent 配置注册

自动注册所有 Agent 配置到全局注册表

配置文件按设计模式组织：
- direct_agents.py - Direct 模式（单次调用，无循环）
- react_agents.py - ReAct 模式（推理+行动循环）
- ooda_agents.py - OODA 模式（观察-定向-决策-行动循环）
- special_agents.py - 特殊用途 Agent
"""
from .direct_agents import PlanAgentConfig, ReflectAgentConfig
from .react_agents import (
    ExploreAgentConfig,
    GeneralPurposeAgentConfig,
    CodingAgentConfig,
)
from .ooda_agents import (
    ReflexionAgentConfig,
)
from .special_agents import (
    OODAAgentConfig,
    SearchSubagentConfig,
    IntentRecognitionAgentConfig,
    ClarificationAgentConfig,
    CDPBrowserAgentConfig,
    ToolRepairAgentConfig,
    MemoryManagerAgentConfig,
)
from ..registry import registry


def register_all_agents() -> None:
    """注册所有内置 Agent 配置"""
    configs = [
        # Direct 模式 - 单次调用
        PlanAgentConfig(),

        # ReAct 模式 - 推理+行动循环
        ExploreAgentConfig(),
        GeneralPurposeAgentConfig(),
        CodingAgentConfig(),

        # OODA 模式 - 观察-定向-决策-行动循环
        ReflectAgentConfig(),
        ReflexionAgentConfig(),

        # 特殊用途 Agent
        OODAAgentConfig(),
        SearchSubagentConfig(),
        IntentRecognitionAgentConfig(),
        ClarificationAgentConfig(),
        CDPBrowserAgentConfig(),
        ToolRepairAgentConfig(),
        MemoryManagerAgentConfig(),
    ]

    registry.register_batch(configs)


# 模块导入时自动注册
register_all_agents()


__all__ = [
    # Direct 模式
    "PlanAgentConfig",

    # ReAct 模式
    "ExploreAgentConfig",
    "GeneralPurposeAgentConfig",
    "CodingAgentConfig",

    # OODA 模式
    "ReflectAgentConfig",
    "ReflexionAgentConfig",

    # 特殊用途
    "OODAAgentConfig",
    "SearchSubagentConfig",
    "IntentRecognitionAgentConfig",
    "ClarificationAgentConfig",
    "CDPBrowserAgentConfig",
    "ToolRepairAgentConfig",
    "MemoryManagerAgentConfig",

    "register_all_agents",
]
