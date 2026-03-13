import os
from dotenv import load_dotenv

load_dotenv(override=True)

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# Context Compaction
# Fallback threshold when LLM max_tokens is unavailable
# Actual threshold = min(COMPACTION_THRESHOLD, llm.max_tokens * 0.9)
COMPACTION_THRESHOLD = int(os.getenv("COMPACTION_THRESHOLD", "25000"))
