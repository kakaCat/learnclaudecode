---
title: "一切皆文件：用 JSON 文件解决 Agent 的「失忆」与「孤岛」问题"
description: "TodoWrite 在压缩后消失，子 Agent 看不到父 Agent 的任务列表——v6_agent.py 用最朴素的方案解决了这两个问题：把任务写成文件。本文解析 TaskManager 的设计逻辑，以及「状态外置」这个核心思想。"
image: "/images/blog/persistent-tasks.jpg"
keywords:
  - Claude Code
  - AI Agent
  - Persistent Tasks
  - Context Compression
  - Multi-Agent
  - Anthropic
tags:
  - Agent
  - Tasks
  - Memory
  - Multi-Agent
  - Implementation
author: "manus-learn"
date: "2026-02-24"
last_modified_at: "2026-02-24"
lang: "zh-CN"
audience: "开发者 / 对 AI Agent 感兴趣的工程师"
difficulty: "intermediate"
estimated_read_time: "12-15min"
topics:
  - Persistent State
  - Everything is a File
  - Multi-Agent Coordination
  - Task Dependencies
series: "从零构建 Claude Code"
series_order: 7
---

# 构建mini Claude Code：07 - 一切皆文件：持久化任务系统

## 📍 导航指南

这是「从零构建 Claude Code」系列的第七篇。根据你的背景，选择合适的阅读路径：

