#!/usr/bin/env python3
"""
v8_agent.py - Mini Claude Code: 21 Tools + Todos + Subagents + Skills + Compaction + Persistent Tasks + Background Tasks + Agent Teams

v7_agent + Agent Teams
===================================

v7_agent: 16 tools + background_run + check_background
v8_agent: 21 tools + spawn_teammate + list_teammates + send_message + read_inbox + broadcast

Persistent named agents with file-based JSONL inboxes. Each teammate runs
its own agent loop in a separate thread.

Key insight: "Teammates that can talk to each other."
"""

import json
import os
import re
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv(override=True)

if os.getenv("ANTHROPIC_BASE_URL"):
    os.environ.pop("ANTHROPIC_AUTH_TOKEN", None)

WORKDIR = Path.cwd()
MODEL = os.getenv("MODEL_ID", "claude-sonnet-4-5-20250929")
client = Anthropic(base_url=os.getenv("ANTHROPIC_BASE_URL"))
SKILLS_DIR = WORKDIR / ".skills"
SESSIONS_DIR = WORKDIR / ".sessions"
SESSION_KEY = time.strftime("%Y%m%d_%H%M%S")
SESSION_DIR = SESSIONS_DIR / SESSION_KEY
TASKS_DIR = SESSION_DIR / "tasks"
TEAM_DIR = SESSION_DIR / "team"
INBOX_DIR = TEAM_DIR / "inbox"

VALID_MSG_TYPES = {"message", "broadcast", "shutdown_request", "shutdown_response", "plan_approval_response"}

THRESHOLD = 50000
TRANSCRIPT_DIR = SESSION_DIR / "transcripts"
KEEP_RECENT = 3


# =============================================================================
# SkillLoader
# =============================================================================

class SkillLoader:
    def __init__(self, skills_dir: Path):
        self.skills_dir = skills_dir
        self.skills = {}
        self._load_all()

    def _load_all(self):
        if not self.skills_dir.exists():
            return
        for f in sorted(self.skills_dir.glob("*.md")):
            name = f.stem
            text = f.read_text()
            meta, body = self._parse_frontmatter(text)
            self.skills[name] = {"meta": meta, "body": body}

    def _parse_frontmatter(self, text: str) -> tuple:
        match = re.match(r"^---\n(.*?)\n---\n(.*)", text, re.DOTALL)
        if not match:
            return {}, text
        meta = {}
        for line in match.group(1).strip().splitlines():
            if ":" in line:
                key, val = line.split(":", 1)
                meta[key.strip()] = val.strip()
        return meta, match.group(2).strip()

    def get_descriptions(self) -> str:
        if not self.skills:
            return "(no skills available)"
        lines = []
        for name, skill in self.skills.items():
            desc = skill["meta"].get("description", "No description")
            tags = skill["meta"].get("tags", "")
            line = f"  - {name}: {desc}"
            if tags:
                line += f" [{tags}]"
            lines.append(line)
        return "\n".join(lines)

    def get_content(self, name: str) -> str:
        skill = self.skills.get(name)
        if not skill:
            return f"Error: Unknown skill '{name}'. Available: {', '.join(self.skills.keys()) or 'none'}"
        return f'<skill name="{name}">\n{skill["body"]}\n</skill>'


SKILL_LOADER = SkillLoader(SKILLS_DIR)


# =============================================================================
# TaskManager (persistent, survives context compression)
# =============================================================================

