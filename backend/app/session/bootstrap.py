"""
Bootstrap 文件加载器

参考 s06_intelligence.py 的 BootstrapLoader 设计：
- 从全局 .bootstrap 目录加载 Bootstrap 文件（SOUL.md, IDENTITY.md, TOOLS.md 等）
- 支持文件截断（防止超长文件）
- 支持总字符数限制
- 支持不同加载模式（full/minimal/none）
"""
from pathlib import Path
from typing import Dict, List

from .constants import BOOTSTRAP_DIR

# Bootstrap 文件名 - 每个 agent 启动时加载这些文件
BOOTSTRAP_FILES = [
    "SOUL.md",       # 人格定义
    "IDENTITY.md",   # 身份定义
    "TOOLS.md",      # 工具使用指南
    "USER.md",       # 用户信息
    "HEARTBEAT.md",  # 心跳配置
    "BOOTSTRAP.md",  # 启动配置
    "AGENTS.md",     # Agent 配置
    "MEMORY.md",     # 长期记忆
]

MAX_FILE_CHARS = 20000      # 单个文件最大字符数
MAX_TOTAL_CHARS = 150000    # 所有文件总字符数上限


class BootstrapLoader:
    """
    Bootstrap 文件加载器

    从全局 .bootstrap 目录加载配置文件，用于构建系统提示词。
    不同加载模式适用于不同场景：
      - full: 主 agent（加载所有文件）
      - minimal: 子 agent / cron（仅加载 AGENTS.md, TOOLS.md）
      - none: 最小化（不加载任何文件）
    """

    def __init__(self, bootstrap_dir: Path = BOOTSTRAP_DIR):
        """
        Args:
            bootstrap_dir: Bootstrap 配置目录路径（默认为全局 .bootstrap）
        """
        self.bootstrap_dir = bootstrap_dir

    def load_file(self, name: str) -> str:
        """
        加载单个文件

        Args:
            name: 文件名（如 "SOUL.md"）

        Returns:
            文件内容，文件不存在或读取失败返回空字符串
        """
        path = self.bootstrap_dir / name
        if not path.is_file():
            return ""
        try:
            return path.read_text(encoding="utf-8")
        except Exception:
            return ""

    def truncate_file(self, content: str, max_chars: int = MAX_FILE_CHARS) -> str:
        """
        截断超长文件内容

        仅保留头部，在行边界处截断，避免截断到单词中间。

        Args:
            content: 原始内容
            max_chars: 最大字符数

        Returns:
            截断后的内容（如果需要截断会添加提示信息）
        """
        if len(content) <= max_chars:
            return content

        # 在行边界处截断
        cut = content.rfind("\n", 0, max_chars)
        if cut <= 0:
            cut = max_chars

        return content[:cut] + f"\n\n[... truncated ({len(content)} chars total, showing first {cut}) ...]"

    def load_all(self, mode: str = "full") -> Dict[str, str]:
        """
        加载所有 Bootstrap 文件

        Args:
            mode: 加载模式
                - "full": 加载所有文件（主 agent）
                - "minimal": 仅加载 AGENTS.md, TOOLS.md（子 agent）
                - "none": 不加载任何文件

        Returns:
            文件名 -> 内容的字典
        """
        if mode == "none":
            return {}

        # 确定要加载的文件列表
        if mode == "minimal":
            names = ["AGENTS.md", "TOOLS.md"]
        else:  # full
            names = list(BOOTSTRAP_FILES)

        result: Dict[str, str] = {}
        total = 0

        for name in names:
            raw = self.load_file(name)
            if not raw:
                continue

            # 截断单个文件
            truncated = self.truncate_file(raw)

            # 检查总字符数限制
            if total + len(truncated) > MAX_TOTAL_CHARS:
                remaining = MAX_TOTAL_CHARS - total
                if remaining > 0:
                    truncated = self.truncate_file(raw, remaining)
                else:
                    break

            result[name] = truncated
            total += len(truncated)

        return result


def load_soul(bootstrap_dir: Path = BOOTSTRAP_DIR) -> str:
    """
    加载 SOUL.md 文件

    SOUL.md 定义 agent 的人格，注入到系统提示词的靠前位置。

    Args:
        bootstrap_dir: Bootstrap 配置目录（默认为全局 .bootstrap）

    Returns:
        SOUL.md 内容，文件不存在返回空字符串
    """
    path = bootstrap_dir / "SOUL.md"
    if not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8").strip()
    except Exception:
        return ""
