# CDP 工具连接管理修复

## 问题描述

### 原始错误
```python
json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)
```

**错误位置**: `pychrome/tab.py:122` 的 WebSocket 接收循环

### 根本原因

1. **频繁重连问题**: 原代码在每次操作后的 `finally` 块中调用 `tab.stop()`，导致：
   - 每次操作都创建和销毁连接
   - WebSocket 连接频繁断开重连
   - 后台线程累积，资源泄漏

2. **WebSocket 异常未处理**: 当 Chrome 发送空消息或非 JSON 消息时：
   - `pychrome` 的 `_recv_loop` 在后台线程运行
   - JSON 解析异常不会被主线程捕获
   - 连接状态未清理，导致后续操作失败

3. **无显式关闭机制**: Agent 无法主动管理浏览器生命周期

## 修复方案

### 1. 连接复用机制

**新增全局变量**:
```python
_active_tab = None  # 保持活跃的 tab 连接，避免频繁重连
```

**新增函数 `_get_or_create_tab()`**:
```python
def _get_or_create_tab():
    """获取或创建活跃的 tab 连接，复用以避免频繁重连"""
    global _active_tab

    browser = _get_browser()
    tabs = browser.list_tab()

    if not tabs:
        raise RuntimeError("No browser tabs available")

    # 如果已有活跃 tab，检查是否仍然有效
    if _active_tab is not None:
        try:
            # 简单的健康检查
            _active_tab.Runtime.evaluate(expression="1+1", _timeout=2)
            return _active_tab
        except Exception as e:
            logger.warning(f"Active tab unhealthy: {e}")
            try:
                _active_tab.stop()
            except:
                pass
            _active_tab = None

    # 创建新的 tab 连接
    tab = tabs[0]
    try:
        tab.start()
        _active_tab = tab
        logger.info("Created new tab connection")
        return tab
    except Exception as e:
        logger.error(f"Failed to start tab: {e}")
        raise RuntimeError(f"Failed to start tab: {e}")
```

**优化 `_get_browser()`**:
```python
def _get_browser():
    """Get or create browser connection."""
    global _browser

    # ... 检查服务可用性 ...

    # 复用现有连接（如果存在）
    if _browser is not None:
        try:
            # 简单测试连接是否有效
            _browser.list_tab()
            return _browser
        except Exception as e:
            logger.warning(f"Existing browser connection invalid: {e}")
            _browser = None

    # 创建新连接
    try:
        import pychrome
        _browser = pychrome.Browser(url="http://127.0.0.1:9222")
        logger.info("Created new browser connection")
    except Exception as e:
        _browser = None
        raise RuntimeError(f"Failed to connect to Chrome: {e}")
    return _browser
```

### 2. 新增 `close` 操作

**功能**: 允许 Agent 显式关闭浏览器连接

```python
@tool(tags=["subagent"])
def cdp_browser(
    action: Literal["navigate", "screenshot", "execute", "eval", "content",
                    "click", "check_health", "wait_for", "inspect", "close"],
    ...
) -> str:
    """
    ...
    - close: Close browser connection and cleanup resources
    ...
    """
    global _active_tab, _browser

    # 关闭连接
    if action == "close":
        closed_items = []

        if _active_tab is not None:
            try:
                _active_tab.stop()
                closed_items.append("tab connection")
            except Exception as e:
                logger.debug(f"Failed to stop tab: {e}")
            _active_tab = None

        if _browser is not None:
            _browser = None
            closed_items.append("browser instance")

        if closed_items:
            return f"✅ Closed: {', '.join(closed_items)}"
        else:
            return "✅ No active connections to close"
```

### 3. 移除 `finally` 块中的关闭逻辑

**修改前**:
```python
def cdp_browser(...):
    tab = None
    try:
        # ... 操作 ...
    except Exception as e:
        return f"Error: {str(e)}"
    finally:
        # 确保关闭 tab 连接
        if tab is not None:
            try:
                tab.stop()
            except Exception as e:
                logger.debug(f"Failed to stop tab: {e}")
```