class TaskManager:
    def __init__(self, tasks_dir: Path):
        self.dir = tasks_dir
        self.dir.mkdir(exist_ok=True)
        self._next_id = self._max_id() + 1

    def _max_id(self) -> int:
        ids = [int(f.stem.split("_")[1]) for f in self.dir.glob("task_*.json")]
        return max(ids) if ids else 0

    def _load(self, task_id: int) -> dict:
        path = self.dir / f"task_{task_id}.json"
        if not path.exists():
            raise ValueError(f"Task {task_id} not found")
        return json.loads(path.read_text())

    def _save(self, task: dict):
        (self.dir / f"task_{task['id']}.json").write_text(json.dumps(task, indent=2))

    def create(self, subject: str, description: str = "") -> str:
        task = {"id": self._next_id, "subject": subject, "description": description,
                "status": "pending", "blockedBy": [], "blocks": [], "owner": ""}
        self._save(task)
        self._next_id += 1
        return json.dumps(task, indent=2)

    def get(self, task_id: int) -> str:
        return json.dumps(self._load(task_id), indent=2)

    def update(self, task_id: int, status: str = None,
               add_blocked_by: list = None, add_blocks: list = None) -> str:
        task = self._load(task_id)
        if status:
            if status not in ("pending", "in_progress", "completed"):
                raise ValueError(f"Invalid status: {status}")
            task["status"] = status
            if status == "completed":
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
        return json.dumps(task, indent=2)

    def list_all(self) -> str:
        tasks = [json.loads(f.read_text()) for f in sorted(self.dir.glob("task_*.json"))]
        if not tasks:
            return "No tasks."
        lines = []
        for t in tasks:
            marker = {"pending": "[ ]", "in_progress": "[>]", "completed": "[x]"}.get(t["status"], "[?]")
            blocked = f" (blocked by: {t['blockedBy']})" if t.get("blockedBy") else ""
            lines.append(f"{marker} #{t['id']}: {t['subject']}{blocked}")
        return "\n".join(lines)


TASKS = TaskManager(TASKS_DIR)


# =============================================================================
# BackgroundManager (fire-and-forget threaded execution)
# =============================================================================

class BackgroundManager:
    def __init__(self):
        self.tasks = {}
        self._notification_queue = []
        self._lock = threading.Lock()

    def run(self, command: str) -> str:
        task_id = str(uuid.uuid4())[:8]
        self.tasks[task_id] = {"status": "running", "result": None, "command": command}
        threading.Thread(target=self._execute, args=(task_id, command), daemon=True).start()
        return f"Background task {task_id} started: {command[:80]}"

    def _execute(self, task_id: str, command: str):
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
        self.tasks[task_id]["status"] = status
        self.tasks[task_id]["result"] = output or "(no output)"
        with self._lock:
            self._notification_queue.append({
                "task_id": task_id, "status": status,
                "command": command[:80],
                "result": (output or "(no output)")[:500],
            })

    def check(self, task_id: str = None) -> str:
        if task_id:
            t = self.tasks.get(task_id)
            if not t:
                return f"Error: Unknown task {task_id}"
            return f"[{t['status']}] {t['command'][:60]}\n{t.get('result') or '(running)'}"
        lines = [f"{tid}: [{t['status']}] {t['command'][:60]}" for tid, t in self.tasks.items()]
        return "\n".join(lines) if lines else "No background tasks."

    def drain_notifications(self) -> list:
        with self._lock:
            notifs = list(self._notification_queue)
            self._notification_queue.clear()
        return notifs


BG = BackgroundManager()


# =============================================================================
# MessageBus (JSONL inbox per teammate)
# =============================================================================

class MessageBus:
    def __init__(self, inbox_dir: Path):
        self.dir = inbox_dir
        self.dir.mkdir(parents=True, exist_ok=True)

    def send(self, sender: str, to: str, content: str,
             msg_type: str = "message", extra: dict = None) -> str:
        if msg_type not in VALID_MSG_TYPES:
            return f"Error: Invalid type '{msg_type}'. Valid: {VALID_MSG_TYPES}"
        msg = {"type": msg_type, "from": sender, "content": content, "timestamp": time.time()}
        if extra:
            msg.update(extra)
        with open(self.dir / f"{to}.jsonl", "a") as f:
            f.write(json.dumps(msg) + "\n")
        return f"Sent {msg_type} to {to}"

    def read_inbox(self, name: str) -> list:
        inbox_path = self.dir / f"{name}.jsonl"
        if not inbox_path.exists():
            return []
        messages = [json.loads(l) for l in inbox_path.read_text().strip().splitlines() if l]
        inbox_path.write_text("")
        return messages

    def broadcast(self, sender: str, content: str, teammates: list) -> str:
        count = sum(1 for name in teammates if name != sender and not self.send(sender, name, content, "broadcast").startswith("Error"))
        return f"Broadcast to {count} teammates"


BUS = MessageBus(INBOX_DIR)


# =============================================================================
# TeammateManager (persistent named agents)
# =============================================================================

