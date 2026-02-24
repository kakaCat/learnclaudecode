---
title: "LLM + Bash = 最小 OS 接口：从 Unix 哲学到 AI Agent"
description: "从 Unix「一切皆文件」哲学出发，深度解析为什么 LLM + 一个 bash 工具就能构成最小智能体，以及 50 行代码如何实现一个完整的 Coding Agent。"
image: "/images/blog/bash-agent.jpg"
keywords:
  - Claude Code
  - AI Agent
  - Bash
  - Unix Philosophy
  - ReAct
  - LLM
  - Anthropic
tags:
  - Agent
  - Bash
  - Unix
  - ReAct
  - Implementation
author: "manus-learn"
date: "2026-02-23"
last_modified_at: "2026-02-23"
lang: "zh-CN"
audience: "开发者 / 对 AI Agent 感兴趣的工程师"
difficulty: "beginner"
estimated_read_time: "12-15min"
topics:
  - Unix Philosophy
  - LLM Agent Design
  - ReAct Loop
  - Minimal Agent Implementation
series: "从零构建 Claude Code"
series_order: 1
---

# 构建mini Claude Code：01 - LLM + Bash = 最小 OS 接口

## 📍 导航指南

这是「从零构建 Claude Code」系列的第一篇。根据你的背景，选择合适的阅读路径：

