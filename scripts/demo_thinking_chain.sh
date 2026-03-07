#!/bin/bash
# LLM 思维链可视化工具 - 快速演示

echo "🧠 LLM 思维链可视化工具 - 演示"
echo "=================================="
echo ""

# 检查是否有 trace 文件
TRACE_FILE=".sessions/20260303_132911/trace.jsonl"

if [ ! -f "$TRACE_FILE" ]; then
    echo "❌ 找不到 trace 文件: $TRACE_FILE"
    echo ""
    echo "请先运行 Agent 生成 trace 文件，或使用其他 session 的 trace 文件"
    echo ""
    echo "示例:"
    echo "  ls -lt .sessions/ | head -5"
    echo "  python scripts/analyze_thinking.py .sessions/<session_id>/trace.jsonl"
    exit 1
fi

echo "📂 使用 trace 文件: $TRACE_FILE"
echo ""

# 演示 1: 基本分析
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "演示 1: 基本思维链分析"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
python scripts/analyze_thinking.py "$TRACE_FILE" 2>&1 | head -80
echo ""
echo "... (输出已截断，完整输出请运行完整命令)"
echo ""
read -p "按 Enter 继续..."
echo ""

# 演示 2: 优化建议
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "演示 2: 生成优化建议"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
python scripts/analyze_thinking.py "$TRACE_FILE" --optimize 2>&1 | tail -20
echo ""
read -p "按 Enter 继续..."
echo ""

# 演示 3: HTML 报告
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "演示 3: 生成 HTML 报告"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

HTML_FILE="/tmp/thinking_chain_demo.html"
python scripts/analyze_thinking.py "$TRACE_FILE" --html "$HTML_FILE"
echo ""
echo "✅ HTML 报告已生成: $HTML_FILE"
echo ""

# 尝试打开 HTML 文件
if command -v open &> /dev/null; then
    echo "🌐 正在浏览器中打开报告..."
    open "$HTML_FILE"
elif command -v xdg-open &> /dev/null; then
    echo "🌐 正在浏览器中打开报告..."
    xdg-open "$HTML_FILE"
else
    echo "💡 请手动在浏览器中打开: $HTML_FILE"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ 演示完成！"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📚 更多用法:"
echo ""
echo "  # 查看详细信息"
echo "  python scripts/analyze_thinking.py $TRACE_FILE --detailed"
echo ""
echo "  # 分析特定的思维链"
echo "  python scripts/analyze_thinking.py $TRACE_FILE --chain 1"
echo ""
echo "  # 生成完整报告"
echo "  python scripts/analyze_thinking.py $TRACE_FILE --html report.html --optimize"
echo ""
echo "📖 完整文档: docs/thinking_chain_guide.md"
echo ""
