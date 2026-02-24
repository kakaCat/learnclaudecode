---
title: "从「一次性」到「持久」：Agent Teams 如何让协作真正发生"
description: "Subagent 是一次性的——它完成任务就消失了。v8_agent.py 引入 TeammateManager，让每个 Agent 拥有持久的工作能力、独立的收件箱和跨轮次的记忆。这是 Multi-Agent 从「任务分发」走向「团队协作」的关键一步。"
image: "/images/blog/agent-teams.jpg"
keywords:
  - Claude Code
  - AI Agent
  - Agent Teams
  - Multi-Agent
  - Persistent Agent
  - Anthropic
tags:
  - Agent
  - Teams
  - Multi-Agent
  - Persistent
  - Implementation
author: "manus-learn"
date: "2026-02-24"
last_modified_at: "2026-02-24"
lang: "zh-CN"
audience: "开发者 / 对 AI Agent 感兴趣的工程师"
difficulty: "intermediate"
estimated_read_time: "12-15min"
topics:
  - Agent Teams
  - Persistent Agents
  - File-based Messaging
  - Multi-Agent Collaboration
series: "从零构建 Claude Code"
series_order: 9
---

# 构建mini Claude Code：09 - 从「一次性」到「持久」：Agent Teams 如何让协作真正发生

## 📍 导航指南

这是「从零构建 Claude Code」系列的第九篇。根据你的背景，选择合适的阅读路径：

