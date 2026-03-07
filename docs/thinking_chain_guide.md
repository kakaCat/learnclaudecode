# LLM 思维链可视化工具

## 功能概述

这个工具可以帮助你理解 LLM Agent 的思考过程，让 LLM 的决策链路变得透明可见。

### 核心功能

1. **思维链解析**：从 trace.jsonl 提取 LLM 的每一轮思考
2. **可视化展示**：清晰展示 LLM 的决策过程（prompt → reasoning → tool_calls → results）
3. **优化建议**：自动识别冗余、低效的思考模式
4. **HTML 报告**：生成美观的可视化报告

## 快速开始

### 1. 基本用法

```bash
# 分析最近的 session
python scripts/analyze_thinking.py .sessions/20260303_132911/trace.jsonl

# 分析指定的链（如果有多条）
python scripts/analyze_thinking.py .sessions/20260303_132911/trace.jsonl --chain 0

# 显示详细信息（包括工具参数和结果）
python scripts/analyze_thinking.py .sessions/20260303_132911/trace.jsonl --detailed
```

### 2. 生成优化建议

```bash
python scripts/analyze_thinking.py .sessions/20260303_132911/trace.jsonl --optimize
```

输出示例：
```
💡 优化建议
====================================================================================================

1. 🔴 工具 get_realtime_data 失败 (Turn 5)
     建议: 检查参数或添加错误处理
2. 🟡 运行时间过长: 135.66s
     建议: 考虑并行化或优化提示词
3. 🟡 思考轮次过多 (15 轮)
     建议: 优化提示词，让 LLM 更快做出决策
```

### 3. 生成 HTML 报告

```bash
python scripts/analyze_thinking.py .sessions/20260303_132911/trace.jsonl --html report.html
```

然后在浏览器中打开 `report.html` 查看可视化报告。

## 输出说明

### 终端输出

```
====================================================================================================
🧠 LLM 思维链可视化 - Run e0bf0247
====================================================================================================

📝 用户输入: 请给我中芯国际的情况
⏱️  总耗时: 135.66s
🔄 思考轮次: 15
🔧 工具调用: 14

🔍 思维链路:

────────────────────────────────────────────────────────────────────────────────────────────────────
🔄 第 1 轮思考 (Turn 1)
────────────────────────────────────────────────────────────────────────────────────────────────────
💭 LLM 思考:
   我来为您获取中芯国际的情况。首先，我需要识别中芯国际的股票代码...

🎯 决策: 调用 1 个工具
   • TodoWrite
     参数: 4 项任务

📊 执行结果:
   ✅ TodoWrite (2ms)
```

### HTML 报告特性

- 📊 **可视化时间线**：展示 LLM 的思考流程
- 🎨 **彩色标记**：成功/失败工具调用一目了然
- 📈 **性能统计**：耗时分析和瓶颈识别
- 💡 **优化建议**：自动生成改进建议

## 使用场景

### 1. 调试 Agent 行为

**问题**：为什么 LLM 选择了这个工具？

**解决**：查看思维链，了解 LLM 的决策依据

```bash
python scripts/analyze_thinking.py .sessions/xxx/trace.jsonl --detailed
```

### 2. 优化提示词

**问题**：哪些提示导致了更好的决策？

**解决**：对比不同提示词的思维链

```bash
# 分析第一次运行
python scripts/analyze_thinking.py .sessions/run1/trace.jsonl --chain 0

# 分析第二次运行
python scripts/analyze_thinking.py .sessions/run2/trace.jsonl --chain 0
```

### 3. 性能分析

**问题**：哪些环节耗时最长？

**解决**：查看优化建议

```bash
python scripts/analyze_thinking.py .sessions/xxx/trace.jsonl --optimize
```

### 4. 学习 LLM 思维

**问题**：LLM 如何分解复杂任务？

**解决**：生成 HTML 报告，详细研究

```bash
python scripts/analyze_thinking.py .sessions/xxx/trace.jsonl --html learning.html
```

## 高级用法

### 分析多条思维链

```bash
# 查看有多少条链
python scripts/analyze_thinking.py .sessions/xxx/trace.jsonl

# 分析第二条链
python scripts/analyze_thinking.py .sessions/xxx/trace.jsonl --chain 1
```

