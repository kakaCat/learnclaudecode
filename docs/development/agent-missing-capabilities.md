# Backend Agent 缺失能力检查报告

> 检查时间: 2026-03-09
> 检查范围: P0/P1/P2 功能实现状态

## ✅ P0 - 已实现（Session 层）

### 1. 记忆系统基础设施 ✅

**已实现**:
- `MemoryStore` 类 - 两层存储（MEMORY.md + daily/*.jsonl）
- `write_memory(content, category)` - 支持分类（preference, fact, context）
- `search_memory(query)` - TF-IDF 搜索
- `hybrid_search_memory(query)` - 混合搜索（关键词+向量+时间衰减+MMR）
- `auto_recall_memory(session_key, user_message)` - 自动召回函数

**位置**:
- `backend/app/session/memory_store.py`
- `backend/app/prompts.py:180`

### 2. 主动记忆召回 ❌ 未集成

**状态**: 函数已实现但未在主流程调用

**问题**:
- `agent.py:80-130` 的 `run()` 方法中没有调用 `auto_recall_memory()`
- 每次对话都是"失忆"状态

**修复方案**:
```python
# backend/app/agent.py 第 107 行后添加
from backend.app.prompts import auto_recall_memory

async def run(self, prompt: str, history: list = None) -> str:
    # ... 现有代码 ...

    # 【新增】自动召回相关记忆
    recalled = auto_recall_memory(self.context.get_session_key(), prompt)
    if recalled:
        memory_msg = HumanMessage(content=f"<recalled-memory>\n{recalled}\n</recalled-memory>")
        history.insert(0, memory_msg)
        _log("🧠", f"召回 {len(recalled.split('- '))-1} 条记忆")
```

---

## ⚠️ P1 - 部分实现

### 3. 用户偏好学习 🟡 基础设施已有，缺少自动化

**已实现**:
- `write_memory(content, category="preference")` - 可以手动保存偏好
- 示例: `store.write_memory("用户喜欢使用 Python", category="preference")`

**缺失**:
- 没有自动从交互中学习偏好的机制
- 没有工具使用偏好统计
- 没有编码风格学习

**需要实现**:
```python
class PreferenceTracker:
    """用户偏好追踪器"""

    def track_tool_usage(self, tool_name: str, success: bool):
        """记录工具使用成功率"""
        key = f"tool_success_{tool_name}"
        stats = self._load_stats(key)
        stats["total"] = stats.get("total", 0) + 1
        stats["success"] = stats.get("success", 0) + (1 if success else 0)
        self._save_stats(key, stats)

    def get_preferred_tool(self, task_type: str) -> str:
        """获取首选工具（基于成功率）"""
        # 返回成功率最高的工具
        pass
```

### 4. 经验学习（成功/失败案例）❌ 未实现

**状态**: 完全缺失

**需要实现**:
- 成功案例保存
- 失败案例保存
- 相似案例检索

---

## ❌ P2 - 未实现（需要设计）

### 5. 智能重试机制 ❌

**状态**: 完全缺失

**当前行为**: 工具失败后直接返回错误，不重试

**需要设计**:
1. 错误分类（可重试 vs 不可重试）
2. 参数调整策略
3. 备选工具映射
4. 重试次数限制

### 6. 自我监控和进度感知 ❌

**状态**: 完全缺失

**需要设计**:
1. 目标设定和分解
2. 进度追踪（完成百分比）
3. 偏离检测（是否在正确轨道）
4. 自我检查点（每N步检查一次）

---

## 📋 优先级行动清单

### 立即可做（1天内）

1. **集成记忆召回** - 在 `agent.py` 中调用 `auto_recall_memory()`
   - 文件: `backend/app/agent.py:107`
   - 改动: 3-5 行代码
   - 收益: 立即让 agent 能利用历史经验

### 短期实现（1周内）

2. **工具使用统计** - 记录每个工具的成功/失败次数
   - 在工具调用后记录结果
   - 保存到 memory 的 `tool_stats` category
   - 优先选择高成功率工具

### 中期设计（2-3周）

3. **经验库设计** - 设计成功/失败案例的存储和检索
4. **智能重试设计** - 设计重试策略和备选方案

### 长期优化（1个月）

5. **自我监控系统** - 设计完整的进度追踪和偏离检测机制

---

## 🎯 P2 设计建议

### 智能重试机制设计

```python
class RetryStrategy:
    """重试策略"""

    # 错误分类
    RETRYABLE_ERRORS = {
        "FileNotFoundError": "adjust_path",
        "PermissionError": "check_permissions",
        "TimeoutError": "increase_timeout",
    }

    # 备选工具映射
    ALTERNATIVE_TOOLS = {
        "read_file": ["bash cat", "grep -A 999"],
        "write_file": ["bash echo"],
        "glob": ["bash find", "list_dir"],
    }

    async def handle_failure(self, tool_call: dict, error: str) -> dict:
        """处理工具失败"""
        # 1. 判断是否可重试
        if not self._is_retryable(error):
            return {"retry": False, "reason": "non-retryable error"}

        # 2. 尝试调整参数
        adjusted = await self._adjust_params(tool_call, error)
        if adjusted:
            return {"retry": True, "method": "adjusted_params", "new_call": adjusted}

        # 3. 尝试备选工具
        alternative = self._get_alternative(tool_call["name"])
        if alternative:
            return {"retry": True, "method": "alternative_tool", "tool": alternative}

        return {"retry": False, "reason": "no viable retry strategy"}
```

### 自我监控系统设计

```python
class SelfMonitor:
    """自我监控系统"""

    def __init__(self):
        self.goal = ""
        self.plan = []  # [{"step": "...", "status": "pending|done"}]
        self.checkpoints = []  # 检查点历史

    def set_goal(self, goal: str, estimated_steps: int):
        """设置目标"""
        self.goal = goal
        self.plan = [{"step": f"Step {i+1}", "status": "pending"}
                     for i in range(estimated_steps)]

    def mark_step_done(self, step_index: int):
        """标记步骤完成"""
        if step_index < len(self.plan):
            self.plan[step_index]["status"] = "done"

    def get_progress(self) -> float:
        """获取进度百分比"""
        done = sum(1 for s in self.plan if s["status"] == "done")
        return done / len(self.plan) if self.plan else 0.0

    async def check_on_track(self, llm) -> dict:
        """检查是否偏离目标"""
        prompt = f"""
Goal: {self.goal}
Plan: {json.dumps(self.plan)}
Progress: {self.get_progress():.0%}

Analyze if we are on track. Return JSON:
{{
  "on_track": true/false,
  "reason": "...",
  "suggestion": "..."
}}
"""
        result = await llm.ainvoke([HumanMessage(content=prompt)])
        check = json.loads(result.content)
        self.checkpoints.append({
            "timestamp": datetime.now().isoformat(),
            "progress": self.get_progress(),
            "on_track": check["on_track"]
        })
        return check
```

---

## 📊 总结

| 功能 | 状态 | 优先级 | 工作量 |
|------|------|--------|--------|
| 记忆召回集成 | ❌ 未集成 | P0 | 0.5天 |
| 工具使用统计 | ❌ 未实现 | P1 | 2天 |
| 经验库 | ❌ 未实现 | P1 | 1周 |
| 智能重试 | ❌ 未实现 | P2 | 2周 |
| 自我监控 | ❌ 未实现 | P2 | 3周 |

**关键发现**: Session 层已经提供了完善的记忆基础设施，但 Agent 层没有使用。最快的改进是集成已有的 `auto_recall_memory()`。
