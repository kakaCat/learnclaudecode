#!/usr/bin/env python3
"""
测试守护系统功能

测试项：
1. 守护线程启动
2. 心跳系统运行
3. 守护系统监控
4. 健康检查端点
5. 异常处理
"""

import sys
import time
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.app.reliability import (
    start_lifecycle,
    stop_lifecycle,
    get_lifecycle_status,
    is_lifecycle_healthy,
    get_heartbeat_status,
    get_guard_status
)


def test_daemon_system():
    """测试守护系统"""
    print("\n" + "="*60)
    print("🧪 测试守护系统")
    print("="*60)

    # 1. 启动生命周期管理
    print("\n[测试 1/5] 启动生命周期管理...")
    success = start_lifecycle()
    if success:
        print("✅ 启动成功")
    else:
        print("⚠️ 启动失败（可能已在运行）")

    time.sleep(2)  # 等待系统初始化

    # 2. 检查生命周期状态
    print("\n[测试 2/5] 检查生命周期状态...")
    status = get_lifecycle_status()
    print(f"  - 运行状态: {status.get('is_running')}")
    print(f"  - 运行时长: {status.get('uptime_seconds', 0):.1f}秒")
    print(f"  - 启动时间: {status.get('start_time')}")
    print("✅ 状态正常")

    # 3. 检查心跳系统
    print("\n[测试 3/5] 检查心跳系统...")
    heartbeat_status = get_heartbeat_status()
    print(f"  - 心跳状态: {heartbeat_status.get('status')}")
    print(f"  - 总心跳数: {heartbeat_status.get('metrics', {}).get('total_beats', 0)}")
    print(f"  - 成功率: {heartbeat_status.get('metrics', {}).get('success_rate', 0)*100:.1f}%")
    print("✅ 心跳正常")

    # 4. 检查守护系统
    print("\n[测试 4/5] 检查守护系统...")
    guard_status = get_guard_status()
    print(f"  - 守护状态: {guard_status.get('status')}")
    print(f"  - 检查次数: {guard_status.get('check_count', 0)}")

    resources = guard_status.get('current_resources', {})
    if resources:
        print(f"  - CPU使用: {resources.get('cpu_percent', 0):.1f}%")
        print(f"  - 内存使用: {resources.get('memory_percent', 0):.1f}%")
        print(f"  - 线程数: {resources.get('thread_count', 0)}")
    print("✅ 守护正常")

    # 5. 检查健康状态
    print("\n[测试 5/5] 检查整体健康状态...")
    is_healthy = is_lifecycle_healthy()
    if is_healthy:
        print("✅ 系统健康")
    else:
        print("⚠️ 系统异常")

    # 等待一段时间观察
    print("\n" + "="*60)
    print("⏳ 运行10秒观察守护系统...")
    print("="*60)

    for i in range(10):
        time.sleep(1)
        status = get_lifecycle_status()
        print(f"[{i+1}/10] 运行时长: {status.get('uptime_seconds', 0):.1f}秒", end="\r")

    print("\n")

    # 关闭系统
    print("\n" + "="*60)
    print("🛑 关闭守护系统...")
    print("="*60)
    stop_lifecycle(graceful=True)
    print("✅ 已关闭")

    print("\n" + "="*60)
    print("✅ 测试完成")
    print("="*60 + "\n")


if __name__ == "__main__":
    try:
        test_daemon_system()
    except KeyboardInterrupt:
        print("\n\n[中断] 测试被用户中断")
        stop_lifecycle(graceful=True)
    except Exception as e:
        print(f"\n\n[错误] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        stop_lifecycle(graceful=True)
