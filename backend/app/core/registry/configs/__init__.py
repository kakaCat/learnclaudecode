"""
Agent 配置注册

自动注册所有 Agent 配置到全局注册表
"""
from .basic_agents import (
    ExploreAgentConfig,
    GeneralPurposeAgentConfig,
    PlanAgentConfig,
    CodingAgentConfig,
    ReflectAgentConfig,
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
        # 基础 Agent
        ExploreAgentConfig(),
        GeneralPurposeAgentConfig(),
        PlanAgentConfig(),
        CodingAgentConfig(),
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
    "ExploreAgentConfig",
    "GeneralPurposeAgentConfig",
    "PlanAgentConfig",
    "CodingAgentConfig",
    "ReflectAgentConfig",
    "ReflexionAgentConfig",
    "OODAAgentConfig",
    "SearchSubagentConfig",
    "IntentRecognitionAgentConfig",
    "ClarificationAgentConfig",
    "CDPBrowserAgentConfig",
    "ToolRepairAgentConfig",
    "MemoryManagerAgentConfig",
    "register_all_agents",
]
