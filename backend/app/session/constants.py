"""
Session 包常量配置
"""
from pathlib import Path

# 项目根目录（backend/ 的父目录）
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent

# 会话存储根目录（固定在项目根目录）
SESSIONS_DIR = PROJECT_ROOT / ".sessions"

# 会话索引文件
SESSIONS_INDEX = SESSIONS_DIR / "sessions.json"

# 全局记忆配置目录（移动到 backend/memory/）
MEMORY_DIR = PROJECT_ROOT / "backend" / "memory"
