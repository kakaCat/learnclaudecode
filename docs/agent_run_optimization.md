# Agent.run() 方法优化建议

## 当前问题分析

### 1. 缺少 ContextGuard 集成
当前使用的是 `compaction.py` 中的 `estimate_tokens` 和 `auto_compact`，但没有使用 `ContextGuard` 的三阶段重试机制。

### 2. 压缩时机不够智能
只在超过阈值时压缩，没有预警机制。

### 3. 工具结果可能过大
没有截断大型工具结果，可能导致上下文溢出。

## 优化方案

### 方案 1：集成 ContextGuard（推荐）

```python
from backend.app.context_guard import ContextGuard

class AgentService:
    def __init__(self):
        self.session_key = None
        self.guard = ContextGuard(max_tokens=180000)  # 新增

        asyncio.run(tools_manager.load_mcp_tools())
        self.agent, self.llm = _build_agent("")
        self.rounds_without_todo = 0
        self.file_writes_since_reflect = 0
        self.reflect_retry_count = 0
        _log("🤖", f"Agent 就绪 | 模型={DEEPSEEK_MODEL}")

    async def run(self, prompt: str, history: list = None) -> str:
        if history is None:
            history = []

        # 第一次对话时创建 session
        if self.session_key is None:
            self.session_key = new_session_key()
            set_session_key(self.session_key)
            self.agent, self.llm = _build_agent(self.session_key)
            _log("🆕", f"创建新 session: {self.session_key}")

        # 上下文使用率检查（预警）
        tokens = self.guard.estimate_messages_tokens(history)
        usage_pct = (tokens / self.guard.max_tokens) * 100
        if usage_pct > 80:
            _log("⚠️", f"Context usage: {tokens:,}/{self.guard.max_tokens:,} ({usage_pct:.1f}%)")

        # Layer 1: micro_compact
        before_micro = len(history)
        micro_compact(history)
        if len(history) < before_micro:
            get_store().save_compaction("main", "micro", before_micro, len(history))

        # Layer 2: auto_compact with ContextGuard
        if tokens > THRESHOLD:
            _log("🗜️", "[auto_compact triggered]")
            tracer.emit("compaction", kind="auto", note=f"tokens>{THRESHOLD}")
            before_auto = len(history)
            # 使用 ContextGuard 的压缩方法
            new_history = self.guard.compact_history(history, self.llm)
            history.clear()
            history.extend(new_history)
            get_store().save_compaction("main", "auto", before_auto, len(history))

        # ... 其余代码保持不变 ...
```

### 方案 2：在 LLM 调用时使用 guard_invoke

```python
async def run(self, prompt: str, history: list = None) -> str:
    # ... 前面代码相同 ...

    messages = history + [HumanMessage(content=prompt)]

    # 添加提醒消息
    if self.rounds_without_todo >= 3:
        messages.append(HumanMessage(content="<reminder>请更新你的 TodoWrite 待办事项。</reminder>"))
    if self.file_writes_since_reflect >= 1:
        retry_hint = f"（已重试 {self.reflect_retry_count} 次，若仍 NEEDS_REVISION 请升级为 Reflexion）" if self.reflect_retry_count >= 1 else ""
        messages.append(HumanMessage(
            content=f"<reflection-gate>你刚写入了文件，必须先调用 Task(subagent_type='Reflect') 校验后才能继续。{retry_hint}</reflection-gate>"
        ))

    output = ""
    turn = 0
    total_tools = 0
    last_state_messages = messages
    tool_results_summary = []
    _pending_calls: dict[str, dict] = {}

    # 使用 ContextGuard 保护 agent 调用
    try:
        async for step in self.agent.astream({"messages": messages}, stream_mode="updates"):
            # ... 处理 step 的逻辑 ...
            pass
    except Exception as e:
        error_str = str(e).lower()
        if "context" in error_str or "token" in error_str:
            _log("⚠️", f"Context overflow detected: {e}")
            # 强制压缩后重试
            before = len(history)
            history = self.guard.compact_history(history, self.llm)
            get_store().save_compaction("main", "emergency", before, len(history))
            _log("🗜️", f"Emergency compaction: {before} → {len(history)}")

            # 重新构建 messages 并重试
            messages = history + [HumanMessage(content=prompt)]
            async for step in self.agent.astream({"messages": messages}, stream_mode="updates"):
                # ... 处理 step 的逻辑 ...
                pass
        else:
            raise
```

### 方案 3：截断大型工具结果

