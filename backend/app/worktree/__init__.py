from backend.app.worktree.event_bus import EventBus
from backend.app.worktree.worktree_manager import WorktreeManager
from backend.app.task import get_tasks

import subprocess
from pathlib import Path
import os

_EVENTS: EventBus | None = None
_WORKTREES: WorktreeManager | None = None


def _repo_root() -> Path:
    cwd = Path(os.getcwd())
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=cwd, capture_output=True, text=True, timeout=10,
        )
        if r.returncode == 0:
            root = Path(r.stdout.strip())
            if root.exists():
                return root
    except Exception:
        pass
    return cwd


def get_events() -> EventBus:
    global _EVENTS
    if _EVENTS is None:
        _EVENTS = EventBus(_repo_root() / ".worktrees" / "events.jsonl")
    return _EVENTS


def get_worktrees() -> WorktreeManager:
    global _WORKTREES
    if _WORKTREES is None:
        _WORKTREES = WorktreeManager(_repo_root(), get_tasks(), get_events())
    return _WORKTREES
