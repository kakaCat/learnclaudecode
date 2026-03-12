"""
MainAgentService 适配器 - 使用新架构

保持与旧接口兼容，内部使用新的 AgentRunner
"""
from backend.app.core import AgentRunner
from backend.app.core.factory import get_factory
from backend.app.core.task_integration import setup_task_tool


class MainAgentService:
    """主 Agent 服务（适配器）"""

    def __init__(self, session_key: str = None, enable_lifecycle: bool = True):
        """
        初始化主 Agent 服务

        Args:
            session_key: 会话标识符
            enable_lifecycle: 是否启用生命周期管理（暂未实现）
        """
        # 初始化 Task Tool（只需要一次）
        setup_task_tool()

        # 创建 Context
        factory = get_factory()
        self.context = factory.create_main_context(session_key or "")

        # 创建 Runner
        self.runner = AgentRunner()

        # 兼容旧接口
        self.llm = self.context.llm

    def switch_session(self, session_key: str):
        """切换会话"""
        factory = get_factory()
        self.context = factory.create_main_context(session_key)

    async def run(self, prompt: str, history: list = None) -> str:
        """
        运行 Agent

        Args:
            prompt: 用户输入
            history: 历史消息列表

        Returns:
            AI 输出
        """
        if history is None:
            history = []

        return await self.runner.run(self.context, prompt, history)
