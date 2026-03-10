# Exceptions Package

统一的异常处理包，提供 Agent 系统所有异常类型。

## 结构

```
backend/app/exceptions/
├── __init__.py          # 包入口，导出所有异常类
└── exceptions.py        # 异常类定义
```

## 使用方式

```python
# 导入异常类
from backend.app.exceptions import (
    AgentError,
    ToolError,
    SessionError,
    MemoryError,
    # ... 其他异常
)

# 使用装饰器
from backend.app.exceptions import handle_agent_errors

@handle_agent_errors
async def my_function():
    # 函数代码
    pass

# 安全执行
from backend.app.exceptions import safe_execute

result = safe_execute(lambda: risky_operation())
```

## 异常类型

### 基础异常
- `AgentError` - 所有异常的基类

### 工具相关
- `ToolError`
- `ToolExecutionError`
- `ToolNotFoundError`
- `ToolValidationError`
- `ToolTimeoutError`

### Session 相关
- `SessionError`
- `SessionNotFoundError`
- `SessionExpiredError`
- `SessionValidationError`

### 记忆相关
- `MemoryError`
- `MemoryWriteError`
- `MemorySearchError`

### 任务相关
- `TaskError`
- `TaskNotFoundError`
- `TaskValidationError`
- `TaskDependencyError`

### LLM 相关
- `LLMError`
- `LLMConnectionError`
- `LLMTimeoutError`
- `LLMRateLimitError`
- `LLMContentFilterError`

### 配置相关
- `ConfigError`
- `ConfigNotFoundError`
- `ConfigValidationError`

### 文件系统相关
- `FileSystemError`
- `FileNotFoundError`
- `FilePermissionError`
- `FileReadError`
- `FileWriteError`

### 网络相关
- `NetworkError`
- `NetworkConnectionError`
- `NetworkTimeoutError`

### 生命周期相关
- `LifecycleError`
- `HeartbeatError`
- `GuardSystemError`

## 工具函数

- `handle_agent_errors(func)` - 错误处理装饰器
- `safe_execute(func, default_return, raise_agent_error)` - 安全执行函数
- `safe_execute_async(func, default_return, raise_agent_error)` - 安全执行异步函数
- `is_agent_error(error)` - 检查是否为 AgentError
- `get_error_code(error)` - 获取错误代码
- `format_error_for_user(error)` - 格式化用户友好的错误信息
- `format_error_for_logging(error)` - 格式化日志记录的错误信息
