"""
MCP Tool - 使用 LangChain 官方 MCP Adapters

提供 MCP 工具的动态加载和调用功能
"""

import json
import logging
from pathlib import Path
from typing import List, Any

from langchain_core.tools import BaseTool, StructuredTool
from langchain_mcp_adapters.client import MultiServerMCPClient

logger = logging.getLogger(__name__)


def _normalize_mcp_result(result: Any) -> str:
    """
    标准化 MCP 工具返回结果为字符串

    MCP 工具可能返回列表格式: [{'type': 'text', 'text': '...'}]
    需要转换为纯字符串供 LLM 使用
    """
    if isinstance(result, str):
        return result

    if isinstance(result, list):
        # 提取所有 text 字段
        texts = []
        for item in result:
            if isinstance(item, dict) and 'text' in item:
                texts.append(item['text'])
            else:
                texts.append(str(item))
        return '\n'.join(texts)

    return str(result)


def _wrap_mcp_tool(tool: BaseTool) -> BaseTool:
    """
    包装 MCP 工具，确保返回字符串格式
    """
    from functools import wraps

    # 保存原始方法
    original_run = tool._run
    original_arun = tool._arun

    @wraps(original_run)
    def wrapped_run(*args, **kwargs):
        result = original_run(*args, **kwargs)
        # 如果是元组 (content, artifact)，只转换 content
        if isinstance(result, tuple) and len(result) == 2:
            content, artifact = result
            return (_normalize_mcp_result(content), artifact)
        return _normalize_mcp_result(result)

    @wraps(original_arun)
    async def wrapped_arun(*args, **kwargs):
        result = await original_arun(*args, **kwargs)
        # 如果是元组 (content, artifact)，只转换 content
        if isinstance(result, tuple) and len(result) == 2:
            content, artifact = result
            return (_normalize_mcp_result(content), artifact)
        return _normalize_mcp_result(result)

    # 替换方法
    tool._run = wrapped_run
    tool._arun = wrapped_arun

    return tool


class MCPToolLoader:
    """MCP 工具加载器 - 使用 LangChain 官方适配器"""

    def __init__(self, config_path: str = None):
        """
        初始化加载器

        Args:
            config_path: 配置文件路径，默认为 backend/mcp_config.json
        """
        if config_path is None:
            backend_dir = Path(__file__).parent.parent.parent
            config_path = backend_dir / "mcp_config.json"

        self.config_path = Path(config_path)
        self._client = None

    def _load_config(self) -> dict:
        """加载 MCP 配置文件"""
        if not self.config_path.exists():
            logger.warning(f"MCP config file not found: {self.config_path}")
            return {}

        with open(self.config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        return config.get("mcpServers", {})

    async def get_tools(self) -> List[BaseTool]:
        """
        获取所有 MCP 工具

        Returns:
            LangChain 工具列表
        """
        try:
            # 加载配置
            servers_config = self._load_config()

            if not servers_config:
                logger.info("No MCP servers configured")
                return []

            # 创建 MultiServerMCPClient
            if self._client is None:
                logger.info(f"Initializing MCP client with {len(servers_config)} server(s)")
                self._client = MultiServerMCPClient(servers_config)

            # 获取工具（自动转换为 LangChain 工具）- 异步调用
            tools = await self._client.get_tools()

            # 包装所有 MCP 工具，确保返回字符串格式
            wrapped_tools = [_wrap_mcp_tool(tool) for tool in tools]

            logger.info(f"Loaded {len(wrapped_tools)} MCP tools")

            return wrapped_tools

        except Exception as e:
            logger.error(f"Failed to load MCP tools: {e}")
            return []


# 全局加载器实例
_loader = None


async def get_mcp_tools() -> List[BaseTool]:
    """
    获取所有 MCP 工具（单例模式）

    Returns:
        LangChain 工具列表
    """
    global _loader
    if _loader is None:
        _loader = MCPToolLoader()

    return await _loader.get_tools()
