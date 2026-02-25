#!/usr/bin/env python3
"""
五粮液股票价格查询脚本
股票代码：000858.SZ
"""

import json
import requests
from datetime import datetime
import time

def get_wuliangye_stock_data(use_real_api=False):
    """
    获取五粮液股票数据
    
    Args:
        use_real_api: 是否使用真实API（需要网络连接）
    
    Returns:
        dict: 股票数据字典
    """
    
    if use_real_api:
        # 使用新浪财经API获取实时数据（示例）
        try:
            # 新浪财经API示例（实际使用时需要检查API是否可用）
            symbol = "sz000858"  # 深圳证券交易所代码
            url = f"http://hq.sinajs.cn/list={symbol}"
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                # 解析新浪财经返回的数据格式
                data_str = response.text
                # 格式示例: var hq_str_sz000858="五粮液,149.50,150.20,148.80,151.50,147.20,...";
                # 这里简化处理，实际需要解析具体字段
                return parse_sina_data(data_str)
            else:
                print(f"API请求失败，状态码: {response.status_code}")
                return get_mock_data()
                
        except Exception as e:
            print(f"API请求异常: {e}")
            print("使用模拟数据...")
            return get_mock_data()
    else:
        # 使用模拟数据
        return get_mock_data()

def parse_sina_data(data_str):
    """
    解析新浪财经API返回的数据
    （简化版本，实际需要根据具体格式解析）
    """
    # 这里简化处理，实际需要解析具体字段
    try:
        # 示例解析逻辑
        parts = data_str.split('"')
        if len(parts) > 1:
            values = parts[1].split(',')
            if len(values) > 30:
                return {
                    "symbol": "000858.SZ",
                    "name": values[0],
                    "open_price": float(values[1]),
                    "last_close": float(values[2]),
                    "current_price": float(values[3]),
                    "high_price": float(values[4]),
                    "low_price": float(values[5]),
                    "volume": int(values[8]),
                    "amount": float(values[9]),
                    "timestamp": datetime.now().isoformat(),
                    "source": "sina"
                }
    except Exception as e:
        print(f"解析API数据失败: {e}")
    
    return get_mock_data()

def get_mock_data():
    """生成五粮液模拟股票数据"""
    
    # 基础价格信息（基于近期市场情况模拟）
    base_price = 148.50  # 基础价格
    change = 1.20  # 涨跌
    change_percent = 0.81  # 涨跌幅百分比
    
    current_price = base_price + change
    
    market_data = {
        "symbol": "000858.SZ",
        "name": "五粮液",
        "company_name": "宜宾五粮液股份有限公司",
        "current_price": current_price,
        "currency": "CNY",
        "change": change,
        "change_percent": change_percent,
        "open_price": 147.80,
        "last_close": base_price,
        "high_price": 149.80,
        "low_price": 147.20,
        "volume": 12567890,  # 成交量（股）
        "amount": 1865000000,  # 成交额（元）
        "market_cap": 576.8,  # 市值（十亿元）
        "pe_ratio": 28.5,  # 市盈率
        "pb_ratio": 6.8,  # 市净率
        "dividend_yield": 1.85,  # 股息率（%）
        "turnover_rate": 0.32,  # 换手率（%）
        "timestamp": datetime.now().isoformat(),
        "source": "mock"
    }
    
    # 技术指标
    technical_indicators = {
        "ma_5": 147.20,  # 5日均线
        "ma_10": 146.80,  # 10日均线
        "ma_20": 145.50,  # 20日均线
        "ma_60": 142.30,  # 60日均线
        "rsi_14": 58.5,  # RSI指标
        "macd": 0.85,  # MACD
        "macd_signal": 0.45,  # MACD信号线
        "bollinger_upper": 152.30,  # 布林带上轨
        "bollinger_middle": 147.80,  # 布林带中轨
        "bollinger_lower": 143.30,  # 布林带下轨
        "support_levels": [147.00, 145.50, 143.00],  # 支撑位
        "resistance_levels": [150.00, 152.50, 155.00]  # 阻力位
    }
    
    # 市场情绪数据
    market_sentiment = {
        "institutional_net_buy": 125600000,  # 机构净买入（元）
        "main_net_inflow": 85600000,  # 主力净流入（元）
        "retail_net_inflow": -45600000,  # 散户净流入（元）
        "northbound_net_buy": 23450000,  # 北向资金净买入（元）
        "short_interest": 1.2,  # 融券余额比例（%）
        "margin_balance": 3.8  # 融资余额比例（%）
    }
    
    # 基本面数据
    fundamental_data = {
        "revenue_growth": 15.8,  # 营收增长率（%）
        "profit_growth": 18.2,  # 净利润增长率（%）
        "roe": 22.5,  # 净资产收益率（%）
        "gross_margin": 75.8,  # 毛利率（%）
        "net_margin": 35.2,  # 净利率（%）
        "debt_ratio": 28.5,  # 资产负债率（%）
        "current_ratio": 2.8  # 流动比率
    }
    
    return {
        "market_data": market_data,
        "technical_indicators": technical_indicators,
        "market_sentiment": market_sentiment,
        "fundamental_data": fundamental_data
    }

