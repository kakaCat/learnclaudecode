"""
意图识别和反思分析模块

功能：
1. 分析 LLM 是否回答了用户的问题（目标对齐）
2. 分析决策链路是否最优（最优路径）
3. 分析导致问题的根本原因（根因分析）
"""

from typing import List, Dict, Any
from backend.app.analysis.thinking_chain import ThinkingChain


def analyze_goal_alignment(chain: ThinkingChain) -> Dict[str, Any]:
    """分析目标对齐：LLM 是否回答了用户的问题"""

    output_length = len(chain.final_output)
    has_data = any('✅' in str(r.get('output', '')) for s in chain.steps for r in s.tool_results)

    issues = []

    # 检查1: 输出是否为空或过短
    if output_length < 50:
        issues.append("🔴 输出过短，可能未充分回答问题")

    # 检查2: 是否有工具成功返回数据
    if not has_data and chain.total_tools > 0:
        issues.append("🟡 工具调用未返回有效数据")

    # 检查3: 是否有过多失败
    failed_count = sum(1 for s in chain.steps for r in s.tool_results if not r['ok'])
    if failed_count > chain.total_tools / 2:
        issues.append(f"🔴 超过一半的工具调用失败 ({failed_count}/{chain.total_tools})")

    return {
        'aligned': len(issues) == 0,
        'issues': issues,
        'output_length': output_length,
        'has_data': has_data,
        'failed_ratio': failed_count / chain.total_tools if chain.total_tools > 0 else 0
    }


def analyze_optimal_path(chain: ThinkingChain) -> Dict[str, Any]:
    """分析最优路径：决策链路是否最优"""

    inefficiencies = []

    # 分析1: 重复调用
    tool_calls = {}
    for step in chain.steps:
        for tc in step.tool_calls:
            key = (tc.get('name'), str(tc.get('args')))
            if key in tool_calls:
                inefficiencies.append({
                    'type': 'duplicate',
                    'tool': tc.get('name'),
                    'turns': [tool_calls[key], step.turn]
                })
            tool_calls[key] = step.turn

    # 分析2: 失败后的重试模式
    failed_tools = []
    for step in chain.steps:
        for result in step.tool_results:
            if not result['ok']:
                failed_tools.append((result['tool'], step.turn))

    for i in range(len(failed_tools) - 1):
        if failed_tools[i][0] == failed_tools[i+1][0]:
            inefficiencies.append({
                'type': 'consecutive_failure',
                'tool': failed_tools[i][0],
                'turns': [failed_tools[i][1], failed_tools[i+1][1]]
            })

    # 分析3: 思考效率
    if chain.total_turns > 10:
        avg_tools_per_turn = chain.total_tools / chain.total_turns
        if avg_tools_per_turn < 1.5:
            inefficiencies.append({
                'type': 'low_efficiency',
                'turns': chain.total_turns,
                'tools': chain.total_tools,
                'ratio': avg_tools_per_turn
            })

    return {
        'optimal': len(inefficiencies) == 0,
        'inefficiencies': inefficiencies,
        'suggestions': _generate_path_suggestions(inefficiencies)
    }


