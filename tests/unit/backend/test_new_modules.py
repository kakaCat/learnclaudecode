#!/usr/bin/env python3
"""
测试新模块的简单脚本

这个脚本用于验证新添加的模块（monitoring.py, exceptions.py）是否正常工作，
不会影响现有系统。
"""

import sys
import os
import pytest

# 添加项目根目录到 Python 路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)  # backend 目录
sys.path.insert(0, project_root)

def test_exceptions_module():
    """测试异常模块"""
    print("=== 测试 exceptions 模块 ===")
    
    try:
        from backend.app.exceptions import AgentError, ToolExecutionError, handle_agent_errors
        
        # 测试基础异常
        base_error = AgentError("测试错误", code="TEST_ERROR")
        print(f"✓ AgentError 创建成功: {base_error}")
        print(f"  错误代码: {base_error.code}")
        print(f"  转换为字典: {base_error.to_dict()}")
        
        # 测试工具异常
        class MockException(Exception):
            pass
        
        tool_error = ToolExecutionError("read_file", MockException("文件不存在"))
        print(f"\n✓ ToolExecutionError 创建成功: {tool_error}")
        print(f"  详细信息: {tool_error.details}")
        
        # 测试装饰器
        @handle_agent_errors
        def risky_function():
            raise ValueError("测试异常")
        
        try:
            risky_function()
        except AgentError as e:
            print(f"\n✓ 错误处理装饰器工作正常: {e}")
            print(f"  包装后的错误代码: {e.code}")
        
        print("\n✅ exceptions 模块测试通过")

    except Exception as e:
        print(f"❌ exceptions 模块测试失败: {e}")
        import traceback
        traceback.print_exc()
        pytest.fail(f"exceptions 模块测试失败: {e}")

def test_monitoring_module():
    """测试监控模块"""
    print("\n=== 测试 monitoring 模块 ===")
    
    try:
        from backend.app.monitoring import PerformanceMonitor, get_global_monitor
        
        # 创建监控器
        monitor = PerformanceMonitor(enabled=True)
        print(f"✓ PerformanceMonitor 创建成功")
        
        # 测试工具跟踪
        import time
        
        with monitor.track_tool("test_tool", param1="value1"):
            time.sleep(0.01)  # 模拟工作
        
        print(f"✓ 工具跟踪工作正常")
        
        # 测试 LLM 跟踪
        with monitor.track_llm("test-model", prompt_tokens=100):
            time.sleep(0.01)
        
        print(f"✓ LLM 跟踪工作正常")
        
        # 获取报告
        report = monitor.get_report()
        print(f"✓ 报告生成成功")
        print(f"  总调用数: {report['total_calls']['total']}")
        print(f"  工具调用: {report['total_calls']['tools']}")
        print(f"  LLM 调用: {report['total_calls']['llm']}")
        print(f"  性能评分: {report['performance_score']['overall']}/100")
        
        # 测试全局监控器
        global_monitor = get_global_monitor()
        print(f"\n✓ 全局监控器获取成功: {global_monitor}")
        
        print("\n✅ monitoring 模块测试通过")

    except Exception as e:
        print(f"❌ monitoring 模块测试失败: {e}")
        import traceback
        traceback.print_exc()
        pytest.fail(f"monitoring 模块测试失败: {e}")

@pytest.mark.skip(reason="项目使用 requirements.txt 而不是 pyproject.toml")
def test_pyproject_toml():
    """验证 pyproject.toml 文件"""
    print("\n=== 验证 pyproject.toml ===")

    try:
        import tomllib

        with open("pyproject.toml", "rb") as f:
            config = tomllib.load(f)
        
        print(f"✓ pyproject.toml 解析成功")
        print(f"  项目名称: {config['project']['name']}")
        print(f"  版本: {config['project']['version']}")
        print(f"  Python 要求: {config['project']['requires-python']}")
        
        # 检查依赖
        deps = config['project']['dependencies']
        print(f"  核心依赖数量: {len(deps)}")
        
        # 检查开发依赖
        if 'dev' in config['project']['optional-dependencies']:
            dev_deps = config['project']['optional-dependencies']['dev']
            print(f"  开发依赖数量: {len(dev_deps)}")
        
        print("\n✅ pyproject.toml 验证通过")

    except Exception as e:
        print(f"❌ pyproject.toml 验证失败: {e}")
        import traceback
        traceback.print_exc()
        pytest.fail(f"pyproject.toml 验证失败: {e}")

def test_compatibility():
    """测试与现有系统的兼容性"""
    print("\n=== 测试与现有系统兼容性 ===")
    
    try:
        # 检查现有 requirements.txt
        if os.path.exists("requirements.txt"):
            with open("requirements.txt", "r") as f:
                requirements = f.read()
            print(f"✓ requirements.txt 存在 ({len(requirements.splitlines())} 行)")
        
        # 检查现有配置文件
        if os.path.exists("app/config.py"):
            print("✓ 现有 config.py 存在")
            
            # 尝试导入现有配置
            import importlib.util
            config_path = os.path.join(project_root, "app/config.py")
            spec = importlib.util.spec_from_file_location("config", config_path)
            config_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(config_module)
            print("✓ 现有 config.py 可以正常导入")
        
        # 检查现有 agent 文件
        agent_files = [f for f in os.listdir(".") if f.startswith("v") and f.endswith("_agent.py")]
        if agent_files:
            print(f"✓ 找到 {len(agent_files)} 个 agent 版本文件")
            for f in agent_files[:3]:  # 显示前3个
                print(f"  - {f}")
        
        print("\n✅ 兼容性测试通过")

    except Exception as e:
        print(f"❌ 兼容性测试失败: {e}")
        import traceback
        traceback.print_exc()
        pytest.fail(f"兼容性测试失败: {e}")

def main():
    """主测试函数"""
    print("🔧 新模块验证测试")
    print("=" * 50)
    
    tests = [
        ("exceptions 模块", test_exceptions_module),
        ("monitoring 模块", test_monitoring_module),
        ("pyproject.toml", test_pyproject_toml),
        ("兼容性", test_compatibility),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"❌ {test_name} 测试异常: {e}")
            results.append((test_name, False))
    
    # 汇总结果
    print("\n" + "=" * 50)
    print("📊 测试结果汇总")
    print("=" * 50)
    
    passed = 0
    total = len(results)
    
    for test_name, success in results:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"{test_name:20} {status}")
        if success:
            passed += 1
    
    print(f"\n总测试: {total}, 通过: {passed}, 失败: {total - passed}")
    
    if passed == total:
        print("\n🎉 所有测试通过！新模块可以安全使用。")
        return 0
    else:
        print(f"\n⚠️  {total - passed} 个测试失败，请检查问题。")
        return 1

if __name__ == "__main__":
    sys.exit(main())