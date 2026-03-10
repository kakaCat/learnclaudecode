# Subagent 运行流程（继承架构）

## 🔄 完整调用链

```
用户输入
  ↓
Main Agent (AgentService with MainContext)
  ↓
调用 Task tool
  ↓
Task tool 执行：
  1. main_context.create_subagent(subagent_type)
     → 创建 SubagentContext(session_key, subagent_type)
     → 继承 BaseContext 的共享资源
  ↓
  2. AgentService(context=sub_context, enable_lifecycle=False)
     → 创建 Subagent 的 AgentService
  ↓
  3. asyncio.run(sub_service.run(prompt, history=[]))
     → 运行 Subagent
  ↓
返回结果给 Main Agent
```

## 📝 详细代码流程

### 1. Main Agent 调用 Task tool

```python
# Main Agent 运行中
main_service = AgentService(context=MainContext("session_001"))
await main_service.run("帮我搜索代码中的 TODO")

# LLM 决策调用 Task tool
tool_calls = [
    {
        "name": "Task",
        "args": {
            "description": "搜索代码中的 TODO",
            "prompt": "使用 grep 搜索所有 .py 文件中的 TODO 注释",
            "subagent_type": "Explore"
        }
    }
]
```

### 2. Task tool 创建 SubagentContext

```python
# spawn_tool.py (第 36 行)
def Task(description: str, prompt: str, subagent_type: str, ...):
    # 通过 MainContext 创建 SubagentContext
    sub_context = main_context.create_subagent(subagent_type)
    # ↓
    # main_context.py (第 107 行)
    return SubagentContext(self.session_key, subagent_type)
    # ↓
    # subagent_context.py (第 25 行)
    class SubagentContext(BaseContext):
        def __init__(self, session_key: str, subagent_type: str):
            super().__init__(session_key)  # 继承共享资源
            self.subagent_type = subagent_type
            self.tools = self._filter_tools()  # 过滤工具（不含 Task）
            self.agent = create_agent(self.llm, self.tools, ...)
```

### 3. 创建 Subagent 的 AgentService

```python
# spawn_tool.py (第 40 行)
sub_service = AgentService(context=sub_context, enable_lifecycle=False)

# agent.py (第 108 行)
class AgentService:
    def __init__(self, context: Union[MainContext, SubagentContext] = None, ...):
        self.context = context
        self.is_subagent = isinstance(context, SubagentContext)  # True
        self.agent_name = context.subagent_type  # "Explore"
```

### 4. 运行 Subagent

```python
# spawn_tool.py (第 45 行)
result = asyncio.run(sub_service.run(prompt, history=[]))

# agent.py (第 371 行)
async def run(self, prompt: str, history: list = None) -> str:
    # 使用 SubagentContext 的资源
    conversation_history = self.context.conversation_history  # 继承自 BaseContext
    tracer = self.context.tracer  # 继承自 BaseContext

    # 运行 Agent
    async for step in self.context.agent.astream(...):
        # 处理 LLM 和 tools 节点
        ...

    # 保存到 session_store
    self.context.session_store.save_turn(
        self.agent_name,  # "Explore"
        prompt,
        output,
        tool_calls_data
    )
    # ↓ 写入 .sessions/session_001/Explore.jsonl

    return output
```

## 🎯 关键点

### 1. 继承共享资源

```python
# SubagentContext 继承 BaseContext
class SubagentContext(BaseContext):
    def __init__(self, session_key: str, subagent_type: str):
        super().__init__(session_key)  # ← 继承共享资源

# 共享的资源（来自 BaseContext）：
- session_key: "session_001"
- session_store: 全局单例（所有 Context 共享）
- llm: ChatOpenAI 实例
- tracer: Tracer 实例
- conversation_history: ConversationHistory 实例
- overflow_guard: OverflowGuard 实例
```

### 2. 独立的资源

```python
# SubagentContext 独有资源：
- subagent_type: "Explore"
- tools: 过滤后的工具列表（不含 Task）
- system_prompt: Subagent 专用的 prompt
- agent: LangChain Agent 实例
```

### 3. Session 数据一致性

```python
# Main Agent 写入
main_context.session_store.save_turn("main", ...)
→ .sessions/session_001/main.jsonl

# Subagent 写入（使用同一个 session_store）
sub_context.session_store.save_turn("Explore", ...)
→ .sessions/session_001/Explore.jsonl  # 同一个目录！

# 因为：
assert main_context.session_store is sub_context.session_store  # True（全局单例）
assert main_context.session_key == sub_context.session_key      # True（相同的 key）
```

## 📊 对比旧架构

### 旧架构（run_subagent）

```python
# subagents/__init__.py (已废弃)
def run_subagent(description, prompt, subagent_type, base_tools, ...):
    # 重新创建 LLM
    llm = ChatOpenAI(...)

    # 重新创建 Agent
    agent = create_agent(llm, sub_tools, ...)

    # 独立运行（不共享资源）
    for step in agent.stream(...):
        ...

    # 独立保存
    save_session(subagent_type, [HumanMessage(...), AIMessage(...)])
```

**问题**：
- 重复创建 LLM
- 不共享 session_store
- 不共享 tracer
- 代码重复

### 新架构（继承模式）

```python
# 1. 创建 SubagentContext（继承 BaseContext）
sub_context = SubagentContext(session_key, subagent_type)

# 2. 使用 AgentService（统一的运行逻辑）
sub_service = AgentService(context=sub_context)

# 3. 运行（共享资源）
result = await sub_service.run(prompt, history=[])
```

**优势**：
- ✅ 继承共享资源（不重复创建）
- ✅ 统一的 AgentService 逻辑
- ✅ Session 数据一致
- ✅ 代码复用

## 🎉 总结

新架构通过**继承**实现资源共享：

```
BaseContext (共享资源)
    ↓ 继承
MainContext / SubagentContext
    ↓ 传递给
AgentService (统一运行逻辑)
    ↓ 执行
Agent (LangChain)
    ↓ 保存
SessionStore (全局单例)
```

所有 Context 都继承自 BaseContext，通过相同的 session_key 和全局单例 session_store 保证数据一致性。
