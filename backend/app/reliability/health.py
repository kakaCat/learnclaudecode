"""
健康检查端点 - 供外部监控使用
"""

from datetime import datetime

# 全局状态
_agent_status = {
    "status": "starting",
    "start_time": datetime.now().isoformat(),
    "last_heartbeat": None,
    "request_count": 0
}


def update_status(status: str):
    """更新状态"""
    _agent_status["status"] = status
    _agent_status["last_heartbeat"] = datetime.now().isoformat()


def start_health_server(port: int = 8000):
    """启动健康检查服务器（简化版）"""
    update_status("running")
