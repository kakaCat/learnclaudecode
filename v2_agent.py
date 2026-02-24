#!/usr/bin/env python3
"""
v3_agent.py - Mini Claude Code: 8 Tools + Structured Planning (~350 lines)

v2_agent + v2_todo_agent 合并升级
=========================================

v2_agent:     7 tools (bash, read_file, write_file, edit_file, glob, grep, list_dir)
v2_todo_agent: 5 tools (bash, read_file, write_file, edit_file, TodoWrite)

v3 合并两者优势:
  | 工具       | 来源          | 用途                    |
  |------------|--------------|-------------------------|
  | bash       | v2_agent     | 执行命令                 |
  | read_file  | v2_agent     | 读取文件                 |
  | write_file | v2_agent     | 写入文件                 |
  | edit_file  | v2_agent     | 精确编辑文件             |
  | glob       | v2_agent NEW | 文件模式匹配             |
  | grep       | v2_agent NEW | 内容搜索                 |
  | list_dir   | v2_agent NEW | 目录列表                 |
  | TodoWrite  | v2_todo NEW  | 结构化任务规划           |

Usage:
    python v3_agent.py
"""

import fnmatch
import os
import re
import subprocess
from pathlib import Path

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv(override=True)

# =============================================================================
# Configuration
# =============================================================================

if os.getenv("ANTHROPIC_BASE_URL"):
    os.environ.pop("ANTHROPIC_AUTH_TOKEN", None)

WORKDIR = Path.cwd()
MODEL = os.getenv("MODEL_ID", "claude-sonnet-4-5-20250929")
client = Anthropic(base_url=os.getenv("ANTHROPIC_BASE_URL"))

SYSTEM = f"""You are a coding agent at {WORKDIR}.

Loop: plan -> act with tools -> update todos -> report.

Rules:
- Use TodoWrite to track multi-step tasks
- Mark tasks in_progress before starting, completed when done
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
        return self.render()

    def render(self) -> str:
        if not self.items:
            return "No todos."
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
# Tool Definitions
# =============================================================================

TOOLS = [
    {
        "name": "bash",
        "description": "Run a shell command. Use for: git, npm, python, running tests. NOT for file exploration (use glob/grep/list_dir instead).",
        "input_schema": {
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"],
        },
    },
    {
        "name": "read_file",
        "description": "Read file contents. Returns UTF-8 text.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "limit": {"type": "integer"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Write content to a file. Creates parent directories if needed.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "edit_file",
        "description": "Replace exact text in a file. old_text must match verbatim.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "old_text": {"type": "string"},
                "new_text": {"type": "string"},
            },
            "required": ["path", "old_text", "new_text"],
        },
    },
    {
        "name": "glob",
        "description": "Find files matching a pattern. Examples: '**/*.py', 'src/**/*.ts'",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string"},
                "dir": {"type": "string"},
            },
            "required": ["pattern"],
        },
    },
    {
        "name": "grep",
        "description": "Search for a pattern in files. Returns file:line:content matches.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string"},
                "dir": {"type": "string"},
                "glob": {"type": "string"},
            },
            "required": ["pattern"],
        },
    },
    {
        "name": "list_dir",
        "description": "List directory contents with file sizes and types.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
            },
            "required": [],
        },
    },
    {
        "name": "TodoWrite",
        "description": "Update the task list. Use to plan and track progress.",
        "input_schema": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "description": "Complete list of tasks (replaces existing)",
                    "items": {
                        "type": "object",
                        "properties": {
                            "content": {"type": "string"},
                            "status": {
                                "type": "string",
                                "enum": ["pending", "in_progress", "completed"],
                            },
                            "activeForm": {"type": "string"},
                        },
                        "required": ["content", "status", "activeForm"],
                    },
                }
            },
            "required": ["items"],
        },
    },
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
        result = subprocess.run(
            command, shell=True, cwd=WORKDIR,
            capture_output=True, text=True, timeout=120
        )
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
        return f"{target.relative_to(WORKDIR) if path else '.'}/\n" + "\n".join(lines)
    except Exception as e:
        return f"Error: {e}"


def run_todo(items: list) -> str:
    try:
        return TODO.update(items)
    except Exception as e:
        return f"Error: {e}"


def execute_tool(name: str, args: dict) -> str:
    if name == "bash":       return run_bash(args["command"])
    if name == "read_file":  return run_read(args["path"], args.get("limit"))
    if name == "write_file": return run_write(args["path"], args["content"])
    if name == "edit_file":  return run_edit(args["path"], args["old_text"], args["new_text"])
    if name == "glob":       return run_glob(args["pattern"], args.get("dir"))
    if name == "grep":       return run_grep(args["pattern"], args.get("dir"), args.get("glob"))
    if name == "list_dir":   return run_list_dir(args.get("path"))
    if name == "TodoWrite":  return run_todo(args["items"])
    return f"Unknown tool: {name}"


# =============================================================================
# Agent Loop
# =============================================================================

rounds_without_todo = 0


def agent_loop(messages: list) -> list:
    global rounds_without_todo

    while True:
        response = client.messages.create(
            model=MODEL,
            system=SYSTEM,
            messages=messages,
            tools=TOOLS,
            max_tokens=8000,
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

        for tc in tool_calls:
            print(f"\n> {tc.name}: {tc.input}")
            output = execute_tool(tc.name, tc.input)
            preview = output[:200] + "..." if len(output) > 200 else output
            print(f"  {preview}")
            results.append({
                "type": "tool_result",
                "tool_use_id": tc.id,
                "content": output,
            })
            if tc.name == "TodoWrite":
                used_todo = True

        rounds_without_todo = 0 if used_todo else rounds_without_todo + 1

        messages.append({"role": "assistant", "content": response.content})

        if rounds_without_todo > 10:
            results.insert(0, {"type": "text", "text": NAG_REMINDER})

        messages.append({"role": "user", "content": results})


# =============================================================================
# Main REPL
# =============================================================================

def main():
    global rounds_without_todo

    print(f"Mini Claude Code v3 (8 Tools + Todos) - {WORKDIR}")
    print("Tools: bash, read_file, write_file, edit_file, glob, grep, list_dir, TodoWrite")
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
