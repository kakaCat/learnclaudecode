# Subagent 上下文压缩机制分析

## 当前状态

### 主 Agent 的压缩机制（完善）

**位置**: `backend/app/agent.py`

**流程**:
```python
def run(self, prompt: str, history: list = None):
    # 1. 准备上下文（应用压缩）
    history = self._prepare_context(history, prompt)

    # 2. 构建消息
    run.messages = self._build_messages(history, prompt)

    # 3. 执行 agent
    async for step in self.context.get_agent().astream({"messages": run.messages}):
        ...
```

**压缩策略** (`backend/app/memory/history.py`):
1. **MicroCompactionStrategy**: 移除连续相同消息
2. **AutoCompactionStrategy**: 超过 50K tokens 时自动压缩
3. **ManualCompactionStrategy**: 响应 `/compact` 命令

**压缩时机**:
- 每次 `run()` 调用前执行 `_prepare_context()`
- 调用 `conversation_history.apply_strategies()`
- 根据策略判断是否需要压缩

---

### Subagent 的压缩机制（不完善）

**位置**: `backend/app/subagents/__init__.py`

#### 1. 输入阶段压缩 ✅ (已修复)

**函数**: `_check_and_truncate_prompt()` (line 475-509)

```python
def run_subagent(description, prompt, subagent_type, base_tools, recursion_limit):
    # 1. 准备 subagent
    sub_tools, sub_system, llm = _prepare_subagent(subagent_type, base_tools)

    # 1.5. 检查并截断 prompt ✅ 新增
    prompt = _check_and_truncate_prompt(prompt, llm)

    # 2. 执行
    if not sub_tools:
        output, tool_count = _invoke_direct(llm, sub_system, prompt)
    else:
        output, tool_count = _invoke_with_tools(...)
```

**机制**:
- 估算 prompt token 数（`len(prompt) // 4`）
- 限制：100K tokens（为系统提示词留空间）
- 超过限制时截断到 400K 字符
- 在换行符处智能截断

**问题**: 只处理初始输入，不处理执行过程中的上下文增长

---

#### 2. 执行阶段压缩 ❌ (缺失)

**ReAct Loop** (`_run_react_loop`, line 195-268):

```python
for step in agent.stream(
    {"messages": [HumanMessage(content=prompt)]},  # ❌ 只有初始 prompt
    stream_mode="updates",
    config={"recursion_limit": recursion_limit},
):
    # 每轮工具调用后，消息列表会增长
    # state["messages"] 包含：
    # - 初始 HumanMessage
    # - AIMessage (tool_calls)
    # - ToolMessage (tool results)
    # - AIMessage (tool_calls)
    # - ToolMessage (tool results)
    # ...

    # ❌ 没有压缩机制
```

**问题**:
1. **消息累积**: 每次工具调用都会添加 AIMessage + ToolMessage
2. **无压缩**: 没有应用任何压缩策略
3. **溢出风险**: 多轮工具调用后可能超出 131K token 限制

**OODA Loop** (`_run_ooda_loop`, line 275-410):

```python
for cycle in range(1, max_cycles + 1):
    # Observe phase
    obs_resp = llm.invoke([
        SystemMessage(content=sub_system),
        HumanMessage(content=f"Goal: {prompt}\nPrevious observations: {observations}\n...")
    ])

    # Orient phase
    orient_resp = llm.invoke([
        SystemMessage(content=sub_system),
        HumanMessage(content=f"Goal: {prompt}\nObservations: {observations}\n...")
    ])

    # Decide phase
    decide_resp = llm.invoke([
        SystemMessage(content=sub_system),
        HumanMessage(content=f"Goal: {prompt}\nSituation: {situation}\n...")
    ])

    # ❌ observations 列表不断增长，没有压缩
```

**问题**:
1. **observations 累积**: 每个 cycle 都添加新的观察结果
2. **重复传递**: 每次 LLM 调用都传递完整的 observations
3. **无限制增长**: 没有长度限制或压缩机制

---

## 问题总结

### 1. ReAct Loop 的问题

