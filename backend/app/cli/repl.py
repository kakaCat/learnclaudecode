"""
REPL (Read-Eval-Print Loop) main interface
"""
import asyncio
from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.styles import Style
from prompt_toolkit.completion import WordCompleter

from backend.app.cli.commands import CommandHandler
from backend.app.cli.task_queue import TaskQueue

COMMANDS = ["/compact", "/tasks", "/team", "/inbox", "/sessions", "/insight", "/insight-llm"]
STYLE = Style.from_dict({"prompt": "ansicyan bold"})
PROMPT = [("class:prompt", "agent >> ")]


async def run_repl(agent, history: list):
    """
    Run the interactive REPL

    Args:
        agent: MainAgentService instance or None (will be created on first query)
        history: Conversation history list
    """
    session = PromptSession(
        history=InMemoryHistory(),
        mouse_support=False,
        style=STYLE,
        completer=WordCompleter(COMMANDS, sentence=True),
    )

    # 使用字典包装 agent，以便在函数内修改
    agent_holder = {"agent": agent}

    command_handler = CommandHandler(agent_holder, history)
    task_queue = TaskQueue()

    print("Ctrl+C / Ctrl+D / 'exit' to quit. ↑↓ for history.")
    print("💡 Agent 运行时可以继续输入命令（输入会排队执行）\n")

    while True:
        try:
            query = (await session.prompt_async(PROMPT)).strip()
        except (EOFError, KeyboardInterrupt):
            await _handle_exit(task_queue)
            break

        if not query or query in ("q", "exit", "quit"):
            if await _confirm_exit(session, task_queue):
                break
            continue

        # Handle commands
        if await command_handler.handle(query):
            continue

        # Handle agent queries
        await _handle_agent_query(query, agent_holder, history, task_queue)


async def _handle_exit(task_queue: TaskQueue):
    """Handle exit with cleanup"""
    if task_queue.is_running():
        await task_queue.cancel_current()
    print("\nBye.")


async def _confirm_exit(session: PromptSession, task_queue: TaskQueue) -> bool:
    """
    Confirm exit if tasks are running

    Returns:
        True if should exit, False otherwise
    """
    if task_queue.is_running():
        print("⚠️  有任务正在运行，确认退出？(y/n)")
        confirm = (await session.prompt_async([("class:prompt", "confirm >> ")])).strip().lower()
        if confirm != "y":
            return False
        await task_queue.cancel_current()
    return True


async def _handle_agent_query(query: str, agent_holder: dict, history: list, task_queue: TaskQueue):
    """
    Handle agent query execution

    Args:
        query: User query
        agent_holder: Dict containing agent instance (may be None initially)
        history: Conversation history
        task_queue: TaskQueue instance
    """
    async def run_agent_task():
        try:
            # 首次查询时创建 session
            if agent_holder["agent"] is None:
                from backend.app.session import new_session_key
                from backend.app.services.main_agent_service_v2 import MainAgentService

                session_key = new_session_key()
                agent_holder["agent"] = MainAgentService(session_key=session_key, enable_lifecycle=True)
                print(f"✅ Created session '{session_key}'\n")

            result = await agent_holder["agent"].run(query, history)
            print(result)
            print()
        except asyncio.CancelledError:
            print("\n⚠️  任务已取消")
            print()
            raise
        except Exception as e:
            print(f"\n❌ 任务执行出错: {e}")
            import traceback
            traceback.print_exc()
            print()

    await task_queue.submit(run_agent_task, query)
