"""
Action Commitment Guard - 检测 "说了要做但没做" 的违规行为

问题：Agent 说 "现在创建网页" 但没有调用工具就结束
原因：LangGraph 的停止条件是 tool_calls 为空，Agent 只输出文字会被判定为完成
解决：检测承诺性语句（"现在/接下来/让我做X"），如果没有工具调用则警告
"""
import re
from typing import Optional
from langchain_core.messages import AIMessage


class ActionCommitmentGuard:
    """
    检测 Agent 是否违反 "先做后说" 原则

    违规模式：
    - "现在创建..."
    - "接下来我将..."
    - "让我..."

    但没有实际调用工具
    """

    # 承诺性语句的正则模式
    COMMITMENT_PATTERNS = [
        r'现在(创建|生成|编写|制作|构建)',
        r'接下来(我将|我会|要)',
        r'让我(创建|生成|编写|制作|构建)',
        r'开始(创建|生成|编写|制作|构建)',
        r'马上(创建|生成|编写|制作|构建)',
    ]

    def __init__(self):
        self.patterns = [re.compile(p) for p in self.COMMITMENT_PATTERNS]

    def check_violation(self, message: AIMessage) -> Optional[str]:
        """
        检查消息是否违反承诺

        Args:
            message: AI 消息

        Returns:
            如果违规，返回警告信息；否则返回 None
        """
        content = message.content or ""
        tool_calls = getattr(message, "tool_calls", []) or []

        # 检查是否有承诺性语句
        has_commitment = any(pattern.search(content) for pattern in self.patterns)

        # 如果有承诺但没有工具调用，则违规
        if has_commitment and not tool_calls:
            return (
                f"⚠️ 违反 '先做后说' 原则！\n"
                f"你说了要做某事，但没有调用任何工具：\n"
                f"消息内容: {content[:200]}\n"
                f"工具调用: {len(tool_calls)} 个\n\n"
                f"请立即调用对应的工具，不要只说不做！"
            )

        return None

    def inject_warning_if_needed(self, message: AIMessage) -> Optional[str]:
        """
        如果检测到违规，返回需要注入的警告消息

        Args:
            message: AI 消息

        Returns:
            警告消息内容，如果没有违规则返回 None
        """
        violation = self.check_violation(message)
        if violation:
            return (
                f"<system-warning>\n"
                f"{violation}\n"
                f"参考规则: backend/memory/TOOLS.md 第88-91行\n"
                f"</system-warning>"
            )
        return None
