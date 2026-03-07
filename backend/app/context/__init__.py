"""
Context 模块

组织结构：
- context.py - 上下文保护和压缩策略
- compaction.py - 三层压缩流水线
"""

from backend.app.context.context import (
    ContextGuard,
    CompactionStrategy,
    MicroCompactionStrategy,
    AutoCompactionStrategy,
    ManualCompactionStrategy
)

from backend.app.context.compaction import (
    estimate_tokens,
    micro_compact,
    auto_compact
)

__all__ = [
    "ContextGuard",
    "CompactionStrategy",
    "MicroCompactionStrategy",
    "AutoCompactionStrategy",
    "ManualCompactionStrategy",
    "estimate_tokens",
    "micro_compact",
    "auto_compact",
]

