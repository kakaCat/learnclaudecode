"""
HistoryManager - 历史管理器

职责：
1. 对话历史压缩
2. 记忆召回
3. 历史保存
"""
from typing import List
from langchain_core.messages import BaseMessage, HumanMessage


class HistoryManager:
    """历史管理器"""

    def __init__(self):
        self.conversation_history = None  # 延迟初始化

    def prepare(
        self,
        context,
        prompt: str,
        history: List[BaseMessage]
    ) -> List[BaseMessage]:
        """
        准备上下文：压缩历史、召回记忆

        Args:
            context: Agent 上下文
            prompt: 用户输入
            history: 历史消息

        Returns:
            准备好的消息列表
        """
        # 1. 压缩历史（启用三层压缩机制）
        if self.conversation_history is None:
            from backend.app.memory import ConversationHistory
            self.conversation_history = ConversationHistory.create_default(
                llm=context.llm,
                tools=context.get_tools(),
                max_tokens=40000,  # DeepSeek 总限制 131K，历史最多 40K，预留 91K 给 system/tools/input/output
                compression_threshold=25000  # Layer 2: 25K tokens 时触发自动压缩
            )

        self.conversation_history.set_messages(history)
        self.conversation_history.apply_strategies()  # 应用三层策略
        compressed = self.conversation_history.get_messages()

        # 2. 召回记忆
        from backend.app.prompts import auto_recall_memory
        recalled = auto_recall_memory(context.session_key, prompt)
        if recalled:
            memory_msg = HumanMessage(
                content=f"<recalled-memory>\n{recalled}\n</recalled-memory>"
            )
            compressed.insert(0, memory_msg)

        return compressed

    def save(
        self,
        context,
        prompt: str,
        output: str,
        tool_calls: List[dict]
    ):
        """
        保存对话历史

        Args:
            context: Agent 上下文
            prompt: 用户输入
            output: AI 输出
            tool_calls: 工具调用列表
        """
        agent_name = getattr(context, "agent_name", "main")
        context.session_store.save_turn(agent_name, prompt, output, tool_calls)
