---
title: "团队协作的「交通规则」：Team Protocols 如何解决 Agent 之间的冲突"
description: "Agent Teams 让协作成为可能，但多个 Agent 并发工作时会产生干扰——谁有权关闭谁？谁的计划需要审批？v9_agent.py 引入 Team Protocols，用 request_id 关联模式解决这两个核心问题。"
image: "/images/blog/team-protocols.jpg"
keywords:
  - Claude Code
  - AI Agent
  - Team Protocols
  - Multi-Agent
  - Shutdown Protocol
  - Plan Approval
  - Anthropic
tags:
  - Agent
  - Teams
  - Protocols
  - Coordination
  - Implementation
author: "manus-learn"
date: "2026-02-24"
last_modified_at: "2026-02-24"
lang: "zh-CN"
audience: "开发者 / 对 AI Agent 感兴趣的工程师"
difficulty: "intermediate"
estimated_read_time: "12-15min"
topics:
  - Team Protocols
  - Shutdown Protocol
  - Plan Approval
  - Request-Response Pattern
  - Multi-Agent Coordination
series: "从零构建 Claude Code"
series_order: 10
---

# 构建mini Claude Code：10 - 团队协作的「交通规则」：Team Protocols 如何解决 Agent 之间的冲突

## 📍 导航指南

这是「从零构建 Claude Code」系列的第十篇。根据你的背景，选择合适的阅读路径：

