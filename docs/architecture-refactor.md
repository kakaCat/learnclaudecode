# Agent 架构重构方案

## 当前架构问题

### 问题1：重复的上下文管理
```
AgentContext (Main Agent)
├── llm
├── tools (包含 Task tool)
├── conversation_history
├── overflow_guard
└── tracer

run_subagent() (Subagent)
├── llm (重新创建)
├── tools (过滤后)
├── 独立的执行逻辑
└── 独立保存 session
```

**问题**：
- Subagent 重新创建 LLM 和执行逻辑
- 没有共享记忆和压缩策略
- 代码重复（run_subagent 重新实现了 Agent 执行）

### 问题2：隐式的全局状态依赖
```python
# AgentContext 同步到全局
def set_session_key(self, session_key: str):
    global_set_session_key(session_key)  # 隐式同步

# Subagent 从全局获取
def run_subagent(...):
    key = get_session_key()  # 隐式依赖全局状态
```

**问题**：
- 依赖关系不清晰
- 难以测试和 mock
- 状态可能不同步

---

## 重构后架构

### 核心设计原则

1. **共享上下文**：Main Agent 和 Subagent 共享会话级资源
2. **显式依赖**：通过构造函数注入依赖，避免全局状态
3. **组合优于继承**：使用组合模式管理共享资源
4. **单一职责**：每个类只负责一件事

### 架构图

```
┌─────────────────────────────────────────────────────────────┐
│                      User Session                            │
│                   (session_key: "20260310_120000")          │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ 创建
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    SharedContext                             │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ session_store: SessionStore (全局单例)                  │ │
│  │   ├── _current_key: "20260310_120000"                  │ │
│  │   ├── _index: {...}                                     │ │
│  │   └── save_turn() / load_history() / save_compaction() │ │
│  ├────────────────────────────────────────────────────────┤ │
│  │ llm: ChatOpenAI (共享 LLM 实例)                         │ │
│  ├────────────────────────────────────────────────────────┤ │
│  │ tracer: Tracer (共享追踪器)                             │ │
│  │   └── emit() → session_store.save_event()              │ │
│  ├────────────────────────────────────────────────────────┤ │
│  │ conversation_history: ConversationHistory               │ │
│  │   ├── session_store (引用)                              │ │
│  │   └── save() → session_store.save_turn()               │ │
│  ├────────────────────────────────────────────────────────┤ │
│  │ overflow_guard: OverflowGuard                           │ │
│  │   ├── session_store (引用)                              │ │
│  │   └── compact() → session_store.save_compaction()      │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                    │                    │
                    │ 组合               │ 组合
                    ▼                    ▼
┌──────────────────────────────┐  ┌──────────────────────────────┐
│   MainAgentContext           │  │   SubagentContext            │
│  ┌────────────────────────┐  │  │  ┌────────────────────────┐  │
│  │ shared: SharedContext  │──┼──┼─▶│ shared: SharedContext  │  │
│  │   (引用同一个实例)      │  │  │  │   (引用同一个实例)      │  │
│  ├────────────────────────┤  │  │  ├────────────────────────┤  │
│  │ tools: List[BaseTool]  │  │  │  │ tools: List[BaseTool]  │  │
│  │   - bash               │  │  │  │   - bash               │  │
│  │   - read_file          │  │  │  │   - read_file          │  │
│  │   - write_file         │  │  │  │   - glob               │  │
│  │   - Task ✓             │  │  │  │   - grep               │  │
│  │   - ...                │  │  │  │   (Task 被过滤)        │  │
│  ├────────────────────────┤  │  │  ├────────────────────────┤  │
│  │ agent: Agent           │  │  │  │ agent: Agent           │  │
│  │   (LangChain Agent)    │  │  │  │   (LangChain Agent)    │  │
│  └────────────────────────┘  │  │  └────────────────────────┘  │
└──────────────────────────────┘  └──────────────────────────────┘
                    │                              │
                    │ 执行                         │ 执行
                    ▼                              ▼
┌──────────────────────────────┐  ┌──────────────────────────────┐
│   AgentExecutor              │  │   AgentExecutor              │
│  ┌────────────────────────┐  │  │  ┌────────────────────────┐  │
│  │ context: MainAgent     │  │  │  │ context: Subagent      │  │
│  ├────────────────────────┤  │  │  ├────────────────────────┤  │
│  │ run(prompt)            │  │  │  │ run(prompt)            │  │
│  │   ├─ 溢出检查          │  │  │  │   ├─ 溢出检查          │  │
│  │   ├─ Agent.invoke()    │  │  │  │   ├─ Agent.invoke()    │  │
│  │   ├─ 保存对话          │  │  │  │   ├─ 保存对话          │  │
│  │   └─ 返回结果          │  │  │  │   └─ 返回结果          │  │
│  └────────────────────────┘  │  │  └────────────────────────┘  │
└──────────────────────────────┘  └──────────────────────────────┘
                    │                              │
                    │ 保存                         │ 保存
                    ▼                              ▼
┌─────────────────────────────────────────────────────────────┐
│              .sessions/20260310_120000/                      │
│  ├── main.jsonl          (Main Agent 对话记录)              │
│  ├── Explore.jsonl       (Explore Subagent 对话记录)        │
│  ├── Plan.jsonl          (Plan Subagent 对话记录)           │
│  ├── compaction.jsonl    (压缩记录，共享)                    │
│  └── events.jsonl        (事件追踪，共享)                    │
└─────────────────────────────────────────────────────────────┘
```

