"""
统一异常处理模块

定义 Agent 系统的所有异常类型，提供统一的错误处理机制。
这是一个可选模块，不影响核心功能。
"""

from typing import Optional, Dict, Any, Union
from dataclasses import dataclass
import traceback
import json


@dataclass
class AgentError(Exception):
    """
    Agent 基础异常类
    
    所有 Agent 相关异常的基类，提供统一的错误格式和序列化能力。
    """
    
    message: str
    code: str = "AGENT_ERROR"
    details: Optional[Dict[str, Any]] = None
    inner_exception: Optional[Exception] = None
    
    def __init__(
        self,
        message: str,
        code: str = "AGENT_ERROR",
        details: Optional[Dict[str, Any]] = None,
        inner_exception: Optional[Exception] = None
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}
        self.inner_exception = inner_exception
        
        # 自动记录堆栈跟踪
        self.stack_trace = traceback.format_exc()
    
    def __str__(self) -> str:
        """友好的错误信息显示"""
        base = f"[{self.code}] {self.message}"
        if self.details:
            details_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            base += f" ({details_str})"
        return base
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式，便于序列化"""
        return {
            "error": True,
            "code": self.code,
            "message": self.message,
            "details": self.details,
            "stack_trace": self.stack_trace,
            "inner_exception": str(self.inner_exception) if self.inner_exception else None
        }
    
    def to_json(self) -> str:
        """转换为 JSON 字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
    
    @classmethod
    def from_exception(cls, exc: Exception, code: str = "UNKNOWN_ERROR") -> "AgentError":
        """从普通异常创建 AgentError"""
        return cls(
            message=str(exc),
            code=code,
            details={"original_type": type(exc).__name__},
            inner_exception=exc
        )


# ============================================================================
# 工具相关异常
# ============================================================================

class ToolError(AgentError):
    """工具相关异常基类"""
    def __init__(self, tool_name: str, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"工具 '{tool_name}' 错误: {message}",
            code="TOOL_ERROR",
            details={"tool": tool_name, **(details or {})}
        )


class ToolExecutionError(ToolError):
    """工具执行异常"""
    def __init__(self, tool_name: str, error: Exception):
        super().__init__(
            tool_name=tool_name,
            message=f"执行失败: {str(error)}",
            details={
                "tool": tool_name,
                "error_type": type(error).__name__,
                "error_message": str(error)
            }
        )


class ToolNotFoundError(ToolError):
    """工具未找到异常"""
    def __init__(self, tool_name: str):
        super().__init__(
            tool_name=tool_name,
            message="工具未找到或未注册"
        )


class ToolValidationError(ToolError):
    """工具参数验证异常"""
    def __init__(self, tool_name: str, param_name: str, param_value: Any, reason: str):
        super().__init__(
            tool_name=tool_name,
            message=f"参数验证失败: {param_name}={param_value} ({reason})",
            details={
                "tool": tool_name,
                "param_name": param_name,
                "param_value": str(param_value),
                "reason": reason
            }
        )


class ToolTimeoutError(ToolError):
    """工具执行超时异常"""
    def __init__(self, tool_name: str, timeout_seconds: float):
        super().__init__(
            tool_name=tool_name,
            message=f"执行超时 ({timeout_seconds}秒)",
            details={
                "tool": tool_name,
                "timeout_seconds": timeout_seconds
            }
        )


# ============================================================================
# Session 相关异常
# ============================================================================

class SessionError(AgentError):
    """Session 相关异常基类"""
    def __init__(self, session_key: str, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"Session '{session_key}' 错误: {message}",
            code="SESSION_ERROR",
            details={"session_key": session_key, **(details or {})}
        )


class SessionNotFoundError(SessionError):
    """Session 不存在异常"""
    def __init__(self, session_key: str):
        super().__init__(
            session_key=session_key,
            message="Session 不存在或已过期"
        )


class SessionExpiredError(SessionError):
    """Session 过期异常"""
    def __init__(self, session_key: str, expired_at: str):
        super().__init__(
            session_key=session_key,
            message=f"Session 已过期 ({expired_at})",
            details={
                "session_key": session_key,
                "expired_at": expired_at
            }
        )


class SessionValidationError(SessionError):
    """Session 验证异常"""
    def __init__(self, session_key: str, reason: str):
        super().__init__(
            session_key=session_key,
            message=f"Session 验证失败: {reason}",
            details={
                "session_key": session_key,
                "reason": reason
            }
        )


# ============================================================================
# 记忆相关异常
# ============================================================================