- 🧠 **理论派？** → [第一部分：协作的代价](#part-1) - 理解为什么团队需要协议
- ⚙️ **实践派？** → [第二部分：两个协议的设计](#part-2) - 掌握 Shutdown 和 Plan Approval 的核心设计
- 💻 **代码派？** → [第三部分：代码实现](#part-3) - 直接看完整实现
- 🔭 **探索派？** → [第四部分：扩展方向](#part-4) - 协议模式的更多应用

---

## 目录

### 第一部分：理论基础 🧠
- [Agent Teams 带来的新问题](#new-problems)
- [两种典型冲突场景](#conflict-scenarios)
- [核心洞察：request_id 关联模式](#core-insight)

### 第二部分：协议设计 ⚙️
- [Shutdown 协议：优雅退出](#shutdown-protocol)
- [Plan Approval 协议：计划审批](#plan-approval-protocol)
- [同一模式，两个域](#same-pattern)

### 第三部分：代码实现 💻
- [请求追踪器](#request-trackers)
- [Shutdown 实现](#shutdown-impl)
- [Plan Approval 实现](#plan-approval-impl)
- [三个新工具](#three-tools)

### 第四部分：扩展方向 🔭
- [更多协议场景](#more-protocols)
- [协议的演化](#protocol-evolution)

### 附录
- [常见问题 FAQ](#faq)

---

## 引言

上一篇我们构建了 Agent Teams：每个 Teammate 在独立线程运行，通过文件系统收件箱异步通信。这是一个巨大的进步——Agent 从「一次性工具」变成了「持久协作者」。

但随之而来的是新问题：

```
场景一：
  lead: "coder，你的任务完成了，可以关闭了"
  coder: [正在写文件的关键步骤，突然被强制终止]
  结果: 文件损坏，工作丢失

场景二：
  coder: [自主决定重构整个认证模块]
  lead: [完全不知情，等待的是一个小功能]
  结果: 方向偏离，大量无效工作
```

这不是 Bug，这是**协作的代价**。当多个 Agent 并发工作时，必须有机制来协调：谁有权关闭谁？谁的计划需要审批？

**v9_agent.py 引入的 Team Protocols，就是 Agent 团队的「交通规则」。**

> **说明**：v9_agent.py 在 v8_agent（持久 Teammate + MessageBus）的基础上，新增了 `shutdown_request/response` 和 `plan_approval` 三个工具，以及对应的请求追踪器。本文聚焦这个新增的协议系统。

---

<a id="part-1"></a>
## 第一部分：理论基础 🧠

<a id="new-problems"></a>
### Agent Teams 带来的新问题

v8 的 Agent Teams 解决了「孤立」问题，但引入了「协调」问题。

想象一个真实的软件团队：

```
没有规则的团队:
  经理: "小王，你今天可以下班了"
  小王: [正在提交代码，事务进行到一半]
  结果: 代码库损坏

  小李: [自己决定把整个数据库重新设计]
  经理: [完全不知情]
  结果: 方向失控
```

真实团队有「交通规则」：
- 下班前要完成手头的工作，不能强制中断
- 重大决策要向上汇报，不能自行其是

Agent Teams 也需要同样的规则。

<a id="conflict-scenarios"></a>
### 两种典型冲突场景

**冲突一：强制关闭 vs 优雅退出**

```
问题:
  lead 想关闭 coder
  但 coder 可能正在执行关键操作（写文件、调用 API）
  强制 kill 线程 → 状态不一致

需要:
  lead 发送「关闭请求」
  coder 在合适的时机「响应同意」
  双方协商，优雅退出
```

**冲突二：自主行动 vs 计划审批**

```
问题:
  coder 是自主 Agent，会自己决定怎么做
  但某些决策影响重大（重构、删除文件、修改架构）
  lead 不知情 → 方向失控

需要:
  coder 在执行重大操作前「提交计划」
  lead 「审批或拒绝」
  获得授权后再执行
```

<a id="core-insight"></a>
### 核心洞察：request_id 关联模式

v9 的注释里有一句话：

```
Key insight: "Same request_id correlation pattern, two domains."
```

两个协议用的是**同一个模式**：

```
请求方:
  1. 生成唯一 request_id
  2. 在追踪器中注册 {request_id: {status: "pending", ...}}
  3. 通过 MessageBus 发送请求（携带 request_id）
  4. 稍后查询追踪器获取结果

响应方:
  1. 收到请求（从收件箱读取）
  2. 处理请求（决定同意/拒绝）
  3. 通过工具发送响应（携带相同的 request_id）
  4. 追踪器状态更新为 approved/rejected
```

这个模式的优雅之处：**异步请求-响应，通过 ID 关联，不需要阻塞等待。**

---

<a id="part-2"></a>
## 第二部分：协议设计 ⚙️

<a id="shutdown-protocol"></a>
### Shutdown 协议：优雅退出

```
状态机:
  pending → approved（Teammate 同意关闭）
           → rejected（Teammate 拒绝，继续工作）

流程:
  lead                          coder
   │                              │
   ├─ shutdown_request("coder")   │
   │   生成 req_id=abc123         │
   │   注册 shutdown_requests     │
   │   发消息到 coder 收件箱 ────→│
   │                              │ [下一轮循环]
   │                              ├─ 读取收件箱
   │                              ├─ 看到 shutdown_request
   │                              ├─ 决定：当前任务可以中断
   │                              ├─ shutdown_response(req_id, approve=True)
   │                              │   更新追踪器状态
   │                              │   发消息到 lead 收件箱 ──→│
   │                              │   should_exit = True      │
   │                              │   [循环结束]              │
   │ [下一轮循环]                  │
   ├─ shutdown_response(req_id)   │
   │   查询追踪器                  │
   │   返回 {status: "approved"}  │
```

关键设计：**Teammate 有权拒绝关闭**。如果正在执行关键操作，可以回复 `approve=False`，lead 稍后再试。这保证了操作的原子性。

<a id="plan-approval-protocol"></a>
### Plan Approval 协议：计划审批

```
状态机:
  pending → approved（lead 批准计划）
           → rejected（lead 拒绝，附带反馈）

流程:
  coder                         lead
   │                              │
   ├─ plan_approval("重构认证模块") │
   │   生成 req_id=xyz789         │
   │   注册 plan_requests         │
   │   发消息到 lead 收件箱 ─────→│
   │   返回"等待审批"              │ [下一轮循环]
   │                              ├─ 读取收件箱
   │                              ├─ 看到 plan_approval_response
   │                              ├─ 阅读计划内容
   │                              ├─ plan_approval(req_id, approve=True/False)
   │                              │   更新追踪器
   │                              │   发消息到 coder 收件箱 ──→│
   │ [下一轮循环]                  │
   ├─ 读取收件箱                   │
   ├─ 看到审批结果                 │
   ├─ approved → 执行计划          │
   │  rejected → 调整方案          │
```

关键设计：**Teammate 主动提交计划，不是被动等待指令**。这符合自主 Agent 的工作方式——它有自己的判断，但在重大决策上寻求授权。

<a id="same-pattern"></a>
### 同一模式，两个域

两个协议的对称性：

```
Shutdown 协议:
  发起方: lead（想关闭 Teammate）
  响应方: Teammate（决定是否同意）
  追踪器: shutdown_requests
  消息类型: shutdown_request / shutdown_response

Plan Approval 协议:
  发起方: Teammate（提交计划）
  响应方: lead（决定是否批准）
  追踪器: plan_requests
  消息类型: plan_approval_response（双向复用）
```

注意方向是**相反的**：
- Shutdown：lead → Teammate（lead 主动）
- Plan Approval：Teammate → lead（Teammate 主动）

但底层机制完全相同：request_id + 追踪器 + MessageBus。

---

<a id="part-3"></a>
## 第三部分：代码实现 💻

<a id="request-trackers"></a>
### 请求追踪器

```python
# 两个追踪器，一把锁
shutdown_requests = {}   # {req_id: {target, status}}
plan_requests = {}       # {req_id: {from, plan, status}}
_tracker_lock = threading.Lock()
```

为什么需要锁？因为追踪器被多个线程访问：
- lead 线程写入请求、读取状态
- Teammate 线程更新状态

`threading.Lock()` 保证了并发安全。

<a id="shutdown-impl"></a>
### Shutdown 实现

**lead 发起关闭请求**（`handle_shutdown_request`）：

```python
def handle_shutdown_request(teammate: str) -> str:
    req_id = str(uuid.uuid4())[:8]
    with _tracker_lock:
        shutdown_requests[req_id] = {"target": teammate, "status": "pending"}
    BUS.send("lead", teammate, "Please shut down gracefully.",
             "shutdown_request", {"request_id": req_id})
    return f"Shutdown request {req_id} sent to '{teammate}' (status: pending)"
```

三步：生成 ID → 注册追踪器 → 发消息。立刻返回，不等待。

**lead 查询关闭状态**（`_check_shutdown_status`）：

```python
def _check_shutdown_status(request_id: str) -> str:
    with _tracker_lock:
        return json.dumps(shutdown_requests.get(request_id, {"error": "not found"}))
```

查询追踪器，返回当前状态。

**Teammate 响应关闭请求**（在 `_exec` 中）：

```python
if tool_name == "shutdown_response":
    req_id = args["request_id"]
    approve = args["approve"]
    with _tracker_lock:
        if req_id in shutdown_requests:
            shutdown_requests[req_id]["status"] = "approved" if approve else "rejected"
    BUS.send(sender, "lead", args.get("reason", ""), "shutdown_response",
             {"request_id": req_id, "approve": approve})
    return f"Shutdown {'approved' if approve else 'rejected'}"
```

更新追踪器 + 发消息通知 lead。

**Teammate 循环中的退出逻辑**：

```python
should_exit = False
for _ in range(50):
    for msg in BUS.read_inbox(name):
        messages.append({"role": "user", "content": json.dumps(msg)})
    if should_exit:
        break
    # ... LLM 调用 ...
    for block in response.content:
        if block.type == "tool_use":
            output = self._exec(name, block.name, block.input)
            if block.name == "shutdown_response" and block.input.get("approve"):
                should_exit = True  # 下一轮循环前退出
```

`should_exit` 标志保证了：Teammate 同意关闭后，**先处理完当前轮次的所有工具调用**，再退出。不会在中途强制中断。

<a id="plan-approval-impl"></a>
### Plan Approval 实现

**Teammate 提交计划**（在 `_exec` 中）：

```python
if tool_name == "plan_approval":
    plan_text = args.get("plan", "")
    req_id = str(uuid.uuid4())[:8]
    with _tracker_lock:
        plan_requests[req_id] = {"from": sender, "plan": plan_text, "status": "pending"}
    BUS.send(sender, "lead", plan_text, "plan_approval_response",
             {"request_id": req_id, "plan": plan_text})
    return f"Plan submitted (request_id={req_id}). Waiting for lead approval."
```

Teammate 调用 `plan_approval` 工具 → 生成 req_id → 注册追踪器 → 发消息给 lead。

**lead 审批计划**（`handle_plan_review`）：

```python
def handle_plan_review(request_id: str, approve: bool, feedback: str = "") -> str:
    with _tracker_lock:
        req = plan_requests.get(request_id)
    if not req:
        return f"Error: Unknown plan request_id '{request_id}'"
    with _tracker_lock:
        req["status"] = "approved" if approve else "rejected"
    BUS.send("lead", req["from"], feedback, "plan_approval_response",
             {"request_id": request_id, "approve": approve, "feedback": feedback})
    return f"Plan {req['status']} for '{req['from']}'"
```

lead 调用 `plan_approval` 工具（带 request_id + approve）→ 更新追踪器 → 发消息给 Teammate。

Teammate 在下一轮循环读取收件箱时，会看到审批结果，决定是否执行计划。

<a id="three-tools"></a>
### 三个新工具

v9 在 v8 的 21 个工具基础上，新增了 3 个：

```python
# lead 使用：发起关闭请求
{"name": "shutdown_request",
 "description": "Request a teammate to shut down gracefully. Returns a request_id for tracking.",
 "input_schema": {"properties": {"teammate": {"type": "string"}}}}

# lead 使用：查询关闭状态
{"name": "shutdown_response",
 "description": "Check the status of a shutdown request by request_id.",
 "input_schema": {"properties": {"request_id": {"type": "string"}}}}

# lead 使用：审批 Teammate 的计划
{"name": "plan_approval",
 "description": "Approve or reject a teammate's plan. Provide request_id + approve + optional feedback.",
 "input_schema": {"properties": {
     "request_id": {"type": "string"},
     "approve": {"type": "boolean"},
     "feedback": {"type": "string"}
 }}}
```

注意：`shutdown_response` 和 `plan_approval` 这两个名字在 lead 和 Teammate 侧含义不同：

```
工具名          lead 侧含义              Teammate 侧含义
shutdown_response  查询关闭请求状态      响应关闭请求（同意/拒绝）
plan_approval      审批 Teammate 的计划  提交计划给 lead 审批
```

同一个工具名，不同的执行逻辑——通过 `execute_tool` vs `_exec` 路由到不同的处理函数。

---

<a id="part-4"></a>
## 第四部分：扩展方向 🔭

<a id="more-protocols"></a>
### 更多协议场景

request_id 关联模式是通用的，可以扩展到更多场景：

**资源锁定协议**：

```python
# Teammate 请求独占某个文件
BUS.send("coder", "lead", "auth/jwt.py", "lock_request",
         {"request_id": req_id, "resource": "auth/jwt.py"})

# lead 批准或拒绝
BUS.send("lead", "coder", "", "lock_response",
         {"request_id": req_id, "granted": True})
```

防止两个 Teammate 同时修改同一个文件。

**进度汇报协议**：

```python
# Teammate 定期汇报进度
BUS.send("coder", "lead", "已完成 3/5 个函数", "progress_report",
         {"request_id": req_id, "progress": 60})
```

lead 可以实时了解每个 Teammate 的工作状态。

**优先级调整协议**：

```python
# lead 动态调整 Teammate 的任务优先级
BUS.send("lead", "coder", "先完成登录功能，认证模块延后", "priority_change",
         {"request_id": req_id, "new_priority": "login_first"})
```

<a id="protocol-evolution"></a>
### 协议的演化

当前协议是「单轮」的：一个请求，一个响应。更复杂的场景需要「多轮」协议：

```
Plan Approval 多轮版:
  coder → 提交计划
  lead  → 要求修改（附带反馈）
  coder → 修改后重新提交
  lead  → 批准

实现思路:
  plan_requests[req_id]["status"] = "revision_requested"
  coder 收到 revision_requested → 修改计划 → 重新调用 plan_approval
  新的提交复用同一个 req_id（或生成新的，关联到原始 req_id）
```

这就是真实团队的工作方式：计划不是一次性批准的，而是经过多轮讨论和修改。

---

<a id="faq"></a>
## 常见问题 FAQ

**Q: Teammate 拒绝关闭请求后，lead 怎么办？**

A: lead 可以稍后再次发送 `shutdown_request`，或者等待 Teammate 自然完成任务（状态变为 `idle`）。强制终止线程（`thread.join(timeout=0)`）是最后手段，会破坏状态一致性，不推荐。

**Q: 如果 Teammate 一直不响应 shutdown_request 怎么办？**

A: 追踪器中的状态会一直是 `pending`。可以设置超时机制：

```python
def handle_shutdown_request(teammate: str, timeout: int = 30) -> str:
    req_id = ...
    # 发送请求
    # 等待最多 timeout 秒
    deadline = time.time() + timeout
    while time.time() < deadline:
        with _tracker_lock:
            if shutdown_requests[req_id]["status"] != "pending":
                break
        time.sleep(1)
    # 超时后强制标记
    with _tracker_lock:
        if shutdown_requests[req_id]["status"] == "pending":
            shutdown_requests[req_id]["status"] = "timeout"
```

**Q: plan_approval 会阻塞 Teammate 吗？**

A: 不会。Teammate 调用 `plan_approval` 后，立刻收到「等待审批」的返回值，然后继续下一轮循环。在下一轮循环中，它会读取收件箱，看到审批结果后再决定是否执行计划。整个过程是异步的，Teammate 不会阻塞等待。

**Q: 如果 Teammate 不提交计划，直接执行重大操作怎么办？**

A: 这取决于 Teammate 的 system prompt。v9 的 system prompt 包含：

```python
sys_prompt = (
    f"You are '{name}', role: {role}, at {WORKDIR}. "
    f"Submit plans via plan_approval before major work. "  # ← 这里
    f"Respond to shutdown_request with shutdown_response."
)
```

通过 prompt 约束 Teammate 的行为。这是「软约束」——LLM 会遵守，但不是强制的。更强的约束需要在工具层面实现（比如写文件前自动检查是否有批准的计划）。

**Q: shutdown_requests 和 plan_requests 会一直增长吗？**

A: 是的，当前实现没有清理机制。对于长时间运行的系统，需要定期清理已完成的请求：

```python
def cleanup_old_requests(max_age: int = 3600):
    cutoff = time.time() - max_age
    with _tracker_lock:
        # 清理已完成且超过 max_age 的请求
        for req_id in list(shutdown_requests.keys()):
            req = shutdown_requests[req_id]
            if req["status"] != "pending" and req.get("timestamp", 0) < cutoff:
                del shutdown_requests[req_id]
```

---

## 📝 结语

从 v8 到 v9，只加了三个工具和两个追踪器。但这个改动背后的思想值得细品：

```
v8 的问题:
  Agent 能协作，但没有「规则」
  强制关闭 → 状态损坏
  自主行动 → 方向失控

v9 的解决:
  Shutdown 协议 → 优雅退出，保护状态完整性
  Plan Approval 协议 → 重大决策需授权，保持方向一致
```

更深层的意义是：**协议是团队的「社会契约」**。

真实团队之所以能高效协作，不只是因为每个人都有能力，更是因为大家遵守共同的规则：下班前完成手头工作、重大决策向上汇报、修改他人代码前沟通。

Agent Teams 也需要这样的社会契约。Shutdown 协议和 Plan Approval 协议，是这个契约的最小实现。

而两个协议共用同一个 request_id 关联模式，说明了一个更普遍的道理：**协调问题的本质是「请求-响应」的异步关联**。无论是关闭请求、计划审批，还是资源锁定、优先级调整，都可以用同一个模式解决。

```
系列能力演进:
  上下文压缩（v5）  → Agent 能长时间运行
  持久化任务（v6）  → Agent 能跨会话追踪任务
  后台执行（v7）    → Agent 能并行处理任务
  Agent Teams（v8） → Agent 能组建团队协作
  Team Protocols（v9）→ Agent 团队能有序协调
                      ↓
              真正的「自主 Agent 系统」
```

五个能力叠加，才能处理真实世界的复杂任务：长时间、多步骤、有依赖、可并行、需协作、能协调。

**系列导航**：
- **上一篇**: [09 - 从「一次性」到「持久」：Agent Teams 如何让协作真正发生]()
- **当前**:   [10 - 团队协作的「交通规则」：Team Protocols 如何解决 Agent 之间的冲突]()
- **下一篇**: 11 - 自主 Agent：把所有能力组合起来