class TeammateManager:
    def __init__(self, team_dir: Path):
        self.dir = team_dir
        self.dir.mkdir(exist_ok=True)
        self.config_path = self.dir / "config.json"
        self.config = json.loads(self.config_path.read_text()) if self.config_path.exists() else {"team_name": "default", "members": []}
        self.threads = {}

    def _find(self, name: str) -> dict:
        return next((m for m in self.config["members"] if m["name"] == name), None)

    def _save(self):
        self.config_path.write_text(json.dumps(self.config, indent=2))

    def spawn(self, name: str, role: str, prompt: str) -> str:
        member = self._find(name)
        if member:
            if member["status"] not in ("idle", "shutdown"):
                return f"Error: '{name}' is currently {member['status']}"
            member.update({"status": "working", "role": role})
        else:
            member = {"name": name, "role": role, "status": "working"}
            self.config["members"].append(member)
        self._save()
        t = threading.Thread(target=self._loop, args=(name, role, prompt), daemon=True)
        self.threads[name] = t
        t.start()
        return f"Spawned '{name}' (role: {role})"

    def _loop(self, name: str, role: str, prompt: str):
        sys_prompt = f"You are '{name}', role: {role}, at {WORKDIR}. Use send_message to communicate. Complete your task."
        messages = [{"role": "user", "content": prompt}]
        tools = [
            {"name": "bash", "description": "Run a shell command.",
             "input_schema": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}},
            {"name": "read_file", "description": "Read file contents.",
             "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
            {"name": "write_file", "description": "Write content to file.",
             "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}},
            {"name": "edit_file", "description": "Replace exact text in file.",
             "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}}, "required": ["path", "old_text", "new_text"]}},
            {"name": "send_message", "description": "Send message to a teammate.",
             "input_schema": {"type": "object", "properties": {"to": {"type": "string"}, "content": {"type": "string"}, "msg_type": {"type": "string", "enum": list(VALID_MSG_TYPES)}}, "required": ["to", "content"]}},
            {"name": "read_inbox", "description": "Read and drain your inbox.",
             "input_schema": {"type": "object", "properties": {}}},
        ]
        for _ in range(50):
            for msg in BUS.read_inbox(name):
                messages.append({"role": "user", "content": json.dumps(msg)})
            try:
                response = client.messages.create(model=MODEL, system=sys_prompt, messages=messages, tools=tools, max_tokens=8000)
            except Exception:
                break
            messages.append({"role": "assistant", "content": response.content})
            if response.stop_reason != "tool_use":
                break
            results = []
            for block in response.content:
                if block.type == "tool_use":
                    output = self._exec(name, block.name, block.input)
                    print(f"  [{name}] {block.name}: {str(output)[:120]}")
                    results.append({"type": "tool_result", "tool_use_id": block.id, "content": str(output)})
            messages.append({"role": "user", "content": results})
        member = self._find(name)
        if member and member["status"] != "shutdown":
            member["status"] = "idle"
            self._save()

    def _exec(self, sender: str, tool_name: str, args: dict) -> str:
        if tool_name == "bash":        return run_bash(args["command"])
        if tool_name == "read_file":   return run_read(args["path"])
        if tool_name == "write_file":  return run_write(args["path"], args["content"])
        if tool_name == "edit_file":   return run_edit(args["path"], args["old_text"], args["new_text"])
        if tool_name == "send_message": return BUS.send(sender, args["to"], args["content"], args.get("msg_type", "message"))
        if tool_name == "read_inbox":  return json.dumps(BUS.read_inbox(sender), indent=2)
        return f"Unknown tool: {tool_name}"

    def list_all(self) -> str:
        if not self.config["members"]:
            return "No teammates."
        lines = [f"Team: {self.config['team_name']}"]
        for m in self.config["members"]:
            lines.append(f"  {m['name']} ({m['role']}): {m['status']}")
        return "\n".join(lines)

    def member_names(self) -> list:
        return [m["name"] for m in self.config["members"]]


TEAM = TeammateManager(TEAM_DIR)

# =============================================================================
# Agent Type Registry
# =============================================================================

AGENT_TYPES = {
    "Explore": {
        "description": "Read-only agent for exploring code, finding files, searching",
        "tools": ["bash", "read_file", "glob", "grep", "list_dir"],
        "prompt": "You are an exploration agent. Search and analyze, but never modify files. Return a concise summary.",
    },
    "general-purpose": {
        "description": "Full agent for implementing features and fixing bugs",
        "tools": "*",
        "prompt": "You are a coding agent. Implement the requested changes efficiently.",
    },
    "Plan": {
        "description": "Planning agent for designing implementation strategies",
        "tools": ["bash", "read_file", "glob", "grep", "list_dir"],
        "prompt": "You are a planning agent. Analyze the codebase and output a numbered implementation plan. Do NOT make changes.",
    },
}


def get_agent_descriptions() -> str:
    return "\n".join(f"- {name}: {cfg['description']}" for name, cfg in AGENT_TYPES.items())


SYSTEM = f"""You are a coding agent at {WORKDIR}.

Loop: plan -> act with tools -> update todos -> report.

You can spawn subagents for complex subtasks:
{get_agent_descriptions()}

Use load_skill to access specialized knowledge before tackling unfamiliar topics.

Skills available:
{SKILL_LOADER.get_descriptions()}

Persistent tasks (survive context compression) are in .tasks/ - use task_* tools for multi-session work.

Agent teams: when multiple subtasks need parallel persistent collaboration (e.g. coder + reviewer + tester), use spawn_teammate to create persistent teammates that run in their own threads and can interact over multiple rounds. Use send_message/read_inbox/broadcast to communicate, list_teammates to check status. Difference from Task: Task is a one-shot isolated subtask; teammate is a persistent thread for multi-round interaction.

Rules:
- Use Task tool for subtasks that need focused exploration or implementation
- Use TodoWrite to track multi-step work within a session
- Use task_create/task_update for work that must survive context compression
- Use glob/grep/list_dir to explore. Use bash only for execution (run tests, git, npm).
- Never invent file paths. Explore first if unsure.
- Make minimal changes. Don't over-engineer.
- After finishing, summarize what changed."""

INITIAL_REMINDER = "<reminder>Use TodoWrite for multi-step tasks.</reminder>"
NAG_REMINDER = "<reminder>10+ turns without todo update. Please update todos.</reminder>"


# =============================================================================
# TodoManager
# =============================================================================

class TodoManager:
    def __init__(self):
        self.items = []

    def update(self, items: list) -> str:
        validated = []
        in_progress_count = 0
        for i, item in enumerate(items):
            content = str(item.get("content", "")).strip()
            status = str(item.get("status", "pending")).lower()
            active_form = str(item.get("activeForm", "")).strip()
            if not content:
                raise ValueError(f"Item {i}: content required")
            if status not in ("pending", "in_progress", "completed"):
                raise ValueError(f"Item {i}: invalid status '{status}'")
            if not active_form:
                raise ValueError(f"Item {i}: activeForm required")
            if status == "in_progress":
                in_progress_count += 1
            validated.append({"content": content, "status": status, "activeForm": active_form})
        if len(validated) > 20:
            raise ValueError("Max 20 todos allowed")
        if in_progress_count > 1:
            raise ValueError("Only one task can be in_progress at a time")
        self.items = validated
        lines = []
        for item in self.items:
            if item["status"] == "completed":
                lines.append(f"[x] {item['content']}")
            elif item["status"] == "in_progress":
                lines.append(f"[>] {item['content']} <- {item['activeForm']}")
            else:
                lines.append(f"[ ] {item['content']}")
        completed = sum(1 for t in self.items if t["status"] == "completed")
        lines.append(f"\n({completed}/{len(self.items)} completed)")
        return "\n".join(lines)


TODO = TodoManager()


# =============================================================================
# Context Compaction
# =============================================================================

def estimate_tokens(messages: list) -> int:
    return len(str(messages)) // 4


def micro_compact(messages: list) -> list:
    tool_results = []
    for msg_idx, msg in enumerate(messages):
        if msg["role"] == "user" and isinstance(msg.get("content"), list):
            for part_idx, part in enumerate(msg["content"]):
                if isinstance(part, dict) and part.get("type") == "tool_result":
                    tool_results.append((msg_idx, part_idx, part))
    if len(tool_results) <= KEEP_RECENT:
        return messages
    tool_name_map = {}
    for msg in messages:
        if msg["role"] == "assistant":
            content = msg.get("content", [])
            if isinstance(content, list):
                for block in content:
                    if hasattr(block, "type") and block.type == "tool_use":
                        tool_name_map[block.id] = block.name
    to_clear = tool_results[:-KEEP_RECENT]
    for _, _, result in to_clear:
        if isinstance(result.get("content"), str) and len(result["content"]) > 100:
            tool_id = result.get("tool_use_id", "")
            tool_name = tool_name_map.get(tool_id, "unknown")
            result["content"] = f"[Previous: used {tool_name}]"
    return messages


def auto_compact(messages: list) -> list:
    TRANSCRIPT_DIR.mkdir(exist_ok=True)
    transcript_path = TRANSCRIPT_DIR / f"transcript_{int(time.time())}.jsonl"
    with open(transcript_path, "w") as f:
        for msg in messages:
            f.write(json.dumps(msg, default=str) + "\n")
    print(f"[transcript saved: {transcript_path}]")
    conversation_text = json.dumps(messages, default=str)[:80000]
    response = client.messages.create(
        model=MODEL,
        messages=[{"role": "user", "content":
            "Summarize this conversation for continuity. Include: "
            "1) What was accomplished, 2) Current state, 3) Key decisions made. "
            "Be concise but preserve critical details.\n\n" + conversation_text}],
        max_tokens=2000,
    )
    summary = response.content[0].text
    return [
        {"role": "user", "content": f"[Conversation compressed. Transcript: {transcript_path}]\n\n{summary}"},
        {"role": "assistant", "content": "Understood. I have the context from the summary. Continuing."},
    ]


# =============================================================================
# Tool Implementations
# =============================================================================

def safe_path(p: str) -> Path:
    path = (WORKDIR / p).resolve()
    if not path.is_relative_to(WORKDIR):
        raise ValueError(f"Path escapes workspace: {p}")
    return path


def run_bash(command: str) -> str:
    dangerous = ["rm -rf /", "sudo", "shutdown", "reboot", "> /dev/"]
    if any(d in command for d in dangerous):
        return "Error: Dangerous command blocked"
    try:
        result = subprocess.run(command, shell=True, cwd=WORKDIR,
                                capture_output=True, text=True, timeout=120)
        output = (result.stdout + result.stderr).strip()
        return output[:50000] if output else "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: Command timed out (120s)"
    except Exception as e:
        return f"Error: {e}"


def run_read(path: str, limit: int = None) -> str:
    try:
        text = safe_path(path).read_text()
        lines = text.splitlines()
        if limit and limit < len(lines):
            lines = lines[:limit]
            lines.append(f"... ({len(text.splitlines()) - limit} more lines)")
        return "\n".join(lines)[:50000]
    except Exception as e:
        return f"Error: {e}"


def run_write(path: str, content: str) -> str:
    try:
        fp = safe_path(path)
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content)
        return f"Wrote {len(content)} bytes to {path}"
    except Exception as e:
        return f"Error: {e}"


def run_edit(path: str, old_text: str, new_text: str) -> str:
    try:
        fp = safe_path(path)
        content = fp.read_text()
        if old_text not in content:
            return f"Error: Text not found in {path}"
        fp.write_text(content.replace(old_text, new_text, 1))
        return f"Edited {path}"
    except Exception as e:
        return f"Error: {e}"


def run_glob(pattern: str, dir: str = None) -> str:
    try:
        base = safe_path(dir) if dir else WORKDIR
        matches = sorted(base.rglob(pattern) if "**" in pattern else base.glob(pattern))
        files = [str(p.relative_to(WORKDIR)) for p in matches if p.is_file()]
        return "\n".join(files[:500]) if files else "(no matches)"
    except Exception as e:
        return f"Error: {e}"


def run_grep(pattern: str, dir: str = None, glob: str = None) -> str:
    try:
        base = safe_path(dir) if dir else WORKDIR
        file_glob = glob or "*"
        results = []
        for filepath in sorted(base.rglob(file_glob)):
            if not filepath.is_file():
                continue
            try:
                text = filepath.read_text(errors="ignore")
            except Exception:
                continue
            for lineno, line in enumerate(text.splitlines(), 1):
                if re.search(pattern, line):
                    rel = filepath.relative_to(WORKDIR)
                    results.append(f"{rel}:{lineno}:{line.rstrip()}")
                    if len(results) >= 200:
                        results.append("... (truncated at 200 matches)")
                        return "\n".join(results)
        return "\n".join(results) if results else "(no matches)"
    except Exception as e:
        return f"Error: {e}"


def run_list_dir(path: str = None) -> str:
    try:
        target = safe_path(path) if path else WORKDIR
        if not target.is_dir():
            return f"Error: Not a directory: {path}"
        lines = []
        for item in sorted(target.iterdir()):
            if item.is_dir():
                lines.append(f"  [dir]  {item.name}/")
            else:
                size = item.stat().st_size
                lines.append(f"  [file] {item.name}  {size:>8,} B")
        return f"{target.relative_to(WORKDIR) if path else './'}\n" + "\n".join(lines)
    except Exception as e:
        return f"Error: {e}"


def run_todo(items: list) -> str:
    try:
        return TODO.update(items)
    except Exception as e:
        return f"Error: {e}"


# =============================================================================
# Tool Definitions
# =============================================================================

BASE_TOOLS = [
    {"name": "bash", "description": "Run a shell command. Use for: git, npm, python, running tests. NOT for file exploration.",
     "input_schema": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}},
    {"name": "read_file", "description": "Read file contents.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["path"]}},
    {"name": "write_file", "description": "Write content to a file.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}},
    {"name": "edit_file", "description": "Replace exact text in a file. old_text must match verbatim.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}}, "required": ["path", "old_text", "new_text"]}},
    {"name": "glob", "description": "Find files matching a pattern.",
     "input_schema": {"type": "object", "properties": {"pattern": {"type": "string"}, "dir": {"type": "string"}}, "required": ["pattern"]}},
    {"name": "grep", "description": "Search for a pattern in files. Returns file:line:content matches.",
     "input_schema": {"type": "object", "properties": {"pattern": {"type": "string"}, "dir": {"type": "string"}, "glob": {"type": "string"}}, "required": ["pattern"]}},
    {"name": "list_dir", "description": "List directory contents with file sizes and types.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": []}},
    {"name": "TodoWrite", "description": "Update the in-session task list.",
     "input_schema": {"type": "object", "properties": {"items": {"type": "array", "items": {"type": "object", "properties": {"content": {"type": "string"}, "status": {"type": "string", "enum": ["pending", "in_progress", "completed"]}, "activeForm": {"type": "string"}}, "required": ["content", "status", "activeForm"]}}}, "required": ["items"]}},
    {"name": "load_skill", "description": "Load specialized knowledge by name.",
     "input_schema": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}},
    {"name": "compact", "description": "Trigger manual conversation compression to free up context.",
     "input_schema": {"type": "object", "properties": {"focus": {"type": "string"}}}},
    {"name": "task_create", "description": "Create a persistent task (survives context compression). Stored in .tasks/.",
     "input_schema": {"type": "object", "properties": {"subject": {"type": "string"}, "description": {"type": "string"}}, "required": ["subject"]}},
    {"name": "task_update", "description": "Update a persistent task's status or dependencies.",
     "input_schema": {"type": "object", "properties": {"task_id": {"type": "integer"}, "status": {"type": "string", "enum": ["pending", "in_progress", "completed"]}, "addBlockedBy": {"type": "array", "items": {"type": "integer"}}, "addBlocks": {"type": "array", "items": {"type": "integer"}}}, "required": ["task_id"]}},
    {"name": "task_list", "description": "List all persistent tasks with status summary.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "task_get", "description": "Get full details of a persistent task by ID.",
     "input_schema": {"type": "object", "properties": {"task_id": {"type": "integer"}}, "required": ["task_id"]}},
    {"name": "background_run", "description": "Run command in background thread. Returns task_id immediately. Use for long-running commands.",
     "input_schema": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}},
    {"name": "check_background", "description": "Check background task status. Omit task_id to list all.",
     "input_schema": {"type": "object", "properties": {"task_id": {"type": "string"}}}},
    {"name": "spawn_teammate", "description": "Spawn a persistent teammate agent in its own thread.",
     "input_schema": {"type": "object", "properties": {"name": {"type": "string"}, "role": {"type": "string"}, "prompt": {"type": "string"}}, "required": ["name", "role", "prompt"]}},
    {"name": "list_teammates", "description": "List all teammates with name, role, status.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "send_message", "description": "Send a message to a teammate's inbox.",
     "input_schema": {"type": "object", "properties": {"to": {"type": "string"}, "content": {"type": "string"}, "msg_type": {"type": "string", "enum": list(VALID_MSG_TYPES)}}, "required": ["to", "content"]}},
    {"name": "read_inbox", "description": "Read and drain the lead's inbox.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "broadcast", "description": "Send a message to all teammates.",
     "input_schema": {"type": "object", "properties": {"content": {"type": "string"}}, "required": ["content"]}},
]

