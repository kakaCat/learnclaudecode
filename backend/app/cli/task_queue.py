"""
Task queue management for CLI
"""
import asyncio
from typing import Optional, Callable, Awaitable


class TaskQueue:
    """Manage async task execution with queuing support"""

    def __init__(self):
        self.running_task: Optional[asyncio.Task] = None
        self.queue: list = []

    def is_running(self) -> bool:
        """Check if a task is currently running"""
        return self.running_task is not None and not self.running_task.done()

    async def submit(self, coro: Callable[[], Awaitable], description: str = ""):
        """
        Submit a task for execution

        Args:
            coro: Coroutine to execute
            description: Task description for display

        If a task is already running, the new task is queued.
        """
        if self.is_running():
            print(f"⏳ 任务正在运行，已加入队列（队列长度: {len(self.queue) + 1}）")
            self.queue.append((coro, description))
        else:
            await self._execute_task(coro)
            await self._process_queue()

    async def _execute_task(self, coro: Callable[[], Awaitable]):
        """Execute a single task"""
        self.running_task = asyncio.create_task(coro())
        try:
            await self.running_task
        except asyncio.CancelledError:
            pass

    async def _process_queue(self):
        """Process queued tasks"""
        while self.queue:
            coro, description = self.queue.pop(0)
            if description:
                print(f"\n▶️  执行队列任务: {description[:50]}...")
            self.running_task = asyncio.create_task(coro())
            try:
                await self.running_task
            except asyncio.CancelledError:
                self.queue.clear()
                break

    async def cancel_current(self):
        """Cancel the currently running task"""
        if self.is_running():
            print("\n⚠️  正在取消运行中的任务...")
            self.running_task.cancel()
            try:
                await self.running_task
            except asyncio.CancelledError:
                pass

    def clear_queue(self):
        """Clear all queued tasks"""
        self.queue.clear()