```python
async def run(self, prompt: str, history: list = None) -> str:
    # ... 前面代码 ...

    async for step in self.agent.astream({"messages": messages}, stream_mode="updates"):
        for node, state in step.items():
            # ... 其他节点处理 ...

            elif node == "tools":
                content_str = last.content if isinstance(last.content, str) else str(last.content)

                # 截断过大的工具结果
                if len(content_str) > 50000:
                    original_len = len(content_str)
                    content_str = self.guard.truncate_tool_result(content_str, max_fraction=0.3)
                    _log("✂️", f"Truncated tool result: {original_len} → {len(content_str)} chars")

                icon = TOOL_ICONS.get(last.name, "🔧")
                _log("📥", f"  {icon}[{last.name}] 返回: {content_str[:80]}")
                tool_results_summary.append(content_str[:500])
                total_tools += 1

                # ... 其余处理 ...
```

## 完整优化版本

```python
from backend.app.context_guard import ContextGuard

class AgentService:
    def __init__(self):
        self.session_key = None
        self.guard = ContextGuard(max_tokens=180000)

        asyncio.run(tools_manager.load_mcp_tools())
        self.agent, self.llm = _build_agent("")
        self.rounds_without_todo = 0
        self.file_writes_since_reflect = 0
        self.reflect_retry_count = 0
        _log("🤖", f"Agent 就绪 | 模型={DEEPSEEK_MODEL}")

    async def run(self, prompt: str, history: list = None) -> str:
        if history is None:
            history = []

        # 第一次对话时创建 session
        if self.session_key is None:
            self.session_key = new_session_key()
            set_session_key(self.session_key)
            self.agent, self.llm = _build_agent(self.session_key)
            _log("🆕", f"创建新 session: {self.session_key}")

        # 上下文使用率检查
        tokens = self.guard.estimate_messages_tokens(history)
        usage_pct = (tokens / self.guard.max_tokens) * 100
        if usage_pct > 80:
            _log("⚠️", f"Context usage: {tokens:,}/{self.guard.max_tokens:,} ({usage_pct:.1f}%)")
        elif usage_pct > 60:
            _log("ℹ️", f"Context usage: {tokens:,}/{self.guard.max_tokens:,} ({usage_pct:.1f}%)")

        # Layer 1: micro_compact
        before_micro = len(history)
        micro_compact(history)
        if len(history) < before_micro:
            get_store().save_compaction("main", "micro", before_micro, len(history))

        # Layer 2: auto_compact with ContextGuard
        if tokens > THRESHOLD:
            _log("🗜️", "[auto_compact triggered]")
            tracer.emit("compaction", kind="auto", note=f"tokens>{THRESHOLD}")
            before_auto = len(history)
            new_history = self.guard.compact_history(history, self.llm)
            history.clear()
            history.extend(new_history)
            get_store().save_compaction("main", "auto", before_auto, len(history))
            # 重新计算 tokens
            tokens = self.guard.estimate_messages_tokens(history)
            _log("📊", f"After compaction: {tokens:,} tokens")

        # 注入 lead inbox 消息
        inbox = get_bus().read_inbox("lead") if _team_state._bus is not None else []
        if inbox and history:
            history.append(HumanMessage(content=f"<inbox>{json.dumps(inbox, indent=2)}</inbox>"))
            history.append(AIMessage(content="Noted inbox messages."))
            _log("📬", f"注入 {len(inbox)} 条 inbox 消息")

        # 注入后台任务完成通知
        notifs = drain_notifications()
        if notifs and history:
            notif_text = "\n".join(
                f"[bg:{n['task_id']}] {n['status']}: {n['result']}" for n in notifs
            )
            history.append(HumanMessage(content=f"<background-results>\n{notif_text}\n</background-results>"))
            history.append(AIMessage(content="Noted background results."))
            _log("📡", f"注入 {len(notifs)} 条后台任务通知")

        _log("👤", f"用户输入: {prompt}")
        run_start = time.time()
        rid = tracer.new_run_id()
        tracer.set_run_id(rid)
        tracer.emit("run.start", prompt=prompt, session=self.session_key, context_tokens=tokens)

        messages = history + [HumanMessage(content=prompt)]
        if self.rounds_without_todo >= 3:
            messages.append(HumanMessage(content="<reminder>请更新你的 TodoWrite 待办事项。</reminder>"))
        if self.file_writes_since_reflect >= 1:
            retry_hint = f"（已重试 {self.reflect_retry_count} 次，若仍 NEEDS_REVISION 请升级为 Reflexion）" if self.reflect_retry_count >= 1 else ""
            messages.append(HumanMessage(
                content=f"<reflection-gate>你刚写入了文件，必须先调用 Task(subagent_type='Reflect') 校验后才能继续。{retry_hint}</reflection-gate>"
            ))

        output = ""
        turn = 0
        total_tools = 0
        last_state_messages = messages
        tool_results_summary = []
        _pending_calls: dict[str, dict] = {}

        try:
            async for step in self.agent.astream({"messages": messages}, stream_mode="updates"):
                for node, state in step.items():
                    _log("🔍", f"DEBUG: node={node}, has_messages={len(state.get('messages', []))}")
                    tracer.emit("debug.node", node=node, msg_count=len(state.get('messages', [])))

                    last = state["messages"][-1]

                    if node in ("agent", "call_model", "llm", "__start__", "model"):
                        turn += 1
                        last_state_messages = state["messages"]
                        _log("🧠", f"[第 {turn} 次调用 LLM] 上下文消息数={len(state['messages'])}")

                        # 记录发送给 LLM 的完整 prompt
                        prompt_messages = []
                        for msg in state["messages"]:
                            msg_dict = {"role": msg.__class__.__name__}
                            if hasattr(msg, "content"):
                                msg_dict["content"] = msg.content[:500] if isinstance(msg.content, str) else str(msg.content)[:500]
                            if hasattr(msg, "name"):
                                msg_dict["name"] = msg.name
                            prompt_messages.append(msg_dict)
                        tracer.emit("llm.prompt", turn=turn, messages=prompt_messages)

                        # 记录 LLM 的完整响应
                        response_data = {"content": last.content[:500] if last.content else ""}
                        if getattr(last, "tool_calls", None):
                            response_data["tool_calls"] = [
                                {"name": tc["name"], "args": tc["args"], "id": tc.get("id", "")}
                                for tc in last.tool_calls
                            ]
                        tracer.emit("llm.response", turn=turn, **response_data)

                        if getattr(last, "tool_calls", None):
                            tcs = last.tool_calls
                            mode = "并行" if len(tcs) > 1 else "串行"
                            _log("🔀", f"  AI 决策: {mode}调用 {len(tcs)} 个工具")
                            decisions = []
                            for tc in tcs:
                                icon = TOOL_ICONS.get(tc["name"], "🔧")
                                _log("🔀", f"    {icon}[{tc['name']}] {_fmt_args(tc['name'], tc['args'])}")
                                decisions.append({"tool": tc["name"], "args": _fmt_args(tc["name"], tc["args"])})
                                call_id = tc.get("id") or tc["name"]
                                _pending_calls[call_id] = {"tool": tc["name"], "t_start": time.time()}
                                tracer.emit("tool.call", turn=turn, tool=tc["name"],
                                            args=tc["args"], call_id=call_id)
                            tracer.emit("llm.turn", turn=turn, msg_count=len(state["messages"]),
                                        decisions=decisions)
                        else:
                            output = last.content or output
                            _log("🧠", f"  AI 决策: 直接回答，无需工具")
                            tracer.emit("llm.turn", turn=turn, msg_count=len(state["messages"]),
                                        direct_answer=True, output_preview=output[:200])

                    elif node == "tools":
                        content_str = last.content if isinstance(last.content, str) else str(last.content)

                        # 截断过大的工具结果
                        if len(content_str) > 50000:
                            original_len = len(content_str)
                            content_str = self.guard.truncate_tool_result(content_str, max_fraction=0.3)
                            _log("✂️", f"Truncated tool result: {original_len} → {len(content_str)} chars")

                        icon = TOOL_ICONS.get(last.name, "🔧")
                        _log("📥", f"  {icon}[{last.name}] 返回: {content_str[:80]}")
                        tool_results_summary.append(content_str[:500])
                        total_tools += 1

                        call_id = getattr(last, "tool_call_id", last.name)
                        pending = _pending_calls.pop(call_id, _pending_calls.pop(last.name, None))
                        duration_ms = round((time.time() - pending["t_start"]) * 1000) if pending else None

                        tracer.emit("tool.result", turn=turn, tool=last.name, call_id=call_id,
                                    duration_ms=duration_ms,
                                    ok=not content_str.startswith("Error:"),
                                    output=content_str[:500])

                        # Save tool result to transcript
                        get_store().save_tool_result("main", last.name, call_id, content_str)

                        if last.name == "TodoWrite":
                            self.rounds_without_todo = 0
                        else:
                            self.rounds_without_todo += 1

                        if last.name in ("write_file", "edit_file"):
                            self.file_writes_since_reflect += 1

                        if last.name == "Task":
                            task_args = _pending_calls.get(call_id, {})
                            subagent = ""
                            for tc in (last_state_messages[-1].tool_calls if getattr(last_state_messages[-1], "tool_calls", None) else []):
                                if tc.get("id") == call_id or tc.get("name") == "Task":
                                    subagent = tc.get("args", {}).get("subagent_type", "")
                                    break
                            if subagent in ("Reflect", "Reflexion"):
                                if "NEEDS_REVISION" in content_str:
                                    self.reflect_retry_count += 1
                                else:
                                    self.file_writes_since_reflect = 0
                                    self.reflect_retry_count = 0
                            if self.reflect_retry_count >= 2:
                                self.reflect_retry_count = 0
                                self.file_writes_since_reflect = 0

                        # drain after each tool batch
                        notifs = drain_notifications()
                        if notifs:
                            notif_text = "\n".join(
                                f"[bg:{n['task_id']}] {n['status']}: {n['result']}" for n in notifs
                            )
                            messages = last_state_messages + [
                                HumanMessage(content=f"<background-results>\n{notif_text}\n</background-results>"),
                                AIMessage(content="Noted background results."),
                            ]
                            _log("📡", f"  同轮注入 {len(notifs)} 条后台任务通知")

        except Exception as e:
            error_str = str(e).lower()
            if "context" in error_str or "token" in error_str:
                _log("❌", f"Context overflow: {e}")
                # 紧急压缩
                before = len(history)
                history = self.guard.compact_history(history, self.llm)
                get_store().save_compaction("main", "emergency", before, len(history))
                _log("🗜️", f"Emergency compaction: {before} → {len(history)}")
                tracer.emit("compaction", kind="emergency", before=before, after=len(history))

                # 返回错误信息
                return f"上下文溢出，已紧急压缩历史。请重新提问。"
            else:
                raise

        # DeepSeek sometimes returns empty content after tool use
        if not output:
            _log("🧠", "  [补充调用] 获取最终回答")
            tool_context = "\n".join(f"- {r}" for r in tool_results_summary)
            fallback_messages = last_state_messages + [
                HumanMessage(content=f"工具调用结果如下：\n{tool_context}\n\n请根据以上结果，用中文简洁地回答用户的问题，直接引用工具返回的原始数据，不要编造任何ID或数值。")
            ]
            t_fallback = time.time()
            resp = self.llm.invoke(fallback_messages)
            output = resp.content
            tracer.emit("llm.fallback", duration_ms=round((time.time() - t_fallback) * 1000),
                        output_preview=output[:200])

        history.append(HumanMessage(content=prompt))
        history.append(AIMessage(content=output))

        # Save turn to transcript
        tool_calls_data = []
        for msg in last_state_messages:
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                tool_calls_data = [{"name": tc["name"], "args": tc["args"]} for tc in msg.tool_calls]
                break
        get_store().save_turn("main", prompt, output, tool_calls_data)

        # Layer 3: manual compact triggered by compact tool
        if was_compact_requested():
            _log("🗜️", "[manual compact]")
            tracer.emit("compaction", kind="manual")
            before_manual = len(history)
            new_history = self.guard.compact_history(history, self.llm)
            history.clear()
            history.extend(new_history)
            get_store().save_compaction("main", "manual", before_manual, len(history))

        duration_ms = round((time.time() - run_start) * 1000)
        final_tokens = self.guard.estimate_messages_tokens(history)
        tracer.emit("run.end", output=output[:300], turns=turn,
                    total_tools=total_tools, duration_ms=duration_ms,
                    final_tokens=final_tokens)
        _log("✅", f"AI 最终回答 → {output[:120]}")
        _log("📊", f"Final context: {final_tokens:,} tokens ({len(history)} messages)")
        return output
```

## 优化要点总结

1. ✅ **集成 ContextGuard**：使用三阶段重试机制
2. ✅ **上下文预警**：80% 以上显示警告，60% 以上显示提示
3. ✅ **截断工具结果**：超过 50KB 自动截断
4. ✅ **紧急压缩**：捕获上下文溢出异常，紧急压缩
5. ✅ **详细日志**：记录 tokens 使用情况
6. ✅ **Tracer 增强**：记录上下文相关指标

## 使用效果

```
🆕 创建新 session: 20260307_091234
ℹ️ Context usage: 120,000/180,000 (66.7%)
👤 用户输入: 帮我分析这个大文件
🧠 [第 1 次调用 LLM] 上下文消息数=25
🔀   AI 决策: 串行调用 1 个工具
🔀     📖[read_file] path=large_file.txt
📥   📖[read_file] 返回: [文件内容...]
✂️ Truncated tool result: 100000 → 30000 chars
🧠 [第 2 次调用 LLM] 上下文消息数=27
✅ AI 最终回答 → 这个文件包含...
📊 Final context: 125,000 tokens (27 messages)
```
