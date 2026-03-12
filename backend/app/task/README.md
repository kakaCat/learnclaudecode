# Task 模块 - 企业级架构

## 架构设计

采用经典的分层架构模式，职责清晰，易于维护和测试。

```
backend/app/task/
├── models.py           # 数据模型层 (Domain Model)
├── exceptions.py       # 异常定义
├── repository.py       # 数据访问层 (Repository Pattern)
├── service.py          # 业务逻辑层 (Service Layer)
├── converter.py        # 数据转换层 (Converter/Presenter)
└── __init__.py         # 模块导出
```

## 各层职责

### 1. Models（models.py）

**职责**: 领域模型定义

- 使用 Pydantic 定义类型安全的数据模型
- 包含业务规则验证
- 提供领域方法（如 `is_blocked()`, `can_start()`）

**核心类**:
- `Task`: 任务实体
- `TaskStatus`: 任务状态枚举（5种状态）
- `TaskPriority`: 任务优先级枚举（4个级别）

**特性**:
- 字段验证（长度、格式、范围）
- 自动去重（blocked_by, blocks）
- 标签自动小写化
- 时间自动管理

### 2. Exceptions（exceptions.py）

**职责**: 业务异常定义

- `TaskError`: 基础异常
- `TaskNotFoundError`: 任务不存在
- `InvalidTaskStatusError`: 无效状态转换
- `TaskValidationError`: 数据验证失败

### 3. Repository（repository.py）

**职责**: 数据持久化

- 文件系统存储实现
- CRUD 操作
- 查询方法（按状态、优先级、标签等）
- 序列化/反序列化

**核心方法**:
```python
get_by_id(task_id) -> Task
save(task) -> None
delete(task_id) -> None
find_all() -> List[Task]
find_by_status(status) -> List[Task]
find_by_priority(priority) -> List[Task]
find_by_tags(tags) -> List[Task]
find_blocked_tasks() -> List[Task]
find_available_tasks() -> List[Task]
```

### 4. Service（service.py）

**职责**: 业务逻辑编排

- 任务生命周期管理
- 依赖关系管理
- 状态转换验证
- 循环依赖检测
- 事件发送

**核心方法**:
```python
# 基础操作
create_task(subject, description, priority, owner, tags) -> Task
get_task(task_id) -> Task
update_task(task_id, ...) -> Task
delete_task(task_id) -> None

# 状态管理
start_task(task_id, owner) -> Task
complete_task(task_id) -> Task
cancel_task(task_id) -> Task
change_status(task_id, status) -> Task

# 依赖管理
add_dependency(task_id, depends_on) -> Task
remove_dependency(task_id, depends_on) -> Task

# 标签管理
add_tag(task_id, tag) -> Task
remove_tag(task_id, tag) -> Task

# 工作树管理
bind_worktree(task_id, worktree, owner) -> Task
unbind_worktree(task_id) -> Task

# 查询
list_all_tasks() -> List[Task]
list_tasks_by_status(status) -> List[Task]
list_tasks_by_owner(owner) -> List[Task]
list_tasks_by_priority(priority) -> List[Task]
list_blocked_tasks() -> List[Task]
list_available_tasks() -> List[Task]
```

**业务规则**:
- 状态转换验证（有限状态机）
- 循环依赖检测
- 完成任务自动解除阻塞
- 开始任务检查阻塞状态

### 5. Converter（converter.py）

**职责**: 数据格式转换和展示

- JSON 序列化
- 字典转换
- 显示格式化（单行、摘要、列表）
- 分组展示（按状态、优先级、负责人）
- CSV 导出

**核心方法**:
```python
to_json(task, pretty) -> str
to_dict(task) -> Dict
to_display_line(task, show_details) -> str
to_summary(task) -> str
tasks_to_list_display(tasks, group_by, show_details) -> str
tasks_to_csv(tasks) -> str
```

## 使用示例

### 基础使用

```python
from backend.app.task import TaskService, TaskPriority, TaskStatus

# 获取服务实例
service = TaskService()

# 创建任务
task = service.create_task(
    subject="实现用户登录功能",
    description="使用JWT实现用户认证",
    priority=TaskPriority.HIGH,
    owner="张三",
    tags=["backend", "auth"]
)

# 开始任务
service.start_task(task.id, owner="张三")

# 完成任务
service.complete_task(task.id)
```

### 依赖管理

```python
# 创建两个任务
task1 = service.create_task("设计数据库")
task2 = service.create_task("实现API")

# task2 依赖 task1
service.add_dependency(task2.id, task1.id)

# 查询被阻塞的任务
blocked = service.list_blocked_tasks()

# 完成 task1 后，task2 自动解除阻塞
service.complete_task(task1.id)
```