| 问题 | 影响 | 严重性 |
|------|------|--------|
| 消息列表无限增长 | 多轮工具调用后超出 token 限制 | 🔴 高 |
| 没有压缩策略 | 无法处理长时间运行的 subagent | 🔴 高 |
| 依赖 LangGraph 内部状态 | 无法手动干预消息列表 | 🟡 中 |

### 2. OODA Loop 的问题

| 问题 | 影响 | 严重性 |
|------|------|--------|
| observations 无限增长 | 每个 cycle 都传递更多上下文 | 🔴 高 |
| 没有总结机制 | 重复传递相同信息 | 🟡 中 |
| 固定 max_cycles=6 | 无法处理复杂任务 | 🟢 低 |

### 3. 通用问题

| 问题 | 影响 | 严重性 |
|------|------|--------|
| 没有 token 监控 | 不知道何时接近限制 | 🟡 中 |
| 没有溢出保护 | 超出限制时直接崩溃 | 🔴 高 |
| 没有历史压缩 | 无法复用主 Agent 的压缩策略 | 🟡 中 |

---

## 优化方案

### 方案 1: 为 Subagent 添加 ConversationHistory（推荐）

**思路**: 让 subagent 也使用 `ConversationHistory` 管理消息

**实现**:
```python
def _run_react_loop_with_compression(
    agent, prompt, subagent_type, span_id, llm, sub_system, recursion_limit
):
    from backend.app.memory import ConversationHistory

    # 创建历史管理器
    history = ConversationHistory.create_default(llm=llm, tools=[], max_tokens=100000)

    # 初始消息
    initial_messages = [HumanMessage(content=prompt)]
    history.set_messages(initial_messages)

    for step in agent.stream(
        {"messages": history.get_messages()},
        stream_mode="updates",
        config={"recursion_limit": recursion_limit},
    ):
        for node, state in step.items():
            if node == "agent":
                # 更新历史
                history.set_messages(state["messages"])

                # 应用压缩策略
                if history.estimate_tokens() > 80000:  # 80K tokens 阈值
                    history.apply_strategies()
                    print(f"   [subagent] compressed to {len(history.get_messages())} messages")

            elif node == "tools":
                # 工具执行后也更新历史
                history.set_messages(state["messages"])
```

**优点**:
- ✅ 复用现有压缩策略
- ✅ 自动监控 token 数量
- ✅ 支持多种压缩策略

**缺点**:
- ❌ 需要修改 ReAct loop 逻辑
- ❌ 可能影响 LangGraph 的状态管理

---

### 方案 2: 截断工具结果（简单）

**思路**: 限制每个 ToolMessage 的大小

**实现**:
```python
def _run_react_loop(agent, prompt, ...):
    for step in agent.stream(...):
        for node, state in step.items():
            if node == "tools":
                # 截断大型工具结果
                last = state["messages"][-1]
                if isinstance(last, ToolMessage) and len(last.content) > 10000:
                    truncated = last.content[:10000] + "\n\n[... truncated]"
                    state["messages"][-1] = ToolMessage(
                        content=truncated,
                        tool_call_id=last.tool_call_id
                    )
```

**优点**:
- ✅ 实现简单
- ✅ 不影响现有逻辑

**缺点**:
- ❌ 可能丢失重要信息
- ❌ 不解决消息累积问题

---

### 方案 3: 定期总结历史（折中）

**思路**: 每 N 轮工具调用后，用 LLM 总结历史

**实现**:
```python
def _run_react_loop(agent, prompt, ...):
    turn_count = 0

    for step in agent.stream(...):
        for node, state in step.items():
            if node == "agent":
                turn_count += 1

                # 每 5 轮总结一次
                if turn_count % 5 == 0 and len(state["messages"]) > 10:
                    summary = _summarize_history(state["messages"], llm, sub_system)
                    state["messages"] = [
                        HumanMessage(content=f"[Previous context summary]\n{summary}\n\n[Current task]\n{prompt}"),
                        AIMessage(content="Understood. Continuing...")
                    ]

def _summarize_history(messages, llm, system_prompt):
    """用 LLM 总结历史消息"""
    context = "\n".join(f"{type(m).__name__}: {str(m.content)[:200]}" for m in messages)
    summary = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"总结以下对话，保留关键信息：\n{context}")
    ])
    return summary.content
```

