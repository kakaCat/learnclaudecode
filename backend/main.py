#!/usr/bin/env python3
"""
backend/main.py - REPL entry point for AgentService

Usage:
    python -m backend.main                    # New session
    python -m backend.main --resume           # Resume latest session
    python -m backend.main --resume <key>     # Resume specific session
    python -m backend.main "task"             # Subagent mode (single run)

Commands:
  /compact     - manually compress conversation history
  /tasks       - list all persistent tasks
  /team        - list all teammates and their status
  /inbox       - read and drain lead's inbox
  /sessions    - list all saved sessions
  /insight     - analyze session trace (performance, bottlenecks, optimization)
  /insight-llm - analyze LLM call quality (uses LLM)
"""
import asyncio
import json
import sys

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.styles import Style

COMMANDS = ["/compact", "/tasks", "/team", "/inbox", "/sessions", "/insight", "/insight-llm"]

from backend.app.agent import AgentService
from backend.app.context import AgentContext
from backend.app.memory.compaction import auto_compact
from backend.app.task.task_manager import TaskManager
from backend.app.team.state import get_bus, get_team
from backend.app.session import list_sessions, load_session, get_session_dir, SESSIONS_DIR

STYLE = Style.from_dict({"prompt": "ansicyan bold"})
PROMPT = [("class:prompt", "agent >> ")]


async def interactive(agent: AgentService, history: list):
    session = PromptSession(
        history=InMemoryHistory(),
        mouse_support=False,
        style=STYLE,
        completer=WordCompleter(COMMANDS, sentence=True),
    )
    task_mgr = TaskManager()
    print("Ctrl+C / Ctrl+D / 'exit' to quit. ↑↓ for history.")
    print("💡 Agent 运行时可以继续输入命令（输入会排队执行）\n")

    running_task = None
    query_queue = []

    while True:
        try:
            query = (await session.prompt_async(PROMPT)).strip()
        except (EOFError, KeyboardInterrupt):
            if running_task and not running_task.done():
                print("\n⚠️  正在取消运行中的任务...")
                running_task.cancel()
                try:
                    await running_task
                except asyncio.CancelledError:
                    pass
            print("\nBye.")
            break

        if not query or query in ("q", "exit", "quit"):
            if running_task and not running_task.done():
                print("⚠️  有任务正在运行，确认退出？(y/n)")
                confirm = (await session.prompt_async([("class:prompt", "confirm >> ")])).strip().lower()
                if confirm != "y":
                    continue
                running_task.cancel()
            break

        if query == "/compact":
            if history:
                print("[manual compact]")
                new_history = auto_compact(history, agent.llm)
                history.clear()
                history.extend(new_history)
            else:
                print("No history to compact.")
            continue

        if query == "/tasks":
            print(task_mgr.list_all())
            continue

        if query == "/team":
            print(get_team().list_all())
            continue

        if query == "/inbox":
            msgs = get_bus().read_inbox("lead")
            print(json.dumps(msgs, indent=2, ensure_ascii=False) if msgs else "Inbox empty.")
            continue

        if query == "/sessions":
            keys = list_sessions()
            if not keys:
                print("No saved sessions.")
                continue
            from prompt_toolkit.shortcuts import radiolist_dialog
            selected = radiolist_dialog(
                title="Sessions",
                text="Select a session to resume (↑↓ to move, Enter to confirm, Esc to cancel):",
                values=[(k, k) for k in keys],
            ).run()
            if selected:
                history.clear()
                history.extend(load_session("main", selected))
                agent.switch_session(selected)  # 切换session并重置状态
                print(f"Resumed session '{selected}' ({len(history)} messages)\n")
            continue

        if query == "/insight":
            from backend.app.insight import analyze_trace
            from prompt_toolkit.shortcuts import radiolist_dialog

            keys = list_sessions()
            if not keys:
                print("⚠️  没有找到任何 session")
                continue

            # 让用户选择 session
            selected = radiolist_dialog(
                title="选择 Session 进行性能分析",
                text="选择要分析的 session (↑↓ 移动, Enter 确认, Esc 取消):",
                values=[(k, k) for k in keys],
            ).run()

            if not selected:
                print("已取消")
                continue

            # 分析选中的 session
            trace_file = SESSIONS_DIR / selected / "trace.jsonl"
            if not trace_file.exists():
                print(f"⚠️  Session '{selected}' 没有 trace 数据")
                continue

            print()
            print(f"📊 分析 session: {selected}")
            print()
            analyze_trace(trace_file)
            print()
            continue

        if query == "/insight-llm":
            from backend.app.llm_insight import analyze_llm_quality
            from prompt_toolkit.shortcuts import radiolist_dialog

            keys = list_sessions()
            if not keys:
                print("⚠️  没有找到任何 session")
                continue

            # 让用户选择 session
            selected = radiolist_dialog(
                title="选择 Session 进行质量分析",
                text="选择要分析的 session (↑↓ 移动, Enter 确认, Esc 取消):",
                values=[(k, k) for k in keys],
            ).run()

            if not selected:
                print("已取消")
                continue

            # 分析选中的 session
            trace_file = SESSIONS_DIR / selected / "trace.jsonl"
            if not trace_file.exists():
                print(f"⚠️  Session '{selected}' 没有 trace 数据")
                continue

            print()
            print(f"🧠 分析 session: {selected}")
            print("   使用 LLM 分析调用质量（这会消耗一些 API token）...")
            print()
            analyze_llm_quality(trace_file, agent.llm)
            print()
            continue

        # 处理 agent 查询
        if running_task and not running_task.done():
            print(f"⏳ 任务正在运行，已加入队列（队列长度: {len(query_queue) + 1}）")
            query_queue.append(query)
        else:
            # 创建新任务
            async def run_agent_task(q):
                try:
                    result = await agent.run(q, history)
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

            running_task = asyncio.create_task(run_agent_task(query))

            # 等待任务完成（不使用 wait_for 避免超时取消任务）
            try:
                await running_task
            except asyncio.CancelledError:
                pass

            # 处理队列中的下一个任务
            while query_queue:
                next_query = query_queue.pop(0)
                print(f"\n▶️  执行队列任务: {next_query[:50]}...")
                running_task = asyncio.create_task(run_agent_task(next_query))
                try:
                    await running_task
                except asyncio.CancelledError:
                    query_queue.clear()
                    break


