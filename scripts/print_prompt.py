#!/usr/bin/env python3
"""
打印系统提示词的测试脚本

用法:
    python scripts/print_prompt.py                    # 打印到控制台
    python scripts/print_prompt.py output.txt         # 保存到文件
    python scripts/print_prompt.py output.txt minimal # 使用 minimal 模式
"""

import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.prompts import print_system_prompt


if __name__ == "__main__":
    output_file = sys.argv[1] if len(sys.argv) > 1 else None
    mode = sys.argv[2] if len(sys.argv) > 2 else "full"
    session_key = ""  # 空会话，使用默认值

    print_system_prompt(session_key, mode, output_file)
