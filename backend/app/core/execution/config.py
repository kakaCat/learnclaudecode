"""
Subagent 配置常量

集中管理所有魔法数字和配置参数
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class SubagentConfig:
    """Subagent 全局配置"""

    # 上下文管理
    MAX_CONTEXT_TOKENS: int = 128_000
    """Subagent 最大上下文 token 数（对齐模型限制）"""

    COMPRESSION_THRESHOLD: int = 102_000
    """触发压缩的 token 阈值（80% 模型限制）"""

    # OODA 循环配置
    MAX_OODA_CYCLES: int = 6
    """OODA 循环最大迭代次数"""

    OBSERVATION_COMPRESSION_LIMIT: int = 10
    """观察结果压缩阈值（超过此数量时压缩）"""

    OODA_COMPRESSION_INTERVAL: int = 3
    """OODA 循环压缩间隔（每 N 个 cycle 压缩一次）"""

    # ReAct 循环配置
    MAX_RECURSION_LIMIT: int = 1000
    """ReAct 循环最大递归深度（设置为 1000 以应对复杂任务）"""

    # Prompt 管理
    MAX_PROMPT_TOKENS: int = 100_000
    """单个 prompt 最大 token 数"""

    PROMPT_TRUNCATE_RATIO: float = 0.9
    """Prompt 截断时保留比例（尝试在行边界截断）"""

    CHARS_PER_TOKEN: int = 4
    """估算 token 数的字符比例（中英文混合）"""

    # 工具调用
    TOOL_RESULT_MAX_LENGTH: int = 800
    """工具调用结果最大长度（字符）"""

    TOOL_SUMMARY_MAX_LENGTH: int = 500
    """工具调用总结最大长度（字符）"""

    # 输出配置
    OUTPUT_PREVIEW_LENGTH: int = 200
    """输出预览长度（用于日志和 tracer）"""

    OBSERVATION_PREVIEW_LENGTH: int = 200
    """观察结果预览长度"""

    # 超时配置
    TOOL_TIMEOUT_MS: int = 30_000
    """工具调用超时时间（毫秒）"""

    LLM_TIMEOUT_MS: int = 60_000
    """LLM 调用超时时间（毫秒）"""


# 全局配置实例
CONFIG = SubagentConfig()
