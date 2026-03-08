"""
增强版配置系统 (config_v2.py)

基于 Pydantic 的配置管理系统，提供：
1. 类型安全的配置验证
2. 多模型支持（DeepSeek, OpenAI, Anthropic）
3. 环境变量自动加载和验证
4. 配置热重载支持
5. 向后兼容现有 config.py

这是一个可选模块，不影响现有系统。
要启用：from backend.app.config_v2 import config
"""

import os
from typing import Optional, Literal, Dict, Any
from enum import Enum
from datetime import timedelta

try:
    # Pydantic 2.x 需要 pydantic-settings
    from pydantic_settings import BaseSettings
    from pydantic import Field, validator, root_validator
except ImportError:
    # 回退到 Pydantic 1.x
    from pydantic import BaseSettings, Field, validator, root_validator
from pydantic.fields import FieldInfo
from dotenv import load_dotenv

# 加载环境变量
load_dotenv(override=True)


class ModelProvider(str, Enum):
    """模型提供商枚举"""
    DEEPSEEK = "deepseek"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    AZURE_OPENAI = "azure_openai"
    LOCAL = "local"


class LLMConfig(BaseSettings):
    """LLM 配置基类"""
    
    api_key: Optional[str] = Field(None, description="API 密钥")
    base_url: Optional[str] = Field(None, description="API 基础 URL")
    model: str = Field(..., description="模型名称")
    temperature: float = Field(0.7, ge=0.0, le=2.0, description="温度参数")
    max_tokens: Optional[int] = Field(None, ge=1, le=128000, description="最大令牌数")
    timeout: int = Field(30, ge=1, description="请求超时时间（秒）")
    
    class Config:
        env_prefix = ""  # 子类可以设置自己的前缀
        extra = "ignore"


class DeepSeekConfig(LLMConfig):
    """DeepSeek 配置"""
    
    model: str = Field("deepseek-chat", description="DeepSeek 模型")
    base_url: str = Field("https://api.deepseek.com/v1", description="DeepSeek API URL")
    
    class Config:
        env_prefix = "DEEPSEEK_"


class OpenAIConfig(LLMConfig):
    """OpenAI 配置"""
    
    model: str = Field("gpt-4-turbo-preview", description="OpenAI 模型")
    base_url: str = Field("https://api.openai.com/v1", description="OpenAI API URL")
    
    class Config:
        env_prefix = "OPENAI_"


class AnthropicConfig(LLMConfig):
    """Anthropic 配置"""
    
    model: str = Field("claude-3-opus-20240229", description="Anthropic 模型")
    base_url: str = Field("https://api.anthropic.com/v1", description="Anthropic API URL")
    
    class Config:
        env_prefix = "ANTHROPIC_"


