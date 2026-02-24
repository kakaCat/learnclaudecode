---
title: "02 - 把 Bash 拆成专用工具（read_file, write_file 等）"
description: "从 Unix「一个程序只做好一件事」哲学出发，解析为什么要把 bash 拆成专用工具，以及工具粒度的黄金法则——不是越细越好，而是意图越明确越好。"
image: "/images/blog/tool-design.jpg"
keywords:
  - Claude Code
  - AI Agent
  - Tool Design
  - Unix Philosophy
  - read_file
  - edit_file
  - Anthropic
tags:
  - Agent
  - Tool Design
  - Unix
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
  - Tool Granularity
  - Security Boundaries
  - Agent Tool Design
series: "从零构建 Claude Code"
series_order: 2
---

# 构建mini Claude Code：02 - 把 Bash 拆成专用工具（read_file, write_file 等）

## 📍 导航指南

这是「从零构建 Claude Code」系列的第二篇。根据你的背景，选择合适的阅读路径：

- 🧠 **理论派？** → [第一部分：为什么要拆工具](#part-1) - 理解拆分的动机
- ⚙️ **原则派？** → [第二部分：工具粒度法则](#part-2) - 掌握「恰好够用」的设计原则
- 💻 **代码派？** → [第三部分：代码实现](#part-3) - 直接看 4 个工具的完整实现

---

## 目录

### 第一部分：为什么要拆工具 🧠
- [v0 的局限：一把锤子打天下](#v0-limits)
- [Unix 哲学：一个程序只做好一件事](#unix-one-thing)
- [拆分带来的四个好处](#four-benefits)

### 第二部分：工具粒度法则 ⚙️
- [不是越细越好](#not-finer-is-better)
- [黄金法则：意图驱动粒度](#intent-driven)
- [参数细化 vs 工具拆分](#params-vs-split)

### 第三部分：代码实现 💻
- [四个工具的设计](#four-tools)
- [关键实现细节](#key-details)
- [完整代码](#full-code)

### 附录
- [常见问题 FAQ](#faq)

---

## 引言

上一篇我们用 **1 个 bash 工具**构建了最小 Agent。它能工作，但有明显的局限。

本篇的问题是：**什么时候应该拆工具？拆到什么粒度？**

答案来自 Unix 哲学的第二条原则：**一个程序只做好一件事（Do one thing and do it well）**。

---

<a id="part-1"></a>
## 第一部分：为什么要拆工具 🧠

<a id="v0-limits"></a>
### v0 的局限：一把锤子打天下

v0 只有一个 bash 工具，模型要读文件得这样做：

```python
# 模型调用 bash 读文件
{"command": "cat src/main.py"}

# 模型调用 bash 修改文件（外科手术式）
{"command": "sed -i 's/old_function/new_function/g' src/main.py"}

# 模型调用 bash 写新文件
{"command": "cat << 'EOF' > config.py\nDEBUG = True\nEOF"}
```

这有几个问题：

```
bash 工具的问题
├── 安全边界模糊   → cat ../../etc/passwd 和 cat src/main.py 一样能过
├── 意图不透明     → 日志里只有 "bash: cat src/main.py"，不知道是读还是搜索
├── 模型容易出错   → sed 语法复杂，模型经常写错转义
└── 输出难以控制   → 大文件 cat 出来直接撑爆上下文
```

<a id="unix-one-thing"></a>
### Unix 哲学：一个程序只做好一件事

Unix 工具链的设计哲学：

```
Unix 工具分工
├── cat    → 只负责输出文件内容
├── grep   → 只负责模式匹配
├── sed    → 只负责流编辑
├── awk    → 只负责字段处理
└── find   → 只负责文件查找

每个工具职责单一，通过管道组合完成复杂任务：
cat access.log | grep 500 | awk '{print $7}' | sort | uniq -c
```

映射到 Agent 工具设计：

```
Agent 工具分工
├── bash       → 只负责执行命令（git, npm, python...）
├── read_file  → 只负责读取文件内容
├── write_file → 只负责创建/覆写文件
└── edit_file  → 只负责精确替换文件中的文本
```

<a id="four-benefits"></a>
### 拆分带来的四个好处

**1. 安全边界更清晰**

```python
# bash 工具：危险命令黑名单，但路径穿越难拦截
dangerous = ["rm -rf /", "sudo", "shutdown"]
# cat ../../etc/passwd → 很难用黑名单拦截

# read_file 工具：路径沙箱，一行代码搞定
def safe_path(p: str) -> Path:
    path = (WORKDIR / p).resolve()
    if not path.is_relative_to(WORKDIR):
        raise ValueError(f"Path escapes workspace: {p}")
    return path
```

**2. 模型意图更明确**

```
日志对比：

bash 工具日志：
  > bash: {"command": "cat src/main.py"}        ← 是读文件？还是检查内容？
  > bash: {"command": "cat src/utils.py"}
  > bash: {"command": "python main.py"}

专用工具日志：
  > read_file: {"path": "src/main.py"}           ← 一眼看出：读文件
  > read_file: {"path": "src/utils.py"}          ← 一眼看出：读文件
  > bash: {"command": "python main.py"}          ← 一眼看出：执行程序
```

**3. edit_file 是关键优势**

纯 bash 做精确修改很麻烦：

```bash
# bash 方式：sed 语法复杂，特殊字符需要转义，模型经常写错
sed -i 's/def old_function(x, y):/def new_function(x, y, z):/g' main.py

# edit_file 方式：直接描述「把什么换成什么」，模型不需要懂 sed
{
  "path": "main.py",
  "old_text": "def old_function(x, y):",
  "new_text": "def new_function(x, y, z):"
}
```

**4. 输出可控**

```python
# bash：输出不可控，大文件直接撑爆上下文
{"command": "cat large_file.py"}  # 可能输出 10 万行

# read_file：内置 limit 参数，精确控制读取范围
{"path": "large_file.py", "limit": 100}  # 只读前 100 行
```

---

<a id="part-2"></a>
## 第二部分：工具粒度法则 ⚙️

<a id="not-finer-is-better"></a>
### 不是越细越好

既然拆工具有这么多好处，是不是应该拆得越细越好？

**不是。** 工具数量增加有代价：

```
工具数量的代价
├── Context 消耗   → 每个工具定义都要传给模型，占用 token
├── 模型选择成本   → 工具太多，模型选错工具的概率上升
└── 维护成本       → 工具越多，代码越复杂
```

极端反例——把 read_file 拆成这样：

```
❌ 过度拆分（错误示范）
├── read_first_line    → 读第一行
├── read_last_line     → 读最后一行
├── read_line_range    → 读指定行范围
├── read_python_file   → 读 Python 文件
└── read_json_file     → 读 JSON 文件
```

这不是「一个程序只做好一件事」，这是「把一件事拆成了五件事」。

<a id="intent-driven"></a>
### 黄金法则：意图驱动粒度

**工具的粒度应该对齐模型的意图，而不是对齐实现细节。**

```
意图层面的分工（正确）：
├── 我想读文件内容    → read_file
├── 我想写/创建文件   → write_file
├── 我想修改文件      → edit_file
└── 我想执行命令      → bash

实现层面的分工（错误）：
├── 我想读前 N 行     → read_first_n_lines
├── 我想读后 N 行     → read_last_n_lines
└── 我想读中间 N 行   → read_middle_n_lines
```

判断标准：**如果两个操作在模型的「思维」里是同一件事，就不应该拆成两个工具。**

读文件的前 100 行和读文件的后 100 行，在模型看来都是「读文件」——只是参数不同。

<a id="params-vs-split"></a>
### 参数细化 vs 工具拆分

这是工具设计中最重要的区分：

```
同一个意图 → 用参数细化（不要拆工具）
不同的意图 → 用工具拆分（不要合并工具）
```

**参数细化的正确示范：read_file**

```python
# v1 基础版：只有 path 和 limit
def read_file(path: str, limit: int = None) -> str:
    ...

# 更好的版本：增加 offset 参数，支持分段读取大文件
def read_file(path: str, offset: int = 1, limit: int = None) -> str:
    """
    offset=50, limit=100 → 读取第 50-149 行
    这让模型可以「翻页」读大文件，而不是一次性读完
    """
    ...
```

`offset` 和 `limit` 参数让 `read_file` 更强大，但工具的**意图没有变**——还是「读文件」。这是正确的细化方向。

对比工具拆分的正确示范：

```
bash vs read_file → 意图完全不同，必须拆分
  bash:      执行命令，有副作用，可能改变系统状态
  read_file: 只读操作，无副作用，只返回内容

write_file vs edit_file → 意图不同，必须拆分
  write_file: 完整覆写，适合创建新文件
  edit_file:  精确替换，适合修改现有代码
```

**工具粒度决策树：**

```
面对一个新操作，问自己：

这个操作和现有工具是「同一个意图」吗？
    │
    ├── 是 → 给现有工具加参数
    │         例：read_file 加 offset 参数
    │
    └── 否 → 创建新工具
              例：bash 和 read_file 意图不同，分开
```

---

<a id="part-3"></a>
## 第三部分：代码实现 💻

<a id="four-tools"></a>
### 四个工具的设计

```
v1 工具集
├── bash       → 执行任意 shell 命令（git, npm, python...）
│               安全：危险命令黑名单
│
├── read_file  → 读取文件内容
│               安全：路径沙箱（safe_path）
│               效率：limit 参数防止上下文溢出
│
├── write_file → 写入文件（创建或覆写）
│               安全：路径沙箱
│               便利：自动创建父目录
│
└── edit_file  → 精确替换文件中的文本
                安全：路径沙箱
                精确：只替换第一次出现（防止误改）
```

<a id="key-details"></a>
### 关键实现细节

**safe_path：路径沙箱**

```python
def safe_path(p: str) -> Path:
    path = (WORKDIR / p).resolve()
    if not path.is_relative_to(WORKDIR):
        raise ValueError(f"Path escapes workspace: {p}")
    return path

# 效果：
# safe_path("src/main.py")      → ✅ 允许
# safe_path("../../etc/passwd") → ❌ 拒绝
```

**edit_file：为什么只替换第一次出现**

```python
# 只替换第一次出现，防止意外批量修改
new_content = content.replace(old_text, new_text, 1)

# 如果文件里有 3 个相同的函数名，模型应该明确指定要改哪一个
# 而不是一次性全改——那样太危险
```

**工具分发：execute_tool**

```python
def execute_tool(name: str, args: dict) -> str:
    if name == "bash":      return run_bash(args["command"])
    if name == "read_file": return run_read(args["path"], args.get("limit"))
    if name == "write_file":return run_write(args["path"], args["content"])
    if name == "edit_file": return run_edit(args["path"], args["old_text"], args["new_text"])
    return f"Unknown tool: {name}"
```

这个分发函数是工具层和 Agent 循环之间的桥梁。每个工具返回字符串，统一送回给模型。

<a id="full-code"></a>
### 完整代码

```python
#!/usr/bin/env python3
import os
import subprocess
from pathlib import Path
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv(override=True)

if os.getenv("ANTHROPIC_BASE_URL"):
    os.environ.pop("ANTHROPIC_AUTH_TOKEN", None)

WORKDIR = Path.cwd()
MODEL = os.getenv("MODEL_ID", "claude-sonnet-4-5-20250929")
client = Anthropic(base_url=os.getenv("ANTHROPIC_BASE_URL"))

SYSTEM = f"""You are a coding agent at {WORKDIR}.
Loop: think briefly -> use tools -> report results.
Rules:
- Prefer tools over prose. Act, don't just explain.
- Never invent file paths. Use bash ls/find first if unsure.
- Make minimal changes. Don't over-engineer.
- After finishing, summarize what changed."""

TOOLS = [
    {
        "name": "bash",
        "description": "Run a shell command. Use for: ls, find, grep, git, npm, python, etc.",
        "input_schema": {
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"],
        },
    },
    {
        "name": "read_file",
        "description": "Read file contents. Returns UTF-8 text.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "limit": {"type": "integer", "description": "Max lines to read"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Write content to a file. Creates parent directories if needed.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "edit_file",
        "description": "Replace exact text in a file. Use for surgical edits.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "old_text": {"type": "string", "description": "Exact text to find"},
                "new_text": {"type": "string", "description": "Replacement text"},
            },
            "required": ["path", "old_text", "new_text"],
        },
    },
]


def safe_path(p: str) -> Path:
    path = (WORKDIR / p).resolve()
    if not path.is_relative_to(WORKDIR):
        raise ValueError(f"Path escapes workspace: {p}")
    return path


def run_bash(command: str) -> str:
    dangerous = ["rm -rf /", "sudo", "shutdown", "reboot", "> /dev/"]
    if any(d in command for d in dangerous):
        return "Error: Dangerous command blocked"
    try:
        result = subprocess.run(
            command, shell=True, cwd=WORKDIR,
            capture_output=True, text=True, timeout=120
        )
        output = (result.stdout + result.stderr).strip()
        return output[:50000] if output else "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: Command timed out (120s)"
    except Exception as e:
        return f"Error: {e}"


def run_read(path: str, limit: int = None) -> str:
    try:
        text = safe_path(path).read_text()
        lines = text.splitlines()
        if limit and limit < len(lines):
            lines = lines[:limit]
            lines.append(f"... ({len(text.splitlines()) - limit} more lines)")
        return "\n".join(lines)[:50000]
    except Exception as e:
        return f"Error: {e}"


def run_write(path: str, content: str) -> str:
    try:
        fp = safe_path(path)
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content)
        return f"Wrote {len(content)} bytes to {path}"
    except Exception as e:
        return f"Error: {e}"


def run_edit(path: str, old_text: str, new_text: str) -> str:
    try:
        fp = safe_path(path)
        content = fp.read_text()
        if old_text not in content:
            return f"Error: Text not found in {path}"
        fp.write_text(content.replace(old_text, new_text, 1))
        return f"Edited {path}"
    except Exception as e:
        return f"Error: {e}"


def execute_tool(name: str, args: dict) -> str:
    if name == "bash":       return run_bash(args["command"])
    if name == "read_file":  return run_read(args["path"], args.get("limit"))
    if name == "write_file": return run_write(args["path"], args["content"])
    if name == "edit_file":  return run_edit(args["path"], args["old_text"], args["new_text"])
    return f"Unknown tool: {name}"


def agent_loop(messages: list) -> list:
    while True:
        response = client.messages.create(
            model=MODEL, system=SYSTEM, messages=messages,
            tools=TOOLS, max_tokens=8000,
        )
        tool_calls = []
        for block in response.content:
            if hasattr(block, "text"):
                print(block.text)
            if block.type == "tool_use":
                tool_calls.append(block)

        if response.stop_reason != "tool_use":
            messages.append({"role": "assistant", "content": response.content})
            return messages

        results = []
        for tc in tool_calls:
            print(f"\n> {tc.name}: {tc.input}")
            output = execute_tool(tc.name, tc.input)
            preview = output[:200] + "..." if len(output) > 200 else output
            print(f"  {preview}")
            results.append({
                "type": "tool_result",
                "tool_use_id": tc.id,
                "content": output,
            })

        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": results})


def main():
    print(f"Mini Claude Code v1 - {WORKDIR}")
    print("Type 'exit' to quit.\n")
    history = []
    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not user_input or user_input.lower() in ("exit", "quit", "q"):
            break
        history.append({"role": "user", "content": user_input})
        try:
            agent_loop(history)
        except Exception as e:
            print(f"Error: {e}")
        print()


if __name__ == "__main__":
    main()
```

代码仓库：[shareAI-lab/learn-claude-code](https://github.com/shareAI-lab/learn-claude-code)

---

<a id="faq"></a>
## 常见问题 FAQ

**Q: 4 个工具够用吗？Claude Code 有 20 多个工具。**

A: 4 个工具覆盖 90% 的编码场景。Claude Code 的额外工具（glob、grep、web_fetch 等）是在这个基础上按需添加的，每个都有明确的意图。本系列后续会逐步引入。

**Q: edit_file 只替换第一次出现，如果我想替换所有呢？**

A: 这是有意为之的安全设计。如果需要批量替换，应该明确告诉模型，让它多次调用 edit_file，或者用 bash + sed。明确的意图比隐式的批量操作更安全。更完善的实现可以加 `replace_all: bool = False` 参数——这正是「参数细化」的正确用法。

**Q: 工具描述（description）重要吗？**

A: 非常重要。description 是模型选择工具的依据。`"Run a shell command. Use for: ls, find, grep, git, npm, python"` 比 `"Run a command"` 好得多——前者告诉模型什么时候该用这个工具。

**Q: 为什么 bash 工具还保留？read_file 不是更安全吗？**

A: bash 负责「执行」，read_file 负责「读取」。执行 `git status`、`npm install`、`python test.py` 这些操作没有对应的专用工具，bash 是必要的。两者意图不同，不能合并。

---

## 📝 结语

从 v0 的一个 bash 工具，到 v1 的四个专用工具，这条演化路径清晰地体现了 Unix 哲学：

```
v0: bash（一把锤子）
    ↓ 按意图拆分
v1: bash + read_file + write_file + edit_file
    ↓ 每个工具只做一件事
    ↓ 安全边界清晰
    ↓ 模型意图明确
    ↓ 日志可审计
```

工具设计的黄金法则：

```
同一个意图 → 参数细化（不要拆工具）
不同的意图 → 工具拆分（不要合并工具）
```

这不只是工程规范，这是让 Agent 更可靠、更安全、更可控的根本原则。

**系列导航**：
- **上一篇**:[01 - LLM + Bash = 最小 OS 接口]（https://juejin.cn/post/7608759940800151602）
- **当前**: 02 - 把 Bash 拆成专用工具（read_file, write_file 等）
- **下一篇**: 03 - TodoWrite：让模型按计划执行
