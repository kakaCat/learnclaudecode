"""Application Context - manages all agent components like Spring ApplicationContext"""
from typing import Optional, List
from langchain_openai import ChatOpenAI
from langchain_core.tools import BaseTool
from langchain.agents import create_agent

from backend.app.context.base import BaseAgentContext
from backend.app.context.overflow_guard import OverflowGuard
from backend.app.memory import ConversationHistory
from backend.app.llm import get_llm
from backend.app.tools.manager import tool_manager
from backend.app.prompts import get_system_prompt
from backend.app.context.tracer import Tracer


class AgentContext(BaseAgentContext):
    """
    Application context that manages all agent components.

    Similar to Spring ApplicationContext, this class:
    - Initializes and manages LLM
    - Initializes and manages tools
    - Initializes and manages prompts
    - Creates and configures OverflowGuard (溢出保护)
    - Creates and configures ConversationHistory (对话记忆)
    - Creates and manages Agent
    - Provides centralized component access

    Usage:
        context = AgentContext.create_default()
        agent = context.get_agent()
        llm = context.get_llm()
        tools = context.get_tools()
        prompt = context.get_system_prompt()
        guard = context.get_overflow_guard()
        history = context.get_conversation_history()
    """

    def __init__(self):
        self._session_key: str = ""
        self._llm: Optional[ChatOpenAI] = None
        self._tools: Optional[List[BaseTool]] = None
        self._system_prompt: Optional[str] = None
        self._overflow_guard: Optional[OverflowGuard] = None
        self._conversation_history: Optional[ConversationHistory] = None
        self._agent = None
        self._tracer: Optional[Tracer] = None

    @classmethod
    def create_default(cls, session_key: str = "") -> "AgentContext":
        """
        Factory method: create context with default configuration

        Args:
            session_key: Session identifier for context isolation

        Returns:
            Fully initialized AgentContext
        """
        context = cls()
        context._session_key = session_key
        context._initialize_components()
        return context

    def _initialize_components(self):
        """Initialize all components in correct order"""
        # 1. Initialize tracer
        self._tracer = Tracer()

        # 2. Initialize LLM
        self._llm = get_llm()

        # 3. Initialize tools
        self._tools = tool_manager.get_main_tools()

        # 4. Initialize system prompt
        self._system_prompt = get_system_prompt(self._session_key)

        # 5. Initialize overflow guard
        self._overflow_guard = OverflowGuard(
            llm=self._llm,
            tools=self._tools,
            max_tokens=180000
        )

        # 6. Initialize conversation history with strategies
        self._conversation_history = ConversationHistory.create_default(
            llm=self._llm,
            tools=self._tools,
            max_tokens=180000
        )

        # 7. Initialize agent
        self._agent = create_agent(
            self._llm,
            self._tools,
            system_prompt=self._system_prompt
        )

    def get_llm(self) -> ChatOpenAI:
        """Get LLM instance"""
        if self._llm is None:
            raise RuntimeError("Context not initialized. Call create_default() first.")
        return self._llm

    def get_tools(self) -> List[BaseTool]:
        """Get tools list"""
        if self._tools is None:
            raise RuntimeError("Context not initialized. Call create_default() first.")
        return self._tools

    def get_system_prompt(self) -> str:
        """Get system prompt"""
        if self._system_prompt is None:
            raise RuntimeError("Context not initialized. Call create_default() first.")
        return self._system_prompt

    def get_guard(self) -> OverflowGuard:
        """Get overflow guard (向后兼容的别名)"""
        return self.get_overflow_guard()

    def get_overflow_guard(self) -> OverflowGuard:
        """Get overflow guard (context overflow protection)"""
        if self._overflow_guard is None:
            raise RuntimeError("Context not initialized. Call create_default() first.")
        return self._overflow_guard

    def get_conversation_history(self) -> ConversationHistory:
        """Get conversation history (memory management)"""
        if self._conversation_history is None:
            raise RuntimeError("Context not initialized. Call create_default() first.")
        return self._conversation_history

    def get_agent(self):
        """Get agent instance"""
        if self._agent is None:
            raise RuntimeError("Context not initialized. Call create_default() first.")
        return self._agent

    def get_session_key(self) -> str:
        """Get session key"""
        return self._session_key

    def set_session_key(self, session_key: str):
        """
        Update session key and reinitialize components that depend on it

        Args:
            session_key: New session identifier
        """
        from backend.app.session import set_session_key as global_set_session_key

        self._session_key = session_key
        # Sync to global session
        global_set_session_key(session_key)
        # Reinitialize system prompt with new session key
        self._system_prompt = get_system_prompt(session_key)
        # Reinitialize agent with new prompt
        self._agent = create_agent(
            self._llm,
            self._tools,
            system_prompt=self._system_prompt
        )

    def set_llm(self, llm: ChatOpenAI):
        """Set custom LLM instance"""
        self._llm = llm
        if self._overflow_guard:
            self._overflow_guard.llm = llm
        if self._conversation_history:
            self._conversation_history.llm = llm

    def set_tools(self, tools: List[BaseTool]):
        """Set custom tools list"""
        self._tools = tools
        if self._overflow_guard:
            self._overflow_guard.tools = tools
        if self._conversation_history:
            self._conversation_history.tools = tools

    def get_tracer(self) -> Tracer:
        """Get tracer instance"""
        if self._tracer is None:
            raise RuntimeError("Context not initialized. Call create_default() first.")
        return self._tracer
