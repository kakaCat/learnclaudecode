"""测试新架构"""
import asyncio
from backend.app.core.factory import get_factory
from backend.app.core import AgentRunner

async def test():
    print("🧪 测试新架构...")

    # 1. 创建 Context
    factory = get_factory()
    context = factory.create_main_context("test_session")
    print(f"✅ Context 创建成功: {context.agent_name}")

    # 2. 创建 Runner
    runner = AgentRunner()
    print("✅ Runner 创建成功")

    # 3. 测试简单对话
    history = []
    output = await runner.run(context, "你好", history)
    print(f"✅ 对话测试成功")
    print(f"📝 输出: {output[:100]}...")
    print(f"📊 历史: {len(history)} 条消息")

if __name__ == "__main__":
    asyncio.run(test())
