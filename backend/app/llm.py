from langchain_openai import ChatOpenAI

from backend.app.config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL


def get_llm(**kwargs) -> ChatOpenAI:
    """返回全局统一的 DeepSeek LLM 实例。

    kwargs 会透传给 ChatOpenAI，可覆盖默认参数（如 temperature、streaming 等）。
    """
    # 设置默认 max_tokens，避免输出被截断
    defaults = {
        "max_tokens": 8192,  # DeepSeek 默认 4096 太小，提升到 8192
    }
    defaults.update(kwargs)

    return ChatOpenAI(
        model=DEEPSEEK_MODEL,
        api_key=DEEPSEEK_API_KEY,
        base_url=DEEPSEEK_BASE_URL,
        **defaults,
    )
