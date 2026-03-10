#!/usr/bin/env python3
"""
开发环境启动脚本 - 带守护线程

功能：
1. 启动守护线程（心跳、守护、监控）
2. 运行主 Agent 逻辑
3. 全局异常捕获
4. 优雅关闭
"""

import sys
import os
import signal
import threading
import time
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.app.reliability import (
    start_lifecycle,
    stop_lifecycle,
    get_lifecycle_status,
    start_health_server
)


class DaemonStarter:
    """守护线程启动器"""

    def __init__(self):
        self.lifecycle_started = False
        self.should_restart = False

    def setup_signal_handlers(self):
        """设置信号处理器"""
        def signal_handler(signum, frame):
            print(f"\n[信号] 收到信号 {signum}，准备关闭...")
            self.shutdown()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    def setup_exception_handler(self):
        """设置全局异常处理器"""
        def exception_handler(exc_type, exc_value, exc_traceback):
            print(f"\n[全局异常] {exc_type.__name__}: {exc_value}")

            # 记录异常
            import traceback
            traceback.print_exception(exc_type, exc_value, exc_traceback)

            # 守护线程会继续运行
            print("[守护线程] 继续运行中...")

        sys.excepthook = exception_handler

    def start_daemon_threads(self):
        """启动守护线程"""
        print("\n" + "="*50)
        print("🚀 启动守护系统...")
        print("="*50)

        # 启动健康检查服务器
        print("\n[1/2] 启动健康检查服务器...")
        start_health_server(port=8000)
        print("✅ 健康检查服务器已启动")

        # 启动生命周期管理（心跳、守护等）
        print("\n[2/2] 启动生命周期管理...")
        success = start_lifecycle()

        if success:
            self.lifecycle_started = True
            print("✅ 生命周期管理已启动")

            # 显示状态
            time.sleep(1)  # 等待系统初始化
            status = get_lifecycle_status()
            print(f"\n📊 系统状态:")
            print(f"  - 运行时长: {status.get('uptime_seconds', 0):.1f}秒")
            print(f"  - 心跳状态: {status.get('heartbeat', {}).get('status', 'unknown')}")
            print(f"  - 守护状态: {status.get('guard', {}).get('status', 'unknown')}")
        else:
            print("⚠️ 生命周期管理启动失败（可能已在运行）")
            self.lifecycle_started = False

        print("\n" + "="*50)
        print("✅ 守护系统启动完成")
        print("="*50 + "\n")

    def shutdown(self):
        """关闭守护系统"""
        if self.lifecycle_started:
            print("\n🛑 关闭守护系统...")
            stop_lifecycle(graceful=True)
            print("✅ 守护系统已关闭")

    def run_main_logic(self):
        """运行主逻辑（示例）"""
        print("\n" + "="*50)
        print("🎯 主 Agent 逻辑运行中...")
        print("="*50)
        print("\n提示:")
        print("  - 按 Ctrl+C 退出")
        print("  - 守护线程会在后台持续运行")
        print("  - 健康检查: http://localhost:8000/health")
        print()

        try:
            # 这里是你的主 Agent 逻辑
            # 例如：启动 FastAPI、处理用户输入等

            # 示例：保持运行
            while True:
                time.sleep(1)

                # 每10秒显示一次状态
                if int(time.time()) % 10 == 0:
                    status = get_lifecycle_status()
                    print(f"[状态] 运行时长: {status.get('uptime_seconds', 0):.0f}秒")

        except KeyboardInterrupt:
            print("\n[主逻辑] 收到中断信号")
        except Exception as e:
            print(f"\n[主逻辑异常] {e}")
            import traceback
            traceback.print_exc()

    def start(self):
        """启动完整系统"""
        # 设置信号处理
        self.setup_signal_handlers()

        # 设置异常处理
        self.setup_exception_handler()

        # 启动守护线程
        self.start_daemon_threads()

        # 运行主逻辑
        try:
            self.run_main_logic()
        finally:
            self.shutdown()


def main():
    """主入口"""
    starter = DaemonStarter()
    starter.start()


if __name__ == "__main__":
    main()
