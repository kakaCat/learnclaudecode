# CDP JSON 解析错误分析报告

## 错误现象

```python
json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)
```

**错误位置**: `pychrome/tab.py:122` 的 `_recv_loop` 方法中

**错误堆栈**:
```
File "/opt/miniconda3/lib/python3.12/site-packages/pychrome/tab.py", line 122, in _recv_loop
    message = json.loads(message_json)
```

## 根本原因

### 1. WebSocket 连接问题

`pychrome` 库通过 WebSocket 与 Chrome DevTools Protocol 通信。当 WebSocket 收到**空消息**或**非 JSON 格式消息**时，`json.loads()` 会抛出此错误。

### 2. 触发场景

从日志分析，错误发生在：
- Agent 执行了长时间的 LLM 调用（49秒）
- 期间浏览器保持连接但无操作
- WebSocket 可能因以下原因发送空帧：
  - **Chrome 浏览器内部错误**
  - **网络超时/不稳定**
  - **Chrome 发送心跳包**（某些版本）
  - **页面崩溃或重定向**

### 3. 代码层面的问题

**当前代码**（cdp_tool.py:290-301）:
```python
try:
    tab.start()
except Exception as e:
    logger.warning(f"Tab connection failed, retrying: {e}")
    # 重置 browser 并重试一次
    global _browser
    _browser = None
    browser = _get_browser()
    tabs = browser.list_tab()
    if not tabs:
        return "Error: No browser tabs available after retry"
    tab = tabs[0]
    tab.start()
```

**问题**:
- 只捕获了 `tab.start()` 的异常
- 没有捕获后续操作（navigate, evaluate 等）中的 WebSocket 错误
- `pychrome` 的 `_recv_loop` 在后台线程运行，异常不会被主线程捕获

## 解决方案

### 方案 1: 增强错误处理（推荐）

在每个 CDP 操作外层添加 try-except，捕获所有可能的异常：

```python
def cdp_browser(...):
    tab = None
    try:
        # ... 现有代码 ...

        if action == "navigate":
            try:
                tab.Page.navigate(url=url, _timeout=15)
                tab.wait(2)
                result = tab.Runtime.evaluate(expression="document.readyState")
                # ...
            except Exception as e:
                logger.error(f"Navigate failed: {e}")
                # 尝试重新连接
                return _retry_with_new_connection(action, url=url, ...)

    except Exception as e:
        logger.error(f"CDP operation failed: {e}", exc_info=True)
        return f"❌ Browser operation failed: {str(e)}"
    finally:
        if tab:
            try:
                tab.stop()
            except:
                pass
```

### 方案 2: 使用连接池和健康检查

```python
def _ensure_healthy_connection(tab):
    """确保连接健康，否则重新创建"""
    try:
        # 简单的健康检查
        tab.Runtime.evaluate(expression="1+1", _timeout=2)
        return tab
    except Exception as e:
        logger.warning(f"Connection unhealthy: {e}")
        # 重新创建连接
        global _browser
        _browser = None
        browser = _get_browser()
        tabs = browser.list_tab()
        if tabs:
            new_tab = tabs[0]
            new_tab.start()
            return new_tab
        raise RuntimeError("Cannot create healthy connection")
```

### 方案 3: 修补 pychrome 库（高级）

创建一个包装器，捕获 `_recv_loop` 的异常：

```python
import pychrome
from pychrome import Tab

class RobustTab(Tab):
    def _recv_loop(self):
        """重写接收循环，增加错误处理"""
        while self.status == "started":
            try:
                message_json = self.ws.recv()
                if not message_json:  # 空消息
                    logger.warning("Received empty message from Chrome")
                    continue
                message = json.loads(message_json)
                # ... 原有逻辑 ...
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error: {e}, raw: {message_json[:100]}")
                continue  # 跳过这条消息，继续接收
            except Exception as e:
                logger.error(f"Recv loop error: {e}")
                break
```

### 方案 4: 添加超时和重试机制

```python
def _safe_cdp_call(func, *args, max_retries=3, timeout=10, **kwargs):
    """安全的 CDP 调用，带重试"""
    for attempt in range(max_retries):
        try:
            # 设置超时
            result = func(*args, **{**kwargs, '_timeout': timeout})
            return result
        except Exception as e:
            logger.warning(f"CDP call failed (attempt {attempt+1}/{max_retries}): {e}")
            if attempt == max_retries - 1:
                raise
            time.sleep(1)  # 等待后重试
```

## 推荐实施步骤

### 第一步：立即修复（最小改动）

在 `cdp_tool.py` 的每个操作中添加异常处理：

```python
if action == "navigate":
    if not url:
        return "Error: url required for navigate"
    try:
        tab.Page.navigate(url=url, _timeout=15)
        tab.wait(2)
        result = tab.Runtime.evaluate(expression="document.readyState")
        state = result.get("result", {}).get("value", "")
        if state != "complete":
            tab.wait(wait_time)
        return f"✅ Navigated to {url}"
    except Exception as e:
        logger.error(f"Navigate failed: {e}", exc_info=True)
        return f"❌ Navigation failed: {str(e)}\nTry restarting Chrome or check the URL"
```

### 第二步：添加连接健康检查

在 `_get_browser()` 后添加：

```python
def _get_healthy_tab():
    """获取健康的 tab 连接"""
    browser = _get_browser()
    tabs = browser.list_tab()
    if not tabs:
        raise RuntimeError("No browser tabs available")

    tab = tabs[0]
    try:
        tab.start()
        # 健康检查
        tab.Runtime.evaluate(expression="1+1", _timeout=2)
        return tab
    except Exception as e:
        logger.warning(f"Tab unhealthy, recreating: {e}")
        # 重置并重试
        global _browser
        _browser = None
        browser = _get_browser()
        tabs = browser.list_tab()
        if not tabs:
            raise RuntimeError("No tabs after reset")
        tab = tabs[0]
        tab.start()
        return tab
```

### 第三步：添加 finally 清理

```python
def cdp_browser(...):
    tab = None
    try:
        tab = _get_healthy_tab()
        # ... 操作 ...
    except Exception as e:
        logger.error(f"CDP error: {e}", exc_info=True)
        return f"❌ Error: {str(e)}"
    finally:
        if tab:
            try:
                tab.stop()
            except:
                pass
```

## 预防措施

1. **定期重启 Chrome**: 长时间运行后重启浏览器
2. **减少等待时间**: 避免长时间空闲连接
3. **使用无头模式**: `--headless=new` 更稳定
4. **监控连接状态**: 定期健康检查
5. **日志记录**: 记录所有 WebSocket 异常

## 临时解决方案（用户侧）

如果遇到此错误：

1. **重启 Chrome**:
   ```bash
   pkill -f "chrome.*remote-debugging"
   google-chrome --remote-debugging-port=9222 --headless=new
   ```

2. **检查 Chrome 进程**:
   ```bash
   lsof -i :9222
   ```

3. **清理僵尸进程**:
   ```bash
   ps aux | grep chrome | grep 9222
   kill -9 <PID>
   ```

## 相关文件

- [cdp_tool.py:290-301](../backend/app/tools/implementations/integration/cdp_tool.py#L290-L301) - 当前错误处理
- [pychrome/tab.py:122](https://github.com/fate0/pychrome/blob/master/pychrome/tab.py#L122) - 错误源头

## 参考

- [pychrome Issue #50](https://github.com/fate0/pychrome/issues/50) - 类似问题
- [Chrome DevTools Protocol](https://chromedevtools.github.io/devtools-protocol/) - 官方文档
