from __future__ import annotations
import logging
import re
import requests

logger = logging.getLogger(__name__)


class WebFetch:
    """
    抓取 URL 全文，返回纯文本。

    去除 HTML 标签，压缩空白，截断至 max_chars。
    """

    def __init__(self, max_chars: int = 3000, timeout: int = 10):
        self.max_chars = max_chars
        self.timeout = timeout

    def fetch(self, url: str, max_chars: int | None = None) -> str:
        """
        抓取 URL 内容，返回纯文本。

        Args:
            url: 目标 URL
            max_chars: 最大字符数，默认使用实例配置

        Returns:
            纯文本内容（截断至 max_chars），失败返回空字符串
        """
        limit = max_chars or self.max_chars
        logger.info("WebFetch: %s (max_chars=%d)", url, limit)
        try:
            resp = requests.get(
                url,
                timeout=self.timeout,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            resp.raise_for_status()
            text = re.sub(r"<[^>]+>", " ", resp.text)
            text = re.sub(r"\s+", " ", text).strip()
            return text[:limit]
        except Exception as e:
            logger.warning("WebFetch failed: %s %s", url, e)
            return ""
