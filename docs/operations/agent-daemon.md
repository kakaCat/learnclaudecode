# Agent 持续运行指南

## 📦 包结构

```
backend/app/reliability/          # 可靠性保障包
├── __init__.py                   # 统一接口
├── heartbeat.py                  # 心跳监控
├── guards.py                     # 守护系统
├── restart.py                    # 自动重启
├── lifecycle.py                  # 生命周期管理
└── health.py                     # 健康检查端点
```

## 🚀 快速启动

### 方式1：使用守护进程启动器（推荐）

```bash
python scripts/run_agent_daemon.py
```

**包含功能：**
- ✅ 心跳监控（每5分钟）
- ✅ 守护系统（每60秒）
- ✅ 健康检查端点（:8000/health）
- ✅ 自动重启支持
- ✅ 优雅关闭

### 方式2：配合外部监控

```bash
# 终端1：启动 Agent
python scripts/run_agent_daemon.py

# 终端2：启动外部监控
python scripts/supervisor.py
```

### 方式3：生产环境（Supervisor）

```bash
sudo supervisorctl start agent
```

## 📊 监控端点

```bash
# 健康检查
curl http://localhost:8000/health

# 返回示例
{
  "status": "ok",
  "agent_status": "running",
  "uptime_seconds": 3600,
  "memory_mb": 256.5,
  "cpu_percent": 12.3
}
```

## 🔧 代码集成

```python
from backend.app.reliability import (
    start_lifecycle,
    start_health_server,
    get_restart_manager
)

# 启动健康检查
start_health_server(port=8000)

# 启动生命周期管理
start_lifecycle()

# 获取重启管理器
restart_manager = get_restart_manager()
```

## 🛡️ 可靠性保障

### 进程内监控
- **心跳系统**：检查会话超时，自动保存状态
- **守护系统**：监控资源使用，检查服务健康

### 进程外监控
- **父进程监控**：检测崩溃，自动重启
- **健康检查**：HTTP 端点供外部监控

## 📝 完整示例

```python
#!/usr/bin/env python3
from backend.app.reliability import start_lifecycle, start_health_server
from backend.app.agent import AgentService

# 1. 启动健康检查
start_health_server(port=8000)

# 2. 启动生命周期管理
start_lifecycle()

# 3. 创建 Agent
agent = AgentService(enable_lifecycle=True)

# 4. 运行
import asyncio
response = asyncio.run(agent.run("你好"))
print(response)
```

## 🎯 总结

**三层保障：**
1. **进程内** - 心跳 + 守护
2. **进程外** - 外部监控
3. **系统级** - Supervisor/systemd

**一键启动：**
```bash
python scripts/run_agent_daemon.py
```

Agent 将持续运行，自动处理故障和恢复！