def print_stock_report(data):
    """打印股票报告"""
    
    market = data["market_data"]
    tech = data["technical_indicators"]
    sentiment = data["market_sentiment"]
    fundamental = data["fundamental_data"]
    
    print("=" * 60)
    print("五粮液股票分析报告")
    print("=" * 60)
    print(f"数据时间: {market['timestamp']}")
    print(f"数据来源: {market['source']}")
    print()
    
    print("📈 实时价格信息")
    print("-" * 40)
    print(f"股票代码: {market['symbol']}")
    print(f"公司名称: {market['company_name']}")
    print(f"当前价格: {market['current_price']} {market['currency']}")
    
    # 显示涨跌颜色
    if market['change'] >= 0:
        change_str = f"↑ +{market['change']} (+{market['change_percent']}%)"
    else:
        change_str = f"↓ {market['change']} ({market['change_percent']}%)"
    
    print(f"涨跌幅: {change_str}")
    print(f"开盘价: {market['open_price']}")
    print(f"昨收价: {market['last_close']}")
    print(f"最高价: {market['high_price']}")
    print(f"最低价: {market['low_price']}")
    print(f"成交量: {market['volume']:,} 股")
    print(f"成交额: {market['amount']:,.0f} 元")
    print(f"市值: {market['market_cap']} 十亿元")
    print()
    
    print("📊 估值指标")
    print("-" * 40)
    print(f"市盈率(PE): {market['pe_ratio']}")
    print(f"市净率(PB): {market['pb_ratio']}")
    print(f"股息率: {market['dividend_yield']}%")
    print(f"换手率: {market['turnover_rate']}%")
    print()
    
    print("📈 技术指标")
    print("-" * 40)
    print("移动平均线:")
    print(f"  5日均线: {tech['ma_5']}")
    print(f"  10日均线: {tech['ma_10']}")
    print(f"  20日均线: {tech['ma_20']}")
    print(f"  60日均线: {tech['ma_60']}")
    print(f"RSI(14): {tech['rsi_14']}")
    print(f"MACD: {tech['macd']}")
    print("布林带:")
    print(f"  上轨: {tech['bollinger_upper']}")
    print(f"  中轨: {tech['bollinger_middle']}")
    print(f"  下轨: {tech['bollinger_lower']}")
    print(f"支撑位: {', '.join(map(str, tech['support_levels']))}")
    print(f"阻力位: {', '.join(map(str, tech['resistance_levels']))}")
    print()
    
    print("💰 资金流向")
    print("-" * 40)
    print(f"机构净买入: {sentiment['institutional_net_buy']:,.0f} 元")
    print(f"主力净流入: {sentiment['main_net_inflow']:,.0f} 元")
    print(f"散户净流入: {sentiment['retail_net_inflow']:,.0f} 元")
    print(f"北向资金净买入: {sentiment['northbound_net_buy']:,.0f} 元")
    print(f"融券余额比例: {sentiment['short_interest']}%")
    print(f"融资余额比例: {sentiment['margin_balance']}%")
    print()
    
    print("🏢 基本面数据")
    print("-" * 40)
    print(f"营收增长率: {fundamental['revenue_growth']}%")
    print(f"净利润增长率: {fundamental['profit_growth']}%")
    print(f"净资产收益率(ROE): {fundamental['roe']}%")
    print(f"毛利率: {fundamental['gross_margin']}%")
    print(f"净利率: {fundamental['net_margin']}%")
    print(f"资产负债率: {fundamental['debt_ratio']}%")
    print(f"流动比率: {fundamental['current_ratio']}")
    print()
    
    print("💡 投资建议摘要")
    print("-" * 40)
    print("1. 当前价格处于近期相对高位")
    print("2. RSI接近60，显示适度强势")
    print("3. 机构资金呈净买入状态")
    print("4. 基本面稳健，盈利能力较强")
    print("5. 需关注150元阻力位突破情况")
    print()
    
    print("=" * 60)
    print("风险提示：股市有风险，投资需谨慎")
    print("此为模拟数据，实际投资请参考实时市场数据")
    print("=" * 60)

def save_to_json(data, filename="wuliangye_stock_data.json"):
    """保存数据到JSON文件"""
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"数据已保存到 {filename}")

def main():
    """主函数"""
    print("正在获取五粮液股票数据...")
    
    # 尝试使用真实API，失败则使用模拟数据
    try:
        data = get_wuliangye_stock_data(use_real_api=False)  # 暂时使用模拟数据
    except Exception as e:
        print(f"获取数据失败: {e}")
        print("使用模拟数据...")
        data = get_mock_data()
    
    # 打印报告
    print_stock_report(data)
    
    # 保存数据
    save_to_json(data)
    
    return data

if __name__ == "__main__":
    main()