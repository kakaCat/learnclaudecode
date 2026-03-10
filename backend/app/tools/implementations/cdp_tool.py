"""改进的 CDP 工具 - 添加健康检查和更好的错误处理"""
import logging
import json
from typing import Literal, Optional
from pathlib import Path
from datetime import datetime
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# Global browser instance
_browser = None
_browser_available = None  # 缓存可用性检查结果
_session_store = None  # Session store instance


def _check_cdp_available() -> tuple[bool, str]:
    """检查 CDP 服务是否可用"""
    global _browser_available

    # 使用缓存结果（避免重复检查）
    if _browser_available is not None:
        return _browser_available

    try:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1.0)
        result = sock.connect_ex(("127.0.0.1", 9222))
        sock.close()

        if result == 0:
            _browser_available = (True, "")
            return _browser_available
        else:
            msg = (
                "Chrome DevTools Protocol 服务未启动\n\n"
                "启动方法：\n"
                "1. macOS/Linux:\n"
                "   google-chrome --remote-debugging-port=9222 --headless\n"
                "   或\n"
                "   chromium --remote-debugging-port=9222 --headless\n\n"
                "2. Windows:\n"
                "   chrome.exe --remote-debugging-port=9222 --headless\n\n"
                "3. 使用 Docker:\n"
                "   docker run -d -p 9222:9222 zenika/alpine-chrome --remote-debugging-port=9222"
            )
            _browser_available = (False, msg)
            return _browser_available

    except Exception as e:
        msg = f"CDP 可用性检查失败: {e}"
        _browser_available = (False, msg)
        return _browser_available


def _try_start_chrome() -> tuple[bool, str]:
    """尝试自动启动Chrome（仅在未运行时）"""
    import subprocess
    import platform
    import time
    import os

    # 先检查是否已经运行
    available, _ = _check_cdp_available()
    if available:
        return (True, "Chrome already running")

    system = platform.system()
    chrome_commands = []
    errors = []  # 记录所有失败原因

    if system == "Darwin":  # macOS
        chrome_commands = [
            ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
             "--remote-debugging-port=9222", "--headless", "--disable-gpu", "--no-sandbox"],
            ["/Applications/Chromium.app/Contents/MacOS/Chromium",
             "--remote-debugging-port=9222", "--headless", "--disable-gpu", "--no-sandbox"]
        ]
    elif system == "Linux":
        chrome_commands = [
            ["google-chrome", "--remote-debugging-port=9222", "--headless", "--disable-gpu", "--no-sandbox"],
            ["chromium", "--remote-debugging-port=9222", "--headless", "--disable-gpu", "--no-sandbox"],
            ["chromium-browser", "--remote-debugging-port=9222", "--headless", "--disable-gpu", "--no-sandbox"]
        ]
    elif system == "Windows":
        chrome_commands = [
            ["C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
             "--remote-debugging-port=9222", "--headless", "--disable-gpu"],
            ["C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
             "--remote-debugging-port=9222", "--headless", "--disable-gpu"]
        ]

    # 尝试启动Chrome
    for cmd in chrome_commands:
        try:
            # 检查文件是否存在
            if not os.path.exists(cmd[0]):
                errors.append(f"{cmd[0]}: not found")
                continue

            logger.info(f"Trying to start Chrome: {cmd[0]}")
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True  # 后台运行
            )

            # 等待启动
            time.sleep(3)

            # 检查进程是否还在运行
            if proc.poll() is not None:
                # 进程已退出，读取错误信息
                _, stderr = proc.communicate()
                error_msg = stderr.decode('utf-8', errors='ignore').strip()
                errors.append(f"{cmd[0]}: process exited - {error_msg[:100]}")
                continue

            # 检查CDP服务是否可用
            # 重置缓存以强制重新检查
            global _browser_available
            _browser_available = None
            available, _ = _check_cdp_available()

            if available:
                logger.info("Chrome started successfully")
                return (True, f"Chrome started: {cmd[0]}")
            else:
                errors.append(f"{cmd[0]}: started but CDP not available")

        except FileNotFoundError:
            errors.append(f"{cmd[0]}: FileNotFoundError")
            continue
        except Exception as e:
            logger.warning(f"Failed to start {cmd[0]}: {e}")
            errors.append(f"{cmd[0]}: {str(e)}")
            continue

    # 所有尝试都失败了
    error_summary = "\n".join(f"  - {err}" for err in errors)
    return (False, f"Failed to start Chrome automatically:\n{error_summary}")


def _get_browser():
    """Get or create browser connection."""
    global _browser

    # 先检查服务是否可用
    available, reason = _check_cdp_available()
    if not available:
        # 尝试自动启动Chrome
        logger.info("CDP not available, trying to start Chrome...")
        started, start_msg = _try_start_chrome()
        if started:
            logger.info(f"Chrome started: {start_msg}")
            # 重置缓存，重新检查
            global _browser_available
            _browser_available = None
            available, reason = _check_cdp_available()
            if not available:
                raise RuntimeError(f"Chrome started but still not available: {reason}")
        else:
            raise RuntimeError(f"{reason}\n\n{_check_cdp_available()[1]}")

    if _browser is None:
        try:
            import pychrome
            _browser = pychrome.Browser(url="http://127.0.0.1:9222")
        except Exception as e:
            raise RuntimeError(f"Failed to connect to Chrome: {e}")
    return _browser


