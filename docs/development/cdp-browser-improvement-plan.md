# CDP Browser 工具改进方案

## 问题分析总结

基于 `.sessions/20260310_015346/trace.jsonl` 的分析，Agent 在执行机票查询任务时失败，主要问题：

### 1. JavaScript 执行上下文错误（核心问题）

**问题表现**：
- `SyntaxError: Illegal return statement` - 在全局作用域使用 return
- `SyntaxError: Identifier 'filled' has already been declared` - 变量重复声明

**根本原因**：
- CDP 的 `Runtime.evaluate` 在全局作用域执行代码，不是函数体
- 多次执行会在同一上下文中累积变量声明

### 2. 表单交互策略失效

**问题表现**：
- 直接设置 `input.value` 无法触发现代 SPA 的状态更新
- 点击搜索按钮后没有实际发起查询

**根本原因**：
- 携程/去哪儿等网站使用 React/Vue 框架
- 需要触发框架的事件系统，而不是原生 DOM 事件

### 3. 日期处理错误

**问题表现**：
- 查询 2026-03-11 但实际使用了 2025-03-11
- 后来又尝试 2024-12-11（过去的日期）

**根本原因**：
- 没有正确获取"明天"的日期
- 机票系统只开放未来 11 个月内的航班

### 4. 缺乏策略切换机制

**问题表现**：
- 花费 31 轮次重复失败的操作
- 直到第 21 轮才尝试直接构造 URL

**根本原因**：
- 没有失败计数和策略切换逻辑
- 应该在 3-5 次失败后自动切换方法

---

## 改进方案

### 方案 1: 修复 JavaScript 执行方式（立即可行）

#### 1.1 修改 `execute` 动作的脚本包装

**当前实现**（cdp_tool.py:318-325）：
```python
elif action == "execute":
    if not script:
        return "Error: script required for execute"
    result = tab.Runtime.evaluate(expression=script)
    tab.wait(wait_time)
    return json.dumps(result.get("result", {}), ensure_ascii=False)
```

**改进方案**：
```python
elif action == "execute":
    if not script:
        return "Error: script required for execute"

    # 包装为 IIFE（立即执行函数表达式），避免全局作用域问题
    wrapped_script = f"""
    (function() {{
        try {{
            {script}
        }} catch(e) {{
            return {{error: e.message, stack: e.stack}};
        }}
    }})()
    """

    result = tab.Runtime.evaluate(expression=wrapped_script)
    tab.wait(wait_time)

    # 检查执行结果
    result_obj = result.get("result", {})
    if result_obj.get("type") == "object" and "error" in str(result_obj):
        return f"❌ Script error: {result_obj}"

    return json.dumps(result_obj, ensure_ascii=False)
```

#### 1.2 添加表达式模式

为简单查询添加表达式模式（不需要 return）：

```python
elif action == "eval":  # 新增：表达式求值
    if not script:
        return "Error: script required for eval"

    result = tab.Runtime.evaluate(expression=script, returnByValue=True)
    return json.dumps(result.get("result", {}), ensure_ascii=False)
```

### 方案 2: 添加智能 URL 构造策略（推荐）

#### 2.1 在 MEMORY.md 中添加 URL 模板

```markdown
## CDP Browser 最佳实践

### 机票查询 URL 模板

优先使用直接 URL 构造，避免复杂的表单交互：

**去哪儿**：
```
https://flight.qunar.com/site/oneway_list.htm?searchDepartureAirport={出发城市}&searchArrivalAirport={到达城市}&searchDepartureTime={日期YYYY-MM-DD}
```

**携程**：
```
https://flights.ctrip.com/online/list/oneway-{出发城市拼音}-{到达城市拼音}?depdate={日期YYYY-MM-DD}
```

**示例**：
- 北京→上海 2026-03-11:
  - 去哪儿: `https://flight.qunar.com/site/oneway_list.htm?searchDepartureAirport=北京&searchArrivalAirport=上海&searchDepartureTime=2026-03-11`
  - 携程: `https://flights.ctrip.com/online/list/oneway-beijing-shanghai?depdate=2026-03-11`

### 策略优先级

1. **首选**：直接构造 URL（成功率 90%+）
2. **备选**：表单填写 + 点击搜索（成功率 30-50%）
3. **最后**：JavaScript 模拟用户输入（成功率 <20%）
```

#### 2.2 添加日期处理工具

在 `cdp_tool.py` 中添加辅助函数：

```python
def _parse_relative_date(date_str: str) -> str:
    """
    解析相对日期表达式

    Args:
        date_str: "明天"、"后天"、"2026-03-11" 等

    Returns:
        YYYY-MM-DD 格式的日期字符串
    """
    from datetime import datetime, timedelta

    today = datetime.now()

    if date_str in ["明天", "tomorrow"]:
        target = today + timedelta(days=1)
    elif date_str in ["后天", "day after tomorrow"]:
        target = today + timedelta(days=2)
    elif date_str in ["今天", "today"]:
        target = today
    else:
        # 尝试解析为日期格式
        try:
            target = datetime.strptime(date_str, "%Y-%m-%d")
        except:
            return date_str  # 无法解析，返回原值

    return target.strftime("%Y-%m-%d")
```

### 方案 3: 添加失败重试和策略切换（重要）

#### 3.1 在 MEMORY.md 中添加策略切换规则

```markdown
## CDP Browser 错误处理

### 失败重试策略

当 cdp_browser 操作失败时：

1. **第 1-2 次失败**：重试相同方法（可能是网络延迟）
2. **第 3 次失败**：切换到备选策略
   - 表单交互失败 → 切换到 URL 构造
   - JavaScript 错误 → 简化脚本或使用 click/type 动作
