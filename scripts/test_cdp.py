#!/usr/bin/env python3
"""
CDP 工具测试脚本

使用前请确保：
1. 已安装 pychrome: pip install pychrome
2. 启动 Chrome 调试模式:
   - macOS: /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222
   - Windows: chrome.exe --remote-debugging-port=9222
   - Linux: google-chrome --remote-debugging-port=9222
"""

import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from app.tools.implementations.cdp_tool import cdp_browser


def test_navigate():
    """测试导航功能"""
    print("\n=== 测试 1: 导航到网页 ===")
    result = cdp_browser.invoke({
        "action": "navigate",
        "url": "https://www.example.com"
    })
    print(f"结果: {result}")


def test_content():
    """测试获取页面内容"""
    print("\n=== 测试 2: 获取页面文本内容 ===")
    result = cdp_browser.invoke({
        "action": "content"
    })
    print(f"页面内容: {result[:200]}...")  # 只显示前200字符


def test_execute():
    """测试执行 JavaScript"""
    print("\n=== 测试 3: 执行 JavaScript ===")
    result = cdp_browser.invoke({
        "action": "execute",
        "script": "document.title"
    })
    print(f"页面标题: {result}")


def test_screenshot():
    """测试截图功能"""
    print("\n=== 测试 4: 截图 ===")
    output_path = "/tmp/cdp_test_screenshot.png"
    result = cdp_browser.invoke({
        "action": "screenshot",
        "output_path": output_path
    })
    print(f"结果: {result}")
    if os.path.exists(output_path):
        print(f"✅ 截图已保存到: {output_path}")
    else:
        print(f"❌ 截图文件未找到")


def test_click():
    """测试点击功能"""
    print("\n=== 测试 5: 点击元素 ===")
    # 先导航到一个有链接的页面
    cdp_browser.invoke({
        "action": "navigate",
        "url": "https://www.example.com"
    })

    # 尝试点击第一个链接
    result = cdp_browser.invoke({
        "action": "click",
        "selector": "a"
    })
    print(f"结果: {result}")


def main():
    """运行所有测试"""
    print("=" * 60)
    print("CDP 工具测试")
    print("=" * 60)

    try:
        # 测试 1: 导航
        test_navigate()

        # 测试 2: 获取内容
        test_content()

        # 测试 3: 执行 JS
        test_execute()

        # 测试 4: 截图
        test_screenshot()

        # 测试 5: 点击
        test_click()

        print("\n" + "=" * 60)
        print("✅ 所有测试完成")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        print("\n请确保：")
        print("1. Chrome 已启动调试模式（端口 9222）")
        print("2. 已安装 pychrome: pip install pychrome")
        sys.exit(1)


if __name__ == "__main__":
    main()
