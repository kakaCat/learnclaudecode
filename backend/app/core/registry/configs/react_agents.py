"""
ReAct Agent 配置 - 推理+行动循环

设计模式：ReAct (Reasoning + Acting)
- 使用 ReAct 循环
- 支持工具调用
- 思考 → 行动 → 观察 → 思考...
- 适合：代码探索、功能实现、文件操作等需要工具的任务
"""
from dataclasses import dataclass
from backend.app.core.registry.base import AgentConfig


@dataclass
class ExploreAgentConfig(AgentConfig):
    """
    Explore Agent - 代码探索

    设计模式：ReAct
    用途：只读探索代码库，查找文件，搜索内容
    """

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
    """
    General-purpose Agent - 通用开发

    设计模式：ReAct
    用途：实现功能、修复 bug、完整的开发任务
    """

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
class CodingAgentConfig(AgentConfig):
    """
    Coding Agent - 代码生成

    设计模式：ReAct
    用途：生成任何语言的代码并保存到工作空间
    """

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
