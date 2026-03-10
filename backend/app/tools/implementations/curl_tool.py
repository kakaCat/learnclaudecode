import subprocess
import logging
from langchain_core.tools import tool

logger = logging.getLogger(__name__)


@tool(tags=["both"])
def curl(url: str, method: str = "GET", headers: str = "", data: str = "") -> str:
    """Execute a curl command to make HTTP requests.

    Args:
        url: The URL to request
        method: HTTP method (GET, POST, PUT, DELETE, etc.)
        headers: Headers in format "Key1: Value1\nKey2: Value2"
        data: Request body data for POST/PUT requests

    Returns:
        Response from the server
    """
    logger.info(f"curl: {method} {url}")

    cmd = ["curl", "-X", method, "-s"]

    if headers:
        for header in headers.strip().split("\n"):
            if header.strip():
                cmd.extend(["-H", header.strip()])

    if data:
        cmd.extend(["-d", data])

    cmd.append(url)

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return result.stdout if result.returncode == 0 else f"Error: {result.stderr}"
    except subprocess.TimeoutExpired:
        return "Error: Request timeout"
    except Exception as e:
        return f"Error: {str(e)}"
