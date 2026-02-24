---
title: "复杂任务的分解之道：Multi-Agent 架构与上下文隔离"
description: "单 Agent 为什么会「失忆」？为什么复杂任务需要多个 Agent 协作？本文从上下文污染问题出发，解析 v3_agent 如何用 Task 工具实现主 Agent 编排、子 Agent 隔离执行的多 Agent 架构。"
image: "/images/blog/multi-agent.jpg"
keywords:
  - Claude Code
  - Multi-Agent
  - AI Agent
  - Context Isolation
  - Subagent
  - Orchestration
  - Anthropic
tags:
  - Agent
  - Multi-Agent
  - Architecture
  - Implementation
author: "manus-learn"
date: "2026-02-23"
last_modified_at: "2026-02-23"
lang: "zh-CN"
audience: "开发者 / 对 AI Agent 感兴趣的工程师"
difficulty: "intermediate"
estimated_read_time: "15-18min"
topics:
  - Context Pollution Problem
  - Multi-Agent Design
  - Task Decomposition
  - Agent Orchestration
series: "从零构建 Claude Code"
series_order: 4
---

# 构建mini Claude Code：04 - 复杂任务的分解之道：Multi-Agent 架构

## 📍 导航指南

这是「从零构建 Claude Code」系列的第四篇。根据你的背景，选择合适的阅读路径：

