#!/usr/bin/env python3
"""
v2_agent.py - Mini Claude Code: 7 Tools (~250 lines)

v1 → v2 升级: 新增 3 个只读探索工具
=========================================

v1 的问题: 探索代码库只能靠 bash (find/grep/ls)
  - 有 shell 注入风险
  - 输出格式不固定，模型解析困难
  - 无法限制在 WORKDIR 内

v2 新增 3 个工具:
  | 工具      | 替代 bash 命令       | 优势                    |
  |-----------|---------------------|-------------------------|
  | glob      | find . -name "*.py" | 结构化输出，无副作用     |
  | grep      | grep -rn "pattern"  | 返回文件名+行号+内容     |
  | list_dir  | ls -la              | 路径沙箱，格式固定       |

7 工具覆盖率: ~97% 编码任务

Usage:
    python v2_agent.py
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

Loop: think briefly -> use tools -> report results.

Rules:
- Prefer tools over prose. Act, don't just explain.
- Use glob/grep/list_dir to explore. Use bash only for execution (run tests, git, npm).
- Never invent file paths. Explore first if unsure.
- Make minimal changes. Don't over-engineer.
- After finishing, summarize what changed."""


# =============================================================================
# Tool Definitions
# =============================================================================

TOOLS = [
    # --- Execution ---
    {
        "name": "bash",
        "description": "Run a shell command. Use for: git, npm, python, running tests. NOT for file exploration (use glob/grep/list_dir instead).",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "The shell command to execute"}
            },
            "required": ["command"],
        },
    },

    # --- File I/O ---
    {
        "name": "read_file",
        "description": "Read file contents. Returns UTF-8 text.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path to the file"},
                "limit": {"type": "integer", "description": "Max lines to read (default: all)"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Write content to a file. Creates parent directories if needed. Use for new files or complete rewrites.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path for the file"},
                "content": {"type": "string", "description": "Content to write"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "edit_file",
        "description": "Replace exact text in a file. Use for surgical edits. old_text must match verbatim.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path to the file"},
                "old_text": {"type": "string", "description": "Exact text to find"},
                "new_text": {"type": "string", "description": "Replacement text"},
            },
            "required": ["path", "old_text", "new_text"],
        },
    },

    # --- Exploration (NEW in v2) ---
    {
        "name": "glob",
        "description": "Find files matching a pattern. Examples: '**/*.py', 'src/**/*.ts', '*.md'",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Glob pattern, e.g. '**/*.py'"},
                "dir": {"type": "string", "description": "Directory to search in (default: workspace root)"},
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
                "pattern": {"type": "string", "description": "Regex or literal string to search for"},
                "dir": {"type": "string", "description": "Directory to search in (default: workspace root)"},
                "glob": {"type": "string", "description": "File pattern filter, e.g. '*.py' (default: all files)"},
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
                "path": {"type": "string", "description": "Relative path to directory (default: workspace root)"},
            },
            "required": [],
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
        # Filter to files only, return relative paths
        files = [str(p.relative_to(WORKDIR)) for p in matches if p.is_file()]
        if not files:
            return "(no matches)"
        return "\n".join(files[:500])  # cap at 500 results
    except Exception as e:
        return f"Error: {e}"


def run_grep(pattern: str, dir: str = None, glob: str = None) -> str:
    try:
        base = safe_path(dir) if dir else WORKDIR
        file_glob = glob or "*"

        results = []
        # Walk files matching the glob pattern
        for filepath in sorted(base.rglob(file_glob)):
            if not filepath.is_file():
                continue
            # Skip binary files
            try:
                text = filepath.read_text(errors="ignore")
            except Exception:
                continue
            for lineno, line in enumerate(text.splitlines(), 1):
                if re.search(pattern, line):
                    rel = filepath.relative_to(WORKDIR)
                    results.append(f"{rel}:{lineno}:{line.rstrip()}")
                    if len(results) >= 200:  # cap results
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
                size_str = f"{size:>8,} B"
                lines.append(f"  [file] {item.name}  {size_str}")

        return f"{target.relative_to(WORKDIR) if path else '.'}/\n" + "\n".join(lines)
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
    return f"Unknown tool: {name}"


# =============================================================================
# Agent Loop
# =============================================================================

def agent_loop(messages: list) -> list:
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

        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": results})


# =============================================================================
# Main REPL
# =============================================================================

def main():
    print(f"Mini Claude Code v2 - {WORKDIR}")
    print("7 tools: bash, read_file, write_file, edit_file, glob, grep, list_dir")
    print("Type 'exit' to quit.\n")

    history = []

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not user_input or user_input.lower() in ("exit", "quit", "q"):
            break

        history.append({"role": "user", "content": user_input})

        try:
            agent_loop(history)
        except Exception as e:
            print(f"Error: {e}")

        print()


if __name__ == "__main__":
    main()
