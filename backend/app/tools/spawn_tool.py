import logging

from langchain_core.tools import tool

from backend.app.subagents import AGENT_TYPES, get_descriptions, run_subagent

logger = logging.getLogger(__name__)


def make_task_tool(base_tools: list):
    """Task tool factory. Injects base_tools into closure for subagent use."""
    descriptions = get_descriptions()
    desc = (
        "Spawn a subagent for a focused subtask. Subagents run in ISOLATED context.\n\n"
        f"Agent types:\n{descriptions}\n\n"
        "Use for subtasks needing focused exploration or implementation without polluting main context."
    )

    @tool(description=desc)
    def Task(description: str, prompt: str, subagent_type: str) -> str:
        logger.info("Task: [%s] %s", subagent_type, description)
        if subagent_type not in AGENT_TYPES:
            return f"Error: Unknown agent type '{subagent_type}'. Choose from: {list(AGENT_TYPES.keys())}"
        return run_subagent(description, prompt, subagent_type, base_tools)

    return Task
