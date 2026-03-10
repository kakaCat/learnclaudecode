#!/usr/bin/env python3
"""
简化版自我修复 Agent 示例

演示如何让 Agent 分析失败、诊断问题并实施修复
"""

import json
import sys
from pathlib import Path
from collections import Counter

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class SimpleHealingAgent:
    """简化版自我修复 Agent"""

    def analyze_trace(self, trace_file: str) -> dict:
        """
        分析 trace 文件，识别失败模式

        Returns:
            {
                "summary": {...},
                "failures": [...],
                "patterns": {...},
                "suggestions": [...]
            }
        """
        print(f"📖 读取 trace 文件: {trace_file}")

        # 读取所有事件
        events = []
        with open(trace_file) as f:
            for line in f:
                try:
                    events.append(json.loads(line))
                except:
                    continue

        # 统计信息
        summary = self._compute_summary(events)
        print(f"\n📊 执行统计:")
        print(f"  - 总轮次: {summary['total_turns']}")
        print(f"  - 工具调用: {summary['total_tool_calls']}")
        print(f"  - 失败次数: {summary['failed_calls']}")
        print(f"  - 运行时长: {summary['duration_sec']:.1f}s")

        # 识别失败
        failures = self._identify_failures(events)
        print(f"\n❌ 失败事件: {len(failures)} 个")

        # 识别模式
        patterns = self._identify_patterns(failures)
        print(f"\n🔍 失败模式:")
        for pattern_type, count in patterns.items():
            print(f"  - {pattern_type}: {count} 次")

        # 生成建议
        suggestions = self._generate_suggestions(patterns, events)
        print(f"\n💡 改进建议:")
        for i, suggestion in enumerate(suggestions, 1):
            print(f"  {i}. {suggestion}")

        return {
            "summary": summary,
            "failures": failures,
            "patterns": patterns,
            "suggestions": suggestions
        }

    def _compute_summary(self, events: list) -> dict:
        """计算统计信息"""
        turns = [e for e in events if e.get("event") == "llm.turn"]
        tool_calls = [e for e in events if e.get("event") == "tool.call"]
        tool_results = [e for e in events if e.get("event") == "tool.result"]

        failed_calls = sum(1 for r in tool_results if not r.get("ok", True))

        start_time = events[0]["ts"] if events else 0
        end_time = events[-1]["ts"] if events else 0

        return {
            "total_turns": len(turns),
            "total_tool_calls": len(tool_calls),
            "failed_calls": failed_calls,
            "duration_sec": end_time - start_time
        }

    def _identify_failures(self, events: list) -> list:
        """识别失败的工具调用"""
        failures = []

        for event in events:
            if event.get("event") == "tool.result":
                output = event.get("output", "")
                ok = event.get("ok", True)

                # 检查是否失败
                if not ok or any(err in output for err in ["Error:", "❌", "SyntaxError", "not found"]):
                    failures.append({
                        "turn": event.get("turn"),
                        "tool": event.get("tool"),
                        "output": output[:200],  # 截断
                        "timestamp": event.get("ts")
                    })

        return failures

    def _identify_patterns(self, failures: list) -> dict:
        """识别失败模式"""
        patterns = Counter()

        for failure in failures:
            output = failure["output"]

            # JavaScript 错误
            if "SyntaxError" in output:
                if "Illegal return" in output:
                    patterns["javascript_illegal_return"] += 1
                elif "already been declared" in output:
                    patterns["javascript_redeclaration"] += 1
                else:
                    patterns["javascript_other"] += 1

            # 元素未找到
            elif "not found" in output or "❌ Element" in output:
                patterns["element_not_found"] += 1

            # 超时
            elif "timeout" in output.lower():
                patterns["timeout"] += 1

            # 其他错误
            else:
                patterns["other_error"] += 1

        return dict(patterns)

    def _generate_suggestions(self, patterns: dict, events: list) -> list:
        """生成改进建议"""
        suggestions = []

        # JavaScript 错误建议
        if patterns.get("javascript_illegal_return", 0) > 0:
            suggestions.append(
                "修改 cdp_tool.py 的 execute 动作，使用 IIFE 包装 JavaScript 代码"
            )
            suggestions.append(
                "添加 eval 动作用于执行表达式（不需要 return）"
            )

        if patterns.get("javascript_redeclaration", 0) > 0:
            suggestions.append(
                "避免在全局作用域重复声明变量，使用 let/const 或函数作用域"
            )

        # 元素未找到建议
        if patterns.get("element_not_found", 0) > 3:
            suggestions.append(
                "在 MEMORY.md 中添加策略：优先使用 URL 构造而非表单交互"
            )
            suggestions.append(
                "增加 wait_for 的超时时间（10-20s）"
            )

        # 重复失败建议
        tool_calls = [e for e in events if e.get("event") == "tool.call"]
        if len(tool_calls) > 20:
            suggestions.append(
                "添加失败重试策略：3 次失败后切换方法，5 次失败后承认任务失败"
            )

        # 通用建议
        if not suggestions:
            suggestions.append("需要人工分析具体失败原因")

        return suggestions

    def generate_fix_plan(self, analysis: dict) -> list:
        """
        根据分析结果生成修复计划

        Returns:
            [
                {"task": "...", "file": "...", "priority": "high"},
                ...
            ]
        """
        plan = []
        patterns = analysis["patterns"]

        # JavaScript 错误修复
        if patterns.get("javascript_illegal_return", 0) > 0:
            plan.append({
                "task": "修改 cdp_tool.py 添加 IIFE 包装",
                "file": "backend/app/tools/implementations/cdp_tool.py",
                "priority": "high",
                "description": "在 execute 动作中自动包装 JavaScript 为 IIFE"
            })
            plan.append({
                "task": "添加 eval 动作",
                "file": "backend/app/tools/implementations/cdp_tool.py",
                "priority": "high",
                "description": "新增 eval 动作用于表达式求值"
            })

        # 策略优化
        if patterns.get("element_not_found", 0) > 3:
            plan.append({
                "task": "更新 MEMORY.md 添加 URL 构造策略",
                "file": ".memory/MEMORY.md",
                "priority": "medium",
                "description": "添加机票查询 URL 模板和策略优先级"
            })

        # 测试验证
        if plan:
            plan.append({
                "task": "创建测试脚本验证修复效果",
                "file": "scripts/test_cdp_improvements.py",
                "priority": "medium",
                "description": "测试 JavaScript 执行和 URL 构造"
            })

        return plan


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法: python scripts/simple_healing_agent.py <trace_file>")
        print("示例: python scripts/simple_healing_agent.py .sessions/20260310_015346/trace.jsonl")
        return

    trace_file = sys.argv[1]

    if not Path(trace_file).exists():
        print(f"❌ 文件不存在: {trace_file}")
        return

    print("=" * 60)
    print("🔧 简化版自我修复 Agent")
    print("=" * 60)
    print()

    # 创建 Agent
    agent = SimpleHealingAgent()

    # 分析失败
    analysis = agent.analyze_trace(trace_file)

    # 生成修复计划
    print("\n" + "=" * 60)
    print("📋 修复计划")
    print("=" * 60)
    plan = agent.generate_fix_plan(analysis)

    if not plan:
        print("✅ 未发现需要修复的问题")
    else:
        for i, task in enumerate(plan, 1):
            print(f"\n{i}. [{task['priority'].upper()}] {task['task']}")
            print(f"   文件: {task['file']}")
            print(f"   说明: {task['description']}")

    print("\n" + "=" * 60)
    print("分析完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