TASK_TOOL = {
    "name": "Task",
    "description": f"""Spawn a subagent for a focused subtask. Subagents run in ISOLATED context.

Agent types:
{get_agent_descriptions()}
""",
    "input_schema": {
        "type": "object",
        "properties": {
            "description": {"type": "string"},
            "prompt": {"type": "string"},
            "subagent_type": {"type": "string", "enum": list(AGENT_TYPES.keys())},
        },
        "required": ["description", "prompt", "subagent_type"],
    },
}

ALL_TOOLS = BASE_TOOLS + [TASK_TOOL]


def get_tools_for_agent(agent_type: str) -> list:
    allowed = AGENT_TYPES.get(agent_type, {}).get("tools", "*")
    excluded = {"compact", "task_create", "task_update", "task_list", "task_get"}
    if allowed == "*":
        return [t for t in BASE_TOOLS if t["name"] not in excluded]
    return [t for t in BASE_TOOLS if t["name"] in allowed]


# =============================================================================
# Subagent Execution
# =============================================================================

def run_task(description: str, prompt: str, subagent_type: str) -> str:
    if subagent_type not in AGENT_TYPES:
        return f"Error: Unknown agent type '{subagent_type}'"
    config = AGENT_TYPES[subagent_type]
    sub_system = f"You are a {subagent_type} subagent at {WORKDIR}.\n\n{config['prompt']}\n\nComplete the task and return a clear, concise summary."
    sub_tools = get_tools_for_agent(subagent_type)
    sub_messages = [{"role": "user", "content": prompt}]
    print(f"  [{subagent_type}] {description}")
    start = time.time()
    tool_count = 0
    while True:
        response = client.messages.create(
            model=MODEL, system=sub_system, messages=sub_messages,
            tools=sub_tools, max_tokens=8000,
        )
        if response.stop_reason != "tool_use":
            break
        tool_calls = [b for b in response.content if b.type == "tool_use"]
        results = []
        for tc in tool_calls:
            tool_count += 1
            output = execute_tool(tc.name, tc.input)
            results.append({"type": "tool_result", "tool_use_id": tc.id, "content": output})
            elapsed = time.time() - start
            sys.stdout.write(f"\r  [{subagent_type}] {description} ... {tool_count} tools, {elapsed:.1f}s")
            sys.stdout.flush()
        sub_messages.append({"role": "assistant", "content": response.content})
        sub_messages.append({"role": "user", "content": results})
    elapsed = time.time() - start
    sys.stdout.write(f"\r  [{subagent_type}] {description} - done ({tool_count} tools, {elapsed:.1f}s)\n")
    for block in response.content:
        if hasattr(block, "text"):
            return block.text
    return "(subagent returned no text)"


