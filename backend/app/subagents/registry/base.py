"""
Agent 配置基类
"""
from dataclasses import dataclass, field
from typing import List, Optional
from abc import ABC, abstractmethod

from ..exceptions import ConfigValidationError


@dataclass
class AgentConfig(ABC):
    """Agent 配置基类"""

    name: str
    """Agent 类型名称"""

    description: str
    """Agent 功能描述"""

    tools: List[str]
    """允许使用的工具列表（"*" 表示所有工具）"""

    prompt: str
    """System prompt"""

    loop_type: str = "react"
    """执行循环类型: "react" | "ooda" | "direct" """

    # 可选配置
    max_recursion: int = 100
    """ReAct 循环最大递归深度"""

    max_cycles: int = 6
    """OODA 循环最大迭代次数"""

    enable_memory: bool = True
    """是否启用 memory 工具"""

    metadata: dict = field(default_factory=dict)
    """额外的元数据"""

    def validate(self) -> None:
        """
        验证配置有效性

        Raises:
            ConfigValidationError: 配置无效时抛出
        """
        if not self.name:
            raise ConfigValidationError("name", "Agent name cannot be empty")

        if not self.description:
            raise ConfigValidationError("description", "Description cannot be empty")

        if not self.tools:
            raise ConfigValidationError("tools", "Tools list cannot be empty")

        if self.loop_type not in ["react", "ooda", "direct"]:
            raise ConfigValidationError(
                "loop_type",
                f"Invalid loop_type '{self.loop_type}', must be 'react', 'ooda', or 'direct'"
            )

        if self.max_recursion <= 0:
            raise ConfigValidationError("max_recursion", "Must be positive")

        if self.max_cycles <= 0:
            raise ConfigValidationError("max_cycles", "Must be positive")

        # 子类可以覆盖此方法添加额外验证
        self._validate_custom()

    def _validate_custom(self) -> None:
        """子类可覆盖的自定义验证"""
        pass

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "name": self.name,
            "description": self.description,
            "tools": self.tools,
            "prompt": self.prompt,
            "loop_type": self.loop_type,
            "max_recursion": self.max_recursion,
            "max_cycles": self.max_cycles,
            "enable_memory": self.enable_memory,
            "metadata": self.metadata,
        }

    def __repr__(self) -> str:
        return f"<AgentConfig name={self.name} loop_type={self.loop_type}>"
