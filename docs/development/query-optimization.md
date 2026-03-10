# Agent 查询优化方案

## 问题诊断

从会话日志 `.sessions/20260309_170139/main.jsonl` 分析，发现以下问题：

### 1. 工具调用失败链
```
web_search (Bing) → Error
web_search (Bing 再试) → Error
cdp_browser → Connection refused (端口 9222 未启动)
curl (携程 API) → 接口下线
search_lead → 成功（但返回的是通用知识，非实时数据）
```

### 2. 核心问题
- **cdp_browser 失败原因**：Chrome DevTools Protocol 服务未启动（端口 9222 无法连接）
- **降级策略不当**：所有实时工具失败后，Agent 降级到 `search_lead`（知识库工具）
- **输出误导用户**：把通用知识（价格范围 ¥500-¥1,500）当成查询结果返回，而非具体航班信息

### 3. 设计缺陷
1. **缺少工具健康检查**：没有在执行前检查工具是否可用
2. **工具分类不清晰**：没有区分"实时工具"和"知识库工具"
3. **缺少明确的失败处理**：失败时没有告知用户真实原因
4. **search_lead 被误用**：作为"最后的救命稻草"，但它不是实时查询工具

---

## 优化方案

### 架构改进

```
优化前：
User Query → 尝试所有工具 → 最后一个成功就返回

优化后：
User Query
  ↓
检查工具健康状态
  ↓
判断查询类型（实时 vs 知识库）
  ↓
选择合适的工具
  ↓
明确告知数据来源
```

### 新增组件

#### 1. 工具健康检查器 (`tool_health.py`)
- 检查 CDP 端口 9222 是否开放
- 检查网络连接是否正常
- 工具分类：realtime / knowledge / utility
- 生成工具状态报告

#### 2. 查询策略管理器 (`query_strategy.py`)
- 判断查询是否需要实时数据（关键词检测）
- 执行实时查询（优先使用可用工具）
- 执行知识库查询
- 明确区分查询结果类型

#### 3. 改进的 CDP 工具 (`cdp_tool_improved.py`)
- 添加 `check_health` 动作
- 缓存可用性检查结果
- 提供详细的启动指南
- 更好的错误处理

#### 4. 智能查询工具 (`smart_query_tool.py`)
- 自动判断查询类型
- 检查工具可用性
- 根据情况选择策略
- 明确告知数据来源

---

## 使用示例

### 场景 1：实时查询（工具可用）

```python
# 用户查询
"查询北京到上海明天的机票价格"

# Agent 执行
1. smart_query 检测到"明天"、"机票"、"价格" → 需要实时数据
2. 检查工具状态 → cdp_browser 可用
3. 使用 cdp_browser 访问携程
4. 返回具体航班信息：
   ✅ 实时查询结果：
   - CA1234: 08:00-10:00, ¥680
   - MU5678: 09:30-11:30, ¥720
   ...
```

### 场景 2：实时查询（工具不可用，不允许降级）

```python
# 用户查询
"查询北京到上海明天的机票价格"

# Agent 执行
1. smart_query 检测需要实时数据
2. 检查工具状态 → 所有实时工具不可用
3. require_realtime=True, allow_fallback=False
4. 返回失败信息：

❌ 无法完成实时查询

实时查询工具状态：
  ❌ web_search: 不可用
     网络连接失败或搜索服务不可用
  ❌ cdp_browser: 不可用
     Chrome DevTools Protocol 服务未启动

     启动方法：
     google-chrome --remote-debugging-port=9222 --headless

建议：
1. 启动 Chrome DevTools Protocol 服务
2. 检查网络连接
3. 或直接访问携程网站查询
```

### 场景 3：实时查询（工具不可用，允许降级）

```python
# 用户查询
"查询北京到上海的机票价格"

# Agent 执行
1. smart_query 检测需要实时数据
2. 检查工具状态 → 所有实时工具不可用
3. allow_fallback=True → 降级到知识库
4. 返回知识库结果：

⚠️ 实时查询不可用，已降级到知识库查询

实时查询工具状态：
  ❌ web_search: 不可用
  ❌ cdp_browser: 不可用

---

📚 以下是基于知识库的参考信息（非实时数据）：

## 北京-上海航线概况
- 主要航空公司：国航、东航、南航、海航
- 飞行时间：约 2 小时
- 价格范围：¥500-¥1,500（经济舱）

⚠️ 注意：这不是实时价格，建议直接访问携程/去哪儿查询
```

### 场景 4：知识库查询

```python
# 用户查询
"Python 最佳实践有哪些？"

# Agent 执行
1. smart_query 检测不需要实时数据
2. 直接使用 search_lead
3. 返回知识库结果：

📚 使用知识库查询

[Python 最佳实践研究报告]
1. 代码风格：遵循 PEP 8
2. 类型提示：使用 type hints
3. 测试：编写单元测试
...
```

---

## 集成步骤

### 1. 安装新文件

