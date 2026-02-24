from langchain_core.tools import tool
from backend.app.session import get_workspace_dir


def _resolve(path: str):
    ws = get_workspace_dir().resolve()
    fp = (ws / path).resolve()
    if not str(fp).startswith(str(ws)):
        raise ValueError("Path escapes workspace")
    return fp


@tool
def workspace_write(path: str, content: str) -> str:
    """Write a file to the session workspace (for AI intermediate outputs). Path is relative to workspace/."""
    try:
        fp = _resolve(path)
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content)
        return f"Wrote {len(content)} bytes to workspace/{path}"
    except Exception as e:
        return f"Error: {e}"


@tool
def workspace_read(path: str) -> str:
    """Read a file from the session workspace."""
    try:
        return _resolve(path).read_text()
    except Exception as e:
        return f"Error: {e}"


@tool
def workspace_list() -> str:
    """List all files in the session workspace."""
    try:
        ws = get_workspace_dir()
        files = sorted(ws.rglob("*"))
        if not files:
            return f"Workspace empty: {ws}"
        return "\n".join(str(f.relative_to(ws)) for f in files if f.is_file())
    except Exception as e:
        return f"Error: {e}"
