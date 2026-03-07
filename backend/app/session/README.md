# Session 包

统一的会话存储管理模块，合并了原 `session.py` 和 `analysis/session_store.py` 的功能。

## 目录结构

```
backend/app/session/
├── __init__.py       # 统一导出接口
├── store.py          # SessionStore 核心类
├── constants.py      # 常量配置
└── README.md         # 本文档
```

## 使用方式

### 推荐方式：使用 SessionStore 类

```python
from backend.app.session import get_store

store = get_store()

# 创建会话
key = store.create_session()
store.set_current_key(key)

# 细粒度保存
store.save_turn("main", user_msg="Hello", ai_msg="Hi!")
store.save_tool_result("main", "bash", "call_123", "output")
store.save_compaction("main", "auto", before_count=100, after_count=10)

# 加载历史
history = store.load_history("main")

# 会话管理
sessions = store.list_sessions()
store.delete_session(key)
```

### 向后兼容方式：使用函数接口

```python
from backend.app.session import (
    new_session_key,
    set_session_key,
    get_session_key,
    get_session_dir,
    get_workspace_dir,
    get_tasks_dir,
    get_team_dir,
    get_board_dir,
    save_session,
    load_session,
    list_sessions,
)

# 创建会话
key = new_session_key()

# 保存完整历史（旧方式）
save_session("main", history)

# 加载历史
history = load_session("main", key)

# 获取目录
session_dir = get_session_dir()
workspace_dir = get_workspace_dir()
tasks_dir = get_tasks_dir()
team_dir = get_team_dir()
board_dir = get_board_dir()
```

## 核心功能

### 1. 会话创建和切换

- `create_session(key=None)` - 创建新会话，自动创建标准目录结构
- `set_current_key(key)` - 切换当前会话
- `get_current_key()` - 获取当前会话 key

### 2. 统一目录管理

Session 包负责创建和管理所有会话子目录：

- `get_session_dir(key)` - 获取会话根目录
- `get_workspace_dir(key)` - 获取 workspace 目录
- `get_tasks_dir(key)` - 获取 tasks 目录
- `get_team_dir(key)` - 获取 team 目录
- `get_board_dir(key)` - 获取 board 目录

所有目录在会话创建时自动生成，各模块无需手动创建。

### 3. 文件路径辅助函数（推荐）

Session 包提供文件路径辅助函数，统一管理所有会话文件的路径：

- `get_task_file_path(task_id, slug)` - 获取 task 文件路径
- `get_board_task_path(task_id)` - 获取 board task 文件路径
- `get_team_config_path()` - 获取 team 配置文件路径
- `get_inbox_path(agent_name)` - 获取 inbox 消息文件路径
- `get_agent_transcript_path(agent_name)` - 获取 agent transcript 文件路径

使用示例：
```python
from backend.app.session import get_task_file_path, get_inbox_path

# 获取任务文件路径
task_path = get_task_file_path(1, "test-task")
# 返回: .sessions/{key}/tasks/task_1_test-task.json

# 获取 inbox 路径
inbox_path = get_inbox_path("agent1")
# 返回: .sessions/{key}/team/inbox/agent1.jsonl
```

### 4. 细粒度保存（推荐）

- `save_turn(agent_name, user_msg, ai_msg, tool_calls)` - 保存一轮对话
- `save_tool_result(agent_name, tool_name, tool_call_id, result)` - 保存工具结果
- `save_compaction(agent_name, kind, before_count, after_count)` - 记录压缩事件

### 5. 历史记录加载

- `load_history(agent_name, key)` - 从 JSONL 加载历史
- `save_full_history(agent_name, history, key)` - 保存完整历史（向后兼容）

### 6. 会话管理

- `list_sessions()` - 列出所有会话
- `delete_session(key)` - 删除会话
- `get_session_dir(key)` - 获取会话目录

## 数据存储格式

### 目录结构

```
.sessions/
├── sessions.json                    # 会话索引（元数据）
└── {session_key}/
    ├── main.jsonl                   # 主 agent 的 transcript
    ├── Explore.jsonl                # 子 agent 的 transcript
    ├── transcript.jsonl             # 压缩时的完整记录
    ├── workspace/                   # 工作空间（自动创建）
    ├── tasks/                       # 任务文件（自动创建）
    ├── team/                        # 团队配置（自动创建）
    │   └── inbox/                   # 消息收件箱（自动创建）
    └── board/                       # 任务看板（自动创建）
```

### sessions.json 格式

