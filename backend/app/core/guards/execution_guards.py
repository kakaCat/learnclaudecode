"""
Execution Guards - 执行层守卫集合

职责：
1. ActionCommitmentGuard - 检测"说了要做但没做"的违规行为
2. ReflectionGatekeeper - 强制代码反思门禁
3. GuardManager - 统一管理所有守卫

核心改进：
- 守卫可以注入警告消息回对话流
- 守卫可以阻止 Agent 继续执行
- 统一的守卫接口和生命周期管理
"""
import re
from typing import List, Optional
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage


class BaseGuard:
    """守卫基类 - 定义统一接口"""

    def should_inject(self) -> bool:
        """是否需要注入警告消息"""
        return False

    def get_warning_message(self) -> Optional[str]:
        """获取警告消息（注入到对话流）"""
        return None

    def on_tool_call(self, tool_name: str, **kwargs):
        """工具调用后更新状态"""
        pass

    def reset(self):
        """重置状态"""
        pass


class EmptyResponseGuard(BaseGuard):
    """
    检测 LLM 返回空响应或无意义响应的情况

    违规模式：
    - 没有工具调用，且输出内容过短（< 50 字符）
    - 没有工具调用，且输出只是重复用户问题
    - 没有工具调用，且输出是"好的"、"明白"等无实质内容
    """

    MEANINGLESS_PATTERNS = [
        r'^好的[。！]*$',
        r'^明白[了。！]*$',
        r'^收到[。！]*$',
        r'^了解[。！]*$',
        r'^OK[。！]*$',
        r'^.\s*$',  # 只有标点或空白
    ]

    def __init__(self):
        self.patterns = [re.compile(p, re.IGNORECASE) for p in self.MEANINGLESS_PATTERNS]
        self.violation_count = 0
        self.max_violations = 2  # 最多警告 2 次

    def check_violation(self, message: AIMessage, has_tool_calls: bool) -> Optional[str]:
        """
        检查是否是空响应

        Args:
            message: AI 消息
            has_tool_calls: 是否有工具调用

        Returns:
            如果违规，返回警告信息；否则返回 None
        """
        # 如果有工具调用，不检查
        if has_tool_calls:
            return None

        # 如果已经警告过太多次，停止检查
        if self.violation_count >= self.max_violations:
            return None

        content = message.content or ""
        content_stripped = content.strip()

        # 检查1：内容过短
        if len(content_stripped) < 50:
            # 检查是否是无意义响应
            for pattern in self.patterns:
                if pattern.match(content_stripped):
                    self.violation_count += 1
                    return (
                        "⚠️ 检测到空响应违规：你只回复了简短确认，但没有实际执行任何操作。\n"
                        "请立即调用工具完成任务，不要只是说'好的'或'明白'。"
                    )

        # 检查2：内容很短但不是无意义（可能是真的完成了）
        if len(content_stripped) < 20 and not any(
            keyword in content_stripped
            for keyword in ['完成', '已', '成功', '创建', '生成', '修改']
        ):
            self.violation_count += 1
            return (
                "⚠️ 检测到响应过短：你的回复只有几个字，但没有调用任何工具。\n"
                "如果任务已完成，请说明完成了什么；如果未完成，请调用工具继续执行。"
            )

        return None

    def reset(self):
        """重置状态"""
        self.violation_count = 0