- 🧠 **理论派？** → [第一部分：为什么需要多 Agent](#part-1) - 理解上下文污染问题
- ⚙️ **架构派？** → [第二部分：主从架构设计](#part-2) - 掌握编排与隔离的核心机制
- 💻 **代码派？** → [第三部分：代码实现](#part-3) - 直接看 Task 工具与子 Agent 实现

---

## 目录

### 第一部分：问题与动机 🧠
- [单 Agent 的天花板：上下文污染](#context-pollution)
- [复杂任务的本质：可分解性](#decomposability)
- [多 Agent 的核心价值](#multi-agent-value)

### 第二部分：架构设计 ⚙️
- [主从模型：编排者与执行者](#orchestrator-executor)
- [上下文隔离：子 Agent 的独立世界](#context-isolation)
- [Agent 类型注册表](#agent-registry)

### 第三部分：代码实现 💻
- [Task 工具：派生子 Agent 的接口](#task-tool)
- [run_task：子 Agent 执行引擎](#run-task)
- [完整架构图](#full-architecture)

### 附录
- [常见问题 FAQ](#faq)

---

## 引言

你已经有了一个能读文件、写代码、执行命令的 Agent。它能完成很多任务。

但当你说「帮我重构整个项目」时，它开始出问题了：

- 读了 20 个文件，上下文塞满了历史记录
- 探索代码结构的过程污染了后续的编写过程
- LLM 在海量上下文中「迷失」，开始犯低级错误

**这不是 LLM 的问题，这是架构的问题。**

解决方案是：**多 Agent 协作**。

---

<a id="part-1"></a>
## 第一部分：问题与动机 🧠

<a id="context-pollution"></a>
### 单 Agent 的天花板：上下文污染

回顾 v0 的 bash agent，它的上下文是这样增长的：

```
Turn 1: [用户: "重构项目"] → [LLM: 调用 bash ls]
Turn 2: [工具结果: 50个文件列表]
Turn 3: [LLM: 调用 read_file main.py]
Turn 4: [工具结果: 500行代码]
Turn 5: [LLM: 调用 read_file utils.py]
Turn 6: [工具结果: 300行代码]
...
Turn 20: [LLM: 终于开始写代码，但上下文已有 8000 tokens 的探索历史]
```

问题在于：**探索阶段产生的上下文，在执行阶段变成了噪音。**

LLM 的注意力是有限的。当上下文里充满了「我读了哪些文件、发现了什么」的历史，它在「现在该写什么代码」这个问题上的注意力就被稀释了。

这就是**上下文污染**：前期工作的痕迹干扰了后期工作的质量。

```
单 Agent 的上下文增长
┌─────────────────────────────────────────────┐
│  探索阶段（读文件、搜索、分析）              │
│  ████████████████████████████               │
│                                             │
│  规划阶段（设计方案）                        │
│  ████████████████████████████████████       │
│                                             │
│  执行阶段（写代码）← LLM 在这里注意力分散   │
│  ████████████████████████████████████████   │
└─────────────────────────────────────────────┘
  上下文越来越长，质量越来越差
```

<a id="decomposability"></a>
### 复杂任务的本质：可分解性

人类工程师面对复杂任务时，本能地会做什么？

**分工。**

- 架构师负责设计，不写代码
- 开发者负责实现，不做架构决策
- 测试工程师负责验证，不关心实现细节

每个角色都在**有限的上下文**里做**专注的工作**。

这不是偶然的——这是人类应对认知负荷的进化策略。**把大问题分解成小问题，每个小问题由专注的执行者处理。**

AI Agent 面临同样的认知负荷问题。解决方案也相同：**分工**。

```
复杂任务的分解
                    ┌─────────────────┐
                    │   复杂任务       │
                    │  "重构整个项目"  │
                    └────────┬────────┘
                             │ 分解
              ┌──────────────┼──────────────┐
              │              │              │
    ┌─────────▼──────┐ ┌─────▼──────┐ ┌────▼───────────┐
    │  探索子任务     │ │  规划子任务 │ │  执行子任务     │
    │  "找出所有      │ │  "设计重构  │ │  "实现重构      │
    │   依赖关系"     │ │   方案"     │ │   方案"         │
    └────────────────┘ └────────────┘ └────────────────┘
      独立上下文          独立上下文      独立上下文
      不污染彼此          不污染彼此      不污染彼此
```

<a id="multi-agent-value"></a>
### 多 Agent 的核心价值

多 Agent 架构解决了三个关键问题：

| 问题 | 单 Agent | 多 Agent |
|------|----------|----------|
| 上下文污染 | 探索历史干扰执行质量 | 子 Agent 上下文隔离，互不干扰 |
| 注意力稀释 | LLM 在海量历史中迷失 | 每个子 Agent 专注单一任务 |
| 权限混乱 | 探索时可能意外修改文件 | 只读 Agent 物理上无法写文件 |

**核心洞察：上下文隔离 = 认知隔离 = 质量保障。**

---

<a id="part-2"></a>
## 第二部分：架构设计 ⚙️

<a id="orchestrator-executor"></a>
### 主从模型：编排者与执行者

v3_agent 采用**主从架构**：

```
主 Agent（编排者）
├── 理解用户意图
├── 分解任务
├── 决定派生哪种子 Agent
├── 整合子 Agent 的结果
└── 向用户汇报

子 Agent（执行者）
├── 接收具体任务
├── 在隔离上下文中执行
├── 返回结果摘要
└── 上下文销毁，不留痕迹
```

关键点：**主 Agent 不做具体工作，子 Agent 不做全局决策。**

这和软件工程里的「关注点分离」原则完全一致：每一层只做自己该做的事。

```
主 Agent 的视角
┌─────────────────────────────────────────────┐
│  用户: "重构项目的错误处理"                  │
│                                             │
│  主 Agent 思考:                             │
│  1. 先探索现有错误处理代码 → 派 Explore Agent│
│  2. 设计重构方案 → 派 Plan Agent            │
│  3. 执行重构 → 派 general-purpose Agent     │
│                                             │
│  主 Agent 上下文只有:                       │
│  - 用户指令                                 │
│  - 子 Agent 返回的摘要（不是原始数据）       │
└─────────────────────────────────────────────┘
```

<a id="context-isolation"></a>
### 上下文隔离：子 Agent 的独立世界

这是多 Agent 架构最关键的设计决策。

每个子 Agent 启动时，都有一个**全新的、空白的上下文**：

```python
# 子 Agent 的上下文从零开始
sub_messages = [{"role": "user", "content": prompt}]
# 没有主 Agent 的历史，没有其他子 Agent 的历史
# 只有当前任务的指令
```

子 Agent 完成任务后，它的整个上下文**被丢弃**。主 Agent 只收到一个文字摘要：

```
子 Agent 执行过程（对主 Agent 不可见）:
  读了 main.py (500行)
  读了 utils.py (300行)
  搜索了 "error" 关键词，找到 23 处
  分析了错误处理模式...

主 Agent 收到的摘要:
  "项目使用 try/except 处理错误，主要集中在 api/ 目录，
   缺少统一的错误类型定义，建议创建 errors.py 模块。"
```

**主 Agent 的上下文保持干净。** 它只知道「发现了什么」，不知道「怎么发现的」。

<a id="agent-registry"></a>
### Agent 类型注册表

v3_agent 定义了三种子 Agent 类型，每种类型有不同的工具权限：

```python
AGENT_TYPES = {
    "Explore": {
        "tools": ["bash", "read_file", "glob", "grep", "list_dir"],
        # 只读工具，物理上无法修改文件
    },
    "Plan": {
        "tools": ["bash", "read_file", "glob", "grep", "list_dir"],
        # 同样只读，专注于分析和规划
    },
    "general-purpose": {
        "tools": "*",  # 全部工具，包括 write_file, edit_file
    },
}
```

这个设计有两层含义：

**第一层：安全隔离**
Explore Agent 物理上没有 `write_file` 工具，即使 LLM 想写文件也做不到。这不是靠提示词约束，而是靠工具列表硬限制。

**第二层：认知专注**
工具越少，LLM 的决策空间越小，越专注。Explore Agent 只需要思考「怎么找到信息」，不需要思考「要不要修改这个文件」。

```
工具权限矩阵
                bash  read  write  edit  glob  grep  list  Todo  Task
Explore          ✓     ✓      ✗      ✗     ✓     ✓     ✓     ✗     ✗
Plan             ✓     ✓      ✗      ✗     ✓     ✓     ✓     ✗     ✗
general-purpose  ✓     ✓      ✓      ✓     ✓     ✓     ✓     ✓     ✗
主 Agent         ✓     ✓      ✓      ✓     ✓     ✓     ✓     ✓     ✓ ← 唯一能派生子 Agent 的
```

注意：**子 Agent 没有 Task 工具**，无法再派生子 Agent。这防止了无限递归，保持了架构的可控性。

---

<a id="part-3"></a>
## 第三部分：代码实现 💻

<a id="task-tool"></a>
### Task 工具：派生子 Agent 的接口

主 Agent 通过 `Task` 工具派生子 Agent：

```python
TASK_TOOL = {
    "name": "Task",
    "description": "Spawn a subagent for a focused subtask. "
                   "Subagents run in ISOLATED context - they don't see parent's history.",
    "input_schema": {
        "type": "object",
        "properties": {
            "description": {"type": "string"},   # 任务简短描述（用于显示进度）
            "prompt":      {"type": "string"},   # 给子 Agent 的详细指令
            "subagent_type": {
                "type": "string",
                "enum": ["Explore", "Plan", "general-purpose"]
            },
        },
        "required": ["description", "prompt", "subagent_type"],
    },
}
```

当主 Agent 调用 Task 工具时，它实际上在说：

> "我需要有人去做这件事，但我不想亲自做（会污染我的上下文）。
> 派一个 Explore Agent 去，让它告诉我结果就行。"

<a id="run-task"></a>
### run_task：子 Agent 执行引擎

`run_task` 是整个多 Agent 机制的核心：

```python
def run_task(description: str, prompt: str, subagent_type: str) -> str:
    config = AGENT_TYPES[subagent_type]

    # 1. 子 Agent 有自己的系统提示
    sub_system = f"You are a {subagent_type} subagent at {WORKDIR}.\n{config['prompt']}"

    # 2. 子 Agent 有自己的工具集（根据类型过滤）
    sub_tools = get_tools_for_agent(subagent_type)

    # 3. 子 Agent 从空白上下文开始 ← 关键！
    sub_messages = [{"role": "user", "content": prompt}]

    # 4. 子 Agent 独立运行完整的 agent loop
    while True:
        response = client.messages.create(
            model=MODEL,
            system=sub_system,
            messages=sub_messages,
            tools=sub_tools,
            max_tokens=8000,
        )
        if response.stop_reason != "tool_use":
            break
        # 执行工具调用，追加结果，继续循环
        ...

    # 5. 只返回最终文字摘要给主 Agent
    for block in response.content:
        if hasattr(block, "text"):
            return block.text  # ← 子 Agent 的全部上下文在这里被丢弃

    return "(subagent returned no text)"
```

注意这个函数的输入输出：
- **输入**：一段文字指令（`prompt`）
- **输出**：一段文字摘要（`return block.text`）

子 Agent 内部发生的一切——读了哪些文件、执行了哪些命令、中间推理过程——**全部不会传递给主 Agent**。

这就是上下文隔离的实现方式：**通过函数边界实现信息过滤**。

<a id="full-architecture"></a>
### 完整架构图

```
v3_agent 完整架构
┌─────────────────────────────────────────────────────────┐
│                      主 Agent                            │
│                                                         │
│  工具: bash, read_file, write_file, edit_file,          │
│        glob, grep, list_dir, TodoWrite, Task            │
│                                                         │
│  上下文: [用户指令] + [子Agent摘要] + [直接工具结果]     │
│                                                         │
│  ┌──────────────────────────────────────────────────┐   │
│  │  agent_loop                                      │   │
│  │  while True:                                     │   │
│  │    response = LLM(messages, ALL_TOOLS)           │   │
│  │    if tool == "Task":                            │   │
│  │      result = run_task(...)  ← 派生子 Agent      │   │
│  │    else:                                         │   │
│  │      result = execute_tool(...)                  │   │
│  └──────────────────────────────────────────────────┘   │
└──────────────────────┬──────────────────────────────────┘
                       │ Task 工具调用
          ┌────────────┼────────────┐
          │            │            │
┌─────────▼──────┐ ┌───▼────────┐ ┌▼───────────────────┐
│  Explore Agent  │ │ Plan Agent │ │ general-purpose    │
│                 │ │            │ │ Agent              │
│  工具: 只读5个  │ │ 工具: 只读 │ │ 工具: 全部8个      │
│                 │ │            │ │                    │
│  独立上下文     │ │ 独立上下文 │ │ 独立上下文         │
│  ┌───────────┐  │ │ ┌────────┐ │ │ ┌───────────────┐ │
│  │ agent_loop│  │ │ │ loop   │ │ │ │  agent_loop   │ │
│  └───────────┘  │ │ └────────┘ │ │ └───────────────┘ │
│                 │ │            │ │                    │
│  返回: 文字摘要 │ │ 返回: 方案 │ │ 返回: 完成报告    │
└─────────────────┘ └────────────┘ └────────────────────┘
  上下文销毁          上下文销毁      上下文销毁
```

主 Agent 的上下文只增长了三行摘要，而不是三个子 Agent 的全部工作历史。

---

<a id="faq"></a>
## 常见问题 FAQ

**Q: 子 Agent 不能再派生子 Agent，这是限制还是设计？**

A: 设计。`get_tools_for_agent` 函数明确过滤掉了 Task 工具：

```python
def get_tools_for_agent(agent_type: str) -> list:
    allowed = AGENT_TYPES.get(agent_type, {}).get("tools", "*")
    if allowed == "*":
        return BASE_TOOLS  # ← BASE_TOOLS 不包含 Task
    return [t for t in BASE_TOOLS if t["name"] in allowed]
```

这防止了无限递归，也保持了架构的可预测性。两层就够了：主 Agent 编排，子 Agent 执行。

**Q: 子 Agent 的上下文隔离会不会导致信息丢失？**

A: 会，这是权衡。子 Agent 的中间过程不会传给主 Agent，但这正是我们想要的——主 Agent 不需要知道「怎么找到的」，只需要知道「找到了什么」。

如果主 Agent 需要更多细节，它可以再派一个子 Agent 去深入探索。

**Q: 什么时候用子 Agent，什么时候主 Agent 直接做？**

A: 经验法则：
- 任务需要大量探索（读很多文件）→ 派 Explore Agent
- 任务需要设计方案（分析后规划）→ 派 Plan Agent
- 任务需要实现功能（写代码）→ 派 general-purpose Agent
- 简单的单步操作 → 主 Agent 直接用工具

**Q: 这和 Claude Code 真实的多 Agent 机制一样吗？**

A: 核心思想一致：上下文隔离、角色分工、摘要传递。真实系统会更复杂，比如支持并行执行多个子 Agent、更细粒度的权限控制、子 Agent 结果的结构化传递等。但这个 v3 实现已经展示了最核心的设计原则。

---

## 📝 结语

从单 Agent 到多 Agent，本质上是一次**认知架构的升级**：

```
单 Agent 的问题:
  一个人做所有事 → 上下文污染 → 注意力稀释 → 质量下降

多 Agent 的解法:
  分工 → 上下文隔离 → 专注执行 → 质量保障

实现机制:
  Task 工具 → run_task 函数 → 独立 agent_loop → 摘要返回
```

这个模式不只适用于 AI Agent。它是人类组织复杂工作的通用策略：**把大问题分解成小问题，让专注的执行者处理每个小问题，由编排者整合结果。**

理解了这个模式，你就理解了为什么 Claude Code 能处理「重构整个项目」这样的复杂任务——它不是一个 Agent 在硬撑，而是一个编排者在指挥多个专注的执行者协同工作。

**系列导航**：
- **上一篇**: [03 - TodoWrite：结构化任务规划](https://juejin.cn/post/7609660097766129674)
- **当前**:  [04 - Multi-Agent：复杂任务的分解之道](https://juejin.cn/editor/drafts/7608937611306090548)
- **下一篇**: 05 - agent 使用技巧Skill
