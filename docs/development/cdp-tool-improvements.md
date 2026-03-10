# CDP工具改进分析

## 问题分析

### 原始问题（来自 trace.jsonl）

**会话**: 20260310_013213
**任务**: 查询北京到上海明天的机票
**结果**: 失败 - 生成了"研究报告"而非实际查询结果

### 失败原因

1. **CDP服务未启动**
   - 所有CDP调用都返回"Chrome DevTools Protocol 服务未启动"
   - 端口9222无法连接

2. **Agent行为问题**
   - Turn 1-7: 主Agent和CDPBrowser子Agent都尝试使用CDP，但都失败
   - Turn 8: 主Agent切换到`search_lead`工具，生成了"研究报告"
   - Turn 10: 返回"2026年3月11日机票信息目前无法查询"

3. **违反记忆规则**
   ```
   ## 行为约束
   1. **禁止生成假报告**：无法获取实时数据时，明确说"任务失败"，不要生成"研究报告"
   ```

### 根本原因

- **工具层**: CDP工具只检查服务可用性，不尝试启动
- **Agent层**: Agent遇到CDP失败后，没有尝试启动服务，而是切换到其他工具

## 改进方案

### 1. 增强CDP工具自动启动能力

**文件**: `backend/app/tools/implementations/cdp_tool.py`

#### 新增函数: `_try_start_chrome()`

```python
def _try_start_chrome() -> tuple[bool, str]:
    """尝试自动启动Chrome（仅在未运行时）"""
    import subprocess
    import platform
    import time

    # 先检查是否已经运行
    available, _ = _check_cdp_available()
    if available:
        return (True, "Chrome already running")

    system = platform.system()
    chrome_commands = []

    if system == "Darwin":  # macOS
        chrome_commands = [
            ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
             "--remote-debugging-port=9222", "--headless", "--disable-gpu"],
            ["/Applications/Chromium.app/Contents/MacOS/Chromium",
             "--remote-debugging-port=9222", "--headless", "--disable-gpu"]
        ]
    elif system == "Linux":
        chrome_commands = [
            ["google-chrome", "--remote-debugging-port=9222", "--headless", "--disable-gpu"],
            ["chromium", "--remote-debugging-port=9222", "--headless", "--disable-gpu"],
            ["chromium-browser", "--remote-debugging-port=9222", "--headless", "--disable-gpu"]
        ]
    elif system == "Windows":
        chrome_commands = [
            ["C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
             "--remote-debugging-port=9222", "--headless", "--disable-gpu"],
            ["C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
             "--remote-debugging-port=9222", "--headless", "--disable-gpu"]
        ]

    # 尝试启动Chrome
    for cmd in chrome_commands:
        try:
            logger.info(f"Trying to start Chrome: {cmd[0]}")
            subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True  # 后台运行
            )
            # 等待启动
            time.sleep(3)
            # 检查是否成功
            available, _ = _check_cdp_available()
            if available:
                logger.info("Chrome started successfully")
                return (True, f"Chrome started: {cmd[0]}")
        except FileNotFoundError:
            continue
        except Exception as e:
            logger.warning(f"Failed to start {cmd[0]}: {e}")
            continue

    return (False, "Failed to start Chrome automatically")
```

#### 修改 `_get_browser()`

```python
def _get_browser():
    """Get or create browser connection."""
    global _browser

    # 先检查服务是否可用
    available, reason = _check_cdp_available()
    if not available:
        # 尝试自动启动Chrome
        logger.info("CDP not available, trying to start Chrome...")
        started, start_msg = _try_start_chrome()
        if started:
            logger.info(f"Chrome started: {start_msg}")
            # 重置缓存，重新检查
            global _browser_available
            _browser_available = None
            available, reason = _check_cdp_available()
            if not available:
                raise RuntimeError(f"Chrome started but still not available: {reason}")
        else:
            raise RuntimeError(f"{reason}\n\n{_check_cdp_available()[1]}")

    if _browser is None:
        try:
            import pychrome
            _browser = pychrome.Browser(url="http://127.0.0.1:9222")
        except Exception as e:
            raise RuntimeError(f"Failed to connect to Chrome: {e}")
    return _browser
```

### 2. 改进效果

#### Before（原始行为）
```
1. Agent调用cdp_browser(action="check_health")
2. 返回: "❌ Chrome DevTools Protocol 服务不可用"
3. Agent切换到search_lead工具
4. 生成"研究报告"（违反规则）
```

#### After（改进后）
```
1. Agent调用cdp_browser(action="navigate", url="...")
2. CDP工具检测到服务不可用
3. 自动尝试启动Chrome（macOS/Linux/Windows）
4. 启动成功 → 继续执行navigate
5. 或启动失败 → 返回明确错误信息
```

### 3. 优势

1. **用户体验改善**
   - 无需手动启动Chrome
   - 首次使用自动配置

2. **Agent行为改善**
   - 减少工具切换
   - 避免生成"假报告"

3. **跨平台支持**
   - macOS: Google Chrome / Chromium
   - Linux: google-chrome / chromium / chromium-browser
   - Windows: Chrome (Program Files / Program Files (x86))

### 4. 限制

1. **需要Chrome已安装**
   - 如果系统没有Chrome，仍然会失败
   - 但会返回明确的错误信息

2. **启动延迟**
   - 首次启动需要3秒等待
   - 后续调用使用已启动的实例

3. **权限问题**
   - 某些系统可能需要额外权限
   - Docker环境需要特殊配置

## 测试建议

### 测试场景1: 首次使用（Chrome未运行）

```python
# 1. 确保Chrome未运行
# 2. 调用CDP工具
result = cdp_browser(action="navigate", url="https://www.baidu.com")
# 预期: 自动启动Chrome，然后导航成功
```

### 测试场景2: Chrome已运行

```python
# 1. 手动启动Chrome: google-chrome --remote-debugging-port=9222 --headless
# 2. 调用CDP工具
result = cdp_browser(action="navigate", url="https://www.baidu.com")
# 预期: 直接使用已有实例，无延迟
```

### 测试场景3: Chrome未安装

```python
# 1. 在没有Chrome的环境
# 2. 调用CDP工具
result = cdp_browser(action="navigate", url="https://www.baidu.com")
# 预期: 返回明确错误信息，包含安装指南
```

## 下一步改进

### 1. Agent层改进

**问题**: Agent遇到CDP失败后，不应切换到search_lead

**建议**: 在系统提示词中强化规则
```markdown
## 工具失败处理
- cdp_browser失败时，检查错误信息
- 如果是"服务未启动"，等待工具自动启动
- 如果是"Chrome未安装"，明确告知用户
- **禁止**切换到search_lead生成"研究报告"
```

### 2. 增加重试机制

```python
def _get_browser_with_retry(max_retries=2):
    """带重试的浏览器连接"""
    for i in range(max_retries):
        try:
            return _get_browser()
        except RuntimeError as e:
            if i == max_retries - 1:
                raise
            logger.warning(f"Retry {i+1}/{max_retries}: {e}")
            time.sleep(2)
```

### 3. 增加健康监控

```python
def _monitor_chrome_health():
    """定期检查Chrome是否仍在运行"""
    # 如果Chrome崩溃，自动重启
    pass
```

## 总结

这次改进主要解决了CDP工具的"被动"问题：

- **Before**: 只检查服务可用性，失败时返回错误
- **After**: 主动尝试启动服务，提高成功率

但仍需要在Agent层面强化规则，避免工具失败后生成"假报告"。
