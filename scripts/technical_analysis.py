#!/usr/bin/env python3
"""
阿里巴巴（BABA）技术分析脚本
用于计算技术指标和生成分析报告
"""

import json
import math
from datetime import datetime, timedelta

class TechnicalAnalyzer:
    def __init__(self, market_data):
        """初始化技术分析器"""
        self.data = market_data
        self.current_price = market_data['market_data']['last_price']
        
    def calculate_trend(self):
        """计算趋势方向"""
        ma_50 = self.data['technical_indicators']['ma_50']
        ma_200 = self.data['technical_indicators']['ma_200']
        
        # 判断趋势
        if self.current_price > ma_50 and ma_50 > ma_200:
            return "上涨趋势"
        elif self.current_price < ma_50 and ma_50 < ma_200:
            return "下跌趋势"
        elif abs(self.current_price - ma_50) < 2 and abs(ma_50 - ma_200) < 5:
            return "盘整趋势"
        else:
            return "震荡趋势"
    
    def analyze_rsi(self):
        """分析RSI指标"""
        rsi = self.data['technical_indicators']['rsi_14']
        
        if rsi < 30:
            return "超卖", "看涨信号"
        elif rsi < 50:
            return "弱势", "中性偏弱"
        elif rsi < 70:
            return "强势", "中性偏强"
        else:
            return "超买", "看跌信号"
    
    def analyze_macd(self):
        """分析MACD指标"""
        macd = self.data['technical_indicators']['macd']
        signal = self.data['technical_indicators']['macd_signal']
        histogram = self.data['technical_indicators']['macd_histogram']
        
        if macd > signal and histogram > 0:
            return "金叉", "看涨信号"
        elif macd < signal and histogram < 0:
            return "死叉", "看跌信号"
        elif abs(macd - signal) < 0.2:
            return "粘合", "方向不明"
        else:
            return "分化", "需要观察"
    
    def analyze_bollinger(self):
        """分析布林带"""
        upper = self.data['technical_indicators']['bollinger_upper']
        lower = self.data['technical_indicators']['bollinger_lower']
        middle = self.data['technical_indicators']['bollinger_middle']
        
        position = (self.current_price - lower) / (upper - lower) * 100
        
        if position > 80:
            return "上轨附近", "可能回调"
        elif position > 60:
            return "中上轨", "偏强"
        elif position > 40:
            return "中轨附近", "中性"
        elif position > 20:
            return "中下轨", "偏弱"
        else:
            return "下轨附近", "可能反弹"
    
    def calculate_support_resistance(self):
        """计算支撑阻力位强度"""
        supports = self.data['technical_indicators']['support_levels']
        resistances = self.data['technical_indicators']['resistance_levels']
        
        # 计算当前价格与关键水平的距离
        nearest_support = min(supports, key=lambda x: abs(x - self.current_price))
        nearest_resistance = min(resistances, key=lambda x: abs(x - self.current_price))
        
        support_distance = (self.current_price - nearest_support) / self.current_price * 100
        resistance_distance = (nearest_resistance - self.current_price) / self.current_price * 100
        
        return {
            'nearest_support': nearest_support,
            'nearest_resistance': nearest_resistance,
            'support_distance_pct': support_distance,
            'resistance_distance_pct': resistance_distance,
            'support_strength': '强' if support_distance < 3 else '中' if support_distance < 6 else '弱',
            'resistance_strength': '强' if resistance_distance < 3 else '中' if resistance_distance < 6 else '弱'
        }
    
    def analyze_volume(self):
        """分析成交量"""
        volume = self.data['market_data']['volume']
        avg_volume = self.data['market_data']['avg_volume']
        
        volume_ratio = volume / avg_volume
        
        if volume_ratio > 1.5:
            return "放量", "关注突破"
        elif volume_ratio > 1.2:
            return "温和放量", "趋势可能延续"
        elif volume_ratio > 0.8:
            return "正常", "趋势稳定"
        else:
            return "缩量", "可能变盘"
    
    def generate_signals(self):
        """生成买卖信号"""
        signals = []
        
        # RSI信号
        rsi_status, rsi_signal = self.analyze_rsi()
        if "看涨" in rsi_signal:
            signals.append(("RSI", "买入信号", "低风险"))
        elif "看跌" in rsi_signal:
            signals.append(("RSI", "卖出信号", "中风险"))
        
        # MACD信号
        macd_status, macd_signal = self.analyze_macd()
        if "看涨" in macd_signal:
            signals.append(("MACD", "买入信号", "中风险"))
        elif "看跌" in macd_signal:
            signals.append(("MACD", "卖出信号", "中风险"))
        
        # 布林带信号
        bollinger_status, bollinger_signal = self.analyze_bollinger()
        if "反弹" in bollinger_signal:
            signals.append(("布林带", "买入信号", "低风险"))
        elif "回调" in bollinger_signal:
            signals.append(("布林带", "卖出信号", "低风险"))
        
        # 移动平均线信号
        trend = self.calculate_trend()
        if "上涨" in trend:
            signals.append(("移动平均线", "买入信号", "低风险"))
        elif "下跌" in trend:
            signals.append(("移动平均线", "卖出信号", "中风险"))
        
        return signals
    
    def calculate_risk_levels(self):
        """计算风险控制水平"""
        supports = self.data['technical_indicators']['support_levels']
        
        # 止损位：最近支撑位下方2%
        stop_loss = min(supports) * 0.98
        
        # 止盈位：基于风险回报比1:2
        risk = self.current_price - stop_loss
        take_profit = self.current_price + risk * 2
        
        # 移动止损位：50日均线
        trailing_stop = self.data['technical_indicators']['ma_50'] * 0.97
        
        return {
            'stop_loss': round(stop_loss, 2),
            'take_profit': round(take_profit, 2),
            'trailing_stop': round(trailing_stop, 2),
            'risk_reward_ratio': 2.0
        }
    
    def generate_report(self):
        """生成技术分析报告"""
        report = {
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'current_price': self.current_price,
            'trend_analysis': {
                'trend': self.calculate_trend(),
                'ma_50': self.data['technical_indicators']['ma_50'],
                'ma_200': self.data['technical_indicators']['ma_200'],
                'price_vs_ma50': round((self.current_price - self.data['technical_indicators']['ma_50']) / self.data['technical_indicators']['ma_50'] * 100, 2)
            },
            'indicator_analysis': {
                'rsi': {
                    'value': self.data['technical_indicators']['rsi_14'],
                    'status': self.analyze_rsi()[0],
                    'signal': self.analyze_rsi()[1]
                },
                'macd': {
                    'value': self.data['technical_indicators']['macd'],
                    'signal_line': self.data['technical_indicators']['macd_signal'],
                    'histogram': self.data['technical_indicators']['macd_histogram'],
                    'status': self.analyze_macd()[0],
                    'signal': self.analyze_macd()[1]
                },
                'bollinger': {
                    'upper': self.data['technical_indicators']['bollinger_upper'],
                    'middle': self.data['technical_indicators']['bollinger_middle'],
                    'lower': self.data['technical_indicators']['bollinger_lower'],
                    'status': self.analyze_bollinger()[0],
                    'signal': self.analyze_bollinger()[1]
                }
            },
            'key_levels': self.calculate_support_resistance(),
            'volume_analysis': {
                'current_volume': self.data['market_data']['volume'],
                'avg_volume': self.data['market_data']['avg_volume'],
                'status': self.analyze_volume()[0],
                'signal': self.analyze_volume()[1]
            },
            'trading_signals': self.generate_signals(),
            'risk_management': self.calculate_risk_levels(),
            'technical_rating': self.calculate_technical_rating()
        }
        
        return report
    
    def calculate_technical_rating(self):
        """计算技术面综合评级"""
        score = 0
        max_score = 10
        
        # 趋势评分（0-3分）
        trend = self.calculate_trend()
        if "上涨" in trend:
            score += 3
        elif "盘整" in trend:
            score += 2
        elif "震荡" in trend:
            score += 1
        
        # RSI评分（0-2分）
        rsi_status, rsi_signal = self.analyze_rsi()
        if "超卖" in rsi_status or "看涨" in rsi_signal:
            score += 2
        elif "中性" in rsi_signal:
            score += 1
        
        # MACD评分（0-2分）
        macd_status, macd_signal = self.analyze_macd()
        if "金叉" in macd_status or "看涨" in macd_signal:
            score += 2
        elif "粘合" in macd_status:
            score += 1
        
        # 支撑阻力评分（0-3分）
        levels = self.calculate_support_resistance()
        if levels['support_distance_pct'] < 3 and levels['support_strength'] == '强':
            score += 3
        elif levels['support_distance_pct'] < 6:
            score += 2
        else:
            score += 1
        
        # 计算评级
        rating_pct = score / max_score * 100
        
        if rating_pct >= 80:
            return "强烈买入", rating_pct
        elif rating_pct >= 60:
            return "买入", rating_pct
        elif rating_pct >= 40:
            return "持有", rating_pct
        elif rating_pct >= 20:
            return "减持", rating_pct
        else:
            return "卖出", rating_pct

