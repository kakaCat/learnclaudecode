"""
上下文管理 - 支持心跳系统的会话上下文
"""

import threading
import time
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class SessionStatus(Enum):
    """会话状态"""
    ACTIVE = "active"
    IDLE = "idle"
    EXPIRED = "expired"
    SAVED = "saved"
    RESTORED = "restored"


@dataclass
class SessionContext:
    """会话上下文"""
    session_key: str
    created_at: datetime
    last_activity: datetime
    status: SessionStatus = SessionStatus.ACTIVE
    metadata: Dict[str, Any] = field(default_factory=dict)
    data: Dict[str, Any] = field(default_factory=dict)
    working_dir: Optional[Path] = None

    @property
    def skills_dir(self) -> Path:
        """获取技能目录路径"""
        base_dir = self.working_dir if self.working_dir else Path.cwd()
        return base_dir / ".skills"
    
    def update_activity(self):
        """更新活动时间"""
        self.last_activity = datetime.now()
        self.status = SessionStatus.ACTIVE
    
    def mark_idle(self):
        """标记为闲置"""
        self.status = SessionStatus.IDLE
    
    def mark_expired(self):
        """标记为过期"""
        self.status = SessionStatus.EXPIRED
    
    def mark_saved(self):
        """标记为已保存"""
        self.status = SessionStatus.SAVED
    
    def mark_restored(self):
        """标记为已恢复"""
        self.status = SessionStatus.RESTORED
    
    def is_expired(self, timeout_minutes: int) -> bool:
        """检查是否过期"""
        timeout_delta = timedelta(minutes=timeout_minutes)
        return datetime.now() - self.last_activity > timeout_delta
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "session_key": self.session_key,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "status": self.status.value,
            "metadata": self.metadata,
            "data_size": len(str(self.data)),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SessionContext':
        """从字典创建"""
        session = cls(
            session_key=data["session_key"],
            created_at=datetime.fromisoformat(data["created_at"]),
            last_activity=datetime.fromisoformat(data["last_activity"]),
            status=SessionStatus(data["status"]),
            metadata=data.get("metadata", {}),
            data=data.get("data", {}),
        )
        return session


class ContextManager:
    """上下文管理器"""
    
    def __init__(self, session_timeout_minutes: int = 30):
        """
        初始化上下文管理器
        
        Args:
            session_timeout_minutes: 会话超时时间（分钟）
        """
        self.session_timeout_minutes = session_timeout_minutes
        self._sessions: Dict[str, SessionContext] = {}
        self._lock = threading.RLock()
        self._save_lock = threading.RLock()
        
        logger.info(f"上下文管理器初始化完成，会话超时: {session_timeout_minutes}分钟")
    
    def create_session(self, session_key: str, metadata: Optional[Dict] = None) -> SessionContext:
        """创建新会话"""
        with self._lock:
            if session_key in self._sessions:
                logger.warning(f"会话已存在: {session_key}")
                return self._sessions[session_key]
            
            now = datetime.now()
            session = SessionContext(
                session_key=session_key,
                created_at=now,
                last_activity=now,
                metadata=metadata or {},
            )
            
            self._sessions[session_key] = session
            logger.info(f"创建新会话: {session_key}")
            return session
    
    def get_session(self, session_key: str, update_activity: bool = True) -> Optional[SessionContext]:
        """获取会话"""
        with self._lock:
            session = self._sessions.get(session_key)
            if session and update_activity:
                session.update_activity()
            return session
    
    def update_session_activity(self, session_key: str) -> bool:
        """更新会话活动时间"""
        with self._lock:
            session = self._sessions.get(session_key)
            if session:
                session.update_activity()
                return True
            return False
    
    def delete_session(self, session_key: str) -> bool:
        """删除会话"""
        with self._lock:
            if session_key in self._sessions:
                del self._sessions[session_key]
                logger.info(f"删除会话: {session_key}")
                return True
            return False
    
    def save_session(self, session_key: str) -> bool:
        """保存会话"""
        with self._save_lock:
            session = self.get_session(session_key, update_activity=False)
            if not session:
                logger.warning(f"会话不存在，无法保存: {session_key}")
                return False
            
            try:
                # 这里实现实际的保存逻辑
                # 例如保存到文件或数据库
                session.mark_saved()
                logger.debug(f"会话保存成功: {session_key}")
                return True
            except Exception as e:
                logger.error(f"保存会话失败: {session_key}, 错误: {e}")
                return False
    
    def save_all_sessions(self) -> Dict[str, bool]:
        """保存所有会话"""
        results = {}
        with self._lock:
            session_keys = list(self._sessions.keys())
        
        for session_key in session_keys:
            results[session_key] = self.save_session(session_key)
        
        logger.info(f"保存所有会话完成，成功: {sum(results.values())}, 总数: {len(results)}")
        return results
    
    def restore_session(self, session_key: str, data: Dict[str, Any]) -> bool:
        """恢复会话"""
        with self._lock:
            try:
                session = SessionContext.from_dict(data)
                self._sessions[session_key] = session
                session.mark_restored()
                logger.info(f"会话恢复成功: {session_key}")
                return True
            except Exception as e:
                logger.error(f"恢复会话失败: {session_key}, 错误: {e}")
                return False
    
    def cleanup_expired_sessions(self) -> List[str]:
        """清理过期会话"""
        expired = []
        with self._lock:
            for session_key, session in list(self._sessions.items()):
                if session.is_expired(self.session_timeout_minutes):
                    session.mark_expired()
                    expired.append(session_key)
        
        # 删除过期会话
        for session_key in expired:
            self.delete_session(session_key)
        
        if expired:
            logger.info(f"清理过期会话: {len(expired)}个")
        
        return expired
    
    def get_active_sessions(self) -> List[SessionContext]:
        """获取活跃会话"""
        with self._lock:
            return [
                session for session in self._sessions.values()
                if session.status != SessionStatus.EXPIRED
            ]
    
    def get_session_count(self) -> Dict[str, int]:
        """获取会话统计"""
        with self._lock:
            total = len(self._sessions)
            active = len([s for s in self._sessions.values() if s.status == SessionStatus.ACTIVE])
            idle = len([s for s in self._sessions.values() if s.status == SessionStatus.IDLE])
            expired = len([s for s in self._sessions.values() if s.status == SessionStatus.EXPIRED])
            
            return {
                "total": total,
                "active": active,
                "idle": idle,
                "expired": expired,
            }
    
    def get_status(self) -> Dict[str, Any]:
        """获取管理器状态"""
        session_count = self.get_session_count()
        
        return {
            "session_timeout_minutes": self.session_timeout_minutes,
            "session_count": session_count,
            "total_memory_usage": "N/A",  # 可以添加内存使用统计
            "last_cleanup": datetime.now().isoformat(),
        }


# 全局上下文管理器实例
_global_context: Optional[ContextManager] = None


def get_global_context() -> ContextManager:
    """获取全局上下文管理器"""
    global _global_context
    if _global_context is None:
        _global_context = ContextManager()
    return _global_context


def create_global_session(session_key: str, metadata: Optional[Dict] = None) -> SessionContext:
    """创建全局会话"""
    return get_global_context().create_session(session_key, metadata)


def get_global_session(session_key: str, update_activity: bool = True) -> Optional[SessionContext]:
    """获取全局会话"""
    return get_global_context().get_session(session_key, update_activity)


def cleanup_global_sessions() -> List[str]:
    """清理全局过期会话"""
    return get_global_context().cleanup_expired_sessions()


def save_all_global_sessions() -> Dict[str, bool]:
    """保存所有全局会话"""
    return get_global_context().save_all_sessions()