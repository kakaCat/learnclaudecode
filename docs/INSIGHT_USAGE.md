# Trace Insight 集成使用指南

## 功能说明

在 Agent REPL 中集成了 Trace Insight 功能，可以实时分析当前 session 的性能。

## 使用方法

### 1. 启动 Agent

```bash
python -m backend.main
```

### 2. 在 REPL 中使用 /insight 命令

```bash
agent >> /insight
```

### 3. 查看分析报告

系统会自动分析当前 session 的 trace.jsonl 文件，并显示：

```
================================================================================
🔍 Session Trace Insight
================================================================================

📊 摘要
  运行次数: 4
  总耗时: 329.99s
  工具调用: 6
  子 Agent: 1

⚡ 性能分析
  最慢的运行:
    • f0f913d5: 261.11s - 我要对港股的阿里巴巴股票投资,你觉得什么价格范围内可以...
    • a420be68: 36.07s - 我想查询股票信息...
    • 78dbd16a: 24.60s - 帮我加个功能...

🔥 瓶颈分析
  Run f0f913d5 (261.11s):
    提示: 我要对港股的阿里巴巴股票投资,你觉得什么价格范围内可以...
    子 Agent: 0.00s (0.0%)
    LLM 调用: 7.14s (2.7%)
    其他: 253.96s (97.3%)  ← 主要瓶颈！

🔧 工具使用
  ✅ web_search: 2 次 (100% 成功)
  ✅ Task: 1 次 (100% 成功)
  ✅ list_dir: 1 次 (100% 成功)

💡 优化建议
  1. 🔴 运行 f0f913d5 耗时过长 (261.11s)
     建议: 考虑并行化、缓存或优化提示词
  2. 🟡 运行 683b5114 无工具调用但耗时 8.22s
     建议: 检查是否可以直接回答或需要添加工具
```

## 所有可用命令

```bash
agent >> /help

Commands:
  /compact  - 手动压缩对话历史
  /tasks    - 列出所有持久化任务
  /team     - 列出所有团队成员及状态
  /inbox    - 读取并清空 lead 的收件箱
  /sessions - 列出所有保存的 session
  /insight  - 分析当前 session 的性能 ⭐新增
```

## 分析指标说明

### 📊 摘要
- **运行次数**: 总共执行了多少次 AI 调用
- **总耗时**: 所有运行的总时间
- **工具调用**: 调用了多少次工具
- **子 Agent**: 启动了多少个子 Agent

### ⚡ 性能分析
显示最慢的 3 个运行，帮助识别性能瓶颈。

### 🔥 瓶颈分析
分析每个运行的时间分布：
- **子 Agent**: 子 Agent 执行时间
- **LLM 调用**: LLM API 调用时间
- **其他**: 网络请求、文件 I/O 等其他操作时间

### 🔧 工具使用
统计每个工具的调用次数和成功率：
- ✅ 100% 成功
- ⚠️ 50-99% 成功
- ❌ <50% 成功

### 💡 优化建议
自动识别问题并提供优化建议：
- 🔴 高优先级（耗时 >60s）
- 🟡 中优先级（耗时 30-60s 或其他问题）
- 🟢 低优先级（轻微问题）

## 优化示例

### 问题 1: 运行耗时过长

```
🔴 运行 f0f913d5 耗时过长 (261.11s)
   其他: 253.96s (97.3%)
```

**原因**: 97.3% 的时间花在网络请求上

**解决方案**:
```python
# 1. 并行化多个 web_search
results = await asyncio.gather(
    web_search(query1),
    web_search(query2)
)

# 2. 添加缓存
@lru_cache(maxsize=100)
def search_with_cache(query):
    return web_search(query)
```

### 问题 2: 无工具调用但耗时长

```
🟡 运行 683b5114 无工具调用但耗时 8.22s
```

**原因**: 提示词不明确，AI 需要更多时间理解

**解决方案**:
```python
# 模糊提示（慢）
"帮我添加一个功能"

# 明确提示（快）
"在 backend/app/tools/ 创建 stock_tool.py，实现股票查询功能"
```

### 问题 3: 工具失败率高

```
🟡 工具 web_search 失败率过高 (100%)
```

**解决方案**:
```python
# 添加重试机制
@retry(max_attempts=3, backoff=2)
def web_search(query):
    return api.search(query)

# 添加降级方案
try:
    result = web_search(query)
except Exception:
    result = fallback_search(query)
```

## 与独立脚本的对比

| 功能 | /insight 命令 | scripts/trace_insight.py |
|------|--------------|-------------------------|
| 使用场景 | REPL 中实时分析 | 离线批量分析 |
| 启动方式 | `/insight` | `python scripts/trace_insight.py <file>` |
| 分析对象 | 当前 session | 任意 trace 文件 |
| 输出格式 | 简洁版 | 详细版（含时间线、调用树） |
| 适用时机 | 开发调试 | 性能优化、报告生成 |

## 最佳实践

1. **定期检查**: 每完成一个功能后运行 `/insight`
2. **对比优化**: 优化前后对比性能变化
3. **关注趋势**: 追踪平均耗时和成功率
4. **优先修复**: 先解决 🔴 高优先级问题
5. **持续改进**: 根据建议持续优化

## 故障排查

### 问题: 提示 "No trace file found"

**原因**: 当前 session 还没有生成 trace 文件

**解决**: 先执行一些命令，然后再运行 `/insight`

### 问题: 分析结果为空

**原因**: trace 文件为空或格式错误

**解决**: 检查 `.sessions/<session_key>/trace.jsonl` 文件

## 扩展功能

如果需要更详细的分析，可以使用独立脚本：

```bash
# 详细分析（含调用树、时间线）
python scripts/trace_insight.py .sessions/20260301_214209/trace.jsonl

# 基础分析
python scripts/trace_analyzer.py .sessions/20260301_214209/trace.jsonl
```

## 贡献

欢迎提交 PR 添加新功能：
- 导出报告（JSON/HTML/PDF）
- 实时监控面板
- Token 使用分析
- 成本估算
- 历史对比

## 许可证

MIT License
