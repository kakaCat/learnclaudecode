"""
Memory 模块 - 管理对话记忆和压缩

组织结构：
- history.py - 对话历史管理（ConversationHistory）
- strategies.py - 压缩策略（Strategy Pattern）
- compaction.py - 压缩算法实现
- llm_invoker.py - LLM 调用封装
- guard.py - 已废弃，使用 context.OverflowGuard
"""

from backend.app.memory.history import ConversationHistory
from backend.app.memory.compaction_strategies import (
    CompactionStrategy,
    MicroCompactionStrategy,
    AutoCompactionStrategy,
    ManualCompactionStrategy
)
from backend.app.memory.compaction import (
    estimate_tokens,
    micro_compact,
    auto_compact
)

# 向后兼容：ContextGuard 已移到 context.OverflowGuard
from backend.app.memory.guard import ContextGuard

__all__ = [
    # Conversation History
    "ConversationHistory",

    # Strategies
    "CompactionStrategy",
    "MicroCompactionStrategy",
    "AutoCompactionStrategy",
    "ManualCompactionStrategy",

    # Compaction
    "estimate_tokens",
    "micro_compact",
    "auto_compact",

    # Deprecated (for backward compatibility)
    "ContextGuard",
]
