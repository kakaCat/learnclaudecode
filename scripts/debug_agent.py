#!/usr/bin/env python3
"""
调试版 Agent - 显示详细的执行日志
用于诊断"任务已取消"问题
"""

import asyncio
import sys
import os
import logging
import traceback

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# 设置详细日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)

from backend.app.agent import AgentService


async def debug_run(prompt: str):
    """调试运行 agent"""
    print("=" * 60)
    print("调试模式 Agent")
    print("=" * 60)
    print(f"用户输入: {prompt}")
    print("=" * 60)
    print()

    agent = AgentService(enable_lifecycle=False)  # 禁用生命周期管理简化调试
    history = []

    try:
        print("🔍 开始执行...")
        result = await agent.run(prompt, history)
        print()
        print("=" * 60)
        print("✅ 执行成功")
        print("=" * 60)
        print(f"结果: {result}")
        print()

    except asyncio.CancelledError as e:
        print()
        print("=" * 60)
        print("❌ 任务被取消 (CancelledError)")
        print("=" * 60)
        print(f"异常: {e}")
        print()
        print("调用栈:")
        traceback.print_exc()
        print()

    except Exception as e:
        print()
        print("=" * 60)
        print("❌ 执行出错")
        print("=" * 60)
        print(f"异常类型: {type(e).__name__}")
        print(f"异常信息: {e}")
        print()
        print("完整调用栈:")
        traceback.print_exc()
        print()


def main():
    if len(sys.argv) < 2:
        print("用法: python scripts/debug_agent.py '你的问题'")
        print()
        print("示例:")
        print("  python scripts/debug_agent.py '测试 cdp工具'")
        print("  python scripts/debug_agent.py '使用 cdp_browser 访问 example.com'")
        sys.exit(1)

    prompt = sys.argv[1]
    asyncio.run(debug_run(prompt))


if __name__ == "__main__":
    main()
