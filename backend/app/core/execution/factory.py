"""
ContextFactory - 上下文工厂

简化 Context 创建，统一依赖注入
"""
from backend.app.core.context.main_context import MainContext
from backend.app.core.context.sub_context import SubContext
from backend.app.core.context.team_context import TeamContext
from backend.app.core.execution.config import CONFIG


class ContextFactory:
    """上下文工厂"""

    def __init__(self):
        # 延迟初始化共享资源
        self._llm = None
        self._session_store = None
        self._tracer = None

    def _ensure_resources(self):
        """确保共享资源已初始化"""
        if self._llm is None:
            from backend.app.llm import get_llm
            self._llm = get_llm()

        if self._session_store is None:
            from backend.app.session import get_store
            self._session_store = get_store()

        if self._tracer is None:
            from backend.app.core.guards.tracer import Tracer
            self._tracer = Tracer()

    def create_main_context(self, session_key: str, recursion_limit: int = None) -> MainContext:
        """创建主 Agent 上下文"""
        self._ensure_resources()
        if recursion_limit is None:
            recursion_limit = CONFIG.MAX_RECURSION_LIMIT
        return MainContext(
            session_key=session_key,
            llm=self._llm,
            session_store=self._session_store,
            tracer=self._tracer,
            recursion_limit=recursion_limit
        )

    def create_sub_context(self, session_key: str, subagent_type: str, recursion_limit: int = 50) -> SubContext:
        """创建子 Agent 上下文"""
        self._ensure_resources()
        return SubContext(
            session_key=session_key,
            subagent_type=subagent_type,
            llm=self._llm,
            session_store=self._session_store,
            tracer=self._tracer,
            recursion_limit=recursion_limit
        )

    def create_team_context(
        self,
        session_key: str,
        name: str,
        role: str
    ) -> TeamContext:
        """创建团队 Agent 上下文"""
        self._ensure_resources()
        return TeamContext(
            session_key=session_key,
            name=name,
            role=role,
            llm=self._llm,
            session_store=self._session_store,
            tracer=self._tracer
        )


# 全局工厂实例
_factory = ContextFactory()


def get_factory() -> ContextFactory:
    """获取全局工厂实例"""
    return _factory
