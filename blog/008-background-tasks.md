---
title: "Fire and Forget：用后台线程解锁 Multi-Agent 并行执行"
description: "Agent 调用 bash 跑测试，要等 30 秒。这 30 秒里，整个 Agent 循环都在阻塞。v7_agent.py 引入 BackgroundManager，让耗时命令在后台线程执行，主 Agent 继续派发任务——这是 Multi-Agent 系统从「串行」走向「并行」的关键一步。"
image: "/images/blog/background-tasks.jpg"
keywords:
  - Claude Code
  - AI Agent
  - Background Tasks
  - Multi-Agent
  - Parallel Execution
  - Anthropic
tags:
  - Agent
  - Background
  - Parallel
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
  - Background Execution
  - Fire and Forget
  - Non-blocking Agent Loop
  - Multi-Agent Parallelism
series: "从零构建 Claude Code"
series_order: 8
---

# 构建mini Claude Code：08 - Fire and Forget：用后台线程解锁 Multi-Agent 并行执行

## 📍 导航指南

这是「从零构建 Claude Code」系列的第八篇。根据你的背景，选择合适的阅读路径：

- 🧠 **理论派？** → [第一部分：阻塞问题](#part-1) - 理解为什么串行执行是 Multi-Agent 的瓶颈
- ⚙️ **实践派？** → [第二部分：BackgroundManager 设计](#part-2) - 掌握后台任务的核心设计
- 💻 **代码派？** → [第三部分：代码实现](#part-3) - 直接看完整实现
- 🔭 **探索派？** → [第四部分：扩展方向](#part-4) - 还有哪些并行化思路

---

## 目录

### 第一部分：理论基础 🧠
- [Agent 循环的阻塞问题](#blocking-problem)
- [Multi-Agent 的串行陷阱](#serial-trap)
- [核心洞察：Fire and Forget](#core-insight)

### 第二部分：BackgroundManager 设计 ⚙️
- [三个核心机制](#three-mechanisms)
- [通知队列：结果如何回到主循环](#notification-queue)
- [工作流：Agent 如何并行执行任务](#workflow)

### 第三部分：代码实现 💻
- [BackgroundManager 类](#background-manager-code)
- [两个工具：background_run / check_background](#two-tools)
- [主循环集成：drain_notifications](#main-loop-integration)

### 第四部分：扩展方向 🔭
- [多 Agent 并行任务分发](#parallel-dispatch)
- [后台任务优先级](#task-priority)
- [超时与重试](#timeout-retry)

### 附录
- [常见问题 FAQ](#faq)

---

## 引言

考虑这个场景：

```
用户: "帮我跑一下完整的测试套件，同时把文档也更新一下"

Agent 的选择:
  方案 A（串行）: 跑测试（等 60 秒）→ 更新文档
  方案 B（并行）: 后台跑测试 → 立刻更新文档 → 测试结果回来后处理
```

方案 A 是 v6_agent 的做法。方案 B 是 v7_agent 引入的能力。

**这不只是速度的差异，而是 Agent 处理复杂任务的范式转变。**

> **说明**：v7_agent.py 在 v6_agent（14 工具 + 持久化任务 + 上下文压缩）的基础上，新增了 `background_run` 和 `check_background` 两个工具，以及 `BackgroundManager` 类。本文聚焦这个新增的后台执行系统。

---

<a id="part-1"></a>
## 第一部分：理论基础 🧠

<a id="blocking-problem"></a>
### Agent 循环的阻塞问题

回顾 Agent 的基本循环：

```
while True:
    response = LLM(messages)          # LLM 决策
    if no tool calls: break
    for tool in tool_calls:
        result = execute_tool(tool)   # ← 这里会阻塞
        results.append(result)
    messages.append(results)
```

`execute_tool` 是同步的。当 Agent 调用 `bash("pytest tests/ -v")` 时，整个循环在这里等待，直到命令执行完毕。

```
时间轴（串行执行）:
  t=0   Agent 决策: 跑测试 + 更新文档
  t=0   bash("pytest") 开始执行
  t=60  pytest 完成，返回结果
  t=60  Agent 决策: 更新文档
  t=61  write_file("docs/...") 执行
  t=62  完成

总耗时: 62 秒
```

60 秒里，Agent 什么都没做——它在等。

<a id="serial-trap"></a>
### Multi-Agent 的串行陷阱

在 Multi-Agent 场景下，这个问题被放大了。

主 Agent 通常会把大任务拆分给多个子 Agent：

```python
# 主 Agent 的典型工作流
run_task("实现认证模块", ..., subagent_type="general-purpose")  # 等待子 Agent A
run_task("实现用户管理", ..., subagent_type="general-purpose")  # 等待子 Agent B
run_task("写集成测试",   ..., subagent_type="general-purpose")  # 等待子 Agent C
```

每个 `run_task` 都是同步的——子 Agent 完成之前，主 Agent 不会继续。

```
时间轴（串行 Multi-Agent）:
  t=0    主 Agent 派发任务 A → 等待
  t=30   子 Agent A 完成
  t=30   主 Agent 派发任务 B → 等待
  t=50   子 Agent B 完成
  t=50   主 Agent 派发任务 C → 等待
  t=80   子 Agent C 完成

总耗时: 80 秒
```

但任务 A 和任务 B 之间没有依赖关系——它们完全可以并行执行。

```
时间轴（并行 Multi-Agent）:
  t=0    主 Agent 后台启动任务 A
  t=0    主 Agent 后台启动任务 B
  t=0    主 Agent 继续处理其他工作
  t=30   任务 A 完成（通知主 Agent）
  t=50   任务 B 完成（通知主 Agent）
  t=50   主 Agent 派发任务 C（依赖 A 和 B）→ 等待
  t=80   子 Agent C 完成

总耗时: 80 秒（但主 Agent 在 0-50 秒内没有空闲）
```

等等，总耗时一样？

关键不在于总耗时，而在于**主 Agent 的利用率**。在并行模式下，主 Agent 在等待 A 和 B 的同时，可以处理其他不依赖 A/B 的任务——比如更新文档、检查代码风格、准备测试数据。

**串行是顺序等待，并行是同时推进。**

<a id="core-insight"></a>
### 核心洞察：Fire and Forget

v7_agent.py 的注释里有一句话，是整个设计的核心：

```
Key insight: "Fire and forget -- the agent doesn't block while the command runs."
```

**Fire and Forget（发射后不管）**：启动一个任务，立刻返回，不等待结果。结果准备好了，再通知你。

这是异步编程的基本思想，但在 Agent 循环里实现它需要解决一个问题：**LLM 调用是同步的，如何把异步结果「注入」到下一次 LLM 调用？**

v7_agent 的答案是：**通知队列 + 每次 LLM 调用前 drain**。

---

<a id="part-2"></a>
## 第二部分：BackgroundManager 设计 ⚙️

<a id="three-mechanisms"></a>
### 三个核心机制

BackgroundManager 由三个机制组成：

```
┌─────────────────────────────────────────────────────┐
│ BackgroundManager                                   │
│                                                     │
│  1. 线程执行器                                       │
│     threading.Thread → 后台运行 subprocess          │
│                                                     │
│  2. 任务注册表                                       │
│     self.tasks = {task_id: {status, result, cmd}}   │
│                                                     │
│  3. 通知队列                                         │
│     self._notification_queue = []                   │
│     完成时 enqueue，主循环 drain                     │
└─────────────────────────────────────────────────────┘
```

**机制一：线程执行器**

每个后台任务在独立线程中运行。线程执行 subprocess，不阻塞主线程（Agent 循环所在的线程）。

**机制二：任务注册表**

`self.tasks` 是一个字典，记录所有后台任务的状态。Agent 可以随时调用 `check_background(task_id)` 查询某个任务的状态和结果。

**机制三：通知队列**

这是最关键的机制。当后台任务完成时，它不能直接「打断」主循环——LLM 调用是同步的，没有回调机制。

解决方案：任务完成时把结果放入队列，主循环在每次 LLM 调用**之前**检查队列，把待处理的通知注入到 messages 里。

<a id="notification-queue"></a>
### 通知队列：结果如何回到主循环

```
后台线程                          主线程（Agent 循环）
─────────────────────────────────────────────────────
subprocess 执行中...
                                  LLM 调用 #1
                                  处理工具调用
subprocess 完成
enqueue(result)  ──────────────→  通知队列: [result]

                                  ← 下一次循环开始
                                  drain_notifications()
                                  注入 <background-results>
                                  LLM 调用 #2  ← Agent 看到结果
```

关键时序：**drain 发生在 LLM 调用之前**。这保证了 Agent 在做下一次决策时，能看到所有已完成的后台任务结果。

```python
# 主循环里的 drain 逻辑
notifs = BG.drain_notifications()
if notifs and messages:
    notif_text = "\n".join(
        f"[bg:{n['task_id']}] {n['status']}: {n['result']}" for n in notifs
    )
    messages.append({"role": "user", "content": f"<background-results>\n{notif_text}\n</background-results>"})
    messages.append({"role": "assistant", "content": "Noted background results."})

# 然后才调用 LLM
response = client.messages.create(...)
```

注意：drain 后立刻追加了一个 `assistant` 消息「Noted background results.」——这是为了保持 messages 的 user/assistant 交替格式，避免 API 报错。

<a id="workflow"></a>
### 工作流：Agent 如何并行执行任务

```
用户: "跑测试，同时更新 README"
         │
         ▼
┌─────────────────────┐
│ Agent 分析任务      │
│ → 两个独立任务      │
│ → 可以并行执行      │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ background_run      │  ← 后台启动 pytest
│ ("pytest tests/")   │    立刻返回 task_id: "a1b2c3d4"
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ write_file          │  ← 同步更新 README
│ ("README.md", ...)  │    Agent 不需要等 pytest
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ ... 其他工作 ...    │  ← pytest 在后台跑
└──────────┬──────────┘
           │
           ▼  （pytest 完成，通知入队）
┌─────────────────────┐
│ drain_notifications │  ← 下次 LLM 调用前
│ → 注入测试结果      │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Agent 处理测试结果  │
│ → 修复失败的测试    │
└─────────────────────┘
```

整个过程中，pytest（60 秒）和 README 更新（1 秒）是**真正并行**的。

---

<a id="part-3"></a>
## 第三部分：代码实现 💻

<a id="background-manager-code"></a>
### BackgroundManager 类

```python
class BackgroundManager:
    def __init__(self):
        self.tasks = {}
        self._notification_queue = []
        self._lock = threading.Lock()

    def run(self, command: str) -> str:
        task_id = str(uuid.uuid4())[:8]
        self.tasks[task_id] = {"status": "running", "result": None, "command": command}
        threading.Thread(target=self._execute, args=(task_id, command), daemon=True).start()
        return f"Background task {task_id} started: {command[:80]}"
```

`run` 方法做了三件事：
1. 生成一个短 UUID 作为 task_id（8位，够用且易读）
2. 在注册表里记录任务状态
3. 启动后台线程，**立刻返回** task_id

注意 `daemon=True`：守护线程，主进程退出时自动终止，不会因为后台任务未完成而阻塞退出。

```python
    def _execute(self, task_id: str, command: str):
        try:
            r = subprocess.run(command, shell=True, cwd=WORKDIR,
                               capture_output=True, text=True, timeout=300)
            output = (r.stdout + r.stderr).strip()[:50000]
            status = "completed"
        except subprocess.TimeoutExpired:
            output = "Error: Timeout (300s)"
            status = "timeout"
        except Exception as e:
            output = f"Error: {e}"
            status = "error"
        self.tasks[task_id]["status"] = status
        self.tasks[task_id]["result"] = output or "(no output)"
        with self._lock:
            self._notification_queue.append({
                "task_id": task_id, "status": status,
                "command": command[:80],
                "result": (output or "(no output)")[:500],
            })
```

`_execute` 在后台线程里运行。几个设计细节：

- **timeout=300**：后台任务最多跑 5 分钟，防止僵尸线程
- **output[:50000]**：截断超长输出，避免撑爆内存
- **`with self._lock`**：写通知队列时加锁，防止主线程同时 drain 导致竞态
- **result[:500]**：通知里只放前 500 字符，完整结果通过 `check_background` 获取

```python
    def drain_notifications(self) -> list:
        with self._lock:
            notifs = list(self._notification_queue)
            self._notification_queue.clear()
        return notifs
```

`drain_notifications` 是线程安全的：加锁、复制、清空、返回。主循环每次调用都能拿到自上次 drain 以来完成的所有任务。

<a id="two-tools"></a>
### 两个工具：background_run / check_background

```python
{"name": "background_run",
 "description": "Run command in background thread. Returns task_id immediately. Use for long-running commands.",
 "input_schema": {"type": "object",
                  "properties": {"command": {"type": "string"}},
                  "required": ["command"]}},

{"name": "check_background",
 "description": "Check background task status. Omit task_id to list all.",
 "input_schema": {"type": "object",
                  "properties": {"task_id": {"type": "string"}}}},
```

工具描述里的关键信息：
- `background_run`：「Returns task_id immediately」——告诉 Agent 这是非阻塞的
- `check_background`：「Omit task_id to list all」——支持查询单个或全部

```python
def execute_tool(name: str, args: dict) -> str:
    ...
    if name == "background_run":    return BG.run(args["command"])
    if name == "check_background":  return BG.check(args.get("task_id"))
```

```python
def check(self, task_id: str = None) -> str:
    if task_id:
        t = self.tasks.get(task_id)
        if not t:
            return f"Error: Unknown task {task_id}"
        return f"[{t['status']}] {t['command'][:60]}\n{t.get('result') or '(running)'}"
    lines = [f"{tid}: [{t['status']}] {t['command'][:60]}" for tid, t in self.tasks.items()]
    return "\n".join(lines) if lines else "No background tasks."
```

`check` 不带参数时，返回所有后台任务的概览——Agent 可以用这个来「盘点」当前有哪些任务在跑。

<a id="main-loop-integration"></a>
### 主循环集成：drain_notifications

主循环的修改非常小，只在 LLM 调用前加了 drain 逻辑：

```python
def agent_loop(messages: list) -> list:
    while True:
        # ← 新增：drain 后台通知
        notifs = BG.drain_notifications()
        if notifs and messages:
            notif_text = "\n".join(
                f"[bg:{n['task_id']}] {n['status']}: {n['result']}" for n in notifs
            )
            messages.append({"role": "user",
                             "content": f"<background-results>\n{notif_text}\n</background-results>"})
            messages.append({"role": "assistant", "content": "Noted background results."})

        micro_compact(messages)
        if estimate_tokens(messages) > THRESHOLD:
            messages[:] = auto_compact(messages)

        response = client.messages.create(...)  # ← LLM 调用
        ...
```

整个集成只有 8 行代码。BackgroundManager 是一个独立的组件，对主循环的侵入极小。

完整的数据流：

```
background_run("pytest") 调用
  → BG.run("pytest")
  → 后台线程启动
  → 返回 "Background task a1b2c3d4 started"

... Agent 继续其他工作 ...

pytest 完成（后台线程）
  → BG._notification_queue.append({task_id, status, result})

下一次 agent_loop 迭代
  → drain_notifications() → [{task_id: "a1b2c3d4", status: "completed", result: "..."}]
  → messages 追加 <background-results>
  → LLM 调用：Agent 看到测试结果，决定下一步
```

---

<a id="part-4"></a>
## 第四部分：扩展方向 🔭

<a id="parallel-dispatch"></a>
### 方向一：多 Agent 并行任务分发

当前的 `run_task`（子 Agent）是同步的。结合 BackgroundManager 的思路，可以实现真正的并行子 Agent：

```
当前（串行子 Agent）:
  主 Agent → run_task(A) → 等待 → run_task(B) → 等待

扩展（并行子 Agent）:
  主 Agent → background_run("python subagent_a.py") → 立刻返回
  主 Agent → background_run("python subagent_b.py") → 立刻返回
  主 Agent → 等待两个后台任务完成 → 汇总结果
```

这需要子 Agent 能以独立进程运行，并通过文件（`.tasks/`）共享状态——这正是上一篇持久化任务系统的价值所在。

两个系统的组合：
```
持久化任务（.tasks/）  +  后台执行（BackgroundManager）
       ↓                           ↓
  共享任务状态              并行执行子任务
       ↓                           ↓
         Multi-Agent 并行协作框架
```

<a id="task-priority"></a>
### 方向二：后台任务优先级

当前所有后台任务平等对待。可以扩展为优先级队列：

```python
import heapq

class PriorityBackgroundManager(BackgroundManager):
    def __init__(self):
        super().__init__()
        self._pending = []  # (priority, task_id, command)
        self._semaphore = threading.Semaphore(3)  # 最多 3 个并发

    def run(self, command: str, priority: int = 5) -> str:
        task_id = str(uuid.uuid4())[:8]
        heapq.heappush(self._pending, (priority, task_id, command))
        threading.Thread(target=self._run_with_limit, args=(task_id, command), daemon=True).start()
        return f"Background task {task_id} queued (priority={priority})"

    def _run_with_limit(self, task_id: str, command: str):
        with self._semaphore:  # 限制并发数
            self._execute(task_id, command)
```

<a id="timeout-retry"></a>
### 方向三：超时与重试

当前实现中，超时的任务直接标记为 `timeout`，不会重试。可以扩展为自动重试：

```python
def _execute(self, task_id: str, command: str, retry: int = 0):
    try:
        r = subprocess.run(command, shell=True, cwd=WORKDIR,
                           capture_output=True, text=True, timeout=300)
        ...
    except subprocess.TimeoutExpired:
        if retry < 2:  # 最多重试 2 次
            self._execute(task_id, command, retry + 1)
            return
        output = "Error: Timeout after 3 attempts"
        status = "timeout"
```

---

<a id="faq"></a>
## 常见问题 FAQ

**Q: background_run 和直接 bash 有什么区别？**

A: 核心区别是阻塞与否。

```
bash("pytest"):
  → 等待 pytest 完成（可能 60 秒）
  → 返回完整输出
  → Agent 循环在此期间完全阻塞

background_run("pytest"):
  → 立刻返回 task_id（< 1ms）
  → pytest 在后台线程运行
  → Agent 循环继续执行其他工具
  → pytest 完成后，结果通过通知队列回到 Agent
```

适合 background_run 的场景：耗时超过 5 秒、不需要立刻用到结果、可以和其他工作并行的命令。

**Q: 如果后台任务完成了，但 Agent 一直没有新的 LLM 调用，通知会丢失吗？**

A: 不会。通知队列会一直保存，直到 drain 被调用。drain 在每次 LLM 调用前执行，所以只要 Agent 还在运行，通知最终都会被处理。

**Q: 多个后台任务同时完成，通知顺序有保证吗？**

A: 没有严格保证。通知按照任务完成的时间顺序入队，但线程调度是操作系统决定的。对于 Agent 来说，通知顺序通常不重要——它会处理所有通知，然后做整体决策。

**Q: 后台任务的输出太长怎么办？**

A: 通知里只包含前 500 字符（`result[:500]`）。如果需要完整输出，Agent 可以调用 `check_background(task_id)` 获取完整结果（最多 50000 字符）。对于超长输出，可以让后台任务把结果写入文件，Agent 再用 `read_file` 读取。

**Q: 后台任务会影响上下文压缩吗？**

A: 不会直接影响。后台任务的结果通过 `<background-results>` 注入 messages，和普通消息一样参与压缩。如果担心后台结果占用太多上下文，可以在 micro_compact 里对 `background-results` 消息做特殊处理（优先截断）。

---

## 📝 结语

从串行到并行，v7_agent 只加了一个 `BackgroundManager` 类和两个工具。但这个改动背后的思想值得细品：

```
串行 Agent:
  执行 → 等待 → 执行 → 等待 → ...
  Agent 的时间 = 执行时间 + 等待时间

并行 Agent:
  执行 → 后台启动 → 继续执行 → 后台启动 → ...
  Agent 的时间 ≈ 执行时间（等待时间被隐藏）
```

更深层的意义是：**Agent 的「注意力」应该用在决策上，而不是等待上。**

耗时的命令（测试、构建、部署）不需要 Agent 盯着看。Agent 应该启动它们，然后去做其他有价值的工作，等结果回来再处理。这和人类工程师的工作方式是一致的——没有人会盯着 CI 跑完再去做下一件事。

结合前几篇的能力：

```
上下文压缩（v5）  → Agent 能长时间运行
持久化任务（v6）  → Agent 能跨会话追踪任务
后台执行（v7）    → Agent 能并行处理任务
                    ↓
              真正的「自主 Agent」
```

三个能力叠加，Agent 才能处理真实世界的复杂任务：长时间、多步骤、有依赖、可并行。

**系列导航**：
- **上一篇**: [07 - 一切皆文件：持久化任务系统](https://juejin.cn/spost/7609504603010875407)
- **当前**:   [08 - Fire and Forget：用后台线程解锁 Multi-Agent 并行执行]()
- **下一篇**: 09 - Multi-Agent 团队协作协议
