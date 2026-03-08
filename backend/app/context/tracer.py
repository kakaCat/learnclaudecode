"""Tracer component for context management"""
import json
import threading
import time
import uuid
from pathlib import Path


class Tracer:
    """
    Structured trace logger component.

    Writes one JSON event per line to {session_dir}/trace.jsonl.
    Managed by AgentContext for proper lifecycle and session isolation.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._run_id: str | None = None
        self._session_dir_fn = None

    def set_session_dir_fn(self, fn):
        """Set function to get session directory"""
        self._session_dir_fn = fn

    def _session_dir(self) -> Path:
        if self._session_dir_fn:
            return self._session_dir_fn()
        from backend.app.session import get_session_dir
        return get_session_dir()

    def _write(self, event: dict) -> None:
        line = json.dumps(event, ensure_ascii=False, default=str)
        path = self._session_dir() / "trace.jsonl"
        with self._lock:
            with open(path, "a", encoding="utf-8") as f:
                f.write(line + "\n")

    def new_run_id(self) -> str:
        return uuid.uuid4().hex[:8]

    def set_run_id(self, rid: str) -> None:
        self._run_id = rid

    def get_run_id(self) -> str | None:
        return self._run_id

    def emit(self, event_type: str, **payload) -> None:
        self._write({"ts": round(time.time(), 3), "event": event_type, "run_id": self._run_id, **payload})


# Global singleton instance for backward compatibility
_global_tracer = Tracer()


def get_global_tracer() -> Tracer:
    """Get global tracer instance"""
    return _global_tracer


# Backward compatibility functions
def new_run_id() -> str:
    return _global_tracer.new_run_id()


def set_run_id(rid: str) -> None:
    _global_tracer.set_run_id(rid)


def get_run_id() -> str | None:
    return _global_tracer.get_run_id()


def emit(event_type: str, **payload) -> None:
    _global_tracer.emit(event_type, **payload)
