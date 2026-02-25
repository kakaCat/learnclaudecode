#!/usr/bin/env python3
"""
获取真实股票数据的脚本
使用免费的金融数据API获取实时股票价格
"""

import sys
import json
import time
from datetime import datetime
import requests
from typing import Dict, Optional, Tuple

class RealStockDataFetcher:
    """真实股票数据获取器"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        
    def get_wuliangye_real_price(self) -> Dict:
        """获取五粮液真实股票价格"""
        
        symbol = "000858.SZ"  # 五粮液A股代码
        
        # 尝试多个数据源
        data_sources = [
            self._try_yahoo_finance,
            self._try_tencent_api,
            self._try_sina_api,
            self._try_eastmoney_api
        ]
        
        for source_func in data_sources:
            try:
                print(f"尝试数据源: {source_func.__name__}")
                data = source_func(symbol)
                if data and data.get('price'):
                    print(f"✓ 成功从 {source_func.__name__} 获取数据")
                    return data
            except Exception as e:
                print(f"✗ {source_func.__name__} 失败: {e}")
                continue
        
        # 所有数据源都失败时返回模拟数据（作为后备）
        print("⚠️ 所有真实数据源均失败，返回模拟数据")
        return self._get_fallback_data(symbol)
    
    def _try_yahoo_finance(self, symbol: str) -> Optional[Dict]:
        """尝试从Yahoo Finance获取数据"""
        try:
            # Yahoo Finance API (免费但可能需要代理)
            yahoo_symbol = "000858.SZ"  # 对于A股，可能需要转换为Yahoo格式
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_symbol}"
            
            params = {
                'range': '1d',
                'interval': '1m',
                'includePrePost': 'false'
            }
            
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            # 解析Yahoo Finance响应
            if 'chart' in data and 'result' in data['chart']:
                result = data['chart']['result'][0]
                meta = result['meta']
                
                price = meta.get('regularMarketPrice')
                prev_close = meta.get('previousClose')
                change = price - prev_close if price and prev_close else 0
                change_percent = (change / prev_close * 100) if prev_close else 0
                
                return {
                    'symbol': symbol,
                    'name': '五粮液',
                    'price': round(price, 2) if price else None,
                    'change': round(change, 2) if change else 0,
                    'change_percent': round(change_percent, 2) if change_percent else 0,
                    'open': round(meta.get('regularMarketOpen', 0), 2),
                    'high': round(meta.get('regularMarketDayHigh', 0), 2),
                    'low': round(meta.get('regularMarketDayLow', 0), 2),
                    'volume': meta.get('regularMarketVolume', 0),
                    'source': 'yahoo_finance',
                    'timestamp': datetime.now().isoformat()
                }
        except Exception as e:
            raise Exception(f"Yahoo Finance API错误: {e}")
        
        return None
    
    def _try_tencent_api(self, symbol: str) -> Optional[Dict]:
        """尝试从腾讯财经API获取数据"""
        try:
            # 腾讯财经API
            url = f"http://qt.gtimg.cn/q={symbol}"
            
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            content = response.text
            # 解析腾讯财经格式: v_sz000858="1~五粮液~000858~148.50~149.00~..."
            if '~' in content:
                parts = content.split('~')
                if len(parts) > 3:
                    name = parts[1]
                    price = float(parts[3]) if parts[3] else 0
                    prev_close = float(parts[4]) if parts[4] else 0
                    change = price - prev_close
                    change_percent = (change / prev_close * 100) if prev_close else 0
                    
                    return {
                        'symbol': symbol,
                        'name': name,
                        'price': round(price, 2),
                        'change': round(change, 2),
                        'change_percent': round(change_percent, 2),
                        'open': float(parts[5]) if len(parts) > 5 and parts[5] else 0,
                        'high': float(parts[33]) if len(parts) > 33 and parts[33] else 0,
                        'low': float(parts[34]) if len(parts) > 34 and parts[34] else 0,
                        'volume': int(parts[6]) if len(parts) > 6 and parts[6] else 0,
                        'turnover': float(parts[37]) if len(parts) > 37 and parts[37] else 0,
                        'source': 'tencent_finance',
                        'timestamp': datetime.now().isoformat()
                    }
        except Exception as e:
            raise Exception(f"腾讯财经API错误: {e}")
        
        return None
    
    def _try_sina_api(self, symbol: str) -> Optional[Dict]:
        """尝试从新浪财经API获取数据"""
        try:
            # 新浪财经API
            sina_symbol = symbol.replace('.SZ', '').replace('.SH', '')
            url = f"http://hq.sinajs.cn/list=sz{sina_symbol}"
            
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            content = response.text
            # 解析新浪格式: var hq_str_sz000858="五粮液,148.50,149.00,..."
            if '=' in content:
                data_str = content.split('=')[1].strip('";\n')
                parts = data_str.split(',')
                
                if len(parts) > 1:
                    name = parts[0]
                    price = float(parts[3]) if parts[3] else 0
                    prev_close = float(parts[2]) if parts[2] else 0
                    change = price - prev_close
                    change_percent = (change / prev_close * 100) if prev_close else 0
                    
                    return {
                        'symbol': symbol,
                        'name': name,
                        'price': round(price, 2),
                        'change': round(change, 2),
                        'change_percent': round(change_percent, 2),
                        'open': float(parts[1]) if parts[1] else 0,
                        'high': float(parts[4]) if len(parts) > 4 and parts[4] else 0,
                        'low': float(parts[5]) if len(parts) > 5 and parts[5] else 0,
                        'volume': int(parts[8]) if len(parts) > 8 and parts[8] else 0,
                        'turnover': float(parts[9]) if len(parts) > 9 and parts[9] else 0,
                        'source': 'sina_finance',
                        'timestamp': datetime.now().isoformat()
                    }
        except Exception as e:
            raise Exception(f"新浪财经API错误: {e}")
        
        return None
    
    def _try_eastmoney_api(self, symbol: str) -> Optional[Dict]:
        """尝试从东方财富API获取数据"""
        try:
            # 东方财富API
            url = f"https://push2.eastmoney.com/api/qt/stock/get"
            
            params = {
                'secid': f'0.{symbol.replace(".SZ", "")}',
                'fields': 'f43,f44,f45,f46,f47,f48,f49,f50,f51,f52,f55,f57,f58,f60,f84,f86,f169,f170',
                'ut': 'fa5fd1943c7b386f172d6893dbfba10b',
                'invt': '2',
                'fltt': '2'
            }
            
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('rc') == 0 and 'data' in data:
                stock_data = data['data']
                
                price = stock_data.get('f43')  # 当前价格
                prev_close = stock_data.get('f60')  # 昨收
                change = stock_data.get('f169')  # 涨跌额
                change_percent = stock_data.get('f170')  # 涨跌幅
                
                return {
                    'symbol': symbol,
                    'name': stock_data.get('f58', '五粮液'),
                    'price': round(price / 100, 2) if price else 0,  # 东方财富价格单位是分
                    'change': round(change / 100, 2) if change else 0,
                    'change_percent': round(change_percent / 100, 2) if change_percent else 0,
                    'open': round(stock_data.get('f46', 0) / 100, 2),
                    'high': round(stock_data.get('f44', 0) / 100, 2),
                    'low': round(stock_data.get('f45', 0) / 100, 2),
                    'volume': stock_data.get('f47', 0),
                    'turnover': stock_data.get('f48', 0),
                    'source': 'eastmoney',
                    'timestamp': datetime.now().isoformat()
                }
        except Exception as e:
            raise Exception(f"东方财富API错误: {e}")
        
        return None
    
    def _get_fallback_data(self, symbol: str) -> Dict:
        """获取后备数据（模拟数据）"""
        import random
        
        base_price = 148.50
        variation = random.uniform(-2.0, 2.0)
        current_price = base_price + variation
        change = current_price - base_price
        change_percent = (change / base_price) * 100
        
        return {
            'symbol': symbol,
            'name': '五粮液',
            'price': round(current_price, 2),
            'change': round(change, 2),
            'change_percent': round(change_percent, 2),
            'open': round(base_price + random.uniform(-1, 1), 2),
            'high': round(base_price + random.uniform(0, 3), 2),
            'low': round(base_price + random.uniform(-3, 0), 2),
            'volume': random.randint(8000000, 15000000),
            'turnover': round(random.uniform(1000000000, 2500000000), 2),
            'source': 'fallback_simulation',
            'timestamp': datetime.now().isoformat(),
            'note': '⚠️ 此为模拟数据，真实数据获取失败'
        }
    
    def print_stock_info(self, stock_data: Dict):
        """打印股票信息"""
        
        print("\n" + "=" * 60)
        print(f"📊 {stock_data['name']} ({stock_data['symbol']})")
        print("=" * 60)
        
        # 数据源信息
        source_map = {
            'yahoo_finance': '雅虎财经',
            'tencent_finance': '腾讯财经',
            'sina_finance': '新浪财经',
            'eastmoney': '东方财富',
            'fallback_simulation': '模拟数据'
        }
        
        source_name = source_map.get(stock_data.get('source', ''), stock_data.get('source', '未知'))
        print(f"📡 数据来源: {source_name}")
        
        if stock_data.get('note'):
            print(f"⚠️  备注: {stock_data['note']}")
        
        print("-" * 60)
        
        # 价格显示
        price_str = f"💰 当前价格: {stock_data['price']} CNY"
        
        # 涨跌显示
        change = stock_data.get('change', 0)
        change_percent = stock_data.get('change_percent', 0)
        
        if change >= 0:
            change_str = f"📈 涨跌: +{change} (+{change_percent}%)"
            color_start = "\033[92m"  # 绿色
            color_end = "\033[0m"
        else:
            change_str = f"📉 涨跌: {change} ({change_percent}%)"
            color_start = "\033[91m"  # 红色
            color_end = "\033[0m"
        
        print(price_str)
        print(f"{color_start}{change_str}{color_end}")
        
        # 其他关键数据
        if stock_data.get('open'):
            print(f"🌅 开盘价: {stock_data['open']}")
        if stock_data.get('high'):
            print(f"⬆️  最高价: {stock_data['high']}")
        if stock_data.get('low'):
            print(f"⬇️  最低价: {stock_data['low']}")
        if stock_data.get('volume'):
            volume_str = f"{stock_data['volume']:,}" if isinstance(stock_data['volume'], int) else stock_data['volume']
            print(f"📈 成交量: {volume_str} 股")
        if stock_data.get('turnover'):
            turnover_str = f"{stock_data['turnover']:,.2f}" if isinstance(stock_data['turnover'], (int, float)) else stock_data['turnover']
            print(f"💵 成交额: {turnover_str} 元")
        
        print(f"🕒 查询时间: {stock_data.get('timestamp', datetime.now().isoformat())}")
        print("=" * 60)
        
        # 简单分析
        print("\n💡 简要分析:")
        
        if stock_data.get('source') == 'fallback_simulation':
            print("  当前显示的是模拟数据，真实数据获取失败")
            print("  建议检查网络连接或稍后重试")
        else:
            if change_percent > 2:
                print("  今日表现强劲，涨幅超过2%")
            elif change_percent > 0.5:
                print("  今日表现良好，小幅上涨")
            elif change_percent < -2:
                print("  今日表现疲软，跌幅超过2%")
            elif change_percent < -0.5:
                print("  今日表现偏弱，小幅下跌")
            else:
                print("  今日表现平稳，波动较小")
            
            price = stock_data.get('price', 0)
            if price > 150:
                print("  价格处于150元以上高位区间")
            elif price < 145:
                print("  价格处于145元以下低位区间")
            else:
                print("  价格处于145-150元中间区间")

def main():
    """主函数"""
    print("正在获取五粮液真实股票价格...")
    print("尝试连接多个金融数据源...")
    
    try:
        fetcher = RealStockDataFetcher()
        stock_data = fetcher.get_wuliangye_real_price()
        
        fetcher.print_stock_info(stock_data)
        
        # 保存到文件
        output_file = "wuliangye_real_price.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(stock_data, f, ensure_ascii=False, indent=2)
        
        print(f"\n✅ 数据已保存到 {output_file}")
        
        # 显示文件内容
        print(f"\n📄 保存的数据内容:")
        print(json.dumps(stock_data, ensure_ascii=False, indent=2))
        
    except Exception as e:
        print(f"❌ 获取真实数据失败: {e}")
        print("\n💡 可能的原因:")
        print("  1. 网络连接问题")
        print("  2. API服务暂时不可用")
        print("  3. 股票代码格式问题")
        print("\n🔧 建议:")
        print("  1. 检查网络连接")
        print("  2. 稍后重试")
        print("  3. 使用专业的股票交易软件查看实时数据")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())