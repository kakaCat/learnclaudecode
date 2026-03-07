"""
Session 包统一入口

提供统一的会话管理接口，合并了原 session.py 和 analysis/session_store.py 的功能。

使用方式:
    from backend.app.session import get_store, save_session, load_session

    # 使用 SessionStore 类（推荐）
    store = get_store()
    store.create_session()
    store.save_turn("main", user_msg, ai_msg)

    # 使用向后兼容的函数接口
    key = new_session_key()
    save_session("main", history)
"""
from pathlib import Path

from .constants import SESSIONS_DIR, SESSIONS_INDEX
from .store import SessionStore

# 全局单例
_store: SessionStore | None = None


def get_store() -> SessionStore:
    """获取全局 SessionStore 实例"""
    global _store
    if _store is None:
        _store = SessionStore()
    return _store


# ============================================================
# 向后兼容的函数接口（保持与旧 session.py 相同的签名）
# ============================================================

def new_session_key() -> str:
    """创建新会话并返回 key"""
    store = get_store()
    key = store.create_session()
    store.set_current_key(key)
    return key


def set_session_key(key: str) -> None:
    """设置当前会话 key"""
    get_store().set_current_key(key)


def get_session_key() -> str | None:
    """获取当前会话 key"""
    return get_store().get_current_key()


def get_session_dir() -> Path:
    """获取当前会话目录"""
    return get_store().get_session_dir()


def get_workspace_dir() -> Path:
    """获取当前会话的 workspace 目录"""
    return get_store().get_workspace_dir()


def get_tasks_dir() -> Path:
    """获取当前会话的 tasks 目录"""
    return get_store().get_tasks_dir()


def get_team_dir() -> Path:
    """获取当前会话的 team 目录"""
    return get_store().get_team_dir()


def get_board_dir() -> Path:
    """获取当前会话的 board 目录"""
    return get_store().get_board_dir()


# ============================================================================
# 文件路径辅助函数
# ============================================================================

def get_task_file_path(task_id: int, slug: str = "") -> Path:
    """获取 task 文件路径"""
    return get_store().get_task_file_path(task_id, slug)


def get_board_task_path(task_id: int) -> Path:
    """获取 board task 文件路径"""
    return get_store().get_board_task_path(task_id)


def get_team_config_path() -> Path:
    """获取 team 配置文件路径"""
    return get_store().get_team_config_path()


def get_inbox_path(agent_name: str) -> Path:
    """获取 inbox 消息文件路径"""
    return get_store().get_inbox_path(agent_name)


def get_agent_transcript_path(agent_name: str) -> Path:
    """获取 agent transcript 文件路径"""
    return get_store().get_agent_transcript_path(agent_name)


def save_session(agent_name: str, history: list) -> None:
    """
    保存完整会话历史（向后兼容）

    Args:
        agent_name: agent 名称（如 "main", "Explore"）
        history: LangChain 消息列表
    """
    if not history:
        return
    get_store().save_full_history(agent_name, history)


def load_session(agent_name: str, key: str) -> list:
    """
    加载会话历史

    Args:
        agent_name: agent 名称
        key: 会话 key

    Returns:
        LangChain 消息列表
    """
    return get_store().load_history(agent_name, key)


def list_sessions() -> list[str]:
    """列出所有会话 key（按时间倒序）"""
    return [s["session_key"] for s in get_store().list_sessions()]


# ============================================================
# 导出所有公共接口
# ============================================================

__all__ = [
    # 类
    'SessionStore',

    # 常量
    'SESSIONS_DIR',
    'SESSIONS_INDEX',

    # 核心函数
    'get_store',

    # 向后兼容函数
    'new_session_key',
    'set_session_key',
    'get_session_key',
    'get_session_dir',
    'get_workspace_dir',
    'get_tasks_dir',
    'get_team_dir',
    'get_board_dir',
    'save_session',
    'load_session',
    'list_sessions',

    # 文件路径辅助函数
    'get_task_file_path',
    'get_board_task_path',
    'get_team_config_path',
    'get_inbox_path',
    'get_agent_transcript_path',
]
