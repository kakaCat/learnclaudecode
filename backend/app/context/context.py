"""
context_guard.py - Context overflow protection inspired by s03_sessions.py

Three-stage retry mechanism:
1. Normal API call
2. Truncate large tool results (keep first 30%)
3. Compact history via LLM summary (compress first 50%)
4. Raise exception if still overflowing

Includes CompactionStrategy pattern for flexible compression strategies.
"""
import json
import time
from abc import ABC, abstractmethod
from typing import Any, List, Dict, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage


# ============================================================================
# 策略模式 - 压缩策略
# ============================================================================

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
        from backend.app.agent.compaction import micro_compact
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
        guard = ContextGuard()
        return guard.compact_history(history, llm)

    def get_kind(self) -> str:
        return "manual"


class ContextGuard:
    """Protects agent from context window overflow with three-stage retry."""

    def __init__(self, max_tokens: int = 180000):
        self.max_tokens = max_tokens
        self.strategies: List[CompactionStrategy] = []

    def add_strategy(self, strategy: CompactionStrategy):
        """添加压缩策略"""
        self.strategies.append(strategy)
        return self

    def apply_strategies(self, history: List, llm: ChatOpenAI) -> List:
        """应用所有适用的压缩策略"""
        from backend.app.session import get_store

        context = {"guard": self, "llm": llm}

        for strategy in self.strategies:
            if strategy.should_compact(history, context):
                before = len(history)
                new_history = strategy.compact(history, llm)

                if len(new_history) < before:
                    get_store().save_compaction("main", strategy.get_kind(), before, len(new_history))
                    print(f"  [compact] [{strategy.get_kind()}] {before} → {len(new_history)} messages")

                history = new_history

        return history

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """Rough token estimation: 1 token ≈ 4 chars."""
        return len(text) // 4

    def estimate_messages_tokens(self, messages: list) -> int:
        """Estimate total tokens in message history."""
        total = 0
        for msg in messages:
            if hasattr(msg, "content"):
                content = msg.content
                if isinstance(content, str):
                    total += self.estimate_tokens(content)
                elif isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict):
                            total += self.estimate_tokens(json.dumps(item))
                        else:
                            total += self.estimate_tokens(str(item))
            # Add tool_calls
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    total += self.estimate_tokens(json.dumps(tc))
        return total

    def truncate_tool_result(self, result: str, max_fraction: float = 0.3) -> str:
        """Truncate tool result at newline boundary, keep first 30%."""
        max_chars = int(self.max_tokens * 4 * max_fraction)
        if len(result) <= max_chars:
            return result

        # Find last newline before max_chars
        cut = result.rfind("\n", 0, max_chars)
        if cut <= 0:
            cut = max_chars

        head = result[:cut]
        return (
            head + f"\n\n[... truncated ({len(result)} chars total, "
            f"showing first {len(head)}) ...]"
        )

    def compact_history(self, messages: list, llm: ChatOpenAI) -> list:
        """
        Compact first 50% of messages via LLM summary.
        Keep last N messages (N = max(4, 20% of total)) unchanged.
        """
        total = len(messages)
        if total <= 4:
            return messages

        keep_count = max(4, int(total * 0.2))
        compress_count = max(2, int(total * 0.5))
        compress_count = min(compress_count, total - keep_count)

        if compress_count < 2:
            return messages

        old_messages = messages[:compress_count]
        recent_messages = messages[compress_count:]

        # Serialize old messages for summary
        old_text = self._serialize_messages(old_messages)

        summary_prompt = (
            "Summarize the following conversation concisely, "
            "preserving key facts and decisions. "
            "Output only the summary in Chinese, no preamble.\n\n"
            f"{old_text}"
        )

        try:
            summary_resp = llm.invoke([HumanMessage(content=summary_prompt)])
            summary_text = summary_resp.content

            print(f"  [compact] {len(old_messages)} messages -> summary ({len(summary_text)} chars)")

            compacted = [
                HumanMessage(content=f"[之前对话摘要]\n{summary_text}"),
                AIMessage(content="明白，我已了解之前的对话上下文。"),
            ]
            compacted.extend(recent_messages)
            return compacted

        except Exception as exc:
            print(f"  [compact] Summary failed ({exc}), dropping old messages")
            return recent_messages

    def _serialize_messages(self, messages: list) -> str:
        """Flatten messages to plain text for LLM summary."""
        parts = []
        for msg in messages:
            if isinstance(msg, HumanMessage):
                parts.append(f"[user]: {msg.content}")
            elif isinstance(msg, AIMessage):
                if isinstance(msg.content, str):
                    parts.append(f"[assistant]: {msg.content}")
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    for tc in msg.tool_calls:
                        parts.append(f"[assistant called {tc['name']}]: {json.dumps(tc['args'], ensure_ascii=False)}")
            elif isinstance(msg, ToolMessage):
                preview = msg.content[:500] if isinstance(msg.content, str) else str(msg.content)[:500]
                parts.append(f"[tool_result]: {preview}")
        return "\n".join(parts)

    def _truncate_large_tool_results(self, messages: list) -> list:
        """Traverse messages and truncate large ToolMessage content."""
        result = []
        for msg in messages:
            if isinstance(msg, ToolMessage) and isinstance(msg.content, str):
                truncated_content = self.truncate_tool_result(msg.content)
                result.append(ToolMessage(
                    content=truncated_content,
                    tool_call_id=msg.tool_call_id
                ))
            else:
                result.append(msg)
        return result

    def guard_invoke(
        self,
        llm: ChatOpenAI,
        messages: list,
        max_retries: int = 2,
    ) -> Any:
        """
        Three-stage retry:
          Attempt 0: Normal call
          Attempt 1: Truncate large tool results
          Attempt 2: Compact history via LLM summary
        """
        current_messages = messages.copy()

        for attempt in range(max_retries + 1):
            try:
                result = llm.invoke(current_messages)
                # Update original messages if modified
                if current_messages is not messages:
                    messages.clear()
                    messages.extend(current_messages)
                return result

            except Exception as exc:
                error_str = str(exc).lower()
                is_overflow = ("context" in error_str or "token" in error_str or "length" in error_str)

                if not is_overflow or attempt >= max_retries:
                    raise

                if attempt == 0:
                    print("  [guard] Context overflow detected, truncating large tool results...")
                    current_messages = self._truncate_large_tool_results(current_messages)
                elif attempt == 1:
                    print("  [guard] Still overflowing, compacting conversation history...")
                    current_messages = self.compact_history(current_messages, llm)

        raise RuntimeError("guard_invoke: exhausted retries")
