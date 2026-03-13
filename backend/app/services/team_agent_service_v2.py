"""
TeamAgentService v2 - 使用新架构

保持与旧接口兼容，内部使用新的 AgentRunner
"""
import asyncio
import logging
import time
from typing import List

from backend.app.core.execution.agent_runner import AgentRunner
from backend.app.core.execution.factory import get_factory
from backend.app.team.state import get_bus, shutdown_requests, tracker_lock, POLL_INTERVAL, IDLE_TIMEOUT

logger = logging.getLogger(__name__)


class TeamAgentService:
    """团队 Agent 服务（适配器）"""

    def __init__(self, name: str, role: str, session_key: str, enable_lifecycle: bool = False):
        """
        初始化团队 Agent 服务

        Args:
            name: Teammate 名称
            role: Teammate 角色
            session_key: 会话标识符
            enable_lifecycle: 是否启用生命周期管理（暂未实现）
        """
        # 创建 Context
        factory = get_factory()
        self.context = factory.create_team_context(session_key, name, role)

        # 创建 Runner
        self.runner = AgentRunner()

        # 兼容旧接口
        self.name = name
        self.role = role
        self.llm = self.context.llm
        self.message_bus = get_bus()

        logger.info(f"TeamAgentService v2 initialized | name={name} role={role}")
    async def run(self, prompt: str, history: list = None) -> str:
        """运行 Agent（兼容旧接口）"""
        if history is None:
            history = []
        return await self.runner.run(self.context, prompt, history)

    async def run_loop(self, initial_prompt: str):
        """独立线程中的主循环"""
        messages = []
        idle_start = None

        self._set_status("working")

        if initial_prompt:
            logger.info(f"[{self.name}] Starting with initial task")
            output = await self.run(initial_prompt, messages)
            logger.info(f"[{self.name}] Initial task completed: {output[:100]}")

        while True:
            if self._check_shutdown_request():
                logger.info(f"[{self.name}] Shutdown approved, exiting")
                break

            inbox = self.message_bus.read_inbox(self.name)
            if inbox:
                idle_start = None
                self._set_status("working")
                prompt = self._build_inbox_prompt(inbox)
                output = await self.run(prompt, messages)
                logger.info(f"[{self.name}] Processed inbox: {output[:100]}")
                continue

            task = self._try_claim_task()
            if task:
                idle_start = None
                self._set_status("working")
                prompt = self._build_task_prompt(task)
                output = await self.run(prompt, messages)
                self._complete_task(task["id"], output)
                logger.info(f"[{self.name}] Completed task {task['id']}")
                continue

            if idle_start is None:
                idle_start = time.time()
                self._set_status("idle")
                logger.info(f"[{self.name}] Entering idle state")

            if time.time() - idle_start > IDLE_TIMEOUT:
                self._set_status("shutdown")
                logger.info(f"[{self.name}] Idle timeout, shutting down")
                break

            await asyncio.sleep(POLL_INTERVAL)
    def _set_status(self, status: str):
        """更新 teammate 状态"""
        from backend.app.team.state import get_team
        team = get_team()
        # TODO: 实现状态更新逻辑

    def _check_shutdown_request(self) -> bool:
        """检查是否有 shutdown 请求被批准"""
        with tracker_lock:
            for req_id, req in shutdown_requests.items():
                if req["target"] == self.name and req["status"] == "approved":
                    return True
        return False

    def _try_claim_task(self) -> dict:
        """尝试认领任务"""
        from backend.app.team.state import scan_unclaimed_tasks, claim_task
        tasks = scan_unclaimed_tasks()
        if not tasks:
            return None
        task = tasks[0]
        claim_task(task["id"], self.name)
        return task

    def _complete_task(self, task_id: str, output: str):
        """完成任务"""
        from backend.app.task import get_task_service
        task_service = get_task_service()
        # TODO: 更新任务状态

    def _build_inbox_prompt(self, inbox: List[dict]) -> str:
        """构建收件箱消息的 prompt"""
        lines = ["You have new messages:"]
        for msg in inbox:
            lines.append(f"From {msg['from']}: {msg['content']}")
        lines.append("\nPlease respond appropriately.")
        return "\n".join(lines)

    def _build_task_prompt(self, task: dict) -> str:
        """构建任务的 prompt"""
        return f"Task: {task.get('subject', '')}\n\nDetails: {task.get('description', '')}"
