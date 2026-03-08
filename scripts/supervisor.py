#!/usr/bin/env python3
"""
外部监控脚本 - 父进程监控子进程
当 Agent 崩溃时自动重启
"""

import subprocess
import time
import sys
import signal
import logging
from datetime import datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


class ProcessSupervisor:
    """进程监控器"""

    def __init__(
        self,
        command: list,
        max_restarts: int = 10,
        restart_delay: int = 5,
        crash_threshold: int = 3
    ):
        self.command = command
        self.max_restarts = max_restarts
        self.restart_delay = restart_delay
        self.crash_threshold = crash_threshold

        self.restart_count = 0
        self.crash_count = 0
        self.process = None
        self.should_stop = False

        # 注册信号处理
        signal.signal(signal.SIGINT, self._handle_stop)
        signal.signal(signal.SIGTERM, self._handle_stop)

    def _handle_stop(self, signum, frame):
        """处理停止信号"""
        logger.info("收到停止信号，准备退出...")
        self.should_stop = True
        if self.process:
            self.process.terminate()

    def start(self):
        """启动监控"""
        logger.info(f"启动进程监控: {' '.join(self.command)}")
        logger.info(f"最大重启次数: {self.max_restarts}")

        while not self.should_stop:
            if self.restart_count >= self.max_restarts:
                logger.error(f"达到最大重启次数 ({self.max_restarts})，停止监控")
                break

            # 启动子进程
            start_time = time.time()
            exit_code = self._run_process()
            run_duration = time.time() - start_time

            if self.should_stop:
                logger.info("监控已停止")
                break

            # 分析退出原因
            self._analyze_exit(exit_code, run_duration)

            # 等待后重启
            if not self.should_stop:
                logger.info(f"等待 {self.restart_delay} 秒后重启...")
                time.sleep(self.restart_delay)

    def _run_process(self):
        """运行子进程"""
        try:
            logger.info(f"启动子进程 (重启次数: {self.restart_count})...")

            self.process = subprocess.Popen(
                self.command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )

            logger.info(f"子进程已启动 (PID: {self.process.pid})")

            # 实时输出日志
            for line in self.process.stdout:
                print(line, end='')

            # 等待进程结束
            exit_code = self.process.wait()
            return exit_code

        except Exception as e:
            logger.error(f"启动子进程失败: {e}")
            return -1

    def _analyze_exit(self, exit_code: int, run_duration: float):
        """分析退出原因"""
        self.restart_count += 1

        if exit_code == 0:
            logger.info(f"子进程正常退出 (运行时长: {run_duration:.1f}秒)")
            self.crash_count = 0
        else:
            logger.error(f"子进程异常退出 (exit code: {exit_code}, 运行时长: {run_duration:.1f}秒)")

            # 检测快速崩溃
            if run_duration < 10:
                self.crash_count += 1
                logger.warning(f"检测到快速崩溃 ({self.crash_count}/{self.crash_threshold})")

                if self.crash_count >= self.crash_threshold:
                    logger.error("连续快速崩溃，增加重启延迟")
                    self.restart_delay = min(self.restart_delay * 2, 60)
            else:
                self.crash_count = 0


def main():
    """主函数"""
    # Agent 启动命令
    agent_command = ["python", "backend/app/agent.py"]

    # 创建监控器
    supervisor = ProcessSupervisor(
        command=agent_command,
        max_restarts=10,
        restart_delay=5,
        crash_threshold=3
    )

    # 启动监控
    try:
        supervisor.start()
    except KeyboardInterrupt:
        logger.info("用户中断")
    except Exception as e:
        logger.error(f"监控异常: {e}")
    finally:
        logger.info("监控已退出")


if __name__ == "__main__":
    main()