**优点**:
- ✅ 保留关键信息
- ✅ 控制上下文大小

**缺点**:
- ❌ 增加 LLM 调用次数
- ❌ 可能丢失细节

---

### 方案 4: OODA Loop 优化

**思路**: 限制 observations 列表大小，定期总结

**实现**:
```python
def _run_ooda_loop(...):
    observations = []
    max_observations = 10  # 最多保留 10 条观察

    for cycle in range(1, max_cycles + 1):
        # Observe phase
        obs_resp = llm.invoke([...])
        raw = _invoke_tools(obs_json.get("tools", []))

        # 截断每条观察结果
        truncated_obs = [r[:500] for r in raw]
        observations.extend(truncated_obs)

        # 限制 observations 大小
        if len(observations) > max_observations:
            # 总结旧的观察结果
            old_obs = observations[:max_observations//2]
            summary = _summarize_observations(old_obs, llm)
            observations = [f"[Summary] {summary}"] + observations[max_observations//2:]

        # Orient phase (使用压缩后的 observations)
        orient_resp = llm.invoke([
            SystemMessage(content=sub_system),
            HumanMessage(content=f"Goal: {prompt}\nObservations: {observations[-5:]}\n...")  # 只传递最近 5 条
        ])
```

**优点**:
- ✅ 控制 observations 大小
- ✅ 保留最近的观察结果

**缺点**:
- ❌ 可能丢失早期重要信息

---

## 推荐实施顺序

### Phase 1: 快速修复（已完成 ✅）
- [x] 添加 `_check_and_truncate_prompt()` 截断初始输入

### Phase 2: 工具结果截断（简单）
- [ ] 在 ReAct loop 中截断大型 ToolMessage
- [ ] 在 OODA loop 中限制每条观察结果大小

### Phase 3: 定期总结（中等）
- [ ] 在 ReAct loop 中每 N 轮总结历史
- [ ] 在 OODA loop 中总结旧的 observations

### Phase 4: 完整压缩机制（复杂）
- [ ] 为 subagent 集成 ConversationHistory
- [ ] 添加 token 监控和自动压缩
- [ ] 添加溢出保护（OverflowGuard）

---

## 测试场景

### 场景 1: 多轮工具调用
```python
# 触发条件：subagent 调用 10+ 次工具
# 预期：不应超出 token 限制
# 测试：运行 Explore agent 搜索大型代码库
```

### 场景 2: 大型工具结果
```python
# 触发条件：read_file 返回 50K+ 字符
# 预期：自动截断或压缩
# 测试：读取大型日志文件
```

### 场景 3: OODA 长时间运行
```python
# 触发条件：OODA loop 运行 6 个 cycles
# 预期：observations 不应无限增长
# 测试：复杂的规划任务
```

---

## 监控指标

建议添加以下监控：

```python
# 在 tracer 中记录
tracer.emit("subagent.context.size",
    span_id=span_id,
    turn=turn,
    message_count=len(messages),
    estimated_tokens=estimate_tokens(messages),
    compressed=False
)

# 压缩时记录
tracer.emit("subagent.context.compressed",
    span_id=span_id,
    before_count=before,
    after_count=after,
    strategy="truncate|summarize"
)
```

---

## 总结

**当前状态**:
- ✅ 主 Agent 有完善的压缩机制
- ✅ Subagent 有初始输入截断（新增）
- ❌ Subagent 执行过程中没有压缩机制
- ❌ 多轮工具调用后可能溢出

**优先级**:
1. 🔴 **高优先级**: 工具结果截断（防止单个结果过大）
2. 🟡 **中优先级**: 定期总结历史（控制累积增长）
3. 🟢 **低优先级**: 完整压缩机制（长期优化）

**建议**: 先实施 Phase 2（工具结果截断），快速解决当前问题，再逐步完善。
