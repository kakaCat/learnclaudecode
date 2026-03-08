#!/bin/bash
# 测试运行脚本

set -e

echo "🧪 运行后端单元测试"
echo "===================="

# 运行所有测试
python -m pytest tests/unit/backend/ -v --tb=short

echo ""
echo "✅ 测试完成"
