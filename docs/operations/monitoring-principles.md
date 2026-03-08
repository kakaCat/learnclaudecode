# 外部监控实现原理

## 核心概念

外部监控是指**在 Agent 主进程之外**运行的监控程序，用于检测和恢复主进程崩溃。

```
┌─────────────────────────────────────┐
│  外部监控进程 (独立运行)             │
│  ├─ 监控 Agent 进程状态              │
│  ├─ 检测崩溃/无响应                  │
│  └─ 自动重启 Agent                   │
└─────────────────────────────────────┘
         ↓ 监控
┌─────────────────────────────────────┐
│  Agent 主进程                        │
│  ├─ 心跳系统 (进程内)                │
│  ├─ 守护系统 (进程内)                │
│  └─ 业务逻辑                         │
└─────────────────────────────────────┘
```

## 实现方案

### 1. 父进程监控子进程

**原理：**
- 父进程启动 Agent 作为子进程
- 使用 `subprocess.Popen()` 创建子进程
- 通过 `process.wait()` 监控子进程退出
- 子进程退出后自动重启

**关键代码：**
```python
while True:
    process = subprocess.Popen(["python", "agent.py"])
    exit_code = process.wait()  # 阻塞等待子进程退出
    if exit_code != 0:
        print("Agent 崩溃，5秒后重启...")
        time.sleep(5)
```

**优点：**
- 简单易实现
- 跨平台
- 不需要额外依赖

**缺点：**
- 功能有限
- 无法检测卡死（只能检测退出）

---

### 2. 健康检查监控

**原理：**
- Agent 提供 HTTP 健康检查端点
- 外部监控定期发送 HTTP 请求
- 连续失败达到阈值时重启 Agent

**关键代码：**
```python
# Agent 端：提供健康检查
@app.route('/health')
def health():
    return {"status": "ok", "timestamp": "..."}

# 监控端：定期检查
while True:
    response = requests.get("http://localhost:8000/health")
    if response.status_code != 200:
        failure_count += 1
        if failure_count >= 3:
            restart_agent()
    time.sleep(30)
```

**优点：**
- 可以检测卡死（无响应）
- 可以获取详细状态信息
- 精确控制

**缺点：**
- 需要 Agent 支持 HTTP 端点
- 需要额外的网络请求

---

### 3. Supervisor（进程管理工具）

**原理：**
- Supervisor 是专业的进程管理工具
- 通过配置文件管理进程
- 自动监控和重启

**配置示例：**
```ini
[program:agent]
command=python agent.py
autostart=true
autorestart=true
startretries=3
```

**使用命令：**
```bash
supervisorctl start agent
supervisorctl status agent
```

**优点：**
- 功能完整
- 配置简单
- 日志管理
- Web 界面

**缺点：**
- 需要安装
- 配置相对复杂

---

### 4. systemd（系统服务）

**原理：**
- systemd 是 Linux 系统的服务管理器
- 将 Agent 注册为系统服务
- 系统级监控和重启

**配置示例：**
```ini
[Service]
ExecStart=/usr/bin/python3 agent.py
Restart=always
RestartSec=10
```

**使用命令：**
```bash
systemctl start agent
systemctl enable agent  # 开机自启
```

**优点：**
- 系统级管理
- 开机自启
- 资源限制
- 日志集成

**缺点：**
- 仅 Linux
- 需要 root 权限

---

## 工作流程对比

### 父进程监控
```
1. 启动监控脚本
2. 监控脚本启动 Agent 子进程
3. 监控脚本等待子进程退出
4. 子进程退出 → 检查退出码
5. 如果异常退出 → 等待 N 秒 → 重启
6. 重复步骤 2-5
```

### 健康检查监控
```
1. Agent 启动并开启健康检查端点
2. 监控脚本定期发送 HTTP 请求
3. 如果请求失败 → 失败计数 +1
4. 如果连续失败 ≥ 阈值 → 触发重启
5. 重启 Agent
6. 重复步骤 2-5
```

### Supervisor/systemd
```
1. 配置服务
2. 启动服务
3. 系统自动监控进程状态
4. 进程退出 → 自动重启
5. 持续监控
```

---

## 实际效果演示

### 场景：Agent 崩溃

**无外部监控：**
```
[Agent] 启动成功
[Agent] 处理任务...
[Agent] ❌ 崩溃！
→ 进程终止，需要手动重启
```

**有外部监控（父进程）：**
```
[Supervisor] 启动 Agent (PID: 12345)
[Agent] 启动成功
[Agent] 处理任务...
[Agent] ❌ 崩溃！
[Supervisor] 检测到子进程异常退出 (exit code: 1)
[Supervisor] 等待 5 秒后重启...
[Supervisor] 启动 Agent (PID: 12346)
[Agent] 启动成功
→ 自动恢复运行
```

**有外部监控（健康检查）：**
```
[Agent] 启动成功，健康检查端点: :8000/health
[Monitor] 健康检查通过 ✓
[Monitor] 健康检查通过 ✓
[Agent] ❌ 崩溃！
[Monitor] 健康检查失败 ✗ (连接失败)
[Monitor] 健康检查失败 ✗ (连接失败)
[Monitor] 健康检查失败 ✗ (连接失败)
[Monitor] 达到失败阈值，触发重启
[Monitor] 执行重启命令...
[Agent] 启动成功
[Monitor] 健康检查通过 ✓
→ 自动恢复运行
```

---

## 最佳实践

### 1. 双重保障
```
进程内监控（心跳+守护）+ 外部监控（Supervisor）
```

### 2. 分层监控
```
- 进程内：监控会话、服务、资源
- 进程外：监控进程存活、健康状态
```

### 3. 告警通知
```python
def on_restart(reason):
    send_alert(f"Agent 重启: {reason}")
```

### 4. 日志记录
```python
# 记录每次重启
log_restart(timestamp, reason, exit_code)
```

---

## 总结

| 监控类型 | 检测范围 | 恢复能力 | 适用场景 |
|---------|---------|---------|---------|
| 进程内（心跳） | 会话超时 | ✓ | 会话管理 |
| 进程内（守护） | 服务健康、资源 | ✓ 部分 | 服务监控 |
| 进程外（父进程） | 进程崩溃 | ✓ | 开发测试 |
| 进程外（健康检查） | 进程卡死 | ✓ | 生产环境 |
| 进程外（Supervisor） | 进程崩溃 | ✓ | 生产环境 |
| 进程外（systemd） | 进程崩溃 | ✓ | Linux 服务器 |

**核心要点：**
- 进程内监控无法处理主进程崩溃
- 外部监控是必需的补充
- 生产环境建议使用 Supervisor 或 systemd
- 健康检查可以检测卡死，不仅仅是崩溃
