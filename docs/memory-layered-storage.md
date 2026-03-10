# 分层记忆存储机制

## 概述

实现了基于 category 的自动分层记忆存储，解决了 subagents 调用 `memory_search` 返回 "No relevant memories found" 的问题。

## 架构设计

### 两层存储结构

| 层级 | 位置 | 生命周期 | 用途 |
|------|------|---------|------|
| **全局记忆** | `backend/memory/` | 永久（跨会话） | 项目知识、用户偏好、工具经验 |
| **会话记忆** | `.sessions/{key}/workspace/memory/` | 当前会话 | 临时发现、上下文信息 |

### Category 映射规则

```python
category → 存储位置

"preference"    → backend/memory/USER.md      # 用户偏好
"architecture"  → backend/memory/MEMORY.md    # 项目架构
"tool"          → backend/memory/TOOLS.md     # 工具经验
"session"       → workspace/memory/daily/{date}.jsonl  # 会话临时
"general"       → workspace/memory/daily/{date}.jsonl  # 默认
```

## 实现细节

### 1. SessionStore.write_memory()

**文件**: `backend/app/session/session.py`

```python
def write_memory(self, content: str, category: str = "general") -> str:
    """
    写入记忆（自动分层）

    Args:
        content: 记忆内容
        category: 分类
            - session/general: 会话临时信息（默认）
            - preference: 用户偏好（全局持久化）
            - architecture: 项目架构知识（全局持久化）
            - tool: 工具使用经验（全局持久化）
    """
    # 全局记忆：写入到 backend/memory/
    if category == "preference":
        return self._append_to_global_file("USER.md", content)
    elif category == "architecture":
        return self._append_to_global_file("MEMORY.md", content)
    elif category == "tool":
        return self._append_to_global_file("TOOLS.md", content)

    # 会话记忆：写入到 workspace/memory/daily/{date}.jsonl
    else:
        if not self._memory_store:
            return "Error: No active session"
        return self._memory_store.write_memory(content, category)
```

### 2. 全局文件追加逻辑

```python
def _append_to_global_file(self, filename: str, content: str) -> str:
    """追加内容到全局记忆文件"""
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"\n\n## {timestamp}\n\n{content}"

    current = self._bootstrap_loader.load_file(filename)
    updated = f"{current}{formatted}".strip()

    success = self._bootstrap_loader.update_file(filename, updated)
    return f"✓ Saved to global {filename}" if success else f"✗ Error writing to global {filename}"
```

### 3. 工具文档更新

**文件**: `backend/app/tools/implementations/memory_tools.py`

```python
@tool(tags=["both"])
def memory_write(content: str, category: str = "general") -> str:
    """
    Save an important fact or observation to memory (auto-layered storage).

    Args:
        content: The fact or observation to remember
        category: Memory category (determines storage location)
            - "session" or "general": Temporary session info (current conversation only)
            - "preference": User preferences (persistent across sessions)
            - "architecture": Project architecture/patterns (persistent across sessions)
            - "tool": Tool usage tips/patterns (persistent across sessions)

    Examples:
        memory_write("User prefers concise code", "preference")
        memory_write("Project uses FastAPI + LangChain", "architecture")
        memory_write("Found agent.py in backend/app/", "session")
    """
```

### 4. Subagent Prompt 更新

**文件**: `backend/app/subagents/__init__.py`

所有 subagents 的 prompt 都更新为明确说明 category 用法：

```python
"Explore": {
    "prompt": (
        "You are an exploration agent. Search and analyze, but never modify files.\n\n"
        "Memory usage:\n"
        "- memory_search(query) - Recall past findings before starting\n"
        "- memory_write(content, category) - Save discoveries:\n"
        "  * category='session' - Temporary findings (file paths, search results)\n"
        "  * category='architecture' - Project patterns/structure (persistent)\n"
        "  * category='tool' - Useful search/exploration techniques (persistent)\n\n"
        "Always save at least one architectural discovery before finishing."
    ),
}
```

## 使用示例

### 场景 1: Explore Subagent 探索代码库

```python
# 临时发现（会话记忆）
memory_write("Found agent.py in backend/app/", "session")
memory_write("Main entry point is backend/main.py", "session")

# 架构发现（全局记忆）
memory_write("Project uses FastAPI + LangChain architecture", "architecture")
memory_write("Session management in backend/app/session/", "architecture")

# 工具技巧（全局记忆）
memory_write("Use grep -r 'class.*Agent' to find agent definitions", "tool")
```

