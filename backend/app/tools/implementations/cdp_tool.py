import logging
import json
from typing import Literal
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# Global browser instance
_browser = None


def _get_browser():
    """Get or create browser connection."""
    global _browser
    if _browser is None:
        try:
            import pychrome
            _browser = pychrome.Browser(url="http://127.0.0.1:9222")
        except Exception as e:
            raise RuntimeError(f"Failed to connect to Chrome. Start Chrome with: chrome --remote-debugging-port=9222. Error: {e}")
    return _browser


@tool
def cdp_browser(
    action: Literal["navigate", "screenshot", "execute", "content", "click"],
    url: str = "",
    script: str = "",
    selector: str = "",
    output_path: str = "screenshot.png"
) -> str:
    """Control browser via Chrome DevTools Protocol.

    Args:
        action: Action to perform (navigate/screenshot/execute/content/click)
        url: URL to navigate to (for navigate action)
        script: JavaScript to execute (for execute action)
        selector: CSS selector (for click action)
        output_path: Path to save screenshot (for screenshot action)

    Returns:
        Result of the action
    """
    logger.info(f"cdp_browser: {action}")

    try:
        browser = _get_browser()
        tab = browser.list_tab()[0]
        tab.start()

        if action == "navigate":
            if not url:
                return "Error: url required for navigate"
            tab.Page.navigate(url=url, _timeout=10)
            tab.wait(5)
            return f"Navigated to {url}"

        elif action == "screenshot":
            result = tab.Page.captureScreenshot()
            import base64
            with open(output_path, "wb") as f:
                f.write(base64.b64decode(result["data"]))
            return f"Screenshot saved to {output_path}"

        elif action == "execute":
            if not script:
                return "Error: script required for execute"
            result = tab.Runtime.evaluate(expression=script)
            return json.dumps(result.get("result", {}), ensure_ascii=False)

        elif action == "content":
            result = tab.Runtime.evaluate(expression="document.body.innerText")
            return result.get("result", {}).get("value", "")

        elif action == "click":
            if not selector:
                return "Error: selector required for click"
            script = f"document.querySelector('{selector}').click()"
            tab.Runtime.evaluate(expression=script)
            return f"Clicked {selector}"

        return "Error: Unknown action"

    except Exception as e:
        return f"Error: {str(e)}"
