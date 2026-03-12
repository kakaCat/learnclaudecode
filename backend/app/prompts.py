import os
from datetime import datetime
from backend.app.skills import SKILL_LOADER
from backend.app.session import get_store


def build_system_prompt(
    session_key: str = "",
    mode: str = "full",
    memory_context: str = "",
) -> str:
    """
    构建系统提示词（参考 s06_intelligence.py 的 8 层组装）

    Args:
        session_key: 会话 key
        mode: 加载模式（full/minimal/none）
        memory_context: 自动召回的记忆上下文

    Returns:
        完整的系统提示词
    """
    store = get_store()
    sections = []

    # 第 1 层: 身份 - 来自 IDENTITY.md 或默认值
    bootstrap_data = {}
    if session_key and mode != "none":
        store.set_current_key(session_key)
        bootstrap_data = store.load_bootstrap(mode)

    identity = bootstrap_data.get("IDENTITY.md", "").strip()
    if identity:
        sections.append(identity)
    else:
        sections.append(f"你是一个运行在 {os.getcwd()} 的 CLI 智能体。")

    # 第 2 层: 灵魂 - 人格注入
    if mode == "full":
        soul = bootstrap_data.get("SOUL.md", "").strip()
        if soul:
            sections.append(f"## Personality\n\n{soul}")

    # 第 3 层: 工具使用指南
    tools_md = bootstrap_data.get("TOOLS.md", "").strip()
    if tools_md:
        sections.append(f"## Tool Usage Guidelines\n\n{tools_md}")

    # 第 4 层: 技能
    if mode == "full":
        skills_desc = SKILL_LOADER.get_descriptions()
        if skills_desc:
            sections.append(f"## Available Skills\n\n{skills_desc}")

    # 第 5 层: 记忆
    if mode == "full":
        mem_md = bootstrap_data.get("MEMORY.md", "").strip()
        parts = []
        if mem_md:
            parts.append(f"### Evergreen Memory\n\n{mem_md}")
        if memory_context:
            parts.append(f"### Recalled Memories (auto-searched)\n\n{memory_context}")
        if parts:
            sections.append("## Memory\n\n" + "\n\n".join(parts))
            sections.append(
                "## Memory Instructions\n\n"
                "- Use memory_write to save important user facts and preferences.\n"
                "- Reference remembered facts naturally in conversation.\n"
                "- Use memory_search to recall specific past information."
            )

    # 第 6 层: Bootstrap 上下文
    if mode in ("full", "minimal"):
        for name in ["HEARTBEAT.md", "BOOTSTRAP.md", "AGENTS.md", "USER.md"]:
            content = bootstrap_data.get(name, "").strip()
            if content:
                sections.append(f"## {name.replace('.md', '')}\n\n{content}")

    # 第 7 层: 运行时上下文
    workspace_path = f".sessions/{session_key}/workspace/" if session_key else ".sessions/<key>/workspace/"
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sections.append(
        f"## Runtime Context\n\n"
        f"- Session key: {session_key or '(未设置)'}\n"
        f"- Current time: {current_time}\n"
        f"- Prompt mode: {mode}\n"
        f"- Workspace: {workspace_path}"
    )

    system_prompt = "\n\n".join(sections)

    # 调试输出
    print("=" * 80)
    print("🔍 build_system_prompt 调试输出")
    print("=" * 80)
    print(f"📊 总字符数: {len(system_prompt)}")
    print(f"📊 总行数: {len(system_prompt.splitlines())}")
    print(f"🔑 Session key: {session_key}")
    print(f"⚙️  Mode: {mode}")
    print("=" * 80)
    print(system_prompt)
    print("=" * 80)

    return system_prompt


def get_system_prompt(session_key: str = "") -> str:
    """
    获取系统提示词（向后兼容接口）

    Args:
        session_key: 会话 key

    Returns:
        系统提示词
    """
    return build_system_prompt(session_key, mode="full")


def get_teammate_system_prompt(name: str, role: str, session_key: str = "") -> str:
    """
    获取 Teammate 的系统提示词

    Args:
        name: Teammate 名称
        role: Teammate 角色
        session_key: 会话 key

    Returns:
        系统提示词
    """
    from backend.app.tools.base import WORKDIR
    from backend.app.session import get_team_config_path
    import json

    # 获取团队名称
    config_path = get_team_config_path()
    team_name = "default"
    if config_path.exists():
        config = json.loads(config_path.read_text())
        team_name = config.get("team_name", "default")

    # 构建基础 prompt
    base_prompt = build_system_prompt(session_key, mode="minimal")

    # 添加 Teammate 特定信息
    teammate_prompt = (
        f"{base_prompt}\n\n"
        f"## Teammate Identity\n\n"
        f"You are '{name}', role: {role}, team: {team_name}, working at {WORKDIR}.\n\n"
        f"## Communication\n\n"
        f"- Use send_message(to, content) to communicate with other teammates or lead\n"
        f"- Use read_inbox_tool() to check your inbox\n"
        f"- Use claim_task_tool() to claim tasks from the queue\n"
        f"- Use report_progress_tool(task_id, status, message) to report progress\n\n"
        f"## Workflow\n\n"
        f"1. Check inbox for messages\n"
        f"2. Claim tasks from the queue if available\n"
        f"3. Execute tasks using available tools\n"
        f"4. Report progress and results\n"
        f"5. Enter idle state when no work available\n"
    )

    return teammate_prompt


def auto_recall_memory(session_key: str, user_message: str) -> str:
    """
    根据用户消息自动搜索相关记忆

    Args:
        session_key: 会话 key
        user_message: 用户消息

    Returns:
        记忆上下文字符串
    """
    if not session_key:
        return ""

    store = get_store()
    store.set_current_key(session_key)
    results = store.hybrid_search_memory(user_message, top_k=3)

    if not results:
        return ""

    return "\n".join(f"- [{r['path']}] {r['snippet']}" for r in results)


def print_system_prompt(session_key: str = "", mode: str = "full", output_file: str = None):
    """
    打印或保存系统提示词到文件

    Args:
        session_key: 会话 key
        mode: 加载模式（full/minimal/none）
        output_file: 输出文件路径，如果为 None 则打印到控制台
    """
    prompt = build_system_prompt(session_key, mode)

    if output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(prompt)
        print(f"✅ 系统提示词已保存到: {output_file}")
        print(f"📊 总字符数: {len(prompt)}")
        print(f"📊 总行数: {len(prompt.splitlines())}")
    else:
        print("=" * 80)
        print("系统提示词 (System Prompt)")
        print("=" * 80)
        print(prompt)
        print("=" * 80)
        print(f"📊 总字符数: {len(prompt)}")
        print(f"📊 总行数: {len(prompt.splitlines())}")


if __name__ == "__main__":
    import sys

    # 支持命令行调用
    # python backend/app/prompts.py [session_key] [mode] [output_file]
    session_key = sys.argv[1] if len(sys.argv) > 1 else ""
    mode = sys.argv[2] if len(sys.argv) > 2 else "full"
    output_file = sys.argv[3] if len(sys.argv) > 3 else None

    print_system_prompt(session_key, mode, output_file)
