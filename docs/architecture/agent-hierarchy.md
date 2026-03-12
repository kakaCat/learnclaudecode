# Agent 层级架构设计

## 架构概览

```
┌─────────────────────────────────────────────────────────────┐
│                        User Input                            │
└──────────────────────────┬──────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                    MainAgent Loop                            │
│  - 可以调用所有普通工具 (bash, read_file, etc.)              │
│  - 可以调用 Task 工具 (spawn subagent)                       │
│  - 可以调用 spawn_teammate 工具 (spawn TeamAgent)           │
└──────────────┬────────────────────────┬─────────────────────┘
               ↓                        ↓
    ┌──────────────────┐    ┌──────────────────────┐
    │  Task (Subagent) │    │  spawn_teammate      │
    │                  │    │  (TeamAgent)         │
    └────────┬─────────┘    └──────────┬───────────┘
             ↓                         ↓
┌────────────────────────┐  ┌─────────────────────────────────┐
│   Subagent Loop        │  │      TeamAgent Loop              │
│  - 普通工具 ✅         │  │  - 普通工具 ✅                   │
│  - Task 工具 ✅       │  │  - Task 工具 ✅                 │
│  - spawn_teammate ❌  │  │  - spawn_teammate ❌             │
│  - 2种模式:            │  │  - 通信工具 (send_message, etc.) │
│    * ReAct Loop        │  │  - 任务认领 (claim_task)         │
│    * OODA Loop         │  │  - 独立线程运行                   │
└────────────────────────┘  └─────────────────────────────────┘
```

## 三层架构

### 1. MainAgent (主 Agent)

**职责**：
- 接收用户输入
- 直接执行简单任务（调用普通工具）
- 委派复杂任务给 Subagent 或 TeamAgent
- 整合结果返回给用户

**可用工具**：
- 所有普通工具（bash, read_file, write_file, edit_file, glob, grep, etc.）
- `Task` 工具（spawn Subagent）
- `spawn_teammate` 工具（spawn TeamAgent）

**实现**：
- 使用 `MainAgentContext`
- 使用 `MainAgentService` (继承 `AgentService`)
- 工具权限：`scope="main"`

---

### 2. TeamAgent (团队 Agent)

**职责**：
- 作为独立的 Agent 运行在后台线程
- 通过消息总线与 MainAgent 和其他 TeamAgent 通信
- 可以认领任务、执行任务、报告进度
- 可以调用 Subagent 处理子任务

**可用工具**：
- 所有普通工具 ✅
- `Task` 工具（spawn Subagent）✅
- `spawn_teammate` 工具 ❌（防止无限递归）
- 通信工具：
  - `send_message` - 发送消息给其他 teammate
  - `read_inbox` - 读取收件箱
  - `claim_task` - 认领任务
  - `report_progress` - 报告进度

**实现**：
- 使用 `TeamAgentContext` (新增)
- 使用 `TeamAgentService` (继承 `AgentService`)
- 工具权限：`scope="team"`
- 运行在独立线程中

**通信机制**：
- 消息总线（MessageBus）
- 任务队列（TaskQueue）
- 状态同步（StateSync）

---

### 3. Subagent (子 Agent)

**职责**：
- 执行专门的子任务（探索、规划、编码、反思等）
- 在隔离的上下文中运行
- 完成后返回结果

**可用工具**：
- 根据 Agent 类型过滤的工具列表
- 不包含 `spawn_teammate` 工具 ❌

**执行模式**：
1. **ReAct Loop**（默认）
   - 适用于大多数任务
   - Reason → Act → Observe → repeat
   - 例如：Explore, Plan, Coding, general-purpose

2. **OODA Loop**（迭代探索）
   - 适用于不确定性高的任务
   - Observe → Orient → Decide → Act → repeat
   - 例如：需要多轮探索的复杂分析

**实现**：
- 使用 `SubagentContext`
- 使用 `SubagentRunner`
- 工具权限：`scope="subagent"`

---

