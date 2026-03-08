#!/usr/bin/env python3
"""
健康检查监控 - 通过 HTTP 端点检查 Agent 健康状态
"""

import requests
import time
import subprocess
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


class HealthMonitor:
    """健康检查监控器"""

    def __init__(
        self,
        health_url: str = "http://localhost:8000/health",
        check_interval: int = 30,
        timeout: int = 5,
        max_failures: int = 3,
        restart_command: list = None
    ):
        self.health_url = health_url
        self.check_interval = check_interval
        self.timeout = timeout
        self.max_failures = max_failures
        self.restart_command = restart_command or ["python", "backend/app/agent.py"]

        self.failure_count = 0
        self.last_check_time = None
        self.is_running = True

    def check_health(self) -> bool:
        """检查健康状态"""
        try:
            response = requests.get(self.health_url, timeout=self.timeout)
            if response.status_code == 200:
                data = response.json()
                logger.info(f"✓ 健康检查通过: {data.get('status')}")
                return True
            else:
                logger.warning(f"✗ 健康检查失败: HTTP {response.status_code}")
                return False
        except requests.exceptions.Timeout:
            logger.error("✗ 健康检查超时")
            return False
        except requests.exceptions.ConnectionError:
            logger.error("✗ 无法连接到 Agent")
            return False
        except Exception as e:
            logger.error(f"✗ 健康检查异常: {e}")
            return False

    def restart_agent(self):
        """重启 Agent"""
        logger.warning(f"尝试重启 Agent: {' '.join(self.restart_command)}")
        try:
            # 先尝试优雅停止
            subprocess.run(["pkill", "-TERM", "-f", "agent.py"], timeout=10)
            time.sleep(2)

            # 启动新进程
            subprocess.Popen(
                self.restart_command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
            logger.info("Agent 重启命令已执行")
            time.sleep(5)  # 等待启动
        except Exception as e:
            logger.error(f"重启失败: {e}")

    def monitor(self):
        """监控循环"""
        logger.info(f"启动健康监控: {self.health_url}")
        logger.info(f"检查间隔: {self.check_interval}秒, 失败阈值: {self.max_failures}")

        while self.is_running:
            self.last_check_time = datetime.now()
            is_healthy = self.check_health()

            if is_healthy:
                self.failure_count = 0
            else:
                self.failure_count += 1
                logger.warning(f"连续失败次数: {self.failure_count}/{self.max_failures}")

                if self.failure_count >= self.max_failures:
                    logger.error("达到失败阈值，触发重启")
                    self.restart_agent()
                    self.failure_count = 0

            time.sleep(self.check_interval)


if __name__ == "__main__":
    monitor = HealthMonitor(
        health_url="http://localhost:8000/health",
        check_interval=30,
        max_failures=3
    )
    try:
        monitor.monitor()
    except KeyboardInterrupt:
        logger.info("监控已停止")
