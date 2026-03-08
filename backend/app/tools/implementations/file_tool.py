import logging
import subprocess
from langchain_core.tools import tool
from backend.app.tools.base import WORKDIR, _safe_path

logger = logging.getLogger(__name__)


@tool
def bash(command: str) -> str:
    """Run a shell command. Use for: git, npm, python, running tests. NOT for file exploration (use glob/grep/list_dir instead)."""
    dangerous = ["rm -rf /", "sudo", "shutdown", "reboot", "> /dev/"]
    if any(d in command for d in dangerous):
        return "Error: Dangerous command blocked"
    logger.info("bash: %s", command)
    try:
        out = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            timeout=120, cwd=WORKDIR
        )
        output = (out.stdout + out.stderr).strip()
    except subprocess.TimeoutExpired:
        output = "(timeout after 120s)"
    return output[:50000]


@tool
def read_file(path: str, offset: int = 1, limit: int = None) -> str:
    """Read file contents with line numbers. offset=start line (1-based), limit=max lines to read.
    Example: offset=50, limit=100 reads lines 50-149. Use for navigating large files."""
    logger.info("read_file: %s (offset=%s, limit=%s)", path, offset, limit)
    try:
        lines = _safe_path(path).read_text(encoding="utf-8", errors="replace").splitlines()
        total = len(lines)
        start = max(1, offset) - 1
        if start >= total:
            return f"Error: offset={offset} exceeds file length ({total} lines)"
        chunk = lines[start:start + limit] if limit else lines[start:]
        end = start + len(chunk)
        numbered = [f"{start + i + 1:4}: {l}" for i, l in enumerate(chunk)]
        if end < total:
            numbered.append(f"... ({total - end} more lines, use offset={end + 1})")
        return "\n".join(numbered)[:50000]
    except Exception as e:
        return f"Error: {e}"


@tool
def write_file(path: str, content: str) -> str:
    """Write content to a file. Creates parent directories if needed. Use for new files or complete rewrites."""
    logger.info("write_file: %s (%d bytes)", path, len(content))
    try:
        fp = _safe_path(path)
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content)
        return f"Wrote {len(content)} bytes to {path}"
    except Exception as e:
        return f"Error: {e}"


@tool
def edit_file(path: str, old_text: str, new_text: str, replace_all: bool = False) -> str:
    """Replace exact text in a file. old_text must match verbatim.
    replace_all=False (default): replaces first occurrence only.
    replace_all=True: replaces every occurrence (useful for renaming)."""
    logger.info("edit_file: %s (replace_all=%s)", path, replace_all)
    try:
        fp = _safe_path(path)
        content = fp.read_text(encoding="utf-8", errors="replace")
        if old_text not in content:
            stripped_match = old_text.strip() in content
            hint = " (hint: text found after stripping whitespace — check indentation/newlines)" if stripped_match else ""
            return f"Error: Text not found in {path}{hint}"
        count = content.count(old_text)
        new_content = content.replace(old_text, new_text) if replace_all else content.replace(old_text, new_text, 1)
        fp.write_text(new_content, encoding="utf-8")
        replaced = count if replace_all else 1
        return f"Edited {path} ({replaced}/{count} occurrence{'s' if count > 1 else ''} replaced)"
    except Exception as e:
        return f"Error: {e}"
