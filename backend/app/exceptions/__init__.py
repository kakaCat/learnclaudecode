"""
异常处理包

提供统一的异常类型和错误处理机制。
"""

from .exceptions import (
    # 基础异常
    AgentError,

    # 工具相关异常
    ToolError,
    ToolExecutionError,
    ToolNotFoundError,
    ToolValidationError,
    ToolTimeoutError,

    # Session 相关异常
    SessionError,
    SessionNotFoundError,
    SessionExpiredError,
    SessionValidationError,

    # 记忆相关异常
    MemoryError,
    MemoryWriteError,
    MemorySearchError,

    # 任务相关异常
    TaskError,
    TaskNotFoundError,
    TaskValidationError,
    TaskDependencyError,

    # LLM 相关异常
    LLMError,
    LLMConnectionError,
    LLMTimeoutError,
    LLMRateLimitError,
    LLMContentFilterError,

    # 配置相关异常
    ConfigError,
    ConfigNotFoundError,
    ConfigValidationError,

    # 文件系统相关异常
    FileSystemError,
    FileNotFoundError,
    FilePermissionError,
    FileReadError,
    FileWriteError,

    # 网络相关异常
    NetworkError,
    NetworkConnectionError,
    NetworkTimeoutError,

    # 生命周期相关异常
    LifecycleError,
    HeartbeatError,
    GuardSystemError,

    # 工具函数
    handle_agent_errors,
    safe_execute,
    safe_execute_async,
    is_agent_error,
    get_error_code,
    format_error_for_user,
    format_error_for_logging,
)

__all__ = [
    # 基础异常
    "AgentError",

    # 工具相关异常
    "ToolError",
    "ToolExecutionError",
    "ToolNotFoundError",
    "ToolValidationError",
    "ToolTimeoutError",

    # Session 相关异常
    "SessionError",
    "SessionNotFoundError",
    "SessionExpiredError",
    "SessionValidationError",

    # 记忆相关异常
    "MemoryError",
    "MemoryWriteError",
    "MemorySearchError",

    # 任务相关异常
    "TaskError",
    "TaskNotFoundError",
    "TaskValidationError",
    "TaskDependencyError",

    # LLM 相关异常
    "LLMError",
    "LLMConnectionError",
    "LLMTimeoutError",
    "LLMRateLimitError",
    "LLMContentFilterError",

    # 配置相关异常
    "ConfigError",
    "ConfigNotFoundError",
    "ConfigValidationError",

    # 文件系统相关异常
    "FileSystemError",
    "FileNotFoundError",
    "FilePermissionError",
    "FileReadError",
    "FileWriteError",

    # 网络相关异常
    "NetworkError",
    "NetworkConnectionError",
    "NetworkTimeoutError",

    # 生命周期相关异常
    "LifecycleError",
    "HeartbeatError",
    "GuardSystemError",

    # 工具函数
    "handle_agent_errors",
    "safe_execute",
    "safe_execute_async",
    "is_agent_error",
    "get_error_code",
    "format_error_for_user",
    "format_error_for_logging",
]
