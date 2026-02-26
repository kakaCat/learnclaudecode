from __future__ import annotations
import importlib
import pkgutil
from pathlib import Path


class ToolsManager:
    """
    Tools 注册中心。

    工具通过 register() 注册，Agent 通过 get_tools() 获取。
    Task 工具依赖其他工具列表，通过 build_task_tool() 延迟创建。
    """

    def __init__(self):
        self._tools: dict = {}
        self._task_tool = None

    def register(self, *tools) -> "ToolsManager":
        for t in tools:
            self._tools[t.name] = t
        return self

    def auto_discover(self, tools_dir: Path, skip: set = None) -> "ToolsManager":
        from langchain_core.tools import BaseTool
        skip = (skip or set()) | {"spawn_tool", "__init__"}
        package = "backend.app.tools"
        for info in pkgutil.iter_modules([str(tools_dir)]):
            if info.name in skip:
                continue
            module = importlib.import_module(f"{package}.{info.name}")
            for attr in dir(module):
                obj = getattr(module, attr)
                if isinstance(obj, BaseTool):
                    self._tools[obj.name] = obj
        return self

    def build_task_tool(self) -> "ToolsManager":
        """创建 Task 工具并注册。subagent tools 在调用时从 manager 动态获取。"""
        from backend.app.tools.spawn_tool import make_task_tool
        self._task_tool = make_task_tool()
        self._tools[self._task_tool.name] = self._task_tool
        return self

    def get_tools(self) -> list:
        return list(self._tools.values())

    def get(self, name: str):
        return self._tools.get(name)

    @property
    def tools_map(self) -> dict:
        return dict(self._tools)


tools_manager = ToolsManager()
