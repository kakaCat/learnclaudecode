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

    def build_task_tool(self, main_context=None) -> "ToolsManager":
        """
        创建 Task 工具并注册，同时注入回调函数实现解耦

        Args:
            main_context: MainAgentContext 实例（用于创建 Subagent）
        """
        # 注入 spawn 回调函数
        from backend.app.tools.implementations.agent.spawn_tool import set_spawn_callback, Task

        def spawn_callback(description: str, prompt: str, subagent_type: str, recursion_limit: int):
            """Spawn subagent 的回调实现"""
            from backend.app.core.context.sub_context import SubContext
            from backend.app.core.execution.subagent_runner import SubagentRunner

            sub_context = SubContext(
                session_key=main_context.session_key,
                subagent_type=subagent_type,
                llm=main_context.llm,
                session_store=main_context.session_store,
                tracer=main_context.tracer,
                recursion_limit=recursion_limit
            )
            runner = SubagentRunner()
            return runner.run(
                sub_context=sub_context,
                description=description,
                prompt=prompt,
                recursion_limit=recursion_limit
            )

        set_spawn_callback(spawn_callback)
        self._task_tool = Task
        self._tools[Task.name] = Task

        # 注入 background_agent 的工具获取回调
        from backend.app.tools.implementations.execution.background_tool import set_get_tools_callback
        set_get_tools_callback(lambda: self.get_subagent_tools())

        return self

    async def load_mcp_tools(self) -> "ToolsManager":
        """异步加载 MCP 工具"""
        if self._mcp_loaded:
            return self

        try:
            from backend.app.tools.mcp.mcp_tool import get_mcp_tools
            mcp_tools = await get_mcp_tools()
            for tool in mcp_tools:
                self._tools[tool.name] = tool
            self._mcp_loaded = True
        except Exception as e:
            import logging
            logging.error(f"Failed to load MCP tools: {e}")

        return self

    def _ensure_initialized(self, main_context=None):
        """
        确保工具已初始化（延迟初始化，避免循环导入）

        Args:
            main_context: MainAgentContext 实例（用于创建 Task tool）
        """
        if not self._initialized:
            from pathlib import Path
            tools_dir = Path(__file__).parent
            self.auto_discover(tools_dir).build_task_tool(main_context)
            self._initialized = True

    def get_tools(self, scope: str = "all") -> list:
        """
        获取工具列表

        Args:
            scope: "main" | "team" | "subagent" | "all"
                - "main": 返回 main agent 可用的工具（包括 both 和 main-only）
                - "team": 返回 team agent 可用的工具（包括 both，排除 main-only，不包含通信工具）
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
            tags = getattr(tool, "tags", None) or []

            # 确定工具的 scope
            if "main" in tags:
                tool_scope = "main"
            elif "subagent" in tags:
                tool_scope = "subagent"
            elif "team" in tags:
                tool_scope = "team"
            else:
                tool_scope = "both"

            # 过滤逻辑
            if tool_scope == "both":
                # both 工具对所有 scope 可见
                filtered.append(tool)
            elif scope == "main" and tool_scope == "main":
                # main-only 工具只对 main 可见
                filtered.append(tool)
            elif scope == "team" and tool_scope == "team":
                # team-only 工具只对 team 可见
                filtered.append(tool)
            elif scope == "subagent" and tool_scope == "subagent":
                # subagent-only 工具只对 subagent 可见
                filtered.append(tool)

        return filtered

    def get_main_tools(self) -> list:
        """获取 main agent 工具（包括 both 和 main-only）"""
        return self.get_tools(scope="main")

    def get_team_tools(self) -> list:
        """获取 team agent 工具（包括 both 和 Task，排除 spawn_teammate）"""
        return self.get_tools(scope="team")

    def get_subagent_tools(self) -> list:
        """获取 subagent 工具（包括 both，排除 main-only 和 team-only）"""
        return self.get_tools(scope="subagent")

    def get(self, name: str):
        self._ensure_initialized()
        return self._tools.get(name)

    @property
    def tools_map(self) -> dict:
        self._ensure_initialized()
        return dict(self._tools)


tool_manager = ToolsManager()
