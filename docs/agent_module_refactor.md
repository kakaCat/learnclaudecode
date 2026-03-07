# Agent 模块重构说明

## 目录结构

```
backend/app/agent/
├── __init__.py              # 模块入口
├── service.py               # AgentService 核心实现（待创建）
├── context_guard.py         # 上下文保护和压缩策略 ✅
├── handlers.py              # 消息处理链（待创建）
└── strategies.py            # 额外的策略实现（可选）
```

## 模块职责

### 1. context_guard.py ✅
**职责**: 上下文溢出保护和压缩策略

**包含**:
- `CompactionStrategy` - 压缩策略抽象基类
- `MicroCompactionStrategy` - 微压缩策略
- `AutoCompactionStrategy` - 自动压缩策略
- `ManualCompactionStrategy` - 手动压缩策略
- `ContextGuard` - 上下文保护管理器

**使用**:
```python
from backend.app.agent.context_guard import (
    ContextGuard,
    MicroCompactionStrategy,
    AutoCompactionStrategy,
    ManualCompactionStrategy
)

guard = ContextGuard(max_tokens=180000)
guard.add_strategy(MicroCompactionStrategy())
guard.add_strategy(AutoCompactionStrategy(threshold=50000))
guard.add_strategy(ManualCompactionStrategy())

history = guard.apply_strategies(history, llm)
```

### 2. service.py（待创建）
**职责**: AgentService 核心实现

**包含**:
- `AgentService` - 主 Agent 服务类
- `_build_agent()` - Agent 构建函数
- `_log()`, `_fmt_args()` - 辅助函数

**迁移自**: `backend/app/agent.py`

### 3. handlers.py（待创建）
**职责**: 消息处理链（责任链模式）

**包含**:
- `MessageHandler` - 消息处理器抽象基类
- `InboxInjectionHandler` - Inbox 消息注入
- `BackgroundNotificationHandler` - 后台任务通知
- `ReminderHandler` - 提醒消息注入

**参考**: `backend/app/agent_refactor.py`

### 4. strategies.py（可选）
**职责**: 额外的压缩策略实现

**包含**:
- 自定义压缩策略
- 特殊场景的压缩逻辑

## 迁移计划

### 阶段 1: 创建 service.py ✅ 待执行
```bash
# 将 agent.py 中的 AgentService 迁移到 agent/service.py
# 更新导入路径
```

### 阶段 2: 创建 handlers.py（可选）
```bash
# 从 agent_refactor.py 提取责任链模式代码
# 集成到 service.py
```

### 阶段 3: 更新导入路径
```bash
# 更新所有引用 agent.py 的地方
# 改为 from backend.app.agent import AgentService
```

### 阶段 4: 清理旧文件
```bash
# 备份 agent.py 和 agent_refactor.py
# 移到 archive/ 或删除
```

## 导入路径变更

### 旧路径
```python
from backend.app.agent import AgentService
from backend.app.context_guard import ContextGuard
```

### 新路径
```python
from backend.app.agent import AgentService
from backend.app.agent.context_guard import ContextGuard
```

## 向后兼容

为了保持向后兼容，在 `backend/app/agent/__init__.py` 中导出所有公共接口：

```python
from backend.app.agent.service import AgentService
from backend.app.agent.context_guard import (
    ContextGuard,
    CompactionStrategy,
    MicroCompactionStrategy,
    AutoCompactionStrategy,
    ManualCompactionStrategy
)

__all__ = [
    "AgentService",
    "ContextGuard",
    "CompactionStrategy",
    "MicroCompactionStrategy",
    "AutoCompactionStrategy",
    "ManualCompactionStrategy",
]
```

## 优势

1. **模块化** - 相关代码组织在一起
2. **职责清晰** - 每个文件职责明确
3. **易于维护** - 代码结构清晰
4. **易于测试** - 模块独立测试
5. **易于扩展** - 新增功能不影响现有代码

## 下一步

1. ✅ 创建 `agent/` 目录
2. ✅ 移动 `context_guard.py` 到 `agent/`
3. ⏳ 创建 `agent/service.py`（迁移 AgentService）
4. ⏳ 更新导入路径
5. ⏳ 测试验证
6. ⏳ 清理旧文件