class AgentConfig(BaseSettings):
    """Agent 主配置"""
    
    # 模型配置
    default_provider: ModelProvider = Field(
        ModelProvider.DEEPSEEK,
        description="默认模型提供商"
    )
    
    deepseek: DeepSeekConfig = Field(
        default_factory=DeepSeekConfig,
        description="DeepSeek 配置"
    )
    
    openai: OpenAIConfig = Field(
        default_factory=OpenAIConfig,
        description="OpenAI 配置"
    )
    
    anthropic: AnthropicConfig = Field(
        default_factory=AnthropicConfig,
        description="Anthropic 配置"
    )
    
    # 系统配置
    session_timeout_minutes: int = Field(
        30,
        ge=1,
        le=1440,
        description="会话超时时间（分钟）"
    )
    
    max_context_length: int = Field(
        128000,
        ge=1000,
        le=1000000,
        description="最大上下文长度"
    )
    
    enable_tracing: bool = Field(
        True,
        description="启用调用追踪"
    )
    
    enable_monitoring: bool = Field(
        False,
        description="启用性能监控"
    )
    
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        "INFO",
        description="日志级别"
    )
    
    # 工具配置
    tool_timeout_seconds: int = Field(
        30,
        ge=1,
        description="工具执行超时时间（秒）"
    )
    
    max_tool_retries: int = Field(
        3,
        ge=0,
        description="工具最大重试次数"
    )
    
    # 记忆配置
    memory_search_top_k: int = Field(
        5,
        ge=1,
        le=50,
        description="记忆搜索返回数量"
    )
    
    memory_retention_days: int = Field(
        30,
        ge=1,
        description="记忆保留天数"
    )
    
    # 安全配置
    enable_sandbox: bool = Field(
        True,
        description="启用沙箱模式（限制文件系统访问）"
    )
    
    allowed_file_paths: list[str] = Field(
        default_factory=lambda: ["./", "./data/", "./logs/"],
        description="允许访问的文件路径"
    )
    
    # 性能配置
    enable_caching: bool = Field(
        True,
        description="启用响应缓存"
    )
    
    cache_ttl_seconds: int = Field(
        300,
        ge=0,
        description="缓存存活时间（秒）"
    )
    
    max_concurrent_tasks: int = Field(
        5,
        ge=1,
        le=20,
        description="最大并发任务数"
    )
    
    @validator("allowed_file_paths")
    def validate_file_paths(cls, v):
        """验证文件路径"""
        validated_paths = []
        for path in v:
            # 确保路径是安全的
            if not os.path.isabs(path) or path.startswith(("./", "../")):
                validated_paths.append(path)
            else:
                raise ValueError(f"不允许的绝对路径: {path}")
        return validated_paths
    
    def validate_api_keys(self):
        """验证 API 密钥配置（手动验证）"""
        default_provider = self.default_provider
        
        # 检查默认提供商的 API 密钥
        if default_provider == ModelProvider.DEEPSEEK:
            if not self.deepseek.api_key:
                raise ValueError("DeepSeek 配置需要 API 密钥")
        elif default_provider == ModelProvider.OPENAI:
            if not self.openai.api_key:
                raise ValueError("OpenAI 配置需要 API 密钥")
        elif default_provider == ModelProvider.ANTHROPIC:
            if not self.anthropic.api_key:
                raise ValueError("Anthropic 配置需要 API 密钥")
    
    def get_llm_config(self, provider: Optional[ModelProvider] = None) -> LLMConfig:
        """获取指定提供商的 LLM 配置"""
        if provider is None:
            provider = self.default_provider
        
        if provider == ModelProvider.DEEPSEEK:
            return self.deepseek
        elif provider == ModelProvider.OPENAI:
            return self.openai
        elif provider == ModelProvider.ANTHROPIC:
            return self.anthropic
        else:
            raise ValueError(f"不支持的提供商: {provider}")
    
    def to_simple_dict(self) -> Dict[str, Any]:
        """转换为简单字典（兼容旧格式）"""
        llm_config = self.get_llm_config()
        
        return {
            "api_key": llm_config.api_key,
            "base_url": llm_config.base_url,
            "model": llm_config.model,
            "provider": self.default_provider.value,
            "session_timeout_minutes": self.session_timeout_minutes,
            "max_context_length": self.max_context_length,
        }
    
    def update_from_env(self):
        """从环境变量更新配置"""
        # Pydantic 会自动处理环境变量
        # 这里主要是为了提供显式的更新方法
        return self.__class__()
    
    class Config:
        env_prefix = "AGENT_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"


# 全局配置实例
config = AgentConfig()

