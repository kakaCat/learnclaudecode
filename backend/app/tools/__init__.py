from pathlib import Path
from backend.app.tools.manager import tool_manager

# 延迟初始化，避免循环导入
_initialized = False

def _ensure_initialized():
    global _initialized
    if not _initialized:
        tool_manager.auto_discover(Path(__file__).parent).build_task_tool()
        _initialized = True

# 向后兼容 - 使用属性访问时才初始化
def __getattr__(name):
    if name in ("TOOLS", "TOOLS_MAP"):
        _ensure_initialized()
        if name == "TOOLS":
            return tool_manager.get_tools()
        elif name == "TOOLS_MAP":
            return tool_manager.tools_map
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
