---
title: "从「被动等待」到「主动找活」：Autonomous Agents 如何让 Teammate 真正自主"
description: "Team Protocols 解决了协作冲突，但 Teammate 仍是被动的——没有任务就干等。v10_agent.py 引入 idle + claim_task + 任务看板，让 Teammate 在空闲时自动扫描、认领、执行任务，实现真正的自主 Agent。"
image: "/images/blog/autonomous-agents.jpg"
keywords:
  - Claude Code
  - AI Agent
  - Autonomous Agent
  - Task Board
  - Idle Protocol
  - Auto-claim
  - Anthropic
tags:
  - Agent
  - Autonomous
  - TaskBoard
  - Implementation
author: "manus-learn"
date: "2026-02-24"
last_modified_at: "2026-02-24"
lang: "zh-CN"
audience: "开发者 / 对 AI Agent 感兴趣的工程师"
difficulty: "intermediate"
estimated_read_time: "12-15min"
topics:
  - Autonomous Agent
  - Task Board
  - Idle Polling
  - Auto-claim
  - Identity Re-injection
series: "从零构建 Claude Code"
series_order: 11
---

# 构建mini Claude Code：11 - 从「被动等待」到「主动找活」：Autonomous Agents 如何让 Teammate 真正自主

## 📍 导航指南

这是「从零构建 Claude Code」系列的第十一篇。根据你的背景，选择合适的阅读路径：

