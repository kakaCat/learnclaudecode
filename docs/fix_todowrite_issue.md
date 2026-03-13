# TodoWrite 问题修复报告

## 问题分析

### 原始问题

从 `.sessions/20260312_161811/trace.jsonl` 日志中发现两个主要问题：

1. **递归限制错误**（主要原因）
   ```
   Recursion limit of 50 reached without hitting a stop condition.
   ```
   - Subagent 在执行任务时达到 LangGraph 的递归限制（50次）
   - 执行时长：177秒后失败
   - 原因：Agent 在使用 CDP 浏览器工具时陷入循环，无法成功获取数据

2. **TodoWrite 冲突错误**
   ```
   Error: Only one task can be in_progress at a time
   ```
   - Agent 尝试同时标记 2 个任务为 `in_progress` 状态
   - 违反了 TodoWrite 的串行执行规则

### 根本原因

**为什么使用了 TodoWrite 而不是 Task 工具？**

- **TodoWrite**（临时任务列表）：
  - 用于当前会话的临时任务跟踪
  - 存储在内存中，会话结束后消失
  - **设计原则：串行执行，只能1个 in_progress 任务**
  - 适合：简单、顺序的任务流程

- **Task 工具**（持久化任务）：
  - 用于跨会话的持久化任务管理
  - 存储在 `.tasks/` 目录的 JSON 文件中
  - **支持多个任务同时 in_progress（并行执行）**
  - 支持任务依赖关系
  - 适合：复杂项目、并行任务

**Agent 的错误行为**：
```json
{'content': '查询北京到武汉交通信息', 'status': 'in_progress'},
{'content': '收集武汉旅游景点信息', 'status': 'in_progress'}  // ❌ 第二个 in_progress
```

Agent 认为可以并行处理多个子任务，但错误地使用了 TodoWrite（只支持串行）。

## 解决方案

### 核心策略：保持 TodoWrite 串行，引导使用 Task 工具

**设计理念**：
- TodoWrite = 串行执行，简单任务
- Task 工具 = 并行执行，复杂任务

### 1. 保持 TodoWrite 的串行限制（不修改）

**文件**: `backend/app/todos/manager.py`

```python
# 保持原有限制
if in_progress_count > 1:
    raise ValueError("Only one task can be in_progress at a time")
```

**理由**：
- TodoWrite 设计用于跟踪 Agent 当前正在做什么
- 一个 Agent 在同一时刻只能专注于一件事
- 串行执行更清晰，避免状态混乱

### 2. 优化工具描述，明确串行 vs 并行

#### TodoWrite 工具描述

**修改文件**: `backend/app/tools/implementations/agent/todo_tool.py`

```python
def TodoWrite(items: list) -> str:
    """更新当前会话的临时任务列表（会话结束后消失）。每个条目需要：content（内容字符串）、status（pending|in_progress|completed）、activeForm（进行时，如"正在读取文件"）。同一时间只能有一个 in_progress 条目（串行执行），最多 20 条。

    使用场景：
    - 单个会话内的临时任务跟踪
    - 简单的顺序任务流程（串行执行）
    - 不需要持久化的任务

    如果需要：
    - 跨会话持久化任务
    - 并行处理多个任务
    - 任务依赖关系管理
    请使用 task_create/task_update/task_list 工具。
    """
```

**关键变更**：
- 明确说明"串行执行"
- 强调"只能有一个 in_progress"
- 引导并行场景使用 Task 工具

#### Task 工具描述

**修改文件**: `backend/app/tools/implementations/agent/task_tool.py`

```python
def task_create(subject: str, description: str = "") -> str:
    """创建持久化任务，跨会话保留。以 JSON 格式存储在 .tasks/ 目录中。

    使用场景：
    - 需要跨会话持久化的任务
    - 复杂项目的任务管理
    - 需要并行处理多个任务
    - 需要任务依赖关系管理

    如果只是当前会话的临时任务跟踪，使用 TodoWrite 更简单。
    """

def task_update(task_id: int, status: str = None,
                addBlockedBy: list = None, addBlocks: list = None) -> str:
    """更新持久化任务的状态（pending|in_progress|completed）或依赖关系。

    支持多个任务同时为 in_progress 状态，适合并行任务场景。
    """
```

### 3. 更新系统 Prompt

**修改文件**: `backend/memory/TOOLS.md`

添加了明确的工具选择指南：

```markdown
## 工作空间

- **临时文件**: workspace_write/workspace_read - 存储中间结果
- **临时任务**: TodoWrite - 当前会话的任务跟踪（串行执行，只能1个 in_progress）
- **持久任务**: task_create/task_update - 跨会话任务管理（支持并行执行）
- **团队协作**: spawn_teammate/send_message - 多 agent 协作

## 执行规则

- **计划和进度跟踪（强制规则）**：
  * **简单任务**（≤3步骤，预计≤3轮对话，串行执行）：使用 TodoWrite 跟踪
    - TodoWrite 限制：只能1个任务为 in_progress 状态（串行执行）
    - 适合：单会话内的临时任务，不需要持久化，顺序执行
  * **复杂任务**（>3步骤，或预计>3轮对话，或需要并行处理）：**必须使用 task 系统**
    - task 系统优势：支持多任务并行 in_progress，跨会话持久化
  * **判断标准**：
    - 需要并行处理多个子任务？→ 必须使用 task 系统
    - 需要跨会话保留？→ 使用 task 系统
    - 简单顺序流程？→ 使用 TodoWrite
    - 不确定？→ 默认使用 task 系统（更安全）
```

## 工具对比

| 特性 | TodoWrite | Task 工具 |
|------|-----------|-----------|
| 执行方式 | ✅ 串行（1个 in_progress） | ✅ 并行（无限制） |
| 持久化 | ❌ 会话结束消失 | ✅ 跨会话保留 |
| 任务依赖 | ❌ 不支持 | ✅ 支持 |
| 适用场景 | 简单、临时、顺序任务 | 复杂、长期、并行任务 |

## 使用建议

### 使用 TodoWrite 的场景
- 简单的3步以内任务
- 顺序执行，一步完成再做下一步
- 当前会话内完成，不需要保留

### 必须使用 Task 工具的场景
- 需要并行处理多个子任务
- 任务需要跨会话保留
- 复杂项目管理
- 需要任务依赖关系

## 修改文件清单

1. `backend/app/tools/implementations/agent/todo_tool.py` - 优化工具描述，强调串行
2. `backend/app/tools/implementations/agent/task_tool.py` - 优化工具描述，强调并行
3. `backend/memory/TOOLS.md` - 更新系统 prompt 指南
4. `docs/fix_todowrite_issue.md` - 修复报告

## 预期效果

1. **保持 TodoWrite 设计原则**：串行执行，简单清晰
2. **引导正确工具选择**：通过工具描述和系统 prompt 引导 Agent 在并行场景使用 Task 工具
3. **清晰的职责划分**：TodoWrite = 串行，Task = 并行
4. **向后兼容**：现有使用 TodoWrite 的代码仍然正常工作

## 注意事项

1. **递归限制问题**仍需单独解决（增加 `recursion_limit` 配置）
2. **CDP 浏览器工具**的循环问题需要优化停止条件
3. Agent 需要学习在并行场景下选择 Task 工具而非 TodoWrite

## 日期

2026-03-13
