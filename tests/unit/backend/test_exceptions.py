"""
异常处理模块测试
"""

import pytest
from backend.app.exceptions import *


class TestAgentError:
    """测试基础异常类"""
    
    def test_basic_error(self):
        """测试基本错误"""
        error = AgentError("测试错误")
        
        assert error.message == "测试错误"
        assert error.code == "AGENT_ERROR"
        assert error.details == {}
        assert error.inner_exception is None
        assert "[AGENT_ERROR] 测试错误" in str(error)
    
    def test_error_with_details(self):
        """测试带详情的错误"""
        error = AgentError(
            message="测试错误",
            code="TEST_ERROR",
            details={"key": "value", "count": 42}
        )
        
        assert error.code == "TEST_ERROR"
        assert error.details["key"] == "value"
        assert error.details["count"] == 42
        assert "key=value" in str(error)
        assert "count=42" in str(error)
    
    def test_error_with_inner_exception(self):
        """测试带内部异常的错误"""
        inner = ValueError("内部错误")
        error = AgentError(
            message="外部错误",
            inner_exception=inner
        )
        
        assert error.inner_exception is inner
        assert str(inner) in str(error.inner_exception)
    
    def test_to_dict(self):
        """测试转换为字典"""
        error = AgentError("测试错误", code="TEST_CODE")
        
        error_dict = error.to_dict()
        
        assert error_dict["error"] is True
        assert error_dict["code"] == "TEST_CODE"
        assert error_dict["message"] == "测试错误"
        assert "stack_trace" in error_dict
    
    def test_to_json(self):
        """测试转换为 JSON"""
        error = AgentError("测试错误")
        
        json_str = error.to_json()
        
        assert isinstance(json_str, str)
        assert "AGENT_ERROR" in json_str
        assert "测试错误" in json_str
    
    def test_from_exception(self):
        """测试从普通异常创建"""
        original = ValueError("原始错误")
        agent_error = AgentError.from_exception(original, code="CONVERTED")
        
        assert agent_error.code == "CONVERTED"
        assert "原始错误" in agent_error.message
        assert agent_error.inner_exception is original
        assert agent_error.details["original_type"] == "ValueError"


class TestToolErrors:
    """测试工具相关异常"""
    
    def test_tool_error(self):
        """测试工具错误基类"""
        error = ToolError("test_tool", "工具执行失败")
        
        assert error.code == "TOOL_ERROR"
        assert "工具 'test_tool' 错误" in error.message
        assert error.details["tool"] == "test_tool"
    
    def test_tool_execution_error(self):
        """测试工具执行错误"""
        original = RuntimeError("执行失败")
        error = ToolExecutionError("test_tool", original)
        
        assert "执行失败" in error.message
        assert error.details["error_type"] == "RuntimeError"
        assert error.details["error_message"] == "执行失败"
    
    def test_tool_not_found_error(self):
        """测试工具未找到错误"""
        error = ToolNotFoundError("unknown_tool")
        
        assert "工具未找到或未注册" in error.message
        assert error.details["tool"] == "unknown_tool"
    
    def test_tool_validation_error(self):
        """测试工具验证错误"""
        error = ToolValidationError(
            tool_name="test_tool",
            param_name="count",
            param_value=-1,
            reason="必须为正数"
        )
        
        assert "参数验证失败" in error.message
        assert error.details["param_name"] == "count"
        assert error.details["param_value"] == "-1"
        assert error.details["reason"] == "必须为正数"
    
    def test_tool_timeout_error(self):
        """测试工具超时错误"""
        error = ToolTimeoutError("slow_tool", timeout_seconds=30)
        
        assert "执行超时" in error.message
        assert "(30秒)" in error.message
        assert error.details["timeout_seconds"] == 30


class TestSessionErrors:
    """测试 Session 相关异常"""
    
    def test_session_error(self):
        """测试 Session 错误基类"""
        error = SessionError("session_123", "Session 操作失败")
        
        assert error.code == "SESSION_ERROR"
        assert "Session 'session_123' 错误" in error.message
        assert error.details["session_key"] == "session_123"
    
    def test_session_not_found_error(self):
        """测试 Session 未找到错误"""
        error = SessionNotFoundError("missing_session")
        
        assert "Session 不存在或已过期" in error.message
        assert error.details["session_key"] == "missing_session"
    
    def test_session_expired_error(self):
        """测试 Session 过期错误"""
        error = SessionExpiredError("expired_session", "2024-01-01T00:00:00")
        
        assert "Session 已过期" in error.message
        assert "2024-01-01T00:00:00" in error.message
        assert error.details["expired_at"] == "2024-01-01T00:00:00"
    
    def test_session_validation_error(self):
        """测试 Session 验证错误"""
        error = SessionValidationError("invalid_session", "格式不正确")
        
        assert "Session 验证失败" in error.message
        assert "格式不正确" in error.message
        assert error.details["reason"] == "格式不正确"


