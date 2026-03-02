#!/usr/bin/env python3
"""
Trace Insight - 高级 AI 调用分析工具

提供更深入的分析：
1. 调用链路可视化（树形结构）
2. 时间线分析
3. 成本估算（基于 token 使用）
4. 并发分析
5. 交互式报告
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List
from datetime import datetime
from collections import defaultdict


class TraceInsight:
    """高级 Trace 分析器"""

    def __init__(self, trace_file: Path):
        self.trace_file = trace_file
        self.events = []
        self.runs = defaultdict(dict)
        self.subagents = defaultdict(dict)
        self.timeline = []

    def load(self):
        """加载并解析 trace 文件"""
        with open(self.trace_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    event = json.loads(line)
                    self.events.append(event)
                    self.timeline.append(event)

        # 按时间排序
        self.timeline.sort(key=lambda x: x.get('ts', 0))
        print(f"✅ 加载了 {len(self.events)} 个事件\n")

    def analyze_all(self):
        """执行完整分析"""
        self._parse_events()

        print("=" * 100)
        print("🔍 Trace Insight - AI 调用深度分析")
        print("=" * 100)
        print()

        self._print_summary()
        self._print_call_tree()
        self._print_timeline()
        self._print_bottleneck_analysis()
        self._print_efficiency_metrics()
        self._print_recommendations()

    def _parse_events(self):
        """解析事件"""
        for event in self.events:
            run_id = event.get('run_id')
            event_type = event.get('event')

            if event_type == 'run.start':
                self.runs[run_id]['start'] = event
                self.runs[run_id]['tools'] = []
                self.runs[run_id]['subagents'] = []
                self.runs[run_id]['llm_calls'] = []

            elif event_type == 'run.end':
                self.runs[run_id]['end'] = event

            elif event_type == 'tool.result':
                if run_id in self.runs:
                    self.runs[run_id]['tools'].append(event)

            elif event_type == 'llm.fallback':
                if run_id in self.runs:
                    self.runs[run_id]['llm_calls'].append(event)

            elif event_type == 'subagent.start':
                span_id = event.get('span_id')
                self.subagents[span_id] = {
                    'start': event,
                    'run_id': run_id,
                    'tools': [],
                    'end': None
                }
                if run_id in self.runs:
                    self.runs[run_id]['subagents'].append(span_id)

            elif event_type == 'subagent.end':
                span_id = event.get('span_id')
                if span_id in self.subagents:
                    self.subagents[span_id]['end'] = event

    def _print_summary(self):
        """打印摘要"""
        print("📊 执行摘要")
        print("-" * 100)

        total_duration = sum(
            run_data.get('end', {}).get('duration_ms', 0)
            for run_data in self.runs.values()
        )
        total_tools = sum(
            run_data.get('end', {}).get('total_tools', 0)
            for run_data in self.runs.values()
        )

        print(f"  总运行次数: {len(self.runs)}")
        print(f"  总耗时: {total_duration/1000:.2f}s")
        print(f"  总工具调用: {total_tools}")
        print(f"  子 Agent 调用: {len(self.subagents)}")
        print(f"  平均每次运行耗时: {total_duration/len(self.runs)/1000:.2f}s" if self.runs else "  N/A")
        print()

    def _print_call_tree(self):
        """打印调用树"""
        print("🌲 调用链路树")
        print("-" * 100)

        for run_id, run_data in self.runs.items():
            start = run_data.get('start', {})
            end = run_data.get('end', {})

            prompt = start.get('prompt', 'N/A')
            duration = end.get('duration_ms', 0)

            print(f"📍 Run {run_id} ({duration/1000:.2f}s)")
            print(f"   └─ 提示: {prompt}")

            # LLM 调用
            llm_calls = run_data.get('llm_calls', [])
            if llm_calls:
                print(f"   ├─ 🤖 LLM 调用: {len(llm_calls)} 次")
                for i, llm_call in enumerate(llm_calls):
                    llm_duration = llm_call.get('duration_ms', 0)
                    output_preview = llm_call.get('output_preview', '')[:50]
                    print(f"   │  └─ [{i+1}] {llm_duration}ms - {output_preview}...")

            # 工具调用
            tools = run_data.get('tools', [])
            if tools:
                print(f"   ├─ 🔧 工具调用: {len(tools)} 次")
                for tool in tools:
                    tool_name = tool.get('tool', 'Unknown')
                    ok = tool.get('ok', False)
                    status = "✅" if ok else "❌"
                    print(f"   │  └─ {status} {tool_name}")

            # 子 Agent
            subagent_ids = run_data.get('subagents', [])
            if subagent_ids:
                print(f"   └─ 🤖 子 Agent: {len(subagent_ids)} 个")
                for span_id in subagent_ids:
                    sub_data = self.subagents.get(span_id, {})
                    start_event = sub_data.get('start', {})
                    end_event = sub_data.get('end', {})

                    agent_type = start_event.get('agent_type', 'Unknown')
                    description = start_event.get('description', 'N/A')
                    sub_duration = end_event.get('duration_ms', 0) if end_event else 0

                    print(f"      └─ {agent_type} ({sub_duration/1000:.2f}s)")
                    print(f"         └─ {description}")

            print()

    def _print_timeline(self):
        """打印时间线"""
        print("⏱️  执行时间线")
        print("-" * 100)

        if not self.timeline:
            print("  无时间线数据")
            print()
            return

        start_ts = self.timeline[0].get('ts', 0)

        for event in self.timeline[:20]:  # 只显示前 20 个事件
            ts = event.get('ts', 0)
            event_type = event.get('event', 'unknown')
            relative_time = ts - start_ts

            # 格式化时间
            time_str = f"+{relative_time:.2f}s"

            # 根据事件类型显示不同的信息
            if event_type == 'run.start':
                prompt = event.get('prompt', 'N/A')[:40]
                print(f"  {time_str:>10} | 🚀 运行开始: {prompt}...")

            elif event_type == 'run.end':
                duration = event.get('duration_ms', 0)
                print(f"  {time_str:>10} | 🏁 运行结束 (耗时: {duration/1000:.2f}s)")

            elif event_type == 'subagent.start':
                agent_type = event.get('agent_type', 'Unknown')
                print(f"  {time_str:>10} | 🤖 子 Agent 启动: {agent_type}")

            elif event_type == 'subagent.end':
                agent_type = event.get('agent_type', 'Unknown')
                duration = event.get('duration_ms', 0)
                print(f"  {time_str:>10} | ✅ 子 Agent 完成: {agent_type} ({duration/1000:.2f}s)")

            elif event_type == 'tool.result':
                tool = event.get('tool', 'Unknown')
                ok = event.get('ok', False)
                status = "✅" if ok else "❌"
                print(f"  {time_str:>10} | 🔧 工具调用: {tool} {status}")

            elif event_type == 'llm.fallback':
                duration = event.get('duration_ms', 0)
                print(f"  {time_str:>10} | 🤖 LLM 调用 ({duration}ms)")

        if len(self.timeline) > 20:
            print(f"  ... 还有 {len(self.timeline) - 20} 个事件")

        print()

    def _print_bottleneck_analysis(self):
        """打印瓶颈分析"""
        print("🔥 性能瓶颈分析")
        print("-" * 100)

        bottlenecks = []

        # 分析每个运行
        for run_id, run_data in self.runs.items():
            start = run_data.get('start', {})
            end = run_data.get('end', {})
            duration = end.get('duration_ms', 0)

            if duration == 0:
                continue

            # 计算子 Agent 占用的时间
            subagent_time = 0
            for span_id in run_data.get('subagents', []):
                sub_data = self.subagents.get(span_id, {})
                end_event = sub_data.get('end', {})
                subagent_time += end_event.get('duration_ms', 0) if end_event else 0

            # 计算 LLM 调用时间
            llm_time = sum(
                llm.get('duration_ms', 0)
                for llm in run_data.get('llm_calls', [])
            )

            # 计算其他时间（网络、工具等）
            other_time = duration - subagent_time - llm_time

            bottlenecks.append({
                'run_id': run_id,
                'prompt': start.get('prompt', 'N/A'),
                'total': duration,
                'subagent': subagent_time,
                'llm': llm_time,
                'other': other_time
            })

        # 按总时间排序
        bottlenecks.sort(key=lambda x: x['total'], reverse=True)

        for i, item in enumerate(bottlenecks[:5], 1):
            print(f"{i}. Run {item['run_id']} - 总耗时: {item['total']/1000:.2f}s")
            print(f"   提示: {item['prompt'][:60]}...")
            print(f"   时间分布:")
            print(f"     - 子 Agent: {item['subagent']/1000:.2f}s ({item['subagent']/item['total']*100:.1f}%)")
            print(f"     - LLM 调用: {item['llm']/1000:.2f}s ({item['llm']/item['total']*100:.1f}%)")
            print(f"     - 其他: {item['other']/1000:.2f}s ({item['other']/item['total']*100:.1f}%)")
            print()

    def _print_efficiency_metrics(self):
        """打印效率指标"""
        print("📈 效率指标")
        print("-" * 100)

        # 工具成功率
        tool_success = 0
        tool_total = 0
        for run_data in self.runs.values():
            for tool in run_data.get('tools', []):
                tool_total += 1
                if tool.get('ok', False):
                    tool_success += 1

        if tool_total > 0:
            print(f"  工具调用成功率: {tool_success}/{tool_total} ({tool_success/tool_total*100:.1f}%)")

        # 平均工具调用数
        avg_tools = sum(
            run_data.get('end', {}).get('total_tools', 0)
            for run_data in self.runs.values()
        ) / len(self.runs) if self.runs else 0

        print(f"  平均每次运行工具调用数: {avg_tools:.1f}")

        # 子 Agent 效率
        if self.subagents:
            avg_subagent_time = sum(
                sub_data.get('end', {}).get('duration_ms', 0)
                for sub_data in self.subagents.values()
            ) / len(self.subagents)
            print(f"  子 Agent 平均耗时: {avg_subagent_time/1000:.2f}s")

        print()

    def _print_recommendations(self):
        """打印优化建议"""
        print("💡 优化建议")
        print("-" * 100)

        recommendations = []

        # 1. 识别慢运行
        for run_id, run_data in self.runs.items():
            end = run_data.get('end', {})
            duration = end.get('duration_ms', 0)

            if duration > 60000:  # 超过 1 分钟
                start = run_data.get('start', {})
                recommendations.append({
                    'priority': 'HIGH',
                    'category': '性能',
                    'issue': f"运行 {run_id} 耗时过长 ({duration/1000:.2f}s)",
                    'suggestion': "考虑并行化子任务、缓存结果或优化提示词"
                })

        # 2. 识别无效运行
        for run_id, run_data in self.runs.items():
            end = run_data.get('end', {})
            total_tools = end.get('total_tools', 0)
            duration = end.get('duration_ms', 0)

            if total_tools == 0 and duration > 5000:
                recommendations.append({
                    'priority': 'MEDIUM',
                    'category': '效率',
                    'issue': f"运行 {run_id} 无工具调用但耗时 {duration/1000:.2f}s",
                    'suggestion': "检查是否可以直接回答或需要添加工具支持"
                })

        # 3. 子 Agent 优化
        agent_stats = defaultdict(list)
        for sub_data in self.subagents.values():
            start = sub_data.get('start', {})
            end = sub_data.get('end', {})
            agent_type = start.get('agent_type', 'Unknown')
            duration = end.get('duration_ms', 0) if end else 0
            if duration > 0:
                agent_stats[agent_type].append(duration)

        for agent_type, durations in agent_stats.items():
            avg_duration = sum(durations) / len(durations)
            if avg_duration > 15000:  # 平均超过 15 秒
                recommendations.append({
                    'priority': 'MEDIUM',
                    'category': '子 Agent',
                    'issue': f"{agent_type} 平均耗时 {avg_duration/1000:.2f}s",
                    'suggestion': "优化 Agent 提示词或减少工具调用次数"
                })

        # 按优先级排序
        priority_order = {'HIGH': 0, 'MEDIUM': 1, 'LOW': 2}
        recommendations.sort(key=lambda x: priority_order.get(x['priority'], 3))

        if recommendations:
            for i, rec in enumerate(recommendations, 1):
                priority_icon = "🔴" if rec['priority'] == 'HIGH' else "🟡" if rec['priority'] == 'MEDIUM' else "🟢"
                print(f"{i}. {priority_icon} [{rec['category']}] {rec['issue']}")
                print(f"   💡 建议: {rec['suggestion']}")
                print()
        else:
            print("✅ 未发现明显问题，系统运行良好！")
            print()


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法: python trace_insight.py <trace.jsonl>")
        print("示例: python trace_insight.py .sessions/20260301_214209/trace.jsonl")
        sys.exit(1)

    trace_file = Path(sys.argv[1])

    if not trace_file.exists():
        print(f"❌ 文件不存在: {trace_file}")
        sys.exit(1)

    insight = TraceInsight(trace_file)
    insight.load()
    insight.analyze_all()


if __name__ == "__main__":
    main()
