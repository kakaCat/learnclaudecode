"""
LLM Insight - 使用 LLM 分析 AI 调用质量

分析内容：
1. LLM 的决策是否合理
2. 工具选择是否正确
3. 提示词是否可以优化
4. 响应质量是否良好
5. 是否有冗余或无效的调用
"""

import json
from pathlib import Path
from collections import defaultdict


def analyze_llm_quality(trace_file: Path, llm):
    """使用 LLM 分析调用质量"""

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
        print("   提示: 先执行一些命令，然后再运行 /insight-llm 分析")
        return

    # 解析运行数据
    runs = defaultdict(dict)
    for event in events:
        run_id = event.get('run_id')
        event_type = event.get('event')

        if event_type == 'run.start':
            runs[run_id]['start'] = event
            runs[run_id]['tools'] = []
            runs[run_id]['llm_calls'] = []

        elif event_type == 'run.end':
            runs[run_id]['end'] = event

        elif event_type == 'tool.result':
            if run_id in runs:
                runs[run_id]['tools'].append(event)

        elif event_type == 'llm.fallback':
            if run_id in runs:
                runs[run_id]['llm_calls'].append(event)

    print("=" * 80)
    print("🧠 LLM 调用质量分析")
    print("=" * 80)
    print()

    # 分析每个运行
    for i, (run_id, run_data) in enumerate(runs.items(), 1):
        start = run_data.get('start', {})
        end = run_data.get('end', {})
        tools = run_data.get('tools', [])
        llm_calls = run_data.get('llm_calls', [])

        prompt = start.get('prompt', 'N/A')
        output = end.get('output', 'N/A')
        duration = end.get('duration_ms', 0)
        total_tools = end.get('total_tools', 0)

        print(f"📋 运行 {i}/{len(runs)} (ID: {run_id})")
        print(f"   耗时: {duration/1000:.2f}s | 工具调用: {total_tools}")
        print()

        # 构建分析提示
        analysis_prompt = f"""
请分析以下 AI Agent 的运行过程，评估调用质量并提供优化建议：

## 用户输入
{prompt}

## 工具调用情况
调用了 {total_tools} 个工具：
{_format_tools(tools)}

## LLM 响应
{output[:500]}{'...' if len(output) > 500 else ''}

## 性能数据
- 总耗时: {duration/1000:.2f}s
- LLM 调用次数: {len(llm_calls)}

请从以下角度分析：

1. **决策质量**: LLM 的工具选择是否合理？是否有更好的方案？
2. **效率**: 是否有冗余或无效的工具调用？
3. **响应质量**: LLM 的回答是否准确、完整、有帮助？
4. **提示词优化**: 用户的提示词是否可以改进以获得更好的结果？
5. **优化建议**: 具体的改进措施

请用简洁的中文回答，每个方面 2-3 句话即可。
"""

        # 调用 LLM 分析
        print("   🤔 分析中...")
        try:
            from langchain_core.messages import HumanMessage
            response = llm.invoke([HumanMessage(content=analysis_prompt)])
            analysis = response.content

            print("   " + "─" * 76)
            # 格式化输出
            for line in analysis.split('\n'):
                if line.strip():
                    print(f"   {line}")
            print("   " + "─" * 76)
            print()

        except Exception as e:
            print(f"   ❌ 分析失败: {e}")
            print()

    # 总体建议
    print("=" * 80)
    print("💡 总体优化建议")
    print("=" * 80)
    print()

    summary_prompt = f"""
基于以下 {len(runs)} 次 AI Agent 运行的统计数据，提供总体优化建议：

## 统计数据
- 总运行次数: {len(runs)}
- 平均耗时: {sum(r.get('end', {}).get('duration_ms', 0) for r in runs.values()) / len(runs) / 1000:.2f}s
- 总工具调用: {sum(r.get('end', {}).get('total_tools', 0) for r in runs.values())}
- 平均工具调用: {sum(r.get('end', {}).get('total_tools', 0) for r in runs.values()) / len(runs):.1f}

## 常见模式
{_analyze_patterns(runs)}

请提供 3-5 条具体的优化建议，帮助改进整体的 Agent 使用效率和质量。
"""

    try:
        from langchain_core.messages import HumanMessage
        response = llm.invoke([HumanMessage(content=summary_prompt)])
        suggestions = response.content

        for line in suggestions.split('\n'):
            if line.strip():
                print(f"  {line}")
        print()

    except Exception as e:
        print(f"❌ 生成总体建议失败: {e}")
        print()


def _format_tools(tools):
    """格式化工具调用信息"""
    if not tools:
        return "无工具调用"

    tool_list = []
    for tool in tools:
        tool_name = tool.get('tool', 'Unknown')
        ok = tool.get('ok', False)
        status = "✅" if ok else "❌"
        tool_list.append(f"  - {status} {tool_name}")

    return '\n'.join(tool_list[:5])  # 最多显示 5 个


def _analyze_patterns(runs):
    """分析常见模式"""
    patterns = []

    # 统计工具使用
    tool_counts = defaultdict(int)
    for run_data in runs.values():
        for tool in run_data.get('tools', []):
            tool_counts[tool.get('tool', 'Unknown')] += 1

    if tool_counts:
        top_tools = sorted(tool_counts.items(), key=lambda x: x[1], reverse=True)[:3]
        patterns.append(f"最常用工具: {', '.join(f'{t}({c}次)' for t, c in top_tools)}")

    # 统计无工具调用的运行
    no_tool_runs = sum(1 for r in runs.values() if r.get('end', {}).get('total_tools', 0) == 0)
    if no_tool_runs > 0:
        patterns.append(f"无工具调用的运行: {no_tool_runs}/{len(runs)}")

    return '\n'.join(patterns) if patterns else "无明显模式"