class TestMemoryErrors:
    """测试记忆相关异常"""
    
    def test_memory_error(self):
        """测试记忆错误基类"""
        error = MemoryError("记忆操作失败")
        
        assert error.code == "MEMORY_ERROR"
        assert "记忆系统错误" in error.message
    
    def test_memory_write_error(self):
        """测试记忆写入错误"""
        original = IOError("磁盘空间不足")
        error = MemoryWriteError("user_preferences", "用户偏好设置...", original)
        
        assert "写入记忆失败" in error.message
        assert error.details["category"] == "user_preferences"
        assert "用户偏好设置" in error.details["content_preview"]
        assert error.details["error_type"] == "OSError"
    
    def test_memory_search_error(self):
        """测试记忆搜索错误"""
        original = ValueError("查询语法错误")
        error = MemorySearchError("最近的项目", original)
        
        assert "搜索记忆失败" in error.message
        assert "'最近的项目'" in error.message
        assert error.details["query"] == "最近的项目"
        assert error.details["error_type"] == "ValueError"


class TestTaskErrors:
    """测试任务相关异常"""
    
    def test_task_error(self):
        """测试任务错误基类"""
        error = TaskError(123, "任务执行失败")
        
        assert error.code == "TASK_ERROR"
        assert "任务 #123 错误" in error.message
        assert error.details["task_id"] == 123
    
    def test_task_not_found_error(self):
        """测试任务未找到错误"""
        error = TaskNotFoundError(999)
        
        assert "任务不存在" in error.message
        assert error.details["task_id"] == 999
    
    def test_task_validation_error(self):
        """测试任务验证错误"""
        error = TaskValidationError(123, "缺少必要参数")
        
        assert "任务验证失败" in error.message
        assert "缺少必要参数" in error.message
        assert error.details["reason"] == "缺少必要参数"
    
    def test_task_dependency_error(self):
        """测试任务依赖错误"""
        error = TaskDependencyError(123, 456, "未完成")
        
        assert "任务依赖错误" in error.message
        assert "依赖任务 #456 未完成" in error.message
        assert error.details["dependency_id"] == 456
        assert error.details["reason"] == "未完成"


class TestLLMErrors:
    """测试 LLM 相关异常"""
    
    def test_llm_error(self):
        """测试 LLM 错误基类"""
        error = LLMError("gpt-4", "模型调用失败")
        
        assert error.code == "LLM_ERROR"
        assert "LLM 'gpt-4' 错误" in error.message
        assert error.details["model"] == "gpt-4"
    
    def test_llm_connection_error(self):
        """测试 LLM 连接错误"""
        original = ConnectionError("连接超时")
        error = LLMConnectionError("claude-3", original)
        
        assert "连接失败" in error.message
        assert error.details["error_type"] == "ConnectionError"
    
    def test_llm_timeout_error(self):
        """测试 LLM 超时错误"""
        error = LLMTimeoutError("deepseek-chat", timeout_seconds=60)
        
        assert "响应超时" in error.message
        assert "(60秒)" in error.message
        assert error.details["timeout_seconds"] == 60
    
    def test_llm_rate_limit_error(self):
        """测试 LLM 速率限制错误"""
        error = LLMRateLimitError("gpt-4", retry_after=30)
        
        assert "达到速率限制" in error.message
        assert "请在 30 秒后重试" in error.message
        assert error.details["retry_after_seconds"] == 30
    
    def test_llm_content_filter_error(self):
        """测试 LLM 内容过滤错误"""
        error = LLMContentFilterError("claude-3", "违反使用政策")
        
        assert "内容被过滤" in error.message
        assert "违反使用政策" in error.message
        assert error.details["reason"] == "违反使用政策"


class TestConfigErrors:
    """测试配置相关异常"""
    
    def test_config_error(self):
        """测试配置错误基类"""
        error = ConfigError("api_key", "配置无效")
        
        assert error.code == "CONFIG_ERROR"
        assert "配置 'api_key' 错误" in error.message
        assert error.details["config_key"] == "api_key"
    
    def test_config_not_found_error(self):
        """测试配置未找到错误"""
        error = ConfigNotFoundError("missing_config")
        
        assert "配置项不存在" in error.message
        assert error.details["config_key"] == "missing_config"
    
    def test_config_validation_error(self):
        """测试配置验证错误"""
        error = ConfigValidationError("timeout", -1, "必须为正数")
        
        assert "配置验证失败" in error.message
        assert "-1" in error.message
        assert "必须为正数" in error.message
        assert error.details["value"] == "-1"
        assert error.details["reason"] == "必须为正数"


