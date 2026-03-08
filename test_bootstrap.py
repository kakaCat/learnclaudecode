"""
测试 Bootstrap 加载和记忆系统

验证：
1. Bootstrap 文件加载
2. 记忆写入和搜索
3. 系统提示词组装
"""
from backend.app.session import get_store
from backend.app.prompts import build_system_prompt, auto_recall_memory

def test_bootstrap_loading():
    """测试 Bootstrap 文件加载"""
    print("=" * 60)
    print("测试 1: Bootstrap 文件加载")
    print("=" * 60)

    store = get_store()
    store.set_current_key("test_session")

    # 加载所有 Bootstrap 文件
    bootstrap_data = store.load_bootstrap(mode="full")

    print(f"\n加载的文件数量: {len(bootstrap_data)}")
    for name, content in bootstrap_data.items():
        print(f"  - {name}: {len(content)} 字符")

    # 加载 SOUL
    soul = store.load_soul()
    print(f"\nSOUL.md 内容预览:")
    print(soul[:200] + "..." if len(soul) > 200 else soul)

    return bootstrap_data


def test_memory_system():
    """测试记忆系统"""
    print("\n" + "=" * 60)
    print("测试 2: 记忆系统")
    print("=" * 60)

    store = get_store()

    # 写入记忆
    print("\n写入记忆...")
    result1 = store.write_memory("用户喜欢使用 Python 编程", category="preference")
    print(f"  {result1}")

    result2 = store.write_memory("项目使用 FastAPI 框架", category="fact")
    print(f"  {result2}")

    result3 = store.write_memory("需要实现 Bootstrap 文件加载功能", category="context")
    print(f"  {result3}")

    # 搜索记忆
    print("\n搜索记忆: 'Python'")
    results = store.hybrid_search_memory("Python", top_k=3)
    for r in results:
        print(f"  [{r['score']:.4f}] {r['path']}: {r['snippet'][:80]}...")

    # 统计信息
    print("\n记忆统计:")
    stats = store.get_memory_stats()
    print(f"  长期记忆: {stats['evergreen_chars']} 字符")
    print(f"  每日文件: {stats['daily_files']} 个")
    print(f"  每日条目: {stats['daily_entries']} 条")


def test_system_prompt():
    """测试系统提示词组装"""
    print("\n" + "=" * 60)
    print("测试 3: 系统提示词组装")
    print("=" * 60)

    # 自动召回记忆
    memory_context = auto_recall_memory("test_session", "帮我写 Python 代码")
    print(f"\n自动召回的记忆:")
    print(memory_context if memory_context else "  (无相关记忆)")

    # 构建系统提示词
    prompt = build_system_prompt(
        session_key="test_session",
        mode="full",
        memory_context=memory_context
    )

    print(f"\n系统提示词总长度: {len(prompt)} 字符")
    print(f"\n系统提示词预览 (前 500 字符):")
    print("-" * 60)
    print(prompt[:500])
    print("...")
    print("-" * 60)


def main():
    """运行所有测试"""
    try:
        test_bootstrap_loading()
        test_memory_system()
        test_system_prompt()

        print("\n" + "=" * 60)
        print("✅ 所有测试完成！")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
