# Backend Agent 真正缺失的能力

> 分析时间: 2026-03-09
> 重新评估后的聚焦改进方向

## ✅ 已有的能力（不需要重复实现）

1. **推理循环** - ReAct loop (Reason→Act→Observe) 和 OODA loop (Observe→Orient→Decide→Act)
2. **规划能力** - Plan subagent 可以分析代码库并创建任务
3. **意图识别** - IntentRecognition 和 Clarification subagent
4. **记忆搜索** - hybrid_search_memory (关键词+向量+时间衰减+MMR)
5. **反思机制** - Reflect 和 Reflexion subagent
6. **多种执行模式** - Explore、general-purpose、ScriptWriter 等

---

## ❌ 真正缺失的核心能力

### 1. 主动记忆召回（未集成到主流程）

**现状**:
- `auto_recall_memory()` 函数已实现但未在 `agent.py` 中调用
- 每次对话都是"失忆"状态，不会主动利用历史经验

**改进**:
```python
# 在 AgentService.run() 开始时
async def run(self, prompt: str, history: list = None) -> str:
    # 自动召回相关记忆
    from backend.app.prompts import auto_recall_memory
    recalled = auto_recall_memory(self.context.get_session_key(), prompt)

    if recalled:
        # 注入到上下文
        memory_msg = HumanMessage(content=f"<recalled-context>\n{recalled}\n</recalled-context>")
        history = (history or []) + [memory_msg]
        _log("🧠", f"召回 {len(recalled.split('- '))-1} 条相关记忆")
```

**收益**: 利用历史经验、避免重复错误、个性化响应

---

### 2. 经验学习和模式识别

**现状**: 没有从成功/失败中学习的机制

**改进方案**:
```python
class ExperienceLibrary:
    """经验库 - 记录成功模式和失败案例"""

    def save_success_pattern(self, task_type: str, solution: dict):
        """保存成功案例"""
        self.store.save_memory(
            f"SUCCESS_{task_type}",
            json.dumps(solution),
            tags=["success", task_type]
        )

    def save_failure_case(self, task_type: str, error: str, attempted_solution: dict):
        """保存失败案例"""
        self.store.save_memory(
            f"FAILURE_{task_type}",
            json.dumps({"error": error, "attempted": attempted_solution}),
            tags=["failure", task_type]
        )

    def get_similar_solutions(self, task: str) -> List[dict]:
        """检索相似任务的解决方案"""
        results = self.store.hybrid_search_memory(task, top_k=3)
        return [r for r in results if "SUCCESS" in r.get("path", "")]
```

**集成点**:
```python
# 在工具调用成功后
if tool_result.success:
    self.experience.save_success_pattern(
        task_type=self._classify_task(prompt),
        solution={"tool": tool_name, "args": tool_args, "result": tool_result}
    )

# 在工具调用失败后
if tool_result.failed:
    self.experience.save_failure_case(
        task_type=self._classify_task(prompt),
        error=tool_result.error,
        attempted_solution={"tool": tool_name, "args": tool_args}
    )
```

---

### 3. 自我监控和进度感知

**现状**: Agent 不知道自己执行到哪一步，是否偏离目标

**改进方案**:
```python
class ProgressMonitor:
    """进度监控器"""

    def __init__(self):
        self.goal = ""
        self.steps_completed = []
        self.current_step = ""
        self.estimated_total = 0

    def set_goal(self, goal: str, estimated_steps: int):
        self.goal = goal
        self.estimated_total = estimated_steps

    def mark_step_complete(self, step: str):
        self.steps_completed.append(step)

    def get_progress(self) -> float:
        if self.estimated_total == 0:
            return 0.0
        return len(self.steps_completed) / self.estimated_total

    async def check_on_track(self, llm) -> dict:
        """检查是否偏离目标"""
        prompt = f"""
Goal: {self.goal}
Completed: {self.steps_completed}
Current: {self.current_step}

Are we on track? Return JSON:
{{"on_track": true/false, "reason": "...", "suggestion": "..."}}
"""
        result = await llm.ainvoke([HumanMessage(content=prompt)])
        return json.loads(result.content)
```

**集成点**:
```python
# 在 run() 开始时
self.progress_monitor.set_goal(prompt, estimated_steps=5)

# 每完成一个工具调用
self.progress_monitor.mark_step_complete(f"{tool_name} completed")

# 每 3 个工具调用后检查
if tool_count % 3 == 0:
    check = await self.progress_monitor.check_on_track(self.context.get_llm())
    if not check["on_track"]:
        _log("⚠️", f"偏离目标: {check['reason']}")
        _log("💡", f"建议: {check['suggestion']}")
```

