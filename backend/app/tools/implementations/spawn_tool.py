import logging

from backend.app.tools.base import tool

from backend.app.subagents import AGENT_TYPES, get_descriptions

logger = logging.getLogger(__name__)


def make_task_tool(main_context=None):
    """
    Task tool factory.

    Args:
        main_context: MainContext 实例（用于获取 session_key）
    """
    descriptions = get_descriptions()
    desc = (
        "Spawn a subagent for a focused subtask. Subagents run in ISOLATED context.\n\n"
        f"Agent types:\n{descriptions}\n\n"
        "Use for subtasks needing focused exploration or implementation without polluting main context."
    )

    @tool(tags=["main"], description=desc)
    def Task(description: str, prompt: str, subagent_type: str, recursion_limit: int = 100) -> str:
        logger.info("Task: [%s] %s", subagent_type, description)

        if subagent_type not in AGENT_TYPES:
            return f"Error: Unknown agent type '{subagent_type}'. Choose from: {list(AGENT_TYPES.keys())}"

        if main_context is None:
            return "Error: Task tool not properly initialized with MainContext"

        # 创建独立的 SubagentContext（与 MainContext 独立，只共享 session_key）
        from backend.app.context.subagent_context import SubagentContext
        sub_context = SubagentContext(main_context.session_key, subagent_type)

        # 使用 subagents 模块的运行逻辑（保留自定义 loop）
        from backend.app.subagents import run_subagent_with_context
        try:
            result = run_subagent_with_context(
                sub_context=sub_context,
                description=description,
                prompt=prompt,
                recursion_limit=recursion_limit
            )
            return result
        except Exception as e:
            logger.error(f"Subagent execution failed: {e}", exc_info=True)
            return f"Error: Subagent execution failed - {str(e)}"

    return Task

