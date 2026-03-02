# Trace 分析工具使用指南

类似 Claude Code Insight 的 AI 调用分析工具集

## 工具概览

### 1. trace_analyzer.py - 基础分析工具
快速分析 trace 文件，提供基本的性能统计和优化建议。

**功能：**
- 📊 运行概览统计
- ⚡ 性能分析（耗时、瓶颈）
- 🔧 工具使用统计
- 🤖 子 Agent 分析
- 💡 优化建议

**使用方法：**
```bash
python scripts/trace_analyzer.py .sessions/20260301_214209/trace.jsonl
```

### 2. trace_insight.py - 高级分析工具
深度分析 AI 调用链路，提供更详细的洞察。

**功能：**
- 📊 执行摘要
- 🌲 调用链路树（可视化层级关系）
- ⏱️ 执行时间线
- 🔥 性能瓶颈分析（时间分布）
- 📈 效率指标
- 💡 优先级优化建议

**使用方法：**
```bash
python scripts/trace_insight.py .sessions/20260301_214209/trace.jsonl
```

## 分析示例

### 从分析结果中发现的优化点

#### 1. 性能瓶颈
```
Run f0f913d5 耗时 261.11s
- 子 Agent: 0.00s (0.0%)
- LLM 调用: 7.14s (2.7%)
- 其他: 253.96s (97.3%)  ← 主要瓶颈！
```

**问题：** 97.3% 的时间花在"其他"操作上（可能是网络请求、文件 I/O）

**优化方案：**
- 并行化多个 web_search 调用
- 添加结果缓存机制
- 使用更快的搜索 API

#### 2. 无效运行
```
Run 683b5114 无工具调用但耗时 8.22s
```

**问题：** 没有调用任何工具，但花费了 8 秒

**优化方案：**
- 优化提示词，让 AI 更快理解意图
- 添加快速响应路径
- 考虑使用更快的模型（如 Haiku）

#### 3. 工具失败率
```
工具 web_search 失败率 100%
调用次数: 2, 失败: 2
```

**问题：** 工具调用全部失败

**优化方案：**
- 检查 API 配置
- 添加重试机制
- 提供降级方案

## Trace 文件格式

### 事件类型

```json
// 运行开始
{"ts": 1772372573.594, "event": "run.start", "run_id": "683b5114", "prompt": "帮我添加一个功能"}

// 运行结束
{"ts": 1772372581.811, "event": "run.end", "run_id": "683b5114", "output": "...", "turns": 0, "total_tools": 0, "duration_ms": 8217}

// LLM 调用
{"ts": 1772372581.81, "event": "llm.fallback", "run_id": "683b5114", "duration_ms": 1902}

// 工具调用结果
{"ts": 1772373967.803, "event": "tool.result", "run_id": "78dbd16a", "tool": "list_dir", "ok": true}

// 子 Agent 启动
{"ts": 1772373733.969, "event": "subagent.start", "run_id": "a420be68", "span_id": "53d44277", "agent_type": "IntentRecognition"}

// 子 Agent 结束
{"ts": 1772373741.296, "event": "subagent.end", "run_id": "a420be68", "span_id": "53d44277", "duration_ms": 7327}
```

## 优化建议分类

### 🔴 高优先级（HIGH）
- 运行耗时超过 60 秒
- 工具失败率超过 50%
- 严重的性能瓶颈

### 🟡 中优先级（MEDIUM）
- 运行耗时 30-60 秒
- 无工具调用但耗时超过 5 秒
- 子 Agent 平均耗时超过 15 秒

### 🟢 低优先级（LOW）
- 轻微的性能问题
- 可选的优化建议

## 常见优化策略

### 1. 并行化
```python
# 串行调用（慢）
result1 = await tool1()
result2 = await tool2()

# 并行调用（快）
results = await asyncio.gather(tool1(), tool2())
```

### 2. 缓存
```python
# 添加结果缓存
@lru_cache(maxsize=100)
def expensive_operation(query):
    return search_api(query)
```

### 3. 提示词优化
```python
# 模糊提示（慢）
"帮我添加一个功能"

# 明确提示（快）
"在 backend/app/tools/ 目录下创建一个新的 stock_tool.py 文件，实现股票查询功能"
```

### 4. 工具选择
```python
# 使用更快的模型处理简单任务
if is_simple_task(prompt):
    model = "claude-haiku-4-5"  # 快速
else:
    model = "claude-sonnet-4-6"  # 强大
```

## 扩展功能

### 添加自定义分析

你可以扩展 `TraceInsight` 类来添加自定义分析：

```python
class CustomTraceInsight(TraceInsight):
    def analyze_token_usage(self):
        """分析 token 使用情况"""
        # 自定义分析逻辑
        pass

    def estimate_cost(self):
        """估算 API 成本"""
        # 基于 token 使用估算成本
        pass
```

### 导出报告

```python
# 导出为 JSON
insight.export_json("report.json")

# 导出为 HTML
insight.export_html("report.html")

# 导出为 Markdown
insight.export_markdown("report.md")
```

## 与 Claude Code Insight 的对比

| 功能 | trace_insight.py | Claude Code Insight |
|------|------------------|---------------------|
| 调用链路可视化 | ✅ 树形结构 | ✅ 图形界面 |
| 时间线分析 | ✅ 文本格式 | ✅ 可视化时间轴 |
| 性能瓶颈识别 | ✅ 时间分布 | ✅ 火焰图 |
| 优化建议 | ✅ 自动生成 | ✅ AI 驱动 |
| Token 使用分析 | ⏳ 待实现 | ✅ 详细统计 |
| 成本估算 | ⏳ 待实现 | ✅ 实时计算 |
| 交互式探索 | ❌ 命令行 | ✅ Web UI |

## 最佳实践

1. **定期分析**：每次重要更新后运行分析
2. **对比分析**：保存历史报告，对比优化效果
3. **关注趋势**：追踪平均耗时、成功率等指标
4. **优先修复**：先解决高优先级问题
5. **持续监控**：在 CI/CD 中集成分析工具

## 故障排查

### 问题：trace.jsonl 文件为空
**解决：** 确保 tracer 已正确初始化并记录事件

### 问题：分析结果不准确
**解决：** 检查事件的时间戳和 duration_ms 字段

### 问题：无法找到瓶颈
**解决：** 使用 trace_insight.py 查看详细的时间分布

## 贡献

欢迎提交 PR 添加新功能：
- 更多可视化选项
- Token 使用分析
- 成本估算
- HTML/PDF 报告导出
- 实时监控面板

## 许可证

MIT License
