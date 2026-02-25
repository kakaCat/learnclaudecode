#!/usr/bin/env python3
"""
股票查询命令行工具
"""

import sys
import json
from accurate_stock_price import AccurateStockFetcher

def main():
    """主函数"""
    
    print("📈 股票查询工具")
    print("=" * 50)
    
    # 默认查询五粮液
    symbol = "000858.SZ"
    name = "五粮液"
    
    print(f"查询股票: {name} ({symbol})")
    print("正在获取实时数据...")
    
    try:
        fetcher = AccurateStockFetcher()
        stock_data = fetcher.get_wuliangye_price()
        
        # 简洁显示
        print("\n" + "=" * 50)
        print(f"{stock_data['name']} ({stock_data['symbol']})")
        print("-" * 50)
        
        price = stock_data['price']
        change = stock_data['change']
        change_percent = stock_data['change_percent']
        
        # 价格显示
        if change >= 0:
            price_display = f"💰 {price}  📈 +{change} (+{change_percent}%)"
            color = "\033[92m"  # 绿色
        else:
            price_display = f"💰 {price}  📉 {change} ({change_percent}%)"
            color = "\033[91m"  # 红色
        
        print(f"{color}{price_display}\033[0m")
        print(f"🕒 {stock_data['timestamp'][:19]}")
        
        # 数据源
        source = stock_data.get('source', 'unknown')
        if source == 'tencent_finance':
            print("📡 数据来源: 腾讯财经实时数据")
        elif source == 'estimated_backup':
            print("⚠️  数据来源: 历史数据估算")
            if stock_data.get('note'):
                print(f"   {stock_data['note']}")
        
        print("=" * 50)
        
        # 保存选项
        save_option = input("\n是否保存数据到文件? (y/n): ").strip().lower()
        if save_option == 'y':
            filename = f"{symbol.replace('.', '_')}_price.json"
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(stock_data, f, ensure_ascii=False, indent=2)
            print(f"✅ 数据已保存到 {filename}")
        
        # 显示更多选项
        more_option = input("\n显示详细数据? (y/n): ").strip().lower()
        if more_option == 'y':
            print("\n" + "=" * 50)
            print("详细数据:")
            print(json.dumps(stock_data, ensure_ascii=False, indent=2))
        
    except Exception as e:
        print(f"❌ 查询失败: {e}")
        print("\n💡 建议:")
        print("  1. 检查网络连接")
        print("  2. 稍后重试")
        print("  3. 使用专业股票软件查看实时行情")
        return 1
    
    print("\n✅ 查询完成")
    return 0

if __name__ == "__main__":
    sys.exit(main())