## 工具权限隔离

### 工具 Scope 定义

```python
# tools/base.py
@tool(tags=["main"])  # 只有 MainAgent 可用
def spawn_teammate(...): ...

@tool(tags=["both"])  # MainAgent 和 TeamAgent 都可用
def Task(...): ...

@tool(tags=["both"])  # 所有 Agent 都可用
def bash(...): ...
def read_file(...): ...
```

### 权限矩阵

| 工具 | MainAgent | TeamAgent | Subagent |
|------|-----------|-----------|----------|
| bash, read_file, write_file, etc. | ✅ | ✅ | ✅ |
| Task (spawn subagent) | ✅ | ✅ | ✅ |
| spawn_teammate | ✅ | ❌ | ❌ |
| send_message, read_inbox | ❌ | ✅ | ❌ |
| claim_task, report_progress | ❌ | ✅ | ❌ |

---

## 核心类设计

### 1. AgentService (基类)

```python
class AgentService:
    """Agent 服务基类 - 通用的 agent loop 逻辑"""

    def __init__(self, context: BaseContext):
        self.context = context
        # ... 共享组件

    async def run(self, prompt: str, history: list) -> str:
        """通用的 agent loop"""
        # 1. 准备上下文
        # 2. 构建消息
        # 3. 执行 agent loop
        # 4. 保存对话
        # 5. 返回结果
```

### 2. MainAgentService (主 Agent)

```python
class MainAgentService(AgentService):
    """主 Agent 服务"""

    def __init__(self, session_key: str = None):
        context = MainAgentContext(session_key or "")
        super().__init__(context)

    # 继承 run() 方法，无需重写
```

### 3. TeamAgentService (团队 Agent)

```python
class TeamAgentService(AgentService):
    """团队 Agent 服务 - 运行在独立线程"""

    def __init__(self, name: str, role: str, session_key: str):
        context = TeamAgentContext(name, role, session_key)
        super().__init__(context)
        self.message_bus = MessageBus()
        self.task_queue = TaskQueue()

    async def run_loop(self, initial_prompt: str):
        """独立线程中的主循环"""
        messages = []

        while True:
            # 1. 检查收件箱
            inbox = self.message_bus.read_inbox(self.name)

            # 2. 检查任务队列
            task = self.task_queue.claim_task(self.name)

            # 3. 构建 prompt
            if inbox:
                prompt = self._build_inbox_prompt(inbox)
            elif task:
                prompt = self._build_task_prompt(task)
            else:
                # 空闲，等待
                await asyncio.sleep(POLL_INTERVAL)
                continue

            # 4. 执行 agent loop
            output = await self.run(prompt, messages)

            # 5. 报告结果
            if task:
                self.task_queue.complete_task(task.id, output)
```

### 4. SubagentRunner (子 Agent 执行器)

```python
class SubagentRunner:
    """Subagent 执行器 - 根据配置选择执行模式"""

    def run(self, sub_context: SubagentContext, description: str, prompt: str) -> str:
        """运行 Subagent"""
        agent_config = registry.get(sub_context.subagent_type)

        # 根据 loop_type 选择执行模式
        if agent_config.loop_type == "react":
            return self._run_react_loop(...)
        elif agent_config.loop_type == "ooda":
            return self._run_ooda_loop(...)
        else:  # direct
            return self._run_direct(...)
```

---

## Context 层级

### 1. BaseContext (基础上下文)

```python
class BaseContext:
    """所有 Agent 共享的资源"""

    def __init__(self, session_key: str):
        self.session_key = session_key
        self.session_store = get_store()
        self.llm = get_llm()
        self.tracer = Tracer()
        self.conversation_history = ConversationHistory(...)
        self.overflow_guard = OverflowGuard(...)
```

### 2. MainAgentContext (主 Agent 上下文)

