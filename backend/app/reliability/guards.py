"""
守护系统 - 确保 Agent 持续运行的保护机制

功能：
1. 监控 Agent 健康状态
2. 自动恢复失败的服务
3. 资源使用限制
4. 故障转移机制
"""

import threading
import time
import logging
import psutil
import os
from typing import Optional, Dict, Any, List, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class GuardStatus(Enum):
    """守护状态"""
    ACTIVE = "active"
    WATCHING = "watching"
    RECOVERING = "recovering"
    DEGRADED = "degraded"
    FAILED = "failed"


@dataclass
class ResourceMetrics:
    """资源指标"""
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    memory_used_mb: float = 0.0
    disk_usage_percent: float = 0.0
    open_files: int = 0
    thread_count: int = 0
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "cpu_percent": round(self.cpu_percent, 2),
            "memory_percent": round(self.memory_percent, 2),
            "memory_used_mb": round(self.memory_used_mb, 2),
            "disk_usage_percent": round(self.disk_usage_percent, 2),
            "open_files": self.open_files,
            "thread_count": self.thread_count,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class ServiceHealth:
    """服务健康状态"""
    service_name: str
    is_healthy: bool
    last_check: datetime
    error_count: int = 0
    last_error: Optional[str] = None
    recovery_attempts: int = 0
    
    def record_error(self, error: str):
        """记录错误"""
        self.is_healthy = False
        self.error_count += 1
        self.last_error = error
        self.last_check = datetime.now()
    
    def record_success(self):
        """记录成功"""
        self.is_healthy = True
        self.error_count = 0
        self.last_error = None
        self.last_check = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "service_name": self.service_name,
            "is_healthy": self.is_healthy,
            "last_check": self.last_check.isoformat(),
            "error_count": self.error_count,
            "last_error": self.last_error,
            "recovery_attempts": self.recovery_attempts,
        }


