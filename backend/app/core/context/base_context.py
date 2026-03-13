"""
BaseContext - 重构后的基础上下文

核心改进：
1. 只管理共享资源，不包含业务逻辑
2. 工具列表通过抽象方法由子类提供
3. 移除对 OverflowGuard 和 ConversationHistory 的直接依赖
"""
from abc import ABC, abstractmethod
from typing import List
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI


class BaseContext(ABC):
    """
    基础上下文 - 所有 Agent 共享的资源

    职责：
    - 管理共享资源（LLM、SessionStore、Tracer）
    - 定义抽象接口（工具列表、系统提示词）
    """

    def __init__(
        self,
        session_key: str,
        llm: ChatOpenAI,
        session_store,
        tracer,
        recursion_limit: int = 100
    ):
        """
        初始化基础上下文

        Args:
            session_key: 会话标识符
            llm: 语言模型实例
            session_store: 会话存储实例
            tracer: 追踪器实例
            recursion_limit: Agent 最大循环次数，默认 100
        """
        self.session_key = session_key
        self.llm = llm
        self.session_store = session_store
        self.tracer = tracer
        self.recursion_limit = recursion_limit

    @abstractmethod
    def get_tools(self) -> List[BaseTool]:
        """获取工具列表（子类实现）"""
        pass

    @abstractmethod
    def get_system_prompt(self) -> str:
        """获取系统提示词（子类实现）"""
        pass
