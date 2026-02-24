---
title: "03 - TodoWrite：让模型按计划执行"
description: "从「复杂任务为什么会失控」出发，解析为什么引入 TodoWrite 不是加功能，而是给 LLM 装上「工作记忆」——让它在多步骤任务中始终知道自己在哪、要去哪。"
image: "/images/blog/todo-agent.jpg"
keywords:
  - Claude Code
  - AI Agent
  - TodoWrite
  - Task Planning
  - Unix Philosophy
  - Anthropic
tags:
  - Agent
  - Planning
  - TodoWrite
  - Implementation
author: "manus-learn"
date: "2026-02-23"
last_modified_at: "2026-02-23"
lang: "zh-CN"
audience: "开发者 / 对 AI Agent 感兴趣的工程师"
difficulty: "beginner"
estimated_read_time: "12-15min"
topics:
  - Task Decomposition
  - Agent Working Memory
  - Structured Planning
  - Tool Design
series: "从零构建 Claude Code"
series_order: 3
---

# 构建mini Claude Code：03 - TodoWrite：让模型按计划执行

## 📍 导航指南

这是「从零构建 Claude Code」系列的第三篇。根据你的背景，选择合适的阅读路径：

- 🧠 **理论派？** → [第一部分：复杂任务为什么会失控](#part-1) - 理解问题的根源
- ⚙️ **设计派？** → [第二部分：TodoWrite 的本质](#part-2) - 理解这个设计决策
- 💻 **代码派？** → [第三部分：代码实现](#part-3) - 直接看完整实现

---

## 目录

### 第一部分：问题 🧠
- [v1 能做什么，不能做什么](#v1-limits)
- [复杂任务为什么会失控](#why-complex-fails)
- [LLM 的「工作记忆」问题](#working-memory)

### 第二部分：设计 ⚙️
- [TodoWrite 的本质：显式化计划](#todo-essence)
- [不是越多工具越好：glob/grep/list_dir 的加入](#exploration-tools)
- [工具组合：复杂问题的解法](#tool-composition)

### 第三部分：代码实现 💻
- [TodoManager：状态机而非列表](#todo-manager)
- [NAG_REMINDER：强制更新机制](#nag-reminder)
- [完整代码](#full-code)

### 附录
- [常见问题 FAQ](#faq)

---

## 引言

v1 有 4 个工具，能读写文件、执行命令。给它一个简单任务——「修复这个 bug」——它能完成。

但给它一个复杂任务——「重构这个模块，确保所有测试通过」——它开始出问题：忘记做了什么、重复探索同一个文件、做到一半不知道下一步是什么。

**工具够用，但模型失控了。**

这篇文章解释为什么，以及 TodoWrite 如何解决这个问题。

---

<a id="part-1"></a>
## 第一部分：问题 🧠

<a id="v1-limits"></a>
### v1 能做什么，不能做什么

v1 的 4 个工具（bash、read_file、write_file、edit_file）覆盖了「执行」层面的所有操作。对于单步任务，它工作得很好：

```
简单任务（v1 能处理）：
├── 「读取 main.py，告诉我有几个函数」  → read_file → 回答
├── 「在 config.py 里把 DEBUG 改成 False」 → read_file → edit_file → 完成
└── 「运行测试，告诉我结果」             → bash → 回答
```

但复杂任务不一样：

```
复杂任务（v1 开始失控）：
└── 「重构 auth 模块，把 JWT 换成 session，确保测试通过」
    ├── 需要先探索：auth 模块在哪？有哪些文件？
    ├── 需要理解：哪些地方用了 JWT？
    ├── 需要规划：改哪些文件？顺序是什么？
    ├── 需要执行：逐个修改
    ├── 需要验证：运行测试
    └── 需要回溯：测试失败了，回去改哪里？
```

这不是工具不够用，而是**任务本身需要规划**。

<a id="why-complex-fails"></a>
### 复杂任务为什么会失控

LLM 处理复杂任务时，有一个结构性的问题：

```
LLM 的上下文随任务进行不断增长：

Turn 1:  [用户指令]
Turn 3:  [用户指令] [工具调用1] [结果1] [工具调用2] [结果2]
Turn 10: [用户指令] [工具调用1..9] [结果1..9] [工具调用10] ...
Turn 20: [用户指令] [工具调用1..19] [结果1..19] ...
                                                    ↑
                                          上下文越来越长
                                          早期的「计划」被淹没
```

当上下文里充满了工具调用和结果，模型很难回答这些问题：

- 我现在完成了哪些步骤？
- 还有哪些步骤没做？
- 我当前在做什么？

没有显式的计划，模型只能从上下文里「推断」自己的进度——这很不可靠。

<a id="working-memory"></a>
### LLM 的「工作记忆」问题

人类做复杂任务时，会用外部工具辅助记忆：

```
人类处理复杂任务：
├── 写 TODO 清单（知道还有什么没做）
├── 划掉已完成项（知道做了什么）
└── 标记「进行中」（知道当前在做什么）
```

LLM 没有这个机制。它的「记忆」就是上下文，而上下文是线性的、只增不减的。

**TodoWrite 就是给 LLM 装上这个外部工作记忆。**

---

<a id="part-2"></a>
## 第二部分：设计 ⚙️

<a id="todo-essence"></a>
### TodoWrite 的本质：显式化计划

TodoWrite 不是一个普通的「记录功能」，它是一个**状态机**：

```
每个 Todo 的状态流转：

pending → in_progress → completed

规则：
- 同时只能有一个 in_progress（强制专注）
- 开始前标记 in_progress（声明意图）
- 完成后立即标记 completed（确认完成）
```

这个状态机解决了「失控」问题：

```
有 TodoWrite 的任务执行：

Turn 1:  用户说「重构 auth 模块」
         → LLM 调用 TodoWrite，写下计划：
           [ ] 探索 auth 模块结构
           [ ] 找出所有 JWT 使用点
           [ ] 修改认证逻辑
           [ ] 更新测试
           [ ] 运行测试验证

Turn 5:  上下文已经很长了，但 TodoWrite 的状态始终可见：
           [x] 探索 auth 模块结构
           [>] 找出所有 JWT 使用点  ← 当前在做这个
           [ ] 修改认证逻辑
           [ ] 更新测试
           [ ] 运行测试验证

Turn 15: 模型随时能看到「我在哪」：
           [x] 探索 auth 模块结构
           [x] 找出所有 JWT 使用点
           [x] 修改认证逻辑
           [>] 更新测试               ← 当前在做这个
           [ ] 运行测试验证
```

**计划是显式的，进度是可见的，模型不会迷失。**

这和 Unix 哲学的「配置存放在纯文本文件」一脉相承：把状态显式化，而不是藏在程序内部。

<a id="exploration-tools"></a>
### 不是越多工具越好：glob/grep/list_dir 的加入

v2 同时加入了三个探索工具：glob、grep、list_dir。为什么？

回到上一篇的黄金法则：**意图驱动粒度**。

```
v1 的探索方式（用 bash）：
  bash: {"command": "find . -name '*.py'"}
  bash: {"command": "grep -r 'import jwt' ."}
  bash: {"command": "ls -la src/"}

v2 的探索方式（专用工具）：
  glob: {"pattern": "**/*.py"}
  grep: {"pattern": "import jwt"}
  list_dir: {"path": "src/"}
```

这不只是语法糖。专用探索工具有三个实质好处：

**1. 路径沙箱自动生效**

```python
# bash 的 find：路径穿越难拦截
bash: {"command": "find ../../ -name '*.env'"}  # 危险

# glob 的 safe_path：自动限制在 WORKDIR 内
glob: {"pattern": "**/*.env"}  # 自动沙箱
```

**2. 输出格式统一**

```
bash find 的输出：
./src/main.py
./src/utils.py
./tests/test_main.py

glob 的输出（相对路径，干净）：
src/main.py
src/utils.py
tests/test_main.py
```

**3. 意图分离**

bash 工具的描述是「执行命令」，用于 git、npm、python 等有副作用的操作。探索操作（只读、无副作用）用专用工具，意图更清晰，日志更可审计。

```
日志对比：
> bash: {"command": "grep -r 'def auth' src/"}   ← 是在搜索？还是在执行什么？
> grep: {"pattern": "def auth", "dir": "src/"}   ← 一眼看出：搜索代码
```

<a id="tool-composition"></a>
### 工具组合：复杂问题的解法

v2 的 8 个工具形成了两个清晰的层次：

```
探索层（只读，理解现状）：
├── list_dir  → 了解目录结构
├── glob      → 找到相关文件
├── grep      → 搜索代码内容
└── read_file → 读取文件详情

执行层（有副作用，改变现状）：
├── write_file → 创建新文件
├── edit_file  → 修改现有文件
└── bash       → 执行命令（git, npm, python...）

规划层（元操作，管理任务本身）：
└── TodoWrite  → 记录和追踪计划
```

复杂任务的解法就是这三层的组合：

```
复杂任务 = 先探索 → 再规划 → 再执行 → 验证 → 循环

具体流程：
1. list_dir / glob    → 了解代码结构
2. grep / read_file   → 理解具体内容
3. TodoWrite          → 写下执行计划
4. edit_file / bash   → 按计划执行
5. bash（运行测试）   → 验证结果
6. TodoWrite（更新）  → 标记完成，看下一步
```

**工具不是孤立的，它们通过「上下文」这条管道串联起来——就像 Unix 的 pipe。**

---

<a id="part-3"></a>
## 第三部分：代码实现 💻

<a id="todo-manager"></a>
### TodoManager：状态机而非列表

TodoManager 的核心是 `update` 方法，它不是「追加」，而是「替换」：

```python
class TodoManager:
    def update(self, items: list) -> str:
        # 验证规则
        in_progress_count = 0
        for item in items:
            if item["status"] == "in_progress":
                in_progress_count += 1

        if in_progress_count > 1:
            raise ValueError("Only one task can be in_progress at a time")

        # 完整替换（不是追加）
        self.items = validated
        return self.render()
```

每次调用 TodoWrite，模型必须传入**完整的任务列表**。这个设计很关键：

```
追加模式（错误设计）：
  Turn 3:  添加「修改 auth.py」
  Turn 7:  添加「运行测试」
  → 模型看不到全局，不知道总共有几步

替换模式（正确设计）：
  Turn 3:  传入完整列表 [探索, 修改, 测试]，标记「探索」为 in_progress
  Turn 7:  传入完整列表 [探索✓, 修改→, 测试]，标记「修改」为 in_progress
  → 模型每次都看到全局，知道自己在哪
```

`render()` 方法把状态渲染成可读的文本，返回给模型：

```python
def render(self) -> str:
    # [x] 已完成的任务
    # [>] 进行中的任务 <- 当前活跃形式
    # [ ] 待完成的任务
    # (2/5 completed)
```

这个文本会出现在工具调用结果里，模型下一轮就能看到当前进度。

<a id="nag-reminder"></a>
### NAG_REMINDER：强制更新机制

只有 TodoWrite 工具还不够——模型可能「忘记」更新。v2 加了一个强制机制：

```python
NAG_REMINDER = "<reminder>10+ turns without todo update. Please update todos.</reminder>"

rounds_without_todo = 0

# 在 agent_loop 里：
if tc.name == "TodoWrite":
    used_todo = True

rounds_without_todo = 0 if used_todo else rounds_without_todo + 1

if rounds_without_todo > 10:
    results.insert(0, {"type": "text", "text": NAG_REMINDER})
```

这个机制的逻辑：如果模型连续 10 轮没有更新 todo，说明它可能在「埋头执行」而忘记了计划层面的追踪。提醒它更新，让它重新审视进度。

这不是惩罚，而是**把「保持计划同步」这个行为规范化**。

<a id="full-code"></a>
### 完整代码

v2 的完整代码在 [v2_agent.py](../v2_agent.py)，核心结构：

```
v2_agent.py
├── TodoManager          → 状态机，管理任务列表
│
├── TOOLS（8个）
│   ├── 探索层: glob, grep, list_dir
│   ├── 执行层: bash, read_file, write_file, edit_file
│   └── 规划层: TodoWrite
│
├── agent_loop
│   ├── 调用 LLM
│   ├── 执行工具
│   ├── 追踪 rounds_without_todo
│   └── 必要时注入 NAG_REMINDER
│
└── main REPL
    └── 首条消息注入 INITIAL_REMINDER
```

关键的系统提示词变化：

```python
# v1 的系统提示
SYSTEM = "Loop: think briefly -> use tools -> report results."

# v2 的系统提示（加入了规划指令）
SYSTEM = """Loop: plan -> act with tools -> update todos -> report.

Rules:
- Use TodoWrite to track multi-step tasks
- Mark tasks in_progress before starting, completed when done
- Use glob/grep/list_dir to explore. Use bash only for execution.
- Never invent file paths. Explore first if unsure."""
```

系统提示明确告诉模型：**先探索，再规划，再执行**。这个顺序很重要——没有探索就规划，计划会脱离实际。

---

<a id="faq"></a>
## 常见问题 FAQ

**Q: TodoWrite 会不会增加很多 token 消耗？**

A: 会，但值得。每次 TodoWrite 调用会在上下文里留下任务列表，但这个「开销」换来的是模型不会迷失方向。对于复杂任务，没有 TodoWrite 导致的重复探索和错误，消耗的 token 更多。

**Q: 简单任务也需要 TodoWrite 吗？**

A: 不需要。系统提示是「Use TodoWrite to track **multi-step** tasks」。单步任务（读一个文件、改一行代码）不需要规划，模型会自己判断。TodoWrite 是工具，不是强制流程。

**Q: 为什么 in_progress 只能有一个？**

A: 强制专注。如果允许多个 in_progress，模型可能「同时开始」多个任务，然后都做到一半。一次只做一件事，做完再做下一件——这是 Unix 哲学「沉默是金」的变体：不要同时做太多事。

**Q: glob/grep 和 bash 里的 find/grep 有什么本质区别？**

A: 意图和安全边界。bash 的 find/grep 可以访问任意路径，glob/grep 工具自动限制在 WORKDIR 内。更重要的是意图：bash 是「执行命令」，glob/grep 是「探索代码」——日志里一眼就能区分。

**Q: 8 个工具是终点吗？**

A: 不是。Claude Code 有 20+ 个工具。但每个工具的加入都有明确理由——意图不同、安全边界不同、或者现有工具组合无法优雅表达的操作。工具数量不是目标，**意图的清晰度**才是。

---

## 📝 结语

从 v0 到 v2，三个版本的演化路径：

```
v0: bash（1个工具）
    ↓ 意图拆分
v1: bash + read_file + write_file + edit_file（4个工具）
    ↓ 加入探索层 + 规划层
v2: 探索(glob/grep/list_dir) + 执行(bash/read/write/edit) + 规划(TodoWrite)（8个工具）
```

每一步都有明确的动机：

```
v0 → v1: 工具太粗，意图不明确，安全边界模糊
v1 → v2: 工具够用，但复杂任务缺少规划机制
```

TodoWrite 的本质不是「加了一个功能」，而是**给 LLM 装上了工作记忆**——让它在多步骤任务中始终知道：

- 我要做什么（完整计划）
- 我做了什么（已完成项）
- 我现在在做什么（in_progress）
- 我还要做什么（pending）

这四个问题，是任何复杂任务执行者——无论是人还是 LLM——都需要随时能回答的。

**系列导航**：
- **上一篇**: [02 - 把 Bash 拆成专用工具（read_file, write_file 等）](https://juejin.cn/spost/7608751148120899610)
- **当前**: 03 - TodoWrite：让模型按计划执行
- **下一篇**:04 - 子智能体：用上下文隔离对抗记忆爆炸