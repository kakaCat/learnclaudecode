import os
import inspect
from pathlib import Path
from langchain_core.tools import tool as _tool

WORKDIR = Path(os.getcwd())
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", ".mypy_cache"}

# 全局工具注册表（类似 Spring 的 ApplicationContext）
_TOOL_REGISTRY = {}


def _safe_path(p: str) -> Path:
    path = (WORKDIR / p).resolve()
    if not path.is_relative_to(WORKDIR):
        raise ValueError(f"Path escapes workspace: {p}")
    return path


def tool(tags=None, category=None, enabled=None, **kwargs):
    """
    工具装饰器（类似 Spring 的 @Component）

    优先级：方法级参数 > 模块级 __tool_config__ > 默认值

    Args:
        tags: 作用域标签 ["main", "subagent", "team", "both"]
        category: 工具分类 (core/agent/storage/execution/integration/system)
        enabled: 是否启用该工具（默认 True）
        **kwargs: 传递给 langchain tool 的参数
    """
    def decorator(func):
        # 尝试从模块级 __tool_config__ 读取默认配置
        module = inspect.getmodule(func)
        module_config = getattr(module, '__tool_config__', {}) if module else {}

        # 检查是否禁用（优先级：方法级 > 模块级 > 默认 True）
        final_enabled = enabled if enabled is not None else module_config.get('enabled', True)
        if not final_enabled:
            # 不注册，直接返回原函数
            return func

        # 创建 langchain tool
        if kwargs:
            tool_func = _tool(**kwargs)(func)
        else:
            tool_func = _tool(func)

        # 优先级：方法级 > 模块级 > 默认值
        final_tags = tags if tags is not None else module_config.get('tags')
        final_category = category if category is not None else module_config.get('category')

        # 注入元数据
        tool_func.tags = final_tags or ["both"]
        tool_func._category = final_category or "general"

        # 注入其他模块级配置
        if 'subagent_types' in module_config:
            tool_func._subagent_types = module_config['subagent_types']

        # 自动注册到全局表
        _TOOL_REGISTRY[tool_func.name] = tool_func

        return tool_func
    return decorator


def get_registered_tools():
    """获取所有已注册的工具（类似 Spring 的 getBeansOfType）"""
    return dict(_TOOL_REGISTRY)