class ActionCommitmentGuard(BaseGuard):
    """
    检测 Agent 是否违反 "先做后说" 原则

    违规模式：
    - "现在创建..." 但没有调用工具
    - "接下来我将..." 但没有调用工具
    - "让我..." 但没有调用工具

    修复方案：
    - 检测到违规时，注入警告消息回对话流
    - 强制 Agent 看到警告并调用工具
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
        self.last_violation: Optional[str] = None
        self.violation_count: int = 0  # 追踪违规次数
        self.max_violations: int = 3  # 最多警告 3 次后停止

    def check_violation(self, message: AIMessage) -> Optional[str]:
        """
        检查消息是否违反承诺

        Args:
            message: AI 消息

        Returns:
            如果违规，返回警告信息；否则返回 None
        """
        # 如果已经警告过太多次，停止检查
        if self.violation_count >= self.max_violations:
            return None

        content = message.content or ""
        tool_calls = getattr(message, "tool_calls", []) or []

        # 检查是否有承诺性语句
        has_commitment = any(pattern.search(content) for pattern in self.patterns)

        # 如果有承诺但没有工具调用，则违规
        if has_commitment and not tool_calls:
            self.violation_count += 1
            self.last_violation = content[:200]
            return (
                f"⚠️ 违反 '先做后说' 原则！\n"
                f"你说了要做某事，但没有调用任何工具：\n"
                f"消息内容: {content[:200]}\n"
                f"工具调用: {len(tool_calls)} 个\n\n"
                f"请立即调用对应的工具，不要只说不做！\n"
                f"(警告 {self.violation_count}/{self.max_violations})"
            )

        # 清除违规记录
        self.last_violation = None
        return None

    def should_inject(self) -> bool:
        """是否需要注入警告"""
        return self.last_violation is not None

    def get_warning_message(self) -> Optional[str]:
        """获取警告消息"""
        if self.last_violation:
            return (
                f"<system-warning>\n"
                f"⚠️ 违反 '先做后说' 原则！\n"
                f"你说了：{self.last_violation}\n"
                f"但没有调用任何工具。请立即调用对应的工具！\n"
                f"</system-warning>"
            )
        return None

    def reset(self):
        """重置守卫状态"""
        self.last_violation = None
        self.violation_count = 0


class ReflectionGatekeeper(BaseGuard):
    """
    代码反思门禁守卫 - 强制写文件后进行质量检查

    机制：
    - 追踪文件写入次数
    - 写入文件后必须调用 Reflect 子 agent
    - 支持重试机制和熔断
    """

    def __init__(self, max_retries: int = 2):
        self.file_writes_since_reflect = 0
        self.reflect_retry_count = 0
        self.max_retries = max_retries

    def on_tool_call(self, tool_name: str, subagent_type: str = "", tool_result: str = ""):
        """工具调用后更新状态"""
        # 文件写入计数
        if tool_name in ("write_file", "edit_file", "Write", "Edit"):
            self.file_writes_since_reflect += 1

        # 反思结果处理
        if tool_name == "Task" and subagent_type in ("Reflect", "Reflexion"):
            if "NEEDS_REVISION" in tool_result:
                self.reflect_retry_count += 1
            else:
                self.file_writes_since_reflect = 0
                self.reflect_retry_count = 0

        # 熔断机制：超过最大重试次数强制重置
        if self.reflect_retry_count >= self.max_retries:
            self.reflect_retry_count = 0
            self.file_writes_since_reflect = 0

    def should_inject(self) -> bool:
        """是否需要门禁（强制反思）"""
        return self.file_writes_since_reflect >= 1

    def get_warning_message(self) -> Optional[str]:
        """获取门禁消息"""
        if not self.should_inject():
            return None

        retry_hint = ""
        if self.reflect_retry_count >= 1:
            retry_hint = f"（已重试 {self.reflect_retry_count} 次，若仍 NEEDS_REVISION 请升级为 Reflexion）"

        return (
            f"<reflection-gate>\n"
            f"你刚写入了文件，必须先调用 Task(subagent_type='Reflect') 校验后才能继续。\n"
            f"{retry_hint}\n"
            f"</reflection-gate>"
        )

    def reset(self):
        """重置状态"""
        self.file_writes_since_reflect = 0
        self.reflect_retry_count = 0


class GuardManager:
    """
    守卫管理器 - 统一管理所有守卫

    职责：
    1. 协调所有守卫检查
    2. 注入守卫消息到对话流
    3. 更新守卫状态
    4. 支持守卫阻断执行

    改进：
    - 支持在 LLM 输出后立即检查并注入警告
    - 支持阻止 Agent 继续执行（通过注入警告消息）
    """

    def __init__(self):
        self.action_commitment = ActionCommitmentGuard()
        self.empty_response = EmptyResponseGuard()
        self.reflection_gate = ReflectionGatekeeper()

        self.all_guards = [
            self.action_commitment,
            self.empty_response,
            self.reflection_gate,
        ]

    def inject_messages(self, messages: List[BaseMessage]) -> List[BaseMessage]:
        """
        注入守卫消息（在发送给 LLM 之前）

        Args:
            messages: 原始消息列表

        Returns:
            注入守卫消息后的列表
        """
        result = messages.copy()

        # 检查所有守卫，注入需要的警告
        for guard in self.all_guards:
            if guard.should_inject():
                warning = guard.get_warning_message()
                if warning:
                    result.append(HumanMessage(content=warning))

        return result

    def check_and_inject_after_llm(
        self,
        ai_message: AIMessage,
        messages: List[BaseMessage]
    ) -> bool:
        """
        在 LLM 输出后立即检查并注入警告

        Args:
            ai_message: LLM 输出的消息
            messages: 当前消息列表（会被修改）

        Returns:
            True 如果注入了警告（需要继续循环），False 否则
        """
        # 检查是否有工具调用
        has_tool_calls = bool(getattr(ai_message, 'tool_calls', None))

        # 检查 EmptyResponseGuard（优先检查，因为更严重）
        empty_violation = self.empty_response.check_violation(ai_message, has_tool_calls)
        if empty_violation:
            warning_msg = HumanMessage(content=f"<system-warning>\n{empty_violation}\n</system-warning>")
            messages.append(warning_msg)
            print(f"⚠️  [EmptyResponseGuard] {empty_violation}")
            return True

        # 检查 ActionCommitmentGuard
        violation = self.action_commitment.check_violation(ai_message)
        if violation:
            # 注入警告消息
            warning_msg = HumanMessage(content=f"<system-warning>\n{violation}\n</system-warning>")
            messages.append(warning_msg)
            print(f"⚠️  [Guard] {violation}")
            return True  # 需要继续循环

        return False  # 没有违规，可以继续

    def on_tool_call(self, tool_name: str, subagent_type: str = "", result: str = ""):
        """
        工具调用后更新守卫状态

        Args:
            tool_name: 工具名称
            subagent_type: Subagent 类型（如果是 Task 工具）
            result: 工具结果
        """
        for guard in self.all_guards:
            guard.on_tool_call(
                tool_name=tool_name,
                subagent_type=subagent_type,
                tool_result=result
            )

    def reset(self):
        """重置所有守卫状态"""
        for guard in self.all_guards:
            guard.reset()
