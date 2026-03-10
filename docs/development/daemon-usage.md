# 开发环境守护系统使用指南

## 📖 概述

开发环境的守护系统通过**后台线程**方式运行，提供心跳监控、资源守护、健康检查等功能。

## 🏗️ 架构

```
主进程 (Main Process)
│
├── 主线程 (Main Thread)
│   └── 你的 Agent 业务逻辑
│
└── 守护线程 (Daemon Threads)
    ├── 心跳线程 (Heartbeat Thread)
    │   └── 每 5 分钟检查会话状态
    │
    ├── 守护线程 (Guard Thread)
    │   └── 每 60 秒监控资源使用
    │
    └── 健康检查线程 (Health Check Thread)
        └── HTTP 端点: http://localhost:8000/health
```

## 🚀 快速开始

### 方式 1: 使用启动脚本（推荐）

```bash
python scripts/start_with_daemon.py
```

**功能**：
- ✅ 自动启动所有守护线程
- ✅ 全局异常捕获
- ✅ 优雅关闭（Ctrl+C）
- ✅ 状态监控

### 方式 2: 在代码中集成

```python
from backend.app.reliability import (
    start_lifecycle,
    stop_lifecycle,
    get_lifecycle_status
)

# 启动守护系统
start_lifecycle()

# 运行你的主逻辑
try:
    run_your_agent()
finally:
    # 关闭守护系统
    stop_lifecycle(graceful=True)
```

## 📊 监控功能

### 1. 心跳系统

**功能**：
- 每 5 分钟检查会话状态
- 自动清理过期会话
- 记录心跳指标

**查看状态**：
```python
from backend.app.reliability import get_heartbeat_status

status = get_heartbeat_status()
print(f"心跳状态: {status['status']}")
print(f"总心跳数: {status['metrics']['total_beats']}")
print(f"成功率: {status['metrics']['success_rate']*100:.1f}%")
```

### 2. 守护系统

**功能**：
- 每 60 秒监控资源使用（CPU、内存、磁盘、线程）
- 检查服务健康状态
- 资源超限告警

**查看状态**：
```python
from backend.app.reliability import get_guard_status

status = get_guard_status()
print(f"守护状态: {status['status']}")
print(f"CPU 使用: {status['current_resources']['cpu_percent']:.1f}%")
print(f"内存使用: {status['current_resources']['memory_percent']:.1f}%")
```

### 3. 健康检查

**HTTP 端点**：
```bash
curl http://localhost:8000/health
```

**返回示例**：
```json
{
  "status": "running",
  "start_time": "2026-03-09T14:34:33.395297",
  "last_heartbeat": "2026-03-09T14:35:00.123456",
  "request_count": 42
}
```

### 4. 生命周期状态

**查看完整状态**：
```python
from backend.app.reliability import get_lifecycle_status

status = get_lifecycle_status()
print(f"运行状态: {status['is_running']}")
print(f"运行时长: {status['uptime_seconds']:.1f}秒")
print(f"心跳状态: {status['heartbeat']['status']}")
print(f"守护状态: {status['guard']['status']}")
```

## 🧪 测试

运行测试脚本：
```bash
python scripts/test_daemon.py
```

**测试内容**：
- ✅ 守护线程启动
- ✅ 心跳系统运行
- ✅ 守护系统监控
- ✅ 健康检查端点
- ✅ 状态查询

## ⚠️ 注意事项

### 优点
- ✅ 实现简单，易于集成
- ✅ 开发环境快速启动
- ✅ 主逻辑异常不影响守护线程

### 限制
- ⚠️ **主进程崩溃时守护线程也会停止**
  - 段错误（Segmentation Fault）
  - OOM Killer
  - `kill -9` 强制杀死

- ⚠️ **无法监控主进程本身**
  - 守护线程运行在主进程内
  - 无法在主进程挂掉后重启

### 适用场景
- ✅ 开发环境
- ✅ 本地测试
- ✅ 快速原型

### 不适用场景
- ❌ 生产环境（建议使用独立守护进程或 systemd）
- ❌ 需要进程级别监控和重启
- ❌ 高可用性要求

## 🔧 自定义配置

### 修改心跳间隔

编辑 `backend/app/reliability/heartbeat.py`:
```python
class HeartbeatSystem:
    def __init__(self, interval: int = 300):  # 默认 300 秒
        self.interval = interval  # 修改为你需要的间隔
```

### 修改守护检查间隔

编辑 `backend/app/reliability/guards.py`:
```python
class GuardSystem:
    def __init__(self, check_interval: int = 60):  # 默认 60 秒
        self.check_interval = check_interval
```

### 修改资源阈值

编辑 `backend/app/reliability/guards.py`:
```python
class GuardSystem:
    def __init__(self, ...):
        self.cpu_threshold = 80.0      # CPU 阈值 80%
        self.memory_threshold = 80.0   # 内存阈值 80%
        self.disk_threshold = 90.0     # 磁盘阈值 90%
```

## 📚 API 参考

### 启动和停止

```python
# 启动生命周期管理（包含心跳、守护、健康检查）
start_lifecycle() -> bool

# 停止生命周期管理
stop_lifecycle(graceful: bool = True) -> bool

# 重启生命周期管理
restart_lifecycle() -> bool
```

### 状态查询

```python
# 获取生命周期状态
get_lifecycle_status() -> Dict[str, Any]

# 检查系统是否健康
is_lifecycle_healthy() -> bool

# 获取心跳状态
get_heartbeat_status() -> Dict[str, Any]

# 获取守护状态
get_guard_status() -> Dict[str, Any]
```

### 服务注册

```python
# 注册服务到守护系统
register_service_guard(
    service_name: str,
    recovery_handler: Optional[Callable] = None
) -> bool

# 更新服务健康状态
update_service_health(
    service_name: str,
    is_healthy: bool,
    error: Optional[str] = None
)
```

## 🎯 最佳实践

1. **在主逻辑开始前启动守护系统**
   ```python
   start_lifecycle()
   run_agent()
   ```

2. **使用 try-finally 确保关闭**
   ```python
   try:
       start_lifecycle()
       run_agent()
   finally:
       stop_lifecycle(graceful=True)
   ```

3. **定期检查健康状态**
   ```python
   if not is_lifecycle_healthy():
       logger.warning("守护系统异常")
   ```

4. **注册关键服务**
   ```python
   register_service_guard("my_service", recovery_handler=restart_my_service)
   ```

## 🚀 生产环境方案

生产环境建议使用：
- **独立守护进程**：`scripts/daemon.py`（待实现）
- **systemd**：系统级进程管理
- **supervisor**：进程监控工具
- **Docker + restart policy**：容器自动重启

参考：`docs/operations/production-deployment.md`（待创建）