### 组合使用

```bash
# 生成详细的 HTML 报告并显示优化建议
python scripts/analyze_thinking.py .sessions/xxx/trace.jsonl --html report.html --optimize
```

## 优化建议类型

工具会自动检测以下问题：

| 类型 | 说明 | 建议 |
|------|------|------|
| 🔴 工具失败 | 工具调用返回错误 | 检查参数或添加错误处理 |
| 🟡 重复调用 | 相同工具被多次调用 | 缓存结果或优化逻辑 |
| 🟡 运行时间长 | 总耗时超过 60 秒 | 考虑并行化或优化提示词 |
| 🟡 多次失败 | 多个工具调用失败 | 添加重试机制或改进错误处理 |
| 🟡 轮次过多 | 思考轮次超过 10 轮 | 优化提示词，让 LLM 更快决策 |

## 工作原理

### 数据流

```
trace.jsonl
    ↓
ThinkingChainAnalyzer.load_events()
    ↓
ThinkingChainAnalyzer.parse_chains()
    ↓
ThinkingChain (包含多个 ThinkingStep)
    ↓
可视化输出 / HTML 报告 / 优化建议
```

### 核心数据结构

```python
@dataclass
class ThinkingStep:
    """单个思考步骤"""
    turn: int                          # 第几轮
    timestamp: float                   # 时间戳
    prompt_messages: List[Dict]        # LLM 输入
    response_content: str              # LLM 思考内容
    tool_calls: List[Dict]             # 工具调用决策
    tool_results: List[Dict]           # 工具执行结果
    duration_ms: int                   # 耗时

@dataclass
class ThinkingChain:
    """完整的思维链"""
    run_id: str                        # 运行 ID
    user_prompt: str                   # 用户输入
    final_output: str                  # 最终输出
    steps: List[ThinkingStep]          # 思考步骤列表
    total_duration_ms: int             # 总耗时
    total_turns: int                   # 总轮次
    total_tools: int                   # 工具调用总数
```

## 与现有工具的对比

| 工具 | 功能 | 适用场景 |
|------|------|---------|
| `/insight` | 性能分析、瓶颈识别 | 优化性能 |
| `/insight-llm` | LLM 质量分析 | 评估决策质量 |
| `analyze_thinking.py` | **思维链可视化** | **理解 LLM 思考过程** |

## 示例输出

### 成功案例

```
🔄 第 9 轮思考 (Turn 9)
────────────────────────────────────────────────────────────────────────────────────────────────────
🎯 决策: 调用 1 个工具
   • get_hist_data
     参数: symbol=688981, 2026-01-01 ~ 2026-03-03

📊 执行结果:
   ✅ get_hist_data (1390ms)
```

### 失败案例

```
🔄 第 5 轮思考 (Turn 5)
────────────────────────────────────────────────────────────────────────────────────────────────────
🎯 决策: 调用 1 个工具
   • get_realtime_data
     参数: symbol=688981, source=xueqiu

📊 执行结果:
   ❌ get_realtime_data (7175ms)
      错误: Failed to get realtime data after 3 attempts: 'data'
```

## 常见问题

### Q: trace.jsonl 文件在哪里？

A: 在 `.sessions/<session_id>/trace.jsonl`

### Q: 如何找到最新的 session？

```bash
ls -lt .sessions/ | head -5
```

### Q: 可以分析历史 session 吗？

A: 可以，只要 trace.jsonl 文件存在

### Q: HTML 报告可以分享吗？

A: 可以，HTML 是独立文件，包含所有样式

## 扩展开发

### 添加自定义分析

编辑 `backend/app/thinking_chain.py`：

```python
def custom_analysis(self, chain: ThinkingChain):
    """自定义分析逻辑"""
    # 你的分析代码
    pass
```

### 自定义 HTML 模板

修改 `generate_html_report()` 方法中的 HTML 模板。

## 相关文件

- `backend/app/thinking_chain.py` - 核心分析器
- `scripts/analyze_thinking.py` - 命令行工具
- `backend/app/tracer.py` - trace 事件记录
- `backend/app/insight.py` - 性能分析工具
- `backend/app/llm_insight.py` - LLM 质量分析工具

## 贡献

欢迎提交 Issue 和 PR！

## License

MIT
