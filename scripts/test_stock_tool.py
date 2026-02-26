#!/usr/bin/env python3
"""
A股股票查询工具使用示例
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.app.tools import stock_a_query, stock_a_batch_query


def main():
    print("=== A股股票查询工具测试 ===\n")
    
    # 测试单个股票查询 - 当前价格
    print("1. 查询平安银行(000001)当前价格:")
    try:
        result = stock_a_query.invoke({"symbol": "000001", "query_type": "current"})
        print(f"   结果: {result}")
    except Exception as e:
        print(f"   错误: {e}")
    
    print()
    
    # 测试单个股票查询 - 基本信息
    print("2. 查询贵州茅台(600519)基本信息:")
    try:
        result = stock_a_query.invoke({"symbol": "600519", "query_type": "basic"})
        print(f"   结果: {result}")
    except Exception as e:
        print(f"   错误: {e}")
    
    print()
    
    # 测试单个股票查询 - 历史数据
    print("3. 查询招商银行(600036)历史数据:")
    try:
        result = stock_a_query.invoke({"symbol": "600036", "query_type": "history"})
        print(f"   结果: {result}")
    except Exception as e:
        print(f"   错误: {e}")
    
    print()
    
    # 测试批量查询
    print("4. 批量查询多个股票当前价格:")
    try:
        symbols = ["000001", "600519", "600036"]
        result = stock_a_batch_query.invoke({"symbols": symbols, "query_type": "current"})
        print(f"   结果: {result}")
    except Exception as e:
        print(f"   错误: {e}")


if __name__ == "__main__":
    main()