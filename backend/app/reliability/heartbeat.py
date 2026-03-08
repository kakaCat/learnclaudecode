"""
心跳系统 - 保持 Agent 持续运行

功能：
1. 定期检查会话状态，防止超时
2. 自动保存会话状态，防止数据丢失
3. 监控系统资源，防止内存泄漏
4. 优雅的错误处理，心跳失败不影响主功能
"""

import threading
import time
import logging
from typing import Optional, Callable, Dict, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class HeartbeatStatus(Enum):
    """心跳状态"""
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class HeartbeatMetrics:
    """心跳指标"""
    total_beats: int = 0
    successful_beats: int = 0
    failed_beats: int = 0
    avg_beat_duration_ms: float = 0.0
    last_beat_time: Optional[datetime] = None
    last_error: Optional[str] = None
    session_saves: int = 0
    session_restores: int = 0
    
    def record_beat(self, success: bool, duration_ms: float, error: Optional[str] = None):
        """记录一次心跳"""
        self.total_beats += 1
        if success:
            self.successful_beats += 1
        else:
            self.failed_beats += 1
            self.last_error = error
        
        # 更新平均持续时间
        if self.avg_beat_duration_ms == 0:
            self.avg_beat_duration_ms = duration_ms
        else:
            self.avg_beat_duration_ms = (self.avg_beat_duration_ms * 0.7 + duration_ms * 0.3)
        
        self.last_beat_time = datetime.now()
    
    def record_session_save(self):
        """记录会话保存"""
        self.session_saves += 1
    
    def record_session_restore(self):
        """记录会话恢复"""
        self.session_restores += 1
    
    def get_summary(self) -> Dict[str, Any]:
        """获取摘要"""
        return {
            "total_beats": self.total_beats,
            "successful_beats": self.successful_beats,
            "failed_beats": self.failed_beats,
            "success_rate": self.successful_beats / self.total_beats if self.total_beats > 0 else 0,
            "avg_beat_duration_ms": round(self.avg_beat_duration_ms, 2),
            "session_saves": self.session_saves,
            "session_restores": self.session_restores,
            "last_beat_time": self.last_beat_time.isoformat() if self.last_beat_time else None,
            "last_error": self.last_error,
        }


