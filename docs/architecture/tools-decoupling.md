# Tools 解耦架构设计

## 问题背景

原有架构存在循环依赖：
```
agent.py → tool_manager → spawn_tool.py → MainAgentContext → agent.py
                       → background_tool.py → tool_manager
```

## 解耦方案：依赖注入 + 回调函数

### 核心思想

**工具层不依赖 Agent 层，通过回调函数注入实现解耦**

```
┌─────────────────────────────────────────────────────────────┐
│                        Agent Layer                          │
│  ┌──────────────┐         ┌─────────────────┐              │
│  │ MainAgent    │────────▶│ MainAgentContext│              │
│  │ Context      │         │                 │              │
│  └──────────────┘         └─────────────────┘              │
│         │                          │                        │
│         │ 1. 初始化                │                        │
│         ▼                          ▼                        │
│  ┌──────────────────────────────────────────┐              │
│  │         ToolsManager                     │              │
│  │  ┌────────────────────────────────────┐  │              │
│  │  │ build_task_tool(main_context)     │  │              │
│  │  │  ├─ 注入 spawn_callback           │  │              │
│  │  │  └─ 注入 get_tools_callback       │  │              │
│  │  └────────────────────────────────────┘  │              │
│  └──────────────────────────────────────────┘              │
└─────────────────────────────────────────────────────────────┘
                         │
                         │ 2. 注入回调
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                      Tools Layer                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  spawn_tool.py                                       │  │
│  │  ┌────────────────────────────────────────────────┐  │  │
│  │  │ _spawn_callback: Optional[Callable] = None     │  │  │
│  │  │                                                 │  │  │
│  │  │ def set_spawn_callback(callback):              │  │  │
│  │  │     global _spawn_callback                     │  │  │
│  │  │     _spawn_callback = callback                 │  │  │
│  │  │                                                 │  │  │
│  │  │ @tool                                          │  │  │
│  │  │ def Task(...):                                 │  │  │
│  │  │     return _spawn_callback(...)  # 调用注入的回调│  │  │
│  │  └────────────────────────────────────────────────┘  │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  background_tool.py                                  │  │
│  │  ┌────────────────────────────────────────────────┐  │  │
│  │  │ _get_tools_callback: Optional[Callable] = None │  │  │
│  │  │                                                 │  │  │
│  │  │ def set_get_tools_callback(callback):          │  │  │
│  │  │     global _get_tools_callback                 │  │  │
│  │  │     _get_tools_callback = callback             │  │  │
│  │  │                                                 │  │  │
│  │  │ @tool                                          │  │  │
│  │  │ def background_agent(...):                     │  │  │
│  │  │     tools = _get_tools_callback()  # 调用注入的回调│  │  │
│  │  └────────────────────────────────────────────────┘  │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## 实现细节

### 1. spawn_tool.py - 使用回调而非直接依赖

**Before (循环依赖):**
```python
def make_task_tool(main_context=None):
    @tool
    def Task(...):
        from backend.app.context.subagent_context import SubagentContext
        sub_context = SubagentContext(main_context.session_key, ...)
        # 直接依赖 main_context
```

**After (依赖注入):**
```python
_spawn_callback: Optional[Callable] = None

def set_spawn_callback(callback: Callable):
    global _spawn_callback
    _spawn_callback = callback

@tool
def Task(...):
    if _spawn_callback is None:
        return "Error: Task tool not initialized"
    return _spawn_callback(...)  # 调用注入的回调
```

### 2. background_tool.py - 使用回调获取工具列表

**Before (循环依赖):**
```python
@tool
def background_agent(...):
    from backend.app.tools.manager import tool_manager
    base_tools = tool_manager.get_subagent_tools()  # 循环导入
```

**After (依赖注入):**
```python
_get_tools_callback: Optional[Callable] = None

def set_get_tools_callback(callback: Callable):
    global _get_tools_callback
    _get_tools_callback = callback

@tool
def background_agent(...):
    if _get_tools_callback is None:
        return "Error: background_agent not initialized"
    base_tools = _get_tools_callback()  # 调用注入的回调
```

### 3. tool_manager.py - 注入回调实现

```python
def build_task_tool(self, main_context=None) -> "ToolsManager":
    # 1. 注入 spawn 回调
    from backend.app.tools.implementations.agent.spawn_tool import set_spawn_callback, Task

    def spawn_callback(description, prompt, subagent_type, recursion_limit):
        from backend.app.context.subagent_context import SubagentContext
        from backend.app.subagents.runner import run_subagent_with_context

        sub_context = SubagentContext(main_context.session_key, subagent_type)
        return run_subagent_with_context(
            sub_context=sub_context,
            description=description,
            prompt=prompt,
            recursion_limit=recursion_limit
        )

    set_spawn_callback(spawn_callback)
    self._tools[Task.name] = Task

    # 2. 注入 background_agent 的工具获取回调
    from backend.app.tools.implementations.execution.background_tool import set_get_tools_callback
    set_get_tools_callback(lambda: self.get_subagent_tools())

    return self
```

## 依赖关系对比

### Before (循环依赖)
```
agent.py ──────────────────┐
    │                      │
    ▼                      │
tool_manager.py            │
    │                      │
    ▼                      │
spawn_tool.py              │
    │                      │
    ▼                      │
MainAgentContext ──────────┘  ❌ 循环依赖
```

### After (单向依赖)
```
agent.py
    │
    ▼
tool_manager.py ──注入回调──▶ spawn_tool.py
    │                            (无依赖)
    │
    └──注入回调──▶ background_tool.py
                     (无依赖)

✅ 单向依赖，无循环
```

## 优势

1. **解耦彻底**: `implementations/` 下的工具完全不依赖 agent 层
2. **易于测试**: 工具可以独立测试，只需 mock 回调函数
3. **灵活扩展**: 新增工具无需关心 agent 实现细节
4. **清晰职责**:
   - Tools Layer: 定义工具接口和行为
   - Agent Layer: 提供具体实现并注入

## 使用示例

### 初始化流程
```python
# 1. 创建 MainAgentContext
context = MainAgentContext(session_key)

# 2. tool_manager 自动注入回调（在 _ensure_initialized 中）
tool_manager._ensure_initialized(main_context=context)

# 3. 工具可以正常使用
tools = tool_manager.get_main_tools()
```

### 工具调用流程
```python
# Agent 调用 Task 工具
result = Task(
    description="探索代码库",
    prompt="找到所有 API 文件",
    subagent_type="Explore"
)

# 内部流程：
# Task() → _spawn_callback() → spawn_callback() → run_subagent_with_context()
```

## 注意事项

1. **初始化顺序**: 必须先创建 `MainAgentContext`，再调用 `build_task_tool()`
2. **回调生命周期**: 回调函数在进程生命周期内全局有效
3. **错误处理**: 工具会检查回调是否已注入，未注入时返回错误信息
4. **线程安全**: 当前实现使用全局变量，单进程单线程安全

## 未来优化

1. 使用 Context Manager 管理回调生命周期
2. 支持多 Agent 实例（每个实例独立回调）
3. 添加回调函数的类型检查和验证
