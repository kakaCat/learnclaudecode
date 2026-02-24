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
