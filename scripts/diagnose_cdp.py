#!/usr/bin/env python3
"""
CDP 工具诊断脚本
检查 CDP 工具是否正确注册和可用
"""

import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def check_pychrome():
    """检查 pychrome 是否安装"""
    print("=" * 60)
    print("1. 检查 pychrome 依赖")
    print("=" * 60)
    try:
        import pychrome
        print(f"✅ pychrome 已安装: {pychrome.__version__ if hasattr(pychrome, '__version__') else 'unknown version'}")
        return True
    except ImportError:
        print("❌ pychrome 未安装")
        print("   请运行: pip install pychrome")
        return False


def check_chrome_connection():
    """检查 Chrome 调试端口连接"""
    print("\n" + "=" * 60)
    print("2. 检查 Chrome 调试端口")
    print("=" * 60)
    try:
        import pychrome
        browser = pychrome.Browser(url="http://127.0.0.1:9222")
        tabs = browser.list_tab()
        print(f"✅ Chrome 调试端口可用")
        print(f"   当前标签页数量: {len(tabs)}")
        return True
    except Exception as e:
        print(f"❌ 无法连接到 Chrome 调试端口")
        print(f"   错误: {e}")
        print("\n   请启动 Chrome 调试模式:")
        print("   macOS: /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome --remote-debugging-port=9222")
        print("   或: google-chrome --remote-debugging-port=9222")
        return False


def check_tool_registration():
    """检查 CDP 工具是否注册"""
    print("\n" + "=" * 60)
    print("3. 检查工具注册")
    print("=" * 60)
    try:
        from backend.app.tools.manager import tool_manager
        tools = tool_manager.get_tools()
        tool_names = [t.name for t in tools]

        print(f"✅ 工具管理器已加载 {len(tools)} 个工具")

        if "cdp_browser" in tool_names:
            print("✅ cdp_browser 工具已注册")

            # 获取工具详情
            cdp_tool = tool_manager.get("cdp_browser")
            print(f"   工具名称: {cdp_tool.name}")
            print(f"   工具描述: {cdp_tool.description[:100]}...")
            return True
        else:
            print("❌ cdp_browser 工具未注册")
            print(f"   已注册的工具: {', '.join(tool_names)}")
            return False

    except Exception as e:
        print(f"❌ 检查工具注册失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_tool_invoke():
    """测试工具调用"""
    print("\n" + "=" * 60)
    print("4. 测试工具调用")
    print("=" * 60)
    try:
        from backend.app.tools.implementations.cdp_tool import cdp_browser

        # 测试导航
        print("测试: 导航到 example.com")
        result = cdp_browser.invoke({
            "action": "navigate",
            "url": "https://www.example.com"
        })
        print(f"✅ 结果: {result}")

        # 测试获取内容
        print("\n测试: 获取页面内容")
        result = cdp_browser.invoke({
            "action": "content"
        })
        print(f"✅ 内容长度: {len(result)} 字符")
        print(f"   前100字符: {result[:100]}...")

        return True

    except Exception as e:
        print(f"❌ 工具调用失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行所有诊断"""
    print("\n" + "=" * 60)
    print("CDP 工具诊断")
    print("=" * 60 + "\n")

    results = []

    # 1. 检查依赖
    results.append(("pychrome 依赖", check_pychrome()))

    # 2. 检查 Chrome 连接
    results.append(("Chrome 调试端口", check_chrome_connection()))

    # 3. 检查工具注册
    results.append(("工具注册", check_tool_registration()))

    # 4. 测试工具调用（只有前面都成功才测试）
    if all(r[1] for r in results):
        results.append(("工具调用", test_tool_invoke()))

    # 总结
    print("\n" + "=" * 60)
    print("诊断总结")
    print("=" * 60)
    for name, success in results:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"{status} - {name}")

    print("\n" + "=" * 60)
    if all(r[1] for r in results):
        print("✅ 所有检查通过！CDP 工具可以正常使用")
        print("\n你可以在 agent 中使用以下命令测试:")
        print('  python -m backend.main "使用 cdp_browser 访问 example.com"')
    else:
        print("❌ 部分检查失败，请根据上述提示修复问题")
    print("=" * 60)


if __name__ == "__main__":
    main()