def main():
    """主函数"""
    # 加载市场数据
    with open('/Users/mac/Documents/ai/learnclaudecode/learnclaudecode/data_collection/market_data/alibaba_market_data.json', 'r') as f:
        market_data = json.load(f)
    
    # 创建技术分析器
    analyzer = TechnicalAnalyzer(market_data)
    
    # 生成分析报告
    report = analyzer.generate_report()
    
    # 保存报告
    with open('/Users/mac/Documents/ai/learnclaudecode/learnclaudecode/alibaba_technical_analysis_report.json', 'w') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print("技术分析报告已生成！")
    print(f"当前价格: ${report['current_price']}")
    print(f"趋势分析: {report['trend_analysis']['trend']}")
    print(f"技术评级: {report['technical_rating'][0]} ({report['technical_rating'][1]:.1f}%)")
    
    # 打印交易信号
    print("\n交易信号:")
    for signal in report['trading_signals']:
        print(f"  {signal[0]}: {signal[1]} ({signal[2]})")
    
    # 打印风险控制
    print("\n风险控制:")
    print(f"  止损位: ${report['risk_management']['stop_loss']}")
    print(f"  止盈位: ${report['risk_management']['take_profit']}")
    print(f"  移动止损: ${report['risk_management']['trailing_stop']}")

if __name__ == "__main__":
    main()