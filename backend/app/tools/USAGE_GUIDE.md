# Spring 风格工具加载 - 完整指南

## 快速开始

### 1. 创建新工具（最简单）

```python
# implementations/core/my_tool.py
from backend.app.tools.base import tool

@tool()  # 默认所有 agent 可用
def my_tool(param: str) -> str:
    """My tool description"""
    return f"Result: {param}"
```

### 2. 使用模块级配置（推荐）

```python
# implementations/agent/my_module.py
__tool_config__ = {
    "tags": ["main"],
    "category": "agent"
}

from backend.app.tools.base import tool

@tool()  # 继承模块配置
def tool1() -> str:
    """Tool 1"""
    return "result1"

@tool()  # 继承模块配置
def tool2() -> str:
    """Tool 2"""
    return "result2"
```

### 3. 禁用工具

```python
# 方式 1: 禁用整个模块
__tool_config__ = {
    "enabled": False  # 所有工具都不加载
}

# 方式 2: 禁用单个工具
@tool(enabled=False)
def dangerous_tool() -> str:
    """Dangerous tool"""
    return "result"

# 方式 3: 模块禁用，个别启用
__tool_config__ = {
    "enabled": False
}

@tool(enabled=True)  # 覆盖为启用
def safe_tool() -> str:
    """Safe tool"""
    return "result"
```

## 配置项完整说明

### tags（作用域）

| 值 | 说明 | 使用场景 |
|----|------|---------|
| `["both"]` | 所有 agent 可用（默认） | 通用工具（文件操作、bash） |
| `["main"]` | 只有 main agent 可用 | 高级功能（spawn、worktree） |
| `["subagent"]` | 只有 subagent 可用 | 专用工具（探索、分析） |
| `["team"]` | 只有 team agent 可用 | 团队协作工具 |
| `["main", "team"]` | main 和 team 可用 | 任务管理工具 |

### category（分类）

| 值 | 说明 | 示例 |
|----|------|------|
| `core` | 核心文件操作 | read_file, write_file, bash |
| `agent` | Agent 协作 | spawn_subagent, task_create |
| `storage` | 数据存储 | memory_write, workspace_read |
| `execution` | 后台执行 | background_run, load_skill |
| `integration` | 外部集成 | cdp_browser, mcp_tool |
| `system` | 系统级操作 | worktree_create, compact |
| `general` | 通用（默认） | 未分类工具 |

### enabled（启用状态）

| 值 | 说明 |
|----|------|
| `True` | 启用（默认） |
| `False` | 禁用，不注册到工具表 |

## 配置优先级

```
方法级 > 模块级 > 默认值
```

示例：
```python
__tool_config__ = {
    "tags": ["main"],      # 模块级
    "category": "agent"
}

@tool()  # 继承: tags=["main"], category="agent"
def tool1(): ...

@tool(tags=["both"])  # 覆盖: tags=["both"], category="agent"
def tool2(): ...

@tool(category="core")  # 覆盖: tags=["main"], category="core"
def tool3(): ...
```

## 实际案例

### 案例 1: 文件工具（所有 agent 可用）

```python
# core/file_tool.py
__tool_config__ = {
    "tags": ["both"],
    "category": "core"
}

@tool()
def read_file(path: str) -> str:
    """Read file"""
    ...

@tool()
def write_file(path: str, content: str) -> str:
    """Write file"""
    ...
```

### 案例 2: 任务工具（main 和 team 可用）

```python
# agent/task_tool.py
__tool_config__ = {
    "tags": ["main", "team"],
    "category": "agent"
}

@tool()
def task_create(...): ...

@tool()
def task_list(...): ...
```

### 案例 3: 禁用的工具模块

```python
# agent/task_tool.py
__tool_config__ = {
    "tags": ["main", "team"],
    "category": "agent",
    "enabled": False  # 整个模块禁用
}

@tool()  # 不会注册
def task_create(...): ...

@tool()  # 不会注册
def task_list(...): ...
```

### 案例 4: 浏览器工具（指定 subagent 类型）

```python
# integration/browser_tool.py
__tool_config__ = {
    "tags": ["subagent"],
    "category": "integration",
    "subagent_types": ["explore", "web-search"]
}

@tool()
def navigate(url: str) -> str:
    """Navigate to URL"""
    ...
```

## 自动加载

```python
from backend.app.tools.manager import tool_manager
from pathlib import Path

# 自动扫描所有工具
tools_dir = Path(__file__).parent / "tools"
tool_manager.auto_discover(tools_dir)

# 获取不同作用域的工具
main_tools = tool_manager.get_main_tools()
subagent_tools = tool_manager.get_subagent_tools()
team_tools = tool_manager.get_team_tools()
all_tools = tool_manager.get_tools(scope="all")
```

## 最佳实践

1. **默认使用 `@tool()`** - 简洁明了
2. **相同配置用模块级** - 避免重复
3. **特殊工具用方法级覆盖** - 灵活控制
4. **禁用用 `enabled=False`** - 清晰表达意图
5. **分类要准确** - 便于管理和查找

## 对比传统方式

### 传统方式（重复配置）
```python
@tool(tags=["main"], category="agent")
def tool1(): ...

@tool(tags=["main"], category="agent")
def tool2(): ...

@tool(tags=["main"], category="agent")
def tool3(): ...
```

### Spring 风格（模块级配置）
```python
__tool_config__ = {
    "tags": ["main"],
    "category": "agent"
}

@tool()
def tool1(): ...

@tool()
def tool2(): ...

@tool()
def tool3(): ...
```

**优势**：
- ✅ 配置只写一次
- ✅ 易于维护
- ✅ 清晰明了
- ✅ 符合 DRY 原则
