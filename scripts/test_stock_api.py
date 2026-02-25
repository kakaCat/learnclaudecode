#!/usr/bin/env python3
"""
测试股票API的简单脚本
"""

import requests
import json
from datetime import datetime

def test_apis():
    """测试各个股票API"""
    
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    })
    
    print("测试各个股票数据API...\n")
    
    # 测试1: 新浪财经
    print("1. 测试新浪财经API:")
    try:
        url = "http://hq.sinajs.cn/list=sz000858"
        response = session.get(url, timeout=5)
        print(f"  状态码: {response.status_code}")
        print(f"  响应长度: {len(response.text)}")
        if response.status_code == 200:
            content = response.text
            print(f"  响应内容: {content[:200]}...")
    except Exception as e:
        print(f"  错误: {e}")
    
    print("\n2. 测试腾讯财经API:")
    try:
        url = "http://qt.gtimg.cn/q=sz000858"
        response = session.get(url, timeout=5)
        print(f"  状态码: {response.status_code}")
        print(f"  响应长度: {len(response.text)}")
        if response.status_code == 200:
            content = response.text
            print(f"  响应内容: {content[:200]}...")
    except Exception as e:
        print(f"  错误: {e}")
    
    print("\n3. 测试东方财富API:")
    try:
        url = "https://push2.eastmoney.com/api/qt/stock/get"
        params = {
            'secid': '0.000858',
            'fields': 'f43,f44,f45,f46,f47,f48,f49,f50,f51,f52,f55,f57,f58,f60,f84,f86,f169,f170',
            'ut': 'fa5fd1943c7b386f172d6893dbfba10b',
            'invt': '2',
            'fltt': '2'
        }
        response = session.get(url, params=params, timeout=5)
        print(f"  状态码: {response.status_code}")
        print(f"  响应长度: {len(response.text)}")
        if response.status_code == 200:
            data = response.json()
            print(f"  完整响应: {json.dumps(data, ensure_ascii=False, indent=2)}")
    except Exception as e:
        print(f"  错误: {e}")
    
    print("\n4. 测试雪球API:")
    try:
        url = "https://stock.xueqiu.com/v5/stock/quote.json"
        params = {
            'symbol': 'SZ000858',
            'extend': 'detail'
        }
        response = session.get(url, params=params, timeout=5)
        print(f"  状态码: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"  响应: {json.dumps(data, ensure_ascii=False, indent=2)[:500]}...")
    except Exception as e:
        print(f"  错误: {e}")

if __name__ == "__main__":
    test_apis()