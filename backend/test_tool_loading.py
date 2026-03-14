#!/usr/bin/env python3
"""
测试 Spring MVC 风格的工具自动加载

运行: python backend/test_tool_loading.py
"""

from pathlib import Path
from backend.app.tools.manager import tool_manager
from backend.app.tools.base import get_registered_tools


def test_auto_discover():
    """测试自动发现和加载"""
    print("=" * 80)
    print("🧪 测试工具自动加载")
    print("=" * 80)

    # 1. 查看注册表（在扫描前）
    print("\n📋 扫描前的注册表:")
    registry = get_registered_tools()
    print(f"  已注册工具数: {len(registry)}")

    # 2. 自动扫描
    tools_dir = Path(__file__).parent / "app" / "tools"
    tool_manager.auto_discover(tools_dir)

    # 3. 查看注册表（在扫描后）
    print("\n📋 扫描后的注册表:")
    registry = get_registered_tools()
    print(f"  已注册工具数: {len(registry)}")

    # 4. 按分类统计
    print("\n📊 按分类统计:")
    categories = {}
    for name, tool in registry.items():
        cat = getattr(tool, "_category", "unknown")
        categories[cat] = categories.get(cat, 0) + 1

    for cat, count in sorted(categories.items()):
        print(f"  {cat}: {count} 个工具")

    # 5. 按作用域获取
    print("\n🎯 按作用域获取:")
    main_tools = tool_manager.get_main_tools()
    subagent_tools = tool_manager.get_subagent_tools()
    all_tools = tool_manager.get_tools(scope="all")

    print(f"  main: {len(main_tools)} 个工具")
    print(f"  subagent: {len(subagent_tools)} 个工具")
    print(f"  all: {len(all_tools)} 个工具")

    # 6. 显示部分工具详情
    print("\n🔧 工具详情示例:")
    for name in list(registry.keys())[:5]:
        tool = registry[name]
        cat = getattr(tool, "_category", "unknown")
        tags = getattr(tool, "tags", [])
        print(f"  - {name} [category={cat}, tags={tags}]")

    print("\n✅ 测试完成!")


if __name__ == "__main__":
    test_auto_discover()