```python
class MainAgentContext(BaseContext):
    """主 Agent 上下文"""

    def __init__(self, session_key: str):
        super().__init__(session_key)

        # Main Agent 独有资源
        self.tools = tool_manager.get_main_tools()  # 包含 Task + spawn_teammate
        self.system_prompt = get_system_prompt(session_key)
        self.agent = create_agent(self.llm, self.tools, self.system_prompt)
```

### 3. TeamAgentContext (团队 Agent 上下文)

```python
class TeamAgentContext(BaseContext):
    """团队 Agent 上下文"""

    def __init__(self, name: str, role: str, session_key: str):
        super().__init__(session_key)

        self.name = name
        self.role = role

        # TeamAgent 独有资源
        self.tools = tool_manager.get_team_tools()  # 包含 Task + 通信工具，不包含 spawn_teammate
        self.system_prompt = self._build_team_prompt(role)
        self.agent = create_agent(self.llm, self.tools, self.system_prompt)

        # 通信组件
        self.message_bus = MessageBus()
        self.task_queue = TaskQueue()
```

### 4. SubagentContext (子 Agent 上下文)

```python
class SubagentContext(BaseContext):
    """子 Agent 上下文"""

    def __init__(self, session_key: str, subagent_type: str):
        super().__init__(session_key)

        self.subagent_type = subagent_type
        self.agent_config = registry.get(subagent_type)

        # Subagent 独有资源
        self.tools = self._filter_tools()  # 根据配置过滤，不包含 spawn_teammate
        self.system_prompt = self.agent_config.prompt
        self.agent = create_agent(self.llm, self.tools, self.system_prompt)
```

---

## 工具注册机制重构

### ToolsManager 增强

```python
class ToolsManager:
    """工具注册中心 - 支持权限隔离"""

    def get_tools(self, scope: str = "all") -> list:
        """
        根据 scope 获取工具列表

        Args:
            scope: "main" | "team" | "subagent" | "all"

        Returns:
            过滤后的工具列表
        """
        if scope == "all":
            return list(self._tools.values())

        filtered = []
        for tool in self._tools.values():
            tags = getattr(tool, "tags", None) or []

            # 判断工具的 scope
            if "main" in tags:
                tool_scope = "main"
            elif "team" in tags:
                tool_scope = "team"
            elif "subagent" in tags:
                tool_scope = "subagent"
            else:
                tool_scope = "both"  # 默认所有 Agent 都可用

            # 过滤逻辑
            if tool_scope == "both":
                filtered.append(tool)
            elif scope == "main" and tool_scope in ("main", "both"):
                filtered.append(tool)
            elif scope == "team" and tool_scope in ("team", "both"):
                filtered.append(tool)
            elif scope == "subagent" and tool_scope in ("subagent", "both"):
                filtered.append(tool)

        return filtered

    def get_main_tools(self) -> list:
        """获取 MainAgent 工具（包含 Task + spawn_teammate）"""
        return self.get_tools(scope="main")

    def get_team_tools(self) -> list:
        """获取 TeamAgent 工具（包含 Task + 通信工具，不包含 spawn_teammate）"""
        return self.get_tools(scope="team")

    def get_subagent_tools(self) -> list:
        """获取 Subagent 工具（不包含 spawn_teammate）"""
        return self.get_tools(scope="subagent")
```

---

## 通信机制设计

### MessageBus (消息总线)

```python
class MessageBus:
    """消息总线 - TeamAgent 之间的通信"""

    def __init__(self):
        self._inboxes: Dict[str, List[Message]] = {}
        self._lock = threading.Lock()

    def send(self, from_name: str, to_name: str, content: str, msg_type: str = "message") -> str:
        """发送消息"""
        with self._lock:
            if to_name not in self._inboxes:
                self._inboxes[to_name] = []

            msg = Message(
                id=str(uuid.uuid4()),
                from_name=from_name,
                to_name=to_name,
                content=content,
                msg_type=msg_type,
                timestamp=time.time()
            )
            self._inboxes[to_name].append(msg)

        return f"Message sent to {to_name}"

    def read_inbox(self, name: str) -> List[Message]:
        """读取并清空收件箱"""
        with self._lock:
            messages = self._inboxes.get(name, [])
            self._inboxes[name] = []
            return messages
```