def execute_tool(name: str, args: dict) -> str:
    if name == "bash":          return run_bash(args["command"])
    if name == "read_file":     return run_read(args["path"], args.get("limit"))
    if name == "write_file":    return run_write(args["path"], args["content"])
    if name == "edit_file":     return run_edit(args["path"], args["old_text"], args["new_text"])
    if name == "glob":          return run_glob(args["pattern"], args.get("dir"))
    if name == "grep":          return run_grep(args["pattern"], args.get("dir"), args.get("glob"))
    if name == "list_dir":      return run_list_dir(args.get("path"))
    if name == "TodoWrite":     return run_todo(args["items"])
    if name == "load_skill":    return SKILL_LOADER.get_content(args["name"])
    if name == "Task":          return run_task(args["description"], args["prompt"], args["subagent_type"])
    if name == "task_create":   return TASKS.create(args["subject"], args.get("description", ""))
    if name == "task_update":   return TASKS.update(args["task_id"], args.get("status"), args.get("addBlockedBy"), args.get("addBlocks"))
    if name == "task_list":     return TASKS.list_all()
    if name == "task_get":      return TASKS.get(args["task_id"])
    if name == "background_run":  return BG.run(args["command"])
    if name == "check_background": return BG.check(args.get("task_id"))
    if name == "spawn_teammate":  return TEAM.spawn(args["name"], args["role"], args["prompt"])
    if name == "list_teammates":  return TEAM.list_all()
    if name == "send_message":    return BUS.send("lead", args["to"], args["content"], args.get("msg_type", "message"))
    if name == "read_inbox":      return json.dumps(BUS.read_inbox("lead"), indent=2)
    if name == "broadcast":       return BUS.broadcast("lead", args["content"], TEAM.member_names())
    return f"Unknown tool: {name}"