**修改后**:
```python
def cdp_browser(...):
    global _active_tab, _browser

    try:
        # 使用复用的 tab 连接
        tab = _get_or_create_tab()
        # ... 操作 ...
    except Exception as e:
        logger.error(f"CDP browser error: {e}", exc_info=True)
        # 连接错误时，清理状态以便下次重试
        if "WebSocket" in str(e) or "JSON" in str(e):
            logger.warning("WebSocket/JSON error detected, cleaning up connection")
            if _active_tab is not None:
                try:
                    _active_tab.stop()
                except:
                    pass
                _active_tab = None
        return f"Error: {str(e)}"
    # 注意：不再在 finally 中关闭 tab，保持连接复用
```

### 4. 增强错误处理

**WebSocket/JSON 错误自动清理**:
```python
except Exception as e:
    logger.error(f"CDP browser error: {e}", exc_info=True)
    # 连接错误时，清理状态以便下次重试
    if "WebSocket" in str(e) or "JSON" in str(e):
        logger.warning("WebSocket/JSON error detected, cleaning up connection")
        if _active_tab is not None:
            try:
                _active_tab.stop()
            except:
                pass
            _active_tab = None
    return f"Error: {str(e)}"
```

### 5. 更新 `reset_cdp_cache()`

```python
def reset_cdp_cache():
    """重置 CDP 可用性缓存（用于测试或重启后）"""
    global _browser_available, _browser, _active_tab
    _browser_available = None
    _browser = None
    if _active_tab is not None:
        try:
            _active_tab.stop()
        except:
            pass
        _active_tab = None
```

## 使用方式

### Agent 使用示例

```python
# 1. 打开浏览器并导航
result = cdp_browser(action="navigate", url="https://www.example.com")

# 2. 多次操作（自动复用连接）
content = cdp_browser(action="content")
screenshot = cdp_browser(action="screenshot", output_path="page.png")

# 3. 完成后显式关闭（可选）
cdp_browser(action="close")
```

### 连接生命周期

```
第一次调用 → 创建连接 → 保持活跃
    ↓
后续调用 → 复用连接 → 健康检查
    ↓
遇到错误 → 自动清理 → 下次重建
    ↓
显式关闭 → 释放资源 → 下次重建
```

## 优势

### 修复前
- ❌ 每次操作都创建/销毁连接
- ❌ WebSocket 频繁断开重连
- ❌ 后台线程累积，资源泄漏
- ❌ JSON 解析错误导致崩溃
- ❌ 无法主动管理连接

### 修复后
- ✅ 连接复用，减少开销
- ✅ 健康检查，自动恢复
- ✅ WebSocket 错误自动清理
- ✅ 显式关闭，资源可控
- ✅ 更好的日志和错误处理

## 测试

运行测试脚本：
```bash
python scripts/test_cdp_close.py
```

测试内容：
1. 连接复用测试
2. 显式关闭测试
3. 错误恢复测试
4. 健康检查测试

## 注意事项

1. **长时间运行**: 如果 Agent 长时间运行，建议定期调用 `close` 释放资源
2. **错误恢复**: WebSocket/JSON 错误会自动清理连接，下次调用会重建
3. **手动重启**: 如果 Chrome 崩溃，调用 `close` 后重新操作即可
4. **并发使用**: 当前实现使用单一全局连接，不支持并发

## 相关文件

- [cdp_tool.py](../backend/app/tools/implementations/integration/cdp_tool.py) - 主要修改
- [test_cdp_close.py](../scripts/test_cdp_close.py) - 测试脚本
- [cdp_json_error_analysis.md](./cdp_json_error_analysis.md) - 错误分析

## 版本历史

- **2026-03-13**: 修复连接管理问题，新增 `close` 操作