### 查询和展示

```python
from backend.app.task import TaskConverter

# 查询高优先级任务
high_priority = service.list_tasks_by_priority(TaskPriority.HIGH)

# 格式化显示
display = TaskConverter.tasks_to_list_display(
    high_priority,
    group_by="status",
    show_details=True
)
print(display)

# 导出CSV
csv = TaskConverter.tasks_to_csv(high_priority)
```

### 全局单例

```python
from backend.app.task import get_task_service

# 获取全局单例
service = get_task_service()
```

## 状态机

任务状态转换规则：

```
PENDING (待开始)
  ├─> IN_PROGRESS (进行中)
  └─> CANCELLED (已取消)

IN_PROGRESS (进行中)
  ├─> COMPLETED (已完成)
  ├─> BLOCKED (被阻塞)
  └─> CANCELLED (已取消)

BLOCKED (被阻塞)
  ├─> IN_PROGRESS (进行中)
  └─> CANCELLED (已取消)

COMPLETED (已完成) - 终态
CANCELLED (已取消) - 终态
```

## 优先级

```
URGENT (紧急) 🔥
HIGH (高) ⚡
MEDIUM (中) 📌
LOW (低) 📋
```

## 数据存储

当前使用文件系统存储（JSON格式）：

```
.claude/tasks/
├── task_1_implement-login.json
├── task_2_design-database.json
└── task_3_write-tests.json
```

文件格式：
```json
{
  "id": 1,
  "subject": "实现用户登录功能",
  "description": "使用JWT实现用户认证",
  "status": "in_progress",
  "priority": "high",
  "blocked_by": [],
  "blocks": [2],
  "owner": "张三",
  "worktree": "",
  "tags": ["backend", "auth"],
  "created_at": "2026-03-11T10:00:00",
  "updated_at": "2026-03-11T10:30:00",
  "completed_at": null
}
```

## 扩展性

### 切换到数据库存储

只需实现新的 Repository：

```python
class DatabaseTaskRepository(TaskRepository):
    def __init__(self, db_session):
        self.session = db_session

    def get_by_id(self, task_id: int) -> Task:
        # 使用 SQLAlchemy 查询
        pass

    def save(self, task: Task) -> None:
        # 使用 SQLAlchemy 保存
        pass
```

然后注入到 Service：

```python
repo = DatabaseTaskRepository(db_session)
service = TaskService(repository=repo)
```

### 添加新的查询方法

在 Repository 中添加：

```python
def find_by_date_range(
    self,
    start: datetime,
    end: datetime
) -> List[Task]:
    return [
        task for task in self.find_all()
        if start <= task.created_at <= end
    ]
```

在 Service 中暴露：

```python
def list_tasks_by_date_range(
    self,
    start: datetime,
    end: datetime
) -> List[Task]:
    return self.repository.find_by_date_range(start, end)
```

## 测试

### 单元测试示例

```python
import pytest
from datetime import datetime
from backend.app.task import TaskService, TaskPriority, TaskStatus

def test_create_task():
    service = TaskService()
    task = service.create_task(
        subject="测试任务",
        priority=TaskPriority.HIGH
    )

    assert task.id > 0
    assert task.subject == "测试任务"
    assert task.status == TaskStatus.PENDING
    assert task.priority == TaskPriority.HIGH

def test_dependency_management():
    service = TaskService()
    task1 = service.create_task("任务1")
    task2 = service.create_task("任务2")

    # 添加依赖
    service.add_dependency(task2.id, task1.id)

    task2 = service.get_task(task2.id)
    assert task1.id in task2.blocked_by
    assert task2.is_blocked()

    # 完成task1后，task2解除阻塞
    service.complete_task(task1.id)
    task2 = service.get_task(task2.id)
    assert not task2.is_blocked()
```

## 性能考虑

当前文件系统实现适合小规模使用（< 1000个任务）。

对于大规模使用，建议：
1. 切换到数据库存储（PostgreSQL/MySQL）
2. 添加索引（status, priority, owner）
3. 实现分页查询
4. 添加缓存层（Redis）

## 总结

这是一个标准的企业级分层架构实现：

✅ **职责分离**: 每层职责清晰
✅ **类型安全**: Pydantic 模型验证
✅ **易于测试**: 依赖注入，Mock友好
✅ **易于扩展**: 接口清晰，易于替换实现
✅ **业务规则**: 状态机、循环依赖检测
✅ **日志记录**: 完整的操作日志
✅ **事件通知**: 关键操作发送事件
