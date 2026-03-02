# 错误提示优化说明

## 问题

用户在新 session 中运行 `/insight` 时，会看到：
```
❌ No trace file found for current session.
```

这个提示不够友好，没有说明原因和解决方法。

## 优化方案

### 1. 文件不存在的情况

**优化前：**
```
❌ No trace file found for current session.
```

**优化后：**
```
⚠️  当前 session 还没有 trace 数据
   提示: 先执行一些命令，然后再运行 /insight 分析性能
```

### 2. 文件为空的情况

**优化前：**
```
⚠️  Trace 文件为空
```

**优化后：**
```
⚠️  Trace 文件为空，还没有记录任何事件
   提示: 先执行一些命令，然后再运行 /insight 分析性能
```

## 改进点

1. ✅ **更友好的图标**: 使用 ⚠️ 而不是 ❌，表示这是正常情况而非错误
2. ✅ **清晰的原因**: 说明为什么没有数据
3. ✅ **可操作的建议**: 告诉用户如何解决
4. ✅ **中文提示**: 使用中文，更易理解

## 使用场景

### 场景 1: 新 session
```bash
python -m backend.main
agent >> /insight

⚠️  当前 session 还没有 trace 数据
   提示: 先执行一些命令，然后再运行 /insight 分析性能
```

### 场景 2: 执行命令后
```bash
agent >> 帮我分析一下项目结构
agent >> /insight

================================================================================
🔍 Session Trace Insight
================================================================================
...
```

## 技术实现

### backend/main.py
```python
if query == "/insight":
    from backend.app.insight import analyze_trace
    trace_file = get_session_dir() / "trace.jsonl"
    if not trace_file.exists():
        print("⚠️  当前 session 还没有 trace 数据")
        print("   提示: 先执行一些命令，然后再运行 /insight 分析性能")
        continue
    print()
    analyze_trace(trace_file)
    print()
    continue
```

### backend/app/insight.py
```python
if not events:
    print("⚠️  Trace 文件为空，还没有记录任何事件")
    print("   提示: 先执行一些命令，然后再运行 /insight 分析性能")
    return
```

## 总结

这不是 bug，而是正常的用户体验优化：
- ✅ 新 session 没有 trace 数据是正常的
- ✅ 提示更友好，告诉用户如何使用
- ✅ 避免用户困惑

## 相关文档

- [docs/INSIGHT_USAGE.md](../docs/INSIGHT_USAGE.md) - 使用指南
- [docs/INSIGHT_IMPLEMENTATION.md](../docs/INSIGHT_IMPLEMENTATION.md) - 实现总结
