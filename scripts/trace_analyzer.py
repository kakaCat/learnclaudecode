#!/usr/bin/env python3
"""
Trace Analyzer - 类似 Claude Code Insight 的分析工具

分析 trace.jsonl 文件，提供：
1. 性能分析：耗时统计、瓶颈识别
2. 调用链路：可视化调用关系
3. 优化建议：识别可优化的点
4. 统计报告：工具使用、成功率等
"""

import json
import sys
from pathlib import Path
from typing import Any
from datetime import datetime
from collections import defaultdict


class TraceAnalyzer:
    """Trace 分析器"""

    def __init__(self, trace_file: Path):
        self.trace_file = trace_file
        self.events = []
        self.runs = defaultdict(dict)
        self.subagents = defaultdict(dict)

    def load(self):
        """加载 trace 文件"""
        with open(self.trace_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    event = json.loads(line)
                    self.events.append(event)
        print(f"✅ 加载了 {len(self.events)} 个事件\n")

    def analyze(self):
        """执行完整分析"""
        self._parse_events()

        print("=" * 80)
        print("📊 Trace 分析报告")
        print("=" * 80)
        print()

        self._print_overview()
        self._print_performance_analysis()
        self._print_tool_usage()
        self._print_subagent_analysis()
        self._print_optimization_suggestions()

    def _parse_events(self):
        """解析事件，构建运行和子 agent 的数据结构"""
        for event in self.events:
            run_id = event.get('run_id')
            event_type = event.get('event')

            if event_type == 'run.start':
                self.runs[run_id]['start'] = event
                self.runs[run_id]['tools'] = []
                self.runs[run_id]['subagents'] = []

            elif event_type == 'run.end':
                self.runs[run_id]['end'] = event

            elif event_type == 'tool.result':
                if run_id in self.runs:
                    self.runs[run_id]['tools'].append(event)

            elif event_type == 'subagent.start':
                span_id = event.get('span_id')
                self.subagents[span_id]['start'] = event
                self.subagents[span_id]['run_id'] = run_id
                if run_id in self.runs:
                    self.runs[run_id]['subagents'].append(span_id)

            elif event_type == 'subagent.end':
                span_id = event.get('span_id')
                self.subagents[span_id]['end'] = event

    def _print_overview(self):
        """打印概览"""
        print("📋 概览")
        print("-" * 80)
        print(f"总运行次数: {len(self.runs)}")
        print(f"总事件数: {len(self.events)}")
        print(f"子 Agent 调用: {len(self.subagents)}")
        print()

        # 运行详情
        for run_id, run_data in self.runs.items():
            start = run_data.get('start', {})
            end = run_data.get('end', {})

            prompt = start.get('prompt', 'N/A')
            duration = end.get('duration_ms', 0)
            turns = end.get('turns', 0)
            total_tools = end.get('total_tools', 0)

            print(f"  Run {run_id}:")
            print(f"    提示: {prompt[:60]}...")
            print(f"    耗时: {duration}ms ({duration/1000:.2f}s)")
            print(f"    轮次: {turns}")
            print(f"    工具调用: {total_tools}")
            print()

    def _print_performance_analysis(self):
        """打印性能分析"""
        print("⚡ 性能分析")
        print("-" * 80)

        # 统计每个 run 的耗时
        durations = []
        for run_id, run_data in self.runs.items():
            end = run_data.get('end', {})
            duration = end.get('duration_ms', 0)
            if duration > 0:
                durations.append((run_id, duration))

        if durations:
            durations.sort(key=lambda x: x[1], reverse=True)

            print("最慢的运行:")
            for run_id, duration in durations[:3]:
                start = self.runs[run_id].get('start', {})
                prompt = start.get('prompt', 'N/A')
                print(f"  {run_id}: {duration}ms ({duration/1000:.2f}s) - {prompt[:50]}...")
            print()

        # 子 agent 耗时分析
        subagent_durations = []
        for span_id, sub_data in self.subagents.items():
            end = sub_data.get('end', {})
            start = sub_data.get('start', {})
            duration = end.get('duration_ms', 0)
            agent_type = start.get('agent_type', 'Unknown')
            if duration > 0:
                subagent_durations.append((agent_type, duration))

        if subagent_durations:
            print("子 Agent 耗时:")
            agent_times = defaultdict(list)
            for agent_type, duration in subagent_durations:
                agent_times[agent_type].append(duration)

            for agent_type, times in agent_times.items():
                avg_time = sum(times) / len(times)
                total_time = sum(times)
                print(f"  {agent_type}:")
                print(f"    调用次数: {len(times)}")
                print(f"    平均耗时: {avg_time:.0f}ms ({avg_time/1000:.2f}s)")
                print(f"    总耗时: {total_time:.0f}ms ({total_time/1000:.2f}s)")
            print()

    def _print_tool_usage(self):
        """打印工具使用统计"""
        print("🔧 工具使用统计")
        print("-" * 80)

        tool_stats = defaultdict(lambda: {'count': 0, 'success': 0, 'fail': 0})

        for run_id, run_data in self.runs.items():
            for tool_event in run_data.get('tools', []):
                tool_name = tool_event.get('tool', 'Unknown')
                ok = tool_event.get('ok', False)

                tool_stats[tool_name]['count'] += 1
                if ok:
                    tool_stats[tool_name]['success'] += 1
                else:
                    tool_stats[tool_name]['fail'] += 1

        if tool_stats:
            print("工具调用统计:")
            for tool_name, stats in sorted(tool_stats.items(), key=lambda x: x[1]['count'], reverse=True):
                success_rate = (stats['success'] / stats['count'] * 100) if stats['count'] > 0 else 0
                print(f"  {tool_name}:")
                print(f"    调用次数: {stats['count']}")
                print(f"    成功: {stats['success']}, 失败: {stats['fail']}")
                print(f"    成功率: {success_rate:.1f}%")
            print()

    def _print_subagent_analysis(self):
        """打印子 Agent 分析"""
        print("🤖 子 Agent 分析")
        print("-" * 80)

        if not self.subagents:
            print("  无子 Agent 调用")
            print()
            return

        for span_id, sub_data in self.subagents.items():
            start = sub_data.get('start', {})
            end = sub_data.get('end', {})

            agent_type = start.get('agent_type', 'Unknown')
            description = start.get('description', 'N/A')
            duration = end.get('duration_ms', 0)
            tool_count = end.get('tool_count', 0)
            output_preview = end.get('output', '')[:100]

            print(f"  {agent_type} ({span_id}):")
            print(f"    描述: {description}")
            print(f"    耗时: {duration}ms ({duration/1000:.2f}s)")
            print(f"    工具调用: {tool_count}")
            print(f"    输出预览: {output_preview}...")
            print()

    def _print_optimization_suggestions(self):
        """打印优化建议"""
        print("💡 优化建议")
        print("-" * 80)

        suggestions = []

        # 1. 检查慢运行
        for run_id, run_data in self.runs.items():
            end = run_data.get('end', {})
            duration = end.get('duration_ms', 0)
            if duration > 30000:  # 超过 30 秒
                start = run_data.get('start', {})
                prompt = start.get('prompt', 'N/A')
                suggestions.append(
                    f"⚠️  运行 {run_id} 耗时过长 ({duration/1000:.2f}s)\n"
                    f"   提示: {prompt[:60]}...\n"
                    f"   建议: 考虑拆分任务或优化子 Agent 调用"
                )

        # 2. 检查工具失败率
        tool_stats = defaultdict(lambda: {'count': 0, 'success': 0, 'fail': 0})
        for run_id, run_data in self.runs.items():
            for tool_event in run_data.get('tools', []):
                tool_name = tool_event.get('tool', 'Unknown')
                ok = tool_event.get('ok', False)
                tool_stats[tool_name]['count'] += 1
                if ok:
                    tool_stats[tool_name]['success'] += 1
                else:
                    tool_stats[tool_name]['fail'] += 1

        for tool_name, stats in tool_stats.items():
            if stats['count'] > 0:
                fail_rate = (stats['fail'] / stats['count'] * 100)
                if fail_rate > 50:  # 失败率超过 50%
                    suggestions.append(
                        f"⚠️  工具 {tool_name} 失败率过高 ({fail_rate:.1f}%)\n"
                        f"   调用次数: {stats['count']}, 失败: {stats['fail']}\n"
                        f"   建议: 检查工具实现或添加重试机制"
                    )

        # 3. 检查子 Agent 效率
        agent_times = defaultdict(list)
        for span_id, sub_data in self.subagents.items():
            start = sub_data.get('start', {})
            end = sub_data.get('end', {})
            agent_type = start.get('agent_type', 'Unknown')
            duration = end.get('duration_ms', 0)
            tool_count = end.get('tool_count', 0)
            if duration > 0:
                agent_times[agent_type].append((duration, tool_count))

        for agent_type, times in agent_times.items():
            avg_time = sum(t[0] for t in times) / len(times)
            avg_tools = sum(t[1] for t in times) / len(times)
            if avg_time > 10000:  # 平均超过 10 秒
                suggestions.append(
                    f"⚠️  子 Agent {agent_type} 平均耗时过长 ({avg_time/1000:.2f}s)\n"
                    f"   平均工具调用: {avg_tools:.1f}\n"
                    f"   建议: 优化 Agent 逻辑或减少工具调用"
                )

        # 4. 检查无效运行（没有工具调用）
        for run_id, run_data in self.runs.items():
            end = run_data.get('end', {})
            total_tools = end.get('total_tools', 0)
            duration = end.get('duration_ms', 0)
            if total_tools == 0 and duration > 5000:
                start = run_data.get('start', {})
                prompt = start.get('prompt', 'N/A')
                suggestions.append(
                    f"⚠️  运行 {run_id} 没有工具调用但耗时 {duration/1000:.2f}s\n"
                    f"   提示: {prompt[:60]}...\n"
                    f"   建议: 检查是否需要添加工具或优化提示"
                )

        if suggestions:
            for i, suggestion in enumerate(suggestions, 1):
                print(f"{i}. {suggestion}")
                print()
        else:
            print("✅ 未发现明显的优化点，运行效率良好！")
            print()


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法: python trace_analyzer.py <trace.jsonl>")
        print("示例: python trace_analyzer.py .sessions/20260301_214209/trace.jsonl")
        sys.exit(1)

    trace_file = Path(sys.argv[1])

    if not trace_file.exists():
        print(f"❌ 文件不存在: {trace_file}")
        sys.exit(1)

    analyzer = TraceAnalyzer(trace_file)
    analyzer.load()
    analyzer.analyze()


if __name__ == "__main__":
    main()