- 🧠 **理论派？** → [第一部分：被动的代价](#part-1) - 理解为什么 Teammate 需要自主性
- ⚙️ **实践派？** → [第二部分：三个核心机制](#part-2) - 掌握 idle、任务看板、auto-claim 的设计
- 💻 **代码派？** → [第三部分：代码实现](#part-3) - 直接看完整实现
- 🔭 **探索派？** → [第四部分：扩展方向](#part-4) - 自主 Agent 的更多可能

---

## 目录

### 第一部分：理论基础 🧠
- [被动 Teammate 的问题](#passive-problem)
- [自主性的本质](#autonomy-essence)
- [核心洞察：Agent 自己找工作](#core-insight)

### 第二部分：机制设计 ⚙️
- [任务看板：共享工作池](#task-board)
- [idle 工具：主动声明空闲](#idle-tool)
- [auto-claim：原子性认领](#auto-claim)
- [身份重注入：压缩后的连续性](#identity-injection)

### 第三部分：代码实现 💻
- [任务看板实现](#board-impl)
- [Teammate 生命周期](#lifecycle-impl)
- [原子认领与锁](#claim-lock)
- [两个新工具](#two-tools)

### 第四部分：扩展方向 🔭
- [更复杂的任务调度](#scheduling)
- [能力匹配](#capability-matching)

### 附录
- [常见问题 FAQ](#faq)

---

## 引言

上一篇我们给 Agent Teams 加了「交通规则」：Shutdown 协议保证优雅退出，Plan Approval 协议保证重大决策需授权。Teammate 能持久运行、能相互通信、能有序协调。

但有一个根本问题没有解决：

```
v9 的 Teammate 是被动的：
  lead: "coder，去做这个任务"
  coder: [执行任务]
  coder: [任务完成，等待...]
  coder: [继续等待...]
  coder: [还在等待...]
  lead: "coder，去做下一个任务"
  coder: [执行任务]
```

Teammate 完成任务后，只能等待 lead 分配下一个任务。如果 lead 忙着处理其他事情，Teammate 就白白空转。这不是「自主 Agent」，这是「远程控制的工具」。

**v10_agent.py 引入的 Autonomous Agents，让 Teammate 在空闲时主动扫描任务看板、认领任务、自主执行。**

> **说明**：v10_agent.py 在 v9_agent（Team Protocols）的基础上，新增了共享任务看板（BOARD_DIR）、`idle` 工具、`claim_task` 工具，以及 Teammate 的 IDLE 轮询阶段。本文聚焦这个新增的自主机制。

---

<a id="part-1"></a>
## 第一部分：理论基础 🧠

<a id="passive-problem"></a>
### 被动 Teammate 的问题

想象一个真实的软件团队：

```
低效团队（被动模式）:
  经理: "小王，做任务A"
  小王: [做完任务A]
  小王: [坐着等...]
  小王: [继续等...]
  经理: [正在开会，忘了分配任务B]
  小王: [浪费了2小时]

高效团队（主动模式）:
  经理: "任务B、C、D 放在看板上了"
  小王: [做完任务A]
  小王: [看看看板，发现任务B没人认领]
  小王: [认领任务B，开始工作]
  小李: [做完任务X]
  小李: [看看看板，发现任务C没人认领]
  小李: [认领任务C，开始工作]
```

高效团队的关键：**任务在看板上，人员主动认领**。经理不需要一对一分配，团队成员不需要被动等待。

v9 的 Teammate 是「低效团队」模式。v10 要变成「高效团队」模式。

<a id="autonomy-essence"></a>
### 自主性的本质

「自主 Agent」不是说 Agent 可以做任何事——而是说 **Agent 能自己决定下一步做什么**。

这需要两个条件：

```
条件一：有工作可做
  → 共享任务看板（BOARD_DIR）
  → 任何人都可以往看板上放任务
  → 任何 Teammate 都可以从看板上认领任务

条件二：知道什么时候去找工作
  → idle 工具：Teammate 主动声明「我没活了」
  → IDLE 阶段：定期轮询看板
  → 发现任务 → 认领 → 继续工作
```

两个条件缺一不可：只有看板没有 idle 机制，Teammate 不知道什么时候去看；只有 idle 机制没有看板，Teammate 找不到工作。

<a id="core-insight"></a>
### 核心洞察：Agent 自己找工作

v10 的注释里有一句话：

```
Key insight: "The agent finds work itself."
```

这句话背后的含义：

```
v9 的工作分配模型:
  lead → 分配任务 → Teammate

v10 的工作分配模型:
  lead → 放任务到看板
  Teammate → 扫描看板 → 认领任务 → 执行
```

lead 从「任务分配者」变成了「任务发布者」。Teammate 从「被动执行者」变成了「主动认领者」。

这个模型的优雅之处：**lead 和 Teammate 解耦**。lead 不需要知道哪个 Teammate 空闲，Teammate 不需要等待 lead 的指令。

---

<a id="part-2"></a>
## 第二部分：机制设计 ⚙️

<a id="task-board"></a>
### 任务看板：共享工作池

```
任务看板（BOARD_DIR）:
  .sessions/{session}/board/
    task_1.json  → {id: 1, subject: "...", status: "pending", owner: ""}
    task_2.json  → {id: 2, subject: "...", status: "in_progress", owner: "coder"}
    task_3.json  → {id: 3, subject: "...", status: "completed", owner: "reviewer"}
```

每个任务文件包含：
- `status`: pending / in_progress / completed
- `owner`: 认领者（空字符串表示未认领）
- `blockedBy`: 依赖的任务 ID 列表（被阻塞时不可认领）

**可认领条件**：`status == "pending"` 且 `owner == ""` 且 `blockedBy == []`

看板是文件系统上的 JSON 文件，天然持久化，多线程可访问。

<a id="idle-tool"></a>
### idle 工具：主动声明空闲

```
Teammate 的工作流:
  [收到任务] → [执行工作] → [任务完成]
                                ↓
                          [还有工作吗？]
                          ↙         ↘
                        是           否
                        ↓             ↓
                    [继续工作]    [调用 idle 工具]
                                      ↓
                                 [进入 IDLE 阶段]
```

`idle` 工具是 Teammate 主动发出的信号：「我当前没有更多工作了，请让我进入空闲轮询模式。」

这个设计的关键：**Teammate 自己决定什么时候空闲**，而不是 lead 来判断。Teammate 最清楚自己的工作状态。

<a id="auto-claim"></a>
### auto-claim：原子性认领

IDLE 阶段的轮询逻辑：

```
IDLE 阶段（每 5 秒一次，最多 60 秒）:
  ┌─ 检查收件箱
  │   有消息？→ 退出 IDLE，回到 WORK 阶段
  │
  ├─ 扫描任务看板
  │   有未认领任务？→ 认领第一个 → 退出 IDLE，回到 WORK 阶段
  │
  └─ 继续等待...
      超时（60秒）？→ 关闭自身
```

「认领」操作必须是原子的：两个 Teammate 同时发现同一个任务，只有一个能成功认领。

```python
# 用锁保证原子性
with _claim_lock:
    task = json.loads(path.read_text())
    if task.get("owner"):
        return "Error: already claimed"  # 另一个 Teammate 抢先了
    task["owner"] = owner
    task["status"] = "in_progress"
    path.write_text(json.dumps(task))
```

`_claim_lock` 是进程内的互斥锁，保证同一时刻只有一个线程能修改任务文件。

<a id="identity-injection"></a>
### 身份重注入：压缩后的连续性

Teammate 长时间运行后，上下文会被压缩（auto_compact）。压缩后，Teammate 可能「忘记」自己是谁。

当 Teammate 从 IDLE 阶段认领新任务时，如果消息历史很短（说明刚经历过压缩），需要重新注入身份：

```python
if len(messages) <= 3:
    messages.insert(0, make_identity_block(name, role, team_name))
    messages.insert(1, {"role": "assistant", "content": f"I am {name}. Continuing."})
```

`make_identity_block` 生成一个包含身份信息的消息：

```python
def make_identity_block(name, role, team_name):
    return {
        "role": "user",
        "content": f"<identity>You are '{name}', role: {role}, team: {team_name}. Continue your work.</identity>"
    }
```

这保证了 Teammate 在认领新任务时，始终知道自己的身份和角色。

---

<a id="part-3"></a>
## 第三部分：代码实现 💻

<a id="board-impl"></a>
### 任务看板实现

```python
BOARD_DIR = SESSION_DIR / "board"

def scan_unclaimed_tasks() -> list:
    BOARD_DIR.mkdir(exist_ok=True)
    unclaimed = []
    for f in sorted(BOARD_DIR.glob("task_*.json")):
        task = json.loads(f.read_text())
        if task.get("status") == "pending" and not task.get("owner") and not task.get("blockedBy"):
            unclaimed.append(task)
    return unclaimed

def claim_task_board(task_id: int, owner: str) -> str:
    with _claim_lock:
        path = BOARD_DIR / f"task_{task_id}.json"
        if not path.exists():
            return f"Error: Task {task_id} not found"
        task = json.loads(path.read_text())
        if task.get("owner"):
            return f"Error: Task {task_id} already claimed by {task['owner']}"
        task["owner"] = owner
        task["status"] = "in_progress"
        path.write_text(json.dumps(task, indent=2))
    return f"Claimed task #{task_id} for {owner}"
```

`scan_unclaimed_tasks` 扫描看板，返回所有可认领的任务。`claim_task_board` 在锁保护下原子性地认领任务。

<a id="lifecycle-impl"></a>
### Teammate 生命周期

v10 的 Teammate 循环分为两个阶段：

```python
while True:
    # -- WORK 阶段 --
    idle_requested = False
    for _ in range(50):
        # 读取收件箱
        for msg in BUS.read_inbox(name):
            if msg.get("type") == "shutdown_request":
                _set_status("shutdown")
                return
            messages.append({"role": "user", "content": json.dumps(msg)})
        # LLM 调用
        response = client.messages.create(...)
        # 处理工具调用
        for block in response.content:
            if block.type == "tool_use":
                if block.name == "idle":
                    idle_requested = True
                    output = "Entering idle phase. Will poll for new tasks."
                else:
                    output = self._exec(name, block.name, block.input)
        if idle_requested:
            break

    # -- IDLE 阶段 --
    _set_status("idle")
    resume = False
    for _ in range(IDLE_TIMEOUT // POLL_INTERVAL):  # 60s / 5s = 12次
        time.sleep(POLL_INTERVAL)
        # 检查收件箱
        inbox = BUS.read_inbox(name)
        if inbox:
            for msg in inbox:
                if msg.get("type") == "shutdown_request":
                    _set_status("shutdown")
                    return
                messages.append({"role": "user", "content": json.dumps(msg)})
            resume = True
            break
        # 扫描任务看板
        unclaimed = scan_unclaimed_tasks()
        if unclaimed:
            task = unclaimed[0]
            claim_task_board(task["id"], name)
            # 注入任务到消息历史
            task_prompt = f"<auto-claimed>Task #{task['id']}: {task['subject']}\n{task.get('description', '')}</auto-claimed>"
            # 身份重注入（如果消息历史很短）
            if len(messages) <= 3:
                messages.insert(0, make_identity_block(name, role, team_name))
                messages.insert(1, {"role": "assistant", "content": f"I am {name}. Continuing."})
            messages.append({"role": "user", "content": task_prompt})
            messages.append({"role": "assistant", "content": f"Claimed task #{task['id']}. Working on it."})
            resume = True
            break

    if not resume:
        _set_status("shutdown")
        return
    _set_status("working")
```

完整的生命周期状态机：

```
spawn
  ↓
WORK（最多50轮LLM调用）
  ↓ [调用 idle 工具]
IDLE（每5秒轮询，最多60秒）
  ├─ 收到消息 → WORK
  ├─ 发现任务 → 认领 → WORK
  └─ 超时 → shutdown
```

<a id="claim-lock"></a>
### 原子认领与锁

```python
_claim_lock = threading.Lock()
```

为什么需要专门的 `_claim_lock`，而不复用 `_tracker_lock`？

```
_tracker_lock: 保护内存中的 shutdown_requests 和 plan_requests
_claim_lock:   保护文件系统上的任务看板文件

两者保护的资源不同，分开使用避免不必要的锁竞争。
```

锁的粒度设计：只在「读取-检查-写入」的原子操作期间持有锁，不在整个认领流程中持有。这最小化了锁的持有时间，减少了线程竞争。

<a id="two-tools"></a>
### 两个新工具

v10 在 v9 的 24 个工具基础上，新增了 2 个：

```python
# Teammate 使用：声明空闲，进入轮询阶段
{"name": "idle",
 "description": "Signal that you have no more work. Enters idle polling phase.",
 "input_schema": {"type": "object", "properties": {}}}

# Teammate 使用：从任务看板认领任务
{"name": "claim_task",
 "description": "Claim a task from the task board by ID.",
 "input_schema": {"properties": {"task_id": {"type": "integer"}}}}
```

注意：`idle` 工具不需要任何参数——它只是一个信号。`claim_task` 需要 `task_id`，通常由 Teammate 在扫描看板后自动填入。

lead 侧也有 `idle` 和 `claim_task` 工具，但含义不同：

```
工具名       lead 侧含义              Teammate 侧含义
idle         lead 不进入 idle 状态    声明空闲，进入轮询
claim_task   lead 直接认领任务        Teammate 认领任务
```

---

<a id="part-4"></a>
## 第四部分：扩展方向 🔭

<a id="scheduling"></a>
### 更复杂的任务调度

当前实现是「先到先得」：Teammate 认领看板上的第一个可用任务。更复杂的场景需要更智能的调度：

**优先级调度**：

```python
def scan_unclaimed_tasks(priority: str = None) -> list:
    unclaimed = []
    for f in sorted(BOARD_DIR.glob("task_*.json")):
        task = json.loads(f.read_text())
        if task.get("status") == "pending" and not task.get("owner"):
            if not task.get("blockedBy"):
                unclaimed.append(task)
    # 按优先级排序
    priority_order = {"P0": 0, "P1": 1, "P2": 2}
    unclaimed.sort(key=lambda t: priority_order.get(t.get("priority", "P2"), 99))
    return unclaimed
```

**截止时间调度**：

```python
# 任务文件中添加 deadline 字段
task = {"id": 1, "subject": "...", "deadline": "2026-02-25T18:00:00", ...}

# 扫描时按截止时间排序
unclaimed.sort(key=lambda t: t.get("deadline", "9999"))
```

<a id="capability-matching"></a>
### 能力匹配

当前实现中，任何 Teammate 都可以认领任何任务。更精细的设计是按能力匹配：

```python
# 任务文件中添加 required_role 字段
task = {"id": 1, "subject": "写单元测试", "required_role": "tester", ...}

# 扫描时过滤
def scan_unclaimed_tasks(my_role: str) -> list:
    unclaimed = []
    for f in sorted(BOARD_DIR.glob("task_*.json")):
        task = json.loads(f.read_text())
        required = task.get("required_role", "")
        if task.get("status") == "pending" and not task.get("owner"):
            if not task.get("blockedBy"):
                if not required or required == my_role:
                    unclaimed.append(task)
    return unclaimed
```

这样，`coder` 只认领编码任务，`reviewer` 只认领审查任务，`tester` 只认领测试任务。

---

<a id="faq"></a>
## 常见问题 FAQ

**Q: Teammate 认领任务后，lead 怎么知道谁在做什么？**

A: 通过 `/board` 命令查看看板状态：

```python
if user_input.strip() == "/board":
    for f in sorted(BOARD_DIR.glob("task_*.json")):
        t = json.loads(f.read_text())
        marker = {"pending": "[ ]", "in_progress": "[>]", "completed": "[x]"}.get(t["status"], "[?]")
        owner = f" @{t['owner']}" if t.get("owner") else ""
        print(f"  {marker} #{t['id']}: {t['subject']}{owner}")
```

输出示例：
```
[ ] #1: 实现登录功能
[>] #2: 编写单元测试 @coder
[x] #3: 代码审查 @reviewer
```

**Q: 如果两个 Teammate 同时扫描到同一个任务，会发生什么？**

A: `_claim_lock` 保证只有一个能成功认领。另一个会收到 `"Error: Task X already claimed by Y"` 的返回值，然后继续扫描下一个可用任务。

**Q: IDLE_TIMEOUT 设置为 60 秒合理吗？**

A: 这取决于任务的产生频率。如果任务产生很快，可以缩短超时；如果任务产生很慢，可以延长。当前设置是保守值——60 秒没有新任务，Teammate 自动关闭，避免无限空转消耗资源。

```python
POLL_INTERVAL = 5   # 每 5 秒检查一次
IDLE_TIMEOUT = 60   # 最多等待 60 秒
```

**Q: Teammate 关闭后，如果有新任务怎么办？**

A: lead 可以重新 `spawn_teammate` 启动新的 Teammate。v10 的 `spawn` 方法支持重新激活已关闭的 Teammate：

```python
def spawn(self, name, role, prompt):
    member = self._find(name)
    if member:
        if member["status"] not in ("idle", "shutdown"):
            return f"Error: '{name}' is currently {member['status']}"
        member.update({"status": "working", "role": role})  # 重新激活
    else:
        member = {"name": name, "role": role, "status": "working"}
        self.config["members"].append(member)
    # 启动新线程
    t = threading.Thread(target=self._loop, args=(name, role, prompt), daemon=True)
    self.threads[name] = t
    t.start()
```

**Q: `<auto-claimed>` 标签有什么作用？**

A: 它是一个语义标记，告诉 Teammate 这个任务是自动认领的（而不是 lead 直接分配的）。Teammate 的 LLM 可以根据这个标记调整行为——比如，自动认领的任务可能需要先提交 plan_approval，而 lead 直接分配的任务可能已经隐含了授权。

---

## 📝 结语

从 v9 到 v10，只加了两个工具（`idle` + `claim_task`）、一个共享目录（BOARD_DIR）、一个轮询循环（IDLE 阶段）。但这个改动背后的思想值得细品：

```
v9 的问题:
  Teammate 能协作、能协调，但不能自主
  完成任务后只能等待 lead 分配
  lead 成为瓶颈

v10 的解决:
  任务看板 → 工作解耦，lead 发布任务而非分配任务
  idle 工具 → Teammate 主动声明空闲
  auto-claim → Teammate 自主认领，原子操作防冲突
  身份重注入 → 压缩后仍知道自己是谁
```

更深层的意义是：**自主性不是「做任何事的自由」，而是「在规则内自己决定下一步」**。

v10 的 Teammate 不是无限制的——它只能认领看板上的任务，只能在 IDLE 阶段轮询，超时后会自动关闭。但在这些约束内，它完全自主：不需要 lead 的指令，不需要等待，自己找工作、自己执行、自己更新状态。

```
系列能力演进:
  上下文压缩（v5）    → Agent 能长时间运行
  持久化任务（v6）    → Agent 能跨会话追踪任务
  后台执行（v7）      → Agent 能并行处理任务
  Agent Teams（v8）   → Agent 能组建团队协作
  Team Protocols（v9）→ Agent 团队能有序协调
  Autonomous（v10）   → Agent 能主动找工作、自主执行
                        ↓
              真正的「自主 Agent 系统」
```

六个能力叠加，才能处理真实世界的复杂任务：长时间、多步骤、有依赖、可并行、需协作、能协调、**会自主**。

**系列导航**：
- **上一篇**: [10 - 团队协作的「交通规则」：Team Protocols 如何解决 Agent 之间的冲突]()
- **当前**:   [11 - 从「被动等待」到「主动找活」：Autonomous Agents 如何让 Teammate 真正自主]()
- **下一篇**: 12 - 把所有能力组合起来：构建完整的自主 Agent 系统
