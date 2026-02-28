from langchain_openai import ChatOpenAI

from backend.app.config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL


def get_llm(**kwargs) -> ChatOpenAI:
    """返回全局统一的 DeepSeek LLM 实例。

    kwargs 会透传给 ChatOpenAI，可覆盖默认参数（如 temperature、streaming 等）。
    """
    return ChatOpenAI(
        model=DEEPSEEK_MODEL,
        api_key=DEEPSEEK_API_KEY,
        base_url=DEEPSEEK_BASE_URL,
        **kwargs,
    )
