"""
代码反思门禁守卫 - 强制写文件后进行质量检查
"""


class ReflectionGatekeeper:
    """追踪文件写入和反思状态，确保代码质量"""

    def __init__(self, max_retries: int = 2):
        self.file_writes_since_reflect = 0
        self.reflect_retry_count = 0
        self.max_retries = max_retries

    def on_tool_call(self, tool_name: str, subagent_type: str = "", tool_result: str = ""):
        """工具调用后更新状态"""
        # 文件写入计数
        if tool_name in ("write_file", "edit_file"):
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

    def should_gate(self) -> bool:
        """是否需要门禁（强制反思）"""
        return self.file_writes_since_reflect >= 1

    def get_gate_message(self) -> str:
        """获取门禁消息"""
        retry_hint = ""
        if self.reflect_retry_count >= 1:
            retry_hint = f"（已重试 {self.reflect_retry_count} 次，若仍 NEEDS_REVISION 请升级为 Reflexion）"
        return f"<reflection-gate>你刚写入了文件，必须先调用 Task(subagent_type='Reflect') 校验后才能继续。{retry_hint}</reflection-gate>"

    def reset(self):
        """重置状态（切换 session 时使用）"""
        self.file_writes_since_reflect = 0
        self.reflect_retry_count = 0
