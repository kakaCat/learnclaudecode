import logging

from langchain_core.tools import tool

from backend.app.subagents import AGENT_TYPES, get_descriptions, run_subagent

logger = logging.getLogger(__name__)


def make_task_tool():
    """Task tool factory. Subagent tools are resolved from tools_manager at call time."""
    from backend.app.tools_manager import tools_manager

    descriptions = get_descriptions()
    desc = (
        "Spawn a subagent for a focused subtask. Subagents run in ISOLATED context.\n\n"
        f"Agent types:\n{descriptions}\n\n"
        "Use for subtasks needing focused exploration or implementation without polluting main context."
    )

    @tool(description=desc)
    def Task(description: str, prompt: str, subagent_type: str, recursion_limit: int = 100) -> str:
        logger.info("Task: [%s] %s", subagent_type, description)
        if subagent_type not in AGENT_TYPES:
            return f"Error: Unknown agent type '{subagent_type}'. Choose from: {list(AGENT_TYPES.keys())}"
        base_tools = [t for t in tools_manager.get_tools() if t.name != "Task"]
        return run_subagent(description, prompt, subagent_type, base_tools, recursion_limit)

    return Task
