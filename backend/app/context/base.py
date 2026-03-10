"""Base Context - Abstract interface for agent context management"""
from abc import ABC, abstractmethod
from typing import Optional, List
from langchain_openai import ChatOpenAI
from langchain_core.tools import BaseTool
from langchain_core.messages import HumanMessage


class BaseAgentContext(ABC):
    """
    Abstract base class for agent context management.

    Defines the unified interface and provides default implementations
    for common methods.
    """

    @abstractmethod
    def get_llm(self) -> ChatOpenAI:
        """Get LLM instance"""
        pass

    @abstractmethod
    def get_tools(self) -> List[BaseTool]:
        """Get tools list"""
        pass

    @abstractmethod
    def get_system_prompt(self) -> str:
        """Get system prompt"""
        pass

    @abstractmethod
    def get_overflow_guard(self):
        """Get overflow guard (context overflow protection)"""
        pass

    @abstractmethod
    def get_conversation_history(self):
        """Get conversation history (memory management)"""
        pass

    @abstractmethod
    def get_agent(self):
        """Get agent instance"""
        pass

    @abstractmethod
    def get_session_key(self) -> str:
        """Get session key"""
        pass

    @abstractmethod
    def set_session_key(self, session_key: str):
        """Update session key and reinitialize dependent components"""
        pass

    @abstractmethod
    def get_tracer(self):
        """Get tracer instance"""
        pass

    def new_session_key(self) -> str:
        """Generate new session key (default implementation)"""
        from backend.app.session import new_session_key
        return new_session_key()

    def get_store(self):
        """Get session store (default implementation)"""
        from backend.app.session import get_store
        return get_store()

    def prepare_context(self, history: list, prompt: str) -> list:
        """
        Prepare context: apply compression strategies and recall memory
        (default implementation)

        Args:
            history: Historical messages
            prompt: User input

        Returns:
            Prepared history with compression and memory
        """
        # Apply conversation history compression
        conversation_history = self.get_conversation_history()
        conversation_history.set_messages(history)
        conversation_history.apply_strategies()
        history = conversation_history.get_messages()

        # Auto recall relevant memory
        from backend.app.prompts import auto_recall_memory
        recalled = auto_recall_memory(self.get_session_key(), prompt)
        if recalled:
            memory_msg = HumanMessage(content=f"<recalled-memory>\n{recalled}\n</recalled-memory>")
            history.insert(0, memory_msg)

        return history
