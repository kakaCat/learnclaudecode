#!/usr/bin/env python3
"""
v4_agent.py - Mini Claude Code: 8 Tools + Todos + Subagents (~500 lines)

v3_agent + Subagent Mechanism
==============================

v3_agent:     8 tools (bash, read_file, write_file, edit_file, glob, grep, list_dir, TodoWrite)
v3_subagent:  5 tools + Task (subagent with isolated context)

v4 合并两者优势:
  | 工具       | 来源           | 用途                    |
  |------------|---------------|-------------------------|
  | bash       | v3_agent      | 执行命令                 |
  | read_file  | v3_agent      | 读取文件                 |
  | write_file | v3_agent      | 写入文件                 |
  | edit_file  | v3_agent      | 精确编辑文件             |
  | glob       | v3_agent      | 文件模式匹配             |
  | grep       | v3_agent      | 内容搜索                 |
  | list_dir   | v3_agent      | 目录列表                 |
  | TodoWrite  | v3_agent      | 结构化任务规划           |
  | Task       | v3_subagent   | 派生隔离上下文子 agent   |

The Key Upgrade - Subagents with Richer Tools:
-----------------------------------------------
v3_subagent's Explore/Plan agents only had bash + read_file.
v4's Explore/Plan agents get the full read-only toolkit:
  bash, read_file, glob, grep, list_dir

This means subagents can now:
  - glob("**/*.py") to find files by pattern
  - grep("TODO", glob="*.py") to search content
  - list_dir() to browse structure
  ...without polluting the main agent's context.

Agent Type Registry:
--------------------
  | Type            | Tools                                    | Purpose                    |
  |-----------------|------------------------------------------|----------------------------|
  | Explore         | bash, read_file, glob, grep, list_dir    | Read-only exploration      |
  | general-purpose | all tools                                | Full implementation access |
  | Plan            | bash, read_file, glob, grep, list_dir    | Design without modifying   |

Usage:
    python v4_agent.py
"""

import fnmatch
import os
import re
import subprocess
import sys
import time
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

Rules:
- Use Task tool for subtasks that need focused exploration or implementation
- Use TodoWrite to track multi-step work
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
# Base Tool Definitions
# =============================================================================

BASE_TOOLS = [
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
            "properties": {"path": {"type": "string"}},
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

TASK_TOOL = {
    "name": "Task",
    "description": f"""Spawn a subagent for a focused subtask.

Subagents run in ISOLATED context - they don't see parent's history.
Use this to keep the main conversation clean.

Agent types:
{get_agent_descriptions()}

Example uses:
- Task(Explore): "Find all files using the auth module"
- Task(Plan): "Design a migration strategy for the database"
- Task(general-purpose): "Implement the user registration form"
""",
    "input_schema": {
        "type": "object",
        "properties": {
            "description": {
                "type": "string",
                "description": "Short task name (3-5 words) for progress display",
            },
            "prompt": {
                "type": "string",
                "description": "Detailed instructions for the subagent",
            },
            "subagent_type": {
                "type": "string",
                "enum": list(AGENT_TYPES.keys()),
                "description": "Type of agent to spawn",
            },
        },
        "required": ["description", "prompt", "subagent_type"],
    },
}

ALL_TOOLS = BASE_TOOLS + [TASK_TOOL]


def get_tools_for_agent(agent_type: str) -> list:
    """Filter tools based on agent type. Subagents never get Task (no recursion)."""
    allowed = AGENT_TYPES.get(agent_type, {}).get("tools", "*")
    if allowed == "*":
        return BASE_TOOLS
    return [t for t in BASE_TOOLS if t["name"] in allowed]


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


# =============================================================================
# Subagent Execution - The core addition in v4
# =============================================================================

def run_task(description: str, prompt: str, subagent_type: str) -> str:
    """
    Execute a subagent with isolated context.

    v4 improvement over v3_subagent:
    - Explore/Plan agents now have glob, grep, list_dir in addition to bash/read_file
    - Subagents can do richer exploration without polluting main context
    """
    if subagent_type not in AGENT_TYPES:
        return f"Error: Unknown agent type '{subagent_type}'"

    config = AGENT_TYPES[subagent_type]
    sub_system = f"""You are a {subagent_type} subagent at {WORKDIR}.

{config["prompt"]}

Complete the task and return a clear, concise summary."""

    sub_tools = get_tools_for_agent(subagent_type)
    sub_messages = [{"role": "user", "content": prompt}]

    print(f"  [{subagent_type}] {description}")
    start = time.time()
    tool_count = 0

    while True:
        response = client.messages.create(
            model=MODEL,
            system=sub_system,
            messages=sub_messages,
            tools=sub_tools,
            max_tokens=8000,
        )

        if response.stop_reason != "tool_use":
            break

        tool_calls = [b for b in response.content if b.type == "tool_use"]
        results = []

        for tc in tool_calls:
            tool_count += 1
            output = execute_tool(tc.name, tc.input)
            results.append({
                "type": "tool_result",
                "tool_use_id": tc.id,
                "content": output,
            })
            elapsed = time.time() - start
            sys.stdout.write(
                f"\r  [{subagent_type}] {description} ... {tool_count} tools, {elapsed:.1f}s"
            )
            sys.stdout.flush()

        sub_messages.append({"role": "assistant", "content": response.content})
        sub_messages.append({"role": "user", "content": results})

    elapsed = time.time() - start
    sys.stdout.write(
        f"\r  [{subagent_type}] {description} - done ({tool_count} tools, {elapsed:.1f}s)\n"
    )

    for block in response.content:
        if hasattr(block, "text"):
            return block.text

    return "(subagent returned no text)"


def execute_tool(name: str, args: dict) -> str:
    if name == "bash":       return run_bash(args["command"])
    if name == "read_file":  return run_read(args["path"], args.get("limit"))
    if name == "write_file": return run_write(args["path"], args["content"])
    if name == "edit_file":  return run_edit(args["path"], args["old_text"], args["new_text"])
    if name == "glob":       return run_glob(args["pattern"], args.get("dir"))
    if name == "grep":       return run_grep(args["pattern"], args.get("dir"), args.get("glob"))
    if name == "list_dir":   return run_list_dir(args.get("path"))
    if name == "TodoWrite":  return run_todo(args["items"])
    if name == "Task":       return run_task(args["description"], args["prompt"], args["subagent_type"])
    return f"Unknown tool: {name}"


# =============================================================================
# Main Agent Loop
# =============================================================================

rounds_without_todo = 0


def agent_loop(messages: list) -> list:
    global rounds_without_todo

    while True:
        response = client.messages.create(
            model=MODEL,
            system=SYSTEM,
            messages=messages,
            tools=ALL_TOOLS,
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
            if tc.name == "Task":
                print(f"\n> Task: {tc.input.get('description', 'subtask')}")
            else:
                print(f"\n> {tc.name}: {tc.input}")

            output = execute_tool(tc.name, tc.input)

            if tc.name != "Task":
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

    print(f"Mini Claude Code v4 (8 Tools + Todos + Subagents) - {WORKDIR}")
    print(f"Agent types: {', '.join(AGENT_TYPES.keys())}")
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
