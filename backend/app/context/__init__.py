"""
Context 模块 - 应用上下文管理

组织结构：
- base.py - 抽象基类（BaseAgentContext）定义统一接口
- context.py - 具体实现（AgentContext）包含默认加载策略
  管理：LLM、Tools、Memory、Session、Tracer、压缩策略、记忆召回
- tracer.py - 结构化追踪日志组件
- overflow_guard.py - 上下文溢出保护（OverflowGuard）
"""

from backend.app.context.base import BaseAgentContext
from backend.app.context.context import AgentContext
from backend.app.context.tracer import Tracer
from backend.app.context.overflow_guard import OverflowGuard

__all__ = [
    "BaseAgentContext",
    "AgentContext",
    "Tracer",
    "OverflowGuard",
]
