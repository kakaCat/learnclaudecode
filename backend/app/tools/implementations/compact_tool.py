from langchain_core.tools import tool

from backend.app.compact import request_compact


@tool(tags=["main"])
def compact(focus: str = "") -> str:
    """Trigger manual conversation compression to free up context."""
    request_compact()
    return "Compressing..."

