# 长期记忆

## 项目信息

- 项目名称: learnclaudecode
- 项目类型: AI Agent 学习示例项目
- 技术栈: Python, Anthropic SDK, LangChain, DeepSeek

## 架构特点

- 采用 session 机制管理会话状态
- 支持 Bootstrap 文件加载（SOUL.md, IDENTITY.md 等）
- 实现了混合记忆搜索（TF-IDF + 向量 + 时间衰减 + MMR）
- 系统提示词采用 8 层组装结构

## 开发规范

- 文件超过 200 行时分段写入，每段 ≤150 行
- 写完文件后运行 `python -m py_compile` 验证语法
- 禁止单次 Write 超过 12800 字符
- 升级 agent 时逐模块进行，一次只写一个文件

## 用户偏好

- 不要主动执行 git commit，除非用户明确要求
- 使用中文进行交流和文档编写
- 注重代码质量和架构清晰度

## 任务识别规则

### Web 操作任务（需要浏览器）
- 特征：查询、购买、预订 + 机票、酒店、商品
- 工具优先级：cdp_browser > web_search
- 示例："查询北京到上海的机票" → 使用 cdp_browser 访问携程/去哪儿

### 信息查询任务
- 特征：什么是、如何、为什么
- 工具优先级：web_search > read_file
- 示例："什么是机票预订流程" → 使用 web_search

## 知识到行动映射

当提到具体网站时，必须实际访问，不要只是"建议用户去访问"：
- 携程 → https://flights.ctrip.com
- 去哪儿 → https://flight.qunar.com
- 飞猪 → https://www.fliggy.com

## 行为约束

1. **禁止生成假报告**：无法获取实时数据时，明确说"任务失败"，不要生成"研究报告"
2. **知行一致**：提到某个网站就必须访问它
3. **工具失败处理**：cdp_browser 失败时给出启动命令，不要切换到"研究模式"
4. **结果验证**：查询机票必须返回航班号、时间、价格

## CDP Browser 最佳实践

### 策略优先级

查询机票等 Web 任务时，按以下优先级选择策略：

1. **首选：直接构造 URL**（成功率 90%+）
   - 去哪儿、携程等网站支持 URL 参数直接跳转到搜索结果页
   - 避免复杂的表单交互和 JavaScript 模拟

2. **备选：表单填写 + 点击搜索**（成功率 30-50%）
   - 使用 type 和 click 动作
   - 需要 wait_for 等待元素加载

3. **最后：JavaScript 模拟用户输入**（成功率 <20%）
   - 现代 SPA 框架难以模拟
   - 仅在前两种方法都失败时使用

### 机票查询 URL 模板

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

### JavaScript 执行规则

**使用 eval 动作**（表达式求值）：
```javascript
// ✅ 正确：直接返回值
document.querySelectorAll('.flight-item').length

// ✅ 正确：获取文本
document.querySelector('.price').textContent
```

**使用 execute 动作**（语句执行）：
```javascript
// ✅ 正确：会自动包装为 IIFE，可以使用 return
const items = document.querySelectorAll('.flight-item');
return Array.from(items).map(item => item.textContent);

// ✅ 正确：可以声明变量
let count = 0;
document.querySelectorAll('.flight').forEach(f => count++);
return count;
```

**禁止的写法**：
```javascript
// ❌ 错误：在全局作用域使用 return（旧版本会报错）
return document.title;  // 现在 execute 会自动包装，但建议用 eval

// ❌ 错误：重复声明全局变量（多次执行会冲突）
var result = ...;  // 使用 let/const 或在 execute 中（会自动隔离）
```

### 错误处理和重试策略

**失败重试规则**：

1. **第 1-2 次失败**：重试相同方法（可能是网络延迟）
2. **第 3 次失败**：切换到备选策略
   - 表单交互失败 → 切换到 URL 构造
   - JavaScript 错误 → 简化脚本或使用 eval 动作
3. **第 5 次失败**：承认任务失败，给出明确说明

**常见错误处理**：

- **JavaScript 语法错误**：
  - 使用 `eval` 动作执行表达式
  - 使用 `execute` 动作执行语句（自动包装为 IIFE）
  - 避免在全局作用域重复声明变量

- **元素未找到**：
  - 先使用 `wait_for` 等待元素出现（timeout 10-20s）
  - 检查 selector 是否正确
  - 使用 `content` 或 `eval` 查看页面实际内容

- **页面跳转失败**：
  - 检查 URL 是否正确编码（中文需要 URL encode）
  - 等待页面加载完成（wait_time=3-5）
  - 使用 `wait_for` 等待关键元素

### 日期处理

使用 `parse_relative_date()` 辅助函数处理相对日期：

```python
from backend.app.tools.implementations.cdp_tool import parse_relative_date

# 支持的格式
parse_relative_date("明天")      # → "2026-03-11"
parse_relative_date("后天")      # → "2026-03-12"
parse_relative_date("今天")      # → "2026-03-10"
parse_relative_date("2026-03-15") # → "2026-03-15"
```

## 行为约束

1. **禁止生成假报告**：无法获取实时数据时，明确说"任务失败"，不要生成"研究报告"
2. **知行一致**：提到某个网站就必须访问它
3. **工具失败处理**：cdp_browser 失败时给出启动命令，不要切换到"研究模式"
4. **结果验证**：查询机票必须返回航班号、时间、价格

## 输出格式要求

### 机票查询结果格式

当查询机票时，必须以表格形式列出**所有**可选航班：

```markdown
## 查询结果：北京 → 上海 (2026-03-11)

| 航空公司 | 航班号 | 起飞 | 到达 | 机场 | 价格 | 舱位 |
|---------|--------|------|------|------|------|------|
| 中国联合航空 | KN5987 | 20:55 | 23:15 | 大兴→浦东T1 | ¥490 | 经济舱3.1折 |
| 吉祥航空 | HO1254 | 21:25 | 23:40 | 大兴→浦东T2 | ¥543 | 经济舱3.1折 |
| 东方航空 | MU8243 | 20:55 | 23:15 | 大兴→浦东T1 | ¥570 | 经济舱3.5折 |
| 南方航空 | CZ8889 | 20:45 | 23:10 | 大兴→浦东T2 | ¥690 | 经济舱4.3折 |
| 中国联合航空 | KN5988 | 21:35 | 23:30 | 大兴→虹桥T2 | ¥710 | 经济舱 |

**推荐**：最便宜的是 KN5987 (¥490)，最快的是 CZ8889 (2小时25分)
```

**禁止**：
- ❌ 只总结"最便宜航班"而不列出所有选项
- ❌ 只给出价格范围而不列出具体航班
- ❌ 用概括性描述代替具体数据
