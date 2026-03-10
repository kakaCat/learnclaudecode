# Context 架构重构总结（继承模式）

## 🎯 架构设计

### 继承层次

```
BaseContext (基类)
    ├─ session_store (全局单例)
    ├─ llm
    ├─ tracer
    ├─ conversation_history
    └─ overflow_guard

    ↓ 继承

MainContext (主 Agent)
    ├─ 继承所有 BaseContext 资源
    └─ 添加独有资源：
        ├─ tools (包含 Task tool)
        ├─ system_prompt
        └─ agent

    ↓ 继承

SubagentContext (子 Agent)
    ├─ 继承所有 BaseContext 资源
    └─ 添加独有资源：
        ├─ subagent_type
        ├─ tools (过滤后，不含 Task)
        ├─ system_prompt
        └─ agent
```

## 📝 核心代码

### BaseContext (基类)

```python
class BaseContext:
    """所有 Agent 共享的资源"""

    def __init__(self, session_key: str):
        self.session_key = session_key
        self.session_store = get_store()  # 全局单例
        self.llm = get_llm()
        self.tracer = Tracer()
        self.conversation_history = ConversationHistory(...)
        self.overflow_guard = OverflowGuard(...)
```

### MainContext (主 Agent)

```python
class MainContext(BaseContext):
    """主 Agent 上下文"""

    def __init__(self, session_key: str):
        super().__init__(session_key)  # 继承共享资源

        # Main 独有资源
        self.tools = tool_manager.get_main_tools()  # 包含 Task
        self.system_prompt = get_system_prompt(session_key)
        self.agent = create_agent(self.llm, self.tools, ...)
```

### SubagentContext (子 Agent)

```python
class SubagentContext(BaseContext):
    """子 Agent 上下文"""

    def __init__(self, session_key: str, subagent_type: str):
        super().__init__(session_key)  # 继承共享资源

        # Subagent 独有资源
        self.subagent_type = subagent_type
        self.tools = self._filter_tools()  # 不含 Task
        self.system_prompt = AGENT_TYPES[subagent_type]["prompt"]
        self.agent = create_agent(self.llm, self.tools, ...)
```

## 🔄 资源共享机制

### 1. 继承共享

```python
# 创建 MainContext
main_ctx = MainContext("session_001")

# 创建 SubagentContext（使用相同的 session_key）
sub_ctx = SubagentContext("session_001", "Explore")

# 它们都继承自 BaseContext，使用相同的 session_key
assert main_ctx.session_key == sub_ctx.session_key  # True
```

### 2. 全局单例共享

```python
# session_store 是全局单例
assert main_ctx.session_store is sub_ctx.session_store  # True

# 所有 Context 写入同一个会话目录
main_ctx.session_store.save_turn("main", ...)
→ .sessions/session_001/main.jsonl

sub_ctx.session_store.save_turn("Explore", ...)
→ .sessions/session_001/Explore.jsonl  # 同一个目录！
```

### 3. 独立创建的资源

```python
# llm, tracer 等是各自创建的（不是同一个对象）
assert main_ctx.llm is not sub_ctx.llm  # True（不同对象）

# 但配置相同，功能一致
assert type(main_ctx.llm) == type(sub_ctx.llm)  # True
```

## ✅ 优势

### 1. 清晰的继承关系

```
BaseContext (共享资源)
    ↓
MainContext / SubagentContext (独有资源)
```

### 2. 代码复用

- BaseContext 只写一次共享资源初始化
- 子类通过 `super().__init__()` 复用

### 3. 类型安全

```python
def process(ctx: BaseContext):
    # 可以接受 MainContext 或 SubagentContext
    print(ctx.session_key)
    print(ctx.llm)
```

### 4. 易于扩展

```python
# 添加新的 Context 类型
class TeamContext(BaseContext):
    def __init__(self, session_key: str, team_name: str):
        super().__init__(session_key)
        self.team_name = team_name
        # ...
```

## 🆚 与旧架构对比

### 旧架构（引用模式）

```python
class SubagentContext:
    def __init__(self, main_context: MainContext, ...):
        self.main_context = main_context  # 引用

    @property
    def llm(self):
        return self.main_context.llm  # 通过引用访问
```

**问题**：
- SubagentContext 依赖 MainContext
- 需要先创建 MainContext
- 关系复杂（引用 + @property）

### 新架构（继承模式）

```python
class MainContext(BaseContext):
    def __init__(self, session_key: str):
        super().__init__(session_key)  # 继承

class SubagentContext(BaseContext):
    def __init__(self, session_key: str, subagent_type: str):
        super().__init__(session_key)  # 继承
```

**优势**：
- MainContext 和 SubagentContext 独立
- 都继承自 BaseContext
- 关系清晰（继承）

## 📊 测试结果

```bash
✅ BaseContext 包含所有共享资源
✅ MainContext 继承 BaseContext，添加 Main 独有资源
✅ SubagentContext 继承 BaseContext，添加 Subagent 独有资源
✅ AgentService 支持两种 Context
✅ Session 数据通过 session_key 和全局单例保持一致
✅ Task tool 使用新架构创建 Subagent
```

## 🎉 总结

继承架构更符合 OOP 设计原则：
- **单一职责**：BaseContext 管理共享资源
- **开闭原则**：通过继承扩展，不修改基类
- **里氏替换**：MainContext 和 SubagentContext 可互换使用
- **依赖倒置**：都依赖 BaseContext 抽象

数据一致性通过：
- **相同的 session_key**
- **全局单例 session_store**
- **写入同一个会话目录**
