"""
意图识别功能测试脚本

测试 IntentService 的各项功能：
1. 意图分析
2. 澄清问题生成
3. 置信度检查
"""
import sys
from pathlib import Path

# 添加项目路径
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from backend.app.intent import IntentService
from backend.app.intent.service import IntentConverter, IntentBuilder


def test_clear_intent():
    """测试明确的意图"""
    print("=" * 60)
    print("测试1: 明确的意图")
    print("=" * 60)

    service = IntentService()

    test_cases = [
        "读取 backend/app/agent.py 文件",
        "在 backend/app/tools/ 目录下搜索包含 @tool 的文件",
        "运行 pytest tests/",
    ]

    for user_input in test_cases:
        print(f"\n用户输入: {user_input}")
        result = service.analyze_intent(user_input)
        print(f"意图类型: {result['intent']}")
        print(f"置信度: {result['confidence']:.2f}")
        print(f"需要澄清: {result['needs_clarification']}")
        print(f"推理: {result['reasoning']}")
        print("-" * 60)


def test_ambiguous_intent():
    """测试模糊的意图"""
    print("\n" + "=" * 60)
    print("测试2: 模糊的意图")
    print("=" * 60)

    service = IntentService()

    test_cases = [
        "帮我加个功能",
        "优化性能",
        "修复bug",
        "实现用户认证",
    ]

    for user_input in test_cases:
        print(f"\n用户输入: {user_input}")
        result = service.analyze_intent(user_input)
        print(f"意图类型: {result['intent']}")
        print(f"置信度: {result['confidence']:.2f}")
        print(f"需要澄清: {result['needs_clarification']}")

        if result['needs_clarification']:
            print(f"\n澄清问题:")
            for i, q in enumerate(result['clarification_questions'], 1):
                print(f"  {i}. {q}")

        print("-" * 60)


def test_clarification_generation():
    """测试澄清问题生成"""
    print("\n" + "=" * 60)
    print("测试3: 澄清问题生成")
    print("=" * 60)

    service = IntentService()

    user_input = "帮我实现一个API"
    ambiguous_aspects = ["API功能", "技术栈", "数据格式", "认证方式"]

    print(f"\n用户输入: {user_input}")
    print(f"模糊方面: {', '.join(ambiguous_aspects)}")

    questions = service.generate_clarification(user_input, ambiguous_aspects)

    print(f"\n生成的澄清问题:")
    for i, q in enumerate(questions, 1):
        print(f"  {i}. {q}")

    print("-" * 60)


def test_converter():
    """测试转换器"""
    print("\n" + "=" * 60)
    print("测试4: 结果转换")
    print("=" * 60)

    result = {
        "intent": "ambiguous",
        "confidence": 0.4,
        "needs_clarification": True,
        "clarification_questions": [
            "您想要实现什么功能？",
            "这个功能应该放在哪个模块？",
            "有什么具体的技术要求吗？"
        ],
        "extracted_info": {},
        "reasoning": "用户输入过于简短"
    }

    message = IntentConverter.to_user_message(result)
    print(f"\n用户友好消息:\n{message}")
    print("-" * 60)


def test_builder():
    """测试构建器"""
    print("\n" + "=" * 60)
    print("测试5: 结果构建")
    print("=" * 60)

    response = IntentBuilder.build_response(
        intent="code_generation",
        confidence=0.85,
        needs_clarification=False,
        questions=[]
    )

    print(f"\n构建的响应:")
    for key, value in response.items():
        print(f"  {key}: {value}")

    print("-" * 60)


def main():
    """运行所有测试"""
    print("\n🧪 意图识别功能测试\n")

    try:
        test_clear_intent()
        test_ambiguous_intent()
        test_clarification_generation()
        test_converter()
        test_builder()

        print("\n" + "=" * 60)
        print("✅ 所有测试完成")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
