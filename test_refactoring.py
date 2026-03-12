"""测试重构后的架构"""
import asyncio
from backend.app.services.main_agent_service_v2 import MainAgentService

async def test_main_agent():
    print("=" * 50)
    print("测试 MainAgentService_v2")
    print("=" * 50)
    
    # 创建服务
    agent = MainAgentService(session_key="test_session", enable_lifecycle=False)
    print("✓ MainAgentService 创建成功")
    
    # 测试简单对话
    history = []
    prompt = "你好，请用一句话介绍你自己"
    print(f"\n用户: {prompt}")
    
    try:
        output = await agent.run(prompt, history)
        print(f"AI: {output[:200]}...")
        print("\n✓ 对话测试成功")
    except Exception as e:
        print(f"\n✗ 对话测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = asyncio.run(test_main_agent())
    print("\n" + "=" * 50)
    if success:
        print("✅ 所有测试通过")
    else:
        print("❌ 测试失败")
    print("=" * 50)
