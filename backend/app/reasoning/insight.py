"""
Trace Insight - 集成到 main 的分析功能

在 REPL 中使用 /insight 命令分析当前 session 的性能
"""

import json
from pathlib import Path
from collections import defaultdict


def analyze_trace(trace_file: Path):
    """分析 trace 文件并打印报告"""

    # 加载事件
    events = []
    try:
        with open(trace_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    events.append(json.loads(line))
    except Exception as e:
        print(f"❌ 加载 trace 文件失败: {e}")
        return

    if not events:
        print("⚠️  Trace 文件为空，还没有记录任何事件")
        print("   提示: 先执行一些命令，然后再运行 /insight 分析性能")
        return

    # 解析数据
    runs = defaultdict(dict)
    subagents = defaultdict(dict)

    for event in events:
        run_id = event.get('run_id')
        event_type = event.get('event')

        if event_type == 'run.start':
            runs[run_id]['start'] = event
            runs[run_id]['tools'] = []
            runs[run_id]['subagents'] = []
            runs[run_id]['llm_calls'] = []

        elif event_type == 'run.end':
            runs[run_id]['end'] = event

        elif event_type == 'tool.result':
            if run_id in runs:
                runs[run_id]['tools'].append(event)

        elif event_type == 'llm.fallback':
            if run_id in runs:
                runs[run_id]['llm_calls'].append(event)

        elif event_type == 'subagent.start':
            span_id = event.get('span_id')
            subagents[span_id] = {
                'start': event,
                'run_id': run_id,
                'end': None
            }
            if run_id in runs:
                runs[run_id]['subagents'].append(span_id)

        elif event_type == 'subagent.end':
            span_id = event.get('span_id')
            if span_id in subagents:
                subagents[span_id]['end'] = event

    # 打印报告
    print("=" * 80)
    print("🔍 Session Trace Insight")
    print("=" * 80)

    # 摘要
    total_duration = sum(
        run_data.get('end', {}).get('duration_ms', 0)
        for run_data in runs.values()
    )
    total_tools = sum(
        run_data.get('end', {}).get('total_tools', 0)
        for run_data in runs.values()
    )

    print(f"\n📊 摘要")
    print(f"  运行次数: {len(runs)}")
    print(f"  总耗时: {total_duration/1000:.2f}s")
    print(f"  工具调用: {total_tools}")
    print(f"  子 Agent: {len(subagents)}")

    # 性能分析
    print(f"\n⚡ 性能分析")

    # 找出最慢的运行
    slow_runs = []
    for run_id, run_data in runs.items():
        end = run_data.get('end', {})
        duration = end.get('duration_ms', 0)
        if duration > 0:
            start = run_data.get('start', {})
            slow_runs.append((run_id, duration, start.get('prompt', 'N/A')))

    slow_runs.sort(key=lambda x: x[1], reverse=True)

    if slow_runs:
        print("  最慢的运行:")
        for run_id, duration, prompt in slow_runs[:3]:
            print(f"    • {run_id}: {duration/1000:.2f}s - {prompt[:50]}...")

    # 瓶颈分析
    print(f"\n🔥 瓶颈分析")

    for run_id, run_data in list(runs.items())[:3]:  # 只分析前3个
        start = run_data.get('start', {})
        end = run_data.get('end', {})
        duration = end.get('duration_ms', 0)

        if duration == 0:
            continue

        # 计算时间分布
        subagent_time = 0
        for span_id in run_data.get('subagents', []):
            sub_data = subagents.get(span_id, {})
            end_event = sub_data.get('end', {})
            subagent_time += end_event.get('duration_ms', 0) if end_event else 0

        llm_time = sum(
            llm.get('duration_ms', 0)
            for llm in run_data.get('llm_calls', [])
        )

        other_time = duration - subagent_time - llm_time

        print(f"  Run {run_id} ({duration/1000:.2f}s):")
        print(f"    提示: {start.get('prompt', 'N/A')[:60]}...")
        print(f"    子 Agent: {subagent_time/1000:.2f}s ({subagent_time/duration*100:.1f}%)")
        print(f"    LLM 调用: {llm_time/1000:.2f}s ({llm_time/duration*100:.1f}%)")
        print(f"    其他: {other_time/1000:.2f}s ({other_time/duration*100:.1f}%)")

    # 工具统计
    print(f"\n🔧 工具使用")

    tool_stats = defaultdict(lambda: {'count': 0, 'success': 0, 'fail': 0})
    for run_data in runs.values():
        for tool_event in run_data.get('tools', []):
            tool_name = tool_event.get('tool', 'Unknown')
            ok = tool_event.get('ok', False)
            tool_stats[tool_name]['count'] += 1
            if ok:
                tool_stats[tool_name]['success'] += 1
            else:
                tool_stats[tool_name]['fail'] += 1

    if tool_stats:
        for tool_name, stats in sorted(tool_stats.items(), key=lambda x: x[1]['count'], reverse=True):
            success_rate = (stats['success'] / stats['count'] * 100) if stats['count'] > 0 else 0
            status = "✅" if success_rate == 100 else "⚠️" if success_rate >= 50 else "❌"
            print(f"  {status} {tool_name}: {stats['count']} 次 ({success_rate:.0f}% 成功)")

    # 优化建议
    print(f"\n💡 优化建议")

    suggestions = []

    # 检查慢运行
    for run_id, duration, prompt in slow_runs:
        if duration > 60000:  # 超过 1 分钟
            suggestions.append(
                f"🔴 运行 {run_id} 耗时过长 ({duration/1000:.2f}s)\n"
                f"     建议: 考虑并行化、缓存或优化提示词"
            )

    # 检查无效运行
    for run_id, run_data in runs.items():
        end = run_data.get('end', {})
        total_tools = end.get('total_tools', 0)
        duration = end.get('duration_ms', 0)

        if total_tools == 0 and duration > 5000:
            suggestions.append(
                f"🟡 运行 {run_id} 无工具调用但耗时 {duration/1000:.2f}s\n"
                f"     建议: 检查是否可以直接回答或需要添加工具"
            )

    # 检查工具失败率
    for tool_name, stats in tool_stats.items():
        if stats['count'] > 0:
            fail_rate = (stats['fail'] / stats['count'] * 100)
            if fail_rate > 50:
                suggestions.append(
                    f"🟡 工具 {tool_name} 失败率过高 ({fail_rate:.0f}%)\n"
                    f"     建议: 检查工具实现或添加重试机制"
                )

    if suggestions:
        for i, suggestion in enumerate(suggestions[:5], 1):  # 最多显示 5 条
            print(f"  {i}. {suggestion}")
    else:
        print("  ✅ 未发现明显问题，运行良好！")

    print()
