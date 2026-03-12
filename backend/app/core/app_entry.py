"""
新架构应用入口

展示如何初始化和使用重构后的架构
"""
import asyncio
from backend.app.core import AgentRunner
from backend.app.core.factory import get_factory
from backend.app.core.task_integration import setup_task_tool


async def main():
    """主函数"""

    # 1. 初始化 Task Tool（应用启动时执行一次）
    setup_task_tool()
    print("✅ Task Tool 已初始化")

    # 2. 创建 Main Agent Context
    factory = get_factory()
    context = factory.create_main_context(session_key="demo_session")
    print(f"✅ Main Context 已创建: {context.agent_name}")

    # 3. 创建 Runner
    runner = AgentRunner()
    print("✅ Agent Runner 已创建")

    # 4. 运行对话
    history = []

    # 第一轮对话
    prompt1 = "你好，请介绍一下你自己"
    print(f"\n👤 用户: {prompt1}")
    output1 = await runner.run(context, prompt1, history)
    print(f"🤖 AI: {output1[:200]}...")

    # 第二轮对话（测试 Task Tool）
    prompt2 = "使用 Explore subagent 搜索所有 Python 文件"
    print(f"\n👤 用户: {prompt2}")
    output2 = await runner.run(context, prompt2, history)
    print(f"🤖 AI: {output2[:200]}...")

    print(f"\n📊 对话历史: {len(history)} 条消息")


if __name__ == "__main__":
    asyncio.run(main())
