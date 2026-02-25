"""
Structured trace logger for AI agent observability.

Writes one JSON event per line to {session_dir}/trace.jsonl.

Event schema (all events):
  ts        float   Unix timestamp (ms precision)
  event     str     Event type (see below)
  run_id    str     Current run identifier (hex8)

Event types & extra fields:
  run.start          prompt, session
  run.end            output, turns, total_tools, duration_ms
  llm.turn           turn, msg_count, decisions:[{tool,args}] | direct_answer:true
  tool.call          turn, tool, args, call_id
  tool.result        turn, tool, call_id, duration_ms, ok, output
  compaction         kind (micro|auto|manual), note
  subagent.start     span_id, agent_type, description
  subagent.llm.turn  span_id, agent_type, turn, decisions:[{tool,args}]
  subagent.tool.call span_id, agent_type, tool, args, call_id
  subagent.tool.result span_id, agent_type, tool, call_id, duration_ms, ok, output
  subagent.end       span_id, agent_type, tool_count, duration_ms, output
  teammate.spawn     name, role
  teammate.tool.call name, tool, args
  teammate.tool.result name, tool, duration_ms, ok, output
  teammate.status    name, status
"""
import json
import threading
import time
import uuid
from pathlib import Path

_lock = threading.Lock()
_run_id: str | None = None


def _session_dir() -> Path:
    from backend.app.session import get_session_dir
    return get_session_dir()


def _write(event: dict) -> None:
    line = json.dumps(event, ensure_ascii=False, default=str)
    path = _session_dir() / "trace.jsonl"
    with _lock:
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")


def new_run_id() -> str:
    return uuid.uuid4().hex[:8]


def set_run_id(rid: str) -> None:
    global _run_id
    _run_id = rid


def get_run_id() -> str | None:
    return _run_id


def emit(event_type: str, **payload) -> None:
    _write({"ts": round(time.time(), 3), "event": event_type, "run_id": _run_id, **payload})
