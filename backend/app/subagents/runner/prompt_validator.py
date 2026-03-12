"""
Prompt 验证器

验证和截断过大的 prompt
"""
import logging
from typing import Any

from ..config import CONFIG
from ..exceptions import PromptTooLargeError
from ..utils.console import console

logger = logging.getLogger(__name__)


class PromptValidator:
    """
    Prompt 验证器

    检查 prompt 大小并在必要时截断，防止上下文溢出。
    """

    @staticmethod
    def validate_and_truncate(prompt: str, llm: Any) -> str:
        """
        检查并截断 prompt

        Args:
            prompt: 用户输入 prompt
            llm: LLM 实例（用于 token 估算）

        Returns:
            原始或截断后的 prompt

        Note:
            DeepSeek 有 131K token 限制。我们使用保守限制：
            - System prompt: ~10K tokens
            - User prompt: max 100K tokens (安全边界)
        """
        # 估算 token 数（1 token ≈ 4 chars for Chinese/English mix）
        estimated_tokens = len(prompt) // CONFIG.CHARS_PER_TOKEN
        max_prompt_tokens = CONFIG.MAX_PROMPT_TOKENS

        if estimated_tokens <= max_prompt_tokens:
            return prompt

        # 需要截断
        logger.warning(
            f"Prompt too large: {estimated_tokens} tokens > {max_prompt_tokens}",
            extra={"prompt_length": len(prompt)}
        )

        # 截断到安全大小
        max_chars = max_prompt_tokens * CONFIG.CHARS_PER_TOKEN
        truncated = prompt[:max_chars]

        # 尝试在行边界截断（保留 90%+ 内容）
        last_newline = truncated.rfind('\n')
        if last_newline > max_chars * CONFIG.PROMPT_TRUNCATE_RATIO:
            truncated = truncated[:last_newline]

        # 添加警告信息
        warning = (
            f"\n\n[⚠️ Prompt truncated from {len(prompt)} to {len(truncated)} chars "
            f"to prevent context overflow]"
        )

        console.yellow(warning)

        return truncated + warning

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """
        估算文本的 token 数

        Args:
            text: 文本内容

        Returns:
            估算的 token 数
        """
        return len(text) // CONFIG.CHARS_PER_TOKEN
