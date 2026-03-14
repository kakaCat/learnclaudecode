"""
集成工具模块

包含外部服务和协议集成工具：
- cdp_tool: Chrome DevTools Protocol 集成
- browser_tool: Browser Use AI 浏览器控制
"""

from .cdp_tool import cdp_browser
from .browser_tool import (
    browser_navigate,
    browser_click,
    browser_input,
    browser_extract,
    browser_screenshot,
    browser_get_page_content,
)

__all__ = [
    "cdp_browser",
    "browser_navigate",
    "browser_click",
    "browser_input",
    "browser_extract",
    "browser_screenshot",
    "browser_get_page_content",
]
