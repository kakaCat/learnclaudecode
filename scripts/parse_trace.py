#!/usr/bin/env python3
"""解析 trace.jsonl 文件，输出易读的执行摘要"""

import json
import sys
from pathlib import Path
from datetime import datetime


def parse_trace(trace_file):
    """解析 trace.jsonl 并输出摘要"""

    with open(trace_file) as f:
        events = [json.loads(line.strip()) for line in f if line.strip()]

    # 提取关键信息
    start_event = next((e for e in events if e.get('event') == 'main_agent.start'), None)
    end_event = next((e for e in events if e.get('event') == 'main_agent.end'), None)

    if not start_event:
        print("❌ 未找到 agent 启动事件")
        return

    # 1. 基本信息
    print("=" * 60)
    print("📋 Agent 执行摘要")
    print("=" * 60)
    print(f"\n🎯 用户请求: {start_event.get('prompt', 'N/A')}")
    print(f"🆔 Run ID: {start_event.get('run_id', 'N/A')}")

    if end_event:
        duration = end_event.get('duration_ms', 0) / 1000
        print(f"⏱️  总耗时: {duration:.2f}秒")
        print(f"🔄 总步骤: {end_event.get('total_steps', 0)}")
        print(f"🤖 LLM调用: {end_event.get('llm_calls', 0)}次")
        print(f"🔧 工具调用: {end_event.get('tool_calls', 0)}次")
        print(f"💰 Token使用: {end_event.get('total_tokens', 0)} (输入:{end_event.get('input_tokens', 0)}, 输出:{end_event.get('output_tokens', 0)})")
        print(f"💵 总成本: ${end_event.get('total_cost', 0):.6f}")

    # 2. 执行步骤
    print("\n" + "=" * 60)
    print("📝 执行步骤详情")
    print("=" * 60)

    step = 0
    for event in events:
        event_type = event.get('event', '')

        if event_type == 'main.llm_start':
            step += 1
            print(f"\n[步骤 {step}] 🤖 LLM 思考")
            print(f"  模型: {event.get('model', 'N/A')}")

        elif event_type == 'main.llm_end':
            duration = event.get('duration_ms', 0) / 1000
            tokens = event.get('total_tokens', 0)
            preview = event.get('output_preview', '')[:100]
            print(f"  耗时: {duration:.2f}秒")
            print(f"  Token: {tokens}")
            if preview:
                print(f"  输出: {preview}...")

        elif event_type == 'main.tool_start':
            tool = event.get('tool', 'N/A')
            inputs = event.get('inputs', {})
            print(f"\n  🔧 调用工具: {tool}")
            print(f"     参数: {inputs}")

        elif event_type == 'main.tool_end':
            tool = event.get('tool', 'N/A')
            duration = event.get('duration_ms', 0)
            ok = event.get('ok', False)
            status = "✅" if ok else "❌"
            print(f"     {status} 完成 ({duration}ms)")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python parse_trace.py <trace.jsonl路径>")
        print("示例: python parse_trace.py .sessions/20260313_150207/trace.jsonl")
        sys.exit(1)

    trace_file = Path(sys.argv[1])
    if not trace_file.exists():
        print(f"❌ 文件不存在: {trace_file}")
        sys.exit(1)

    parse_trace(trace_file)