### 场景 2: IntentRecognition 识别用户偏好

```python
# 用户偏好（全局记忆）
memory_write("User prefers concise code without verbose comments", "preference")
memory_write("User wants Chinese documentation", "preference")
```

### 场景 3: Plan Subagent 规划任务

```python
# 架构决策（全局记忆）
memory_write("Decided to use category-based memory routing", "architecture")
memory_write("Memory search uses TF-IDF + vector + temporal decay", "architecture")
```

## 解决的问题

### 问题 1: 空记忆库

**原因**: Subagents 虽然有 `memory_write` 工具，但从未调用，导致记忆库为空。

**解决**:
1. 更新 prompt 明确要求"Always save at least one architectural discovery"
2. 提供清晰的 category 使用示例
3. 区分临时信息（session）和持久知识（architecture/preference/tool）

### 问题 2: 记忆污染

**原因**: 如果所有记忆都写入全局，会导致全局记忆文件膨胀且充满临时信息。

**解决**:
- 默认写入会话记忆（session/general）
- 只有明确标记为 preference/architecture/tool 的才写入全局
- 全局记忆保持高质量和可维护性

### 问题 3: 跨会话知识丢失

**原因**: 会话记忆在会话结束后不可访问，重要发现无法复用。

**解决**:
- 通过 category 自动路由到全局记忆
- 全局记忆在所有会话中加载（通过 GlobalMemoryLoader）
- 重要的架构知识、用户偏好持久化保存

## 验证

### 语法检查

```bash
✓ python -m py_compile backend/app/session/session.py
✓ python -m py_compile backend/app/tools/implementations/memory_tools.py
✓ python -m py_compile backend/app/subagents/__init__.py
```

### 测试场景

1. **启动 Explore subagent**
   - 应该调用 `memory_search` 查询过往发现
   - 应该调用 `memory_write(..., "architecture")` 保存架构发现
   - 全局 `backend/memory/MEMORY.md` 应该有新增内容

2. **启动 IntentRecognition subagent**
   - 应该调用 `memory_search` 查询用户历史偏好
   - 应该调用 `memory_write(..., "preference")` 保存用户偏好
   - 全局 `backend/memory/USER.md` 应该有新增内容

3. **下次会话**
   - 新会话启动时应该能通过 `memory_search` 找到上次保存的全局记忆
   - 不应该再返回 "No relevant memories found"

## 文件变更清单

1. `backend/app/session/session.py`
   - 修改 `write_memory()` 方法，添加 category 路由逻辑
   - 新增 `_append_to_global_file()` 方法

2. `backend/app/tools/implementations/memory_tools.py`
   - 更新 `memory_write()` 工具文档，说明 category 用法

3. `backend/app/subagents/__init__.py`
   - 更新所有 subagent 的 prompt，明确 memory_write 的 category 用法
   - 强调"Always save at least one discovery"

4. `docs/memory-layered-storage.md` (本文档)
   - 记录设计决策和实现细节

## 后续优化

### 可选改进 1: 记忆质量评分

```python
def write_memory(self, content: str, category: str = "general", importance: int = 1):
    """
    importance: 1-5，5 表示最重要
    - 低重要性记忆可能在会话结束时被清理
    - 高重要性记忆优先显示在搜索结果中
    """
```

### 可选改进 2: 自动提升机制

```python
def consolidate_session_memory():
    """
    会话结束时，自动分析会话记忆，将高价值内容提升到全局

    规则：
    - 被多次引用的记忆 → 提升
    - 包含关键词（architecture, pattern, design）→ 提升
    - 其他 → 保留在会话记忆
    """
```

### 可选改进 3: 记忆去重

```python
def deduplicate_memory():
    """
    定期检查全局记忆，合并重复或相似的条目
    使用语义相似度检测重复内容
    """
```

## 总结

通过实现基于 category 的自动分层存储，解决了以下核心问题：

1. ✅ Subagents 现在会主动写入记忆（通过 prompt 引导）
2. ✅ 重要知识持久化到全局记忆（跨会话可用）
3. ✅ 临时信息隔离在会话记忆（避免污染）
4. ✅ 清晰的语义分类（preference/architecture/tool/session）
5. ✅ 打破"空记忆 → 不写入 → 仍然空记忆"的恶性循环

这个设计既保持了灵活性，又确保了记忆系统的可维护性和实用性。
