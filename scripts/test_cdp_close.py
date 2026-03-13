#!/usr/bin/env python3
"""测试 CDP 工具的连接管理和关闭功能"""

import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.app.tools.implementations.integration.cdp_tool import cdp_browser, reset_cdp_cache


def test_connection_reuse():
    """测试连接复用"""
    print("=" * 60)
    print("测试 1: 连接复用")
    print("=" * 60)

    # 第一次调用 - 创建连接
    print("\n1. 第一次导航（创建新连接）")
    result = cdp_browser(action="navigate", url="https://www.baidu.com")
    print(f"   结果: {result}")

    # 第二次调用 - 应该复用连接
    print("\n2. 第二次导航（复用连接）")
    result = cdp_browser(action="navigate", url="https://www.google.com")
    print(f"   结果: {result}")

    # 第三次调用 - 获取内容
    print("\n3. 获取页面内容（复用连接）")
    result = cdp_browser(action="content")
    print(f"   结果: {result[:100]}...")

    print("\n✅ 连接复用测试完成")


def test_explicit_close():
    """测试显式关闭"""
    print("\n" + "=" * 60)
    print("测试 2: 显式关闭连接")
    print("=" * 60)

    # 打开连接
    print("\n1. 打开连接")
    result = cdp_browser(action="navigate", url="https://www.baidu.com")
    print(f"   结果: {result}")

    # 显式关闭
    print("\n2. 显式关闭连接")
    result = cdp_browser(action="close")
    print(f"   结果: {result}")

    # 再次关闭（应该提示无连接）
    print("\n3. 再次关闭（应该提示无连接）")
    result = cdp_browser(action="close")
    print(f"   结果: {result}")

    # 重新打开（应该创建新连接）
    print("\n4. 重新打开（创建新连接）")
    result = cdp_browser(action="navigate", url="https://www.google.com")
    print(f"   结果: {result}")

    print("\n✅ 显式关闭测试完成")


def test_error_recovery():
    """测试错误恢复"""
    print("\n" + "=" * 60)
    print("测试 3: 错误恢复")
    print("=" * 60)

    # 正常操作
    print("\n1. 正常导航")
    result = cdp_browser(action="navigate", url="https://www.baidu.com")
    print(f"   结果: {result}")

    # 执行错误的 JavaScript（模拟错误）
    print("\n2. 执行错误的 JavaScript")
    result = cdp_browser(action="eval", script="throw new Error('test error')")
    print(f"   结果: {result}")

    # 应该能继续工作
    print("\n3. 继续操作（应该能恢复）")
    result = cdp_browser(action="content")
    print(f"   结果: {result[:100]}...")

    print("\n✅ 错误恢复测试完成")


def test_health_check():
    """测试健康检查"""
    print("\n" + "=" * 60)
    print("测试 4: 健康检查")
    print("=" * 60)

    print("\n1. 检查 CDP 服务状态")
    result = cdp_browser(action="check_health")
    print(f"   结果: {result}")

    print("\n✅ 健康检查测试完成")


def main():
    print("\n🧪 CDP 工具连接管理测试")
    print("=" * 60)

    try:
        # 重置状态
        reset_cdp_cache()

        # 运行测试
        test_health_check()
        test_connection_reuse()
        test_explicit_close()
        test_error_recovery()

        # 清理
        print("\n" + "=" * 60)
        print("清理资源")
        print("=" * 60)
        result = cdp_browser(action="close")
        print(f"结果: {result}")

        print("\n" + "=" * 60)
        print("✅ 所有测试完成！")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
