"""
Conversation History - 对话历史管理

职责：
1. 管理对话消息列表
2. 应用压缩策略（micro/auto/manual）
3. Token 估算
4. 与 SessionStore 协作持久化
"""
from typing import List, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage


class ConversationHistory:
    """
    对话历史管理器

    管理对话消息列表，应用压缩策略，估算 token 数量。

    Usage:
        history = ConversationHistory(llm=llm, tools=tools)
        history.add_message(HumanMessage(content="Hello"))
        history.apply_strategies()  # 自动应用压缩策略
        messages = history.get_messages()
    """

    def __init__(
        self,
        llm: Optional[ChatOpenAI] = None,
        tools: Optional[List] = None,
        max_tokens: int = 180000
    ):
        self.llm = llm
        self.tools = tools or []
        self.max_tokens = max_tokens
        self._messages: List[BaseMessage] = []
        self._strategies = []

    @classmethod
    def create_default(
        cls,
        llm: ChatOpenAI,
        tools: List,
        max_tokens: int = 180000
    ) -> "ConversationHistory":
        """
        创建带默认策略的历史管理器

        默认策略：
        - MicroCompactionStrategy: 移除旧的 ToolMessage 内容
        - AutoCompactionStrategy: 超过 50000 tokens 时压缩
        - ManualCompactionStrategy: 响应 /compact 命令
        """
        from backend.app.memory.compaction_strategies import (
            MicroCompactionStrategy,
            AutoCompactionStrategy,
            ManualCompactionStrategy
        )

        history = cls(llm=llm, tools=tools, max_tokens=max_tokens)
        history.add_strategy(MicroCompactionStrategy())
        history.add_strategy(AutoCompactionStrategy(threshold=50000))
        history.add_strategy(ManualCompactionStrategy())
        return history

    def add_strategy(self, strategy):
        """添加压缩策略"""
        self._strategies.append(strategy)
        return self

    def add_message(self, message: BaseMessage):
        """添加消息到历史"""
        self._messages.append(message)

    def add_messages(self, messages: List[BaseMessage]):
        """批量添加消息"""
        self._messages.extend(messages)

    def get_messages(self) -> List[BaseMessage]:
        """获取消息列表"""
        return self._messages

    def set_messages(self, messages: List[BaseMessage]):
        """设置消息列表"""
        self._messages = messages

    def clear(self):
        """清空历史"""
        self._messages = []

    def estimate_tokens(self) -> int:
        """估算当前历史的 token 数量"""
        if self.llm is not None:
            try:
                return self.llm.get_num_tokens_from_messages(self._messages)
            except (NotImplementedError, AttributeError):
                pass
        # Fallback: 1 token ≈ 4 chars
        return len(str(self._messages)) // 4

    def apply_strategies(self) -> bool:
        """
        应用所有适用的压缩策略

        Returns:
            bool: 是否执行了压缩
        """
        from backend.app.session import get_store

        if not self.llm:
            return False

        context = {"history": self, "llm": self.llm}
        compressed = False

        for strategy in self._strategies:
            if strategy.should_compact(self._messages, context):
                before = len(self._messages)
                new_messages = strategy.compact(self._messages, self.llm)

                if len(new_messages) < before:
                    store = get_store()
                    store.save_compaction("main", strategy.get_kind(), before, len(new_messages))
                    print(f"  [compact] [{strategy.get_kind()}] {before} → {len(new_messages)} messages")
                    compressed = True

                self._messages = new_messages

        return compressed

    def to_dict(self) -> dict:
        """导出为字典（用于序列化）"""
        return {
            "messages": [
                {
                    "type": type(m).__name__,
                    "content": str(m.content)
                }
                for m in self._messages
            ],
            "token_count": self.estimate_tokens()
        }
