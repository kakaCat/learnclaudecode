#!/bin/bash
# 外部监控测试脚本

echo "========================================="
echo "外部监控演示"
echo "========================================="
echo ""

# 测试1：正常运行
echo "测试1：正常运行的 Agent"
echo "命令: python scripts/supervisor.py"
echo "预期: Agent 正常运行并退出，监控器不重启"
echo ""
read -p "按回车开始测试1..."
python scripts/supervisor.py &
SUPERVISOR_PID=$!
sleep 25
kill $SUPERVISOR_PID 2>/dev/null
echo ""

# 测试2：崩溃重启
echo "测试2：崩溃的 Agent（自动重启）"
echo "命令: python scripts/supervisor.py"
echo "预期: Agent 崩溃后自动重启"
echo ""
read -p "按回车开始测试2..."
# 修改 supervisor.py 使用 crash 模式
echo "（需要手动修改 supervisor.py 中的命令为 crash 模式）"
echo ""

# 测试3：健康检查
echo "测试3：健康检查监控"
echo "命令: python scripts/health_monitor.py"
echo "预期: 定期检查健康端点，失败时重启"
echo ""
read -p "按回车开始测试3..."
echo "（需要先启动 Agent 的健康检查端点）"
echo ""

echo "========================================="
echo "演示完成"
echo "========================================="
