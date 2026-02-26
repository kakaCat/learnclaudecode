#!/usr/bin/env python3
"""
A股股票查询工具修复版本测试脚本
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.app.tools.stock_query import stock_a_query, stock_a_batch_query

def main():
    print("=== A股股票查询工具修复版本测试 ===\n")
    
    # 测试单个股票查询 - 当前价格
    print("1. 查询平安银行(000001)当前价格:")
    try:
        result = stock_a_query("000001", "current")
        if "error" in result:
            print(f"   错误: {result['error']}")
            print(f"   建议: {result.get('suggestion', '')}")
        else:
            print(f"   股票名称: {result.get('name', '')}")
            print(f"   当前价格: {result.get('price', 0)}")
            print(f"   涨跌幅: {result.get('change', 0)}%")
            print(f"   市场: {result.get('market', '')}")
    except Exception as e:
        print(f"   异常: {e}")
    
    print()
    
    # 测试单个股票查询 - 基本信息
    print("2. 查询贵州茅台(600519)基本信息:")
    try:
        result = stock_a_query("600519", "basic")
        if "error" in result:
            print(f"   错误: {result['error']}")
            print(f"   建议: {result.get('suggestion', '')}")
        else:
            print(f"   股票名称: {result.get('name', '')}")
            print(f"   所属行业: {result.get('industry', '')}")
            print(f"   总市值: {result.get('total_value', '')}")
            print(f"   市盈率: {result.get('pe', '')}")
    except Exception as e:
        print(f"   异常: {e}")
    
    print()
    
    # 测试单个股票查询 - 历史数据
    print("3. 查询招商银行(600036)历史数据:")
    try:
        result = stock_a_query("600036", "history")
        if "error" in result:
            print(f"   错误: {result['error']}")
            print(f"   建议: {result.get('suggestion', '')}")
        else:
            history = result.get('history', [])
            if history:
                print(f"   最近{len(history)}个交易日数据:")
                for i, day in enumerate(history[-3:], 1):  # 显示最近3天
                    print(f"     {day['date']}: 开盘{day['open']}, 收盘{day['close']}, 涨跌幅{(day['close']/day['open']-1)*100:.2f}%")
            else:
                print("   无历史数据")
    except Exception as e:
        print(f"   异常: {e}")
    
    print()
    
    # 测试批量查询
    print("4. 批量查询多个股票当前价格:")
    try:
        symbols = ["000001", "600519", "600036"]
        result = stock_a_batch_query(symbols, "current")
        for symbol, data in result.items():
            if "error" in data:
                print(f"   {symbol}: 错误 - {data['error']}")
            else:
                print(f"   {symbol} ({data.get('name', '')}): {data.get('price', 0)}元, {data.get('change', 0)}%")
    except Exception as e:
        print(f"   异常: {e}")

if __name__ == "__main__":
    main()