from backend.app.tools.base import tool

from backend.app.memory.compact import request_compact

__tool_config__ = {
    "tags": ["main", "team"],
    "category": "system",
    "enabled": False 
}

@tool()
def compact(focus: str = "") -> str:
    """Trigger manual conversation compression to free up context."""
    request_compact()
    return "Compressing..."