```json
{
  "20260307_135945": {
    "session_key": "20260307_135945",
    "session_id": "a1b2c3d4e5f6",
    "created_at": "2026-03-07T13:59:45.123456+00:00",
    "updated_at": "2026-03-07T14:05:30.789012+00:00",
    "message_count": 15,
    "compaction_count": 2
  }
}
```

### JSONL transcript 格式

每个 agent 的 `.jsonl` 文件包含：

```jsonl
{"type": "session", "id": "a1b2c3d4e5f6", "key": "20260307_135945", "created": "2026-03-07T13:59:45Z"}
{"type": "user", "content": "Hello", "ts": "2026-03-07T13:59:46Z"}
{"type": "assistant", "content": "Hi!", "tool_calls": [], "ts": "2026-03-07T13:59:47Z"}
{"type": "tool_result", "tool": "bash", "tool_call_id": "call_123", "result": "output", "ts": "2026-03-07T13:59:48Z"}
{"type": "compaction", "kind": "auto", "before_count": 100, "after_count": 10, "ts": "2026-03-07T14:05:30Z"}
```

## 目录管理职责

### ✅ Session 包负责

- 会话元数据管理（sessions.json）
- JSONL transcript 文件
- **所有标准子目录的创建和管理**：
  - `workspace/` - 工作空间
  - `tasks/` - 任务文件
  - `team/` - 团队配置
  - `team/inbox/` - 消息收件箱
  - `board/` - 任务看板

### ✅ 各模块职责

- **TaskManager** - 使用 `get_task_file_path()` 获取文件路径
- **Team State** - 使用 `get_board_task_path()` 获取文件路径
- **TeammateManager** - 使用 `get_team_config_path()` 获取配置路径
- **MessageBus** - 使用 `get_inbox_path()` 获取消息文件路径

所有目录在 `create_session()` 时自动创建，`get_session_dir()` 时确保存在。
所有文件路径通过 session 包的辅助函数获取，无需手动拼接。

## 迁移说明

### 从旧 session.py 迁移

旧代码：
```python
from backend.app.session import save_session, load_session
```

新代码（无需修改）：
```python
from backend.app.session import save_session, load_session
# 完全兼容，无需修改代码
```

### 从 analysis/session_store.py 迁移

旧代码：
```python
from backend.app.analysis.session_store import get_store
```

新代码：
```python
from backend.app.session import get_store
# 只需修改导入路径
```

### 目录创建迁移

旧代码：
```python
from backend.app.session import get_session_dir

def get_tasks_dir():
    d = get_session_dir() / "tasks"
    d.mkdir(parents=True, exist_ok=True)
    return d
```

新代码：
```python
from backend.app.session import get_tasks_dir

# 直接使用，目录已自动创建
tasks_dir = get_tasks_dir()
```

### 文件路径迁移

旧代码：
```python
from backend.app.task.task_manager import TaskManager

class TaskManager:
    def _save(self, task):
        slug = _slug(task["subject"])
        path = self.dir / f"task_{task['id']}_{slug}.json"
        path.write_text(json.dumps(task))
```

新代码：
```python
from backend.app.session import get_task_file_path

class TaskManager:
    def _save(self, task):
        slug = _slug(task["subject"])
        path = get_task_file_path(task['id'], slug)
        path.write_text(json.dumps(task))
```

## 优势

✅ **统一入口** - 只需导入 `backend.app.session`
✅ **向后兼容** - 保留所有旧函数接口
✅ **功能完整** - 合并两个版本的优点
✅ **易于维护** - 单一职责，清晰结构
✅ **类型安全** - 统一的类型定义
✅ **细粒度保存** - 支持增量保存，避免重复写入
✅ **元数据索引** - 快速查询会话信息
✅ **统一目录管理** - 所有子目录由 session 包统一创建和管理
✅ **统一路径管理** - 所有文件路径由 session 包提供辅助函数

## 测试

运行测试：
```bash
PYTHONPATH=/Users/mac/Documents/ai/learnclaudecode/learnclaudecode python3 << 'EOF'
from backend.app.session import (
    new_session_key,
    get_task_file_path,
    get_inbox_path
)
from backend.app.task.task_manager import TaskManager
import shutil

# 创建会话
key = new_session_key()

# 测试目录自动创建
task_path = get_task_file_path(1, "test-task")
inbox_path = get_inbox_path("agent1")
print(f'✅ Task path: {task_path}')
print(f'✅ Inbox path: {inbox_path}')

# 测试 TaskManager 集成
tm = TaskManager()
tm.create("Test task")
print(f'✅ TaskManager works')

# 清理
from backend.app.session import get_session_dir
shutil.rmtree(get_session_dir())
print(f'✅ All tests passed!')
EOF
```