class TestFileSystemErrors:
    """测试文件系统相关异常"""
    
    def test_file_system_error(self):
        """测试文件系统错误基类"""
        error = FileSystemError("/path/to/file", "文件操作失败")
        
        assert error.code == "FILE_SYSTEM_ERROR"
        assert "文件系统错误 '/path/to/file'" in error.message
        assert error.details["path"] == "/path/to/file"
    
    def test_file_not_found_error(self):
        """测试文件未找到错误"""
        error = FileNotFoundError("/missing/file.txt")
        
        assert "文件不存在" in error.message
        assert error.details["path"] == "/missing/file.txt"
    
    def test_file_permission_error(self):
        """测试文件权限错误"""
        error = FilePermissionError("/protected/file.txt", "write")
        
        assert "权限不足" in error.message
        assert "无法执行 write 操作" in error.message
        assert error.details["path"] == "/protected/file.txt"
    
    def test_file_read_error(self):
        """测试文件读取错误"""
        original = UnicodeDecodeError("utf-8", b"", 0, 1, "无效编码")
        error = FileReadError("/corrupted/file.txt", original)
        
        assert "读取失败" in error.message
        assert error.details["error_type"] == "UnicodeDecodeError"
    
    def test_file_write_error(self):
        """测试文件写入错误"""
        original = PermissionError("权限被拒绝")
        error = FileWriteError("/readonly/file.txt", original)
        
        assert "写入失败" in error.message
        assert error.details["error_type"] == "PermissionError"


class TestNetworkErrors:
    """测试网络相关异常"""
    
    def test_network_error(self):
        """测试网络错误基类"""
        error = NetworkError("https://api.example.com", "网络请求失败")
        
        assert error.code == "NETWORK_ERROR"
        assert "网络错误 'https://api.example.com'" in error.message
        assert error.details["url"] == "https://api.example.com"
    
    def test_network_connection_error(self):
        """测试网络连接错误"""
        original = ConnectionRefusedError("连接被拒绝")
        error = NetworkConnectionError("https://down.example.com", original)
        
        assert "连接失败" in error.message
        assert error.details["error_type"] == "ConnectionRefusedError"
    
    def test_network_timeout_error(self):
        """测试网络超时错误"""
        error = NetworkTimeoutError("https://slow.example.com", timeout_seconds=10)
        
        assert "请求超时" in error.message
        assert "(10秒)" in error.message
        assert error.details["timeout_seconds"] == 10


class TestUtilityFunctions:
    """测试工具函数"""
    
    def test_handle_agent_errors_sync(self):
        """测试同步错误处理装饰器"""
        
        @handle_agent_errors
        def successful_function():
            return "成功"
        
        @handle_agent_errors
        def failing_function():
            raise ValueError("测试错误")
        
        # 成功情况
        result = successful_function()
        assert result == "成功"
        
        # 失败情况（应该包装为 AgentError）
        with pytest.raises(AgentError) as exc_info:
            failing_function()
        
        assert exc_info.value.code == "UNKNOWN_ERROR"
        assert "测试错误" in exc_info.value.message
    
    def test_handle_agent_errors_async(self):
        """测试异步错误处理装饰器"""
        import asyncio
        
        @handle_agent_errors
        async def async_successful():
            return "异步成功"
        
        @handle_agent_errors
        async def async_failing():
            raise RuntimeError("异步错误")
        
        # 成功情况
        result = asyncio.run(async_successful())
        assert result == "异步成功"
        
        # 失败情况
        with pytest.raises(AgentError) as exc_info:
            asyncio.run(async_failing())
        
        assert exc_info.value.code == "UNKNOWN_ERROR"
        assert "异步错误" in exc_info.value.message
    
    def test_safe_execute(self):
        """测试安全执行函数"""
        
        def successful_func():
            return 42
        
        def failing_func():
            raise ValueError("失败")
        
        # 成功情况
        result = safe_execute(successful_func, default_return=0)
        assert result == 42
        
        # 失败情况（返回默认值）
        result = safe_execute(failing_func, default_return=0, raise_agent_error=False)
        assert result == 0
        
        # 失败情况（抛出异常）
        with pytest.raises(AgentError):
            safe_execute(failing_func, raise_agent_error=True)
    
    def test_is_agent_error(self):
        """测试是否为 AgentError"""
        agent_error = AgentError("测试")
        value_error = ValueError("测试")
        
        assert is_agent_error(agent_error) is True
        assert is_agent_error(value_error) is False
    
    def test_get_error_code(self):
        """测试获取错误代码"""
        agent_error = AgentError("测试", code="TEST_CODE")
        value_error = ValueError("测试")
        
        assert get_error_code(agent_error) == "TEST_CODE"
        assert get_error_code(value_error) == "UNKNOWN_ERROR"
    
    def test_format_error_for_user(self):
        """测试格式化用户错误信息"""
        agent_error = AgentError("配置错误", code="CONFIG_ERROR")
        value_error = ValueError("内部错误")
        
        user_msg1 = format_error_for_user(agent_error)
        user_msg2 = format_error_for_user(value_error)
        
        assert "错误: 配置错误" in user_msg1
        assert "系统发生未知错误" in user_msg2
    
    def test_format_error_for_logging(self):
        """测试格式化日志错误信息"""
        agent_error = AgentError("测试错误", code="TEST_CODE")
        value_error = ValueError("普通错误")
        
        log1 = format_error_for_logging(agent_error)
        log2 = format_error_for_logging(value_error)
        
        assert log1["code"] == "TEST_CODE"
        assert log2["code"] == "UNKNOWN_ERROR"
        assert "stack_trace" in log2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])