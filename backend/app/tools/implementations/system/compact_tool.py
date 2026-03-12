from backend.app.tools.base import tool

from backend.app.memory.compact import request_compact


@tool(tags=["both"])
def compact(focus: str = "") -> str:
    """Trigger manual conversation compression to free up context."""
    request_compact()
    return "Compressing..."

