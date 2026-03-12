"""
Task Tool 集成 - 连接新架构

解决 Task Tool 的回调注入问题
"""
from backend.app.core.factory import get_factory
from backend.app.core.agent_runner import AgentRunner


def setup_task_tool():
    """
    设置 Task Tool 的回调函数

    这个函数应该在应用启动时调用一次
    """
    from backend.app.tools.implementations.agent.spawn_tool import set_spawn_callback

    # 创建全局 runner 和 factory
    factory = get_factory()
    runner = AgentRunner()

    def spawn_subagent(description: str, prompt: str, subagent_type: str, recursion_limit: int):
        """Spawn subagent 的回调实现"""
        import asyncio

        # 获取当前 session_key（从全局状态）
        from backend.app.session import get_store
        store = get_store()
        session_key = store.get_current_key() or "default"

        # 创建 SubContext
        sub_context = factory.create_sub_context(session_key, subagent_type)

        # 运行 subagent
        result = asyncio.run(runner.run(sub_context, prompt))

        return result

    # 注入回调
    set_spawn_callback(spawn_subagent)
