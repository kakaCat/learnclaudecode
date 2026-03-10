# Agent 架构重构方案（简化版）

## 核心设计

**只分两层**：
1. `MainContext` - 主 Agent 上下文
2. `SubagentContext` - 子 Agent 上下文（共享 MainContext 的资源）

## 架构图

```
┌─────────────────────────────────────────────────────────────┐
│                    MainContext                               │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ 会话级共享资源（Main 和 Subagent 都用）                 │ │
│  ├────────────────────────────────────────────────────────┤ │
│  │ session_store: SessionStore                             │ │
│  │   ├── _current_key: "20260310_120000"                  │ │
│  │   └── save_turn() / load_history()                     │ │
│  ├────────────────────────────────────────────────────────┤ │
│  │ llm: ChatOpenAI                                         │ │
│  ├────────────────────────────────────────────────────────┤ │
│  │ tracer: Tracer                                          │ │
│  ├────────────────────────────────────────────────────────┤ │
│  │ conversation_history: ConversationHistory               │ │
│  ├────────────────────────────────────────────────────────┤ │
│  │ overflow_guard: OverflowGuard                           │ │
│  ├────────────────────────────────────────────────────────┤ │
│  │ Main Agent 独有资源                                     │ │
│  ├────────────────────────────────────────────────────────┤ │
│  │ tools: List[BaseTool]                                   │ │
│  │   - bash, read_file, write_file, Task, ...             │ │
│  ├────────────────────────────────────────────────────────┤ │
│  │ agent: Agent (LangChain)                                │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ 创建 Subagent
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  SubagentContext                             │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ 引用 MainContext 的共享资源                             │ │
│  ├────────────────────────────────────────────────────────┤ │
│  │ main_context: MainContext (引用)                        │ │
│  │   ├── session_store ──┐                                │ │
│  │   ├── llm ────────────┼─ 共享                          │ │
│  │   ├── tracer ─────────┤                                │ │
│  │   ├── conversation_history ─┤                          │ │
│  │   └── overflow_guard ───────┘                          │ │
│  ├────────────────────────────────────────────────────────┤ │
│  │ Subagent 独有资源                                       │ │
│  ├────────────────────────────────────────────────────────┤ │
│  │ subagent_type: str ("Explore", "Plan", ...)            │ │
│  ├────────────────────────────────────────────────────────┤ │
│  │ tools: List[BaseTool] (过滤后，无 Task)                │ │
│  │   - bash, read_file, glob, grep, ...                   │ │
│  ├────────────────────────────────────────────────────────┤ │
│  │ agent: Agent (LangChain)                                │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## 代码结构

```python
# backend/app/context/main_context.py
class MainContext:
    """主 Agent 上下文，包含所有共享资源"""

    def __init__(self, session_key: str):
        # 1. 会话级共享资源
        self.session_key = session_key
        self.session_store = get_store()
        self.session_store.set_current_key(session_key)

        self.llm = get_llm()
        self.tracer = Tracer(self.session_store)
        self.conversation_history = ConversationHistory(
            session_key,
            self.session_store
        )
        self.overflow_guard = OverflowGuard(
            self.llm,
            self.session_store
        )

        # 2. Main Agent 独有资源
        self.tools = tool_manager.get_tools()  # 包含 Task tool
        self.agent = create_agent(
            self.llm,
            self.tools,
            system_prompt=get_system_prompt(session_key)
        )

    def create_subagent(self, subagent_type: str) -> "SubagentContext":
        """创建 Subagent，共享资源"""
        return SubagentContext(self, subagent_type)


# backend/app/context/subagent_context.py
class SubagentContext:
    """子 Agent 上下文，引用 MainContext 的共享资源"""

    def __init__(self, main_context: MainContext, subagent_type: str):
        # 1. 引用 MainContext（共享资源）
        self.main_context = main_context
        self.subagent_type = subagent_type

        # 2. Subagent 独有资源
        self.tools = self._filter_tools(
            main_context.tools,
            subagent_type
        )
        self.agent = create_agent(
            main_context.llm,  # 共享 LLM
            self.tools,
            system_prompt=get_subagent_prompt(subagent_type)
        )

    # 便捷访问共享资源
    @property
    def session_store(self):
        return self.main_context.session_store

    @property
    def llm(self):
        return self.main_context.llm

    @property
    def tracer(self):
        return self.main_context.tracer

    @property
    def conversation_history(self):
        return self.main_context.conversation_history

    @property
    def overflow_guard(self):
        return self.main_context.overflow_guard
```

## 使用示例

### 1. 创建 Main Agent

```python
# backend/app/agent.py
def create_main_agent(session_key: str):
    # 创建 MainContext（包含所有共享资源）
    context = MainContext(session_key)

    # 创建 AgentExecutor
    executor = AgentExecutor(context)

    return executor
```

### 2. Main Agent 调用 Subagent

```python
# backend/app/tools/task.py
class Task(BaseTool):
    def __init__(self, main_context: MainContext):
        self.main_context = main_context

    def _run(self, subagent_type: str, prompt: str):
        # 创建 Subagent（共享 MainContext）
        sub_context = self.main_context.create_subagent(subagent_type)

        # 执行 Subagent
        sub_executor = AgentExecutor(sub_context)
        result = sub_executor.run(prompt)

        return result
