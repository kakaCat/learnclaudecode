"""
Subagent 自定义异常
"""


class SubagentError(Exception):
    """Subagent 基础异常"""
    pass


class AgentNotFoundError(SubagentError):
    """Agent 类型不存在"""

    def __init__(self, agent_type: str):
        self.agent_type = agent_type
        super().__init__(f"Unknown agent type: {agent_type}")


class ContextOverflowError(SubagentError):
    """上下文溢出异常"""

    def __init__(self, current_tokens: int, max_tokens: int):
        self.current_tokens = current_tokens
        self.max_tokens = max_tokens
        super().__init__(
            f"Context overflow: {current_tokens} tokens exceeds limit {max_tokens}"
        )


class PromptTooLargeError(SubagentError):
    """Prompt 过大异常"""

    def __init__(self, prompt_length: int, max_length: int):
        self.prompt_length = prompt_length
        self.max_length = max_length
        super().__init__(
            f"Prompt too large: {prompt_length} chars exceeds limit {max_length}"
        )


class LoopExecutionError(SubagentError):
    """循环执行异常"""

    def __init__(self, loop_type: str, message: str):
        self.loop_type = loop_type
        super().__init__(f"[{loop_type}] {message}")


class ToolInvocationError(SubagentError):
    """工具调用异常"""

    def __init__(self, tool_name: str, error: Exception):
        self.tool_name = tool_name
        self.original_error = error
        super().__init__(f"Tool '{tool_name}' failed: {error}")


class ConfigValidationError(SubagentError):
    """配置验证异常"""

    def __init__(self, field: str, message: str):
        self.field = field
        super().__init__(f"Invalid config field '{field}': {message}")