### TaskQueue (任务队列)

```python
class TaskQueue:
    """任务队列 - TeamAgent 认领任务"""

    def __init__(self):
        self._tasks: Dict[str, Task] = {}
        self._lock = threading.Lock()

    def add_task(self, task: Task) -> str:
        """添加任务到队列"""
        with self._lock:
            self._tasks[task.id] = task
        return task.id

    def claim_task(self, agent_name: str) -> Optional[Task]:
        """认领一个未分配的任务"""
        with self._lock:
            for task in self._tasks.values():
                if task.status == "pending":
                    task.status = "claimed"
                    task.assignee = agent_name
                    return task
        return None

    def complete_task(self, task_id: str, result: str):
        """完成任务"""
        with self._lock:
            if task_id in self._tasks:
                self._tasks[task_id].status = "completed"
                self._tasks[task_id].result = result
```

---

## 执行流程示例

### 场景 1: MainAgent 直接处理简单任务

```
User: "读取 README.md 文件"
  ↓
MainAgent Loop:
  ├─ 决策: 直接调用 read_file 工具
  ├─ 执行: read_file("README.md")
  └─ 返回: 文件内容
```

### 场景 2: MainAgent 委派给 Subagent

```
User: "探索代码库，找到所有 API 端点"
  ↓
MainAgent Loop:
  ├─ 决策: 任务复杂，调用 Task 工具
  ├─ 执行: Task(subagent_type="Explore", prompt="找到所有 API 端点")
  │   ↓
  │  Subagent Loop (Explore):
  │   ├─ 调用 glob("**/*.py")
  │   ├─ 调用 grep("@router")
  │   ├─ 调用 read_file(...)
  │   └─ 返回: "找到 15 个 API 端点: ..."
  │       ↓
  └─ 返回: Subagent 的结果
```

### 场景 3: MainAgent 委派给 TeamAgent

```
User: "启动一个后台 Agent 持续监控日志"
  ↓
MainAgent Loop:
  ├─ 决策: 需要长期运行，调用 spawn_teammate
  ├─ 执行: spawn_teammate(name="logger", role="monitor", prompt="监控日志")
  │   ↓
  │  TeamAgent Loop (独立线程):
  │   ├─ 初始化: 创建 TeamAgentContext
  │   ├─ 主循环:
  │   │   ├─ 检查收件箱
  │   │   ├─ 认领任务
  │   │   ├─ 执行任务 (可以调用 Task spawn Subagent)
  │   │   ├─ 报告进度
  │   │   └─ 等待下一轮
  │   └─ 持续运行...
  │       ↓
  └─ 返回: "Spawned 'logger' (role: monitor)"
```

### 场景 4: TeamAgent 调用 Subagent

```
TeamAgent Loop (logger):
  ├─ 收到任务: "分析最近的错误日志"
  ├─ 决策: 需要深度分析，调用 Task 工具
  ├─ 执行: Task(subagent_type="Explore", prompt="分析错误日志")
  │   ↓
  │  Subagent Loop (Explore):
  │   ├─ 调用 bash("tail -n 100 app.log")
  │   ├─ 调用 grep("ERROR")
  │   └─ 返回: "发现 3 个错误: ..."
  │       ↓
  ├─ 整合结果
  └─ 发送消息给 MainAgent: send_message("main", "错误分析完成: ...")
```

---

## 实现计划

### Phase 1: 重构 AgentService (基类)

1. 保持 `agent.py` 中的 `AgentService` 作为基类
2. 提取通用的 loop 逻辑
3. 支持不同的 Context 类型

### Phase 2: 实现 MainAgentService

1. 创建 `backend/app/agents/main_agent.py`
2. 继承 `AgentService`
3. 使用 `MainAgentContext`
4. 工具权限：`scope="main"`

