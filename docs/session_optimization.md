# Session 和 Context 优化说明

## 核心改进

参考 `s03_sessions.py` 的设计，实现了两层机制：

1. **SessionStore** - JSONL 持久化（写入时追加，读取时重放）
2. **ContextGuard** - 三阶段溢出重试（正常调用 → 截断工具结果 → 压缩历史）

```
用户输入
    ↓
load_session() → 从 JSONL 重建 messages[]
    ↓
guard_invoke() → 尝试 → 截断 → 压缩 → 抛异常
    ↓
save_turn() → 追加到 JSONL
    ↓
打印响应
```

### 1. SessionStore 类（统一管理）

**之前**：只有函数，分散管理
```python
# session.py
def save_session(agent_name, history)  # 覆盖写入
def load_session(agent_name, key)
```

**现在**：SessionStore 类，集中管理
```python
# session_store.py
class SessionStore:
    def create_session(key) -> str
    def save_turn(agent_name, user_msg, ai_msg, tool_calls)
    def save_tool_result(agent_name, tool_name, call_id, result)
    def save_compaction(agent_name, kind, before, after)
    def load_history(agent_name, key) -> list
    def list_sessions() -> list[dict]
    def delete_session(key) -> bool
```

### 2. sessions.json 索引

**新增元数据索引**：
```json
{
  "20260307_085736": {
    "session_key": "20260307_085736",
    "session_id": "a1b2c3d4e5f6",
    "created_at": "2026-03-07T08:57:36Z",
    "updated_at": "2026-03-07T09:15:22Z",
    "message_count": 15,
    "compaction_count": 2
  }
}
```

### 3. Append-only JSONL

**之前**：每次覆盖整个文件
```python
with open(path, "w") as f:  # 覆盖
    for msg in history:
        f.write(json.dumps(msg.model_dump()) + "\n")
```

**现在**：只追加新内容
```python
with open(path, "a") as f:  # 追加
    f.write(json.dumps(entry) + "\n")
```

### 4. 细粒度保存

**JSONL 格式**：
```jsonl
{"type":"session","id":"abc123","key":"20260307_085736","created":"2026-03-07T08:57:36Z"}
{"type":"user","content":"帮我分析代码","ts":"2026-03-07T08:57:40Z"}
{"type":"assistant","content":"好的，我来分析","tool_calls":[...],"ts":"2026-03-07T08:57:42Z"}
{"type":"tool_result","tool":"read_file","tool_call_id":"call_123","result":"...","ts":"2026-03-07T08:57:45Z"}
{"type":"compaction","kind":"auto","before_count":50,"after_count":20,"ts":"2026-03-07T09:00:00Z"}
```

### 5. 压缩事件记录

**集成到 agent.py**：
```python
# Layer 1: micro_compact
before_micro = len(history)
micro_compact(history)
if len(history) < before_micro:
    get_store().save_compaction("main", "micro", before_micro, len(history))

# Layer 2: auto_compact
if estimate_tokens(history, self.llm) > THRESHOLD:
    before_auto = len(history)
    new_history = auto_compact(history, self.llm)
    history.clear()
    history.extend(new_history)
    get_store().save_compaction("main", "auto", before_auto, len(history))

# Layer 3: manual compact
if was_compact_requested():
    before_manual = len(history)
    new_history = auto_compact(history, self.llm)
    history.clear()
    history.extend(new_history)
    get_store().save_compaction("main", "manual", before_manual, len(history))
```

## 使用方式

### 创建和切换会话

```python
from backend.app.session_store import get_store

store = get_store()

# 创建新会话
key = store.create_session()  # 自动生成时间戳 key
# 或指定 key
key = store.create_session("my-session-001")

# 切换会话
store.set_current_key(key)

# 列出所有会话
sessions = store.list_sessions()
for s in sessions:
    print(f"{s['session_key']}: {s['message_count']} msgs, {s['compaction_count']} compactions")

# 删除会话
store.delete_session("old-session")
```

### 保存对话