def analyze_root_causes(chain: ThinkingChain) -> List[Dict[str, Any]]:
    """根因分析：导致问题的根本原因"""

    root_causes = []

    # 根因1: 工具失败
    failed_tools = {}
    for step in chain.steps:
        for result in step.tool_results:
            if not result['ok']:
                tool = result['tool']
                error = result.get('output', '')[:100]
                if tool not in failed_tools:
                    failed_tools[tool] = []
                failed_tools[tool].append({'turn': step.turn, 'error': error})

    if failed_tools:
        root_causes.append({
            'category': '工具失败',
            'severity': 'high',
            'details': failed_tools,
            'root_cause': '工具实现问题或参数错误',
            'solution': '检查工具实现、验证参数格式、添加错误处理'
        })

    # 根因2: 思考轮次过多
    if chain.total_turns > 10:
        if len(failed_tools) > 0:
            root_causes.append({
                'category': '思考轮次过多',
                'severity': 'medium',
                'details': f'{chain.total_turns} 轮，{len(failed_tools)} 个工具失败',
                'root_cause': '工具失败导致 LLM 需要多次重试',
                'solution': '修复工具失败问题，减少重试次数'
            })
        else:
            root_causes.append({
                'category': '思考轮次过多',
                'severity': 'medium',
                'details': f'{chain.total_turns} 轮',
                'root_cause': '提示词不够明确，LLM 无法一次性规划',
                'solution': '优化提示词，明确告诉 LLM 可以并行调用工具'
            })

    # 根因3: 运行时间过长
    if chain.total_duration_ms > 60000:
        tool_durations = []
        for step in chain.steps:
            for result in step.tool_results:
                tool_durations.append((result['tool'], result['duration_ms']))

        if tool_durations:
            slowest = max(tool_durations, key=lambda x: x[1])
            total_tool_time = sum(d for _, d in tool_durations)

            if total_tool_time > chain.total_duration_ms * 0.8:
                root_causes.append({
                    'category': '运行时间过长',
                    'severity': 'medium',
                    'details': f'{chain.total_duration_ms/1000:.2f}s，最慢: {slowest[0]} ({slowest[1]}ms)',
                    'root_cause': '工具调用耗时过长',
                    'solution': f'优化 {slowest[0]} 工具性能，或使用缓存'
                })

    # 根因4: 重复调用
    tool_calls = {}
    duplicates = []
    for step in chain.steps:
        for tc in step.tool_calls:
            key = (tc.get('name'), str(tc.get('args')))
            if key in tool_calls:
                duplicates.append(tc.get('name'))
            tool_calls[key] = step.turn

    if duplicates:
        root_causes.append({
            'category': '重复调用',
            'severity': 'low',
            'details': f'{len(duplicates)} 次重复',
            'root_cause': 'LLM 没有记住之前的工具调用结果',
            'solution': '在提示词中强调"使用已有数据"，或实现工具结果缓存'
        })

    return root_causes


def _generate_path_suggestions(inefficiencies: List[Dict]) -> List[str]:
    """生成路径优化建议"""
    suggestions = []

    has_duplicate = any(i['type'] == 'duplicate' for i in inefficiencies)
    has_failure = any(i['type'] == 'consecutive_failure' for i in inefficiencies)
    has_low_efficiency = any(i['type'] == 'low_efficiency' for i in inefficiencies)

    if has_duplicate:
        suggestions.append("缓存重复调用的结果")
    if has_failure:
        suggestions.append("添加工具调用重试机制")
    if has_low_efficiency:
        suggestions.append("优化提示词，让 LLM 一次性规划多个工具")
        suggestions.append("使用并行工具调用减少轮次")

    return suggestions


def print_goal_alignment(chain: ThinkingChain):
    """打印目标对齐分析"""
    print("=" * 100)
    print("🎯 目标对齐分析")
    print("=" * 100)
    print()

    print(f"📝 用户问题: {chain.user_prompt}")
    print()

    result = analyze_goal_alignment(chain)

    if result['aligned']:
        print("✅ LLM 成功回答了用户的问题")
    else:
        print("⚠️  发现问题:")
        for issue in result['issues']:
            print(f"   {issue}")

    print()


def print_optimal_path(chain: ThinkingChain):
    """打印最优路径分析"""
    print("=" * 100)
    print("🛤️  最优路径分析")
    print("=" * 100)
    print()

    result = analyze_optimal_path(chain)

    if result['optimal']:
        print("✅ 决策链路较为高效")
    else:
        print("⚠️  发现低效模式:")
        for i, ineff in enumerate(result['inefficiencies'][:5], 1):
            if ineff['type'] == 'duplicate':
                print(f"   {i}. 🟡 重复调用: {ineff['tool']} (Turn {ineff['turns'][0]} 和 {ineff['turns'][1]})")
            elif ineff['type'] == 'consecutive_failure':
                print(f"   {i}. 🔴 连续失败: {ineff['tool']} (Turn {ineff['turns'][0]} → {ineff['turns'][1]})")
            elif ineff['type'] == 'low_efficiency':
                print(f"   {i}. 🟡 思考效率低: {ineff['turns']} 轮只调用了 {ineff['tools']} 个工具")

        if result['suggestions']:
            print()
            print("💡 最优路径建议:")
            for suggestion in result['suggestions']:
                print(f"   • {suggestion}")

    print()


def print_root_causes(chain: ThinkingChain):
    """打印根因分析"""
    print("=" * 100)
    print("🔍 根因分析")
    print("=" * 100)
    print()

    causes = analyze_root_causes(chain)

    if not causes:
        print("✅ 未发现明显问题")
    else:
        for i, cause in enumerate(causes, 1):
            severity_icon = '🔴' if cause['severity'] == 'high' else '🟡' if cause['severity'] == 'medium' else '🟢'
            print(f"{i}. {severity_icon} {cause['category']}")
            print(f"   现象: {cause['details']}")
            print(f"   根因: {cause['root_cause']}")
            print(f"   解决: {cause['solution']}")
            print()
