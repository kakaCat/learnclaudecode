# Agent 优化方案总结

## 问题诊断

**原始问题**：武汉旅游计划任务，Agent 在 Turn 10 说要创建网页，但没有实际创建，也没有告知用户交付物路径。

**根本原因**：
1. ❌ 工具选择错误：使用 TodoWrite 而非 task 系统（复杂任务应该用 task）
2. ❌ 短期记忆丢失：Turn 10 时"忘记"调用 workspace_write
3. ❌ 说了但没做：只输出文字，没有工具调用
4. ❌ 缺少交付物确认：没有告知用户文件路径

## 优化方案

### 1. 任务跟踪机制强化

**修改位置**：`backend/memory/TOOLS.md` 第78-80行

**核心改进**：
- 明确判断标准：>3步骤或>3轮对话 → 必须用 task 系统
- 默认策略：不确定时使用 task（更安全）
- 定期检查：每3-5轮调用 task_list

### 2. 先做后说原则

**修改位置**：`backend/memory/TOOLS.md` 第83-88行

**核心改进**：
- 禁止只说不做
- 强制告知交付物路径
- 添加状态检查机制

### 3. 状态持久化

**新增机制**：
```python
# 每完成关键步骤
workspace_write("_task_state.json", {
    "completed": ["步骤1", "步骤2"],
    "next_action": "创建 HTML 文件",
    "tool": "workspace_write",
    "args": {"path": "xxx.html"}
})

# 下一轮开始前
state = workspace_read("_task_state.json")
# 明确知道下一步该做什么
```

### 4. 检查清单

**新增文件**：`backend/memory/TASK_CHECKLIST.md`

包含：
- 任务开始前检查
- 执行过程中检查
- 任务完成后检查
- 常见错误避免

## 预期效果

✅ 复杂任务自动使用 task 系统，避免上下文丢失
✅ 每个关键步骤保存状态到 workspace
✅ 禁止"说了但没做"
✅ 强制告知用户交付物路径
✅ 长对话中定期检查任务状态

## 验证方法

重新执行相同任务，观察：
1. 是否在 Turn 1-2 调用 Task(subagent_type="Plan")
2. 是否定期 task_list 检查状态
3. Turn 10 是否实际调用 workspace_write
4. 是否告知用户文件路径

## 文件清单

修改的文件：
- ✅ `backend/memory/TOOLS.md` - 任务跟踪规则强化

新增的文件：
- ✅ `backend/memory/TASK_CHECKLIST.md` - 执行检查清单
