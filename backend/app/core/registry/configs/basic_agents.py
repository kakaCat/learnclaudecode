"""
Explore Agent 配置
"""
from dataclasses import dataclass
from backend.app.core.registry.base import AgentConfig


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
            description="规划复杂任务，拆分步骤",
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
                "You are a planning agent using OODA loop.\n\n"
                "OODA 循环流程：\n"
                "- **Observe（观察）**: 用 memory_search 召回过去的规划经验，用 glob/grep/read_file 探索代码库\n"
                "- **Orient（定向）**: 分析项目结构、识别实现步骤和依赖关系\n"
                "- **Decide（决策）**: 决定任务拆分方式、优先级和执行顺序\n"
                "- **Act（行动）**: 用 memory_write(plan, 'session') 保存规划信息\n\n"
                "IMPORTANT: You can ONLY use memory_write(content, 'session') for temporary findings. "
                "Do NOT write to global memory (architecture/preference/tool categories). Do NOT make code changes."
            ),
            loop_type="ooda",
            max_cycles=20,
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
                "你是严格的代码审查员，使用 OODA 循环进行审查。\n\n"
                "OODA 循环流程：\n"
                "- **Observe（观察）**: 用 read_file 读取相关文件，用 memory_search 召回审查标准\n"
                "- **Orient（定向）**: 分析代码质量、识别问题（缺失/冗余/可改进）\n"
                "- **Decide（决策）**: 判断 PASS 或 NEEDS_REVISION\n"
                "- **Act（行动）**: 返回 JSON 结果，用 memory_write 保存常见问题模式\n\n"
                "Return ONLY valid JSON with keys:\n"
                "  verdict: 'PASS' or 'NEEDS_REVISION'\n"
                "  missing: list of missing aspects\n"
                "  superfluous: list of unnecessary/redundant parts\n"
                "  suggestion: concise actionable improvement advice (empty string if PASS)\n"
                "No explanation outside the JSON."
            ),
            loop_type="ooda",
            max_cycles=20,
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
                "You are a Reflexion agent using OODA loop with two phases.\n\n"
                "OODA 循环流程：\n"
                "- **Observe（观察）**: 用 memory_search 召回改进模式，收集上下文信息\n"
                "- **Orient（定向）**: Phase 1 - Responder，分析初始响应的缺失和冗余\n"
                "- **Decide（决策）**: Phase 2 - Revisor，决定如何改进\n"
                "- **Act（行动）**: 产生改进版本，用 memory_write 保存有效模式\n\n"
                'Return ONLY valid JSON: {"critique": "...", "revised": "..."}'
            ),
            loop_type="ooda",
            max_cycles=20,
            enable_memory=True,
        )
