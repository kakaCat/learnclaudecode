"""LLM invocation with tool binding"""
from typing import Any, List, Optional
from langchain_openai import ChatOpenAI
from langchain_core.tools import BaseTool


class LLMInvoker:
    """Handles LLM invocation with optional tool binding"""

    @staticmethod
    def invoke(llm: ChatOpenAI, messages: list, tools: Optional[List[BaseTool]] = None) -> Any:
        """
        Invoke LLM with messages and optional tools

        Args:
            llm: LLM instance
            messages: Message history
            tools: Optional tools to bind

        Returns:
            LLM response
        """
        if tools:
            bound_llm = llm.bind_tools(tools)
            return bound_llm.invoke(messages)
        else:
            return llm.invoke(messages)
