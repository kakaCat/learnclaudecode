"""Browser Use 工具 - AI 控制浏览器"""
from backend.app.tools.base import tool

__tool_config__ = {
    "tags": ["main", "team"],
    "category": "integration",
    "enabled": False
}

@tool()
def browser_navigate(url: str) -> str:
    """
    导航到指定网页

    Args:
        url: 目标网址

    Returns:
        页面标题和内容摘要
    """
    try:
        from browser_use import Browser

        browser = Browser()
        result = browser.navigate(url)
        return f"已打开: {result.title}\n内容: {result.text[:200]}..."
    except ImportError:
        return "错误: 请先安装 browser-use (pip install browser-use playwright)"
    except Exception as e:
        return f"浏览器错误: {str(e)}"


@tool()
def browser_click(selector: str) -> str:
    """
    点击页面元素

    Args:
        selector: CSS 选择器

    Returns:
        操作结果
    """
    try:
        from browser_use import Browser

        browser = Browser()
        browser.click(selector)
        return f"已点击: {selector}"
    except Exception as e:
        return f"点击失败: {str(e)}"


@tool()
def browser_input(selector: str, text: str) -> str:
    """
    在输入框中输入文本

    Args:
        selector: CSS 选择器
        text: 输入内容

    Returns:
        操作结果
    """
    try:
        from browser_use import Browser

        browser = Browser()
        browser.fill(selector, text)
        return f"已输入到 {selector}: {text}"
    except Exception as e:
        return f"输入失败: {str(e)}"


@tool()
def browser_extract(selector: str) -> str:
    """
    提取页面元素的文本内容

    Args:
        selector: CSS 选择器

    Returns:
        元素文本内容
    """
    try:
        from browser_use import Browser

        browser = Browser()
        text = browser.get_text(selector)
        return f"提取内容: {text}"
    except Exception as e:
        return f"提取失败: {str(e)}"


@tool()
def browser_screenshot(filename: str = "screenshot.png") -> str:
    """
    截取当前页面截图

    Args:
        filename: 保存文件名

    Returns:
        截图保存路径
    """
    try:
        from browser_use import Browser

        browser = Browser()
        path = browser.screenshot(filename)
        return f"截图已保存: {path}"
    except Exception as e:
        return f"截图失败: {str(e)}"


@tool()
def browser_get_page_content() -> str:
    """
    获取当前页面的完整文本内容

    Returns:
        页面文本内容
    """
    try:
        from browser_use import Browser

        browser = Browser()
        content = browser.get_page_text()
        return content[:1000] + "..." if len(content) > 1000 else content
    except Exception as e:
        return f"获取内容失败: {str(e)}"