```

### 3. 统一的 AgentExecutor

```python
# backend/app/executor.py
class AgentExecutor:
    """统一的 Agent 执行器，支持 MainContext 和 SubagentContext"""

    def __init__(self, context: MainContext | SubagentContext):
        self.context = context

    def run(self, prompt: str) -> str:
        # 1. 溢出检查（共享）
        if isinstance(self.context, SubagentContext):
            overflow_guard = self.context.main_context.overflow_guard
        else:
            overflow_guard = self.context.overflow_guard

        messages = overflow_guard.check_and_compact([
            HumanMessage(content=prompt)
        ])

        # 2. 执行 Agent
        result = self.context.agent.invoke({"messages": messages})

        # 3. 保存对话（共享 session_store）
        agent_name = (
            self.context.subagent_type
            if isinstance(self.context, SubagentContext)
            else "main"
        )

        if isinstance(self.context, SubagentContext):
            session_store = self.context.main_context.session_store
        else:
            session_store = self.context.session_store

        session_store.save_turn(agent_name, prompt, result)

        return result
```

## 数据流

### Main Agent → Subagent

```
1. 用户输入
   User: "帮我分析代码结构"
   ↓

2. MainContext 创建
   main_context = MainContext("20260310_120000")
   ├── session_store (全局单例)
   ├── llm
   ├── tracer
   ├── conversation_history
   ├── overflow_guard
   ├── tools (包含 Task)
   └── agent
   ↓

3. Main Agent 执行
   executor = AgentExecutor(main_context)
   executor.run("帮我分析代码结构")
   ├── overflow_guard.check()
   ├── agent.invoke()
   └── 决定调用 Task tool
   ↓

4. Task tool 创建 Subagent
   sub_context = main_context.create_subagent("Explore")
   ├── main_context (引用)
   │   ├── session_store ──┐
   │   ├── llm ────────────┼─ 共享
   │   ├── tracer ─────────┤
   │   ├── conversation_history ─┤
   │   └── overflow_guard ───────┘
   ├── subagent_type = "Explore"
   ├── tools (过滤后，无 Task)
   └── agent (新创建)
   ↓

5. Subagent 执行
   sub_executor = AgentExecutor(sub_context)
   sub_executor.run("分析代码结构")
   ├── sub_context.main_context.overflow_guard.check()  # 共享
   ├── sub_context.agent.invoke()
   └── sub_context.main_context.session_store.save_turn()  # 共享
   ↓

6. 保存到同一个会话
   .sessions/20260310_120000/
   ├── main.jsonl       (Main Agent 对话)
   ├── Explore.jsonl    (Explore Subagent 对话)
   ├── compaction.jsonl (压缩记录，共享)
   └── events.jsonl     (事件追踪，共享)
```

## 关键优势

### 1. 简单清晰
- 只有两个类：`MainContext` 和 `SubagentContext`
- 关系明确：Subagent 引用 Main

### 2. 资源共享
- Session、LLM、Tracer、History、OverflowGuard 都共享
- 避免重复创建和状态不一致

### 3. 显式依赖
- Subagent 通过 `main_context` 引用访问共享资源
- 不依赖全局状态

### 4. 易于测试
- 可以 mock MainContext
- 可以独立测试 Subagent

### 5. 统一执行
- `AgentExecutor` 同时支持 Main 和 Subagent
- 代码不重复

## 重构步骤

### Step 1: 创建 MainContext
```bash
# 新建文件
backend/app/context/main_context.py
```

### Step 2: 创建 SubagentContext
```bash
# 新建文件
backend/app/context/subagent_context.py
```

### Step 3: 重构 AgentExecutor
```bash
# 修改文件
backend/app/executor.py
```

### Step 4: 重构 Task tool
```bash
# 修改文件
backend/app/tools/task.py
```

### Step 5: 删除旧代码
```bash
# 删除 run_subagent() 函数
backend/app/subagents/__init__.py
```

## 对比：重构前 vs 重构后

### 重构前
```python
# Main Agent
context = AgentContext.create_default()
context.set_session_key(session_key)  # 同步到全局

# Subagent（独立）
def run_subagent(...):
    llm = ChatOpenAI(...)  # 重新创建
    agent = create_agent(llm, tools, ...)
    key = get_session_key()  # 从全局获取
    save_session(...)  # 保存到全局
```

### 重构后
```python
# Main Agent
main_context = MainContext(session_key)

# Subagent（共享）
sub_context = main_context.create_subagent("Explore")
# sub_context.main_context.llm  # 共享 LLM
# sub_context.main_context.session_store  # 共享 SessionStore
```

## 总结

**核心思想**：
- Main 和 Subagent 是"分身"关系
- 它们共享会话级资源（Session、LLM、Tracer、History、OverflowGuard）
- 只有工具列表和 Agent 实例不同

**实现方式**：
- `MainContext` 包含所有资源
- `SubagentContext` 引用 `MainContext`，通过 `@property` 便捷访问共享资源
- 统一的 `AgentExecutor` 处理两种 Context

**数据一致性**：
- 所有 Agent 使用同一个 `SessionStore` 实例
- 所有对话保存到同一个会话目录
- 压缩、追踪都是共享的
