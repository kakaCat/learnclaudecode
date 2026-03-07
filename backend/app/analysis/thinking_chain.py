"""
LLM 思维链可视化工具 - Thinking Chain Visualizer

核心功能：
1. 解析 trace.jsonl，提取 LLM 的每一轮思考
2. 展示 LLM 的决策过程：prompt → reasoning → tool_calls → results
3. 可视化思维链路：显示 LLM 如何一步步解决问题
4. 生成优化建议：识别冗余、低效的思考模式

使用场景：
- 调试 Agent 行为：为什么 LLM 选择了这个工具？
- 优化提示词：哪些提示导致了更好的决策？
- 性能分析：哪些环节耗时最长？
- 学习 LLM 思维：理解 LLM 如何分解复杂任务
"""

import json
from pathlib import Path
from collections import defaultdict
from typing import List, Dict, Any
from dataclasses import dataclass, field


@dataclass
class ThinkingStep:
    """单个思考步骤"""
    turn: int
    timestamp: float

    # LLM 输入
    prompt_messages: List[Dict] = field(default_factory=list)

    # LLM 输出
    response_content: str = ""
    tool_calls: List[Dict] = field(default_factory=list)

    # 工具执行结果
    tool_results: List[Dict] = field(default_factory=list)

    # 元数据
    duration_ms: int = 0
    msg_count: int = 0


@dataclass
class ThinkingChain:
    """完整的思维链"""
    run_id: str
    user_prompt: str
    final_output: str

    steps: List[ThinkingStep] = field(default_factory=list)

    total_duration_ms: int = 0
    total_turns: int = 0
    total_tools: int = 0


