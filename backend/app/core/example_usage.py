"""
新架构使用示例

展示如何使用重构后的核心组件
"""
import asyncio
from backend.app.core import AgentRunner, HistoryManager, GuardManager
from backend.app.core.factory import get_factory


async def example_main_agent():
    """示例：使用主 Agent"""

    # 1. 创建 Context
    factory = get_factory()
    context = factory.create_main_context(session_key="demo_session")

    # 2. 创建 Runner
    runner = AgentRunner(
        history_manager=HistoryManager(),
        guard_manager=GuardManager()
    )

    # 3. 运行
    history = []
    output = await runner.run(context, "帮我分析代码", history)

    print(f"输出: {output}")
    print(f"历史消息数: {len(history)}")


async def example_subagent():
    """示例：使用子 Agent"""

    # 1. 创建 SubContext
    factory = get_factory()
    sub_context = factory.create_sub_context(
        session_key="demo_session",
        subagent_type="Explore"
    )

    # 2. 创建 Runner（可复用）
    runner = AgentRunner()

    # 3. 运行
    output = await runner.run(sub_context, "搜索所有 Python 文件")

    print(f"Subagent 输出: {output}")


async def example_team_agent():
    """示例：使用团队 Agent"""

    # 1. 创建 TeamContext
    factory = get_factory()
    team_context = factory.create_team_context(
        session_key="demo_session",
        name="coder",
        role="后端开发"
    )

    # 2. 运行
    runner = AgentRunner()
    output = await runner.run(team_context, "实现用户登录功能")

    print(f"Team Agent 输出: {output}")


if __name__ == "__main__":
    # 运行示例
    asyncio.run(example_main_agent())