class MemoryError(AgentError):
    """记忆相关异常基类"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"记忆系统错误: {message}",
            code="MEMORY_ERROR",
            details=details
        )


class MemoryWriteError(MemoryError):
    """记忆写入异常"""
    def __init__(self, category: str, content: str, error: Exception):
        super().__init__(
            message=f"写入记忆失败: {category}",
            details={
                "category": category,
                "content_preview": content[:100] + "..." if len(content) > 100 else content,
                "error_type": type(error).__name__,
                "error_message": str(error)
            }
        )


class MemorySearchError(MemoryError):
    """记忆搜索异常"""
    def __init__(self, query: str, error: Exception):
        super().__init__(
            message=f"搜索记忆失败: '{query}'",
            details={
                "query": query,
                "error_type": type(error).__name__,
                "error_message": str(error)
            }
        )


# ============================================================================
# 任务相关异常
# ============================================================================

class TaskError(AgentError):
    """任务相关异常基类"""
    def __init__(self, task_id: Optional[int], message: str, details: Optional[Dict[str, Any]] = None):
        task_info = f"任务 #{task_id}" if task_id is not None else "任务"
        super().__init__(
            message=f"{task_info} 错误: {message}",
            code="TASK_ERROR",
            details={"task_id": task_id, **(details or {})}
        )


class TaskNotFoundError(TaskError):
    """任务未找到异常"""
    def __init__(self, task_id: int):
        super().__init__(
            task_id=task_id,
            message="任务不存在"
        )


class TaskValidationError(TaskError):
    """任务验证异常"""
    def __init__(self, task_id: Optional[int], reason: str):
        super().__init__(
            task_id=task_id,
            message=f"任务验证失败: {reason}",
            details={"reason": reason}
        )


class TaskDependencyError(TaskError):
    """任务依赖异常"""
    def __init__(self, task_id: int, dependency_id: int, reason: str):
        super().__init__(
            task_id=task_id,
            message=f"任务依赖错误: 依赖任务 #{dependency_id} {reason}",
            details={
                "task_id": task_id,
                "dependency_id": dependency_id,
                "reason": reason
            }
        )


# ============================================================================
# LLM 相关异常
# ============================================================================

class LLMError(AgentError):
    """LLM 相关异常基类"""
    def __init__(self, model: str, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"LLM '{model}' 错误: {message}",
            code="LLM_ERROR",
            details={"model": model, **(details or {})}
        )


class LLMConnectionError(LLMError):
    """LLM 连接异常"""
    def __init__(self, model: str, error: Exception):
        super().__init__(
            model=model,
            message=f"连接失败: {str(error)}",
            details={
                "model": model,
                "error_type": type(error).__name__,
                "error_message": str(error)
            }
        )


class LLMTimeoutError(LLMError):
    """LLM 响应超时异常"""
    def __init__(self, model: str, timeout_seconds: float):
        super().__init__(
            model=model,
            message=f"响应超时 ({timeout_seconds}秒)",
            details={
                "model": model,
                "timeout_seconds": timeout_seconds
            }
        )


class LLMRateLimitError(LLMError):
    """LLM 速率限制异常"""
    def __init__(self, model: str, retry_after: Optional[int] = None):
        details = {"model": model}
        if retry_after is not None:
            details["retry_after_seconds"] = retry_after
            
        super().__init__(
            model=model,
            message="达到速率限制" + (f"，请在 {retry_after} 秒后重试" if retry_after else ""),
            details=details
        )


class LLMContentFilterError(LLMError):
    """LLM 内容过滤异常"""
    def __init__(self, model: str, reason: str):
        super().__init__(
            model=model,
            message=f"内容被过滤: {reason}",
            details={
                "model": model,
                "reason": reason
            }
        )


# ============================================================================
# 配置相关异常
# ============================================================================

class ConfigError(AgentError):
    """配置相关异常基类"""
    def __init__(self, config_key: str, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"配置 '{config_key}' 错误: {message}",
            code="CONFIG_ERROR",
            details={"config_key": config_key, **(details or {})}
        )


class ConfigNotFoundError(ConfigError):
    """配置未找到异常"""
    def __init__(self, config_key: str):
        super().__init__(
            config_key=config_key,
            message="配置项不存在"
        )


class ConfigValidationError(ConfigError):
    """配置验证异常"""
    def __init__(self, config_key: str, value: Any, reason: str):
        super().__init__(
            config_key=config_key,
            message=f"配置验证失败: {value} ({reason})",
            details={
                "config_key": config_key,
                "value": str(value),
                "reason": reason
            }
        )


# ============================================================================
# 文件系统相关异常
# ============================================================================

class FileSystemError(AgentError):
    """文件系统相关异常基类"""
    def __init__(self, path: str, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"文件系统错误 '{path}': {message}",
            code="FILE_SYSTEM_ERROR",
            details={"path": path, **(details or {})}
        )


class FileNotFoundError(FileSystemError):
    """文件未找到异常"""
    def __init__(self, path: str):
        super().__init__(
            path=path,
            message="文件不存在"
        )


class FilePermissionError(FileSystemError):
    """文件权限异常"""
    def __init__(self, path: str, operation: str):
        super().__init__(
            path=path,
            message=f"权限不足，无法执行 {operation} 操作"
        )


class FileReadError(FileSystemError):
    """文件读取异常"""
    def __init__(self, path: str, error: Exception):
        super().__init__(
            path=path,
            message=f"读取失败: {str(error)}",
            details={
                "path": path,
                "error_type": type(error).__name__,
                "error_message": str(error)
            }
        )


class FileWriteError(FileSystemError):
    """文件写入异常"""
    def __init__(self, path: str, error: Exception):
        super().__init__(
            path=path,
            message=f"写入失败: {str(error)}",
            details={
                "path": path,
                "error_type": type(error).__name__,
                "error_message": str(error)
            }
        )


# ============================================================================
# 网络相关异常
# ============================================================================

class NetworkError(AgentError):
    """网络相关异常基类"""
    def __init__(self, url: str, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"网络错误 '{url}': {message}",
            code="NETWORK_ERROR",
            details={"url": url, **(details or {})}
        )


class NetworkConnectionError(NetworkError):
    """网络连接异常"""
    def __init__(self, url: str, error: Exception):
        super().__init__(
            url=url,
            message=f"连接失败: {str(error)}",
            details={
                "url": url,
                "error_type": type(error).__name__,
                "error_message": str(error)
            }
        )


class NetworkTimeoutError(NetworkError):
    """网络超时异常"""
    def __init__(self, url: str, timeout_seconds: float):
        super().__init__(
            url=url,
            message=f"请求超时 ({timeout_seconds}秒)",
            details={
                "url": url,
                "timeout_seconds": timeout_seconds
            }
        )


# ============================================================================
# 工具函数
# ============================================================================

def handle_agent_errors(func):
    """
    错误处理装饰器
    
    使用示例:
        @handle_agent_errors
        async def my_function():
            # 函数代码
            pass
    """
    import functools
    
    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except AgentError:
            # 已知的 AgentError，直接抛出
            raise
        except Exception as e:
            # 未知异常，包装为 AgentError
            raise AgentError.from_exception(e)
    
    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except AgentError:
            raise
        except Exception as e:
            raise AgentError.from_exception(e)
    
    # 根据函数类型返回合适的包装器
    import inspect
    if inspect.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper


def safe_execute(func, default_return=None, raise_agent_error=True):
    """
    安全执行函数，捕获所有异常
    
    Args:
        func: 要执行的函数
        default_return: 发生异常时的默认返回值
        raise_agent_error: 是否将异常转换为 AgentError
    
    Returns:
        函数执行结果或默认返回值
    """
    try:
        return func()
    except AgentError:
        if raise_agent_error:
            raise
        return default_return
    except Exception as e:
        if raise_agent_error:
            raise AgentError.from_exception(e)
        return default_return


async def safe_execute_async(func, default_return=None, raise_agent_error=True):
    """
    安全执行异步函数
    """
    try:
        return await func()
    except AgentError:
        if raise_agent_error:
            raise
        return default_return
    except Exception as e:
        if raise_agent_error:
            raise AgentError.from_exception(e)
        return default_return


def is_agent_error(error: Exception) -> bool:
    """检查异常是否为 AgentError 或其子类"""
    return isinstance(error, AgentError)


def get_error_code(error: Exception) -> str:
    """获取错误代码，如果不是 AgentError 则返回 'UNKNOWN_ERROR'"""
    if is_agent_error(error):
        return error.code
    return "UNKNOWN_ERROR"


def format_error_for_user(error: Exception) -> str:
    """
    格式化错误信息给用户显示
    
    返回友好的错误信息，隐藏技术细节
    """
    if is_agent_error(error):
        # 对于已知错误，显示友好信息
        return f"错误: {error.message}"
    else:
        # 对于未知错误，显示通用信息
        return "系统发生未知错误，请稍后重试"


def format_error_for_logging(error: Exception) -> Dict[str, Any]:
    """
    格式化错误信息用于日志记录
    
    返回包含所有技术细节的字典
    """
    if is_agent_error(error):
        return error.to_dict()
    else:
        return {
            "error": True,
            "code": "UNKNOWN_ERROR",
            "message": str(error),
            "type": type(error).__name__,
            "stack_trace": traceback.format_exc()
        }


# ============================================================================
# 生命周期管理相关异常
# ============================================================================

class LifecycleError(AgentError):
    """
    生命周期管理异常
    
    当生命周期管理系统（心跳、守护等）发生错误时抛出。
    """
    
    def __init__(self, message: str, component: str = "lifecycle", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            code="LIFECYCLE_ERROR",
            details={
                "component": component,
                "system": "lifecycle_management",
                **(details or {})
            }
        )


class HeartbeatError(LifecycleError):
    """心跳系统异常"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"心跳系统错误: {message}",
            component="heartbeat",
            details=details
        )


class GuardSystemError(LifecycleError):
    """守护系统异常"""
    def __init__(self, message: str, service_name: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        details = details or {}
        if service_name:
            details["service_name"] = service_name
            
        super().__init__(
            message=f"守护系统错误: {message}",
            component="guard_system",
            details=details
        )