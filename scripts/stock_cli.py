#!/usr/bin/env python3
"""
股票查询命令行工具
"""

import sys
import argparse
from datetime import datetime
import json

def get_stock_data(symbol):
    """根据股票代码获取数据"""
    
    stock_map = {
        "000858": {
            "name": "五粮液",
            "full_name": "宜宾五粮液股份有限公司",
            "exchange": "SZ",
            "sector": "食品饮料",
            "industry": "白酒"
        },
        "600519": {
            "name": "贵州茅台",
            "full_name": "贵州茅台酒股份有限公司",
            "exchange": "SH",
            "sector": "食品饮料",
            "industry": "白酒"
        },
        "000001": {
            "name": "平安银行",
            "full_name": "平安银行股份有限公司",
            "exchange": "SZ",
            "sector": "金融",
            "industry": "银行"
        },
        "000002": {
            "name": "万科A",
            "full_name": "万科企业股份有限公司",
            "exchange": "SZ",
            "sector": "房地产",
            "industry": "房地产开发"
        }
    }
    
    if symbol not in stock_map:
        return None
    
    import random
    import time
    
    # 生成模拟价格数据
    random.seed(int(time.time()) // 60)
    
    base_prices = {
        "000858": 148.50,
        "600519": 1680.00,
        "000001": 10.25,
        "000002": 8.75
    }
    
    base_price = base_prices.get(symbol, 100.00)
    variation = random.uniform(-0.03, 0.03) * base_price
    current_price = base_price + variation
    
    change = current_price - base_price
    change_percent = (change / base_price) * 100
    
    stock_info = stock_map[symbol]
    
    return {
        "symbol": f"{symbol}.{stock_info['exchange']}",
        "name": stock_info['name'],
        "full_name": stock_info['full_name'],
        "price": round(current_price, 2),
        "change": round(change, 2),
        "change_percent": round(change_percent, 2),
        "volume": random.randint(5000000, 20000000),
        "amount": round(current_price * random.randint(5000000, 20000000), 2),
        "open": round(base_price * (1 + random.uniform(-0.02, 0.02)), 2),
        "high": round(current_price * (1 + random.uniform(0, 0.03)), 2),
        "low": round(current_price * (1 - random.uniform(0, 0.03)), 2),
        "prev_close": base_price,
        "exchange": stock_info['exchange'],
        "sector": stock_info['sector'],
        "industry": stock_info['industry'],
        "time": datetime.now().strftime("%H:%M:%S"),
        "date": datetime.now().strftime("%Y-%m-%d"),
        "timestamp": datetime.now().isoformat()
    }

def print_simple(stock_data):
    """简单格式输出"""
    if stock_data['change'] >= 0:
        change_color = "\033[92m"  # 绿色
    else:
        change_color = "\033[91m"  # 红色
    
    reset_color = "\033[0m"
    
    print(f"{stock_data['name']} ({stock_data['symbol']})")
    print(f"价格: {stock_data['price']} CNY")
    print(f"{change_color}涨跌: {stock_data['change']:+} ({stock_data['change_percent']:+.2f}%){reset_color}")
    print(f"时间: {stock_data['date']} {stock_data['time']}")

def print_detailed(stock_data):
    """详细格式输出"""
    print("\n" + "=" * 60)
    print(f"📊 {stock_data['name']} ({stock_data['symbol']})")
    print("=" * 60)
    
    # 价格信息
    print("💰 价格信息:")
    print(f"  当前价格: {stock_data['price']} CNY")
    
    if stock_data['change'] >= 0:
        print(f"  📈 涨跌: +{stock_data['change']} (+{stock_data['change_percent']:.2f}%)")
    else:
        print(f"  📉 涨跌: {stock_data['change']} ({stock_data['change_percent']:.2f}%)")
    
    print(f"  开盘价: {stock_data['open']}")
    print(f"  最高价: {stock_data['high']}")
    print(f"  最低价: {stock_data['low']}")
    print(f"  昨收价: {stock_data['prev_close']}")
    
    # 交易信息
    print("\n📈 交易信息:")
    print(f"  成交量: {stock_data['volume']:,} 股")
    print(f"  成交额: {stock_data['amount']:,.2f} 元")
    
    # 公司信息
    print("\n🏢 公司信息:")
    print(f"  公司全称: {stock_data['full_name']}")
    print(f"  交易所: {stock_data['exchange']}")
    print(f"  行业板块: {stock_data['sector']}")
    print(f"  细分行业: {stock_data['industry']}")
    
    print(f"\n📅 数据时间: {stock_data['date']} {stock_data['time']}")
    print("=" * 60)

def print_json(stock_data):
    """JSON格式输出"""
    print(json.dumps(stock_data, ensure_ascii=False, indent=2))

def main():
    parser = argparse.ArgumentParser(description="股票查询命令行工具")
    parser.add_argument("symbol", help="股票代码（如：000858）")
    parser.add_argument("-d", "--detailed", action="store_true", help="显示详细信息")
    parser.add_argument("-j", "--json", action="store_true", help="JSON格式输出")
    parser.add_argument("-s", "--save", help="保存到文件")
    
    args = parser.parse_args()
    
    # 获取股票数据
    stock_data = get_stock_data(args.symbol)
    
    if not stock_data:
        print(f"错误：未找到股票代码 {args.symbol}")
        print("支持的股票代码：")
        print("  000858 - 五粮液")
        print("  600519 - 贵州茅台")
        print("  000001 - 平安银行")
        print("  000002 - 万科A")
        return 1
    
    # 输出数据
    if args.json:
        print_json(stock_data)
    elif args.detailed:
        print_detailed(stock_data)
    else:
        print_simple(stock_data)
    
    # 保存到文件
    if args.save:
        with open(args.save, "w", encoding="utf-8") as f:
            json.dump(stock_data, f, ensure_ascii=False, indent=2)
        print(f"\n✅ 数据已保存到 {args.save}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())