---

## 数据流示例

### 场景1：Main Agent 调用 Subagent

```
1. 用户输入
   User: "帮我分析代码结构"
   ↓

2. Main Agent 执行
   MainAgentExecutor.run("帮我分析代码结构")
   ├─ context.shared.overflow_guard.check()  # 检查溢出
   ├─ context.agent.invoke()                 # LLM 推理
   └─ 决定调用 Task tool
   ↓

3. Task tool 创建 Subagent
   Task.run(subagent_type="Explore", prompt="分析代码结构")
   ├─ SubagentContext.create(
   │     shared=main_context.shared,  # 共享 SharedContext
   │     subagent_type="Explore"
   │  )
   ├─ SubagentExecutor.run(prompt)
   │  ├─ shared.overflow_guard.check()      # 使用共享的溢出检查
   │  ├─ agent.invoke()                     # Subagent 执行
   │  └─ shared.session_store.save_turn()   # 保存到共享 session
   └─ 返回结果给 Main Agent
   ↓

4. Main Agent 继续
   ├─ 接收 Subagent 结果
   ├─ shared.session_store.save_turn("main", ...)  # 保存对话
   └─ 返回最终结果给用户
```

### 场景2：压缩触发

```
1. 溢出检查
   overflow_guard.check(messages)
   ├─ 计算 token 数量
   └─ 超过阈值 → 触发压缩
   ↓

2. 执行压缩
   overflow_guard.compact(messages)
   ├─ 调用 LLM 生成摘要
   ├─ 保存压缩记录
   │  └─ shared.session_store.save_compaction(
   │        agent_name="main",
   │        original_count=50,
   │        compressed_count=10,
   │        summary="..."
   │     )
   └─ 返回压缩后的消息
   ↓

3. 所有 Agent 共享压缩结果
   ├─ Main Agent 看到压缩后的历史
   └─ Subagent 也看到压缩后的历史
```

---

## 核心类设计

### 1. SharedContext

```python
class SharedContext:
    """
    共享上下文：管理会话级别的共享资源

    职责：
    - 管理 SessionStore（会话存储）
    - 管理 LLM（语言模型）
    - 管理 Tracer（事件追踪）
    - 管理 ConversationHistory（对话记忆）
    - 管理 OverflowGuard（溢出保护）
    """

    def __init__(self, session_key: str):
        # 1. 获取全局 SessionStore 单例
        self.session_store = get_store()
        self.session_store.set_current_key(session_key)

        # 2. 创建共享资源（显式传递 session_store）
        self.session_key = session_key
        self.llm = get_llm()
        self.tracer = Tracer(session_store=self.session_store)
        self.conversation_history = ConversationHistory(
            session_key=session_key,
            session_store=self.session_store
        )
        self.overflow_guard = OverflowGuard(
            llm=self.llm,
            session_store=self.session_store
        )
```

### 2. AgentContext

```python
class AgentContext:
    """
    Agent 上下文：管理单个 Agent 的独立资源

    职责：
    - 组合 SharedContext（共享资源）
    - 管理 tools（工具列表）
    - 管理 agent（LangChain Agent 实例）
    """

    def __init__(self, shared: SharedContext, tools: List[BaseTool]):
        self.shared = shared
        self.tools = tools
        self.agent = create_agent(
            self.shared.llm,
            self.tools,
            system_prompt=get_system_prompt(self.shared.session_key)
        )

    @classmethod
    def create_main(cls, session_key: str) -> "AgentContext":
        """创建 Main Agent 上下文"""
        shared = SharedContext(session_key)
        tools = tool_manager.get_tools()  # 包含 Task tool
        return cls(shared, tools)

    @classmethod
    def create_subagent(
        cls,
        parent_shared: SharedContext,
        subagent_type: str
    ) -> "AgentContext":
        """创建 Subagent 上下文（共享 SharedContext）"""
        filtered_tools = filter_tools_by_type(subagent_type)
        return cls(parent_shared, filtered_tools)
```

### 3. AgentExecutor

