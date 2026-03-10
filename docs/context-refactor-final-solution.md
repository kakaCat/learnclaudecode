# Context 架构重构 - 最终方案

## 问题分析

当前有两套运行逻辑：
1. **AgentService.run()** - 标准 LangChain ReAct loop
2. **subagents/__init__.py** - 自定义 loop（包含 tracer、压缩、OODA 等）

## 正确的架构

```
Task tool
  ↓
subagents.run_subagent_with_context(sub_context, prompt, ...)
  ↓
使用 SubagentContext 的资源（llm, tracer, tools）
  ↓
运行自定义 loop（_run_react_loop / _run_ooda_loop）
```

## 实现方案

### 1. 修改 `subagents/__init__.py`

添加新函数 `run_subagent_with_context()`：

```python
def run_subagent_with_context(
    sub_context: "SubagentContext",
    description: str,
    prompt: str,
    recursion_limit: int = 100
) -> str:
    """
    使用 SubagentContext 运行 Subagent（新架构）

    Args:
        sub_context: SubagentContext 实例（继承 BaseContext，共享资源）
        description: 任务描述
        prompt: 用户输入
        recursion_limit: 递归限制

    Returns:
        Subagent 输出
    """
    subagent_type = sub_context.subagent_type

    # 使用 SubagentContext 的资源
    llm = sub_context.llm  # 继承自 BaseContext
    tools = sub_context.tools  # 过滤后的工具
    tracer = sub_context.tracer  # 继承自 BaseContext
    system_prompt = sub_context.system_prompt

    # 1. 检查并截断 prompt
    prompt = _check_and_truncate_prompt(prompt, llm)

    # 2. 开始 span
    span_id, start = _start_span(subagent_type, description, tools)

    # 3. 执行（根据类型选择 loop）
    if subagent_type == "OODASubagent":
        output, tool_count = _run_ooda_loop(
            llm=llm,
            sub_tools=tools,
            sub_system=system_prompt,
            prompt=prompt,
            subagent_type=subagent_type,
            span_id=span_id
        )
    elif not tools:
        output, tool_count = _invoke_direct(llm, system_prompt, prompt)
    else:
        agent = sub_context.agent  # 使用 SubagentContext 的 agent
        output, tool_count = _run_react_loop(
            agent=agent,
            prompt=prompt,
            subagent_type=subagent_type,
            span_id=span_id,
            llm=llm,
            sub_system=system_prompt,
            recursion_limit=recursion_limit
        )

    # 4. 结束 span
    _end_span(span_id, subagent_type, tool_count, start, output)

    # 5. 保存 session（使用 SubagentContext 的 session_store）
    sub_context.session_store.save_turn(
        subagent_type,
        prompt,
        output,
        []  # tool_calls_data
    )

    return output or "(subagent returned no text)"
```

### 2. 修改 `spawn_tool.py`

```python
def Task(description: str, prompt: str, subagent_type: str, recursion_limit: int = 100) -> str:
    # 创建 SubagentContext（继承 BaseContext，共享资源）
    sub_context = main_context.create_subagent(subagent_type)

    # 使用 subagents 模块的运行逻辑
    from backend.app.subagents import run_subagent_with_context
    result = run_subagent_with_context(
        sub_context=sub_context,
        description=description,
        prompt=prompt,
        recursion_limit=recursion_limit
    )

    return result
```

## 优势

✅ **保留自定义逻辑**：tracer、压缩、OODA loop 等
✅ **使用共享资源**：通过 SubagentContext 继承 BaseContext
✅ **代码复用**：不重复创建 LLM、tracer 等
✅ **架构清晰**：SubagentContext 提供资源，subagents 提供运行逻辑

## 对比

### 旧方案（错误）
```
Task tool → AgentService(sub_context).run()
→ 使用标准 LangChain loop
→ 丢失了自定义逻辑（tracer、OODA 等）
```

### 新方案（正确）
```
Task tool → run_subagent_with_context(sub_context, ...)
→ 使用 SubagentContext 的资源
→ 运行自定义 loop（保留所有逻辑）
```
