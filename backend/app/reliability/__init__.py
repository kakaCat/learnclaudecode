"""
可靠性保障包 - 确保 Agent 持续运行

包含：
- 心跳监控：定期检查会话状态
- 守护系统：监控资源和服务健康
- 自动重启：进程崩溃时自动恢复
- 生命周期管理：统一管理所有维持系统
- 健康检查：提供 HTTP 端点供外部监控
"""

# 心跳系统
from .heartbeat import (
    HeartbeatSystem,
    get_global_heartbeat,
    start_global_heartbeat,
    stop_global_heartbeat,
    get_heartbeat_status,
    is_heartbeat_healthy
)

# 守护系统
from .guards import (
    GuardSystem,
    get_global_guard,
    start_global_guard,
    stop_global_guard,
    get_guard_status,
    is_system_healthy,
    register_service_guard,
    update_service_health
)

# 自动重启
from .restart import (
    RestartManager,
    get_restart_manager,
    request_restart,
    is_restart_requested,
    get_restart_logs
)

# 生命周期管理
from .lifecycle import (
    LifecycleManager,
    get_global_lifecycle,
    start_lifecycle,
    stop_lifecycle,
    get_lifecycle_status
)

# 健康检查
from .health import (
    start_health_server,
    update_status
)

# 性能监控
from .monitoring import (
    PerformanceMonitor,
    PerformanceMetrics
)

# 异常处理
from .exceptions import (
    AgentError,
    ToolError,
    SessionError,
    MemoryError,
    TaskError,
    LLMError,
    ConfigError,
    FileSystemError,
    NetworkError,
    LifecycleError
)

__all__ = [
    # 心跳
    'HeartbeatSystem',
    'get_global_heartbeat',
    'start_global_heartbeat',
    'stop_global_heartbeat',
    'get_heartbeat_status',
    'is_heartbeat_healthy',

    # 守护
    'GuardSystem',
    'get_global_guard',
    'start_global_guard',
    'stop_global_guard',
    'get_guard_status',
    'is_system_healthy',
    'register_service_guard',
    'update_service_health',

    # 重启
    'RestartManager',
    'get_restart_manager',
    'request_restart',
    'is_restart_requested',
    'get_restart_logs',

    # 生命周期
    'LifecycleManager',
    'get_global_lifecycle',
    'start_lifecycle',
    'stop_lifecycle',
    'get_lifecycle_status',

    # 健康检查
    'start_health_server',
    'update_status',

    # 性能监控
    'PerformanceMonitor',
    'PerformanceMetrics',

    # 异常处理
    'AgentError',
    'ToolError',
    'SessionError',
    'MemoryError',
    'TaskError',
    'LLMError',
    'ConfigError',
    'FileSystemError',
    'NetworkError',
    'LifecycleError',
]
