"""
工具 Fallback 系统

提供通用的工具失败后的替代方案机制
"""
from typing import Dict, Callable, Optional, List
import os


class ToolFallbackRule:
    """单个工具的 fallback 规则"""

    def __init__(
        self,
        fallback_tool: str,
        transform_args: Optional[Callable] = None,
        condition: Optional[Callable] = None
    ):
        """
        Args:
            fallback_tool: 替代工具名称
            transform_args: 参数转换函数 (original_args, error) -> new_args
            condition: 条件函数 (error) -> bool，判断是否应该使用此 fallback
        """
        self.fallback_tool = fallback_tool
        self.transform_args = transform_args or (lambda args, err: args)
        self.condition = condition or (lambda err: True)


class ToolFallbackRegistry:
    """工具 Fallback 注册表"""

    def __init__(self):
        self.rules: Dict[str, List[ToolFallbackRule]] = {}
        self._register_default_rules()

    def register(self, tool_name: str, rule: ToolFallbackRule):
        """注册 fallback 规则"""
        if tool_name not in self.rules:
            self.rules[tool_name] = []
        self.rules[tool_name].append(rule)

    def get_fallback(self, tool_name: str, error: Exception) -> Optional[tuple]:
        """
        获取 fallback 工具和转换后的参数

        Returns:
            (fallback_tool_name, transform_function) 或 None
        """
        if tool_name not in self.rules:
            return None

        for rule in self.rules[tool_name]:
            if rule.condition(error):
                return (rule.fallback_tool, rule.transform_args)

        return None

    def _register_default_rules(self):
        """注册默认的 fallback 规则"""

        # workspace_write → write_file
        def transform_workspace_to_file(args, error):
            """将 workspace 路径转换为绝对路径"""
            session_key = os.environ.get("CURRENT_SESSION_KEY", "")
            workspace_path = f".sessions/{session_key}/workspace/"
            return {
                "path": os.path.join(workspace_path, args.get("path", "")),
                "content": args.get("content", "")
            }

        self.register(
            "workspace_write",
            ToolFallbackRule(
                fallback_tool="write_file",
                transform_args=transform_workspace_to_file
            )
        )

        # workspace_read → read_file
        def transform_workspace_read(args, error):
            session_key = os.environ.get("CURRENT_SESSION_KEY", "")
            workspace_path = f".sessions/{session_key}/workspace/"
            return {
                "path": os.path.join(workspace_path, args.get("path", ""))
            }

        self.register(
            "workspace_read",
            ToolFallbackRule(
                fallback_tool="read_file",
                transform_args=transform_workspace_read
            )
        )


# 全局单例
_registry = ToolFallbackRegistry()


def get_fallback_registry() -> ToolFallbackRegistry:
    """获取全局 fallback 注册表"""
    return _registry
