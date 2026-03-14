# Tools 自动加载机制（Spring 风格）

## 核心理念

**约定优于配置**：默认扫描所有 `@tool` 装饰的工具，配置文件只用于覆盖默认行为。

## 快速开始

### 1. 定义工具（使用装饰器）

```python
from backend.app.tools.base import tool

@tool(tags=["both"], category="core")
def my_tool(param: str) -> str:
    """工具描述"""
    return f"Result: {param}"
```

### 2. 自动加载（无需配置）

```python
from backend.app.tools.manager import tool_manager

# 自动扫描所有工具
tool_manager.auto_discover(tools_dir)
```

### 3. 配置覆盖（可选）

```yaml
# tools_config.yaml
profile: dev

modules:
  agent.spawn_tool:
    enabled: false
```

## 配置文件

### 基本结构

```yaml
# 环境配置（类似 Spring Profile）
profile: dev  # dev | prod | test

# 全局开关
auto_scan: true

# 模块级配置
modules:
  agent.spawn_tool:
    enabled: false

  storage.memory_tools:
    scope: subagent
    subagent_types: [explore]

# 工具级配置
tools:
  dangerous_tool:
    enabled: false
```

### 环境隔离（Profile）

```yaml
profile: prod

profiles:
  dev:
    # 开发环境：所有工具可用
    modules: {}

  prod:
    # 生产环境：禁用危险工具
    modules:
      system.worktree_tool:
        enabled: false
```

## 配置优先级

**工具级 > 模块级 > 装饰器**

```python
# 装饰器定义
@tool(tags=["both"])
def my_tool(): ...

# 模块配置覆盖
modules:
  core.my_module:
    scope: subagent

# 工具配置覆盖（最高优先级）
tools:
  my_tool:
    scope: main
```

## 对比 Spring

| Spring | 本系统 |
|--------|--------|
| `@Component` | `@tool` |
| `@ComponentScan` | `auto_discover()` |
| `@Profile` | `profile: dev/prod` |
| `application.yml` | `tools_config.yaml` |
| 约定优于配置 | ✅ 默认加载所有 |