- 🧠 **理论派？** → [第一部分：两个根本问题](#part-1) - 理解为什么 TodoWrite 不够用
- ⚙️ **实践派？** → [第二部分：TaskManager 设计](#part-2) - 掌握持久化任务的设计逻辑
- 💻 **代码派？** → [第三部分：代码实现](#part-3) - 直接看完整实现
- 🔭 **探索派？** → [第四部分：扩展方向](#part-4) - 还有哪些思路值得尝试

---

## 目录

### 第一部分：理论基础 🧠
- [TodoWrite 的两个致命缺陷](#todo-limits)
- [问题一：压缩后失忆](#problem-compression)
- [问题二：多 Agent 孤岛](#problem-isolation)
- [核心洞察：状态外置](#core-insight)

### 第二部分：TaskManager 设计 ⚙️
- [一切皆文件：设计哲学](#everything-is-file)
- [任务结构：最小化 JSON](#task-structure)
- [依赖图：blockedBy / blocks](#dependency-graph)
- [四个工具：CRUD 接口](#four-tools)

### 第三部分：代码实现 💻
- [TaskManager 类](#taskmanager-code)
- [工具定义](#tool-definitions)
- [主循环集成](#main-loop)

### 第四部分：扩展方向 🔭
- [多 Agent 任务看板](#multi-agent-board)
- [任务事件通知](#task-events)
- [任务历史与审计](#task-history)

### 附录
- [常见问题 FAQ](#faq)

---

## 引言

上一篇我们解决了 Agent 的「撑死」问题——三层压缩流水线让 Agent 能长时间运行。

但压缩带来了一个新问题：**TodoWrite 里的任务列表，在压缩后消失了。**

更深层的问题是：当 Agent 派生出子 Agent 处理子任务时，子 Agent 根本看不到父 Agent 的任务列表。两个 Agent 各自维护各自的 todos，互相不知道对方在做什么。

`v6_agent.py` 用一个极其朴素的方案解决了这两个问题：**把任务写成文件**。

---

<a id="part-1"></a>
## 第一部分：理论基础 🧠

<a id="todo-limits"></a>
### TodoWrite 的两个致命缺陷

TodoWrite 是一个优秀的工具——它让 Agent 在单次会话中追踪多步骤任务，给用户可见的进度反馈。

但它有两个根本性的局限：

```
TodoWrite 的本质:
  - 存储位置: 内存（Python 对象）
  - 生命周期: 当前会话
  - 可见范围: 当前 Agent

这意味着:
  - 上下文压缩 → 内存不变，但 Agent 「忘记」了 todos 的存在
  - 子 Agent 启动 → 新的进程，看不到父 Agent 的内存
```

<a id="problem-compression"></a>
### 问题一：压缩后失忆

回顾上一篇的 auto_compact：它把整个 messages 替换为一段摘要。

```
压缩前:
  messages = [
    ...50 条消息...,
    {role: "user", content: [tool_result: "TodoWrite 结果: [>] 步骤3 <- 正在执行"]}
  ]

压缩后:
  messages = [
    {role: "user", content: "摘要: 已完成步骤1和2，正在执行步骤3..."},
    {role: "assistant", content: "Understood. Continuing."}
  ]
```

摘要里可能提到「正在执行步骤3」，但 TodoManager 对象里的 `items` 列表已经和 messages 脱节了。

更糟的是：Agent 在压缩后继续工作，它可能重新调用 TodoWrite 创建一个全新的任务列表，和之前的任务列表毫无关联。**任务的连续性断了。**

<a id="problem-isolation"></a>
### 问题二：多 Agent 孤岛

当主 Agent 派生子 Agent 时：

```python
# 主 Agent 调用 Task 工具
run_task(
    description="实现用户认证模块",
    prompt="实现 JWT 认证，包括登录、注册、token 刷新",
    subagent_type="general-purpose"
)
```

子 Agent 在 `run_task` 函数里启动，它有自己的 `sub_messages`，但：

- 看不到主 Agent 的 TodoWrite 列表
- 不知道主 Agent 还有哪些任务在等待
- 完成后只能通过返回文本告知主 Agent 结果

这是一个**信息孤岛**问题。每个 Agent 都在自己的上下文泡泡里工作，无法共享任务状态。

```
主 Agent:
  TodoWrite: [>] 实现认证模块, [ ] 实现用户管理, [ ] 写测试
  ↓ 派生子 Agent
  子 Agent:
    TodoWrite: [>] 实现 JWT, [ ] 实现登录接口, [ ] 实现注册接口
    （主 Agent 完全不知道子 Agent 的进度）
```

<a id="core-insight"></a>
### 核心洞察：状态外置

v6_agent.py 的注释里有一句话，是整个设计的核心：

```
Key insight: "State that survives compression -- because it's outside the conversation."
```

**状态外置**：把需要持久化的状态放到对话上下文之外。

对话上下文（messages）是易失的——它会被压缩、被截断、被替换。但文件系统是持久的。

```
易失的（会被压缩）:
  - messages 列表
  - TodoManager.items（内存对象）
  - 工具调用结果

持久的（压缩后依然存在）:
  - .tasks/ 目录下的 JSON 文件
  - .transcripts/ 目录下的对话记录
  - 代码文件、配置文件
```

这个洞察不复杂，但它解决了根本问题：**任何 Agent，在任何时刻，都可以读取 `.tasks/` 目录，获得完整的任务状态。**

---

<a id="part-2"></a>
## 第二部分：TaskManager 设计 ⚙️

<a id="everything-is-file"></a>
### 一切皆文件：设计哲学

Unix 哲学有一条：「一切皆文件」。

TaskManager 把这个哲学用到了极致：

```
.tasks/
  task_1.json   ← 一个任务 = 一个文件
  task_2.json
  task_3.json
```

为什么是文件，而不是数据库？

```
文件的优势:
  ✅ 零依赖（不需要安装任何数据库）
  ✅ 人类可读（直接打开 JSON 文件查看）
  ✅ Agent 可读（read_file 工具直接读取）
  ✅ 天然持久化（文件系统保证）
  ✅ 天然共享（多个 Agent 读同一个目录）
  ✅ 天然版本控制（可以 git 追踪）

文件的代价:
  ❌ 并发写入需要注意（但 Agent 通常是串行的）
  ❌ 查询不如数据库灵活（但任务数量通常很少）
```

对于 Agent 的任务管理场景，文件是最合适的选择。

<a id="task-structure"></a>
### 任务结构：最小化 JSON

每个任务文件的结构：

```json
{
  "id": 1,
  "subject": "实现用户认证模块",
  "description": "包括 JWT 登录、注册、token 刷新",
  "status": "in_progress",
  "blockedBy": [],
  "blocks": [2, 3],
  "owner": ""
}
```

字段设计遵循最小化原则：

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int | 自增 ID，文件名也用这个 |
| `subject` | str | 一句话描述任务 |
| `description` | str | 可选的详细说明 |
| `status` | str | `pending` / `in_progress` / `completed` |
| `blockedBy` | list[int] | 被哪些任务阻塞（前置依赖） |
| `blocks` | list[int] | 阻塞哪些任务（后置依赖） |
| `owner` | str | 任务负责人（可选） |

没有时间戳、没有标签、没有优先级——这些都可以加，但最小化设计让核心逻辑保持清晰。

<a id="dependency-graph"></a>
### 依赖图：blockedBy / blocks

任务之间的依赖关系是 TaskManager 最有价值的设计。

```
任务依赖示例:
  task_1: 设计数据库 Schema
  task_2: 实现 Repository 层  (blockedBy: [1])
  task_3: 实现 Service 层     (blockedBy: [2])
  task_4: 实现 API 接口       (blockedBy: [3])
  task_5: 写集成测试          (blockedBy: [4])
```

当 task_1 完成时，TaskManager 自动从 task_2 的 `blockedBy` 列表中移除 task_1：

```python
if status == "completed":
    for f in self.dir.glob("task_*.json"):
        t = json.loads(f.read_text())
        if task_id in t.get("blockedBy", []):
            t["blockedBy"].remove(task_id)
            self._save(t)
```

这个自动解锁机制让 Agent 可以查询「哪些任务现在可以开始」：

```
task_list 输出:
  [x] #1: 设计数据库 Schema
  [ ] #2: 实现 Repository 层        ← blockedBy 已清空，可以开始
  [ ] #3: 实现 Service 层           (blocked by: [2])
  [ ] #4: 实现 API 接口             (blocked by: [3])
  [ ] #5: 写集成测试                (blocked by: [4])
```

Agent 看到这个列表，知道下一步应该做 task_2。

<a id="four-tools"></a>
### 四个工具：CRUD 接口

TaskManager 通过四个工具暴露给 Agent：

```
task_create  → 创建新任务（写文件）
task_update  → 更新状态/依赖（改文件）
task_list    → 查看所有任务（读目录）
task_get     → 查看单个任务详情（读文件）
```

这是最标准的 CRUD 接口，Agent 很容易理解和使用。

关键设计：**子 Agent 不能使用这四个工具**。

```python
def get_tools_for_agent(agent_type: str) -> list:
    excluded = {"compact", "task_create", "task_update", "task_list", "task_get"}
    if allowed == "*":
        return [t for t in BASE_TOOLS if t["name"] not in excluded]
```

为什么？因为任务的创建和状态管理应该由主 Agent 负责。子 Agent 专注于执行，主 Agent 负责协调。这避免了子 Agent 随意修改任务状态导致的混乱。

---

<a id="part-3"></a>
## 第三部分：代码实现 💻

<a id="taskmanager-code"></a>
### TaskManager 类

```python
class TaskManager:
    def __init__(self, tasks_dir: Path):
        self.dir = tasks_dir
        self.dir.mkdir(exist_ok=True)
        self._next_id = self._max_id() + 1

    def _max_id(self) -> int:
        ids = [int(f.stem.split("_")[1]) for f in self.dir.glob("task_*.json")]
        return max(ids) if ids else 0

    def _load(self, task_id: int) -> dict:
        path = self.dir / f"task_{task_id}.json"
        if not path.exists():
            raise ValueError(f"Task {task_id} not found")
        return json.loads(path.read_text())

    def _save(self, task: dict):
        (self.dir / f"task_{task['id']}.json").write_text(json.dumps(task, indent=2))
```

注意 `_max_id()`：每次启动时扫描 `.tasks/` 目录，找到最大 ID，从那里继续计数。这保证了跨会话的 ID 连续性——即使 Agent 重启，也不会创建重复 ID 的任务。

```python
    def create(self, subject: str, description: str = "") -> str:
        task = {"id": self._next_id, "subject": subject, "description": description,
                "status": "pending", "blockedBy": [], "blocks": [], "owner": ""}
        self._save(task)
        self._next_id += 1
        return json.dumps(task, indent=2)
```

`create` 返回完整的任务 JSON——Agent 立刻知道新任务的 ID，可以在后续调用中引用它。

```python
    def update(self, task_id: int, status: str = None,
               add_blocked_by: list = None, add_blocks: list = None) -> str:
        task = self._load(task_id)
        if status:
            if status not in ("pending", "in_progress", "completed"):
                raise ValueError(f"Invalid status: {status}")
            task["status"] = status
            if status == "completed":
                # 自动解锁：从所有依赖此任务的任务中移除阻塞
                for f in self.dir.glob("task_*.json"):
                    t = json.loads(f.read_text())
                    if task_id in t.get("blockedBy", []):
                        t["blockedBy"].remove(task_id)
                        self._save(t)
        if add_blocks:
            task["blocks"] = list(set(task["blocks"] + add_blocks))
            for bid in add_blocks:
                try:
                    b = self._load(bid)
                    if task_id not in b["blockedBy"]:
                        b["blockedBy"].append(task_id)
                        self._save(b)
                except ValueError:
                    pass
        self._save(task)
        return json.dumps(task, indent=2)
```

`update` 里有一个双向同步：当设置 `add_blocks=[2, 3]` 时，不仅更新当前任务的 `blocks` 字段，还自动更新 task_2 和 task_3 的 `blockedBy` 字段。依赖关系始终保持双向一致。

```python
    def list_all(self) -> str:
        tasks = [json.loads(f.read_text()) for f in sorted(self.dir.glob("task_*.json"))]
        if not tasks:
            return "No tasks."
        lines = []
        for t in tasks:
            marker = {"pending": "[ ]", "in_progress": "[>]", "completed": "[x]"}.get(t["status"], "[?]")
            blocked = f" (blocked by: {t['blockedBy']})" if t.get("blockedBy") else ""
            lines.append(f"{marker} #{t['id']}: {t['subject']}{blocked}")
        return "\n".join(lines)
```

`list_all` 的输出格式和 TodoWrite 类似，Agent 很容易理解：

```
[x] #1: 设计数据库 Schema
[>] #2: 实现 Repository 层
[ ] #3: 实现 Service 层 (blocked by: [2])
[ ] #4: 实现 API 接口 (blocked by: [3])
```

<a id="tool-definitions"></a>
### 工具定义

```python
{"name": "task_create",
 "description": "Create a persistent task (survives context compression). Stored in .tasks/.",
 "input_schema": {"type": "object",
                  "properties": {"subject": {"type": "string"},
                                 "description": {"type": "string"}},
                  "required": ["subject"]}},

{"name": "task_update",
 "description": "Update a persistent task's status or dependencies.",
 "input_schema": {"type": "object",
                  "properties": {"task_id": {"type": "integer"},
                                 "status": {"type": "string",
                                            "enum": ["pending", "in_progress", "completed"]},
                                 "addBlockedBy": {"type": "array", "items": {"type": "integer"}},
                                 "addBlocks": {"type": "array", "items": {"type": "integer"}}},
                  "required": ["task_id"]}},
```

工具描述里明确写了「survives context compression」——这是给 Agent 的提示：当你需要追踪跨压缩的任务时，用 task_* 工具，而不是 TodoWrite。

<a id="main-loop"></a>
### 主循环集成

TaskManager 的集成非常轻量——它只是在 `execute_tool` 里增加了四个分支：

```python
def execute_tool(name: str, args: dict) -> str:
    # ... 其他工具 ...
    if name == "task_create":   return TASKS.create(args["subject"], args.get("description", ""))
    if name == "task_update":   return TASKS.update(args["task_id"], args.get("status"),
                                                     args.get("addBlockedBy"), args.get("addBlocks"))
    if name == "task_list":     return TASKS.list_all()
    if name == "task_get":      return TASKS.get(args["task_id"])
```

主循环本身不需要任何修改。TaskManager 是一个纯粹的工具——Agent 决定什么时候用它，主循环只负责路由调用。

---

<a id="part-4"></a>
## 第四部分：扩展方向 🔭

<a id="multi-agent-board"></a>
### 方向一：多 Agent 任务看板

当前实现中，子 Agent 不能读写任务。但如果我们允许子 Agent 读取任务（只读），就能实现一个简单的任务看板：

```
主 Agent 创建任务:
  task_1: 实现认证模块  → 派生子 Agent A
  task_2: 实现用户管理  → 派生子 Agent B
  task_3: 写集成测试    → 派生子 Agent C（等待 A 和 B 完成）

子 Agent A 完成后:
  主 Agent: task_update(1, status="completed")
  → task_3 的 blockedBy 自动减少
  → 主 Agent 检查 task_list，发现 task_3 可以开始
  → 派生子 Agent C
```

这是一个简单的 DAG（有向无环图）任务调度器，完全基于文件实现。

<a id="task-events"></a>
### 方向二：任务事件通知

当前的任务状态变更是「拉取」模式——Agent 需要主动调用 `task_list` 才能知道状态变化。

可以扩展为「推送」模式：在任务状态变更时写入事件文件：

```python
def _emit_event(self, task_id: int, event_type: str):
    events_dir = self.dir / "events"
    events_dir.mkdir(exist_ok=True)
    event = {"task_id": task_id, "type": event_type, "timestamp": time.time()}
    (events_dir / f"{int(time.time())}_{task_id}_{event_type}.json").write_text(
        json.dumps(event)
    )
```

Agent 可以定期检查 `events/` 目录，响应任务状态变化。这是一个极简的事件总线，同样基于文件。

<a id="task-history"></a>
### 方向三：任务历史与审计

当前实现中，任务完成后文件依然存在（只是 status 变为 completed）。可以扩展为保留完整的状态变更历史：

```python
def _append_history(self, task: dict, change: dict):
    history_path = self.dir / f"task_{task['id']}_history.jsonl"
    with open(history_path, "a") as f:
        f.write(json.dumps({"timestamp": time.time(), **change}) + "\n")
```

这样每个任务都有完整的审计日志：什么时候创建、什么时候开始、什么时候完成、中间经历了哪些状态变化。

---

<a id="faq"></a>
## 常见问题 FAQ

**Q: task_* 工具和 TodoWrite 应该怎么选？**

A: 两者定位不同，可以同时使用。

```
TodoWrite:
  - 当前会话内的短期任务追踪
  - 给用户实时的进度反馈
  - 不需要跨会话或跨 Agent 共享

task_* 工具:
  - 需要跨上下文压缩的长期任务
  - 需要多个 Agent 协作的任务
  - 有依赖关系的复杂任务
  - 需要在会话结束后继续追踪的任务
```

典型用法：用 task_* 管理「项目级」任务，用 TodoWrite 管理「当前步骤」的子任务。

**Q: 任务文件会越来越多吗？**

A: 会。但这通常不是问题——任务文件很小（几百字节），几千个任务也只占几 MB。如果需要清理，可以手动删除 completed 状态的任务文件，或者写一个归档脚本把旧任务移到 `.tasks/archive/`。

**Q: 多个 Agent 同时写同一个任务文件会有冲突吗？**

A: 理论上会，但实践中很少发生。当前实现中，子 Agent 不能写任务文件，只有主 Agent 可以写。如果需要真正的并发安全，可以用文件锁（`fcntl.flock`）或者原子写入（写临时文件再重命名）。

**Q: 为什么不用 SQLite 而用 JSON 文件？**

A: 零依赖。JSON 文件不需要安装任何库，不需要初始化数据库，不需要管理连接。对于 Agent 的任务管理场景，任务数量通常在几十到几百之间，JSON 文件完全够用。SQLite 的优势（事务、索引、复杂查询）在这个场景下用不上。

---

## 📝 结语

TaskManager 的设计体现了一个简单但深刻的原则：

```
对话上下文是易失的，文件系统是持久的。
需要持久化的状态，就放到文件里。
```

这不是什么新思想——Unix 几十年前就这么做了。但在 AI Agent 的语境下，这个原则解决了两个具体问题：

```
问题                    解决方案
─────────────────────────────────────────────────────
压缩后 todos 消失    → 任务写文件，压缩不影响文件
子 Agent 看不到任务  → 任务在文件系统，任何 Agent 都能读
```

更深层的意义是：**Agent 的「记忆」不应该只存在于对话上下文里**。对话上下文是工作记忆，文件系统是长期记忆。两者各司其职，Agent 才能真正「长时间工作」。

这和上一篇的上下文压缩是互补的：压缩解决了「工作记忆太满」的问题，持久化任务解决了「压缩后状态丢失」的问题。两者合在一起，Agent 才能在复杂的长任务中保持连贯性。

**系列导航**：
- **上一篇**: [06 - Agent 如何「战略性遗忘」（上下文压缩）](./006-context-compaction.md)
- **当前**:   [07 - 一切皆文件：持久化任务系统]()
- **下一篇**: 08 - 多 Agent 团队协作
