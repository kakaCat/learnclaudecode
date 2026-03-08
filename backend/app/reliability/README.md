# Reliability Package - 可靠性保障系统

确保 Agent 持续运行的完整解决方案。

## 🎯 核心功能

### 1. 心跳监控 (Heartbeat)
- 每5分钟检查会话状态
- 自动清理过期会话
- 记录心跳指标

### 2. 守护系统 (Guards)
- 每60秒监控资源使用
- 检查服务健康状态
- 自动恢复失败服务

### 3. 自动重启 (Restart)
- 响应重启信号
- 保存状态后重启
- 记录重启日志

### 4. 生命周期管理 (Lifecycle)
- 统一管理所有系统
- 协调启动和停止
- 状态监控

### 5. 健康检查 (Health)
- HTTP 端点 `/health`
- 返回运行状态
- 供外部监控使用

## 🚀 快速开始

```python
from backend.app.reliability import start_lifecycle, start_health_server

# 启动所有系统
start_health_server(port=8000)
start_lifecycle()
```

## 📊 架构

```
┌─────────────────────────────────────┐
│  Lifecycle Manager (生命周期管理)    │
├─────────────────────────────────────┤
│  ├─ Heartbeat (心跳)                │
│  ├─ Guards (守护)                   │
│  ├─ Restart (重启)                  │
│  └─ Health (健康检查)               │
└─────────────────────────────────────┘
```

## 📖 详细文档

- [使用指南](../../../docs/operations/agent-daemon.md)
- [监控原理](../../../docs/operations/monitoring-principles.md)
- [外部监控](../../../docs/operations/external-monitoring.md)
