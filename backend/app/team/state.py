import json
import threading
from pathlib import Path

from backend.app.team.message_bus import MessageBus
from backend.app.team.teammate_manager import TeammateManager
from backend.app.task import TaskStatus

_bus: "MessageBus | None" = None
_team: "TeammateManager | None" = None

# -- Request trackers: correlate by request_id --
shutdown_requests: dict = {}
plan_requests: dict = {}
tracker_lock = threading.Lock()
claim_lock = threading.Lock()

POLL_INTERVAL = 5
IDLE_TIMEOUT = 60


def get_board_dir() -> Path:
    from backend.app.session import get_board_dir as _get_board_dir
    return _get_board_dir()


def scan_unclaimed_tasks() -> list:
    board = get_board_dir()
    unclaimed = []
    for f in sorted(board.glob("task_*.json")):
        task = json.loads(f.read_text())
        if task.get("status") == TaskStatus.PENDING and not task.get("owner") and not task.get("blockedBy"):
            unclaimed.append(task)
    return unclaimed


def claim_task(task_id: int, owner: str) -> str:
    from backend.app.session import get_board_task_path
    board = get_board_dir()
    with claim_lock:
        path = get_board_task_path(task_id)
        if not path.exists():
            return f"Error: Task {task_id} not found"
        task = json.loads(path.read_text())
        if task.get("owner"):
            return f"Error: Task {task_id} already claimed by {task['owner']}"
        task["owner"] = owner
        task["status"] = TaskStatus.IN_PROGRESS
        path.write_text(json.dumps(task, indent=2))
    return f"Claimed task #{task_id} for {owner}"


def _get_team_dir() -> Path:
    from backend.app.session import get_team_dir
    return get_team_dir()


def get_bus() -> MessageBus:
    global _bus
    if _bus is None:
        _bus = MessageBus(_get_team_dir() / "inbox")
    return _bus


def get_team() -> TeammateManager:
    global _team
    if _team is None:
        _team = TeammateManager(_get_team_dir())
    return _team
