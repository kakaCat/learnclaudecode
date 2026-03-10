import os
from pathlib import Path
from langchain_core.tools import tool as _tool

WORKDIR = Path(os.getcwd())
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", ".mypy_cache"}


def _safe_path(p: str) -> Path:
    path = (WORKDIR / p).resolve()
    if not path.is_relative_to(WORKDIR):
        raise ValueError(f"Path escapes workspace: {p}")
    return path


def tool(tags=None, **kwargs):
    """带 tags 的 tool 装饰器"""
    def decorator(func):
        if kwargs:
            tool_func = _tool(**kwargs)(func)
        else:
            tool_func = _tool(func)
        tool_func.tags = tags or ["both"]
        return tool_func
    return decorator