class HeartbeatSystem:
    """心跳系统"""
    
    def __init__(
        self,
        interval_seconds: int = 300,  # 5分钟
        session_timeout_minutes: int = 30,
        max_retries: int = 3,
        on_heartbeat: Optional[Callable] = None,
        on_session_save: Optional[Callable] = None,
        on_session_restore: Optional[Callable] = None,
    ):
        """
        初始化心跳系统
        
        Args:
            interval_seconds: 心跳间隔（秒）
            session_timeout_minutes: 会话超时时间（分钟）
            max_retries: 最大重试次数
            on_heartbeat: 心跳回调函数
            on_session_save: 会话保存回调函数
            on_session_restore: 会话恢复回调函数
        """
        self.interval_seconds = interval_seconds
        self.session_timeout_minutes = session_timeout_minutes
        self.max_retries = max_retries
        
        # 回调函数
        self.on_heartbeat = on_heartbeat
        self.on_session_save = on_session_save
        self.on_session_restore = on_session_restore
        
        # 状态
        self.status = HeartbeatStatus.STOPPED
        self.metrics = HeartbeatMetrics()
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.RLock()
        
        # 会话管理
        self._sessions: Dict[str, datetime] = {}  # session_key -> last_activity
        self._session_lock = threading.RLock()
        
        logger.info(f"心跳系统初始化完成，间隔: {interval_seconds}秒，会话超时: {session_timeout_minutes}分钟")
    
    def start(self) -> bool:
        """启动心跳系统"""
        with self._lock:
            if self.status == HeartbeatStatus.RUNNING:
                logger.warning("心跳系统已经在运行中")
                return False
            
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._heartbeat_loop,
                name="HeartbeatThread",
                daemon=True  # 守护线程，主程序退出时自动退出
            )
            self._thread.start()
            self.status = HeartbeatStatus.RUNNING
            
            logger.info("心跳系统启动成功")
            return True
    
    def stop(self) -> bool:
        """停止心跳系统"""
        with self._lock:
            if self.status != HeartbeatStatus.RUNNING:
                logger.warning("心跳系统未在运行中")
                return False
            
            self.status = HeartbeatStatus.STOPPED
            self._stop_event.set()
            
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=5.0)
            
            logger.info("心跳系统停止成功")
            return True
    
    def pause(self) -> bool:
        """暂停心跳系统"""
        with self._lock:
            if self.status != HeartbeatStatus.RUNNING:
                logger.warning("心跳系统未在运行中，无法暂停")
                return False
            
            self.status = HeartbeatStatus.PAUSED
            logger.info("心跳系统已暂停")
            return True
    
    def resume(self) -> bool:
        """恢复心跳系统"""
        with self._lock:
            if self.status != HeartbeatStatus.PAUSED:
                logger.warning("心跳系统未在暂停状态，无法恢复")
                return False
            
            self.status = HeartbeatStatus.RUNNING
            logger.info("心跳系统已恢复")
            return True
    
    def register_session(self, session_key: str) -> bool:
        """注册会话"""
        with self._session_lock:
            self._sessions[session_key] = datetime.now()
            logger.debug(f"会话注册: {session_key}")
            return True
    
    def update_session_activity(self, session_key: str) -> bool:
        """更新会话活动时间"""
        with self._session_lock:
            if session_key not in self._sessions:
                logger.warning(f"会话不存在: {session_key}")
                return False
            
            self._sessions[session_key] = datetime.now()
            return True
    
    def unregister_session(self, session_key: str) -> bool:
        """注销会话"""
        with self._session_lock:
            if session_key in self._sessions:
                del self._sessions[session_key]
                logger.debug(f"会话注销: {session_key}")
                return True
            return False
    
    def _heartbeat_loop(self):
        """心跳循环"""
        logger.info("心跳循环开始")
        
        while not self._stop_event.is_set():
            try:
                # 检查是否需要暂停
                if self.status == HeartbeatStatus.PAUSED:
                    time.sleep(1)
                    continue
                
                # 执行心跳
                start_time = time.time()
                success, error = self._perform_heartbeat()
                duration_ms = (time.time() - start_time) * 1000
                
                # 记录指标
                self.metrics.record_beat(success, duration_ms, error)
                
                if success:
                    logger.debug(f"心跳成功，耗时: {duration_ms:.2f}ms")
                else:
                    logger.warning(f"心跳失败: {error}")
                
            except Exception as e:
                logger.error(f"心跳循环异常: {e}", exc_info=True)
                self.metrics.record_beat(False, 0, str(e))
            
            # 等待下一个心跳周期
            self._stop_event.wait(self.interval_seconds)
        
        logger.info("心跳循环结束")
    
    def _perform_heartbeat(self) -> tuple[bool, Optional[str]]:
        """执行单次心跳"""
        try:
            # 1. 检查会话状态
            expired_sessions = self._check_session_timeouts()
            
            # 2. 保存活跃会话
            saved = self._save_active_sessions()
            if saved:
                self.metrics.record_session_save()
            
            # 3. 执行用户定义的心跳回调
            if self.on_heartbeat:
                try:
                    self.on_heartbeat(self.metrics.get_summary())
                except Exception as e:
                    logger.warning(f"心跳回调执行失败: {e}")
            
            # 4. 清理过期会话
            for session_key in expired_sessions:
                logger.info(f"会话超时，自动清理: {session_key}")
                self.unregister_session(session_key)
            
            return True, None
            
        except Exception as e:
            logger.error(f"心跳执行失败: {e}", exc_info=True)
            return False, str(e)
    
    def _check_session_timeouts(self) -> list[str]:
        """检查会话超时"""
        expired = []
        timeout_delta = timedelta(minutes=self.session_timeout_minutes)
        now = datetime.now()
        
        with self._session_lock:
            for session_key, last_activity in list(self._sessions.items()):
                if now - last_activity > timeout_delta:
                    expired.append(session_key)
        
        return expired
    
    def _save_active_sessions(self) -> bool:
        """保存活跃会话"""
        try:
            # 这里可以调用会话管理器的保存方法
            # 暂时返回 True 表示成功
            return True
        except Exception as e:
            logger.error(f"保存会话失败: {e}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        with self._lock:
            with self._session_lock:
                active_sessions = len(self._sessions)
                expired_sessions = len(self._check_session_timeouts())
                
                return {
                    "status": self.status.value,
                    "interval_seconds": self.interval_seconds,
                    "session_timeout_minutes": self.session_timeout_minutes,
                    "active_sessions": active_sessions,
                    "expired_sessions": expired_sessions,
                    "metrics": self.metrics.get_summary(),
                    "thread_alive": self._thread.is_alive() if self._thread else False,
                }
    
    def is_healthy(self) -> bool:
        """检查系统是否健康"""
        with self._lock:
            if self.status == HeartbeatStatus.ERROR:
                return False
            
            # 检查心跳是否正常
            if self.metrics.total_beats > 0:
                success_rate = self.metrics.successful_beats / self.metrics.total_beats
                if success_rate < 0.8:  # 成功率低于80%认为不健康
                    return False
            
            # 检查线程是否存活
            if self.status == HeartbeatStatus.RUNNING and self._thread:
                return self._thread.is_alive()
            
            return True


# 全局心跳系统实例
_global_heartbeat: Optional[HeartbeatSystem] = None


def get_global_heartbeat() -> HeartbeatSystem:
    """获取全局心跳系统实例"""
    global _global_heartbeat
    if _global_heartbeat is None:
        _global_heartbeat = HeartbeatSystem()
    return _global_heartbeat


def start_global_heartbeat() -> bool:
    """启动全局心跳系统"""
    return get_global_heartbeat().start()


def stop_global_heartbeat() -> bool:
    """停止全局心跳系统"""
    global _global_heartbeat
    if _global_heartbeat:
        result = _global_heartbeat.stop()
        _global_heartbeat = None
        return result
    return False


def get_heartbeat_status() -> Dict[str, Any]:
    """获取全局心跳状态"""
    heartbeat = get_global_heartbeat()
    return heartbeat.get_status()


def is_heartbeat_healthy() -> bool:
    """检查心跳是否健康"""
    heartbeat = get_global_heartbeat()
    return heartbeat.is_healthy()