# =============================================================================
# Main Agent Loop
# =============================================================================

rounds_without_todo = 0


def agent_loop(messages: list) -> list:
    global rounds_without_todo

    while True:
        # Drain background notifications and inject before LLM call
        notifs = BG.drain_notifications()
        if notifs and messages:
            notif_text = "\n".join(
                f"[bg:{n['task_id']}] {n['status']}: {n['result']}" for n in notifs
            )
            messages.append({"role": "user", "content": f"<background-results>\n{notif_text}\n</background-results>"})
            messages.append({"role": "assistant", "content": "Noted background results."})
        # Drain lead inbox and inject before LLM call
        inbox = BUS.read_inbox("lead")
        if inbox and messages:
            messages.append({"role": "user", "content": f"<inbox>{json.dumps(inbox, indent=2)}</inbox>"})
            messages.append({"role": "assistant", "content": "Noted inbox messages."})
        micro_compact(messages)
        if estimate_tokens(messages) > THRESHOLD:
            print("[auto_compact triggered]")
            messages[:] = auto_compact(messages)

        response = client.messages.create(
            model=MODEL, system=SYSTEM, messages=messages,
            tools=ALL_TOOLS, max_tokens=8000,
        )

        tool_calls = []
        for block in response.content:
            if hasattr(block, "text"):
                print(block.text)
            if block.type == "tool_use":
                tool_calls.append(block)

        if response.stop_reason != "tool_use":
            messages.append({"role": "assistant", "content": response.content})
            return messages

        results = []
        used_todo = False
        manual_compact = False

        for tc in tool_calls:
            if tc.name == "Task":
                print(f"\n> Task: {tc.input.get('description', 'subtask')}")
            elif tc.name == "compact":
                print(f"\n> compact")
                manual_compact = True
            else:
                print(f"\n> {tc.name}: {tc.input}")

            output = "Compressing..." if tc.name == "compact" else execute_tool(tc.name, tc.input)

            if tc.name not in ("Task", "compact"):
                preview = output[:200] + "..." if len(output) > 200 else output
                print(f"  {preview}")

            results.append({"type": "tool_result", "tool_use_id": tc.id, "content": str(output)})

            if tc.name == "TodoWrite":
                used_todo = True

        rounds_without_todo = 0 if used_todo else rounds_without_todo + 1
        messages.append({"role": "assistant", "content": response.content})

        if rounds_without_todo > 10:
            results.insert(0, {"type": "text", "text": NAG_REMINDER})

        messages.append({"role": "user", "content": results})

        if manual_compact:
            print("[manual compact]")
            messages[:] = auto_compact(messages)


# =============================================================================
# Main REPL
# =============================================================================

def main():
    global rounds_without_todo

    print(f"Mini Claude Code v8 (21 Tools + Todos + Subagents + Skills + Compaction + Persistent Tasks + Background Tasks + Agent Teams) - {WORKDIR}")
    print(f"Agent types: {', '.join(AGENT_TYPES.keys())}")
    print(f"Skills: {', '.join(SKILL_LOADER.skills.keys()) or '(none - add .skills/*.md)'}")
    print(f"Persistent tasks: {TASKS_DIR}")
    print("Type 'exit' to quit.\n")

    history = []
    first_message = True

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not user_input or user_input.lower() in ("exit", "quit", "q"):
            break
        if user_input.strip() == "/team":
            print(TEAM.list_all())
            continue
        if user_input.strip() == "/inbox":
            print(json.dumps(BUS.read_inbox("lead"), indent=2))
            continue

        content = []
        if first_message:
            content.append({"type": "text", "text": INITIAL_REMINDER})
            first_message = False
        content.append({"type": "text", "text": user_input})
        history.append({"role": "user", "content": content})

        try:
            agent_loop(history)
        except Exception as e:
            print(f"Error: {e}")

        print()


if __name__ == "__main__":
    main()
