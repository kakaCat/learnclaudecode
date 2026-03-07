"""
意图识别功能使用示例

演示如何在实际场景中使用意图识别和澄清功能。
"""
import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from backend.app.intent import IntentService


def example_1_simple_workflow():
    """示例1: 简单的意图识别工作流"""
    print("=" * 60)
    print("示例1: 简单工作流")
    print("=" * 60)

    service = IntentService()

    # 用户输入
    user_input = "帮我优化代码"

    # 步骤1: 分析意图
    print(f"\n用户: {user_input}")
    result = service.analyze_intent(user_input)

    print(f"\n意图分析:")
    print(f"  类型: {result['intent']}")
    print(f"  置信度: {result['confidence']:.2f}")

    # 步骤2: 判断是否需要澄清
    if result['needs_clarification']:
        print(f"\n⚠️ 需要澄清，向用户提问:")
        for i, q in enumerate(result['clarification_questions'], 1):
            print(f"  {i}. {q}")

        # 模拟用户回答
        print(f"\n用户回答: 优化 backend/app/agent.py 的性能，减少内存占用")
        print("✅ 现在可以继续执行任务")
    else:
        print(f"\n✅ 意图明确，可以直接执行")


def example_2_confidence_check():
    """示例2: 置信度检查"""
    print("\n" + "=" * 60)
    print("示例2: 置信度检查")
    print("=" * 60)

    service = IntentService()

    test_inputs = [
        ("读取 config.py 文件", 0.7),  # 明确
        ("改一下配置", 0.7),           # 模糊
    ]

    for user_input, threshold in test_inputs:
        print(f"\n用户: {user_input}")
        result = service.analyze_intent(user_input)

        if result['confidence'] >= threshold:
            print(f"✅ 置信度 {result['confidence']:.2f} >= {threshold}，可以执行")
        else:
            print(f"⚠️ 置信度 {result['confidence']:.2f} < {threshold}，建议澄清")
            if result['clarification_questions']:
                print(f"建议问题: {result['clarification_questions'][0]}")


def example_3_extract_info():
    """示例3: 提取关键信息"""
    print("\n" + "=" * 60)
    print("示例3: 提取关键信息")
    print("=" * 60)

    service = IntentService()

    user_input = "在 backend/app/tools/ 目录下创建一个新的工具文件"

    print(f"\n用户: {user_input}")
    result = service.analyze_intent(user_input)

    print(f"\n提取的信息:")
    for key, value in result.get('extracted_info', {}).items():
        print(f"  {key}: {value}")

    print(f"\n可以直接使用这些信息执行任务")


def example_4_multi_turn_clarification():
    """示例4: 多轮澄清"""
    print("\n" + "=" * 60)
    print("示例4: 多轮澄清")
    print("=" * 60)

    service = IntentService()

    # 第一轮
    user_input_1 = "实现一个功能"
    print(f"\n[第1轮] 用户: {user_input_1}")

    result_1 = service.analyze_intent(user_input_1)
    if result_1['needs_clarification']:
        print(f"AI: {result_1['clarification_questions'][0]}")

    # 第二轮
    user_input_2 = "用户登录功能"
    print(f"\n[第2轮] 用户: {user_input_2}")

    result_2 = service.analyze_intent(user_input_2)
    if result_2['needs_clarification']:
        print(f"AI: {result_2['clarification_questions'][0]}")

    # 第三轮
    user_input_3 = "使用JWT认证，支持邮箱和手机号登录"
    print(f"\n[第3轮] 用户: {user_input_3}")

    result_3 = service.analyze_intent(user_input_3)
    if not result_3['needs_clarification']:
        print(f"✅ 信息充足，开始实现")


def main():
    """运行所有示例"""
    print("\n📚 意图识别功能使用示例\n")

    try:
        example_1_simple_workflow()
        example_2_confidence_check()
        example_3_extract_info()
        example_4_multi_turn_clarification()

        print("\n" + "=" * 60)
        print("✅ 所有示例运行完成")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ 示例运行失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
