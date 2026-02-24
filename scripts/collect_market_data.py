#!/usr/bin/env python3
"""
阿里巴巴市场数据收集脚本
"""

import json
import requests
from datetime import datetime, timedelta

def get_alibaba_market_data():
    """获取阿里巴巴市场数据"""
    
    # 模拟数据（实际应用中应使用API获取实时数据）
    market_data = {
        "symbol": "BABA",
        "company_name": "Alibaba Group Holding Limited",
        "last_price": 74.50,  # 美元
        "currency": "USD",
        "change": -1.20,
        "change_percent": -1.58,
        "volume": 12500000,
        "avg_volume": 15000000,
        "market_cap": 189.5,  # 十亿美元
        "pe_ratio": 11.5,
        "dividend_yield": 1.32,
        "beta": 0.85,
        "52_week_high": 102.50,
        "52_week_low": 58.01,
        "day_range": "73.80-75.20",
        "year_range": "58.01-102.50",
        "timestamp": datetime.now().isoformat()
    }
    
    # 技术指标
    technical_indicators = {
        "ma_50": 76.80,
        "ma_200": 82.40,
        "rsi_14": 42.5,
        "macd": -1.20,
        "macd_signal": -0.80,
        "macd_histogram": -0.40,
        "bollinger_upper": 80.20,
        "bollinger_middle": 76.80,
        "bollinger_lower": 73.40,
        "support_levels": [73.00, 70.50, 68.00],
        "resistance_levels": [76.00, 78.50, 82.00]
    }
    
    # 机构持仓数据（模拟）
    institutional_data = {
        "institutional_holders": 1567,
        "percent_held": 15.8,
        "mutual_fund_holders": 2345,
        "percent_held_mutual": 12.3,
        "insider_ownership": 6.5,
        "short_interest": 2.8,  # 百分比
        "short_ratio": 3.2,  # 天数
        "analyst_ratings": {
            "strong_buy": 12,
            "buy": 18,
            "hold": 8,
            "sell": 2,
            "strong_sell": 1,
            "average_target": 98.50,
            "high_target": 125.00,
            "low_target": 65.00
        }
    }
    
    return {
        "market_data": market_data,
        "technical_indicators": technical_indicators,
        "institutional_data": institutional_data
    }

def save_market_data():
    """保存市场数据到文件"""
    data = get_alibaba_market_data()
    
    # 保存到JSON文件
    with open("data_collection/market_data/alibaba_market_data.json", "w") as f:
        json.dump(data, f, indent=2)
    
    # 保存到Markdown文件
    md_content = generate_markdown_report(data)
    with open("data_collection/market_data/alibaba_market_analysis.md", "w") as f:
        f.write(md_content)
    
    print("市场数据已保存")

def generate_markdown_report(data):
    """生成Markdown格式的报告"""
    
    market = data["market_data"]
    tech = data["technical_indicators"]
    inst = data["institutional_data"]
    
    content = f"""# 阿里巴巴市场数据分析报告

## 基本信息
- **股票代码**: {market['symbol']}
- **公司名称**: {market['company_name']}
- **数据时间**: {market['timestamp']}

## 市场价格数据
- **最新价格**: ${market['last_price']} {market['currency']}
- **涨跌幅**: {market['change']} ({market['change_percent']}%)
- **成交量**: {market['volume']:,} 股
- **平均成交量**: {market['avg_volume']:,} 股
- **市值**: ${market['market_cap']}B

## 价格区间
- **当日区间**: {market['day_range']}
- **52周区间**: {market['year_range']}
- **52周高点**: ${market['52_week_high']}
- **52周低点**: ${market['52_week_low']}

## 估值指标
- **市盈率(PE)**: {market['pe_ratio']}
- **股息率**: {market['dividend_yield']}%
- **Beta系数**: {market['beta']}

## 技术指标
### 移动平均线
- **50日均线**: ${tech['ma_50']}
- **200日均线**: ${tech['ma_200']}

### 动量指标
- **RSI(14)**: {tech['rsi_14']}
- **MACD**: {tech['macd']}
- **MACD信号线**: {tech['macd_signal']}
- **MACD柱状图**: {tech['macd_histogram']}

### 布林带
- **上轨**: ${tech['bollinger_upper']}
- **中轨**: ${tech['bollinger_middle']}
- **下轨**: ${tech['bollinger_lower']}

### 关键价位
- **支撑位**: ${', $'.join(map(str, tech['support_levels']))}
- **阻力位**: ${', $'.join(map(str, tech['resistance_levels']))}

## 机构与市场情绪
### 持仓情况
- **机构持有者**: {inst['institutional_holders']} 家
- **机构持股比例**: {inst['percent_held']}%
- **共同基金持有者**: {inst['mutual_fund_holders']} 家
- **共同基金持股比例**: {inst['percent_held_mutual']}%
- **内部人持股**: {inst['insider_ownership']}%

### 做空数据
- **做空比例**: {inst['short_interest']}%
- **做空比率**: {inst['short_ratio']} 天

### 分析师评级
- **强力买入**: {inst['analyst_ratings']['strong_buy']}
- **买入**: {inst['analyst_ratings']['buy']}
- **持有**: {inst['analyst_ratings']['hold']}
- **卖出**: {inst['analyst_ratings']['sell']}
- **强力卖出**: {inst['analyst_ratings']['strong_sell']}
- **平均目标价**: ${inst['analyst_ratings']['average_target']}
- **最高目标价**: ${inst['analyst_ratings']['high_target']}
- **最低目标价**: ${inst['analyst_ratings']['low_target']}

## 技术分析摘要
1. **趋势判断**: 股价在50日和200日均线下方，处于下降趋势
2. **超买超卖**: RSI为42.5，接近中性区域
3. **动量**: MACD为负值，显示下跌动量
4. **波动性**: 股价在布林带中下轨之间运行
5. **关键价位**: 重要支撑位在$73，阻力位在$76

## 投资建议参考
- 当前价格较52周高点下跌约27%
- 市盈率相对较低，估值具有吸引力
- 机构持股比例适中，做空比例不高
- 分析师平均目标价较当前价格有32%上涨空间

---
*注：此为模拟数据，实际投资决策需基于实时数据和专业分析*"""
    
    return content

if __name__ == "__main__":
    save_market_data()
    print("阿里巴巴市场数据分析报告已生成")