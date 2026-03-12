"""
Explore Agent 配置
"""
from dataclasses import dataclass
from ..base import AgentConfig


@dataclass
class ExploreAgentConfig(AgentConfig):
    """Explore Agent 配置"""

    def __init__(self):
        super().__init__(
            name="Explore",
            description="Read-only agent for exploring code, finding files, searching",
            tools=[
                "bash",
                "read_file",
                "glob",
                "grep",
                "list_dir",
                "memory_search",
                "memory_write"
            ],
            prompt=(
                "You are an exploration agent. Search and analyze, but never modify files.\n\n"
                "Memory usage:\n"
                "- memory_search(query) - Recall past findings before starting\n"
                "- memory_write(content, category) - Save discoveries:\n"
                "  * category='session' - Temporary findings (file paths, search results)\n"
                "  * category='architecture' - Project patterns/structure (persistent)\n"
                "  * category='tool' - Useful search/exploration techniques (persistent)\n\n"
                "Always save at least one architectural discovery before finishing. Return a concise summary."
            ),
            loop_type="react",
            max_recursion=100,
            enable_memory=True,
        )


@dataclass
class GeneralPurposeAgentConfig(AgentConfig):
    """General-purpose Agent 配置"""

    def __init__(self):
        super().__init__(
            name="general-purpose",
            description="Full agent for implementing features and fixing bugs",
            tools="*",  # all BASE_TOOLS, Task excluded automatically
            prompt=(
                "You are a coding agent. Implement the requested changes efficiently. "
                "Use memory_write(content, 'architecture') to save important patterns you discover."
            ),
            loop_type="react",
            max_recursion=100,
            enable_memory=True,
        )


@dataclass
class PlanAgentConfig(AgentConfig):
    """Plan Agent 配置"""

    def __init__(self):
        super().__init__(
            name="Plan",
            description="规划复杂任务，拆分步骤并创建持久化任务",
            tools=[
                "bash",
                "read_file",
                "glob",
                "grep",
                "list_dir",
                "task_create",
                "task_list",
                "memory_search",
                "memory_write"
            ],
            prompt=(
                "You are a planning agent. Use memory_search to recall past decisions and patterns. "
                "Analyze the codebase, create a numbered implementation plan, and use task_create to create persistent tasks for each step. "
                "IMPORTANT: You can ONLY use memory_write(content, 'session') for temporary findings. "
                "Do NOT write to global memory (architecture/preference/tool categories). Do NOT make code changes."
            ),
            loop_type="react",
            max_recursion=100,
            enable_memory=True,
        )


@dataclass
class CodingAgentConfig(AgentConfig):
    """Coding Agent 配置"""

    def __init__(self):
        super().__init__(
            name="Coding",
            description="生成任何语言的代码并保存到工作空间",
            tools=[
                "workspace_write",
                "workspace_read",
                "memory_search",
                "memory_write"
            ],
            prompt=(
                "You are a coding agent. Generate code in any programming language based on user requirements. "
                "Use memory_search to recall coding patterns. Save all generated code to workspace using workspace_write. "
                "Return the file path when done. Use memory_write(pattern, 'architecture') to save useful patterns."
            ),
            loop_type="react",
            max_recursion=50,
            enable_memory=True,
        )


@dataclass
class ReflectAgentConfig(AgentConfig):
    """Reflect Agent 配置"""

    def __init__(self):
        super().__init__(
            name="Reflect",
            description="Reflection agent: reads relevant files to verify correctness, returns verdict PASS|NEEDS_REVISION with missing/superfluous/suggestion",
            tools=[
                "read_file",
                "memory_search",
                "memory_write"
            ],
            prompt=(
                "你是严格的代码审查员。用 memory_search 召回审查标准和常见问题，用 read_file 读取相关文件后再评判，不要仅凭 prompt 中的描述下结论。\n"
                "Return ONLY valid JSON with keys:\n"
                "  verdict: 'PASS' or 'NEEDS_REVISION'\n"
                "  missing: list of missing aspects\n"
                "  superfluous: list of unnecessary/redundant parts\n"
                "  suggestion: concise actionable improvement advice (empty string if PASS)\n"
                "Use memory_write(issue, 'architecture') to save recurring issues. No explanation outside the JSON."
            ),
            loop_type="react",
            max_recursion=50,
            enable_memory=True,
        )


@dataclass
class ReflexionAgentConfig(AgentConfig):
    """Reflexion Agent 配置"""

    def __init__(self):
        super().__init__(
            name="Reflexion",
            description="Reflexion agent: two-phase Responder+Revisor. Gathers context via tools, critiques initial response, then produces improved version",
            tools=[
                "bash",
                "read_file",
                "glob",
                "grep",
                "list_dir",
                "memory_search",
                "memory_write"
            ],
            prompt=(
                "You are a Reflexion agent with two phases.\n"
                "Phase 1 - Responder: use memory_search to recall improvement patterns, critically analyze the initial response against the goal. "
                "Identify what is MISSING and what is SUPERFLUOUS.\n"
                "Phase 2 - Revisor: produce an improved response that addresses all critique points. "
                "Use memory_write(pattern, 'architecture') to save effective patterns.\n"
                'Return ONLY valid JSON: {"critique": "...", "revised": "..."}'
            ),
            loop_type="react",
            max_recursion=80,
            enable_memory=True,
        )
