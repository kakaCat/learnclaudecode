# LLM 思维链可视化工具

让 LLM 的思考过程变得透明可见，帮助你理解和优化 AI Agent 的决策链路。

## 🎯 核心价值

**问题**：使用 LLM Agent 时，你是否遇到过这些困惑？
- 🤔 为什么 LLM 选择了这个工具？
- 🐛 为什么 Agent 运行这么慢？
- 🔄 为什么 LLM 重复调用同一个工具？
- 💡 如何优化提示词让 LLM 更高效？

**解决方案**：思维链可视化工具
- ✅ 展示 LLM 每一轮的思考过程
- ✅ 可视化工具调用决策链路
- ✅ 自动识别性能瓶颈和优化点
- ✅ 生成美观的 HTML 分析报告

## 🚀 快速开始

### 1. 基本分析

```bash
python scripts/analyze_thinking.py .sessions/20260303_132911/trace.jsonl
```

输出示例：
```
🧠 LLM 思维链可视化 - Run e0bf0247
====================================================================================================

📝 用户输入: 请给我中芯国际的情况
⏱️  总耗时: 135.66s
🔄 思考轮次: 15
🔧 工具调用: 14

🔍 思维链路:

🔄 第 1 轮思考 (Turn 1)
────────────────────────────────────────────────────────────────────────────────────────────────────
💭 LLM 思考:
   我来为您获取中芯国际的情况。首先，我需要识别中芯国际的股票代码...

🎯 决策: 调用 1 个工具
   • TodoWrite

📊 执行结果:
   ✅ TodoWrite (2ms)
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

在浏览器中打开 `report.html` 查看可视化报告。

## 📊 功能特性

### 思维链可视化
- 展示 LLM 每一轮的思考内容
- 显示工具调用决策和参数
- 标记成功/失败的工具执行
- 追踪完整的决策链路

### 性能分析
- 识别耗时最长的环节
- 检测重复和冗余调用
- 统计工具使用频率
- 分析思维模式

### 优化建议
- 🔴 工具失败检测
- 🟡 重复调用识别
- 🟡 性能瓶颈定位
- 🟡 思考效率评估

### HTML 报告
- 📊 可视化时间线
- 🎨 彩色状态标记
- 📈 性能统计图表
- 💡 自动优化建议

## 📖 使用场景

### 场景 1: 调试 Agent 行为

**问题**：Agent 没有按预期工作

**解决**：
```bash
python scripts/analyze_thinking.py .sessions/xxx/trace.jsonl --detailed
```

查看 LLM 的每一步决策，找出问题所在。

### 场景 2: 优化性能

**问题**：Agent 运行太慢

**解决**：
```bash
python scripts/analyze_thinking.py .sessions/xxx/trace.jsonl --optimize
```

获取具体的优化建议。

### 场景 3: 改进提示词

**问题**：不知道如何改进提示词

**解决**：
```bash
# 对比不同提示词的效果
python scripts/analyze_thinking.py .sessions/run1/trace.jsonl --html report1.html
python scripts/analyze_thinking.py .sessions/run2/trace.jsonl --html report2.html
```

对比两个报告，找出更好的提示词模式。

### 场景 4: 学习 LLM 思维

**问题**：想了解 LLM 如何分解复杂任务

**解决**：
```bash
python scripts/analyze_thinking.py .sessions/xxx/trace.jsonl --html learning.html
```

详细研究 LLM 的思考过程。

## 🔧 命令行选项

```bash
python scripts/analyze_thinking.py <trace_file> [options]

选项:
  --chain N         分析第 N 条思维链 (默认: 0)
  --detailed        显示详细信息（工具参数和结果）
  --html FILE       生成 HTML 报告
  --optimize        生成优化建议
```

## 📚 完整文档

详细使用指南请查看：[docs/thinking_chain_guide.md](docs/thinking_chain_guide.md)

## 🎨 示例

### 成功的工具调用

```
🔄 第 9 轮思考 (Turn 9)
────────────────────────────────────────────────────────────────────────────────────────────────────
🎯 决策: 调用 1 个工具
   • get_hist_data
     参数: symbol=688981, 2026-01-01 ~ 2026-03-03

📊 执行结果:
   ✅ get_hist_data (1390ms)
```

### 失败的工具调用

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

## 🔗 相关工具

| 工具 | 功能 | 适用场景 |
|------|------|---------|
| `/insight` | 性能分析 | 优化性能 |
| `/insight-llm` | LLM 质量分析 | 评估决策质量 |
| `analyze_thinking.py` | **思维链可视化** | **理解思考过程** |

## 💡 设计理念

这个工具的核心理念是：**让 LLM 的思维过程从隐性变为显性**

- **隐性**：你只看到输入和输出，不知道中间发生了什么
- **显性**：你能看到 LLM 的每一步思考、每一个决策、每一次工具调用

当思维过程变得透明，你就能：
1. 理解 LLM 的决策逻辑
2. 发现潜在的问题
3. 优化提示词和工具
4. 提升 Agent 的整体性能

## 🛠️ 技术实现

- **数据源**：trace.jsonl（由 tracer.py 记录）
- **核心类**：ThinkingChainAnalyzer
- **数据结构**：ThinkingChain + ThinkingStep
- **输出格式**：终端彩色输出 + HTML 报告

## 📦 文件结构

```
backend/app/
  ├── thinking_chain.py      # 核心分析器
  ├── tracer.py              # trace 事件记录
  ├── insight.py             # 性能分析
  └── llm_insight.py         # LLM 质量分析

scripts/
  └── analyze_thinking.py    # 命令行工具

docs/
  └── thinking_chain_guide.md # 完整文档
```

## 🎯 下一步

1. 运行你的 Agent，生成 trace.jsonl
2. 使用工具分析思维链
3. 根据优化建议改进 Agent
4. 重复迭代，持续优化

## 🤝 贡献

欢迎提交 Issue 和 PR！

## 📄 License

MIT