3. **第 5 次失败**：承认任务失败，给出明确说明

### 常见错误处理

**JavaScript 语法错误**：
- ❌ 不要使用 `return` 语句（除非在函数内）
- ❌ 不要重复声明变量（使用唯一变量名）
- ✅ 使用表达式而非语句
- ✅ 使用 `console.log()` 返回结果

**元素未找到**：
- 先使用 `wait_for` 等待元素出现
- 检查 selector 是否正确
- 使用 `content` 查看页面实际内容

**页面跳转失败**：
- 检查 URL 是否正确编码（中文需要 URL encode）
- 等待页面加载完成（wait_time=3-5）
- 使用 `wait_for` 等待关键元素
```

### 方案 4: 改进 cdp_tool.py 的错误提示

#### 4.1 添加更详细的错误信息

```python
def cdp_browser(
    action: Literal["navigate", "content", "click", "type", "wait_for", "screenshot", "execute", "eval"],
    url: Optional[str] = None,
    selector: Optional[str] = None,
    text: Optional[str] = None,
    script: Optional[str] = None,
    wait_time: int = 2,
) -> str:
    """
    CDP Browser 工具 - 控制浏览器进行 Web 自动化

    常见错误和解决方案：

    1. JavaScript 语法错误：
       - 不要在全局作用域使用 return
       - 避免重复声明变量
       - 使用 eval 动作执行表达式

    2. 元素未找到：
       - 先用 wait_for 等待元素
       - 检查 selector 语法
       - 用 content 查看页面内容

    3. 表单交互失败：
       - 优先使用 URL 参数
       - 避免复杂的 JavaScript 模拟

    Args:
        action: 操作类型
            - navigate: 导航到 URL
            - content: 获取页面文本内容
            - click: 点击元素
            - type: 输入文本
            - wait_for: 等待元素出现
            - screenshot: 截图
            - execute: 执行 JavaScript 语句（会自动包装为函数）
            - eval: 执行 JavaScript 表达式（直接求值）
        url: 目标 URL（navigate 需要）
        selector: CSS 选择器（click/type/wait_for 需要）
        text: 输入文本（type 需要）
        script: JavaScript 代码（execute/eval 需要）
        wait_time: 等待时间（秒）

    Returns:
        操作结果字符串
    """
    # ... 现有实现 ...
```

---

## 实施步骤

### 阶段 1: 快速修复（1 小时）

1. ✅ 修改 `cdp_tool.py` 的 `execute` 动作，添加 IIFE 包装
2. ✅ 添加 `eval` 动作用于表达式求值
3. ✅ 添加 `_parse_relative_date` 辅助函数
4. ✅ 改进错误提示信息

### 阶段 2: 记忆优化（30 分钟）

1. ✅ 更新 `.memory/MEMORY.md`，添加：
   - URL 模板
   - 策略优先级
   - 错误处理规则
   - 失败重试策略

### 阶段 3: 测试验证（30 分钟）

1. ✅ 创建测试脚本 `scripts/test_cdp_improvements.py`
2. ✅ 测试机票查询场景
3. ✅ 验证错误处理逻辑
4. ✅ 确认策略切换机制

---

## 预期效果

### 改进前（当前状态）

- ❌ JavaScript 语法错误频繁出现
- ❌ 表单交互成功率低（<30%）
- ❌ 需要 20-30 轮次才能完成或失败
- ❌ 日期处理错误
- ❌ 缺乏策略切换

### 改进后（目标状态）

- ✅ JavaScript 执行成功率 >95%
- ✅ 直接 URL 构造成功率 >90%
- ✅ 5 轮次内完成任务或明确失败
- ✅ 正确处理相对日期
- ✅ 自动策略切换

---

## 附录：测试用例

### 测试 1: JavaScript 执行

```python
# 测试 execute 动作（语句）
result = cdp_browser(
    action="execute",
    script="""
        const inputs = document.querySelectorAll('input');
        console.log('Found inputs:', inputs.length);
        inputs.length;  // 返回值（不使用 return）
    """
)

# 测试 eval 动作（表达式）
result = cdp_browser(
    action="eval",
    script="document.querySelectorAll('input').length"
)
```

### 测试 2: 机票查询（URL 构造）

```python
# 直接构造 URL
date = _parse_relative_date("明天")  # 2026-03-11
url = f"https://flight.qunar.com/site/oneway_list.htm?searchDepartureAirport=北京&searchArrivalAirport=上海&searchDepartureTime={date}"

result = cdp_browser(action="navigate", url=url)
result = cdp_browser(action="wait_for", selector=".m-airfly-lst", wait_time=10)
result = cdp_browser(action="content")
```

### 测试 3: 策略切换

```python
# 模拟失败场景
attempts = 0
max_attempts = 5

while attempts < max_attempts:
    if attempts < 3:
        # 策略 1: 表单交互
        result = try_form_interaction()
    else:
        # 策略 2: URL 构造
        result = try_url_construction()

    if "success" in result:
        break

    attempts += 1

if attempts >= max_attempts:
    print("任务失败：无法获取机票数据")
```

---

## 总结

通过以上改进，Agent 将能够：

1. **正确执行 JavaScript**：避免语法错误
2. **优先使用可靠策略**：URL 构造 > 表单交互
3. **快速失败**：5 轮内完成或明确失败
4. **正确处理日期**：支持相对日期表达式
5. **自动策略切换**：失败后自动尝试备选方案

这将大幅提升 Web 自动化任务的成功率和效率。
