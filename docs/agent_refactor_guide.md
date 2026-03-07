# Agent 重构设计说明

## 核心改进

将 `CompactionStrategy` 整合到 `ContextGuard` 中，使用策略模式管理压缩逻辑。

## 设计模式应用

### 1. 策略模式 - 压缩策略（在 ContextGuard 中）

**位置**: `backend/app/context_guard.py`

```python
from backend.app.context_guard import (
    ContextGuard,
    MicroCompactionStrategy,
    AutoCompactionStrategy,
    ManualCompactionStrategy
)

# 创建 ContextGuard 并添加策略
guard = ContextGuard(max_tokens=180000)
guard.add_strategy(MicroCompactionStrategy())
guard.add_strategy(AutoCompactionStrategy(threshold=50000))
guard.add_strategy(ManualCompactionStrategy())

# 应用所有策略
history = guard.apply_strategies(history, llm)
```

**优势**:
- ✅ 单一职责：压缩策略都在 ContextGuard 中
- ✅ 开闭原则：新增策略无需修改现有代码
- ✅ 易于测试：每个策略独立测试
- ✅ 灵活配置：可动态添加/移除策略

### 2. 责任链模式 - 消息处理链

**位置**: `backend/app/agent_refactor.py`

```python
class MessageHandler(ABC):
    """消息处理器抽象基类"""

    def set_next(self, handler: 'MessageHandler') -> 'MessageHandler':
        self.next_handler = handler
        return handler

    @abstractmethod
    def handle(self, history: List, context: Dict) -> List:
        pass

# 构建处理链
inbox_handler = InboxInjectionHandler()
bg_handler = BackgroundNotificationHandler()
reminder_handler = ReminderHandler()

inbox_handler.set_next(bg_handler).set_next(reminder_handler)

# 处理消息
history = inbox_handler.handle(history, context)
```

**优势**:
- ✅ 解耦：每个处理器独立
- ✅ 灵活：可动态调整处理顺序
- ✅ 可扩展：新增处理器不影响现有代码

## 使用示例

### 基础用法

```python
from backend.app.context_guard import (
    ContextGuard,
    MicroCompactionStrategy,
    AutoCompactionStrategy,
    ManualCompactionStrategy
)

class AgentService:
    def __init__(self):
        # 创建 ContextGuard
        self.guard = ContextGuard(max_tokens=180000)

        # 添加压缩策略
        self.guard.add_strategy(MicroCompactionStrategy())
        self.guard.add_strategy(AutoCompactionStrategy(threshold=50000))
        self.guard.add_strategy(ManualCompactionStrategy())

        self.llm = ChatOpenAI(...)

    async def run(self, prompt: str, history: list) -> str:
        # 应用所有压缩策略
        history = self.guard.apply_strategies(history, self.llm)

        # 检查上下文使用率
        tokens = self.guard.estimate_messages_tokens(history)
        if tokens > self.guard.max_tokens * 0.8:
            _log("⚠️", f"Context usage: {tokens:,}/{self.guard.max_tokens:,}")

        # ... 其余逻辑
```

### 自定义策略

```python
from backend.app.context_guard import CompactionStrategy

class AggressiveCompactionStrategy(CompactionStrategy):
    """激进压缩策略 - 压缩前 70%"""

    def should_compact(self, history: List, context: Dict) -> bool:
        guard = context.get("guard")
        tokens = guard.estimate_messages_tokens(history)
        return tokens > guard.max_tokens * 0.7  # 70% 就压缩

    def compact(self, history: List, llm: ChatOpenAI) -> List:
        # 压缩前 70% 的消息
        compress_count = int(len(history) * 0.7)
        old_messages = history[:compress_count]
        recent_messages = history[compress_count:]

        # 生成摘要
        summary = self._generate_summary(old_messages, llm)

        return [
            HumanMessage(content=f"[摘要]\n{summary}"),
            AIMessage(content="已了解。"),
        ] + recent_messages

    def get_kind(self) -> str:
        return "aggressive"

# 使用自定义策略
guard.add_strategy(AggressiveCompactionStrategy())
```

## 对比：重构前 vs 重构后

### 重构前（agent.py）

```python
class AgentService:
    async def run(self, prompt: str, history: list) -> str:
        # Layer 1: micro_compact
        before_micro = len(history)
        micro_compact(history)
        if len(history) < before_micro:
            get_store().save_compaction("main", "micro", before_micro, len(history))

        # Layer 2: auto_compact
        if estimate_tokens(history, self.llm) > THRESHOLD:
            _log("🗜️", "[auto_compact triggered]")
            before_auto = len(history)
            new_history = auto_compact(history, self.llm)
            history.clear()
            history.extend(new_history)
            get_store().save_compaction("main", "auto", before_auto, len(history))

        # Layer 3: manual compact
        if was_compact_requested():
            _log("🗜️", "[manual compact]")
            before_manual = len(history)
            new_history = auto_compact(history, self.llm)
            history.clear()
            history.extend(new_history)
            get_store().save_compaction("main", "manual", before_manual, len(history))

        # ... 200+ 行代码 ...
```

