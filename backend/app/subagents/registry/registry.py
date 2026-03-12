"""
Agent 注册表（单例模式）
"""
from typing import Dict, List, Optional
import logging

from .base import AgentConfig
from ..exceptions import AgentNotFoundError

logger = logging.getLogger(__name__)


class AgentRegistry:
    """
    Agent 注册表（单例模式）

    管理所有 Agent 类型的配置，支持动态注册和查询。

    Example:
        >>> registry = AgentRegistry()
        >>> registry.register(ExploreAgentConfig())
        >>> config = registry.get("Explore")
        >>> print(config.description)
    """

    _instance: Optional['AgentRegistry'] = None
    _agents: Dict[str, AgentConfig] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._agents = {}
        return cls._instance

    def register(self, config: AgentConfig) -> None:
        """
        注册 Agent 配置

        Args:
            config: Agent 配置对象

        Raises:
            ConfigValidationError: 配置验证失败
        """
        config.validate()
        self._agents[config.name] = config
        logger.info(f"Registered agent: {config.name} (loop_type={config.loop_type})")

    def register_batch(self, configs: List[AgentConfig]) -> None:
        """
        批量注册 Agent 配置

        Args:
            configs: Agent 配置列表
        """
        for config in configs:
            self.register(config)

    def get(self, name: str) -> AgentConfig:
        """
        获取 Agent 配置

        Args:
            name: Agent 类型名称

        Returns:
            Agent 配置对象

        Raises:
            AgentNotFoundError: Agent 类型不存在
        """
        if name not in self._agents:
            raise AgentNotFoundError(name)
        return self._agents[name]

    def has(self, name: str) -> bool:
        """
        检查 Agent 是否存在

        Args:
            name: Agent 类型名称

        Returns:
            是否存在
        """
        return name in self._agents

    def list_agents(self) -> List[str]:
        """
        列出所有 Agent 类型

        Returns:
            Agent 类型名称列表
        """
        return list(self._agents.keys())

    def get_descriptions(self) -> str:
        """
        获取所有 Agent 的描述信息

        Returns:
            格式化的描述字符串
        """
        return "\n".join(
            f"- {name}: {cfg.description}"
            for name, cfg in self._agents.items()
        )

    def clear(self) -> None:
        """清空注册表（主要用于测试）"""
        self._agents.clear()
        logger.warning("Agent registry cleared")

    def __len__(self) -> int:
        """返回已注册的 Agent 数量"""
        return len(self._agents)

    def __contains__(self, name: str) -> bool:
        """支持 'in' 操作符"""
        return name in self._agents

    def __repr__(self) -> str:
        return f"<AgentRegistry agents={len(self._agents)}>"


# 全局注册表实例
registry = AgentRegistry()
