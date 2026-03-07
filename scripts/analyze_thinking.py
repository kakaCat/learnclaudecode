#!/usr/bin/env python3
"""
思维链分析命令行工具

使用方法:
    python scripts/analyze_thinking.py <trace_file>
    python scripts/analyze_thinking.py .sessions/20260303_132911/trace.jsonl
    python scripts/analyze_thinking.py .sessions/20260303_132911/trace.jsonl --detailed
    python scripts/analyze_thinking.py .sessions/20260303_132911/trace.jsonl --html output.html
    python scripts/analyze_thinking.py .sessions/20260303_132911/trace.jsonl --deep-analysis
"""

import sys
import argparse
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.app.analysis.thinking_chain import ThinkingChainAnalyzer
from backend.app.analysis.intent_recognition import (
    print_goal_alignment,
    print_optimal_path,
    print_root_causes
)


def main():
    parser = argparse.ArgumentParser(
        description="分析 LLM 思维链，可视化 Agent 的思考过程"
    )
    parser.add_argument(
        "trace_file",
        type=str,
        help="trace.jsonl 文件路径"
    )
    parser.add_argument(
        "--chain",
        type=int,
        default=0,
        help="要分析的链索引 (默认: 0，即第一条)"
    )
    parser.add_argument(
        "--detailed",
        action="store_true",
        help="显示详细信息（包括完整的工具参数和结果）"
    )
    parser.add_argument(
        "--html",
        type=str,
        help="生成 HTML 报告并保存到指定文件"
    )
    parser.add_argument(
        "--optimize",
        action="store_true",
        help="生成优化建议"
    )
    parser.add_argument(
        "--deep-analysis",
        action="store_true",
        help="深度分析：目标对齐 + 最优路径 + 根因分析"
    )

    args = parser.parse_args()

    # 检查文件是否存在
    trace_path = Path(args.trace_file)
    if not trace_path.exists():
        print(f"❌ 文件不存在: {trace_path}")
        sys.exit(1)

    # 创建分析器
    analyzer = ThinkingChainAnalyzer(trace_path)

    # 加载事件
    print(f"📂 加载 trace 文件: {trace_path}")
    if not analyzer.load_events():
        sys.exit(1)

    print(f"✅ 加载了 {len(analyzer.events)} 个事件")
    print()

    # 解析思维链
    analyzer.parse_chains()
    print(f"🔗 解析出 {len(analyzer.chains)} 条思维链")
    print()

    if not analyzer.chains:
        print("⚠️  没有找到完整的思维链")
        sys.exit(0)

    # 可视化
    if args.html:
        # 生成 HTML 报告
        html_path = Path(args.html)
        analyzer.generate_html_report(html_path, chain_index=args.chain)
        print(f"📄 HTML 报告已生成: {html_path}")
    else:
        # 终端可视化
        analyzer.visualize(chain_index=args.chain, detailed=args.detailed)

    # 深度分析
    if args.deep_analysis:
        print()
        chain = analyzer.chains[args.chain]
        print_goal_alignment(chain)
        print_optimal_path(chain)
        print_root_causes(chain)

    # 优化建议
    if args.optimize:
        print()
        analyzer.generate_optimization_suggestions(chain_index=args.chain)


if __name__ == "__main__":
    main()