- 🧠 **理论派？** → [第一部分：Subagent 的局限](#part-1) - 理解为什么一次性 Agent 不够用
- ⚙️ **实践派？** → [第二部分：TeammateManager 设计](#part-2) - 掌握持久 Agent 的核心设计
- 💻 **代码派？** → [第三部分：代码实现](#part-3) - 直接看完整实现
- 🔭 **探索派？** → [第四部分：扩展方向](#part-4) - 还有哪些协作模式

---

## 目录

### 第一部分：理论基础 🧠
- [Subagent 的本质局限](#subagent-limit)
- [真实协作需要什么](#real-collaboration)
- [核心洞察：一切皆文件](#core-insight)

### 第二部分：TeammateManager 设计 ⚙️
- [三个核心组件](#three-components)
- [MessageBus：文件即通信](#message-bus)
- [工作流：团队如何协作](#workflow)

### 第三部分：代码实现 💻
- [TeammateManager 类](#teammate-manager-code)
- [MessageBus 类](#message-bus-code)
- [五个工具：spawn / list / send / inbox / broadcast](#five-tools)

### 第四部分：扩展方向 🔭
- [角色专业化](#role-specialization)
- [协作协议](#collaboration-protocol)
- [团队状态持久化](#team-persistence)

### 附录
- [常见问题 FAQ](#faq)

---

## 引言

考虑这个场景：

```
用户: "帮我实现一个新功能，需要写代码、做 Code Review、跑测试"

Subagent 方案（v7 之前）:
  主 Agent → run_task("写代码", subagent_type="general-purpose")  # 完成后消失
  主 Agent → run_task("Code Review", subagent_type="general-purpose")  # 完成后消失
  主 Agent → run_task("跑测试", subagent_type="general-purpose")  # 完成后消失

问题:
  - Reviewer 看不到 Coder 的思路
  - Tester 不知道 Review 发现了什么问题
  - 每个 Agent 都是孤立的，没有上下文传递
```

这不是真正的协作，这是流水线。

**v8_agent.py 引入的 Agent Teams，让每个 Agent 拥有持久的身份、独立的收件箱、跨轮次的记忆——这才是真正的团队协作。**

> **说明**：v8_agent.py 在 v7_agent（后台执行 + 持久任务 + 上下文压缩）的基础上，新增了 `TeammateManager`、`MessageBus` 和五个团队工具。本文聚焦这个新增的 Agent Teams 系统。

---

<a id="part-1"></a>
## 第一部分：理论基础 🧠

<a id="subagent-limit"></a>
### Subagent 的本质局限

回顾 v7 的 `run_task`：

```python
def run_task(description: str, prompt: str, subagent_type: str) -> str:
    # 创建独立上下文
    sub_messages = [{"role": "user", "content": prompt}]
    # 运行直到完成
    while True:
        response = client.messages.create(...)
        if response.stop_reason != "tool_use":
            break
        ...
    # 返回结果，上下文丢弃
    return result_text
```

Subagent 的生命周期：

```
创建 → 执行 → 返回结果 → 消失
  ↑                         ↑
  孤立的上下文              上下文丢弃
```

这带来三个根本性的局限：

**局限一：无法持续工作**

Subagent 是一次性的。它完成任务就消失了。如果任务需要多轮交互——比如 Reviewer 发现问题，Coder 修改，Reviewer 再次检查——Subagent 做不到，因为它没有「下一轮」。

**局限二：无法相互通信**

两个 Subagent 之间没有通信机制。Coder 完成代码后，Reviewer 只能通过主 Agent 的转述来了解情况，信息在传递中损耗。

**局限三：无法共享上下文**

每个 Subagent 都从零开始。Reviewer 不知道 Coder 做了哪些权衡，Tester 不知道 Review 发现了什么问题。团队的「集体记忆」不存在。

<a id="real-collaboration"></a>
### 真实协作需要什么

想象一个真实的软件团队：

```
Coder:    "我实现了认证模块，用了 JWT，放在 auth/ 目录"
Reviewer: "看了你的代码，token 过期处理有个问题，第 42 行"
Coder:    "明白，我修一下"
Reviewer: "好了，这次没问题了，可以合并"
Tester:   "我看到你们的对话了，我来写对应的测试"
```

这个过程有几个关键特征：

1. **持久身份**：Coder、Reviewer、Tester 是固定的角色，不是一次性的
2. **直接通信**：他们可以直接对话，不需要通过「主管」转述
3. **共享上下文**：Tester 能看到 Coder 和 Reviewer 的对话历史
4. **异步协作**：Reviewer 在看代码时，Coder 可以去做别的事

<a id="core-insight"></a>
### 核心洞察：一切皆文件

v8_agent.py 的注释里有一句话：

```
Key insight: "Teammates that can talk to each other."
```

但实现这个洞察的方式更值得关注：**用文件系统作为通信基础设施**。

每个 Teammate 有一个 JSONL 格式的收件箱文件：

```
.sessions/20260224_130000/team/inbox/
├── coder.jsonl      ← Coder 的收件箱
├── reviewer.jsonl   ← Reviewer 的收件箱
└── tester.jsonl     ← Tester 的收件箱
```

发消息 = 写文件。读消息 = 读文件并清空。

这不只是实现细节，这是一种设计哲学：**通信状态外化为文件，Agent 的「记忆」不依赖进程内存，而是持久化在文件系统中。**

这和上一篇的持久化任务系统（`.tasks/`）是同一个理念的延伸——**一切皆文件**。

---

<a id="part-2"></a>
## 第二部分：TeammateManager 设计 ⚙️

<a id="three-components"></a>
### 三个核心组件

Agent Teams 由三个组件构成：

```
┌─────────────────────────────────────────────────────────┐
│ Agent Teams 系统                                         │
│                                                         │
│  1. TeammateManager                                     │
│     管理 Teammate 的生命周期                              │
│     spawn / list / 状态追踪                              │
│                                                         │
│  2. MessageBus                                          │
│     文件系统消息队列                                      │
│     send / read_inbox / broadcast                       │
│                                                         │
│  3. Teammate Loop                                       │
│     每个 Teammate 的独立 Agent 循环                       │
│     运行在独立线程，有自己的 messages 历史                  │
└─────────────────────────────────────────────────────────┘
```

<a id="message-bus"></a>
### MessageBus：文件即通信

MessageBus 是整个系统的核心。它把「发消息」和「读消息」映射到文件操作：

```
发消息（send）:
  sender="lead", to="coder", content="请实现认证模块"
  → 追加到 inbox/coder.jsonl
  → {"type": "message", "from": "lead", "content": "...", "timestamp": 1234567890}

读消息（read_inbox）:
  name="coder"
  → 读取 inbox/coder.jsonl 的所有行
  → 清空文件（drain 语义）
  → 返回消息列表
```

为什么用 JSONL 而不是普通文本？

```
JSONL（每行一个 JSON）的优势:
  - 结构化：消息有类型、发送者、时间戳
  - 追加安全：多个线程同时写不会互相覆盖
  - 易解析：逐行读取，不需要解析整个文件
  - 可审计：文件保留了完整的消息历史
```

消息类型（`VALID_MSG_TYPES`）：

```python
VALID_MSG_TYPES = {
    "message",              # 普通消息
    "broadcast",            # 广播消息
    "shutdown_request",     # 请求关闭
    "shutdown_response",    # 关闭响应
    "plan_approval_response" # 计划审批响应
}
```

类型系统让 Teammate 能区分不同性质的消息，做出不同的响应。

<a id="workflow"></a>
### 工作流：团队如何协作

```
主 Agent（lead）
    │
    ├─ spawn_teammate("coder", "实现认证模块")
    │       │
    │       └─ 独立线程启动，开始工作
    │
    ├─ spawn_teammate("reviewer", "Review coder 的代码")
    │       │
    │       └─ 独立线程启动，等待消息
    │
    │  ... lead 继续其他工作 ...
    │
    │  [coder 完成代码]
    │  coder → send_message("reviewer", "代码在 auth/ 目录，请 Review")
    │                │
    │                └─ 写入 inbox/reviewer.jsonl
    │
    │  [reviewer 的下一轮循环]
    │  reviewer → read_inbox()  ← 读到 coder 的消息
    │  reviewer → 开始 Review
    │  reviewer → send_message("coder", "第 42 行有问题")
    │
    │  [coder 的下一轮循环]
    │  coder → read_inbox()  ← 读到 reviewer 的反馈
    │  coder → 修复问题
    │  coder → send_message("lead", "修复完成")
    │
    │  [lead 的下一轮循环]
    │  lead → read_inbox()  ← 读到 coder 的完成通知
    │  lead → 继续下一步
```

关键点：**整个过程中，lead 不需要轮询或等待。每个 Teammate 在自己的线程里运行，通过文件系统异步通信。**

---

<a id="part-3"></a>
## 第三部分：代码实现 💻

<a id="message-bus-code"></a>
### MessageBus 类

```python
class MessageBus:
    def __init__(self, inbox_dir: Path):
        self.dir = inbox_dir
        self.dir.mkdir(parents=True, exist_ok=True)

    def send(self, sender: str, to: str, content: str,
             msg_type: str = "message", extra: dict = None) -> str:
        if msg_type not in VALID_MSG_TYPES:
            return f"Error: Invalid type '{msg_type}'. Valid: {VALID_MSG_TYPES}"
        msg = {"type": msg_type, "from": sender, "content": content, "timestamp": time.time()}
        if extra:
            msg.update(extra)
        with open(self.dir / f"{to}.jsonl", "a") as f:
            f.write(json.dumps(msg) + "\n")
        return f"Sent {msg_type} to {to}"

    def read_inbox(self, name: str) -> list:
        inbox_path = self.dir / f"{name}.jsonl"
        if not inbox_path.exists():
            return []
        messages = [json.loads(l) for l in inbox_path.read_text().strip().splitlines() if l]
        inbox_path.write_text("")  # drain
        return messages

    def broadcast(self, sender: str, content: str, teammates: list) -> str:
        count = sum(1 for name in teammates
                    if name != sender and
                    not self.send(sender, name, content, "broadcast").startswith("Error"))
        return f"Broadcast to {count} teammates"
```

`read_inbox` 的 drain 语义很重要：读完就清空。这保证了每条消息只被处理一次，不会重复消费。

<a id="teammate-manager-code"></a>
### TeammateManager 类

```python
class TeammateManager:
    def __init__(self, team_dir: Path):
        self.dir = team_dir
        self.dir.mkdir(exist_ok=True)
        self.config_path = self.dir / "config.json"
        self.config = (json.loads(self.config_path.read_text())
                       if self.config_path.exists()
                       else {"team_name": "default", "members": []})
        self.threads = {}

    def spawn(self, name: str, role: str, prompt: str) -> str:
        member = self._find(name)
        if member:
            if member["status"] not in ("idle", "shutdown"):
                return f"Error: '{name}' is currently {member['status']}"
            member.update({"status": "working", "role": role})
        else:
            member = {"name": name, "role": role, "status": "working"}
            self.config["members"].append(member)
        self._save()
        t = threading.Thread(target=self._loop, args=(name, role, prompt), daemon=True)
        self.threads[name] = t
        t.start()
        return f"Spawned '{name}' (role: {role})"
```

`spawn` 做了三件事：
1. 注册成员到 `config.json`（持久化）
2. 启动独立线程运行 Agent 循环
3. 立刻返回，不等待 Teammate 完成

注意 `daemon=True`：守护线程，主进程退出时自动终止。

### Teammate 的 Agent 循环

```python
def _loop(self, name: str, role: str, prompt: str):
    sys_prompt = f"You are '{name}', role: {role}, at {WORKDIR}. Use send_message to communicate. Complete your task."
    messages = [{"role": "user", "content": prompt}]
    tools = [bash, read_file, write_file, edit_file, send_message, read_inbox]

    for _ in range(50):  # 最多 50 轮
        # 每轮开始前检查收件箱
        for msg in BUS.read_inbox(name):
            messages.append({"role": "user", "content": json.dumps(msg)})

        response = client.messages.create(model=MODEL, system=sys_prompt,
                                          messages=messages, tools=tools, max_tokens=8000)
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            break  # 任务完成

        results = []
        for block in response.content:
            if block.type == "tool_use":
                output = self._exec(name, block.name, block.input)
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": str(output)})
        messages.append({"role": "user", "content": results})

    # 循环结束，标记为 idle
    member = self._find(name)
    if member and member["status"] != "shutdown":
        member["status"] = "idle"
        self._save()
```

这个循环有几个关键设计：

**每轮检查收件箱**：在每次 LLM 调用之前，先读取收件箱。这保证了 Teammate 能及时响应其他成员的消息。

**消息注入 messages**：收件箱的消息被追加到 `messages` 列表，成为 LLM 上下文的一部分。Teammate 的「记忆」就是这个不断增长的 messages 列表。

**最多 50 轮**：防止无限循环。50 轮对于大多数任务已经足够。

**状态更新**：循环结束后，状态从 `working` 变为 `idle`，可以被重新 spawn。

<a id="five-tools"></a>
### 五个工具

主 Agent（lead）通过五个工具与团队交互：

```python
# 1. 创建 Teammate
{"name": "spawn_teammate",
 "description": "Spawn a persistent teammate agent in its own thread.",
 "input_schema": {"properties": {"name": ..., "role": ..., "prompt": ...}}}

# 2. 查看团队状态
{"name": "list_teammates",
 "description": "List all teammates with name, role, status."}

# 3. 发消息给某个 Teammate
{"name": "send_message",
 "description": "Send a message to a teammate's inbox.",
 "input_schema": {"properties": {"to": ..., "content": ..., "msg_type": ...}}}

# 4. 读取 lead 自己的收件箱
{"name": "read_inbox",
 "description": "Read and drain the lead's inbox."}

# 5. 广播给所有 Teammate
{"name": "broadcast",
 "description": "Send a message to all teammates.",
 "input_schema": {"properties": {"content": ...}}}
```

Teammate 内部也有 `send_message` 和 `read_inbox`，但它们只能发给其他成员，不能调用 `spawn_teammate`——这保持了层级结构：lead 负责组建团队，Teammate 负责执行任务。

### 团队状态持久化

团队配置保存在 `config.json`：

```json
{
  "team_name": "default",
  "members": [
    {"name": "coder", "role": "实现认证模块", "status": "idle"},
    {"name": "reviewer", "role": "Code Review", "status": "working"},
    {"name": "tester", "role": "编写测试", "status": "idle"}
  ]
}
```

这意味着即使主进程重启，团队的组成和状态也不会丢失。结合 `.tasks/` 持久化任务系统，整个工作状态都外化到了文件系统。

---

<a id="part-4"></a>
## 第四部分：扩展方向 🔭

<a id="role-specialization"></a>
### 方向一：角色专业化

当前所有 Teammate 使用相同的工具集。可以根据角色限制工具：

```python
ROLE_TOOLS = {
    "coder":    ["bash", "read_file", "write_file", "edit_file", "send_message", "read_inbox"],
    "reviewer": ["read_file", "grep", "send_message", "read_inbox"],  # 只读
    "tester":   ["bash", "read_file", "write_file", "send_message", "read_inbox"],
}

def _loop(self, name: str, role: str, prompt: str):
    tools = ROLE_TOOLS.get(role, DEFAULT_TOOLS)
    ...
```

Reviewer 只有读权限，不能修改文件——这和真实团队的权限设计一致。

<a id="collaboration-protocol"></a>
### 方向二：协作协议

当前的通信是非结构化的自然语言。可以定义结构化协议：

```python
# Coder 完成后发送结构化消息
BUS.send("coder", "reviewer", json.dumps({
    "action": "review_request",
    "files_changed": ["auth/jwt.py", "auth/middleware.py"],
    "summary": "实现了 JWT 认证，token 有效期 24 小时",
    "concerns": ["refresh token 的存储方式还不确定"]
}), msg_type="message")

# Reviewer 收到后，能精确知道要 Review 哪些文件
```

结构化协议减少了歧义，让 Teammate 能更高效地协作。

<a id="team-persistence"></a>
### 方向三：跨会话团队

当前 Teammate 的线程在进程退出时终止。结合 `config.json` 的持久化，可以实现跨会话恢复：

```python
def resume_team(self):
    """恢复上次会话的团队"""
    for member in self.config["members"]:
        if member["status"] == "working":
            # 上次会话中断时正在工作的成员，重新启动
            self.spawn(member["name"], member["role"],
                       f"继续上次的工作。检查你的收件箱获取最新状态。")
```

结合文件系统的收件箱，Teammate 重启后能从收件箱里恢复上下文，继续未完成的工作。

---

<a id="faq"></a>
## 常见问题 FAQ

**Q: Teammate 和 Subagent（Task）有什么区别？**

A: 核心区别是生命周期和通信能力。

```
Subagent（Task）:
  - 一次性：完成任务就消失
  - 孤立：没有通信机制
  - 同步：主 Agent 等待结果
  - 适合：独立的、有明确边界的子任务

Teammate:
  - 持久：有自己的 Agent 循环，可以多轮工作
  - 互联：通过 MessageBus 相互通信
  - 异步：在独立线程运行，主 Agent 不需要等待
  - 适合：需要多轮交互、相互依赖的协作任务
```

**Q: Teammate 的收件箱消息会丢失吗？**

A: 不会。消息写入 JSONL 文件后持久化在磁盘上，即使进程崩溃也不会丢失。Teammate 重启后读取收件箱，能看到所有未处理的消息。

**Q: 多个 Teammate 同时写同一个收件箱会有竞态问题吗？**

A: 文件追加（`open(path, "a")`）在大多数操作系统上是原子的——每次 `write` 调用要么完整写入，要么不写入。JSONL 格式（每行一条消息）进一步保证了即使多个线程同时写，每条消息也是完整的。

**Q: Teammate 的 50 轮限制够用吗？**

A: 对于大多数任务足够。50 轮意味着 Teammate 可以调用 50 次工具，处理 50 次收件箱消息。如果任务需要更多轮次，可以调整这个参数，或者让 Teammate 完成后重新 spawn（状态变为 `idle` 后可以再次 spawn）。

**Q: 如何知道所有 Teammate 都完成了？**

A: 调用 `list_teammates` 查看所有成员的状态。当所有成员都是 `idle` 时，说明当前轮次的工作都完成了。也可以让每个 Teammate 完成后发消息给 lead，lead 通过 `read_inbox` 收集完成通知。

---

## 📝 结语

从 Subagent 到 Teammate，v8_agent 只加了两个类（`TeammateManager` + `MessageBus`）和五个工具。但这个改动背后的思想值得细品：

```
Subagent 模型:
  主 Agent → 派发任务 → 等待结果 → 派发下一个任务
  Agent 是工具，不是协作者

Teammate 模型:
  主 Agent → 组建团队 → 团队自主协作 → 主 Agent 处理结果
  Agent 是协作者，有自己的判断和沟通能力
```

更深层的意义是：**Agent 的「能力」不只是执行工具，还包括持续工作、主动沟通、响应反馈。**

一次性的 Subagent 能完成任务，但不能建立关系。持久的 Teammate 能在多轮交互中积累上下文，形成真正的协作——就像真实团队里的工程师，不是做完一件事就消失，而是持续参与、持续贡献。

而这一切的基础，是文件系统。收件箱是文件，团队配置是文件，任务状态是文件。**一切皆文件**，让 Agent 的状态从进程内存走向持久存储，从单次会话走向跨会话协作。

结合前几篇的能力：

```
上下文压缩（v5）  → Agent 能长时间运行
持久化任务（v6）  → Agent 能跨会话追踪任务
后台执行（v7）    → Agent 能并行处理任务
Agent Teams（v8） → Agent 能组建团队协作
                    ↓
              真正的「自主 Agent 系统」
```

四个能力叠加，才能处理真实世界的复杂任务：长时间、多步骤、有依赖、可并行、需协作。

**系列导航**：
- **上一篇**: [08 - Fire and Forget：用后台线程解锁 Multi-Agent 并行执行]()
- **当前**:   [09 - 从「一次性」到「持久」：Agent Teams 如何让协作真正发生]()
- **下一篇**: 10 - 自主 Agent：把所有能力组合起来