def _get_session_store():
    """Get or create session store instance."""
    global _session_store
    if _session_store is None:
        try:
            from backend.app.session import SessionStore
            _session_store = SessionStore()
        except Exception as e:
            logger.warning(f"Failed to load SessionStore: {e}")
    return _session_store


def _get_screenshot_path(output_path: str) -> str:
    """
    获取截图保存路径

    如果 output_path 是相对路径且没有指定目录，则保存到 session workspace
    否则使用指定的路径
    """
    path = Path(output_path)

    # 如果是绝对路径，直接使用
    if path.is_absolute():
        return output_path

    # 如果指定了目录（包含 /），使用相对路径
    if "/" in output_path or "\\" in output_path:
        return output_path

    # 否则尝试保存到 session workspace
    store = _get_session_store()
    if store:
        try:
            workspace_dir = store.get_workspace_dir()
            # 如果只是文件名，添加时间戳避免覆盖
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = path.stem
            extension = path.suffix or ".png"
            final_path = workspace_dir / f"{filename}_{timestamp}{extension}"
            return str(final_path)
        except Exception as e:
            logger.warning(f"Failed to get workspace dir: {e}")

    # 降级：保存到当前目录
    return output_path


@tool
def cdp_browser(
    action: Literal["navigate", "screenshot", "execute", "content", "click", "check_health", "wait_for"],
    url: str = "",
    script: str = "",
    selector: str = "",
    output_path: str = "screenshot.png",
    wait_time: int = 3
) -> str:
    """Control browser via Chrome DevTools Protocol.

    Args:
        action: Action to perform
            - navigate: Navigate to URL (auto-waits for load)
            - screenshot: Take screenshot
            - execute: Execute JavaScript
            - content: Get page text content
            - click: Click element by CSS selector
            - check_health: Check if CDP service is available
            - wait_for: Wait for element to appear (requires selector)
        url: URL to navigate to (for navigate action)
        script: JavaScript to execute (for execute action)
        selector: CSS selector (for click/wait_for action)
        output_path: Path to save screenshot (for screenshot action)
        wait_time: Seconds to wait after action (default: 3)

    Returns:
        Result of the action or error message
    """
    logger.info(f"cdp_browser: {action}")

    # 健康检查
    if action == "check_health":
        available, reason = _check_cdp_available()
        if available:
            return "✅ Chrome DevTools Protocol 服务可用 (端口 9222)"
        else:
            return f"❌ Chrome DevTools Protocol 服务不可用\n\n{reason}"

    try:
        browser = _get_browser()
        tabs = browser.list_tab()

        if not tabs:
            return "Error: No browser tabs available"

        tab = tabs[0]
        tab.start()

        # 辅助函数：等待元素出现
        def wait_for_element(sel: str, timeout: int = 10) -> bool:
            """等待元素出现，返回是否成功"""
            import time
            check_script = f"!!document.querySelector('{sel}')"
            end_time = time.time() + timeout
            while time.time() < end_time:
                result = tab.Runtime.evaluate(expression=check_script)
                if result.get("result", {}).get("value"):
                    return True
                time.sleep(0.5)
            return False

        if action == "navigate":
            if not url:
                return "Error: url required for navigate"
            tab.Page.navigate(url=url, _timeout=15)
            # 等待页面加载完成
            tab.wait(2)
            # 检查 document.readyState
            result = tab.Runtime.evaluate(expression="document.readyState")
            state = result.get("result", {}).get("value", "")
            if state != "complete":
                tab.wait(wait_time)
            return f"✅ Navigated to {url}"

        elif action == "screenshot":
            # 获取最终保存路径（可能是 workspace）
            final_path = _get_screenshot_path(output_path)
            result = tab.Page.captureScreenshot()
            import base64

            # 确保目录存在
            Path(final_path).parent.mkdir(parents=True, exist_ok=True)

            with open(final_path, "wb") as f:
                f.write(base64.b64decode(result["data"]))
            return f"✅ Screenshot saved to {final_path}"

        elif action == "wait_for":
            if not selector:
                return "Error: selector required for wait_for"
            success = wait_for_element(selector, timeout=wait_time * 2)
            if success:
                return f"✅ Element {selector} appeared"
            else:
                return f"❌ Element {selector} not found after {wait_time * 2}s"

        elif action == "execute":
            if not script:
                return "Error: script required for execute"
            result = tab.Runtime.evaluate(expression=script)
            tab.wait(wait_time)
            return json.dumps(result.get("result", {}), ensure_ascii=False)

        elif action == "content":
            result = tab.Runtime.evaluate(expression="document.body.innerText")
            content = result.get("result", {}).get("value", "")
            return content if content else "Error: No content retrieved"

        elif action == "click":
            if not selector:
                return "Error: selector required for click"
            # 先等待元素出现
            if not wait_for_element(selector, timeout=5):
                return f"Error: Element {selector} not found"
            script = f"document.querySelector('{selector}').click()"
            tab.Runtime.evaluate(expression=script)
            tab.wait(wait_time)
            return f"✅ Clicked {selector}"

        return "Error: Unknown action"

    except RuntimeError as e:
        # CDP 服务不可用的错误
        return f"Error: {str(e)}"
    except Exception as e:
        logger.error(f"CDP browser error: {e}", exc_info=True)
        return f"Error: {str(e)}"


def reset_cdp_cache():
    """重置 CDP 可用性缓存（用于测试或重启后）"""
    global _browser_available, _browser
    _browser_available = None
    _browser = None
