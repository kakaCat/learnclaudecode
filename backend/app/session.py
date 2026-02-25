"""
session.py - Persistent session storage for main agent and subagents.

Directory structure: .sessions/{key}/
  main.jsonl              - main agent context
  Explore.jsonl           - subagent contexts
  general-purpose.jsonl
  tasks/                  - persistent task files
    task_1.json
  transcript.jsonl        - compaction transcript
  team/                   - agent team state
    config.json
    inbox/
"""
import json
import time
from pathlib import Path

SESSIONS_DIR = Path.cwd() / ".sessions"
_current_key: str | None = None


def new_session_key() -> str:
    return time.strftime("%Y%m%d_%H%M%S")


def set_session_key(key: str) -> None:
    global _current_key
    _current_key = key
    # Reset team singletons so they re-initialize under the new session dir
    import backend.app.team.state as _ts
    _ts._bus = None
    _ts._team = None


def get_session_key() -> str | None:
    return _current_key


def get_session_dir() -> Path:
    key = _current_key or "default"
    d = SESSIONS_DIR / key
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_workspace_dir() -> Path:
    d = get_session_dir() / "workspace"
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_session(agent_name: str, history: list) -> None:
    """Write history to .sessions/{key}/{agent_name}.jsonl"""
    if not history:
        return
    path = get_session_dir() / f"{agent_name}.jsonl"
    with open(path, "w") as f:
        for msg in history:
            f.write(json.dumps(msg.model_dump(), ensure_ascii=False) + "\n")


def list_sessions() -> list[str]:
    """Return session keys sorted newest-first."""
    if not SESSIONS_DIR.exists():
        return []
    return sorted((d.name for d in SESSIONS_DIR.iterdir() if d.is_dir()), reverse=True)


def load_session(agent_name: str, key: str) -> list:
    """Load history from .sessions/{key}/{agent_name}.jsonl as LangChain messages."""
    from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
    _type_map = {"human": HumanMessage, "ai": AIMessage, "tool": ToolMessage}
    _keep = {
        "human": {"content", "additional_kwargs"},
        "ai": {"content", "additional_kwargs", "tool_calls", "invalid_tool_calls"},
        "tool": {"content", "tool_call_id"},
    }
    path = SESSIONS_DIR / key / f"{agent_name}.jsonl"
    if not path.exists():
        return []
    history = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            data = json.loads(line)
            msg_type = data.get("type")
            cls = _type_map.get(msg_type)
            if cls:
                fields = {k: v for k, v in data.items() if k in _keep.get(msg_type, set())}
                history.append(cls(**fields))
        except Exception:
            continue
    return history
