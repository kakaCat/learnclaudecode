#!/usr/bin/env python3
"""
最小化 Agent 测试 - 跳过所有生命周期管理
专门用于测试 CDP 工具
"""

import asyncio
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


async def minimal_test():
    """最小化测试"""
    print("=" * 60)
    print("最小化 Agent 测试（无生命周期管理）")
    print("=" * 60)

    # 1. 测试工具是否注册
    print("\n1️⃣ 检查 CDP 工具注册...")
    try:
        from backend.app.tools.manager import tool_manager
        tools = tool_manager.get_tools()
        tool_names = [t.name for t in tools]

        if "cdp_browser" in tool_names:
            print(f"✅ cdp_browser 已注册（共 {len(tools)} 个工具）")
        else:
            print(f"❌ cdp_browser 未注册")
            print(f"   已注册工具: {', '.join(tool_names[:10])}...")
            return
    except Exception as e:
        print(f"❌ 工具检查失败: {e}")
        import traceback
        traceback.print_exc()
        return

    # 2. 创建 Agent（禁用生命周期）
    print("\n2️⃣ 创建 Agent...")
    try:
        from backend.app.agent import AgentService
        agent = AgentService(enable_lifecycle=False)
        print("✅ Agent 创建成功")
    except Exception as e:
        print(f"❌ Agent 创建失败: {e}")
        import traceback
        traceback.print_exc()
        return

    # 3. 运行测试
    print("\n3️⃣ 运行测试...")
    prompt = "测试 cdp 工具"
    history = []

    try:
        print(f"   输入: {prompt}")
        print("   执行中...")
        print()

        result = await agent.run(prompt, history)

        print()
        print("=" * 60)
        print("✅ 测试成功")
        print("=" * 60)
        print(f"结果: {result}")

    except asyncio.CancelledError:
        print()
        print("=" * 60)
        print("❌ 任务被取消 (CancelledError)")
        print("=" * 60)
        import traceback
        traceback.print_exc()

    except Exception as e:
        print()
        print("=" * 60)
        print(f"❌ 执行失败: {type(e).__name__}")
        print("=" * 60)
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(minimal_test())