class GuardSystem:
    """守护系统"""
    
    def __init__(
        self,
        check_interval_seconds: int = 60,
        max_recovery_attempts: int = 3,
        resource_thresholds: Optional[Dict[str, float]] = None,
    ):
        """
        初始化守护系统
        
        Args:
            check_interval_seconds: 检查间隔（秒）
            max_recovery_attempts: 最大恢复尝试次数
            resource_thresholds: 资源阈值配置
        """
        self.check_interval_seconds = check_interval_seconds
        self.max_recovery_attempts = max_recovery_attempts
        
        # 资源阈值配置
        self.resource_thresholds = resource_thresholds or {
            "cpu_percent": 80.0,      # CPU使用率阈值
            "memory_percent": 80.0,   # 内存使用率阈值
            "disk_usage_percent": 90.0,  # 磁盘使用率阈值
        }
        
        # 状态
        self.status = GuardStatus.ACTIVE
        self._services: Dict[str, ServiceHealth] = {}
        self._resource_history: List[ResourceMetrics] = []
        self._max_history_size = 100
        
        # 线程控制
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.RLock()
        
        # 恢复回调函数
        self._recovery_handlers: Dict[str, Callable] = {}
        
        # 自动注册核心服务
        self._register_core_services()
        
        logger.info(f"守护系统初始化完成，检查间隔: {check_interval_seconds}秒")
    
    def _register_core_services(self):
        """注册核心服务"""
        core_services = [
            "heartbeat_system",
            "context_manager",
            "session_storage",
            "tool_registry",
            "llm_service",
        ]
        
        for service in core_services:
            self.register_service(service)
    
    def register_service(self, service_name: str, recovery_handler: Optional[Callable] = None) -> bool:
        """注册服务"""
        with self._lock:
            if service_name in self._services:
                logger.warning(f"服务已注册: {service_name}")
                return False
            
            self._services[service_name] = ServiceHealth(
                service_name=service_name,
                is_healthy=True,
                last_check=datetime.now(),
            )
            
            if recovery_handler:
                self._recovery_handlers[service_name] = recovery_handler
            
            logger.info(f"服务注册成功: {service_name}")
            return True
    
    def unregister_service(self, service_name: str) -> bool:
        """注销服务"""
        with self._lock:
            if service_name in self._services:
                del self._services[service_name]
                if service_name in self._recovery_handlers:
                    del self._recovery_handlers[service_name]
                logger.info(f"服务注销成功: {service_name}")
                return True
            return False
    
    def update_service_health(self, service_name: str, is_healthy: bool, error: Optional[str] = None):
        """更新服务健康状态"""
        with self._lock:
            if service_name not in self._services:
                logger.warning(f"服务未注册: {service_name}")
                return
            
            service = self._services[service_name]
            if is_healthy:
                service.record_success()
            else:
                service.record_error(error or "Unknown error")
                
                # 触发自动恢复
                if service_name in self._recovery_handlers:
                    self._attempt_recovery(service_name, service)
    
    def start(self) -> bool:
        """启动守护系统"""
        with self._lock:
            if self.status in [GuardStatus.ACTIVE, GuardStatus.WATCHING]:
                logger.warning("守护系统已经在运行中")
                return False
            
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._watchdog_loop,
                name="GuardWatchdog",
                daemon=True
            )
            self._thread.start()
            self.status = GuardStatus.WATCHING
            
            logger.info("守护系统启动成功")
            return True
    
    def stop(self) -> bool:
        """停止守护系统"""
        with self._lock:
            if self.status not in [GuardStatus.ACTIVE, GuardStatus.WATCHING]:
                logger.warning("守护系统未在运行中")
                return False
            
            self.status = GuardStatus.FAILED
            self._stop_event.set()
            
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=5.0)
            
            logger.info("守护系统停止成功")
            return True
    
    def _watchdog_loop(self):
        """看门狗循环"""
        logger.info("看门狗循环开始")
        
        while not self._stop_event.is_set():
            try:
                # 收集资源指标
                resource_metrics = self._collect_resource_metrics()
                self._resource_history.append(resource_metrics)
                
                # 限制历史记录大小
                if len(self._resource_history) > self._max_history_size:
                    self._resource_history = self._resource_history[-self._max_history_size:]
                
                # 检查资源使用
                resource_ok = self._check_resource_usage(resource_metrics)
                
                # 检查服务健康
                services_ok = self._check_services_health()
                
                # 更新系统状态
                if not resource_ok or not services_ok:
                    self.status = GuardStatus.DEGRADED
                    logger.warning("系统状态降级")
                else:
                    self.status = GuardStatus.WATCHING
                
                # 记录检查日志
                if len(self._resource_history) % 10 == 0:  # 每10次记录一次
                    logger.debug(f"守护检查完成，资源正常: {resource_ok}, 服务正常: {services_ok}")
                
            except Exception as e:
                logger.error(f"看门狗循环异常: {e}", exc_info=True)
                self.status = GuardStatus.FAILED
            
            # 等待下一个检查周期
            self._stop_event.wait(self.check_interval_seconds)
        
        logger.info("看门狗循环结束")
    
    def _collect_resource_metrics(self) -> ResourceMetrics:
        """收集资源指标"""
        try:
            process = psutil.Process(os.getpid())
            
            # 获取CPU使用率（非阻塞）
            cpu_percent = process.cpu_percent(interval=0.1)
            
            # 获取内存使用
            memory_info = process.memory_info()
            memory_percent = process.memory_percent()
            memory_used_mb = memory_info.rss / 1024 / 1024  # 转换为MB
            
            # 获取磁盘使用
            disk_usage = psutil.disk_usage('.')
            disk_usage_percent = disk_usage.percent
            
            # 获取打开文件数
            open_files = len(process.open_files())
            
            # 获取线程数
            thread_count = process.num_threads()
            
            return ResourceMetrics(
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                memory_used_mb=memory_used_mb,
                disk_usage_percent=disk_usage_percent,
                open_files=open_files,
                thread_count=thread_count,
            )
            
        except Exception as e:
            logger.error(f"收集资源指标失败: {e}")
            return ResourceMetrics()  # 返回空指标
    
    def _check_resource_usage(self, metrics: ResourceMetrics) -> bool:
        """检查资源使用"""
        violations = []
        
        if metrics.cpu_percent > self.resource_thresholds["cpu_percent"]:
            violations.append(f"CPU使用率过高: {metrics.cpu_percent}%")
        
        if metrics.memory_percent > self.resource_thresholds["memory_percent"]:
            violations.append(f"内存使用率过高: {metrics.memory_percent}%")
        
        if metrics.disk_usage_percent > self.resource_thresholds["disk_usage_percent"]:
            violations.append(f"磁盘使用率过高: {metrics.disk_usage_percent}%")
        
        if violations:
            logger.warning(f"资源使用异常: {', '.join(violations)}")
            return False
        
        return True
    
    def _check_services_health(self) -> bool:
        """检查服务健康"""
        all_healthy = True
        
        with self._lock:
            for service_name, service in list(self._services.items()):
                # 检查服务是否长时间未更新
                time_since_check = datetime.now() - service.last_check
                if time_since_check > timedelta(minutes=5):
                    logger.warning(f"服务长时间未更新: {service_name}")
                    service.record_error("长时间未更新状态")
                    all_healthy = False
                
                # 检查错误次数
                if service.error_count > 3:
                    logger.error(f"服务错误次数过多: {service_name} ({service.error_count}次)")
                    all_healthy = False
        
        return all_healthy
    
    def _attempt_recovery(self, service_name: str, service: ServiceHealth):
        """尝试恢复服务"""
        if service.recovery_attempts >= self.max_recovery_attempts:
            logger.error(f"服务恢复尝试次数已达上限: {service_name}")
            return
        
        logger.info(f"尝试恢复服务: {service_name} (第{service.recovery_attempts + 1}次)")
        
        try:
            if service_name in self._recovery_handlers:
                handler = self._recovery_handlers[service_name]
                success = handler()
                
                if success:
                    service.record_success()
                    service.recovery_attempts = 0
                    logger.info(f"服务恢复成功: {service_name}")
                else:
                    service.recovery_attempts += 1
                    logger.warning(f"服务恢复失败: {service_name}")
            else:
                logger.warning(f"服务无恢复处理器: {service_name}")
                service.recovery_attempts += 1
                
        except Exception as e:
            logger.error(f"服务恢复异常: {service_name}, 错误: {e}")
            service.recovery_attempts += 1
    
    def get_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        with self._lock:
            # 服务健康统计
            services_status = {}
            healthy_count = 0
            total_count = len(self._services)
            
            for service_name, service in self._services.items():
                services_status[service_name] = service.to_dict()
                if service.is_healthy:
                    healthy_count += 1
            
            # 最新资源指标
            latest_resources = None
            if self._resource_history:
                latest_resources = self._resource_history[-1].to_dict()
            
            # 资源历史趋势
            resource_trend = []
            if len(self._resource_history) >= 5:
                recent = self._resource_history[-5:]
                avg_cpu = sum(m.cpu_percent for m in recent) / len(recent)
                avg_memory = sum(m.memory_percent for m in recent) / len(recent)
                resource_trend = [
                    {"metric": "avg_cpu_percent", "value": round(avg_cpu, 2)},
                    {"metric": "avg_memory_percent", "value": round(avg_memory, 2)},
                ]
            
            return {
                "status": self.status.value,
                "check_interval_seconds": self.check_interval_seconds,
                "services_total": total_count,
                "services_healthy": healthy_count,
                "services_unhealthy": total_count - healthy_count,
                "services_health_percent": round(healthy_count / total_count * 100, 2) if total_count > 0 else 0,
                "latest_resources": latest_resources,
                "resource_trend": resource_trend,
                "resource_thresholds": self.resource_thresholds,
                "thread_alive": self._thread.is_alive() if self._thread else False,
            }
    
    def is_system_healthy(self) -> bool:
        """检查系统是否健康"""
        with self._lock:
            if self.status == GuardStatus.FAILED:
                return False
            
            # 检查服务健康
            unhealthy_services = [
                name for name, service in self._services.items()
                if not service.is_healthy
            ]
            
            if unhealthy_services:
                logger.warning(f"有不健康服务: {unhealthy_services}")
                return False
            
            return True


# 全局守护系统实例
_global_guard: Optional[GuardSystem] = None


def get_global_guard() -> GuardSystem:
    """获取全局守护系统"""
    global _global_guard
    if _global_guard is None:
        _global_guard = GuardSystem()
    return _global_guard


def start_global_guard() -> bool:
    """启动全局守护系统"""
    return get_global_guard().start()


def stop_global_guard() -> bool:
    """停止全局守护系统"""
    global _global_guard
    if _global_guard:
        result = _global_guard.stop()
        _global_guard = None
        return result
    return False


def get_guard_status() -> Dict[str, Any]:
    """获取全局守护状态"""
    guard = get_global_guard()
    return guard.get_status()


def is_system_healthy() -> bool:
    """检查系统是否健康"""
    guard = get_global_guard()
    return guard.is_system_healthy()


def register_service_guard(service_name: str, recovery_handler: Optional[Callable] = None) -> bool:
    """注册服务到守护系统"""
    guard = get_global_guard()
    return guard.register_service(service_name, recovery_handler)


def update_service_health(service_name: str, is_healthy: bool, error: Optional[str] = None):
    """更新服务健康状态"""
    guard = get_global_guard()
    guard.update_service_health(service_name, is_healthy, error)