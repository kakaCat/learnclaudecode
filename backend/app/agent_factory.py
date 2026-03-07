"""Agent factory - creates agent instances"""

from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from backend.app.config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL
from backend.app.prompts import get_system_prompt
from backend.app.tools_manager import tools_manager


def build_agent(session_key: str = ""):
    """Build agent and LLM instances"""
    llm = ChatOpenAI(
        model=DEEPSEEK_MODEL,
        api_key=DEEPSEEK_API_KEY,
        base_url=DEEPSEEK_BASE_URL,
    )
    return create_agent(llm, tools_manager.get_tools(), system_prompt=get_system_prompt(session_key)), llm