# 向后兼容：提供与旧 config.py 相同的接口
def get_backward_compatible_config():
    """获取向后兼容的配置（模拟旧 config.py）"""
    llm_config = config.get_llm_config()
    
    class BackwardCompatibleConfig:
        DEEPSEEK_API_KEY = llm_config.api_key if config.default_provider == ModelProvider.DEEPSEEK else None
        DEEPSEEK_BASE_URL = llm_config.base_url if config.default_provider == ModelProvider.DEEPSEEK else "https://api.deepseek.com/v1"
        DEEPSEEK_MODEL = llm_config.model if config.default_provider == ModelProvider.DEEPSEEK else "deepseek-chat"
        
        # 添加新配置的访问方式
        @property
        def SESSION_TIMEOUT_MINUTES(self):
            return config.session_timeout_minutes
        
        @property
        def MAX_CONTEXT_LENGTH(self):
            return config.max_context_length
        
        @property
        def ENABLE_TRACING(self):
            return config.enable_tracing
    
    return BackwardCompatibleConfig()


# 导出兼容接口
backward_config = get_backward_compatible_config()
DEEPSEEK_API_KEY = backward_config.DEEPSEEK_API_KEY
DEEPSEEK_BASE_URL = backward_config.DEEPSEEK_BASE_URL
DEEPSEEK_MODEL = backward_config.DEEPSEEK_MODEL

# 辅助函数
def is_configured() -> bool:
    """检查配置是否完整"""
    try:
        llm_config = config.get_llm_config()
        return bool(llm_config.api_key)
    except (ValueError, AttributeError):
        return False


def validate_config() -> tuple[bool, list[str]]:
    """验证配置并返回问题和警告"""
    issues = []
    warnings = []
    
    # 检查 API 密钥
    llm_config = config.get_llm_config()
    if not llm_config.api_key:
        issues.append(f"{config.default_provider.value} API 密钥未设置")
    
    # 检查超时设置
    if config.tool_timeout_seconds < 5:
        warnings.append("工具超时时间较短，可能导致超时错误")
    
    if config.session_timeout_minutes < 5:
        warnings.append("会话超时时间较短，可能导致频繁超时")
    
    # 检查文件路径
    for path in config.allowed_file_paths:
        if not os.path.exists(path) and not path.startswith("./"):
            warnings.append(f"配置的文件路径不存在: {path}")
    
    return len(issues) == 0, issues + warnings


def print_config_summary():
    """打印配置摘要"""
    llm_config = config.get_llm_config()
    
    print("🔧 Agent 配置摘要")
    print("=" * 50)
    print(f"默认提供商: {config.default_provider.value}")
    print(f"模型: {llm_config.model}")
    print(f"API URL: {llm_config.base_url}")
    print(f"API 密钥: {'已设置' if llm_config.api_key else '未设置'}")
    print(f"会话超时: {config.session_timeout_minutes} 分钟")
    print(f"最大上下文: {config.max_context_length} 令牌")
    print(f"性能监控: {'启用' if config.enable_monitoring else '禁用'}")
    print(f"工具超时: {config.tool_timeout_seconds} 秒")
    print(f"最大并发: {config.max_concurrent_tasks}")
    print("=" * 50)
    
    # 验证配置
    valid, messages = validate_config()
    if valid:
        print("✅ 配置验证通过")
    else:
        print("⚠️  配置验证警告:")
        for msg in messages:
            print(f"  - {msg}")


# 测试代码（仅当直接运行时执行）
if __name__ == "__main__":
    print_config_summary()
    
    # 演示向后兼容
    print("\n🔙 向后兼容测试:")
    print(f"DEEPSEEK_API_KEY: {DEEPSEEK_API_KEY}")
    print(f"DEEPSEEK_BASE_URL: {DEEPSEEK_BASE_URL}")
    print(f"DEEPSEEK_MODEL: {DEEPSEEK_MODEL}")
    
    # 演示多模型切换
    print("\n🔄 多模型支持演示:")
    for provider in [ModelProvider.DEEPSEEK, ModelProvider.OPENAI, ModelProvider.ANTHROPIC]:
        try:
            llm_cfg = config.get_llm_config(provider)
            print(f"{provider.value}: {llm_cfg.model} ({'已配置' if llm_cfg.api_key else '未配置'})")
        except ValueError:
            print(f"{provider.value}: 不支持")