```python
# 保存一轮对话
store.save_turn(
    agent_name="main",
    user_msg="帮我分析代码",
    ai_msg="好的，我来分析",
    tool_calls=[{"name": "read_file", "args": {"path": "app.py"}}]
)

# 保存工具结果
store.save_tool_result(
    agent_name="main",
    tool_name="read_file",
    tool_call_id="call_123",
    result="文件内容..."
)

# 记录压缩事件
store.save_compaction(
    agent_name="main",
    kind="auto",  # micro/auto/manual
    before_count=50,
    after_count=20
)
```

### 加载历史

```python
# 加载当前会话
history = store.load_history("main")

# 加载指定会话
history = store.load_history("main", key="20260307_085736")
```

## 目录结构

```
.sessions/
├── sessions.json                    # 索引文件
├── 20260307_085736/                 # 会话目录
│   ├── main.jsonl                   # 主 agent transcript
│   ├── Explore.jsonl                # 子 agent transcript
│   ├── workspace/                   # 工作空间
│   ├── tasks/                       # 任务文件
│   └── team/                        # 团队状态
└── 20260307_091522/
    └── main.jsonl
```

## 优势总结

1. **持久化更可靠**：append-only，不会丢失历史
2. **元数据丰富**：创建时间、消息数、压缩次数
3. **多会话支持**：可以切换和管理多个会话
4. **压缩可追溯**：记录每次压缩事件
5. **细粒度保存**：每个操作都被记录
6. **向后兼容**：保留了原有的函数接口
7. **上下文保护**：三阶段重试机制防止溢出

## ContextGuard - 上下文溢出保护

### 三阶段重试机制

```python
from backend.app.agent.context_guard import ContextGuard

guard = ContextGuard(max_tokens=180000)

# 自动处理溢出
response = guard.guard_invoke(llm, messages)
```

**阶段 0**：正常调用
```python
response = llm.invoke(messages)
```

**阶段 1**：截断过大的工具结果（保留前 30%）
```python
# 在换行边界处截断
truncated = guard.truncate_tool_result(result, max_fraction=0.3)
# "文件内容...\n\n[... truncated (10000 chars total, showing first 3000) ...]"
```

**阶段 2**：压缩历史（LLM 摘要前 50%）
```python
# 压缩前 50% 的消息为摘要
# 保留最后 20% 的消息不变
compacted = guard.compact_history(messages, llm)
```

**阶段 3**：仍然溢出则抛出异常

### Token 估算

```python
# 估算单个文本
tokens = guard.estimate_tokens("Hello world")  # ~3 tokens

# 估算整个消息历史
total_tokens = guard.estimate_messages_tokens(messages)
print(f"Context usage: {total_tokens} / {guard.max_tokens}")
```

### 压缩策略

```python
# 假设有 20 条消息
messages = [msg1, msg2, ..., msg20]

# 压缩前 50% (10 条)
old_messages = messages[:10]

# 保留后 20% (4 条) 不变
keep_count = max(4, int(20 * 0.2))  # 4

# 实际压缩 10 条，保留 10 条
compress_count = min(10, 20 - 4)  # 10

# 结果：
# [摘要] + [msg11, msg12, ..., msg20]
```

### 集成到 Agent

```python
from backend.app.agent.context_guard import ContextGuard

class AgentService:
    def __init__(self):
        self.guard = ContextGuard(max_tokens=180000)

    async def run(self, prompt: str, history: list) -> str:
        # 检查上下文使用率
        tokens = self.guard.estimate_messages_tokens(history)
        if tokens > self.guard.max_tokens * 0.8:
            print(f"⚠️ Context usage: {tokens}/{self.guard.max_tokens} (80%+)")

        # 使用 guard 保护调用
        try:
            response = self.guard.guard_invoke(self.llm, history)
        except Exception as e:
            print(f"❌ Context overflow: {e}")
            # 强制压缩
            history = self.guard.compact_history(history, self.llm)
            response = self.llm.invoke(history)

        return response.content
```

## 与 s03_sessions.py 的对应