### Phase 3: 实现 TeamAgentContext

1. 创建 `backend/app/context/team_context.py`
2. 继承 `BaseContext`
3. 添加通信组件（MessageBus, TaskQueue）
4. 过滤工具：排除 `spawn_teammate`

### Phase 4: 实现 TeamAgentService

1. 创建 `backend/app/agents/team_agent.py`
2. 继承 `AgentService`
3. 实现独立线程的主循环
4. 实现通信逻辑

### Phase 5: 重构工具权限

1. 修改 `tools/base.py`，支持 `tags` 参数
2. 修改 `tools/manager.py`，实现 `get_team_tools()`
3. 给 `spawn_teammate` 添加 `tags=["main"]`
4. 给通信工具添加 `tags=["team"]`

### Phase 6: 更新 Subagent

1. 确保 Subagent 不能调用 `spawn_teammate`
2. 保持现有的 ReAct/OODA 双模式
3. 工具权限：`scope="subagent"`

---

## 关键设计决策

### 1. 为什么 TeamAgent 不能调用 spawn_teammate？

**原因**：防止无限递归和资源耗尽
- TeamAgent 已经是后台线程
- 如果 TeamAgent 再 spawn TeamAgent，会导致线程爆炸
- MainAgent 是唯一的"指挥官"，负责团队管理

### 2. 为什么 TeamAgent 可以调用 Task (Subagent)？

**原因**：TeamAgent 需要处理复杂任务
- Subagent 是同步执行，不会创建新线程
- Subagent 在隔离上下文中运行，不会污染 TeamAgent 的状态
- 这是合理的"委派"模式

### 3. 为什么需要 TeamAgent？

**原因**：支持长期运行的后台任务
- 监控日志、定期检查、持续集成等
- 与 MainAgent 并行工作，不阻塞用户交互
- 通过消息总线协作

### 4. ReAct vs OODA 如何选择？

**ReAct Loop**：
- 适用于目标明确的任务
- 快速执行，直接返回结果
- 例如：Explore, Plan, Coding

**OODA Loop**：
- 适用于不确定性高的任务
- 需要多轮观察和调整
- 例如：复杂的问题诊断、探索性分析

---

## 文件结构

```
backend/app/
├── agent.py                    # AgentService (基类) ✅ 保留
├── agents/                     # Agent 实现 ⭐新增
│   ├── __init__.py
│   ├── main_agent.py           # MainAgentService
│   └── team_agent.py           # TeamAgentService
│
├── context/
│   ├── base_context.py         # BaseContext ✅ 保留
│   ├── main_context.py         # MainAgentContext ✅ 保留
│   ├── team_context.py         # TeamAgentContext ⭐新增
│   └── subagent_context.py     # SubagentContext ✅ 保留
│
├── subagents/
│   ├── registry/               # Agent 注册表 ✅ 保留
│   ├── loops/                  # 执行循环 ✅ 保留
│   │   ├── react_loop.py       # ReAct Loop
│   │   └── ooda_loop.py        # OODA Loop
│   └── runner/                 # 执行器 ✅ 保留
│       └── runner.py           # SubagentRunner
│
├── team/                       # 团队协作 ✅ 保留
│   ├── message_bus.py          # 消息总线
│   ├── task_queue.py           # 任务队列
│   └── teammate_manager.py     # 团队管理器
│
└── tools/
    ├── manager.py              # ToolsManager ✅ 增强
    └── implementations/
        ├── agent/
        │   ├── spawn_tool.py   # Task 工具 ✅ 保留
        │   └── team_tool.py    # spawn_teammate ✅ 保留
        └── system/
            └── communication_tools.py  # 通信工具 ⭐新增
```

---

## 下一步

1. 创建架构设计文档 ✅ (当前文档)
2. 实现 `TeamAgentContext`
3. 实现 `MainAgentService`
4. 实现 `TeamAgentService`
5. 重构 `ToolsManager` 权限机制
6. 创建通信工具
7. 测试整体流程
