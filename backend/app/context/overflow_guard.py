"""
Overflow Guard - 防止上下文窗口溢出

职责：
1. 包装 LLM 调用，捕获上下文溢出错误
2. 自动重试机制（截断工具结果 → 压缩历史）
3. 不负责压缩策略（由 ConversationHistory 管理）
"""
import json
from typing import List, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import BaseTool

from backend.app.memory.llm_invoker import LLMInvoker


class OverflowGuard:
    """
    上下文溢出保护器

    三阶段重试机制：
    1. 正常调用 LLM
    2. 截断大型工具结果（保留前 30%）
    3. 压缩对话历史（LLM 总结）
    4. 仍然溢出则抛出异常

    Usage:
        guard = OverflowGuard(llm=llm, tools=tools)
        result = guard.guard_invoke(messages=messages)
    """

    def __init__(
        self,
        llm: Optional[ChatOpenAI] = None,
        tools: Optional[List[BaseTool]] = None,
        max_tokens: int = 180000
    ):
        self.llm = llm
        self.tools = tools or []
        self.max_tokens = max_tokens

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """粗略估算 token 数：1 token ≈ 4 chars"""
        return len(text) // 4

    def estimate_messages_tokens(self, messages: list) -> int:
        """估算消息列表的总 token 数"""
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
        """截断工具结果，保留前 30%"""
        max_chars = int(self.max_tokens * 4 * max_fraction)
        if len(result) <= max_chars:
            return result

        lines = result.split("\n")
        truncated_lines = []
        current_length = 0

        for line in lines:
            if current_length + len(line) > max_chars:
                break
            truncated_lines.append(line)
            current_length += len(line) + 1

        return "\n".join(truncated_lines) + f"\n\n[... truncated {len(result) - current_length} chars]"

    def _truncate_large_tool_results(self, messages: List) -> List:
        """截断大型工具结果"""
        new_messages = []
        for msg in messages:
            if isinstance(msg, ToolMessage):
                content = msg.content
                if isinstance(content, str) and len(content) > 10000:
                    truncated = self.truncate_tool_result(content)
                    new_messages.append(ToolMessage(
                        content=truncated,
                        tool_call_id=msg.tool_call_id
                    ))
                else:
                    new_messages.append(msg)
            else:
                new_messages.append(msg)
        return new_messages

    def compact_history(self, messages: List, llm: ChatOpenAI) -> List:
        """
        压缩对话历史

        保存完整记录到 transcript，用 LLM 总结替换所有消息
        """
        from backend.app.session import get_store

        store = get_store()
        session_dir = store.get_session_dir()
        transcript_path = session_dir / "transcript.jsonl"

        # 保存完整对话记录
        with open(transcript_path, "w") as f:
            for m in messages:
                f.write(json.dumps({
                    "role": type(m).__name__,
                    "content": str(m.content)
                }) + "\n")

        # 让 LLM 总结对话
        conversation_text = "\n".join(
            f"{type(m).__name__}: {str(m.content)[:500]}"
            for m in messages
        )[:80000]

        summary = llm.invoke([HumanMessage(content=
            "请总结这段对话以便后续继续。包含：1) 已完成的工作，2) 当前状态，3) 关键决策。"
            "简明扼要，但保留关键细节。\n\n" + conversation_text
        )]).content

        # 用摘要替换所有消息
        return [
            HumanMessage(content=f"[Conversation compressed. Transcript: {transcript_path}]\n\n{summary}"),
            AIMessage(content="明白。我已获取摘要中的上下文，继续执行。"),
        ]

    def guard_invoke(
        self,
        messages: List,
        llm: Optional[ChatOpenAI] = None,
        tools: Optional[List[BaseTool]] = None,
        max_retries: int = 2
    ):
        """
        带保护的 LLM 调用

        Args:
            messages: 消息列表（会被原地修改）
            llm: LLM 实例（可选，使用构造时的 llm）
            tools: 工具列表（可选，使用构造时的 tools）
            max_retries: 最大重试次数

        Returns:
            LLM 响应

        Raises:
            ValueError: 参数错误
            RuntimeError: 重试耗尽仍然溢出
        """
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

                # 如果成功，更新原始消息列表
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