if __name__ == "__main__":
    # 应用启动时加载 MCP 工具（只加载一次）
    from backend.app.tools.manager import tool_manager
    asyncio.run(tool_manager.load_mcp_tools())

    args = sys.argv[1:]
    resume_key = None

    if args and args[0] == "--resume":
        keys = list_sessions()
        if not keys:
            print("No saved sessions found.")
            sys.exit(1)
        resume_key = args[1] if len(args) > 1 else keys[0]
        if resume_key not in keys:
            print(f"Session '{resume_key}' not found. Available:\n" + "\n".join(keys))
            sys.exit(1)
        args = args[2:] if len(args) > 1 else []

    agent = AgentService()

    # 启动生命周期管理系统
    from backend.app.reliability import start_lifecycle, get_lifecycle_status
    try:
        print("🔄 启动生命周期管理系统...")
        if start_lifecycle():
            print("✅ 生命周期管理系统启动成功")
            status = get_lifecycle_status()
            print(f"📊 心跳间隔: {status.get('heartbeat_system', {}).get('interval_seconds', 'N/A')}秒")
            print(f"🛡️ 守护服务: {status.get('guard_system', {}).get('services_healthy', 'N/A')}/{status.get('guard_system', {}).get('services_total', 'N/A')}")
        else:
            print("⚠️ 生命周期管理系统启动失败，继续运行")
    except Exception as e:
        print(f"❌ 生命周期管理系统启动异常: {e}")
        import traceback
        traceback.print_exc()

    history = []

    if resume_key:
        history = load_session("main", resume_key)
        agent.switch_session(resume_key)  # 切换session并重置状态
        print(f"Resumed session '{resume_key}' ({len(history)} messages)\n")

    if args:
        # Subagent mode: single run
        import asyncio
        result = asyncio.run(agent.run(args[0], history))
        print(result)
    else:
        import asyncio
        asyncio.run(interactive(agent, history))
