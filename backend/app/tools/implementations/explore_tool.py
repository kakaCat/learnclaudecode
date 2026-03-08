import logging
import re
from langchain_core.tools import tool
from backend.app.tools.base import WORKDIR, SKIP_DIRS, _safe_path

logger = logging.getLogger(__name__)


@tool
def glob(pattern: str, dir: str = None) -> str:
    """Find files matching a glob pattern. Examples: '**/*.py', 'src/**/*.ts', '*.md'
    Automatically skips .git, __pycache__, node_modules, .venv."""
    logger.info("glob: %s (dir=%s)", pattern, dir)
    try:
        base = _safe_path(dir) if dir else WORKDIR
        matches = sorted(base.rglob(pattern) if "**" in pattern else base.glob(pattern))
        files = [
            str(p.relative_to(WORKDIR)) for p in matches
            if p.is_file() and not any(part in SKIP_DIRS for part in p.parts)
        ]
        return "\n".join(files[:500]) if files else "(no matches)"
    except Exception as e:
        return f"Error: {e}"


@tool
def grep(pattern: str, dir: str = None, file_glob: str = "*", ignore_case: bool = False) -> str:
    """Search for a regex pattern in files. Returns file:line:content matches.
    ignore_case=True for case-insensitive search.
    Automatically skips .git, __pycache__, node_modules, .venv."""
    logger.info("grep: %r (file_glob=%s, ignore_case=%s)", pattern, file_glob, ignore_case)
    try:
        base = _safe_path(dir) if dir else WORKDIR
        flags = re.IGNORECASE if ignore_case else 0
        results = []
        for filepath in sorted(base.rglob(file_glob)):
            if not filepath.is_file():
                continue
            if any(part in SKIP_DIRS for part in filepath.parts):
                continue
            try:
                text = filepath.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            for lineno, line in enumerate(text.splitlines(), 1):
                if re.search(pattern, line, flags):
                    results.append(f"{filepath.relative_to(WORKDIR)}:{lineno}:{line.rstrip()}")
                    if len(results) >= 200:
                        results.append("... (truncated at 200 matches)")
                        return "\n".join(results)
        return "\n".join(results) if results else "(no matches)"
    except re.error as e:
        return f"Error: Invalid regex pattern — {e}"
    except Exception as e:
        return f"Error: {e}"


@tool
def list_dir(path: str = ".") -> str:
    """List directory contents with file sizes and types."""
    logger.info("list_dir: %s", path)
    try:
        target = _safe_path(path)
        if not target.is_dir():
            return f"Error: Not a directory: {path}"
        lines = []
        for item in sorted(target.iterdir()):
            if item.is_dir():
                lines.append(f"[dir]  {item.name}/")
            else:
                lines.append(f"[file] {item.name}  {item.stat().st_size:,} B")
        return f"{path}/\n" + "\n".join(lines)
    except Exception as e:
        return f"Error: {e}"
