# A股股票查询工具使用说明

## 工具概述

本工具提供了查询A股（沪深京交易所）股票信息的功能，支持以下查询类型：

- **当前实时行情**：最新价格、涨跌幅、成交量等
- **基本信息**：公司名称、行业、市值、市盈率等
- **历史数据**：最近5个交易日的历史价格数据

## 使用方法

### 1. 单个股票查询

```python
from backend.app.tools import stock_a_query

# 查询当前价格
result = stock_a_query.invoke({"symbol": "000001", "query_type": "current"})

# 查询基本信息  
result = stock_a_query.invoke({"symbol": "600519", "query_type": "basic"})

# 查询历史数据
result = stock_a_query.invoke({"symbol": "600036", "query_type": "history"})
```

### 2. 批量股票查询

```python
from backend.app.tools import stock_a_batch_query

# 批量查询多个股票的当前价格
symbols = ["000001", "600519", "600036"]
result = stock_a_batch_query.invoke({"symbols": symbols, "query_type": "current"})
```

## 股票代码格式

支持多种股票代码格式：

- **6位纯数字**：`000001`、`600519`
- **带市场前缀**：`sz000001`、`sh600519`、`bj830799`
- **大写前缀**：`SZ000001`、`SH600519`

## 返回数据结构

### 当前行情 (query_type="current")
```json
{
  "code": "000001",
  "name": "平安银行",
  "price": 12.34,
  "change": 1.23,
  "volume": 1000000,
  "amount": 12345678.90,
  "high": 12.50,
  "low": 12.20,
  "open": 12.25,
  "close": 12.10,
  "market": "深市",
  "query_type": "current"
}
```

### 基本信息 (query_type="basic")
```json
{
  "code": "600519",
  "name": "贵州茅台",
  "market": "沪市",
  "industry": "白酒",
  "total_shares": "12.56亿",
  "circulating_shares": "10.23亿", 
  "total_value": "2.1万亿",
  "circulating_value": "1.8万亿",
  "pe": "35.67",
  "pb": "12.34",
  "listing_date": "2001-08-27",
  "query_type": "basic"
}
```

### 历史数据 (query_type="history")
```json
{
  "code": "600036",
  "name": "招商银行",
  "history": [
    {
      "date": "2024-01-15",
      "open": 35.20,
      "high": 35.80,
      "low": 34.90,
      "close": 35.50,
      "volume": 500000,
      "amount": 176500000.0
    }
  ],
  "query_type": "history"
}
```

## 错误处理

当查询失败时（如网络问题、股票代码不存在等），工具会返回包含错误信息的字典：

```json
{
  "error": "查询失败: 具体错误信息",
  "code": "000001", 
  "query_type": "current",
  "suggestion": "请检查网络连接，或稍后再试。也可以尝试其他股票代码。"
}
```

## 注意事项

1. **网络依赖**：工具依赖akshare库从网络获取数据，请确保网络连接正常
2. **API限制**：频繁查询可能会触发API限流，建议合理控制查询频率
3. **数据延迟**：实时行情可能存在几分钟的延迟
4. **股票代码**：确保输入的股票代码正确有效

## 示例代码

```python
# 基本使用示例
from backend.app.tools import stock_a_query, stock_a_batch_query

# 查询单个股票
stock_info = stock_a_query.invoke({
    "symbol": "000001", 
    "query_type": "current"
})

if "error" not in stock_info:
    print(f"{stock_info['name']}({stock_info['code']}) 当前价格: {stock_info['price']}")
else:
    print(f"查询失败: {stock_info['error']}")

# 批量查询
stocks = ["000001", "600519", "600036"]
batch_result = stock_a_batch_query.invoke({
    "symbols": stocks,
    "query_type": "current"
})

for symbol, info in batch_result.items():
    if "error" not in info:
        print(f"{info['name']}: {info['price']}")
    else:
        print(f"{symbol}: 查询失败")
```