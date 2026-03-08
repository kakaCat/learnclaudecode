"""
Context 模块 - 应用上下文管理

组织结构：
- context.py - 应用上下文（AgentContext，类似 Spring ApplicationContext）
  管理：LLM、Tools、Memory、Session、Tracer
- tracer.py - 结构化追踪日志组件
- overflow_guard.py - 上下文溢出保护（OverflowGuard）
"""

from backend.app.context.context import AgentContext
from backend.app.context.tracer import Tracer
from backend.app.context.overflow_guard import OverflowGuard

__all__ = [
    "AgentContext",
    "Tracer",
    "OverflowGuard",
]

