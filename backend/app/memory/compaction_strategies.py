"""Compaction strategies for context management"""
from abc import ABC, abstractmethod
from typing import List, Dict
from langchain_openai import ChatOpenAI


class CompactionStrategy(ABC):
    """压缩策略抽象基类"""

    @abstractmethod
    def should_compact(self, history: List, context: Dict) -> bool:
        """判断是否需要压缩"""
        pass

    @abstractmethod
    def compact(self, history: List, llm: ChatOpenAI) -> List:
        """执行压缩"""
        pass

    @abstractmethod
    def get_kind(self) -> str:
        """返回压缩类型"""
        pass


class MicroCompactionStrategy(CompactionStrategy):
    """微压缩策略 - 移除连续的相同消息"""

    def should_compact(self, history: List, context: Dict) -> bool:
        return len(history) > 0

    def compact(self, history: List, llm: ChatOpenAI) -> List:
        from backend.app.memory.compaction import micro_compact
        micro_compact(history)
        return history

    def get_kind(self) -> str:
        return "micro"


class AutoCompactionStrategy(CompactionStrategy):
    """自动压缩策略 - 超过阈值时压缩"""

    def __init__(self, threshold: int = 50000):
        self.threshold = threshold

    def should_compact(self, history: List, context: Dict) -> bool:
        guard = context.get("guard")
        if not guard:
            return False
        tokens = guard.estimate_messages_tokens(history)
        return tokens > self.threshold

    def compact(self, history: List, llm: ChatOpenAI) -> List:
        from backend.app.memory.guard import ContextGuard
        guard = ContextGuard()
        return guard.compact_history(history, llm)

    def get_kind(self) -> str:
        return "auto"


class ManualCompactionStrategy(CompactionStrategy):
    """手动压缩策略 - 用户触发"""

    def should_compact(self, history: List, context: Dict) -> bool:
        from backend.app.compact import was_compact_requested
        return was_compact_requested()

    def compact(self, history: List, llm: ChatOpenAI) -> List:
        from backend.app.memory.guard import ContextGuard
        guard = ContextGuard()
        return guard.compact_history(history, llm)

    def get_kind(self) -> str:
        return "manual"
