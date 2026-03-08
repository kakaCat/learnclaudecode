"""
Session 包常量配置
"""
from pathlib import Path

# 会话存储根目录
SESSIONS_DIR = Path.cwd() / ".sessions"

# 会话索引文件
SESSIONS_INDEX = SESSIONS_DIR / "sessions.json"

# 全局 Bootstrap 配置目录
BOOTSTRAP_DIR = Path.cwd() / ".bootstrap"
