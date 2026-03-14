# 为什么经验学习需要 LLM？

## 问题演示

### 当前纯规则系统的问题

查看 `backend/memory/TOOLS.md` 的末尾：

```markdown
## 强化学习经验 (2026-03-14 01:16:01)
### Web Query 任务
**推荐工具序列**: spawn_subagent → curl → curl → curl → curl → workspace_list
**成功次数**: 1

## 强化学习经验 (2026-03-14 01:16:16)
### Web Query 任务
**推荐工具序列**: spawn_subagent → curl → curl → curl → curl → workspace_list
**成功次数**: 1

## 强化学习经验 (2026-03-14 01:16:36)
### Web Query 任务
**推荐工具序列**: spawn_subagent → curl → curl → curl → curl → workspace_list
**成功次数**: 1
```

**问题**：
1. ❌ **重复记录**：相同的模式被记录了 3 次
2. ❌ **无意义的描述**："Web Query 任务" 太泛化
3. ❌ **缺少上下文**：不知道这个序列为什么成功
4. ❌ **无法判断价值**：`curl → curl → curl → curl` 是合理的还是冗余的？

## 对比：规则 vs LLM

### 场景1: 经验质量评估

#### 规则系统
```python
def should_record(pattern):
    # 简单规则：工具数量 >= 2 就记录
    return len(pattern['tools']) >= 2
```

**结果**：所有模式都被记录，包括无价值的

#### LLM 系统
```python
def should_record(pattern):
    # LLM 理解语义
    evaluation = llm.evaluate(f"""
    这个模式值得记录吗？
    任务: {pattern['task']}
    工具: {pattern['tools']}

    考虑：
    1. 是否通用？
    2. 是否高效？
    3. 是否有学习价值？
    """)
    return evaluation['should_record']
```

**结果**：只记录有价值的模式

### 场景2: 去重判断

#### 规则系统
```python
def is_duplicate(new, existing):
    # 精确匹配
    return new['tool_sequence'] == existing['tool_sequence']
```

**问题**：
- `spawn_subagent → curl → curl`
- `spawn_subagent → curl → curl → curl`

这两个是重复吗？规则系统说"不是"，但实际上可能是同一个模式的变体。

#### LLM 系统
```python
def is_duplicate(new, existing):
    result = llm.judge(f"""
    这两个模式是否本质相同？

    新模式: {new}
    已有模式: {existing}

    判断标准：
    - 解决的问题是否相同？
    - 核心步骤是否一致？
    - 差异是否重要？
    """)
    return result['is_duplicate']
```

**结果**：能识别语义上的重复

### 场景3: 生成有意义的总结

#### 规则系统
```python
def generate_summary(patterns):
    return f"""
    ### {patterns[0]['task_type']} 任务
    **工具序列**: {' → '.join(patterns[0]['tools'])}
    **成功次数**: {len(patterns)}
    """
```

**输出**：
```markdown
### Web Query 任务
**工具序列**: spawn_subagent → curl → curl → curl
**成功次数**: 3
```

**问题**：没有告诉我"为什么"、"什么时候用"、"注意什么"

#### LLM 系统
```python
def generate_summary(patterns):
    return llm.summarize(f"""
    基于这些成功案例生成记忆：
    {patterns}

    要求：
    1. 提炼成功要素
    2. 给出使用建议
    3. 标注适用场景
    """)
```

**输出**：
```markdown
### 机票查询任务的最佳实践

**适用场景**:
需要从网站获取实时航班信息时（如飞猪、携程）

**推荐做法**:
1. 使用 spawn_subagent(type="CDPBrowser") 启动浏览器
2. 通过多次 curl 检查子 agent 状态
3. 用 workspace_list 确认结果文件生成

**注意事项**:
- 某些网站需要登录，优先选择飞猪
- 等待页面加载完成再提取数据
- 验证返回的航班信息是否完整

**成功案例**: 3 次（北京→厦门、哈尔滨→北京、北京→杭州）
```

**差异**：LLM 生成的总结有实际指导价值

## 具体改进点

### 1. 质量评估

**规则系统**：
```python
# 只能用简单阈值
if len(tools) >= 3 and "spawn_subagent" in tools:
    record = True
```

**LLM 系统**：
```python
# 理解任务和工具的匹配度
evaluation = llm.evaluate("""
这个工具序列对于"查询机票"任务是否合理？
- spawn_subagent: 启动浏览器 ✓
- curl × 4: 检查状态（是否过多？）
- workspace_list: 查看结果 ✓

判断：工具选择合理，但 4 次 curl 可能可以优化为等待机制
""")
```

