"""
生命周期管理 - 集成心跳和守护系统，确保 Agent 持续运行

功能：
1. 启动/停止所有维持系统
2. 健康检查集成
3. 优雅的关闭和重启
4. 状态监控和报告
"""

import logging
import threading
import time
from typing import Dict, Any, Optional, Callable
from datetime import datetime

from .heartbeat import get_global_heartbeat, start_global_heartbeat, stop_global_heartbeat, get_heartbeat_status
from .guards import get_global_guard, start_global_guard, stop_global_guard, get_guard_status, register_service_guard
from backend.app.session.context import get_global_context, cleanup_global_sessions, save_all_global_sessions
from .exceptions import AgentError, LifecycleError

logger = logging.getLogger(__name__)


class LifecycleManager:
    """生命周期管理器"""
    
    def __init__(self):
        """初始化生命周期管理器"""
        self._is_running = False
        self._start_time: Optional[datetime] = None
        self._lock = threading.RLock()
        
        # 回调函数
        self._on_start_callbacks: list[Callable] = []
        self._on_stop_callbacks: list[Callable] = []
        self._on_restart_callbacks: list[Callable] = []
        
        # 服务注册
        self._registered_services: Dict[str, Dict] = {}
        
        logger.info("生命周期管理器初始化完成")
    
    def start(self) -> bool:
        """启动所有维持系统"""
        with self._lock:
            if self._is_running:
                logger.warning("生命周期系统已经在运行中")
                return False
            
            try:
                logger.info("启动生命周期系统...")
                
                # 记录启动时间
                self._start_time = datetime.now()
                
                # 1. 启动心跳系统
                logger.info("启动心跳系统...")
                heartbeat_started = start_global_heartbeat()
                if not heartbeat_started:
                    # 检查心跳系统是否已经在运行
                    from .heartbeat import get_heartbeat_status
                    status = get_heartbeat_status()
                    if status.get("status") == "running":
                        logger.info("心跳系统已经在运行中，继续...")
                    else:
                        raise LifecycleError("心跳系统启动失败")
                
                # 2. 启动守护系统
                logger.info("启动守护系统...")
                guard_started = start_global_guard()
                if not guard_started:
                    # 检查守护系统是否已经在运行
                    status = get_guard_status()
                    if status.get("status") in ["active", "watching"]:
                        logger.info("守护系统已经在运行中，继续...")
                    else:
                        raise LifecycleError("守护系统启动失败")
                
                # 3. 注册核心服务到守护系统
                self._register_core_services()
                
                # 4. 执行启动回调
                self._execute_callbacks(self._on_start_callbacks, "启动")
                
                # 5. 更新状态
                self._is_running = True
                
                logger.info("生命周期系统启动成功")
                return True
                
            except Exception as e:
                logger.error(f"生命周期系统启动失败: {e}")
                # 尝试清理
                self._emergency_stop()
                return False
    
    def stop(self, graceful: bool = True) -> bool:
        """停止所有维持系统"""
        with self._lock:
            if not self._is_running:
                logger.warning("生命周期系统未在运行中")
                return False
            
            try:
                logger.info("停止生命周期系统...")
                
                if graceful:
                    # 优雅停止
                    self._graceful_stop()
                else:
                    # 强制停止
                    self._emergency_stop()
                
                # 更新状态
                self._is_running = False
                self._start_time = None
                
                logger.info("生命周期系统停止成功")
                return True
                
            except Exception as e:
                logger.error(f"生命周期系统停止失败: {e}")
                return False
    
    def restart(self) -> bool:
        """重启所有维持系统"""
        with self._lock:
            logger.info("重启生命周期系统...")
            
            # 执行重启前回调
            self._execute_callbacks(self._on_restart_callbacks, "重启前")
            
            # 停止系统
            if self._is_running:
                if not self.stop(graceful=True):
                    logger.error("重启失败：停止阶段出错")
                    return False
            
            # 等待一小段时间
            time.sleep(1)
            
            # 启动系统
            if not self.start():
                logger.error("重启失败：启动阶段出错")
                return False
            
            # 执行重启后回调
            self._execute_callbacks(self._on_restart_callbacks, "重启后")
            
            logger.info("生命周期系统重启成功")
            return True
    
    def _graceful_stop(self):
        """优雅停止"""
        try:
            # 1. 保存所有会话
            logger.info("保存所有会话...")
            save_results = save_all_global_sessions()
            saved_count = sum(1 for result in save_results.values() if result)
            logger.info(f"会话保存完成，成功: {saved_count}, 总数: {len(save_results)}")
            
            # 2. 执行停止回调
            self._execute_callbacks(self._on_stop_callbacks, "停止")
            
            # 3. 停止守护系统
            logger.info("停止守护系统...")
            guard_stopped = stop_global_guard()
            if not guard_stopped:
                logger.warning("守护系统停止异常")
            
            # 4. 停止心跳系统
            logger.info("停止心跳系统...")
            heartbeat_stopped = stop_global_heartbeat()
            if not heartbeat_stopped:
                logger.warning("心跳系统停止异常")
            
            # 5. 清理过期会话
            logger.info("清理过期会话...")
            expired_sessions = cleanup_global_sessions()
            if expired_sessions:
                logger.info(f"清理了 {len(expired_sessions)} 个过期会话")
            
        except Exception as e:
            logger.error(f"优雅停止过程中出错: {e}")
            # 继续执行紧急停止
            self._emergency_stop()
    
    def _emergency_stop(self):
        """紧急停止"""
        try:
            # 强制停止所有系统
            stop_global_guard()
            stop_global_heartbeat()
            logger.warning("执行了紧急停止")
        except Exception as e:
            logger.error(f"紧急停止过程中出错: {e}")
    
    def _register_core_services(self):
        """注册核心服务"""
        try:
            # 注册心跳系统服务
            register_service_guard(
                "heartbeat_system",
                recovery_handler=self._recover_heartbeat
            )
            
            # 注册上下文管理器服务
            register_service_guard(
                "context_manager",
                recovery_handler=self._recover_context
            )
            
            # 注册其他核心服务
            core_services = [
                "session_storage",
                "tool_registry", 
                "llm_service",
                "memory_system",
                "notification_service",
            ]
            
            for service in core_services:
                register_service_guard(service)
                
            logger.info(f"注册了 {len(core_services) + 2} 个核心服务到守护系统")
            
        except Exception as e:
            logger.error(f"注册核心服务失败: {e}")
    
    def _recover_heartbeat(self) -> bool:
        """恢复心跳系统"""
        try:
            logger.info("尝试恢复心跳系统...")
            
            # 停止当前心跳
            stop_global_heartbeat()
            time.sleep(1)
            
            # 重新启动
            success = start_global_heartbeat()
            if success:
                logger.info("心跳系统恢复成功")
            else:
                logger.error("心跳系统恢复失败")
            
            return success
            
        except Exception as e:
            logger.error(f"心跳系统恢复异常: {e}")
            return False
    
    def _recover_context(self) -> bool:
        """恢复上下文管理器"""
        try:
            logger.info("尝试恢复上下文管理器...")
            
            # 保存当前会话
            save_all_global_sessions()
            
            # 清理过期会话
            cleanup_global_sessions()
            
            logger.info("上下文管理器恢复成功")
            return True
            
        except Exception as e:
            logger.error(f"上下文管理器恢复异常: {e}")
            return False
    
    def _execute_callbacks(self, callbacks: list[Callable], stage: str):
        """执行回调函数"""
        if not callbacks:
            return
        
        logger.info(f"执行{stage}回调函数 ({len(callbacks)}个)")
        
        for i, callback in enumerate(callbacks):
            try:
                callback()
                logger.debug(f"回调函数 {i+1}/{len(callbacks)} 执行成功")
            except Exception as e:
                logger.error(f"回调函数 {i+1}/{len(callbacks)} 执行失败: {e}")
    
    def register_callback(self, event: str, callback: Callable) -> bool:
        """注册回调函数"""
        with self._lock:
            if event == "start":
                self._on_start_callbacks.append(callback)
            elif event == "stop":
                self._on_stop_callbacks.append(callback)
            elif event == "restart":
                self._on_restart_callbacks.append(callback)
            else:
                logger.warning(f"未知的事件类型: {event}")
                return False
            
            logger.info(f"注册了 {event} 事件回调函数")
            return True
    
    def get_status(self) -> Dict[str, Any]:
        """获取生命周期状态"""
        with self._lock:
            # 获取各子系统状态
            heartbeat_status = get_heartbeat_status()
            guard_status = get_guard_status()
            
            # 计算运行时间
            uptime_seconds = None
            if self._start_time:
                uptime_seconds = (datetime.now() - self._start_time).total_seconds()
            
            return {
                "is_running": self._is_running,
                "start_time": self._start_time.isoformat() if self._start_time else None,
                "uptime_seconds": round(uptime_seconds, 2) if uptime_seconds else None,
                "uptime_human": self._format_uptime(uptime_seconds) if uptime_seconds else None,
                "heartbeat_system": heartbeat_status,
                "guard_system": guard_status,
                "callbacks_registered": {
                    "start": len(self._on_start_callbacks),
                    "stop": len(self._on_stop_callbacks),
                    "restart": len(self._on_restart_callbacks),
                },
                "services_registered": len(self._registered_services),
            }
    
    def _format_uptime(self, seconds: float) -> str:
        """格式化运行时间"""
        if seconds < 60:
            return f"{int(seconds)}秒"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            return f"{minutes}分钟"
        elif seconds < 86400:
            hours = int(seconds / 3600)
            minutes = int((seconds % 3600) / 60)
            return f"{hours}小时{minutes}分钟"
        else:
            days = int(seconds / 86400)
            hours = int((seconds % 86400) / 3600)
            return f"{days}天{hours}小时"
    
    def is_healthy(self) -> bool:
        """检查生命周期系统是否健康"""
        with self._lock:
            if not self._is_running:
                return False
            
            # 检查心跳系统
            from .heartbeat import is_heartbeat_healthy
            if not is_heartbeat_healthy():
                logger.warning("心跳系统不健康")
                return False
            
            # 检查守护系统
            from .guards import is_system_healthy
            if not is_system_healthy():
                logger.warning("守护系统不健康")
                return False
            
            return True
    
    def get_health_report(self) -> Dict[str, Any]:
        """获取健康报告"""
        status = self.get_status()
        
        # 导入健康检查函数
        from .heartbeat import is_heartbeat_healthy
        from .guards import is_system_healthy
        
        # 检查各项健康指标
        checks = {
            "lifecycle_running": self._is_running,
            "heartbeat_healthy": is_heartbeat_healthy(),
            "guard_healthy": is_system_healthy(),
            "uptime_reasonable": self._check_uptime_reasonable(),
        }
        
        # 计算健康分数
        passed_checks = sum(1 for check in checks.values() if check)
        total_checks = len(checks)
        health_score = round(passed_checks / total_checks * 100, 1) if total_checks > 0 else 0
        
        # 确定健康状态
        if health_score >= 90:
            health_status = "excellent"
        elif health_score >= 70:
            health_status = "good"
        elif health_score >= 50:
            health_status = "fair"
        else:
            health_status = "poor"
        
        return {
            "health_score": health_score,
            "health_status": health_status,
            "checks": checks,
            "passed_checks": passed_checks,
            "total_checks": total_checks,
            "recommendations": self._generate_recommendations(checks),
            "detailed_status": status,
        }
    
    def _check_uptime_reasonable(self) -> bool:
        """检查运行时间是否合理"""
        if not self._start_time:
            return False
        
        uptime_seconds = (datetime.now() - self._start_time).total_seconds()
        
        # 如果运行时间超过24小时，可能有问题
        if uptime_seconds > 86400:  # 24小时
            logger.warning(f"系统运行时间过长: {self._format_uptime(uptime_seconds)}")
            return False
        
        return True
    
    def _generate_recommendations(self, checks: Dict[str, bool]) -> list[str]:
        """生成改进建议"""
        recommendations = []
        
        if not checks.get("lifecycle_running"):
            recommendations.append("启动生命周期管理系统")
        
        if not checks.get("heartbeat_healthy"):
            recommendations.append("检查并修复心跳系统")
        
        if not checks.get("guard_healthy"):
            recommendations.append("检查守护系统状态")
        
        if not checks.get("uptime_reasonable"):
            recommendations.append("考虑重启系统以清理资源")
        
        return recommendations


