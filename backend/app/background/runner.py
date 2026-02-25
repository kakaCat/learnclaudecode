import subprocess
import threading
import time
import uuid

from backend.app.tools.base import WORKDIR
from backend.app import tracer

_tasks: dict = {}
_notification_queue: list = []
_lock = threading.Lock()


def execute(task_id: str, command: str):
    t_start = time.time()
    tracer.emit("background.start", task_id=task_id, command=command[:120])
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
    duration_ms = round((time.time() - t_start) * 1000)
    _tasks[task_id]["status"] = status
    _tasks[task_id]["result"] = output or "(no output)"
    tracer.emit("background.end", task_id=task_id, command=command[:120],
                status=status, duration_ms=duration_ms,
                ok=status == "completed", output=output[:300])
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


def execute_agent(task_id: str, description: str, prompt: str, subagent_type: str, base_tools: list):
    t_start = time.time()
    tracer.emit("background.agent.start", task_id=task_id, subagent_type=subagent_type, description=description[:120])
    try:
        from backend.app.subagents import run_subagent
        output = run_subagent(description, prompt, subagent_type, base_tools)
        status = "completed"
    except Exception as e:
        output = f"Error: {e}"
        status = "error"
    duration_ms = round((time.time() - t_start) * 1000)
    _tasks[task_id]["status"] = status
    _tasks[task_id]["result"] = (output or "(no output)")[:50000]
    tracer.emit("background.agent.end", task_id=task_id, status=status, duration_ms=duration_ms)
    with _lock:
        _notification_queue.append({
            "task_id": task_id, "status": status,
            "command": f"agent:{subagent_type}:{description[:60]}",
            "result": (output or "(no output)")[:500],
        })


def run_agent(description: str, prompt: str, subagent_type: str, base_tools: list) -> str:
    task_id = str(uuid.uuid4())[:8]
    _tasks[task_id] = {"status": "running", "result": None, "command": f"agent:{subagent_type}:{description[:60]}"}
    threading.Thread(target=execute_agent, args=(task_id, description, prompt, subagent_type, base_tools), daemon=True).start()
    return task_id


def drain_notifications() -> list:
    with _lock:
        notifs = list(_notification_queue)
        _notification_queue.clear()
    return notifs
