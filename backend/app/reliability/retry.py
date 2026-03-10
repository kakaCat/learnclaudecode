"""
智能重试策略 - 工具失败时自动调整参数或切换备选方案
"""
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class RetryStrategy:
    """智能重试策略"""

    # 可重试的错误类型
    RETRYABLE_ERRORS = {
        "FileNotFoundError": "adjust_path",
        "PermissionError": "check_permissions",
        "TimeoutError": "increase_timeout",
        "ConnectionError": "retry_connection",
    }

    # 备选工具映射
    ALTERNATIVE_TOOLS = {
        "read_file": ["bash", "grep"],
        "write_file": ["bash"],
        "glob": ["bash", "list_dir"],
    }

    def __init__(self, max_retries: int = 2):
        self.max_retries = max_retries
        self.retry_count: Dict[str, int] = {}

    def is_retryable(self, error: str) -> bool:
        """判断错误是否可重试"""
        return any(err_type in error for err_type in self.RETRYABLE_ERRORS)

    def should_retry(self, tool_name: str, error: str) -> bool:
        """判断是否应该重试"""
        key = f"{tool_name}:{error[:50]}"
        count = self.retry_count.get(key, 0)
        return self.is_retryable(error) and count < self.max_retries

    def record_retry(self, tool_name: str, error: str):
        """记录重试次数"""
        key = f"{tool_name}:{error[:50]}"
        self.retry_count[key] = self.retry_count.get(key, 0) + 1

    def get_alternative_tool(self, tool_name: str) -> Optional[str]:
        """获取备选工具"""
        alternatives = self.ALTERNATIVE_TOOLS.get(tool_name, [])
        return alternatives[0] if alternatives else None

    def suggest_adjustment(self, tool_name: str, args: dict, error: str) -> Optional[dict]:
        """建议参数调整"""
        if "FileNotFoundError" in error and tool_name == "read_file":
            # 尝试添加常见路径前缀
            file_path = args.get("file_path", "")
            if not file_path.startswith("/"):
                return {"file_path": f"./{file_path}"}

        if "PermissionError" in error:
            logger.warning(f"Permission denied for {tool_name}, no auto-fix available")
            return None

        return None

    async def handle_failure(self, tool_name: str, args: dict, error: str) -> Dict[str, Any]:
        """
        处理工具失败

        Returns:
            {"retry": bool, "method": str, "suggestion": dict/str}
        """
        if not self.should_retry(tool_name, error):
            return {"retry": False, "reason": "max retries exceeded or non-retryable"}

        self.record_retry(tool_name, error)

        # 1. 尝试调整参数
        adjusted = self.suggest_adjustment(tool_name, args, error)
        if adjusted:
            return {
                "retry": True,
                "method": "adjusted_params",
                "suggestion": adjusted,
                "reason": f"Adjusted params based on {error[:30]}"
            }

        # 2. 尝试备选工具
        alternative = self.get_alternative_tool(tool_name)
        if alternative:
            return {
                "retry": True,
                "method": "alternative_tool",
                "suggestion": alternative,
                "reason": f"Try {alternative} instead of {tool_name}"
            }

        return {"retry": False, "reason": "no viable retry strategy"}


# 全局实例
_global_retry_strategy = RetryStrategy()


def get_retry_strategy() -> RetryStrategy:
    """获取全局重试策略实例"""
    return _global_retry_strategy
