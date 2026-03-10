"""
Agent 自动重启系统
让 Agent 能够优雅地退出并重新启动自己
"""

import os
import sys
import time
import subprocess
import signal
import threading
from pathlib import Path
from typing import Optional, Dict, Any
import json
from datetime import datetime

from backend.app.exceptions import AgentError
from .monitoring import PerformanceMonitor
from .heartbeat import HeartbeatSystem

class AutoRestartError(AgentError):
    """自动重启相关异常"""
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(
            message=message,
            code="AUTO_RESTART_ERROR",
            details=details
        )

class RestartManager:
    """重启管理器"""
    
    def __init__(self, agent_pid: Optional[int] = None):
        """
        初始化重启管理器
        
        Args:
            agent_pid: 当前 Agent 的进程 ID，如果为 None 则自动获取
        """
        self.agent_pid = agent_pid or os.getpid()
        self.restart_log_path = Path(".sessions/restart_log.jsonl")
        self.restart_log_path.parent.mkdir(exist_ok=True, parents=True)
        
        # 性能监控
        self.monitor = PerformanceMonitor()
        
        # 注册信号处理器
        self._setup_signal_handlers()
        
        # 重启状态
        self._restart_requested = False
        self._restart_reason = ""
        self._restart_timestamp = None
        
        print(f"[重启管理器] 初始化完成，当前 PID: {self.agent_pid}")
    
    def _setup_signal_handlers(self):
        """设置信号处理器"""
        signal.signal(signal.SIGUSR1, self._handle_restart_signal)
        signal.signal(signal.SIGTERM, self._handle_graceful_shutdown)
        signal.signal(signal.SIGINT, self._handle_interrupt)
    
    def _handle_restart_signal(self, signum, frame):
        """处理重启信号"""
        print(f"[重启管理器] 收到重启信号 (SIGUSR1)")
        self.request_restart("收到重启信号")
    
    def _handle_graceful_shutdown(self, signum, frame):
        """处理优雅关闭信号"""
        print(f"[重启管理器] 收到优雅关闭信号 (SIGTERM)")
        self.request_restart("优雅关闭请求")
    
    def _handle_interrupt(self, signum, frame):
        """处理中断信号"""
        print(f"[重启管理器] 收到中断信号 (SIGINT)")
        self.request_restart("用户中断")
    
    def request_restart(self, reason: str = "手动请求"):
        """
        请求重启
        
        Args:
            reason: 重启原因
        """
        if self._restart_requested:
            print(f"[重启管理器] 重启已在进行中，忽略新请求")
            return
        
        self._restart_requested = True
        self._restart_reason = reason
        self._restart_timestamp = datetime.now()
        
        print(f"[重启管理器] 重启请求已记录: {reason}")
        
        # 记录重启日志
        self._log_restart_request()
        
        # 启动重启线程
        restart_thread = threading.Thread(
            target=self._perform_restart,
            daemon=True,
            name="restart-worker"
        )
        restart_thread.start()
    
    def _log_restart_request(self):
        """记录重启请求日志"""
        log_entry = {
            "timestamp": self._restart_timestamp.isoformat() if self._restart_timestamp else datetime.now().isoformat(),
            "pid": self.agent_pid,
            "reason": self._restart_reason,
            "status": "requested",
            "performance": self.monitor.get_report()
        }
        
        with open(self.restart_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    
    def _perform_restart(self):
        """执行重启操作"""
        try:
            print(f"[重启管理器] 开始执行重启: {self._restart_reason}")
            
            # 1. 停止心跳系统（如果存在）
            self._stop_heartbeat_system()
            
            # 2. 保存当前状态
            self._save_agent_state()
            
            # 3. 获取重启命令
            restart_command = self._get_restart_command()
            
            # 4. 记录重启开始
            self._log_restart_start()
            
            # 5. 执行重启
            print(f"[重启管理器] 执行重启命令: {restart_command}")
            subprocess.Popen(
                restart_command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True
            )
            
            # 6. 优雅退出当前进程
            print(f"[重启管理器] 优雅退出当前进程 (PID: {self.agent_pid})")
            os._exit(0)
            
        except Exception as e:
            error_msg = f"重启失败: {str(e)}"
            print(f"[重启管理器] {error_msg}")
            self._log_restart_failure(error_msg)
            raise AutoRestartError(error_msg)
    
    def _stop_heartbeat_system(self):
        """停止心跳系统"""
        try:
            # 尝试导入并停止心跳系统
            from .heartbeat import HeartbeatSystem, HeartbeatStatus
            heartbeat = HeartbeatSystem()
            # 检查心跳系统状态
            if hasattr(heartbeat, 'status') and heartbeat.status == HeartbeatStatus.RUNNING:
                print(f"[重启管理器] 停止心跳系统")
                heartbeat.stop()
            else:
                print(f"[重启管理器] 心跳系统未运行，无需停止")
        except Exception as e:
            print(f"[重启管理器] 停止心跳系统时出错: {e}")
    
    def _save_agent_state(self):
        """保存 Agent 状态"""
        try:
            # 保存会话状态
            sessions_dir = Path(".sessions")
            if sessions_dir.exists():
                # 标记当前会话为需要恢复
                current_session = self._find_current_session()
                if current_session:
                    state_file = current_session / "restore_state.json"
                    state_data = {
                        "restart_time": datetime.now().isoformat(),
                        "reason": self._restart_reason,
                        "pid": self.agent_pid,
                        "performance": self.monitor.get_report()
                    }
                    with open(state_file, "w", encoding="utf-8") as f:
                        json.dumps(state_data, f, indent=2, ensure_ascii=False)
                    print(f"[重启管理器] 已保存 Agent 状态到 {state_file}")
        except Exception as e:
            print(f"[重启管理器] 保存状态时出错: {e}")
    
    def _find_current_session(self) -> Optional[Path]:
        """查找当前会话目录"""
        sessions_dir = Path(".sessions")
        if not sessions_dir.exists():
            return None
        
        # 查找最新的会话目录
        session_dirs = [d for d in sessions_dir.iterdir() if d.is_dir()]
        if not session_dirs:
            return None
        
        # 按修改时间排序，返回最新的
        latest_session = max(session_dirs, key=lambda d: d.stat().st_mtime)
        return latest_session
    
    def _get_restart_command(self) -> str:
        """获取重启命令"""
        # 获取当前脚本路径
        script_path = self._find_main_script()
        
        # 构建重启命令
        if script_path:
            return f"python {script_path}"
        else:
            # 默认命令
            return "python -m backend.app.agent"
    
    def _find_main_script(self) -> Optional[str]:
        """查找主脚本路径"""
        possible_paths = [
            "v11_agent.py",
            "agent.py",
            "main.py",
            "run.py",
            "backend/app/agent.py",
            "backend/app/main.py"
        ]
        
        for path in possible_paths:
            if Path(path).exists():
                return path
        
        return None
    
    def _log_restart_start(self):
        """记录重启开始日志"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "pid": self.agent_pid,
            "reason": self._restart_reason,
            "status": "starting",
            "command": self._get_restart_command()
        }
        
        with open(self.restart_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    
    def _log_restart_failure(self, error: str):
        """记录重启失败日志"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "pid": self.agent_pid,
            "reason": self._restart_reason,
            "status": "failed",
            "error": error
        }
        
        with open(self.restart_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    
    def is_restart_requested(self) -> bool:
        """检查是否有重启请求"""
        return self._restart_requested
    
    def get_restart_info(self) -> Dict[str, Any]:
        """获取重启信息"""
        return {
            "requested": self._restart_requested,
            "reason": self._restart_reason,
            "timestamp": self._restart_timestamp.isoformat() if self._restart_timestamp else None,
            "pid": self.agent_pid
        }
    
    def check_and_restart_if_needed(self):
        """检查并执行重启（如果需要）"""
        if self._restart_requested:
            print(f"[重启管理器] 检测到待处理的重启请求: {self._restart_reason}")
            return True
        return False

# 全局重启管理器实例
_restart_manager: Optional[RestartManager] = None

def get_restart_manager(agent_pid: Optional[int] = None) -> RestartManager:
    """
    获取重启管理器实例（单例模式）
    
    Args:
        agent_pid: 当前 Agent 的进程 ID
    
    Returns:
        RestartManager 实例
    """
    global _restart_manager
    if _restart_manager is None:
        _restart_manager = RestartManager(agent_pid)
    return _restart_manager

def request_restart(reason: str = "手动请求"):
    """
    请求重启（便捷函数）
    
    Args:
        reason: 重启原因
    """
    manager = get_restart_manager()
    manager.request_restart(reason)

def is_restart_requested() -> bool:
    """检查是否有重启请求"""
    if _restart_manager is None:
        return False
    return _restart_manager.is_restart_requested()

def get_restart_logs(limit: int = 10) -> list:
    """
    获取重启日志
    
    Args:
        limit: 返回的日志条数限制
    
    Returns:
        重启日志列表
    """
    log_path = Path(".sessions/restart_log.jsonl")
    if not log_path.exists():
        return []
    
    logs = []
    with open(log_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        for line in lines[-limit:]:
            try:
                logs.append(json.loads(line.strip()))
            except json.JSONDecodeError:
                continue
    
    return logs[::-1]  # 返回最新的在前面

def test_auto_restart():
    """测试自动重启功能"""
    print("=== 测试自动重启功能 ===")
    
    # 创建重启管理器
    manager = get_restart_manager()
    
    # 测试重启请求
    print("1. 发送重启请求...")
    manager.request_restart("测试重启")
    
    # 检查重启状态
    print("2. 检查重启状态...")
    if manager.is_restart_requested():
        print("   ✓ 重启请求已记录")
    else:
        print("   ✗ 重启请求未记录")
    
    # 获取重启信息
    print("3. 获取重启信息...")
    info = manager.get_restart_info()
    print(f"   重启原因: {info['reason']}")
    print(f"   请求时间: {info['timestamp']}")
    
    # 获取重启日志
    print("4. 获取重启日志...")
    logs = get_restart_logs(5)
    print(f"   找到 {len(logs)} 条日志记录")
    
    print("=== 测试完成 ===")
    return True

if __name__ == "__main__":
    # 直接运行测试
    test_auto_restart()