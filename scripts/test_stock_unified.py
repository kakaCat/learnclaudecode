#!/usr/bin/env python3
"""
A股股票查询工具统一版本测试脚本
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.app.tools.stock_query_unified import stock_a_query_unified, stock_a_batch_query_unified

def main():
    print("=== A股股票查询工具统一版本测试 ===\n")
    
    # 测试单个股票查询
    print("1. 查询平安银行(000001)当前价格:")
    try:
        result = stock_a_query_unified("000001", "current")
        if "error" in result:
            print(f"   错误: {result['error']}")
        if "warning" in result:
            print(f"   警告: {result['warning']}")
        
        print(f"   股票代码: {result.get('code', '')}")
        print(f"   股票名称: {result.get('name', '')}")
        print(f"   当前价格: {result.get('price', 0)}")
        print(f"   涨跌幅: {result.get('change', 0)}%")
        print(f"   市场: {result.get('market', '')}")
        print(f"   数据来源: {result.get('source', 'unknown')}")
    except Exception as e:
        print(f"   异常: {e}")
    
    print()
    
    # 测试其他股票
    print("2. 查询贵州茅台(600519):")
    try:
        result = stock_a_query_unified("600519", "current")
        if "warning" in result:
            print(f"   警告: {result['warning']}")
        print(f"   股票名称: {result.get('name', '')}")
        print(f"   当前价格: {result.get('price', 0)}")
        print(f"   数据来源: {result.get('source', 'unknown')}")
    except Exception as e:
        print(f"   异常: {e}")
    
    print()
    
    # 测试批量查询
    print("3. 批量查询多个股票:")
    try:
        symbols = ["000001", "600519", "600036"]
        result = stock_a_batch_query_unified(symbols, "current")
        for symbol, data in result.items():
            if "warning" in data and data["source"] == "mock":
                status = "⚠️ 模拟数据"
            else:
                status = "✅ 真实数据"
            print(f"   {symbol} ({data.get('name', '')}): {data.get('price', 0)}元 {status}")
    except Exception as e:
        print(f"   异常: {e}")
    
    print()
    print("=== 测试完成 ===")
    print("注意：如果显示'模拟数据'，说明真实数据源暂时不可用，但工具仍能正常工作")

if __name__ == "__main__":
    main()