---
title: "从「文件冲突」到「分身协作」：Worktree 如何让多 Agent 安全并行"
description: "多个 Agent 同时修改同一文件会产生冲突——谁来改？改哪里？v11 借鉴 git 分支思想，用 Worktree 给每个任务创建独立的文件系统「分身」，完成后再合并，彻底解决并行冲突问题。"
image: "/images/blog/worktree-task-isolation.jpg"
keywords:
  - Claude Code
  - AI Agent
  - Worktree
  - Task Isolation
  - Git Worktree
  - Parallel Agents
  - Anthropic
tags:
  - Agent
  - Worktree
  - Isolation
  - Implementation
author: "manus-learn"
date: "2026-02-25"
last_modified_at: "2026-02-25"
lang: "zh-CN"
audience: "开发者 / 对 AI Agent 感兴趣的工程师"
difficulty: "intermediate"
estimated_read_time: "12-15min"
topics:
  - Worktree Isolation
  - Task Board
  - Git Worktree
  - Parallel Execution
  - Merge Strategy
series: "从零构建 Claude Code"
series_order: 12
---

# 构建mini Claude Code：12 - 从「文件冲突」到「分身协作」：Worktree 如何让多 Agent 安全并行

## 📍 导航指南

这是「从零构建 Claude Code」系列的第十二篇。根据你的背景，选择合适的阅读路径：