class ThinkingChainAnalyzer:
    """思维链分析器"""

    def __init__(self, trace_file: Path):
        self.trace_file = trace_file
        self.events = []
        self.chains: List[ThinkingChain] = []

    def load_events(self):
        """加载 trace 事件"""
        try:
            with open(self.trace_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        self.events.append(json.loads(line))
        except Exception as e:
            print(f"❌ 加载 trace 文件失败: {e}")
            return False

        if not self.events:
            print("⚠️  Trace 文件为空")
            return False

        return True

    def parse_chains(self):
        """解析思维链"""
        # 按 run_id 分组
        runs = defaultdict(list)
        for event in self.events:
            run_id = event.get('run_id')
            if run_id:
                runs[run_id].append(event)

        # 为每个 run 构建思维链
        for run_id, events in runs.items():
            chain = self._build_chain(run_id, events)
            if chain:
                self.chains.append(chain)

    def _build_chain(self, run_id: str, events: List[Dict]) -> ThinkingChain:
        """构建单个思维链"""
        chain = ThinkingChain(run_id=run_id, user_prompt="", final_output="")

        # 提取基本信息
        for event in events:
            event_type = event.get('event')

            if event_type == 'run.start':
                chain.user_prompt = event.get('prompt', '')

            elif event_type == 'run.end':
                chain.final_output = event.get('output', '')
                chain.total_duration_ms = event.get('duration_ms', 0)
                chain.total_turns = event.get('turns', 0)
                chain.total_tools = event.get('total_tools', 0)

        # 按 turn 分组事件
        turns = defaultdict(list)
        for event in events:
            turn = event.get('turn')
            if turn is not None:
                turns[turn].append(event)

        # 构建每个思考步骤
        for turn in sorted(turns.keys()):
            step = self._build_step(turn, turns[turn])
            if step:
                chain.steps.append(step)

        return chain

    def _build_step(self, turn: int, events: List[Dict]) -> ThinkingStep:
        """构建单个思考步骤"""
        step = ThinkingStep(turn=turn, timestamp=0)

        for event in events:
            event_type = event.get('event')

            if event_type == 'llm.prompt':
                step.timestamp = event.get('ts', 0)
                step.prompt_messages = event.get('messages', [])

            elif event_type == 'llm.response':
                step.response_content = event.get('content', '')
                step.tool_calls = event.get('tool_calls', [])

            elif event_type == 'tool.result':
                step.tool_results.append({
                    'tool': event.get('tool'),
                    'ok': event.get('ok'),
                    'output': event.get('output', '')[:200],  # 截断
                    'duration_ms': event.get('duration_ms', 0)
                })

            elif event_type == 'llm.turn':
                step.msg_count = event.get('msg_count', 0)
                decisions = event.get('decisions', [])
                if decisions:
                    step.duration_ms = sum(
                        d.get('duration_ms', 0) for d in decisions
                    )

        return step

    def visualize(self, chain_index: int = 0, detailed: bool = True):
        """可视化思维链"""
        if chain_index >= len(self.chains):
            print(f"❌ 链索引 {chain_index} 超出范围 (共 {len(self.chains)} 条)")
            return

        chain = self.chains[chain_index]

        print("=" * 100)
        print(f"🧠 LLM 思维链可视化 - Run {chain.run_id}")
        print("=" * 100)
        print()

        # 基本信息
        print(f"📝 用户输入: {chain.user_prompt}")
        print(f"⏱️  总耗时: {chain.total_duration_ms/1000:.2f}s")
        print(f"🔄 思考轮次: {chain.total_turns}")
        print(f"🔧 工具调用: {chain.total_tools}")
        print()

        # 展示每一轮思考
        print("🔍 思维链路:")
        print()

        for i, step in enumerate(chain.steps, 1):
            self._visualize_step(i, step, detailed)

        # 最终输出
        print("─" * 100)
        print(f"✅ 最终输出:")
        print(f"   {chain.final_output[:300]}{'...' if len(chain.final_output) > 300 else ''}")
        print()

    def _visualize_step(self, step_num: int, step: ThinkingStep, detailed: bool):
        """可视化单个思考步骤"""
        print(f"{'─' * 100}")
        print(f"🔄 第 {step_num} 轮思考 (Turn {step.turn})")
        print(f"{'─' * 100}")

        # LLM 的思考内容
        if step.response_content:
            print(f"💭 LLM 思考:")
            # 截取前200字符
            content = step.response_content[:200]
            print(f"   {content}{'...' if len(step.response_content) > 200 else ''}")
            print()

        # 工具调用决策
        if step.tool_calls:
            print(f"🎯 决策: 调用 {len(step.tool_calls)} 个工具")
            for tc in step.tool_calls:
                tool_name = tc.get('name', 'Unknown')
                args = tc.get('args', {})
                print(f"   • {tool_name}")
                if detailed and args:
                    # 显示关键参数
                    key_args = self._extract_key_args(tool_name, args)
                    if key_args:
                        print(f"     参数: {key_args}")
            print()

        # 工具执行结果
        if step.tool_results:
            print(f"📊 执行结果:")
            for result in step.tool_results:
                tool = result['tool']
                ok = result['ok']
                status = "✅" if ok else "❌"
                duration = result['duration_ms']
                print(f"   {status} {tool} ({duration}ms)")
                if detailed and not ok:
                    output = result.get('output', '')
                    if output:
                        print(f"      错误: {output[:100]}")
            print()

    def _extract_key_args(self, tool_name: str, args: Dict) -> str:
        """提取关键参数"""
        # 根据工具类型提取关键信息
        if tool_name == 'get_realtime_data':
            return f"symbol={args.get('symbol')}, source={args.get('source')}"
        elif tool_name == 'get_hist_data':
            return f"symbol={args.get('symbol')}, {args.get('start_date')} ~ {args.get('end_date')}"
        elif tool_name == 'web_search':
            return f"query={args.get('query')}"
        elif tool_name == 'TodoWrite':
            todos = args.get('items', [])
            return f"{len(todos)} 项任务"
        else:
            # 通用处理：显示前3个参数
            items = list(args.items())[:3]
            return ', '.join(f"{k}={v}" for k, v in items)

    def analyze_patterns(self):
        """分析思维模式"""
        print("=" * 100)
        print("📊 思维模式分析")
        print("=" * 100)
        print()

        if not self.chains:
            print("⚠️  没有可分析的思维链")
            return

        # 统计数据
        total_chains = len(self.chains)
        avg_turns = sum(c.total_turns for c in self.chains) / total_chains
        avg_tools = sum(c.total_tools for c in self.chains) / total_chains
        avg_duration = sum(c.total_duration_ms for c in self.chains) / total_chains / 1000

        print(f"📈 统计数据:")
        print(f"   总运行次数: {total_chains}")
        print(f"   平均思考轮次: {avg_turns:.1f}")
        print(f"   平均工具调用: {avg_tools:.1f}")
        print(f"   平均耗时: {avg_duration:.2f}s")
        print()

        # 工具使用模式
        tool_usage = defaultdict(int)
        tool_success = defaultdict(int)
        tool_fail = defaultdict(int)

        for chain in self.chains:
            for step in chain.steps:
                for result in step.tool_results:
                    tool = result['tool']
                    tool_usage[tool] += 1
                    if result['ok']:
                        tool_success[tool] += 1
                    else:
                        tool_fail[tool] += 1

        if tool_usage:
            print(f"🔧 工具使用模式:")
            for tool, count in sorted(tool_usage.items(), key=lambda x: x[1], reverse=True):
                success = tool_success[tool]
                fail = tool_fail[tool]
                success_rate = (success / count * 100) if count > 0 else 0
                status = "✅" if success_rate == 100 else "⚠️" if success_rate >= 50 else "❌"
                print(f"   {status} {tool}: {count} 次 (成功率 {success_rate:.0f}%)")
            print()

        # 识别常见模式
        print(f"🔍 常见思维模式:")
        self._identify_patterns()
        print()

    def _identify_patterns(self):
        """识别常见思维模式"""
        patterns = []

        # 模式1: 重试模式
        for chain in self.chains:
            retry_count = 0
            prev_tool = None
            for step in chain.steps:
                for result in step.tool_results:
                    if not result['ok'] and result['tool'] == prev_tool:
                        retry_count += 1
                    prev_tool = result['tool']

            if retry_count > 0:
                patterns.append(f"   🔄 检测到重试模式: {retry_count} 次工具重试")

        # 模式2: 顺序探索模式
        for chain in self.chains:
            if len(chain.steps) > 3:
                tool_sequence = []
                for step in chain.steps:
                    for tc in step.tool_calls:
                        tool_sequence.append(tc.get('name'))

                if len(tool_sequence) > 3:
                    patterns.append(f"   🔍 顺序探索: {' → '.join(tool_sequence[:5])}")

        # 模式3: 并行调用模式
        for chain in self.chains:
            for step in chain.steps:
                if len(step.tool_calls) > 1:
                    tools = [tc.get('name') for tc in step.tool_calls]
                    patterns.append(f"   ⚡ 并行调用: {', '.join(tools)}")

        if patterns:
            for pattern in patterns[:5]:  # 最多显示5个
                print(pattern)
        else:
            print("   ℹ️  未检测到明显模式")

    def generate_optimization_suggestions(self, chain_index: int = 0):
        """生成优化建议"""
        print("=" * 100)
        print("💡 优化建议")
        print("=" * 100)
        print()

        if chain_index >= len(self.chains):
            print(f"❌ 链索引 {chain_index} 超出范围 (共 {len(self.chains)} 条)")
            return

        suggestions = []

        # 分析指定的链
        chain = self.chains[chain_index]

        # 建议1: 检查失败的工具调用
        for step in chain.steps:
            for result in step.tool_results:
                if not result['ok']:
                    suggestions.append(
                        f"🔴 工具 {result['tool']} 失败 (Turn {step.turn})\n"
                        f"     建议: 检查参数或添加错误处理"
                    )

        # 建议2: 检查冗余调用
        tool_calls = []
        for step in chain.steps:
            for tc in step.tool_calls:
                tool_calls.append((tc.get('name'), tc.get('args'), step.turn))

        # 检查重复调用
        seen = {}
        for tool, args, turn in tool_calls:
            key = (tool, str(args))
            if key in seen:
                suggestions.append(
                    f"🟡 检测到重复调用: {tool} (Turn {seen[key]} 和 Turn {turn})\n"
                    f"     建议: 缓存结果或优化逻辑"
                )
            seen[key] = turn

        # 建议3: 检查长时间运行
        if chain.total_duration_ms > 60000:  # 超过1分钟
            suggestions.append(
                f"🟡 运行时间过长: {chain.total_duration_ms/1000:.2f}s\n"
                f"     建议: 考虑并行化或优化提示词"
            )

        # 建议4: 检查工具失败后的重试
        failed_tools = []
        for step in chain.steps:
            for result in step.tool_results:
                if not result['ok']:
                    failed_tools.append((result['tool'], step.turn))

        if len(failed_tools) > 2:
            suggestions.append(
                f"🟡 多次工具失败 ({len(failed_tools)} 次)\n"
                f"     建议: 添加重试机制或改进错误处理"
            )

        # 建议5: 检查思考轮次过多
        if chain.total_turns > 10:
            suggestions.append(
                f"🟡 思考轮次过多 ({chain.total_turns} 轮)\n"
                f"     建议: 优化提示词，让 LLM 更快做出决策"
            )

        if suggestions:
            for i, suggestion in enumerate(suggestions[:5], 1):
                print(f"{i}. {suggestion}")
        else:
            print("✅ 未发现明显问题，思维链运行良好！")

        print()

    def generate_html_report(self, output_path: Path, chain_index: int = 0):
        """生成 HTML 报告"""
        if chain_index >= len(self.chains):
            print(f"❌ 链索引 {chain_index} 超出范围 (共 {len(self.chains)} 条)")
            return

        chain = self.chains[chain_index]

        html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LLM 思维链分析报告 - {chain.run_id}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            background: #f5f5f5;
            padding: 20px;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            padding: 40px;
        }}
        h1 {{
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
            margin-bottom: 30px;
        }}
        h2 {{
            color: #34495e;
            margin-top: 30px;
            margin-bottom: 15px;
            padding-left: 10px;
            border-left: 4px solid #3498db;
        }}
        .summary {{
            background: #ecf0f1;
            padding: 20px;
            border-radius: 5px;
            margin-bottom: 30px;
        }}
        .summary-item {{
            display: inline-block;
            margin-right: 30px;
            margin-bottom: 10px;
        }}
        .summary-label {{
            font-weight: bold;
            color: #7f8c8d;
        }}
        .summary-value {{
            color: #2c3e50;
            font-size: 1.2em;
        }}
        .step {{
            background: #fff;
            border: 1px solid #ddd;
            border-radius: 5px;
            padding: 20px;
            margin-bottom: 20px;
            transition: box-shadow 0.3s;
        }}
        .step:hover {{
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }}
        .step-header {{
            background: #3498db;
            color: white;
            padding: 10px 15px;
            border-radius: 5px;
            margin-bottom: 15px;
            font-weight: bold;
        }}
        .thinking {{
            background: #fff9e6;
            border-left: 4px solid #f39c12;
            padding: 15px;
            margin-bottom: 15px;
            border-radius: 3px;
        }}
        .tool-call {{
            background: #e8f5e9;
            border-left: 4px solid #4caf50;
            padding: 15px;
            margin-bottom: 15px;
            border-radius: 3px;
        }}
        .tool-result {{
            background: #f5f5f5;
            padding: 10px;
            margin-top: 10px;
            border-radius: 3px;
            font-family: monospace;
            font-size: 0.9em;
        }}
        .tool-result.success {{
            border-left: 4px solid #4caf50;
        }}
        .tool-result.failure {{
            border-left: 4px solid #f44336;
        }}
        .suggestion {{
            background: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 15px;
            margin-bottom: 10px;
            border-radius: 3px;
        }}
        .suggestion.error {{
            background: #f8d7da;
            border-left-color: #dc3545;
        }}
        .suggestion.warning {{
            background: #fff3cd;
            border-left-color: #ffc107;
        }}
        .badge {{
            display: inline-block;
            padding: 3px 8px;
            border-radius: 3px;
            font-size: 0.85em;
            font-weight: bold;
            margin-right: 5px;
        }}
        .badge-success {{
            background: #d4edda;
            color: #155724;
        }}
        .badge-error {{
            background: #f8d7da;
            color: #721c24;
        }}
        .final-output {{
            background: #e8f5e9;
            border: 2px solid #4caf50;
            padding: 20px;
            border-radius: 5px;
            margin-top: 30px;
        }}
        .timeline {{
            position: relative;
            padding-left: 30px;
        }}
        .timeline::before {{
            content: '';
            position: absolute;
            left: 10px;
            top: 0;
            bottom: 0;
            width: 2px;
            background: #3498db;
        }}
        .timeline-item {{
            position: relative;
            margin-bottom: 20px;
        }}
        .timeline-item::before {{
            content: '';
            position: absolute;
            left: -24px;
            top: 5px;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background: #3498db;
            border: 2px solid white;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🧠 LLM 思维链分析报告</h1>

        <div class="summary">
            <div class="summary-item">
                <span class="summary-label">Run ID:</span>
                <span class="summary-value">{chain.run_id}</span>
            </div>
            <div class="summary-item">
                <span class="summary-label">总耗时:</span>
                <span class="summary-value">{chain.total_duration_ms/1000:.2f}s</span>
            </div>
            <div class="summary-item">
                <span class="summary-label">思考轮次:</span>
                <span class="summary-value">{chain.total_turns}</span>
            </div>
            <div class="summary-item">
                <span class="summary-label">工具调用:</span>
                <span class="summary-value">{chain.total_tools}</span>
            </div>
        </div>

        <h2>📝 用户输入</h2>
        <div class="thinking">
            {chain.user_prompt}
        </div>

        <h2>🔍 思维链路</h2>
        <div class="timeline">
"""

        # 添加每个步骤
        for i, step in enumerate(chain.steps, 1):
            html_content += f"""
            <div class="timeline-item">
                <div class="step">
                    <div class="step-header">
                        🔄 第 {i} 轮思考 (Turn {step.turn})
                    </div>
"""

            # LLM 思考内容
            if step.response_content:
                html_content += f"""
                    <div class="thinking">
                        <strong>💭 LLM 思考:</strong><br>
                        {step.response_content[:300]}{'...' if len(step.response_content) > 300 else ''}
                    </div>
"""

            # 工具调用
            if step.tool_calls:
                html_content += f"""
                    <div class="tool-call">
                        <strong>🎯 决策: 调用 {len(step.tool_calls)} 个工具</strong><br>
"""
                for tc in step.tool_calls:
                    tool_name = tc.get('name', 'Unknown')
                    html_content += f"                        • {tool_name}<br>\n"

                html_content += "                    </div>\n"

            # 工具结果
            if step.tool_results:
                html_content += "                    <div>\n"
                html_content += "                        <strong>📊 执行结果:</strong><br>\n"
                for result in step.tool_results:
                    tool = result['tool']
                    ok = result['ok']
                    duration = result['duration_ms']
                    status_class = 'success' if ok else 'failure'
                    status_badge = 'badge-success' if ok else 'badge-error'
                    status_text = '✅ 成功' if ok else '❌ 失败'

                    html_content += f"""
                        <div class="tool-result {status_class}">
                            <span class="badge {status_badge}">{status_text}</span>
                            <strong>{tool}</strong> ({duration}ms)
                        </div>
"""
                html_content += "                    </div>\n"

            html_content += """
                </div>
            </div>
"""

        # 最终输出
        html_content += f"""
        </div>

        <h2>✅ 最终输出</h2>
        <div class="final-output">
            {chain.final_output[:500]}{'...' if len(chain.final_output) > 500 else ''}
        </div>

        <h2>💡 优化建议</h2>
"""

        # 生成建议
        suggestions = self._generate_suggestions_list(chain)

        if suggestions:
            for suggestion in suggestions[:5]:
                suggestion_type = 'error' if '🔴' in suggestion else 'warning'
                html_content += f"""
        <div class="suggestion {suggestion_type}">
            {suggestion.replace(chr(10), '<br>')}
        </div>
"""
        else:
            html_content += """
        <div class="suggestion">
            ✅ 未发现明显问题，思维链运行良好！
        </div>
"""

        html_content += """
    </div>
</body>
</html>
"""

        # 写入文件
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            print(f"✅ HTML 报告已生成: {output_path}")
        except Exception as e:
            print(f"❌ 生成 HTML 报告失败: {e}")

    def _generate_suggestions_list(self, chain: ThinkingChain) -> List[str]:
        """生成建议列表（用于 HTML）"""
        suggestions = []

        # 检查失败的工具调用
        for step in chain.steps:
            for result in step.tool_results:
                if not result['ok']:
                    suggestions.append(
                        f"🔴 工具 {result['tool']} 失败 (Turn {step.turn})\n"
                        f"     建议: 检查参数或添加错误处理"
                    )

        # 检查运行时间
        if chain.total_duration_ms > 60000:
            suggestions.append(
                f"🟡 运行时间过长: {chain.total_duration_ms/1000:.2f}s\n"
                f"     建议: 考虑并行化或优化提示词"
            )

        # 检查思考轮次
        if chain.total_turns > 10:
            suggestions.append(
                f"🟡 思考轮次过多 ({chain.total_turns} 轮)\n"
                f"     建议: 优化提示词，让 LLM 更快做出决策"
            )

        return suggestions


def visualize_thinking_chain(trace_file: Path, chain_index: int = 0, detailed: bool = True):
    """主入口：可视化思维链"""
    analyzer = ThinkingChainAnalyzer(trace_file)

    if not analyzer.load_events():
        return

    analyzer.parse_chains()

    if not analyzer.chains:
        print("⚠️  未找到完整的思维链")
        return

    # 可视化指定的链
    analyzer.visualize(chain_index, detailed)

    # 分析模式
    analyzer.analyze_patterns()

    # 生成建议
    analyzer.generate_optimization_suggestions()


def visualize_all_chains(trace_file: Path):
    """可视化所有思维链（简化版）"""
    analyzer = ThinkingChainAnalyzer(trace_file)

    if not analyzer.load_events():
        return

    analyzer.parse_chains()

    if not analyzer.chains:
        print("⚠️  未找到完整的思维链")
        return

    print("=" * 100)
    print(f"🧠 所有思维链概览 (共 {len(analyzer.chains)} 条)")
    print("=" * 100)
    print()

    for i, chain in enumerate(analyzer.chains):
        print(f"{i+1}. Run {chain.run_id}")
        print(f"   输入: {chain.user_prompt[:60]}...")
        print(f"   轮次: {chain.total_turns} | 工具: {chain.total_tools} | 耗时: {chain.total_duration_ms/1000:.2f}s")
        print()

    # 分析模式
    analyzer.analyze_patterns()

    # 生成建议
    analyzer.generate_optimization_suggestions()
