"""
Registry 模块导出
"""
from .base import AgentConfig
from .registry import AgentRegistry, registry

# 导入配置会自动触发注册
from .configs import (
    ExploreAgentConfig,
    GeneralPurposeAgentConfig,
    PlanAgentConfig,
    CodingAgentConfig,
    ReflectAgentConfig,
    ReflexionAgentConfig,
    OODAAgentConfig,
    SearchSubagentConfig,
    IntentRecognitionAgentConfig,
    ClarificationAgentConfig,
    CDPBrowserAgentConfig,
    ToolRepairAgentConfig,
    register_all_agents,
)


def get_descriptions() -> str:
    """
    获取所有 Subagent 类型的描述

    Returns:
        格式化的描述字符串
    """
    return registry.get_descriptions()


__all__ = [
    # 基类
    "AgentConfig",

    # 注册表
    "AgentRegistry",
    "registry",

    # 配置类
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

    # 工具函数
    "register_all_agents",
    "get_descriptions",
]
