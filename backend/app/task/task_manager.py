import json
import re
import time
from enum import Enum
from pathlib import Path

from backend.app.session import get_session_dir
from backend.app import tracer


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower())[:40].strip("-")


class TaskManager:
    @property
    def dir(self) -> Path:
        d = get_session_dir() / "tasks"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _max_id(self) -> int:
        ids = [int(f.stem.split("_")[1]) for f in self.dir.glob("task_*.json")]
        return max(ids) if ids else 0

    def _find(self, task_id: int) -> Path:
        matches = list(self.dir.glob(f"task_{task_id}_*.json"))
        if not matches:
            raise ValueError(f"Task {task_id} not found")
        return matches[0]

    def _load(self, task_id: int) -> dict:
        return json.loads(self._find(task_id).read_text())

    def _save(self, task: dict):
        slug = _slug(task["subject"])
        for old in self.dir.glob(f"task_{task['id']}_*.json"):
            old.unlink()
        (self.dir / f"task_{task['id']}_{slug}.json").write_text(json.dumps(task, indent=2, ensure_ascii=False))

    def exists(self, task_id: int) -> bool:
        return bool(list(self.dir.glob(f"task_{task_id}_*.json")))

    def create(self, subject: str, description: str = "") -> str:
        next_id = self._max_id() + 1
        task = {"id": next_id, "subject": subject, "description": description,
                "status": TaskStatus.PENDING, "blockedBy": [], "blocks": [], "owner": "",
                "worktree": "", "created_at": time.time(), "updated_at": time.time()}
        self._save(task)
        tracer.emit("task.create", task_id=next_id, subject=subject)
        return json.dumps(task, indent=2)

    def get(self, task_id: int) -> str:
        return json.dumps(self._load(task_id), indent=2)

    def update(self, task_id: int, status: str = None,
               add_blocked_by: list = None, add_blocks: list = None) -> str:
        task = self._load(task_id)
        old_status = task["status"]
        if status:
            if status not in TaskStatus._value2member_map_:
                raise ValueError(f"Invalid status: {status}")
            task["status"] = status
            if status == TaskStatus.COMPLETED:
                for f in self.dir.glob("task_*.json"):
                    t = json.loads(f.read_text())
                    if task_id in t.get("blockedBy", []):
                        t["blockedBy"].remove(task_id)
                        self._save(t)
        if add_blocked_by:
            task["blockedBy"] = list(set(task["blockedBy"] + add_blocked_by))
        if add_blocks:
            task["blocks"] = list(set(task["blocks"] + add_blocks))
            for bid in add_blocks:
                try:
                    b = self._load(bid)
                    if task_id not in b["blockedBy"]:
                        b["blockedBy"].append(task_id)
                        self._save(b)
                except ValueError:
                    pass
        self._save(task)
        if status and status != old_status:
            tracer.emit("task.status", task_id=task_id, subject=task["subject"],
                        from_status=old_status, to_status=status)
        return json.dumps(task, indent=2)

    def bind_worktree(self, task_id: int, worktree: str, owner: str = "") -> str:
        task = self._load(task_id)
        task["worktree"] = worktree
        if owner:
            task["owner"] = owner
        if task["status"] == TaskStatus.PENDING:
            task["status"] = TaskStatus.IN_PROGRESS
        task["updated_at"] = time.time()
        self._save(task)
        tracer.emit("task.bind_worktree", task_id=task_id, subject=task["subject"],
                    worktree=worktree, owner=owner or task.get("owner", ""))
        return json.dumps(task, indent=2)

    def unbind_worktree(self, task_id: int) -> str:
        task = self._load(task_id)
        task["worktree"] = ""
        task["updated_at"] = time.time()
        self._save(task)
        return json.dumps(task, indent=2)

    def list_all(self) -> str:
        tasks = [json.loads(f.read_text()) for f in sorted(self.dir.glob("task_*.json"))]
        if not tasks:
            return "No tasks."
        lines = []
        for t in tasks:
            marker = {TaskStatus.PENDING: "[ ]", TaskStatus.IN_PROGRESS: "[>]", TaskStatus.COMPLETED: "[x]"}.get(t["status"], "[?]")
            blocked = f" (blocked by: {t['blockedBy']})" if t.get("blockedBy") else ""
            wt = f" wt={t['worktree']}" if t.get("worktree") else ""
            lines.append(f"{marker} #{t['id']}: {t['subject']}{blocked}{wt}")
        return "\n".join(lines)