# 全局生命周期管理器实例
_global_lifecycle: Optional[LifecycleManager] = None


def get_global_lifecycle() -> LifecycleManager:
    """获取全局生命周期管理器"""
    global _global_lifecycle
    if _global_lifecycle is None:
        _global_lifecycle = LifecycleManager()
    return _global_lifecycle


def start_lifecycle() -> bool:
    """启动全局生命周期系统"""
    return get_global_lifecycle().start()


def stop_lifecycle(graceful: bool = True) -> bool:
    """停止全局生命周期系统"""
    return get_global_lifecycle().stop(graceful)


def restart_lifecycle() -> bool:
    """重启全局生命周期系统"""
    return get_global_lifecycle().restart()


def get_lifecycle_status() -> Dict[str, Any]:
    """获取全局生命周期状态"""
    return get_global_lifecycle().get_status()


def get_lifecycle_health_report() -> Dict[str, Any]:
    """获取全局生命周期健康报告"""
    return get_global_lifecycle().get_health_report()


def is_lifecycle_healthy() -> bool:
    """检查生命周期系统是否健康"""
    return get_global_lifecycle().is_healthy()


def register_lifecycle_callback(event: str, callback: Callable) -> bool:
    """注册生命周期回调函数"""
    return get_global_lifecycle().register_callback(event, callback)