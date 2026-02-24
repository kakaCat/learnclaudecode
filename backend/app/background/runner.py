import subprocess
import threading
import uuid

from backend.app.tools.base import WORKDIR

_tasks: dict = {}
_notification_queue: list = []
_lock = threading.Lock()


def execute(task_id: str, command: str):
    try:
        r = subprocess.run(command, shell=True, cwd=WORKDIR,
                           capture_output=True, text=True, timeout=300)
        output = (r.stdout + r.stderr).strip()[:50000]
        status = "completed"
    except subprocess.TimeoutExpired:
        output = "Error: Timeout (300s)"
        status = "timeout"
    except Exception as e:
        output = f"Error: {e}"
        status = "error"
    _tasks[task_id]["status"] = status
    _tasks[task_id]["result"] = output or "(no output)"
    with _lock:
        _notification_queue.append({
            "task_id": task_id, "status": status,
            "command": command[:80],
            "result": (output or "(no output)")[:500],
        })


def run(command: str) -> str:
    task_id = str(uuid.uuid4())[:8]
    _tasks[task_id] = {"status": "running", "result": None, "command": command}
    threading.Thread(target=execute, args=(task_id, command), daemon=True).start()
    return task_id


def check(task_id: str = None) -> str:
    if task_id:
        t = _tasks.get(task_id)
        if not t:
            return f"Error: Unknown task {task_id}"
        return f"[{t['status']}] {t['command'][:60]}\n{t.get('result') or '(running)'}"
    lines = [f"{tid}: [{t['status']}] {t['command'][:60]}" for tid, t in _tasks.items()]
    return "\n".join(lines) if lines else "No background tasks."


def drain_notifications() -> list:
    with _lock:
        notifs = list(_notification_queue)
        _notification_queue.clear()
    return notifs