- 🧠 **理论派？** → [第一部分：冲突的根源](#part-1) - 理解为什么多 Agent 并行会产生文件冲突
- ⚙️ **实践派？** → [第二部分：Worktree 机制](#part-2) - 掌握分身、任务绑定、生命周期的设计
- 💻 **代码派？** → [第三部分：代码实现](#part-3) - 直接看完整实现
- 🔭 **探索派？** → [第四部分：扩展方向](#part-4) - Worktree 的更多可能

---

## 目录

### 第一部分：理论基础 🧠
- [多 Agent 并行的文件冲突问题](#conflict-problem)
- [git 分支给我们的启示](#git-insight)
- [核心洞察：隔离执行，统一协调](#core-insight)

### 第二部分：机制设计 ⚙️
- [Worktree：文件系统的「分身」](#worktree-concept)
- [任务看板：控制平面](#task-board)
- [何时触发 Worktree，何时不触发](#when-to-use)
- [生命周期：创建、执行、关闭](#lifecycle)
- [EventBus：可观测性](#eventbus)

### 第三部分：代码实现 💻
- [WorktreeManager 实现](#worktree-impl)
- [TaskManager 与 Worktree 绑定](#task-binding)
- [工具接口设计](#tool-design)

### 第四部分：扩展方向 🔭
- [自动合并策略](#merge-strategy)
- [多级隔离](#multi-level)

### 附录
- [常见问题 FAQ](#faq)

---

## 引言

上一篇我们让 Teammate 学会了「主动找活」：空闲时扫描任务看板、认领任务、自主执行。Agent 系统终于从「被动工具」变成了「自主团队」。

但随之而来一个新问题，而且是个根本性的问题：

```
场景：两个 Agent 同时处理同一个代码库

coder_1: [认领任务A：重构 auth.py 的登录逻辑]
coder_2: [认领任务B：给 auth.py 添加 OAuth 支持]

coder_1: [读取 auth.py，开始修改...]
coder_2: [读取 auth.py，开始修改...]

coder_1: [写入修改后的 auth.py]
coder_2: [写入修改后的 auth.py]  ← 覆盖了 coder_1 的修改！
```

**谁来改这个文件？能改什么？改完怎么合并？**

这不是调度问题，也不是锁的问题——锁只能让两个 Agent 串行，失去了并行的意义。这是一个**隔离**问题。

v11 的答案借鉴了 git 最核心的设计思想：**分支**。

> **说明**：v11_worktree_task_isolation.py 在任务看板的基础上，引入了 git worktree 机制，让每个任务在独立的文件系统目录中执行，完成后通过 git 合并回主分支。本文聚焦这个隔离机制的设计与实现。
>
> **重要**：v11 本身是单 Agent REPL——一个 Agent 使用 worktree 工具管理多个隔离目录。「多 Agent 并行」需要在外层启动多个 v11 实例（比如结合 v10 的多线程 Team 机制），v11 提供的是隔离基础设施，不负责并发调度。

---

<a id="part-1"></a>
## 第一部分：理论基础 🧠

<a id="conflict-problem"></a>
### 多 Agent 并行的文件冲突问题

想象一个真实的软件团队同时处理同一个文件：

```
没有隔离的并行（危险）:
  工作目录: /project/
    auth.py  ← 所有人都在改这个文件

  Agent A: read(auth.py) → 修改登录逻辑 → write(auth.py)
  Agent B: read(auth.py) → 添加 OAuth   → write(auth.py)

  结果: 后写入的覆盖先写入的，其中一个 Agent 的工作丢失
```

这个问题有几种「错误的解法」：

```
错误解法1：加锁
  → Agent A 持有 auth.py 的锁
  → Agent B 等待...
  → 并行变串行，失去了多 Agent 的意义

错误解法2：任务分配时避免冲突
  → 需要提前知道每个任务会修改哪些文件
  → Agent 的工作是动态的，无法提前预知
  → 过于保守，大量任务被迫串行

错误解法3：事后合并（无隔离）
  → Agent A 和 B 都修改了 auth.py
  → 合并时发现冲突，但已经无法还原各自的修改意图
  → 合并质量极差
```

<a id="git-insight"></a>
### git 分支给我们的启示

git 早就解决了这个问题，答案是**分支**：

```
git 的解法:
  main 分支: auth.py (原始版本)
      ↓
  ┌─────────────────────────────────┐
  │                                 │
  feature/login    feature/oauth
  auth.py (副本A)  auth.py (副本B)
      ↓                ↓
  修改登录逻辑      添加 OAuth
      ↓                ↓
  └─────────────────────────────────┘
              ↓
          git merge
              ↓
  main 分支: auth.py (合并版本)
```

关键洞察：**每个分支都有自己的文件副本，互不干扰，最后通过 merge 合并**。

但普通的 git 分支有一个问题：`git checkout` 会切换整个工作目录，同一时刻只能在一个分支上工作。

这就是 `git worktree` 的用武之地。

<a id="core-insight"></a>
### 核心洞察：隔离执行，统一协调

v11 的注释里有一句话：

```
Key insight: "Isolate by directory, coordinate by task ID."
```

翻译过来：**用目录隔离执行，用任务 ID 协调控制**。

```
v10 的工作模型（共享目录）:
  所有 Agent → 同一个工作目录 → 文件冲突

v11 的工作模型（隔离目录）:
  任务A → worktree/auth-refactor/ → 独立修改
  任务B → worktree/oauth-support/ → 独立修改
  任务C → worktree/test-coverage/ → 独立修改

  完成后 → git merge → 主分支
```

两个平面分离：
- **控制平面**：任务看板（`.tasks/`），记录任务状态、归属、绑定关系
- **执行平面**：Worktree 目录（`.worktrees/`），每个任务有独立的文件系统

---

<a id="part-2"></a>
## 第二部分：机制设计 ⚙️

<a id="worktree-concept"></a>
### Worktree：文件系统的「分身」

`git worktree` 是 git 的一个功能，允许同一个仓库在**多个目录**中同时检出不同的分支：

```bash
# 创建一个新的 worktree
git worktree add -b wt/auth-refactor .worktrees/auth-refactor HEAD

# 结果：
# .worktrees/auth-refactor/  ← 独立目录，有完整的文件副本
#   auth.py                  ← 与主目录的 auth.py 完全独立
#   ...
# 分支：wt/auth-refactor     ← 独立的 git 分支
```

这正是我们需要的：

```
主工作目录 /project/
  auth.py (main 分支)

.worktrees/auth-refactor/
  auth.py (wt/auth-refactor 分支) ← Agent A 在这里工作

.worktrees/oauth-support/
  auth.py (wt/oauth-support 分支) ← Agent B 在这里工作
```

三个 `auth.py`，互不干扰。Agent A 和 B 可以真正并行，不需要任何锁。

<a id="task-board"></a>
### 任务看板：控制平面

任务文件（`.tasks/task_12.json`）记录了任务与 worktree 的绑定关系：

```json
{
  "id": 12,
  "subject": "Implement auth refactor",
  "status": "in_progress",
  "owner": "coder_1",
  "worktree": "auth-refactor",
  "blockedBy": [],
  "created_at": 1234567890,
  "updated_at": 1234567891
}
```

Worktree 索引（`.worktrees/index.json`）记录了所有 worktree 的生命周期状态：

```json
{
  "worktrees": [
    {
      "name": "auth-refactor",
      "path": "/project/.worktrees/auth-refactor",
      "branch": "wt/auth-refactor",
      "task_id": 12,
      "status": "active",
      "created_at": 1234567890
    }
  ]
}
```

两个文件互相引用：任务知道自己绑定了哪个 worktree，worktree 知道自己服务于哪个任务。

<a id="when-to-use"></a>
### 何时触发 Worktree，何时不触发

Worktree **不是自动触发的**——它是 Agent 根据任务性质主动选择的工具。系统提示里给了明确的判断标准：

```
"For parallel or risky changes: create tasks, allocate worktree lanes,
 run commands in those lanes, then choose keep/remove for closeout."
```

**触发 Worktree 的场景**：

```
✅ 并行修改（最典型）:
  多个 Agent 同时处理同一代码库
  → 每个任务必须有独立的 worktree，否则文件互相覆盖

✅ 高风险修改:
  重构核心模块、修改数据库 schema、大规模重命名
  → 在隔离目录中实验，失败了直接 worktree_remove 丢弃
  → 主目录始终保持干净可运行状态

✅ 需要独立测试环境:
  修改依赖版本、更改配置文件
  → 在 worktree 中运行测试，不污染主目录的环境
```

**不触发 Worktree 的场景**：

```
❌ 只读操作:
  读取文件、查看日志、运行分析脚本
  → 不修改文件，不需要隔离

❌ 串行的简单修改:
  修改一个配置项、修复一个明确的 typo
  → 没有并行冲突风险，直接在主目录操作更简单

❌ 临时调试:
  加一行 print、查看变量值
  → 生命周期极短，worktree 的创建/删除开销不值得

❌ 跨任务有强依赖:
  任务 B 必须等任务 A 完成才能开始
  → 串行执行，不需要隔离
```

判断的核心问题只有两个：**会不会并行？会不会有风险？** 两个都否，直接操作主目录；任意一个是，创建 worktree。

<a id="lifecycle"></a>
### 生命周期：创建、执行、关闭

每个 worktree 经历完整的生命周期：

```
创建阶段:
  1. task_create → 在看板上创建任务
  2. worktree_create → 创建 git worktree + 绑定任务
     → git worktree add -b wt/{name} .worktrees/{name} HEAD
     → 更新 index.json
     → 更新 task.json (status: in_progress, worktree: name)

执行阶段:
  3. worktree_run → 在 worktree 目录中执行命令
     → 所有文件操作都在隔离目录中进行
  4. worktree_status → 查看 worktree 的 git 状态

关闭阶段（二选一）:
  5a. worktree_remove (complete_task=true)
      → git worktree remove
      → task.status = "completed"
      → index.json status = "removed"

  5b. worktree_keep
      → index.json status = "kept"
      → worktree 目录保留，等待手动合并
```

关闭阶段的「二选一」设计很关键：

```
worktree_remove: 直接删除
  适用于: 修改已经由 Agent 合并到主分支，或者任务失败需要丢弃

worktree_keep: 保留目录
  适用于: 需要人工审查后再合并，或者作为参考保留
```

<a id="eventbus"></a>
### EventBus：可观测性

多个 worktree 并行运行时，如何知道发生了什么？

v11 引入了 `EventBus`，将所有生命周期事件追加写入 `.worktrees/events.jsonl`：

```json
{"event": "worktree.create.before", "ts": 1234567890, "task": {"id": 12}, "worktree": {"name": "auth-refactor"}}
{"event": "worktree.create.after",  "ts": 1234567891, "task": {"id": 12}, "worktree": {"name": "auth-refactor", "status": "active"}}
{"event": "worktree.remove.before", "ts": 1234567900, "task": {"id": 12}, "worktree": {"name": "auth-refactor"}}
{"event": "task.completed",         "ts": 1234567901, "task": {"id": 12, "status": "completed"}, "worktree": {"name": "auth-refactor"}}
{"event": "worktree.remove.after",  "ts": 1234567902, "task": {"id": 12}, "worktree": {"name": "auth-refactor", "status": "removed"}}
```

JSONL 格式（每行一个 JSON）的优点：
- **追加写入**，不需要读取整个文件再写回
- **天然有序**，按时间顺序排列
- **并发安全**，多个 worktree 同时写入不会互相覆盖（文件追加是原子的）

通过 `worktree_events` 工具，Agent 可以随时查看最近的事件，了解整个系统的运行状态。

---

<a id="part-3"></a>
## 第三部分：代码实现 💻

<a id="worktree-impl"></a>
### WorktreeManager 实现

`WorktreeManager` 是核心类，封装了所有 worktree 操作：

```python
class WorktreeManager:
    def __init__(self, repo_root: Path, tasks: TaskManager, events: EventBus):
        self.repo_root = repo_root
        self.tasks = tasks
        self.events = events
        self.dir = repo_root / ".worktrees"
        self.index_path = self.dir / "index.json"
```

**创建 worktree**：

```python
def create(self, name: str, task_id: int = None, base_ref: str = "HEAD") -> str:
    self._validate_name(name)          # 名称只允许字母数字.-_
    if self._find(name):
        raise ValueError(f"Worktree '{name}' already exists")

    path = self.dir / name
    branch = f"wt/{name}"

    self.events.emit("worktree.create.before", ...)
    self._run_git(["worktree", "add", "-b", branch, str(path), base_ref])

    # 更新 index.json
    entry = {"name": name, "path": str(path), "branch": branch,
             "task_id": task_id, "status": "active", ...}
    idx = self._load_index()
    idx["worktrees"].append(entry)
    self._save_index(idx)

    # 绑定任务
    if task_id is not None:
        self.tasks.bind_worktree(task_id, name)

    self.events.emit("worktree.create.after", ...)
    return json.dumps(entry, indent=2)
```

名称验证是安全关键点：

```python
def _validate_name(self, name: str):
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,40}", name or ""):
        raise ValueError("Invalid worktree name. Use 1-40 chars: letters, numbers, ., _, -")
```

这防止了路径注入攻击——如果 `name` 包含 `../` 或空格，`git worktree add` 可能产生意外行为。

**在 worktree 中执行命令**：

```python
def run(self, name: str, command: str) -> str:
    dangerous = ["rm -rf /", "sudo", "shutdown", "reboot", "> /dev/"]
    if any(d in command for d in dangerous):
        return "Error: Dangerous command blocked"

    wt = self._find(name)
    path = Path(wt["path"])

    r = subprocess.run(command, shell=True, cwd=path, ...)
    return (r.stdout + r.stderr).strip()[:50000]
```

关键：`cwd=path` 确保命令在 worktree 目录中执行，而不是主工作目录。

<a id="task-binding"></a>
### TaskManager 与 Worktree 绑定

`TaskManager` 新增了两个方法处理绑定关系：

```python
def bind_worktree(self, task_id: int, worktree: str, owner: str = "") -> str:
    task = self._load(task_id)
    task["worktree"] = worktree
    if owner:
        task["owner"] = owner
    if task["status"] == "pending":
        task["status"] = "in_progress"   # 绑定时自动推进状态
    task["updated_at"] = time.time()
    self._save(task)
    return json.dumps(task, indent=2)

def unbind_worktree(self, task_id: int) -> str:
    task = self._load(task_id)
    task["worktree"] = ""               # 清空绑定
    task["updated_at"] = time.time()
    self._save(task)
    return json.dumps(task, indent=2)
```

`worktree_remove` 时的完整清理流程：

```python
def remove(self, name: str, force: bool = False, complete_task: bool = False) -> str:
    wt = self._find(name)

    # 1. 删除 git worktree
    self._run_git(["worktree", "remove", wt["path"]])

    # 2. 如果需要，完成关联任务
    if complete_task and wt.get("task_id") is not None:
        task_id = wt["task_id"]
        self.tasks.update(task_id, status="completed")
        self.tasks.unbind_worktree(task_id)
        self.events.emit("task.completed", ...)

    # 3. 更新 index.json 状态
    for item in idx["worktrees"]:
        if item["name"] == name:
            item["status"] = "removed"
            item["removed_at"] = time.time()
    self._save_index(idx)
```

`complete_task=True` 是一个便利参数：删除 worktree 的同时标记任务完成，一步完成收尾工作。

<a id="tool-design"></a>
### 工具接口设计

v11 提供了 11 个工具，分为三组：

```
基础工具（4个）:
  bash, read_file, write_file, edit_file
  → 在主工作目录操作

任务工具（5个）:
  task_create, task_list, task_get, task_update, task_bind_worktree
  → 管理控制平面（.tasks/）

Worktree 工具（6个）:
  worktree_create   → 创建 worktree + 可选绑定任务
  worktree_list     → 列出所有 worktree
  worktree_status   → 查看某个 worktree 的 git 状态
  worktree_run      → 在 worktree 中执行命令
  worktree_keep     → 标记保留（不删除）
  worktree_remove   → 删除 worktree + 可选完成任务
  worktree_events   → 查看生命周期事件
```

典型的 Agent 工作流：

```
1. task_create(subject="重构登录逻辑")
   → 创建任务 #12

2. worktree_create(name="auth-refactor", task_id=12)
   → 创建 .worktrees/auth-refactor/
   → 创建分支 wt/auth-refactor
   → 任务 #12 绑定到 auth-refactor

3. worktree_run(name="auth-refactor", command="cat auth.py")
   → 在隔离目录中读取文件

4. worktree_run(name="auth-refactor", command="python -m pytest tests/")
   → 在隔离目录中运行测试

5. worktree_status(name="auth-refactor")
   → 查看修改了哪些文件

6. worktree_run(name="auth-refactor", command="git add -A && git commit -m 'refactor login'")
   → 提交修改到 wt/auth-refactor 分支

7. bash(command="git merge --no-ff wt/auth-refactor -m 'Merge auth-refactor'")
   → Agent 自己执行 merge，将修改合并回主分支

8. worktree_remove(name="auth-refactor", complete_task=true)
   → 删除 worktree 目录
   → 任务 #12 标记为 completed
```

---

<a id="part-4"></a>
## 第四部分：扩展方向 🔭

<a id="merge-strategy"></a>
### 合并策略

v11 没有封装 `worktree_merge` 工具——merge 策略（`--no-ff` / `--squash` / `rebase`）、目标分支、commit message 都是任务相关的决策，Agent 直接用 `bash` 调 git 更灵活：

```bash
# Agent 在完成工作后自己执行
git merge --no-ff wt/auth-refactor -m "Merge auth-refactor"
git merge --squash wt/oauth-support  # 压缩成一个 commit
```

如果想封装成专用工具，可以在 `WorktreeManager` 里加：

```python
def merge(self, name: str, strategy: str = "--no-ff") -> str:
    wt = self._find(name)
    branch = wt["branch"]  # wt/auth-refactor
    try:
        return self._run_git(["merge", strategy, branch, "-m", f"Merge {branch}"])
    except RuntimeError as e:
        return f"Merge conflict: {e}"  # 冲突时 Agent 可以进一步处理
```

<a id="multi-level"></a>
### 多级隔离

当前实现是「任务级隔离」：每个任务一个 worktree。更细粒度的设计是「步骤级隔离」：

```
任务 #12: 重构登录逻辑
  ├─ 步骤1: 提取 LoginService → worktree/auth-step1/
  ├─ 步骤2: 添加单元测试    → worktree/auth-step2/
  └─ 步骤3: 更新 API 文档   → worktree/auth-step3/

每个步骤完成后合并到任务分支，任务完成后合并到主分支。
```

这种「树状合并」策略在大型重构中特别有用，可以精确控制每个步骤的影响范围。

---

<a id="faq"></a>
## 常见问题 FAQ

**Q: git worktree 和普通 git branch 有什么区别？**

A: 普通 `git checkout branch` 会切换整个工作目录，同一时刻只能在一个分支上工作。`git worktree` 允许同一个仓库在**多个目录**中同时检出不同分支，互不干扰。

```bash
# 普通分支：切换工作目录（破坏性）
git checkout feature/auth  # 整个目录变了

# worktree：新增目录（非破坏性）
git worktree add -b feature/auth .worktrees/auth HEAD
# 主目录不变，.worktrees/auth/ 是新的独立目录
```

**Q: worktree 目录和主目录共享 git 历史吗？**

A: 是的。所有 worktree 共享同一个 `.git` 目录（通过 `.git/worktrees/` 链接），所以它们共享完整的 git 历史、远程配置、标签等。只有工作目录和当前分支是独立的。

**Q: 如果 Agent 在 worktree 中崩溃了，怎么清理？**

A: worktree 目录会残留，但不影响主仓库。可以手动清理：

```bash
# 列出所有 worktree
git worktree list

# 删除残留的 worktree
git worktree remove --force .worktrees/auth-refactor

# 清理无效引用
git worktree prune
```

v11 的 `worktree_remove(force=True)` 对应 `git worktree remove --force`，可以强制删除有未提交修改的 worktree。

**Q: 多个 Agent 可以同时操作同一个 worktree 吗？**

A: 不建议。每个 worktree 应该只有一个 Agent 在操作。v11 通过任务绑定（`task.owner`）来保证这一点——一个任务只能被一个 Agent 认领，一个 worktree 只绑定一个任务。

**Q: worktree 的数量有限制吗？**

A: git 本身没有硬性限制，但每个 worktree 都是完整的文件系统副本，会占用磁盘空间。对于大型代码库，建议及时清理已完成的 worktree。

---

## 📝 结语

从 v10 到 v11，核心变化只有一个：**给每个任务一个独立的文件系统目录**。但这个改变背后的思想值得细品：

```
v10 的问题:
  多 Agent 共享同一个工作目录
  文件修改互相覆盖
  并行执行存在根本性冲突

v11 的解决:
  git worktree → 每个任务有独立的文件副本
  任务看板    → 控制平面，记录绑定关系
  EventBus    → 可观测性，追踪生命周期
  keep/remove → 灵活的关闭策略
```

更深层的洞察是：**并行的本质是隔离**。

不是「谁先抢到锁谁先改」，而是「每个人在自己的空间里改，改完再合并」。这正是 git 分支模型的精髓，也是 v11 把它引入 Agent 系统的原因。

```
系列能力演进:
  上下文压缩（v5）    → Agent 能长时间运行
  持久化任务（v6）    → Agent 能跨会话追踪任务
  后台执行（v7）      → Agent 能并行处理任务
  Agent Teams（v8）   → Agent 能组建团队协作
  Team Protocols（v9）→ Agent 团队能有序协调
  Autonomous（v10）   → Agent 能主动找工作、自主执行
  Worktree（v11）     → Agent 能安全并行、隔离执行
                        ↓
              真正的「并行自主 Agent 系统」
```

七个能力叠加，才能处理真实世界的复杂任务：长时间、多步骤、有依赖、可并行、需协作、能协调、会自主、**不冲突**。

**系列导航**：
- **上一篇**: [11 - 从「被动等待」到「主动找活」：Autonomous Agents 如何让 Teammate 真正自主]()
- **当前**:   [12 - 从「文件冲突」到「分身协作」：Worktree 如何让多 Agent 安全并行]()
- **下一篇**: 13 - 把所有能力组合起来：构建完整的自主 Agent 系统
