"""
ToolRegistry - 工具注册中心

解决循环依赖问题的核心设计：
1. 独立初始化，不依赖任何 Context
2. 通过 scope 管理工具可见性
3. 支持自动发现和手动注册
"""
from typing import List, Dict, Set
from pathlib import Path
from langchain_core.tools import BaseTool
import importlib
import pkgutil


class ToolRegistry:
    """工具注册中心"""

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
        self._scopes: Dict[str, Set[str]] = {
            "main": set(),    # 主 Agent 工具
            "sub": set(),     # 子 Agent 工具
            "team": set(),    # 团队 Agent 工具
            "both": set(),    # 所有 Agent 共享
        }

    def register(self, tool: BaseTool, scope: str = "both") -> "ToolRegistry":
        """
        注册工具

        Args:
            tool: 工具实例
            scope: 作用域 ("main" | "sub" | "team" | "both")
        """
        self._tools[tool.name] = tool

        if scope == "both":
            # both 工具对所有 scope 可见
            self._scopes["main"].add(tool.name)
            self._scopes["sub"].add(tool.name)
            self._scopes["team"].add(tool.name)
        else:
            self._scopes[scope].add(tool.name)

        return self

    def get(self, scope: str) -> List[BaseTool]:
        """
        获取指定 scope 的工具列表

        Args:
            scope: "main" | "sub" | "team" | "all"
        """
        if scope == "all":
            return list(self._tools.values())

        tool_names = self._scopes.get(scope, set())
        return [self._tools[name] for name in tool_names if name in self._tools]

    def get_tool(self, name: str) -> BaseTool:
        """获取单个工具"""
        return self._tools.get(name)

    def auto_discover(self, tools_dir: Path, skip: Set[str] = None) -> "ToolRegistry":
        """
        自动发现并注册工具

        Args:
            tools_dir: 工具目录
            skip: 跳过的模块名
        """
        skip = skip or set()
        skip.update({"__init__", "base", "manager"})

        package = "backend.app.tools"

        # 扫描主目录
        for info in pkgutil.iter_modules([str(tools_dir)]):
            if info.name in skip:
                continue

            try:
                module = importlib.import_module(f"{package}.{info.name}")
                self._register_from_module(module)
            except Exception as e:
                print(f"⚠️  Failed to load {info.name}: {e}")

        # 扫描 implementations 子目录
        impl_dir = tools_dir / "implementations"
        if impl_dir.exists():
            self._scan_implementations(impl_dir, package, skip)

        # 按 scope 分组统计
        scope_counts = {scope: len(names) for scope, names in self._scopes.items() if names}
        print(f"✅ 已加载 {len(self._tools)} 个工具: {scope_counts}")
        return self

    def _scan_implementations(self, impl_dir: Path, package: str, skip: Set[str]):
        """扫描 implementations 目录"""
        for category_dir in impl_dir.iterdir():
            if not category_dir.is_dir() or category_dir.name.startswith("_"):
                continue

            for info in pkgutil.iter_modules([str(category_dir)]):
                if info.name in skip:
                    continue

                try:
                    module_path = f"{package}.implementations.{category_dir.name}.{info.name}"
                    module = importlib.import_module(module_path)
                    self._register_from_module(module)
                except Exception as e:
                    print(f"⚠️  Failed to load {category_dir.name}/{info.name}: {e}")

    def _register_from_module(self, module):
        """从模块中注册工具"""
        for attr in dir(module):
            obj = getattr(module, attr)
            if isinstance(obj, BaseTool):
                # 从 tags 推断 scope
                scope = self._infer_scope(obj)

                if scope == "multi":
                    # 多个 scope，分别注册
                    tags = getattr(obj, "tags", None) or []
                    scope_tags = [t for t in tags if t in ["main", "sub", "subagent", "team"]]
                    for tag in scope_tags:
                        if tag in ["sub", "subagent"]:
                            self._scopes["sub"].add(obj.name)
                        else:
                            self._scopes[tag].add(obj.name)
                    self._tools[obj.name] = obj
                else:
                    self.register(obj, scope)

    def _infer_scope(self, tool: BaseTool) -> str:
        """从工具的 tags 推断 scope"""
        tags = getattr(tool, "tags", None) or []

        # 如果有多个 scope tags，需要特殊处理
        # 例如 ["main", "team"] 表示只对 main 和 team 可见
        scope_tags = [t for t in tags if t in ["main", "sub", "subagent", "team", "both"]]

        if not scope_tags or "both" in scope_tags:
            return "both"
        elif len(scope_tags) == 1:
            # 单个 scope
            if scope_tags[0] in ["sub", "subagent"]:
                return "sub"
            return scope_tags[0]
        else:
            # 多个 scope，需要分别注册
            return "multi"


# 全局单例
_registry = None


def get_registry() -> ToolRegistry:
    """获取全局工具注册中心"""
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
        # 自动发现工具
        # __file__ = backend/app/core/tools/tool_registry.py
        # parent = backend/app/core/tools/
        # parent.parent = backend/app/core/
        # parent.parent.parent = backend/app/
        tools_dir = Path(__file__).parent.parent.parent / "tools"
        if tools_dir.exists():
            _registry.auto_discover(tools_dir)
    return _registry