```python
class AgentExecutor:
    """
    Agent 执行器：统一的执行逻辑

    职责：
    - 执行 Agent（Main 或 Subagent）
    - 溢出检查和压缩
    - 保存对话历史
    - 事件追踪
    """

    def __init__(self, context: AgentContext, agent_name: str = "main"):
        self.context = context
        self.agent_name = agent_name

    async def run(self, prompt: str, history: List = None) -> str:
        """统一的执行逻辑（Main 和 Subagent 共用）"""
        # 1. 溢出检查
        messages = self.context.shared.overflow_guard.check(history or [])

        # 2. 执行 Agent
        result = await self.context.agent.ainvoke({
            "messages": messages + [HumanMessage(content=prompt)]
        })

        # 3. 保存对话
        self.context.shared.session_store.save_turn(
            agent_name=self.agent_name,
            user_msg=prompt,
            ai_msg=result["output"]
        )

        # 4. 事件追踪
        self.context.shared.tracer.emit(
            "agent.run",
            agent_name=self.agent_name,
            prompt=prompt[:100],
            output=result["output"][:100]
        )

        return result["output"]
```

---

## 重构步骤

### Phase 1: 创建 SharedContext
- [ ] 创建 `backend/app/context/shared.py`
- [ ] 实现 `SharedContext` 类
- [ ] 修改 `ConversationHistory` 接收 `session_store`
- [ ] 修改 `OverflowGuard` 接收 `session_store`
- [ ] 修改 `Tracer` 接收 `session_store`

### Phase 2: 重构 AgentContext
- [ ] 修改 `AgentContext` 组合 `SharedContext`
- [ ] 添加 `create_main()` 工厂方法
- [ ] 添加 `create_subagent()` 工厂方法
- [ ] 移除全局状态同步逻辑

### Phase 3: 统一 AgentExecutor
- [ ] 提取 `AgentExecutor` 类
- [ ] Main Agent 使用 `AgentExecutor`
- [ ] Subagent 使用 `AgentExecutor`
- [ ] 删除 `run_subagent()` 中的重复逻辑

### Phase 4: 重构 Task Tool
- [ ] 修改 `Task` tool 接收 `AgentContext`
- [ ] 使用 `AgentContext.create_subagent()` 创建子上下文
- [ ] 使用 `AgentExecutor` 执行 Subagent

### Phase 5: 测试和验证
- [ ] 单元测试：SharedContext
- [ ] 单元测试：AgentContext
- [ ] 集成测试：Main Agent 调用 Subagent
- [ ] 验证 session 数据一致性

---

## 优势总结

### 1. 共享资源
- ✅ Main Agent 和 Subagent 共享 LLM
- ✅ 共享 SessionStore（数据一致性）
- ✅ 共享 Tracer（统一追踪）
- ✅ 共享 ConversationHistory（记忆一致）
- ✅ 共享 OverflowGuard（压缩策略一致）

### 2. 显式依赖
- ✅ 所有依赖通过构造函数注入
- ✅ 避免隐式全局状态
- ✅ 易于测试和 mock
- ✅ 依赖关系清晰

### 3. 代码复用
- ✅ Main Agent 和 Subagent 使用同一个 `AgentExecutor`
- ✅ 消除重复的执行逻辑
- ✅ 统一的溢出检查和保存逻辑

### 4. 易于扩展
- ✅ 可以轻松添加新的 Subagent 类型
- ✅ 可以替换 SharedContext 的组件（如换 LLM）
- ✅ 可以并行执行多个 Subagent（未来）

---

## 对比：重构前 vs 重构后

| 维度 | 重构前 | 重构后 |
|------|--------|--------|
| **上下文管理** | Main 和 Sub 独立创建 | 共享 SharedContext |
| **LLM 实例** | 重复创建 | 共享同一个实例 |
| **Session 管理** | 隐式全局状态 | 显式注入 SessionStore |
| **执行逻辑** | 重复实现 | 统一 AgentExecutor |
| **记忆一致性** | 独立管理 | 共享 ConversationHistory |
| **压缩策略** | 独立管理 | 共享 OverflowGuard |
| **事件追踪** | 独立管理 | 共享 Tracer |
| **代码行数** | ~600 行 | ~400 行（估计） |
| **可测试性** | 难以 mock | 易于 mock |
| **可扩展性** | 低 | 高 |

---

## 结论

通过引入 **SharedContext** 和统一的 **AgentExecutor**，我们实现了：

1. **Main Agent 和 Subagent 是真正的"分身"**
   - 共享记忆、压缩、追踪
   - 只是工具列表不同

2. **数据一致性保证**
   - 所有 Agent 写入同一个 SessionStore
   - 所有数据保存到同一个会话目录

3. **清晰的架构**
   - 显式依赖，易于理解
   - 单一职责，易于维护
   - 组合优于继承，易于扩展

这正是你最初的直觉：**Main Agent 和 Subagent 应该共享 Context**！
