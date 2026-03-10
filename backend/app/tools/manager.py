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
        self._mcp_loaded = False
        self._initialized = False

    def register(self, *tools) -> "ToolsManager":
        for t in tools:
            self._tools[t.name] = t
        return self

    def auto_discover(self, tools_dir: Path, skip: set = None) -> "ToolsManager":
        from langchain_core.tools import BaseTool
        skip = (skip or set()) | {"spawn_tool", "__init__", "mcp_tool", "cdp_tool"}
        package = "backend.app.tools"

        print("=" * 80)
        print("🔧 ToolsManager.auto_discover()")
        print("=" * 80)

        # Scan main tools directory
        print(f"📂 Scanning: {tools_dir}")
        for info in pkgutil.iter_modules([str(tools_dir)]):
            if info.name in skip:
                print(f"⏭️  Skip: {info.name}")
                continue
            module = importlib.import_module(f"{package}.{info.name}")
            for attr in dir(module):
                obj = getattr(module, attr)
                if isinstance(obj, BaseTool):
                    self._tools[obj.name] = obj
                    print(f"✅ Loaded: {obj.name} (from {info.name})")

        # Scan implementations subdirectory
        impl_dir = tools_dir / "implementations"
        if impl_dir.exists():
            print(f"📂 Scanning: {impl_dir}")
            for info in pkgutil.iter_modules([str(impl_dir)]):
                if info.name in skip:
                    print(f"⏭️  Skip: {info.name}")
                    continue
                module = importlib.import_module(f"{package}.implementations.{info.name}")
                for attr in dir(module):
                    obj = getattr(module, attr)
                    if isinstance(obj, BaseTool):
                        self._tools[obj.name] = obj
                        print(f"✅ Loaded: {obj.name} (from implementations/{info.name})")

        print(f"📊 Total tools loaded: {len(self._tools)}")
        print("=" * 80)
        return self

    def build_task_tool(self) -> "ToolsManager":
        """创建 Task 工具并注册。subagent tools 在调用时从 manager 动态获取。"""
        from backend.app.tools.implementations.spawn_tool import make_task_tool
        self._task_tool = make_task_tool()
        self._tools[self._task_tool.name] = self._task_tool
        return self

    async def load_mcp_tools(self) -> "ToolsManager":
        """异步加载 MCP 工具"""
        if self._mcp_loaded:
            return self

        try:
            from backend.app.tools.implementations.mcp_tool import get_mcp_tools
            mcp_tools = await get_mcp_tools()
            for tool in mcp_tools:
                self._tools[tool.name] = tool
            self._mcp_loaded = True
        except Exception as e:
            import logging
            logging.error(f"Failed to load MCP tools: {e}")

        return self

    def _ensure_initialized(self):
        """确保工具已初始化（延迟初始化，避免循环导入）"""
        if not self._initialized:
            from pathlib import Path
            tools_dir = Path(__file__).parent
            self.auto_discover(tools_dir).build_task_tool()
            self._initialized = True

    def get_tools(self, scope: str = "all") -> list:
        """
        获取工具列表

        Args:
            scope: "main" | "subagent" | "all"
                - "main": 返回 main agent 可用的工具（包括 both 和 main）
                - "subagent": 返回 subagent 可用的工具（包括 both，排除 main-only）
                - "all": 返回所有工具

        Returns:
            工具列表
        """
        self._ensure_initialized()

        if scope == "all":
            return list(self._tools.values())

        filtered = []
        for tool in self._tools.values():
            # 从 tags 中提取 scope
            tags = getattr(tool, "tags", [])
            if "main" in tags:
                tool_scope = "main"
            elif "subagent" in tags:
                tool_scope = "subagent"
            else:
                tool_scope = "both"

            if tool_scope == "both":
                filtered.append(tool)
            elif scope == "main" and tool_scope == "main":
                filtered.append(tool)
            elif scope == "subagent" and tool_scope == "subagent":
                filtered.append(tool)

        return filtered

    def get_main_tools(self) -> list:
        """获取 main agent 工具（包括 both 和 main-only）"""
        return self.get_tools(scope="main")

    def get_subagent_tools(self) -> list:
        """获取 subagent 工具（包括 both，排除 main-only）"""
        return self.get_tools(scope="subagent")

    def get(self, name: str):
        self._ensure_initialized()
        return self._tools.get(name)

    @property
    def tools_map(self) -> dict:
        self._ensure_initialized()
        return dict(self._tools)


tool_manager = ToolsManager()