**问题**:
- ❌ 方法太长（300+ 行）
- ❌ 职责不清晰
- ❌ 难以测试
- ❌ 难以扩展

### 重构后（使用 ContextGuard）

```python
class AgentService:
    def __init__(self):
        self.guard = ContextGuard(max_tokens=180000)
        self.guard.add_strategy(MicroCompactionStrategy())
        self.guard.add_strategy(AutoCompactionStrategy(threshold=50000))
        self.guard.add_strategy(ManualCompactionStrategy())

    async def run(self, prompt: str, history: list) -> str:
        # 一行代码应用所有压缩策略
        history = self.guard.apply_strategies(history, self.llm)

        # ... 其余逻辑 ...
```

**优势**:
- ✅ 方法简洁（压缩逻辑 1 行）
- ✅ 职责清晰（压缩在 ContextGuard）
- ✅ 易于测试（策略独立测试）
- ✅ 易于扩展（添加新策略）

## 架构图

```
AgentService
    ↓
ContextGuard (策略管理器)
    ├── MicroCompactionStrategy
    ├── AutoCompactionStrategy
    └── ManualCompactionStrategy

每个策略独立决策和执行：
1. should_compact() - 判断是否需要压缩
2. compact() - 执行压缩
3. get_kind() - 返回类型（用于日志）
```

## 迁移指南

### 步骤 1: 更新 agent.py

```python
# 旧代码
from backend.app.compaction import estimate_tokens, micro_compact, auto_compact

# 新代码
from backend.app.context_guard import (
    ContextGuard,
    MicroCompactionStrategy,
    AutoCompactionStrategy,
    ManualCompactionStrategy
)
```

### 步骤 2: 初始化 ContextGuard

```python
class AgentService:
    def __init__(self):
        # 新增
        self.guard = ContextGuard(max_tokens=180000)
        self.guard.add_strategy(MicroCompactionStrategy())
        self.guard.add_strategy(AutoCompactionStrategy(threshold=50000))
        self.guard.add_strategy(ManualCompactionStrategy())
```

### 步骤 3: 替换压缩逻辑

```python
# 旧代码（删除）
before_micro = len(history)
micro_compact(history)
if len(history) < before_micro:
    get_store().save_compaction("main", "micro", before_micro, len(history))

if estimate_tokens(history, self.llm) > THRESHOLD:
    _log("🗜️", "[auto_compact triggered]")
    before_auto = len(history)
    new_history = auto_compact(history, self.llm)
    history.clear()
    history.extend(new_history)
    get_store().save_compaction("main", "auto", before_auto, len(history))

if was_compact_requested():
    _log("🗜️", "[manual compact]")
    before_manual = len(history)
    new_history = auto_compact(history, self.llm)
    history.clear()
    history.extend(new_history)
    get_store().save_compaction("main", "manual", before_manual, len(history))

# 新代码（替换为）
history = self.guard.apply_strategies(history, self.llm)
```

## 测试示例

```python
import pytest
from backend.app.context_guard import (
    ContextGuard,
    MicroCompactionStrategy,
    AutoCompactionStrategy
)

def test_micro_compaction():
    strategy = MicroCompactionStrategy()
    history = [
        HumanMessage(content="hello"),
        HumanMessage(content="hello"),  # 重复
        AIMessage(content="hi"),
    ]

    result = strategy.compact(history, llm)
    assert len(result) == 2  # 移除了重复消息

def test_auto_compaction():
    guard = ContextGuard(max_tokens=1000)
    strategy = AutoCompactionStrategy(threshold=500)

    # 创建大量消息
    history = [HumanMessage(content="x" * 100) for _ in range(20)]

    context = {"guard": guard}
    assert strategy.should_compact(history, context) == True

def test_guard_apply_strategies():
    guard = ContextGuard(max_tokens=180000)
    guard.add_strategy(MicroCompactionStrategy())
    guard.add_strategy(AutoCompactionStrategy(threshold=50000))

    history = [...]  # 测试数据
    result = guard.apply_strategies(history, llm)

    assert len(result) <= len(history)  # 压缩后消息数减少
```

## 总结

通过将 `CompactionStrategy` 整合到 `ContextGuard` 中：

1. **更清晰的职责划分** - 压缩逻辑都在 ContextGuard
2. **更简洁的 Agent 代码** - run() 方法从 300+ 行减少到 ~100 行
3. **更好的可扩展性** - 新增策略只需实现接口
4. **更容易测试** - 每个策略独立测试
5. **更符合设计原则** - 单一职责、开闭原则

现在 `agent.py` 只需要：
```python
history = self.guard.apply_strategies(history, self.llm)
```

一行代码完成所有压缩逻辑！
