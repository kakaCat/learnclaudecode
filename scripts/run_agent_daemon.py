#!/usr/bin/env python3
"""
Agent 持续运行启动器
集成所有可靠性保障系统
"""

import sys
import os
import signal
import logging

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.reliability import (
    start_lifecycle,
    stop_lifecycle,
    start_health_server,
    get_restart_manager
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


class AgentDaemon:
    """Agent 守护进程"""

    def __init__(self):
        self.is_running = False
        self.restart_manager = None

        # 注册信号处理
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)

    def _handle_shutdown(self, signum, frame):
        """处理关闭信号"""
        logger.info("收到关闭信号，准备退出...")
        self.stop()
        sys.exit(0)

    def start(self):
        """启动 Agent 守护进程"""
        logger.info("=" * 50)
        logger.info("启动 Agent 守护进程")
        logger.info("=" * 50)

        try:
            # 1. 启动健康检查服务器
            logger.info("启动健康检查服务器...")
            start_health_server(port=8000)
            logger.info("✓ 健康检查端点: http://localhost:8000/health")

            # 2. 启动生命周期管理（包含心跳+守护）
            logger.info("启动生命周期管理系统...")
            start_lifecycle()
            logger.info("✓ 生命周期管理系统已启动")

            # 3. 初始化重启管理器
            logger.info("初始化重启管理器...")
            self.restart_manager = get_restart_manager()
            logger.info("✓ 重启管理器已就绪")

            self.is_running = True

            logger.info("=" * 50)
            logger.info("✓ Agent 守护进程启动成功")
            logger.info("=" * 50)
            logger.info("")
            logger.info("可靠性保障:")
            logger.info("  - 心跳监控: 每5分钟检查会话状态")
            logger.info("  - 守护系统: 每60秒检查资源和服务")
            logger.info("  - 健康检查: http://localhost:8000/health")
            logger.info("  - 自动重启: 支持信号触发重启")
            logger.info("")
            logger.info("按 Ctrl+C 停止")
            logger.info("=" * 50)

            return True

        except Exception as e:
            logger.error(f"启动失败: {e}", exc_info=True)
            return False

    def stop(self):
        """停止 Agent 守护进程"""
        if not self.is_running:
            return

        logger.info("停止 Agent 守护进程...")

        try:
            # 停止生命周期管理
            stop_lifecycle()
            logger.info("✓ 生命周期管理系统已停止")

            self.is_running = False
            logger.info("✓ Agent 守护进程已停止")

        except Exception as e:
            logger.error(f"停止失败: {e}")


def main():
    """主函数"""
    daemon = AgentDaemon()

    # 启动守护进程
    if not daemon.start():
        logger.error("启动失败")
        sys.exit(1)

    # 导入并运行 Agent
    try:
        from backend.app.agent import AgentService

        agent = AgentService(enable_lifecycle=True)

        # 运行 Agent 主循环
        while daemon.is_running:
            try:
                prompt = input("\n用户: ")
                if prompt.lower() in ['exit', 'quit', 'q']:
                    break

                import asyncio
                response = asyncio.run(agent.run(prompt))
                print(f"\nAgent: {response}")

            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Agent 运行错误: {e}", exc_info=True)

    except Exception as e:
        logger.error(f"Agent 初始化失败: {e}", exc_info=True)
    finally:
        daemon.stop()


if __name__ == "__main__":
    main()