| s03_sessions.py | 后端项目 | 说明 |
|----------------|---------|------|
| **SessionStore** | **backend/app/analysis/session_store.py** | |
| SessionStore | SessionStore | 核心类 |
| sessions.json | sessions.json | 索引文件 |
| {session_id}.jsonl | {key}/*.jsonl | JSONL 文件 |
| create_session() | create_session() | 创建会话 |
| load_session() | load_history() | 加载历史 |
| save_turn() | save_turn() | 保存对话 |
| save_tool_result() | save_tool_result() | 保存工具结果 |
| - | save_compaction() | 记录压缩（新增） |
| list_sessions() | list_sessions() | 列出会话 |
| **ContextGuard** | **backend/app/agent/context_guard.py** | |
| ContextGuard | ContextGuard | 上下文保护类 |
| estimate_tokens() | estimate_tokens() | Token 估算 |
| truncate_tool_result() | truncate_tool_result() | 截断工具结果 |
| compact_history() | compact_history() | 压缩历史 |
| guard_api_call() | guard_invoke() | 三阶段重试 |

## 完整工作流程

### 1. 启动时恢复会话

```python
from backend.app.analysis.session_store import get_store

store = get_store()

# 恢复最近的会话
sessions = store.list_sessions()
if sessions:
    latest = sessions[0]
    key = latest["session_key"]
    history = store.load_history("main", key)
    print(f"恢复会话: {key} ({len(history)} 条消息)")
else:
    # 创建新会话
    key = store.create_session()
    history = []
    print(f"创建新会话: {key}")
```

### 2. 对话循环

```python
from backend.app.agent.context_guard import ContextGuard

guard = ContextGuard(max_tokens=180000)

while True:
    user_input = input("You > ")

    # 添加用户消息
    history.append(HumanMessage(content=user_input))

    # 使用 guard 保护调用
    try:
        response = guard.guard_invoke(llm, history)
    except Exception as e:
        print(f"错误: {e}")
        break

    # 添加 AI 回复
    history.append(AIMessage(content=response.content))

    # 保存到 transcript
    store.save_turn("main", user_input, response.content)

    print(f"Assistant: {response.content}")
```

### 3. 工具调用

```python
# AI 调用工具
if hasattr(response, "tool_calls") and response.tool_calls:
    for tc in response.tool_calls:
        # 执行工具
        result = execute_tool(tc["name"], tc["args"])

        # 保存工具结果
        store.save_tool_result("main", tc["name"], tc["id"], result)

        # 添加到历史
        history.append(ToolMessage(
            content=result,
            tool_call_id=tc["id"]
        ))
```

### 4. 压缩事件

```python
# 自动压缩
if guard.estimate_messages_tokens(history) > 50000:
    before = len(history)
    history = guard.compact_history(history, llm)
    after = len(history)

    # 记录压缩
    store.save_compaction("main", "auto", before, after)
    print(f"自动压缩: {before} → {after} 条消息")
```

### 5. 会话管理命令

```python
# /new - 创建新会话
if user_input == "/new":
    key = store.create_session()
    history = []
    print(f"创建新会话: {key}")

# /list - 列出所有会话
elif user_input == "/list":
    sessions = store.list_sessions()
    for s in sessions:
        print(f"{s['session_key']}: {s['message_count']} msgs, "
              f"{s['compaction_count']} compactions")

# /switch <key> - 切换会话
elif user_input.startswith("/switch"):
    key = user_input.split()[1]
    history = store.load_history("main", key)
    store.set_current_key(key)
    print(f"切换到会话: {key} ({len(history)} 条消息)")

# /context - 查看上下文使用率
elif user_input == "/context":
    tokens = guard.estimate_messages_tokens(history)
    pct = (tokens / guard.max_tokens) * 100
    print(f"Context: {tokens:,} / {guard.max_tokens:,} ({pct:.1f}%)")
    print(f"Messages: {len(history)}")

# /compact - 手动压缩
elif user_input == "/compact":
    before = len(history)
    history = guard.compact_history(history, llm)
    after = len(history)
    store.save_compaction("main", "manual", before, after)
    print(f"手动压缩: {before} → {after} 条消息")
```

## 后续优化方向

1. **会话恢复**：启动时自动恢复上次会话 ✅ 已实现
2. **会话归档**：自动归档旧会话
3. **压缩策略优化**：根据压缩历史调整阈值
4. **多 agent 协作**：更好地管理子 agent 的 transcript
5. **智能压缩**：根据消息重要性选择性压缩
6. **增量保存**：实时追加而非批量保存 ✅ 已实现
7. **上下文预警**：接近阈值时提前警告
8. **压缩质量评估**：评估摘要是否保留了关键信息

## 关键设计决策

### 为什么使用 JSONL 而不是 JSON？

1. **追加友好**：只需 append，不需要读取整个文件
2. **容错性好**：单行损坏不影响其他行
3. **流式处理**：可以逐行读取，内存友好
4. **易于调试**：每行独立，方便查看和编辑

### 为什么分三阶段重试？

1. **渐进式处理**：从最小代价开始
2. **保留信息**：尽可能保留完整上下文
3. **用户体验**：避免突然失败，给出明确反馈
4. **可观测性**：每个阶段都有日志

### 为什么压缩前 50%？

1. **平衡性**：既保留足够上下文，又释放足够空间
2. **经验值**：s03_sessions.py 验证过的比例
3. **保留最近**：最近的对话最重要
4. **可调整**：可以根据实际情况调整比例

## 实际效果

### 压缩效果示例

**压缩前**（50 条消息，~150,000 tokens）：
```
[user]: 帮我分析这个文件
[assistant]: 好的，我来读取文件
[tool_use]: read_file(path="app.py")
[tool_result]: [10000 行代码...]
[user]: 这个函数是做什么的？
[assistant]: 这个函数负责...
...（46 条消息）
```

**压缩后**（27 条消息，~80,000 tokens）：
```
[user]: [之前对话摘要]
用户请求分析 app.py 文件，我读取了文件内容并解释了主要函数的功能。
讨论了代码结构、性能优化建议和潜在的 bug。
[assistant]: 明白，我已了解之前的对话上下文。
...（最近 25 条消息保持不变）
```

**节省**：23 条消息，~70,000 tokens（46.7%）

### 截断效果示例

**截断前**（工具结果 100,000 字符）：
```python
result = read_file("large_file.txt")
# 100,000 字符的文件内容
```

**截断后**（保留前 30%）：
```python
result = """
[文件前 30,000 字符...]

[... truncated (100000 chars total, showing first 30000) ...]
"""
```

**节省**：70,000 字符，~17,500 tokens

## 监控和调试

### 查看会话统计

```python
from backend.app.analysis.session_store import get_store

store = get_store()
sessions = store.list_sessions()

for s in sessions:
    print(f"""
会话: {s['session_key']}
创建: {s['created_at']}
更新: {s['updated_at']}
消息数: {s['message_count']}
压缩次数: {s['compaction_count']}
    """)
```

### 查看 JSONL 内容

```bash
# 查看会话文件
cat .sessions/20260307_085736/main.jsonl

# 统计消息类型
grep '"type"' .sessions/20260307_085736/main.jsonl | sort | uniq -c

# 查看压缩事件
grep '"type":"compaction"' .sessions/20260307_085736/main.jsonl
```

### 分析上下文使用

```python
from backend.app.agent.context_guard import ContextGuard

guard = ContextGuard()
tokens = guard.estimate_messages_tokens(history)

print(f"总 tokens: {tokens:,}")
print(f"使用率: {tokens / guard.max_tokens * 100:.1f}%")
print(f"剩余空间: {guard.max_tokens - tokens:,} tokens")
```

## 总结

通过参考 `s03_sessions.py` 的设计，我们实现了：

✅ **SessionStore** - 可靠的会话持久化
- JSONL 追加式写入
- 元数据索引
- 多会话管理

✅ **ContextGuard** - 智能的上下文保护
- 三阶段重试
- 工具结果截断
- LLM 摘要压缩

✅ **完整集成** - 无缝融入现有系统
- 向后兼容
- 细粒度保存
- 压缩可追溯

这套机制让 agent 能够：
1. 长期运行不丢失上下文
2. 自动处理上下文溢出
3. 保留关键信息
4. 提供清晰的可观测性
