"""
BaseContext - 基础上下文（共享资源）

所有 Agent 共享的资源：
- session_store: 会话存储
- llm: 语言模型
- tracer: 事件追踪
- conversation_history: 对话记忆
- overflow_guard: 溢出保护
"""
from typing import Optional
from langchain_openai import ChatOpenAI

from backend.app.session import get_store, SessionStore
from backend.app.llm import get_llm
from backend.app.context.tracer import Tracer
from backend.app.context.overflow_guard import OverflowGuard
from backend.app.memory import ConversationHistory


class BaseContext:
    """
    基础上下文 - 所有 Agent 共享的资源

    MainContext 和 SubagentContext 都继承此类
    """

    def __init__(self, session_key: str):
        """
        初始化基础上下文

        Args:
            session_key: 会话标识符
        """
        self.session_key = session_key

        # 1. SessionStore（全局单例）
        self.session_store: SessionStore = get_store()
        self.session_store.set_current_key(session_key)

        # 2. LLM
        self.llm: ChatOpenAI = get_llm()

        # 3. Tracer
        self.tracer: Tracer = Tracer()

        # 4. ConversationHistory
        self.conversation_history: ConversationHistory = ConversationHistory(
            llm=self.llm,
            tools=None,  # 子类设置
            max_tokens=180000
        )

        # 5. OverflowGuard
        self.overflow_guard: OverflowGuard = OverflowGuard(
            llm=self.llm,
            tools=None,  # 子类设置
            max_tokens=180000
        )