已创建以下文件：
- `backend/app/tools/tool_health.py` - 工具健康检查
- `backend/app/tools/query_strategy.py` - 查询策略管理
- `backend/app/tools/implementations/cdp_tool_improved.py` - 改进的 CDP 工具
- `backend/app/tools/implementations/smart_query_tool.py` - 智能查询工具

### 2. 更新工具注册

在 `backend/app/tools/__init__.py` 中注册新工具：

```python
from backend.app.tools.implementations.smart_query_tool import (
    smart_query,
    check_query_tools
)
from backend.app.tools.implementations.cdp_tool_improved import (
    cdp_browser as cdp_browser_improved
)

# 替换旧的 cdp_browser
TOOLS = [
    # ... 其他工具
    smart_query,           # 新增：智能查询
    check_query_tools,     # 新增：工具健康检查
    cdp_browser_improved,  # 替换：改进的 CDP 工具
]
```

### 3. 更新 System Prompt

在系统提示词中添加工具使用指南：

```markdown
## 查询工具使用指南

### 实时查询
当用户需要实时数据（机票、股票、天气等）时：
1. 优先使用 `smart_query(query, require_realtime=True)`
2. 如果失败，明确告知用户原因
3. 不要用知识库结果伪装成实时数据

### 知识库查询
当用户需要通用知识时：
1. 使用 `smart_query(query, require_realtime=False)`
2. 或直接使用 `search_lead(topic)`

### 工具健康检查
在会话开始时，可以运行：
- `check_query_tools()` - 检查所有工具状态
- `cdp_browser(action="check_health")` - 检查 CDP 服务
```

### 4. 启动 CDP 服务（可选）

如果需要使用浏览器自动化：

```bash
# macOS/Linux
google-chrome --remote-debugging-port=9222 --headless --disable-gpu

# 或使用 Docker
docker run -d -p 9222:9222 zenika/alpine-chrome \
  --remote-debugging-port=9222 --no-sandbox
```

---

## 测试验证

### 测试 1：工具健康检查

```python
from backend.app.tools.tool_health import get_tool_health_checker

checker = get_tool_health_checker()
print(checker.format_status_report())
```

预期输出：
```
## 工具状态检查

### REALTIME 工具
- ❌ cdp_browser
  - 原因: Chrome DevTools Protocol 未启动 (端口 9222 未开放)
- ✅ web_search

### KNOWLEDGE 工具
- ✅ search_lead
```

### 测试 2：智能查询（CDP 不可用）

```python
from backend.app.tools.implementations.smart_query_tool import smart_query

result = smart_query.invoke({
    "query": "北京到上海明天的机票",
    "require_realtime": True,
    "allow_fallback": False
})
print(result)
```

预期输出：
```
❌ 无法完成实时查询

实时查询工具状态：
  ❌ cdp_browser: 不可用
     Chrome DevTools Protocol 服务未启动
     ...

建议：
1. 启动 Chrome DevTools Protocol 服务
2. 检查网络连接
3. 或直接访问相关网站查询
```

---

## 关键改进点总结

### 1. 透明性
- ✅ 明确告知用户数据来源（实时 vs 知识库）
- ✅ 工具失败时提供详细原因
- ✅ 不再用通用知识伪装成实时数据

### 2. 可靠性
- ✅ 工具健康检查（避免盲目调用）
- ✅ 明确的降级策略
- ✅ 更好的错误处理

### 3. 可维护性
- ✅ 工具分类清晰（realtime / knowledge / utility）
- ✅ 策略模式（QueryStrategy）
- ✅ 单一职责（每个组件职责明确）

### 4. 用户体验
- ✅ 失败时提供可操作的建议
- ✅ 明确的状态反馈
- ✅ 避免误导性输出

---

## 后续优化建议

### 1. 自动启动 CDP 服务
```python
def auto_start_cdp():
    """自动启动 Chrome DevTools Protocol"""
    if not check_port(9222):
        subprocess.Popen([
            "google-chrome",
            "--remote-debugging-port=9222",
            "--headless",
            "--disable-gpu"
        ])
        time.sleep(2)
```

### 2. 工具重试机制
```python
async def execute_with_retry(tool, params, max_retries=3):
    """带重试的工具执行"""
    for i in range(max_retries):
        try:
            result = await tool.ainvoke(params)
            if "Error" not in result:
                return result
        except Exception as e:
            if i == max_retries - 1:
                raise
            await asyncio.sleep(1)
```

### 3. 工具性能监控
```python
class ToolPerformanceMonitor:
    """工具性能监控"""
    def __init__(self):
        self.stats = {}  # tool_name -> {success_count, fail_count, avg_time}

    def record(self, tool_name, success, duration):
        # 记录工具调用统计
        pass
```

### 4. 智能工具选择
```python
def select_best_tool(query, available_tools):
    """根据查询内容和历史成功率选择最佳工具"""
    # 基于历史数据和查询特征选择工具
    pass
```
