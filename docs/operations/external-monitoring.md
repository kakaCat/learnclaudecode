# 外部监控使用指南

## 📋 概述

外部监控用于在 Agent 主进程崩溃时自动重启，弥补进程内监控的不足。

## 🚀 方案对比

| 方案 | 适用场景 | 优点 | 缺点 |
|------|---------|------|------|
| 父进程监控 | 开发/测试 | 简单、跨平台 | 功能有限 |
| 健康检查 | 生产环境 | 精确检测 | 需要 HTTP 端点 |
| Supervisor | 生产环境 | 功能完整、易配置 | 需要安装 |
| systemd | Linux 服务器 | 系统级、开机自启 | 仅 Linux |

---

## 方案1：父进程监控

### 使用方法

```bash
# 启动监控
python scripts/supervisor.py
```

### 工作原理

```
┌─────────────────────────────────┐
│  supervisor.py (父进程)          │
│  ├─ 启动 agent.py (子进程)       │
│  ├─ 监控子进程状态               │
│  ├─ 子进程退出 → 自动重启        │
│  └─ 达到最大重启次数 → 停止      │
└─────────────────────────────────┘
```

### 特性

- ✅ 自动重启崩溃的进程
- ✅ 检测快速崩溃（10秒内退出）
- ✅ 连续崩溃时增加重启延迟
- ✅ 实时输出子进程日志
- ✅ 优雅停止（Ctrl+C）

### 配置参数

```python
supervisor = ProcessSupervisor(
    command=["python", "backend/app/agent.py"],
    max_restarts=10,        # 最大重启次数
    restart_delay=5,        # 重启延迟（秒）
    crash_threshold=3       # 快速崩溃阈值
)
```

---

## 方案2：健康检查监控

### 第一步：在 Agent 中启动健康检查端点

```python
# 在 agent.py 中添加
from backend.app.health_endpoint import start_health_server

class AgentService:
    def __init__(self):
        # 启动健康检查服务器
        start_health_server(port=8000)
```

### 第二步：启动健康监控

```bash
# 启动监控
python scripts/health_monitor.py
```

### 工作原理

```
┌──────────────────────────────────┐
│  health_monitor.py               │
│  ├─ 每30秒检查 /health 端点      │
│  ├─ 连续3次失败 → 触发重启       │
│  └─ 重启 agent.py                │
└──────────────────────────────────┘
         ↓ HTTP GET
┌──────────────────────────────────┐
│  agent.py (Flask /health)        │
│  返回: {"status": "ok", ...}     │
└──────────────────────────────────┘
```

### 健康检查端点

```bash
# 手动测试
curl http://localhost:8000/health

# 返回示例
{
  "status": "ok",
  "agent_status": "running",
  "timestamp": "2026-03-08T15:46:26",
  "uptime_seconds": 3600,
  "memory_mb": 256.5,
  "cpu_percent": 12.3,
  "pid": 12345
}
```

### 配置参数

```python
monitor = HealthMonitor(
    health_url="http://localhost:8000/health",
    check_interval=30,      # 检查间隔（秒）
    timeout=5,              # 请求超时（秒）
    max_failures=3          # 失败阈值
)
```

---

## 方案3：Supervisor（推荐生产环境）

### 安装

```bash
# macOS
brew install supervisor

# Ubuntu/Debian
sudo apt-get install supervisor

# CentOS/RHEL
sudo yum install supervisor
```

### 配置

```bash
# 复制配置文件
sudo cp deploy/supervisor.conf /etc/supervisor/conf.d/agent.conf

# 重新加载配置
sudo supervisorctl reread
sudo supervisorctl update
```

### 使用命令

```bash
# 启动
sudo supervisorctl start agent

# 停止
sudo supervisorctl stop agent

# 重启
sudo supervisorctl restart agent

# 查看状态
sudo supervisorctl status agent

# 查看日志
sudo supervisorctl tail -f agent
```

### 特性

- ✅ 自动重启
- ✅ 日志管理
- ✅ 进程组管理
- ✅ Web 管理界面
- ✅ 开机自启

---

## 方案4：systemd（Linux 服务器）

### 安装

```bash
# 复制服务文件
sudo cp deploy/agent.service /etc/systemd/system/

# 重新加载 systemd
sudo systemctl daemon-reload

# 启用开机自启
sudo systemctl enable agent
```

### 使用命令

```bash
# 启动
sudo systemctl start agent

# 停止
sudo systemctl stop agent

# 重启
sudo systemctl restart agent

# 查看状态
sudo systemctl status agent

# 查看日志
sudo journalctl -u agent -f
```

### 特性

- ✅ 系统级管理
- ✅ 开机自启
- ✅ 资源限制（内存、CPU）
- ✅ 日志集成（journald）
- ✅ 依赖管理

---

## 🔧 实战示例

### 场景1：开发环境快速测试

```bash
# 使用父进程监控
python scripts/supervisor.py
```

### 场景2：生产环境部署

```bash
# 1. 启动健康检查端点（在 agent.py 中）
# 2. 使用 Supervisor 管理进程
sudo supervisorctl start agent

# 3. 启动健康监控（可选，双重保障）
nohup python scripts/health_monitor.py > health_monitor.log 2>&1 &
```

### 场景3：Linux 服务器

```bash
# 使用 systemd
sudo systemctl start agent
sudo systemctl enable agent
```

---

## 📊 监控效果对比

### 无外部监控

```
Agent 崩溃 → ❌ 停止运行 → 需要手动重启
```

### 有外部监控

```
Agent 崩溃 → ✅ 自动检测 → ✅ 自动重启 → ✅ 恢复运行
```

---

## 💡 最佳实践

### 1. 双重保障

```
进程内监控（心跳+守护） + 外部监控（Supervisor）
```

### 2. 日志管理

```bash
# 配置日志轮转
/var/log/agent/*.log {
    daily
    rotate 7
    compress
    missingok
}
```

### 3. 告警通知

```python
# 在监控脚本中添加告警
def send_alert(message):
    # 发送邮件/Slack/钉钉通知
    pass
```

### 4. 资源限制

```ini
# supervisor.conf
[program:agent]
; 限制内存
rlimit_as=2147483648  ; 2GB
```

---

## 🐛 故障排查

### 问题1：健康检查失败

```bash
# 检查端口是否监听
lsof -i :8000

# 检查防火墙
sudo ufw status

# 手动测试
curl -v http://localhost:8000/health
```

### 问题2：Supervisor 无法启动

```bash
# 查看详细日志
sudo supervisorctl tail agent stderr

# 检查配置
sudo supervisorctl reread
```

### 问题3：systemd 服务失败

```bash
# 查看详细状态
sudo systemctl status agent -l

# 查看日志
sudo journalctl -u agent -n 50
```

---

## 📈 监控指标

### 关键指标

- 重启次数
- 平均运行时长
- 崩溃频率
- 资源使用（CPU/内存）
- 健康检查响应时间

### 查看统计

```bash
# Supervisor
sudo supervisorctl status

# systemd
sudo systemctl show agent
```