---

### 4. 用户偏好学习

**现状**: 不记录用户的编码风格、工具偏好、沟通习惯

**改进方案**:
```python
class UserPreferenceTracker:
    """用户偏好追踪器"""

    def learn_from_interaction(self, user_input: str, agent_action: str, user_feedback: str):
        """从交互中学习"""
        # 分析用户是否满意
        if self._is_positive_feedback(user_feedback):
            self._save_preference("approved_action", agent_action)
        elif self._is_negative_feedback(user_feedback):
            self._save_preference("rejected_action", agent_action)

    def learn_tool_preference(self, task_type: str, tool_used: str, success: bool):
        """学习工具偏好"""
        key = f"tool_pref_{task_type}"
        prefs = self._load_preferences(key)
        prefs[tool_used] = prefs.get(tool_used, 0) + (1 if success else -1)
        self._save_preference(key, prefs)

    def get_preferred_tool(self, task_type: str) -> str:
        """获取首选工具"""
        prefs = self._load_preferences(f"tool_pref_{task_type}")
        return max(prefs.items(), key=lambda x: x[1])[0] if prefs else None
```

---

### 5. 智能重试和备选方案

**现状**: 工具失败后直接返回错误，缺少智能重试

**改进方案**:
```python
class SmartRetryHandler:
    """智能重试处理器"""

    async def retry_with_adjustment(self, tool_call: dict, error: str, llm) -> dict:
        """根据错误调整参数重试"""
        prompt = f"""
Tool: {tool_call['name']}
Args: {tool_call['args']}
Error: {error}

Suggest adjusted args to fix the error. Return JSON:
{{"adjusted_args": {{...}}, "reason": "..."}}
"""
        result = await llm.ainvoke([HumanMessage(content=prompt)])
        adjusted = json.loads(result.content)

        # 重试
        return await self._execute_tool(tool_call['name'], adjusted['adjusted_args'])

    async def try_alternative(self, tool_call: dict, error: str) -> dict:
        """尝试备选工具"""
        alternatives = {
            "read_file": ["bash cat", "grep"],
            "write_file": ["bash echo"],
            "glob": ["bash find", "list_dir"],
        }

        alt_tools = alternatives.get(tool_call['name'], [])
        for alt in alt_tools:
            try:
                result = await self._execute_alternative(alt, tool_call['args'])
                if result.success:
                    return result
            except:
                continue

        return {"success": False, "error": "All alternatives failed"}
```

---

## 🎯 优先级排序

### P0 - 立即实现（1周内）
1. **主动记忆召回** - 只需在 `agent.py` 中调用已有的 `auto_recall_memory()`
2. **用户偏好学习** - 记录工具使用成功率，优先选择成功率高的工具

### P1 - 重要提升（2-3周）
3. **经验学习** - 保存成功/失败案例，避免重复错误
4. **智能重试** - 工具失败时自动调整参数或切换备选方案

### P2 - 长期优化（1个月）
5. **自我监控** - 进度追踪和偏离检测

---

## 💡 最小改动示例

### 立即可用：集成记忆召回

```python
# backend/app/agent.py 第 80 行附近
async def run(self, prompt: str, history: list = None) -> str:
    if history is None:
        history = []

    # 【新增】自动召回相关记忆
    from backend.app.prompts import auto_recall_memory
    recalled = auto_recall_memory(self.context.get_session_key(), prompt)
    if recalled:
        memory_context = HumanMessage(content=f"<context>\n{recalled}\n</context>")
        history.insert(0, memory_context)
        _log("🧠", f"召回记忆: {len(recalled)} 字符")

    # 原有流程继续...
```

**效果**: 立即让 agent 能利用历史对话和保存的记忆，无需修改其他代码。

---

## 📊 预期改进效果

| 能力 | 当前状态 | 改进后 |
|------|---------|--------|
| 记忆利用 | 被动（需手动 memory_search） | 主动召回 |
| 错误恢复 | 失败即停止 | 智能重试+备选方案 |
| 经验积累 | 无 | 记录成功/失败模式 |
| 用户适应 | 无 | 学习偏好和习惯 |
| 自我感知 | 无 | 进度追踪+偏离检测 |

---

**总结**: 你的架构已经很完善（ReAct/OODA循环、规划、意图识别都有），真正缺的是：
1. 把已有的 `auto_recall_memory` 集成到主流程
2. 添加经验学习机制（成功/失败案例）
3. 实现智能重试和备选方案
4. 添加自我监控和进度感知

这些都是"连接层"的工作，不需要重新设计架构。
