# Trace Insight 实现总结

## 🎯 实现目标

创建一个类似 Claude Code Insight 的 AI 调用分析工具，帮助开发者：
- 识别性能瓶颈
- 优化 Agent 调用链路
- 提高工具使用效率
- 降低 API 成本

## 📦 已实现的功能

### 1. 核心分析模块

#### `backend/app/insight.py`
集成到 main REPL 的轻量级分析模块

**功能：**
- 📊 执行摘要（运行次数、总耗时、工具调用）
- ⚡ 性能分析（识别最慢的运行）
- 🔥 瓶颈分析（时间分布：子 Agent、LLM、其他）
- 🔧 工具使用统计（成功率）
- 💡 优化建议（自动识别问题）

**使用方式：**
```bash
python -m backend.main
agent >> /insight
```

#### `scripts/trace_analyzer.py`
基础分析工具，快速查看性能统计

**功能：**
- 运行概览
- 性能分析
- 工具使用统计
- 子 Agent 分析
- 优化建议

**使用方式：**
```bash
python scripts/trace_analyzer.py .sessions/20260301_214209/trace.jsonl
```

#### `scripts/trace_insight.py`
高级分析工具，提供详细的洞察

**功能：**
- 执行摘要
- 🌲 调用链路树（可视化层级关系）
- ⏱️ 执行时间线（事件序列）
- 🔥 性能瓶颈分析（详细时间分布）
- 📈 效率指标
- 💡 优先级优化建议（HIGH/MEDIUM/LOW）

**使用方式：**
```bash
python scripts/trace_insight.py .sessions/20260301_214209/trace.jsonl
```

### 2. 集成到 main.py

修改了 `backend/main.py`，添加了 `/insight` 命令：

```python
# 新增命令
COMMANDS = ["/compact", "/tasks", "/team", "/inbox", "/sessions", "/insight"]

# 命令处理
if query == "/insight":
    from backend.app.insight import analyze_trace
    trace_file = get_session_dir() / "trace.jsonl"
    if not trace_file.exists():
        print("❌ No trace file found for current session.")
        continue
    analyze_trace(trace_file)
    continue
```

### 3. 文档

- `docs/INSIGHT_USAGE.md` - 使用指南
- `scripts/README_TRACE_ANALYSIS.md` - 详细分析工具文档
- `README.md` - 更新了主文档

## 🔍 分析能力

### 识别的问题类型

#### 1. 性能瓶颈 🔴
```
Run f0f913d5: 261.11s
- 其他: 253.96s (97.3%)  ← 网络/IO 瓶颈
```

**优化方案：**
- 并行化多个 API 调用
- 添加结果缓存
- 使用更快的 API

#### 2. 无效运行 🟡
```
Run 683b5114: 8.22s 但无工具调用
```

**优化方案：**
- 优化提示词
- 使用更快的模型（Haiku）
- 添加快速响应路径

#### 3. 工具失败率高 🟡
```
工具 web_search 失败率 100%
```

**优化方案：**
- 检查 API 配置
- 添加重试机制
- 提供降级方案

#### 4. 子 Agent 效率低 🟡
```
子 Agent IntentRecognition 平均耗时 15s
```

**优化方案：**
- 优化 Agent 提示词
- 减少工具调用次数
- 考虑缓存结果

## 📊 分析指标

### 时间分布分析

每个运行的时间分为三部分：
1. **子 Agent 时间**: 子 Agent 执行耗时
2. **LLM 调用时间**: LLM API 调用耗时
3. **其他时间**: 网络请求、文件 I/O、工具执行等

示例：
```
Run f0f913d5 (261.11s):
  子 Agent: 0.00s (0.0%)
  LLM 调用: 7.14s (2.7%)
  其他: 253.96s (97.3%)  ← 主要瓶颈
```

### 工具成功率

```
✅ web_search: 2 次 (100% 成功)
⚠️ api_call: 5 次 (60% 成功)
❌ database_query: 3 次 (33% 成功)
```

## 🎨 与 Claude Code Insight 的对比

| 功能 | 本项目实现 | Claude Code Insight |
|------|-----------|---------------------|
| 调用链路可视化 | ✅ 树形结构 | ✅ 图形界面 |
| 时间线分析 | ✅ 文本格式 | ✅ 可视化时间轴 |
| 性能瓶颈识别 | ✅ 时间分布 | ✅ 火焰图 |
| 优化建议 | ✅ 自动生成 | ✅ AI 驱动 |
| Token 使用分析 | ⏳ 待实现 | ✅ 详细统计 |
| 成本估算 | ⏳ 待实现 | ✅ 实时计算 |
| 交互式探索 | ❌ 命令行 | ✅ Web UI |
| 集成方式 | ✅ REPL 命令 | ✅ IDE 插件 |