### 2. 智能去重

**规则系统**：
```python
# 只能精确匹配
if new_seq == existing_seq:
    skip()
```

**LLM 系统**：
```python
# 语义理解
llm.judge("""
模式A: spawn_subagent → curl → curl → workspace_list
模式B: spawn_subagent → curl → curl → curl → workspace_list

这两个模式本质上是否相同？
答：是的，都是"启动子agent → 轮询状态 → 获取结果"，
    只是轮询次数不同，应该合并为一个模式
""")
```

### 3. 上下文理解

**规则系统**：
```python
# 只看工具名称
tools = ["spawn_subagent", "curl", "curl"]
```

**LLM 系统**：
```python
# 理解工具的作用和上下文
llm.analyze("""
工具序列：spawn_subagent → curl → curl

上下文：
- spawn_subagent 的参数是 CDPBrowser
- curl 的目标是检查子 agent 的 inbox
- 任务是查询机票

理解：这是一个"派发子任务 → 等待完成"的模式
""")
```

## 实际效果对比

### 纯规则系统（当前）

**记录内容**：
```markdown
## 强化学习经验 (2026-03-14 01:16:36)

### Web Query 任务
**关键词**: 航班, 查询
**推荐工具序列**: spawn_subagent → curl → curl → curl → curl → workspace_list
**成功次数**: 1
```

**问题**：
- 重复记录
- 描述泛化
- 无指导价值

### LLM 增强系统（改进后）

**记录内容**：
```markdown
## 强化学习经验 (2026-03-14 01:20:00)

### 航班信息查询的标准流程

**适用场景**:
从旅游网站（飞猪、携程等）获取实时航班数据

**核心模式**:
1. 派发 CDPBrowser 子 agent 访问目标网站
2. 轮询检查子 agent 执行状态（通常 2-4 次）
3. 确认结果文件已生成到 workspace

**工具序列**:
spawn_subagent → [curl × N] → workspace_list

**优化建议**:
- 可以用 check_background 替代多次 curl
- 设置合理的超时时间避免无限等待

**成功案例**:
- 北京→厦门 (6 次工具调用)
- 哈尔滨→北京 (8 次工具调用)
- 平均成功率: 66% (2/3)

**失败教训**:
- 某些网站需要登录，提前检查可用性
```

**优势**：
- ✅ 去重合并
- ✅ 具体场景
- ✅ 可操作建议
- ✅ 包含失败教训

## 成本考虑

### 方案1: 完全使用 LLM
```python
# 每次都调用 LLM
for pattern in patterns:
    evaluation = llm.evaluate(pattern)  # 调用1
    duplicate = llm.check_duplicate(pattern)  # 调用2
    summary = llm.summarize(pattern)  # 调用3
```

**成本**: 高（每个 session 3+ 次调用）

### 方案2: 混合策略（推荐）
```python
# 规则预筛选 + LLM 精细处理
for pattern in patterns:
    # 规则快速判断
    if not quick_filter(pattern):
        continue

    # 只对候选模式使用 LLM
    if is_candidate(pattern):
        evaluation = llm.evaluate(pattern)  # 只调用有价值的
```

**成本**: 低（每个 session 0-1 次调用）

### 方案3: 批量处理
```python
# 积累多个 session 后批量分析
if len(accumulated_patterns) >= 10:
    summary = llm.batch_analyze(accumulated_patterns)  # 1 次调用处理多个
```

**成本**: 最低（每 10 个 session 1 次调用）

## 结论

### 纯规则系统的局限
1. ❌ 无法理解语义
2. ❌ 无法判断价值
3. ❌ 无法智能去重
4. ❌ 生成的总结无指导意义

### LLM 的必要性
1. ✅ 理解任务和工具的匹配度
2. ✅ 识别语义上的重复
3. ✅ 生成有实际价值的建议
4. ✅ 从失败中学习

### 推荐方案

**混合策略**：
- 规则系统：快速筛选、基础判断
- LLM 系统：质量评估、去重、总结

**触发条件**：
- 发现新的成功模式 → 用 LLM 评估
- 检测到可能重复 → 用 LLM 判断
- 积累 5+ 个模式 → 用 LLM 生成总结

**成本控制**：
- 每个 session 最多 1 次 LLM 调用
- 批量处理降低频率
- 缓存 LLM 的判断结果

## 下一步

1. 实现 LLM 增强版本（已完成框架）
2. 集成到现有系统
3. A/B 测试对比效果
4. 优化 prompt 提高准确率
