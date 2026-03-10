---
name: self-heal
description: Analyze failed agent runs and implement fixes automatically
version: 1.0.0
author: System
tags: [debugging, reflection, self-improvement]
---

# Self-Healing Skill

分析失败的 Agent 运行记录，诊断问题并自动实施修复。

## 触发条件

当用户提到以下内容时触发：
- "分析失败原因"
- "为什么任务失败"
- "修复上次的问题"
- "@.sessions/{key}/trace.jsonl 分析"
- "agent 没有完成任务"

## 工作流程

### 1. 读取失败记录

```python
# 读取 trace.jsonl
trace_file = ".sessions/{session_key}/trace.jsonl"
with open(trace_file) as f:
    events = [json.loads(line) for line in f]
```

### 2. 分析失败模式

使用以下维度分析：

#### 工具调用失败
- 检查 `tool.result` 中的 `ok: false`
- 统计错误类型（SyntaxError, TimeoutError, etc.）
- 识别重复失败的工具调用

#### 策略问题
- 检查是否有更优策略未使用
- 识别低效的重复尝试（>5 次相同操作）
- 分析是否缺少必要的前置步骤

#### 逻辑错误
- 日期计算错误
- 数据解析错误
- 参数传递错误

### 3. 生成诊断报告

输出格式：

```markdown
## 失败分析报告

### 任务描述
{original_prompt}

### 执行统计
- 总轮次: {total_turns}
- 工具调用: {total_tool_calls}
- 失败次数: {failed_calls}
- 运行时长: {duration}

### 失败模式

#### 1. JavaScript 执行错误（出现 {count} 次）
- **错误类型**: SyntaxError: Illegal return statement
- **出现位置**: Turn 5, 7, 9, 11
- **根本原因**: CDP Runtime.evaluate 在全局作用域执行，不支持 return 语句

#### 2. 策略选择不当
- **问题**: 花费 20 轮次尝试表单交互，成功率低
- **更优方案**: 直接使用 URL 参数构造搜索结果页

#### 3. 日期处理错误
- **问题**: 查询 2026-03-11 但使用了 2025-03-11
- **原因**: 没有正确计算"明天"的日期

### 改进建议

1. **代码层面**：
   - 修改 cdp_tool.py 的 execute 动作，添加 IIFE 包装
   - 添加 eval 动作用于表达式求值
   - 添加日期解析辅助函数

2. **策略层面**：
   - 在 MEMORY.md 中添加 URL 构造优先策略
   - 添加失败重试和策略切换规则

3. **测试验证**：
   - 创建测试脚本验证修复效果
```

### 4. 制定修复方案

使用 TodoWrite 创建任务列表：

```python
todos = [
    {
        "content": "修改 cdp_tool.py 添加 IIFE 包装",
        "status": "pending",
        "activeForm": "代码修复"
    },
    {
        "content": "添加 eval 动作",
        "status": "pending",
        "activeForm": "代码修复"
    },
    {
        "content": "更新 MEMORY.md 添加策略规则",
        "status": "pending",
        "activeForm": "记忆优化"
    },
    {
        "content": "创建测试脚本",
        "status": "pending",
        "activeForm": "测试验证"
    }
]
```

### 5. 执行修复

按照任务列表逐项执行：

1. **读取相关文件**：使用 Read 工具
2. **分析代码结构**：理解现有实现
3. **实施修改**：使用 Edit 工具精确修改
4. **验证语法**：运行 `python -m py_compile`
5. **更新状态**：标记任务为 completed

### 6. 验证效果

创建测试脚本并运行：

```python
# 测试修复效果
python scripts/test_cdp_improvements.py
```

## 关键技术

### 失败模式识别

```python
def identify_failure_patterns(events):
    """识别失败模式"""
    patterns = {
        "javascript_errors": [],
        "repeated_failures": [],
        "strategy_issues": []
    }

    # 统计工具调用失败
    for event in events:
        if event["event"] == "tool.result" and not event.get("ok", True):
            error_msg = event.get("output", "")
            if "SyntaxError" in error_msg:
                patterns["javascript_errors"].append(event)

    # 检测重复失败
    tool_calls = [e for e in events if e["event"] == "tool.call"]
    for i, call in enumerate(tool_calls):
        if i > 0 and call["tool"] == tool_calls[i-1]["tool"]:
            # 检查是否连续失败
            patterns["repeated_failures"].append(call)

    return patterns
```

### 根因分析

```python
def analyze_root_cause(patterns):
    """分析根本原因"""
    if patterns["javascript_errors"]:
        # 分析 JavaScript 错误
        error_types = {}
        for error in patterns["javascript_errors"]:
            msg = error["output"]
            if "Illegal return" in msg:
                return {
                    "type": "javascript_scope_error",
                    "cause": "CDP Runtime.evaluate 在全局作用域执行",
                    "solution": "使用 IIFE 包装或添加 eval 动作"
                }

    if len(patterns["repeated_failures"]) > 5:
        return {
            "type": "strategy_failure",
            "cause": "当前策略成功率低，需要切换方法",
            "solution": "添加策略优先级和切换机制"
        }

    return {"type": "unknown", "cause": "需要人工分析"}
```

### 自动修复

```python
def auto_fix(root_cause):
    """自动应用修复"""
    if root_cause["type"] == "javascript_scope_error":
        # 修改 cdp_tool.py
        file_path = "backend/app/tools/implementations/cdp_tool.py"

        # 读取文件
        content = read_file(file_path)

        # 找到 execute 动作
        # 应用 IIFE 包装
        # 使用 Edit 工具修改

        return "已修复 JavaScript 执行问题"

    elif root_cause["type"] == "strategy_failure":
        # 更新 MEMORY.md
        memory_path = ".memory/MEMORY.md"

        # 添加策略规则
        new_content = """
## CDP Browser 策略优先级

1. 首选：直接构造 URL
2. 备选：表单填写
3. 最后：JavaScript 模拟
"""
        append_to_file(memory_path, new_content)

        return "已更新策略规则"
```

## 使用示例

### 示例 1: 分析失败的机票查询

```
用户: @.sessions/20260310_015346/trace.jsonl agent没有完成任务，分析一下原因

Agent:
1. 读取 trace 文件（156 行事件）
2. 分析发现：
   - JavaScript 语法错误 8 次
   - 表单交互失败 15 次
   - 日期处理错误 1 次
3. 根因：CDP execute 不支持全局 return
4. 制定方案：5 个修复任务
5. 执行修复：
   ✅ 修改 cdp_tool.py
   ✅ 添加 eval 动作
   ✅ 添加日期解析函数
   ✅ 更新 MEMORY.md
   ✅ 创建测试脚本
6. 验证：测试通过 ✅
```

### 示例 2: 持续改进

```
用户: 再次运行机票查询任务，看看是否修复成功

Agent:
1. 使用改进后的工具
2. 优先使用 URL 构造策略
3. 正确解析"明天"日期
4. 成功获取航班列表
5. 返回表格格式结果 ✅
```

## 注意事项

1. **不要过度修复**：只修复明确的问题，避免引入新 bug
2. **保留原有功能**：修改时确保向后兼容
3. **验证修复效果**：必须运行测试确认
4. **记录修复经验**：将成功案例写入 MEMORY.md

## 相关文档

- [Agent Self-Healing Guide](../../docs/development/agent-self-healing-guide.md)
- [CDP Browser Improvement Plan](../../docs/development/cdp-browser-improvement-plan.md)
