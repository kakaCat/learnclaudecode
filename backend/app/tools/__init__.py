from pathlib import Path
from backend.app.tools_manager import tools_manager

tools_manager.auto_discover(Path(__file__).parent).build_task_tool()

# 向后兼容
TOOLS = tools_manager.get_tools()
TOOLS_MAP = tools_manager.tools_map
