#!/usr/bin/env python3
"""
测试 CDP Browser 改进效果

测试场景：
1. JavaScript 执行（execute vs eval）
2. 日期解析
3. URL 构造策略
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.app.tools.implementations.cdp_tool import cdp_browser, parse_relative_date


def test_date_parsing():
    """测试日期解析功能"""
    print("=" * 60)
    print("测试 1: 日期解析")
    print("=" * 60)

    test_cases = [
        ("明天", "相对日期"),
        ("后天", "相对日期"),
        ("今天", "相对日期"),
        ("2026-03-15", "绝对日期"),
        ("2026/03/15", "斜杠格式"),
        ("20260315", "紧凑格式"),
    ]

    for date_str, desc in test_cases:
        result = parse_relative_date(date_str)
        print(f"  {desc:12} '{date_str:12}' → {result}")

    print()


def test_cdp_health():
    """测试 CDP 服务健康检查"""
    print("=" * 60)
    print("测试 2: CDP 服务健康检查")
    print("=" * 60)

    result = cdp_browser(action="check_health")
    print(f"  {result}")
    print()

    if "不可用" in result:
        print("⚠️  CDP 服务未启动，跳过后续测试")
        print()
        print("启动方法：")
        print("  google-chrome --remote-debugging-port=9222 --headless")
        return False

    return True


def test_javascript_execution():
    """测试 JavaScript 执行（execute vs eval）"""
    print("=" * 60)
    print("测试 3: JavaScript 执行")
    print("=" * 60)

    # 先导航到一个页面
    print("  导航到测试页面...")
    nav_result = cdp_browser(action="navigate", url="https://example.com")
    print(f"  {nav_result}")

    # 测试 eval（表达式）
    print("\n  测试 eval 动作（表达式求值）:")
    eval_result = cdp_browser(action="eval", script="document.title")
    print(f"    document.title → {eval_result}")

    # 测试 execute（语句）
    print("\n  测试 execute 动作（语句执行，自动包装为 IIFE）:")
    execute_script = """
        const title = document.title;
        const url = document.URL;
        return {title: title, url: url};
    """
    execute_result = cdp_browser(action="execute", script=execute_script)
    print(f"    返回对象 → {execute_result[:100]}...")

    print()


def test_url_construction():
    """测试 URL 构造策略"""
    print("=" * 60)
    print("测试 4: URL 构造策略（机票查询）")
    print("=" * 60)

    # 解析日期
    date = parse_relative_date("明天")
    print(f"  查询日期: 明天 → {date}")

    # 构造去哪儿 URL
    qunar_url = (
        f"https://flight.qunar.com/site/oneway_list.htm?"
        f"searchDepartureAirport=北京&"
        f"searchArrivalAirport=上海&"
        f"searchDepartureTime={date}"
    )
    print(f"\n  去哪儿 URL:")
    print(f"    {qunar_url}")

    # 导航测试
    print(f"\n  导航到去哪儿...")
    nav_result = cdp_browser(action="navigate", url=qunar_url, wait_time=5)
    print(f"    {nav_result}")

    # 等待页面加载
    print(f"\n  等待航班列表元素...")
    wait_result = cdp_browser(
        action="wait_for",
        selector=".m-airfly-lst, .list-item, .flight-item",
        wait_time=10
    )
    print(f"    {wait_result}")

    # 获取页面内容
    if "appeared" in wait_result:
        print(f"\n  获取页面内容...")
        content = cdp_browser(action="content")
        # 只显示前 500 字符
        print(f"    {content[:500]}...")

    print()


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("CDP Browser 改进效果测试")
    print("=" * 60)
    print()

    # 测试 1: 日期解析（不需要 CDP）
    test_date_parsing()

    # 测试 2: CDP 健康检查
    cdp_available = test_cdp_health()

    if not cdp_available:
        print("❌ 测试终止：CDP 服务不可用")
        return

    # 测试 3: JavaScript 执行
    try:
        test_javascript_execution()
    except Exception as e:
        print(f"  ❌ JavaScript 执行测试失败: {e}")

    # 测试 4: URL 构造
    try:
        test_url_construction()
    except Exception as e:
        print(f"  ❌ URL 构造测试失败: {e}")

    print("=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
