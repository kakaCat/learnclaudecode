# Tools 自动加载机制（Spring 风格 - 纯代码配置）

## 核心理念

**约定优于配置**：通过装饰器和模块级变量声明配置，无需外部配置文件。

## 配置方式

### 1. 最简方式（推荐）

```python
@tool()  # 默认: tags=["both"], category="general"
def my_tool() -> str:
    """My tool - 所有 agent 都可以使用"""
    return "result"
```

**默认值**：
- `tags=["both"]` - 所有 agent (main/subagent/team) 都可以使用
- `category="general"` - 通用分类

### 2. 模块级配置（推荐）

在每个工具文件开头声明 `__tool_config__`：

```python
# agent/spawn_tool.py
__tool_config__ = {
    "tags": ["main"],
    "category": "agent"
}

from backend.app.tools.base import tool

@tool()  # 继承模块配置
def spawn_subagent(description: str, prompt: str) -> str:
    """Spawn a subagent"""
    return f"Spawned: {description}"

@tool(tags=["both"])  # 覆盖为 both
def list_subagents() -> str:
    """List all subagents"""
    return "subagent1, subagent2"
```

### 3. 方法级配置（显式指定）

直接在装饰器中指定：

```python
@tool(tags=["main"], category="agent")
def my_tool() -> str:
    """My tool"""
    return "result"
```

## 配置优先级

```
方法级 @tool(tags=["main"]) > 模块级 __tool_config__ > 默认值
```

## 配置项说明

| 配置项 | 类型 | 可选值 | 说明 |
|--------|------|--------|------|
| `tags` | list | `["main"]`, `["subagent"]`, `["team"]`, `["both"]` | 工具作用域 |
| `category` | str | `core`, `agent`, `storage`, `execution`, `integration`, `system` | 工具分类 |
| `subagent_types` | list | `["explore", "web-search"]` | 指定哪些 subagent 可用 |

## 完整示例

### 示例 1: 核心文件工具

```python
# core/file_tool.py
__tool_config__ = {
    "tags": ["both"],
    "category": "core"
}

from backend.app.tools.base import tool

@tool()
def read_file(path: str) -> str:
    """Read file"""
    return f"Read: {path}"

@tool()
def write_file(path: str, content: str) -> str:
    """Write file"""
    return f"Write: {path}"
```

### 示例 2: Agent 工具（覆盖配置）

```python
# agent/spawn_tool.py
__tool_config__ = {
    "tags": ["main"],
    "category": "agent"
}

from backend.app.tools.base import tool

@tool()  # 继承: tags=["main"]
def spawn_subagent(...) -> str:
    """Spawn subagent (main only)"""
    pass

@tool(tags=["both"])  # 覆盖: tags=["both"]
def list_subagents() -> str:
    """List subagents (all agents)"""
    pass
```

### 示例 3: 浏览器工具（指定 subagent 类型）

```python
# integration/browser_tool.py
__tool_config__ = {
    "tags": ["subagent"],
    "category": "integration",
    "subagent_types": ["explore", "web-search"]
}

from backend.app.tools.base import tool

@tool()
def navigate(url: str) -> str:
    """Navigate to URL"""
    return f"Navigate: {url}"
```

## 对比 Spring

| Spring MVC | 本系统 |
|-----------|--------|
| `@RestController` | `__tool_config__` |
| `@RequestMapping("/api")` | `category="core"` |
| `@GetMapping` | `@tool()` |
| `application.yml` | ❌ 不需要 |
| 约定优于配置 | ✅ 纯代码配置 |

## 自动加载

```python
from backend.app.tools.manager import tool_manager

# 自动扫描所有工具
tool_manager.auto_discover(tools_dir)

# 获取工具
main_tools = tool_manager.get_main_tools()
subagent_tools = tool_manager.get_subagent_tools()
```

## 优势

✅ **纯代码配置** - 无需外部配置文件
✅ **类型安全** - IDE 自动补全和检查
✅ **就近原则** - 配置和代码在一起
✅ **灵活覆盖** - 方法级可覆盖模块级
✅ **自动发现** - 无需手动注册
