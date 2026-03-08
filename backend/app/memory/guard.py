"""Context guard - protects agent from context window overflow"""
import json
from typing import Any, List, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import BaseTool


class ContextGuard:
    """
    Context overflow protection with three-stage retry mechanism.

    Inspired by s03_sessions.py, this class wraps LLM invocation with automatic
    context overflow handling:
    1. Normal API call
    2. Truncate large tool results (keep first 30%)
    3. Compact history via LLM summary (compress first 50%)
    4. Raise exception if still overflowing

    Usage:
        guard = ContextGuard.create_default(llm, tools)
        result = guard.guard_invoke(messages=messages)
    """

    def __init__(self, llm: Optional[ChatOpenAI] = None, tools: Optional[List[BaseTool]] = None, max_tokens: int = 180000):
        self.llm = llm
        self.tools = tools or []
        self.max_tokens = max_tokens
        self.strategies = []

    @classmethod
    def create_default(cls, llm: ChatOpenAI, tools: List[BaseTool], max_tokens: int = 180000) -> "ContextGuard":
        """
        Factory method: create ContextGuard with default strategies

        Default strategies:
        - MicroCompactionStrategy: remove duplicate messages
        - AutoCompactionStrategy: compact when exceeds 50000 tokens
        - ManualCompactionStrategy: compact on /compact command
        """
        from backend.app.memory.compaction_strategies import MicroCompactionStrategy, AutoCompactionStrategy, ManualCompactionStrategy

        guard = cls(llm=llm, tools=tools, max_tokens=max_tokens)
        guard.add_strategy(MicroCompactionStrategy())
        guard.add_strategy(AutoCompactionStrategy(threshold=50000))
        guard.add_strategy(ManualCompactionStrategy())
        return guard

    def add_strategy(self, strategy):
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
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    total += self.estimate_tokens(json.dumps(tc))
        return total

    def truncate_tool_result(self, result: str, max_fraction: float = 0.3) -> str:
        """Truncate tool result at newline boundary, keep first 30%."""
        max_chars = int(self.max_tokens * 4 * max_fraction)
        if len(result) <= max_chars:
            return result

        cut = result.rfind("\n", 0, max_chars)
        if cut <= 0:
            cut = max_chars

        head = result[:cut]
        return head + f"\n\n[... truncated ({len(result)} chars total, showing first {len(head)}) ...]"

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
        llm: Optional[ChatOpenAI] = None,
        messages: Optional[list] = None,
        tools: Optional[List[BaseTool]] = None,
        max_retries: int = 2,
    ) -> Any:
        """
        Three-stage retry with full API call management:
          Attempt 0: Normal call
          Attempt 1: Truncate large tool results
          Attempt 2: Compact history via LLM summary

        Args:
            llm: LLM instance (uses self.llm if not provided)
            messages: Message history (required)
            tools: Tools list (uses self.tools if not provided)
            max_retries: Maximum retry attempts
        """
        from backend.app.memory.llm_invoker import LLMInvoker

        active_llm = llm or self.llm
        active_tools = tools if tools is not None else self.tools

        if not active_llm:
            raise ValueError("LLM must be provided either in constructor or as parameter")
        if messages is None:
            raise ValueError("messages parameter is required")

        current_messages = messages.copy()

        for attempt in range(max_retries + 1):
            try:
                result = LLMInvoker.invoke(active_llm, current_messages, active_tools)

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
                    current_messages = self.compact_history(current_messages, active_llm)

        raise RuntimeError("guard_invoke: exhausted retries")