## 🚀 使用场景

### 场景 1: 开发调试
```bash
# 在 REPL 中实时分析
python -m backend.main
agent >> 执行一些任务...
agent >> /insight  # 快速查看性能
```

### 场景 2: 性能优化
```bash
# 使用详细分析工具
python scripts/trace_insight.py .sessions/20260301_214209/trace.jsonl

# 查看调用树、时间线、详细建议
```

### 场景 3: 批量分析
```bash
# 分析多个 session
for session in .sessions/*/trace.jsonl; do
    echo "Analyzing $session"
    python scripts/trace_analyzer.py "$session"
done
```

## 💡 优化策略

### 1. 并行化
```python
# 串行（慢）
result1 = await tool1()
result2 = await tool2()

# 并行（快）
results = await asyncio.gather(tool1(), tool2())
```

### 2. 缓存
```python
from functools import lru_cache

@lru_cache(maxsize=100)
def expensive_operation(query):
    return search_api(query)
```

### 3. 提示词优化
```python
# 模糊（慢）
"帮我添加一个功能"

# 明确（快）
"在 backend/app/tools/ 创建 stock_tool.py，实现股票查询功能"
```

### 4. 模型选择
```python
# 简单任务用快速模型
if is_simple_task(prompt):
    model = "claude-haiku-4-5"
else:
    model = "claude-sonnet-4-6"
```

## 📈 实际效果

从测试 session 的分析结果：

### 发现的问题
1. **严重性能瓶颈**: Run f0f913d5 耗时 261s，97.3% 时间在网络请求
2. **无效运行**: Run 683b5114 无工具调用但耗时 8s
3. **工具成功率**: 所有工具 100% 成功（良好）

### 优化建议
1. 🔴 并行化 web_search 调用
2. 🟡 优化提示词，减少无效运行
3. ✅ 工具实现良好，无需优化

## 🔮 未来扩展

### 短期计划
- [ ] Token 使用分析
- [ ] API 成本估算
- [ ] HTML 报告导出
- [ ] 历史对比功能

### 长期计划
- [ ] 实时监控面板（Web UI）
- [ ] 火焰图可视化
- [ ] 自动优化建议（AI 驱动）
- [ ] 集成到 CI/CD

## 📝 技术实现

### Trace 文件格式

```json
// 运行开始
{"ts": 1772372573.594, "event": "run.start", "run_id": "683b5114", "prompt": "..."}

// 运行结束
{"ts": 1772372581.811, "event": "run.end", "run_id": "683b5114", "duration_ms": 8217}

// LLM 调用
{"ts": 1772372581.81, "event": "llm.fallback", "run_id": "683b5114", "duration_ms": 1902}

// 工具调用
{"ts": 1772373967.803, "event": "tool.result", "run_id": "78dbd16a", "tool": "list_dir", "ok": true}

// 子 Agent
{"ts": 1772373733.969, "event": "subagent.start", "run_id": "a420be68", "span_id": "53d44277"}
{"ts": 1772373741.296, "event": "subagent.end", "run_id": "a420be68", "span_id": "53d44277", "duration_ms": 7327}
```

### 核心算法

```python
# 时间分布计算
def analyze_time_distribution(run_data):
    total_duration = run_data['end']['duration_ms']

    # 子 Agent 时间
    subagent_time = sum(
        subagent['end']['duration_ms']
        for subagent in run_data['subagents']
    )

    # LLM 时间
    llm_time = sum(
        llm['duration_ms']
        for llm in run_data['llm_calls']
    )

    # 其他时间
    other_time = total_duration - subagent_time - llm_time

    return {
        'subagent': subagent_time / total_duration,
        'llm': llm_time / total_duration,
        'other': other_time / total_duration
    }
```

## 🎓 学习价值

通过实现这个工具，你将学习到：

1. **性能分析**: 如何识别和分析 AI Agent 的性能瓶颈
2. **数据处理**: 如何解析和分析 JSONL 格式的日志
3. **可视化**: 如何用文本格式展示复杂的调用关系
4. **优化策略**: 常见的 AI Agent 优化方法
5. **工具设计**: 如何设计易用的分析工具

## 📚 参考资源

- [Claude Code 官方文档](https://docs.anthropic.com/claude/code)
- [OpenTelemetry Tracing](https://opentelemetry.io/docs/concepts/signals/traces/)
- [Performance Analysis Best Practices](https://www.brendangregg.com/perf.html)

## 🤝 贡献

欢迎提交 PR 添加新功能：
- Token 使用分析
- 成本估算
- HTML/PDF 报告导出
- 实时监控面板
- 火焰图可视化

## 📄 许可证

MIT License
