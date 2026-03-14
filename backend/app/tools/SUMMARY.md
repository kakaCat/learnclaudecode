# Spring 风格工具加载机制 - 总结

## 🎯 设计目标

实现类似 Spring MVC 的工具自动加载机制：
- **约定优于配置**
- **装饰器标记**
- **自动扫描**
- **模块级配置**
- **纯代码配置**

## 📐 核心架构

```
┌─────────────────────────────────────────────────────────┐
│                    @tool 装饰器                          │
│  (类似 Spring 的 @Component)                            │
│  - 自动注册到全局表                                      │
│  - 支持模块级配置继承                                    │
│  - 支持方法级覆盖                                        │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│              _TOOL_REGISTRY (全局注册表)                 │
│  (类似 Spring 的 ApplicationContext)                    │
│  - 存储所有已注册的工具                                  │
│  - 装饰器执行时自动注册                                  │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│           ToolsManager.auto_discover()                  │
│  (类似 Spring 的 @ComponentScan)                        │
│  - 递归扫描 implementations/ 目录                        │
│  - 触发模块导入，激活装饰器                              │
│  - 从注册表实例化工具                                    │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│              按作用域分发工具                            │
│  - get_main_tools()                                     │
│  - get_subagent_tools()                                 │
│  - get_team_tools()                                     │
└─────────────────────────────────────────────────────────┘
```

## 🔧 核心组件

### 1. 装饰器 `@tool`

**位置**: `backend/app/tools/base.py`

**功能**:
- 标记函数为工具
- 读取模块级 `__tool_config__`
- 应用配置优先级
- 自动注册到全局表

**使用**:
```python
@tool()  # 默认配置
@tool(tags=["main"])  # 方法级配置
@tool(enabled=False)  # 禁用工具
```

### 2. 全局注册表 `_TOOL_REGISTRY`

**位置**: `backend/app/tools/base.py`

**功能**:
- 存储所有已注册的工具
- 装饰器执行时自动填充
- 提供 `get_registered_tools()` 访问

### 3. 工具管理器 `ToolsManager`

**位置**: `backend/app/tools/manager.py`

**功能**:
- `auto_discover()` - 自动扫描和加载
- `get_tools(scope)` - 按作用域获取工具
- `get_main_tools()` - 获取 main agent 工具
- `get_subagent_tools()` - 获取 subagent 工具

### 4. 模块级配置 `__tool_config__`

**位置**: 每个工具文件开头

**功能**:
- 声明模块默认配置
- 所有工具继承此配置
- 方法级可覆盖

**示例**:
```python
__tool_config__ = {
    "tags": ["main"],
    "category": "agent",
    "enabled": True
}
```

## 📊 配置优先级

```
方法级 @tool(tags=["main"])
    ↓
模块级 __tool_config__
    ↓
默认值 tags=["both"], category="general", enabled=True
```

## 🎨 使用方式

### 方式 1: 最简单（推荐）

```python
@tool()  # 所有 agent 可用
def my_tool() -> str:
    """My tool"""
    return "result"
```

### 方式 2: 模块级配置

```python
__tool_config__ = {
    "tags": ["main"],
    "category": "agent"
}

@tool()  # 继承模块配置
def tool1(): ...

@tool()  # 继承模块配置
def tool2(): ...
```

### 方式 3: 方法级覆盖

```python
__tool_config__ = {
    "tags": ["main"]
}

@tool(tags=["both"])  # 覆盖为 both
def special_tool(): ...
```

### 方式 4: 禁用工具

```python
__tool_config__ = {
    "enabled": False  # 禁用整个模块
}

@tool(enabled=True)  # 个别启用
def safe_tool(): ...
```

## 📁 目录结构

```
tools/
├── base.py                    # @tool 装饰器 + 注册表
├── manager.py                 # ToolsManager
├── USAGE_GUIDE.md             # 使用指南
├── PURE_CODE_CONFIG.md        # 纯代码配置文档
└── implementations/           # 工具实现
    ├── core/                  # 核心工具
    │   └── file_tool.py       # ✅ 已改造
    ├── agent/                 # Agent 工具
    │   └── task_tool.py       # ✅ 已改造
    ├── storage/               # 存储工具
    ├── execution/             # 执行工具
    ├── integration/           # 集成工具
    └── system/                # 系统工具
```

## ✅ 已完成的改造

1. ✅ `file_tool.py` - 模块级配置
2. ✅ `task_tool.py` - 模块级配置 + 禁用示例

## 🔄 对比 Spring MVC

| Spring MVC | 本系统 | 说明 |
|-----------|--------|------|
| `@Component` | `@tool()` | 标记组件 |
| `@ComponentScan` | `auto_discover()` | 自动扫描 |
| `ApplicationContext` | `_TOOL_REGISTRY` | 全局容器 |
| `@RequestMapping` | `__tool_config__` | 模块级配置 |
| `application.yml` | ❌ 不需要 | 纯代码配置 |
| 约定优于配置 | ✅ | 默认加载所有 |

## 🎯 核心优势

1. **约定优于配置** - `@tool()` 即可，无需繁琐配置
2. **DRY 原则** - 模块级配置避免重复
3. **类型安全** - 纯代码配置，IDE 支持
4. **灵活覆盖** - 方法级可覆盖模块级
5. **自动发现** - 无需手动注册
6. **清晰禁用** - `enabled=False` 明确表达意图

## 📚 文档

- [USAGE_GUIDE.md](USAGE_GUIDE.md) - 完整使用指南
- [PURE_CODE_CONFIG.md](PURE_CODE_CONFIG.md) - 纯代码配置说明
- [SPRING_STYLE.md](SPRING_STYLE.md) - Spring 风格对比

## 🚀 下一步

可以继续改造其他工具文件：
- `storage/memory_tools.py`
- `execution/background_tool.py`
- `integration/browser_tool.py`
- `system/worktree_tool.py`

改造方式：
1. 添加 `__tool_config__`
2. 将 `@tool(tags=..., category=...)` 改为 `@tool()`
3. 测试验证
