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
import sys

from backend.app.services.main_agent_service_v2 import MainAgentService
from backend.app.session import list_sessions, load_session, new_session_key
from backend.app.cli.repl import run_repl


if __name__ == "__main__":
    # 应用启动时加载 MCP 工具（只加载一次）
    # 暂时禁用 MCP 加载，调试其他问题
    # from backend.app.tools.manager import tool_manager
    # asyncio.run(tool_manager.load_mcp_tools())

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

    # 创建 MainAgentContext 和 AgentService
    if resume_key:
        agent = MainAgentService(session_key=resume_key, enable_lifecycle=True)
    else:
        agent = None  # 延迟创建，首次查询时创建

    # 启动生命周期管理系统
    from backend.app.reliability import start_lifecycle, get_lifecycle_status
    try:
        if start_lifecycle():
            status = get_lifecycle_status()
            print(f"✅ 生命周期系统已启动 (心跳: {status.get('heartbeat_system', {}).get('interval_seconds', 'N/A')}s)")
    except Exception as e:
        print(f"⚠️ 生命周期系统启动失败: {e}")

    history = []

    if resume_key:
        history = load_session("main", resume_key)
        print(f"Resumed session '{resume_key}' ({len(history)} messages)\n")
    else:
        print("Ready (session will be created on first query)\n")

    if args:
        # Subagent mode: single run
        if agent is None:
            agent = MainAgentService(session_key=new_session_key(), enable_lifecycle=True)
        result = asyncio.run(agent.run(args[0], history))
        print(result)
    else:
        asyncio.run(run_repl(agent, history))