- 🧠 **理论派？** → [第一部分：Unix 哲学与 LLM](#part-1) - 理解「一切皆文件」如何映射到 LLM
- ⚙️ **实践派？** → [第二部分：ReAct 循环](#part-2) - 掌握 LLM 操作文件的核心机制
- 💻 **代码派？** → [第三部分：50 行实现](#part-3) - 直接看完整代码与逐行解析

---

## 目录

### 第一部分：理论基础 🧠
- [Unix 哲学：一切皆文件](#unix-philosophy)
- [LLM 即 Agent：上下文就是感知](#llm-as-agent)
- [为什么 Bash 就够了](#why-bash)

### 第二部分：ReAct 循环 ⚙️
- [人类 vs LLM：操作计算机的方式](#human-vs-llm)
- [ReAct：感知 → 思考 → 行动](#react-loop)
- [工具调用：LLM 的「双手」](#tool-call)

### 第三部分：代码实现 💻
- [整体架构](#architecture)
- [工具定义：一个 bash 工具](#tool-definition)
- [核心循环：agent_loop 函数](#chat-function)
- [完整代码](#full-code)

### 附录
- [常见问题 FAQ](#faq)

---

## 引言

Claude Code 是如何工作的？它为什么能读文件、写代码、执行命令？

答案出乎意料地简单：**LLM + bash 工具 + 一个循环**。

这不是简化，这就是本质。本文将从 Unix 哲学出发，解释为什么这个组合能构成一个完整的智能体，并用 50 行 Python 代码证明它。

---

<a id="part-1"></a>
## 第一部分：理论基础 🧠

<a id="unix-philosophy"></a>
### Unix 哲学：一切皆文件

1969 年，Unix 的设计者提出了一个影响深远的哲学：

> **一切皆文件（Everything is a file）**

在 Unix 世界里，不只是文档是文件——进程、网络连接、硬件设备，全部抽象为文件。这个统一的抽象带来了一个强大的推论：

**掌握文件操作，就掌握了整个系统。**

```
文件系统
├── 代码文件      → cat, echo, sed
├── 进程          → /proc/[pid]/
├── 网络          → /dev/tcp/
├── 设备          → /dev/sda
└── 一切...
```

Unix 工具链（`cat`, `grep`, `find`, `pipe`）正是基于这个哲学构建的。每个工具做好一件事，通过管道组合，就能完成任意复杂的任务。

**这个哲学对 AI Agent 意味着什么？**

如果 LLM 能够操作文件——读取、写入、搜索、执行——它就拥有了操控整个计算机系统的能力。

<a id="llm-as-agent"></a>
### LLM 即 Agent：上下文就是感知

传统程序通过变量存储状态，通过函数调用执行逻辑。LLM 不同：

**LLM 的「状态」就是它的上下文（Context）。**

```
传统程序:
  state = {}
  state["file_content"] = read_file("main.py")
  result = process(state)

LLM Agent:
  context = [
    {"role": "user", "content": "读取 main.py"},
    {"role": "assistant", "content": "...", "tool_use": {"bash": "cat main.py"}},
    {"role": "user", "content": "tool_result: def main(): ..."},
    {"role": "assistant", "content": "文件内容是..."}
  ]
```

上下文就是 LLM 的「工作记忆」。它看到的一切——用户指令、工具执行结果、历史对话——都在这个上下文里。

**LLM 通过读写上下文来感知世界，通过工具调用来改变世界。**

<a id="why-bash"></a>
### 为什么 Bash 就够了

回到 Unix 哲学：如果一切皆文件，而 bash 是操作文件的通用接口，那么：

| 你需要做什么 | Bash 命令 |
|-------------|-----------|
| 读取文件 | `cat`, `head`, `tail`, `grep` |
| 写入文件 | `echo '...' > file`, `cat << 'EOF'` |
| 搜索代码 | `find`, `grep`, `rg`, `ls` |
| 执行程序 | `python`, `npm`, `make` |

**Bash 是 Unix 系统的统一接口。LLM 掌握 bash，就掌握了整个 OS。**


---

<a id="part-2"></a>
## 第二部分：ReAct 循环 ⚙️

<a id="human-vs-llm"></a>
### 人类 vs LLM：操作计算机的方式

人类使用计算机的方式：

```
人类操作计算机
┌─────────────────────────────────────┐
│  看终端输出  →  敲命令  →  看输出   │
│      ↑                    │         │
│      └────────────────────┘         │
│           不断循环直到完成           │
└─────────────────────────────────────┘
```

LLM Agent 操作计算机的方式：

```
LLM Agent 操作计算机
┌─────────────────────────────────────┐
│  看上下文  →  产生命令调用  →  读输出│
│     ↑                      │        │
│     └──────────────────────┘        │
│          不断循环直到完成            │
└─────────────────────────────────────┘
```

**结构完全相同。** 唯一的区别是：人类用眼睛看终端，LLM 用上下文感知；人类用手敲键盘，LLM 用工具调用。

<a id="react-loop"></a>
### ReAct：感知 → 思考 → 行动

ReAct（Reasoning + Acting）是 AI Agent 的核心范式：

```
ReAct 循环
                    ┌──────────────────┐
                    │   用户输入任务    │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │  LLM 分析上下文  │  ← Reasoning
                    │  决定下一步行动  │
                    └────────┬─────────┘
                             │
              ┌──────────────▼──────────────┐
              │         有工具调用？          │
              └──────┬───────────────┬───────┘
                    是               否
                     │               │
          ┌──────────▼──────┐  ┌─────▼──────┐
          │  执行 bash 命令  │  │  返回结果  │ ← 任务完成
          │  (Acting)        │  └────────────┘
          └──────────┬───────┘
                     │
          ┌──────────▼──────┐
          │  将输出追加到    │
          │  上下文（记忆）  │
          └──────────┬───────┘
                     │
                     └──────────────────┐
                                        │
                    ┌───────────────────▼──┐
                    │  LLM 再次分析上下文  │
                    └──────────────────────┘
```

每一次循环，LLM 都在：
1. **感知**：读取上下文中的所有信息
2. **推理**：决定下一步该做什么
3. **行动**：调用 bash 工具执行命令
4. **记忆**：将结果写回上下文

这个循环不断重复，直到任务完成。

<a id="tool-call"></a>
### 工具调用：LLM 的「双手」

没有工具，LLM 只能「说话」，无法「行动」。工具调用（Tool Use）是 LLM 与外部世界交互的桥梁：

```python
# LLM 决定调用工具时，返回的不是文字，而是结构化的工具调用
{
  "type": "tool_use",
  "name": "bash",
  "input": {
    "command": "cat main.py"
  }
}
```

程序捕获这个调用，执行真实的 bash 命令，将输出返回给 LLM：

```python
# 工具执行结果
{
  "type": "tool_result",
  "content": "def main():\n    print('hello world')\n"
}
```

LLM 读到这个结果，继续推理。**工具调用让 LLM 从「语言模型」变成了「行动主体」。**

---

<a id="part-3"></a>
## 第三部分：代码实现 💻

<a id="architecture"></a>
### 整体架构

`bash_agent.py` 的架构极其简洁：

```
bash_agent.py
├── 配置层
│   ├── Anthropic 客户端
│   ├── 模型 ID
│   └── 系统提示词
│
├── 工具层（只有一个工具）
│   └── bash: 执行任意 shell 命令
│
└── 核心循环
    └── chat(prompt, history)
        ├── 追加用户消息
        ├── while True:
        │   ├── 调用 LLM
        │   ├── 无工具调用 → return 结果
        │   └── 有工具调用 → 执行 bash → 追加结果 → 继续
        └── 返回最终文本
```

整个 Agent 的核心逻辑不超过 50 行。

<a id="tool-definition"></a>
### 工具定义：一个 bash 工具

```python
TOOL = [{
    "name": "bash",
    "description": "Run a shell command.",
    "input_schema": {
        "type": "object",
        "properties": {"command": {"type": "string"}},
        "required": ["command"],
    },
}]
```

**工具描述（description）至关重要。** 它不只是说明工具用途，更是在教 LLM 如何使用这个工具。注意描述里列出了常见的使用模式——这直接影响 LLM 的行为质量。

<a id="chat-function"></a>
### 核心循环：agent_loop 函数

```python
def agent_loop(messages: list):
    while True:
        # 1. 调用 LLM
        response = client.messages.create(
            model=MODEL,
            system=SYSTEM,
            messages=messages,
            tools=TOOLS,
            max_tokens=8000
        )

        # 2. 保存 LLM 的回复
        messages.append({"role": "assistant", "content": response.content})

        # 3. 没有工具调用 → 任务完成
        if response.stop_reason != "tool_use":
            return

        # 4. 执行工具调用，收集结果
        results = []
        for block in response.content:
            if block.type == "tool_use":
                output = run_bash(block.input["command"])
                results.append({"type": "tool_result",
                                 "tool_use_id": block.id,
                                 "content": output})

        # 5. 将结果追加到历史，继续循环
        messages.append({"role": "user", "content": results})
```

这个函数就是整个 Agent 的心脏。注意几个关键设计：

- **`messages` 是可变对象**：历史在多轮对话间共享，LLM 能记住之前的操作
- **`stop_reason` 判断**：`tool_use` 表示 LLM 想调用工具，否则表示任务完成
- **输出截断**：`output[:50000]` 防止超长输出撑爆上下文

---

<a id="full-code"></a>
### 完整代码

```python
#!/usr/bin/env python
import os
import subprocess
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv(override=True)

client = Anthropic(base_url=os.getenv("ANTHROPIC_BASE_URL"))
MODEL = os.getenv("MODEL_ID", "claude-sonnet-4-5-20250929")

SYSTEM = f"You are a coding agent at {os.getcwd()}. Use bash to solve tasks. Act, don't explain."

TOOLS = [{
    "name": "bash",
    "description": "Run a shell command.",
    "input_schema": {
        "type": "object",
        "properties": {"command": {"type": "string"}},
        "required": ["command"],
    },
}]


def run_bash(command: str) -> str:
    try:
        r = subprocess.run(command, shell=True, cwd=os.getcwd(),
                           capture_output=True, text=True, timeout=120)
        out = (r.stdout + r.stderr).strip()
        return out[:50000] if out else "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: Timeout (120s)"


def agent_loop(messages: list):
    while True:
        response = client.messages.create(
            model=MODEL, system=SYSTEM, messages=messages,
            tools=TOOLS, max_tokens=8000,
        )
        messages.append({"role": "assistant", "content": response.content})
        if response.stop_reason != "tool_use":
            return
        results = []
        for block in response.content:
            if block.type == "tool_use":
                print(f"\033[33m$ {block.input['command']}\033[0m")
                output = run_bash(block.input["command"])
                print(output[:200])
                results.append({"type": "tool_result", "tool_use_id": block.id,
                                "content": output})
        messages.append({"role": "user", "content": results})


if __name__ == "__main__":
    history = []
    while True:
        try:
            query = input("\033[36magent >> \033[0m")
        except (EOFError, KeyboardInterrupt):
            break
        if query.strip().lower() in ("q", "exit", ""):
            break
        history.append({"role": "user", "content": query})
        agent_loop(history)
        last = history[-1]["content"]
        if isinstance(last, list):
            for block in last:
                if hasattr(block, "text"):
                    print(block.text)
        print()
```

代码仓库：[shareAI-lab/learn-claude-code](https://github.com/shareAI-lab/learn-claude-code)

---

<a id="faq"></a>
## 常见问题 FAQ

**Q: 只有一个 bash 工具，安全吗？**

A: 这是学习版本，展示最小实现。生产环境需要沙盒隔离（后续会有 Docker + VNC 沙盒实现专篇）。

**Q: 为什么不用更多专用工具（read_file, write_file 等）？**

A: 这是 v0 教学版，我们刻意只暴露一个 bash 工具，让你先看清「LLM + 最小 OS 接口」这条线。真实系统里会遵循「一个程序只做好一件事」的原则，把 bash 再拆成 read_file、write_file、run_command 等专用工具，方便做权限控制、审计和限流。下一篇会专门讲如何把 bash 拆成这类专用工具。

**Q: 上下文会不会越来越长，最终超出限制？**

A: 会。这是 v0 版本的局限。后续版本会介绍上下文压缩技术。

---

## 📝 结语

从 Unix「一切皆文件」的哲学，到 LLM 通过 bash 操控整个系统，这条线索清晰而优雅：

```
Unix 哲学: 一切皆文件
    ↓
Bash: 操作文件的统一接口
    ↓
LLM + Bash: 能思考的 OS 操作者
    ↓
ReAct 循环: 感知 → 推理 → 行动 → 记忆
    ↓
50 行代码: 一个完整的 Coding Agent
```

这不只是一个玩具实现。Claude Code、Cursor、Devin——所有现代 Coding Agent 的核心，都是这个循环的变体。理解了这个最小模型，你就理解了它们的本质。

在接下来的系列中，我们将在这个基础上逐步构建：安全沙盒、多 Agent 协作、上下文管理、任务规划……每一步都有可运行的代码。

**系列导航**：
- **当前**: 01 - LLM + Bash = 最小 OS 接口()
- **下一篇**: [02 - 把 Bash 拆成专用工具（read_file, write_file 等）](https://juejin.cn/spost/7608751148120899610)
