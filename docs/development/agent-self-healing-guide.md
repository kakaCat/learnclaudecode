# Agent 自我修复机制设计指南

## 概述

让 Agent 像人类开发者一样分析失败、诊断问题、制定方案并实施修复，需要以下核心能力：

1. **失败感知**：能够识别任务失败
2. **根因分析**：能够分析失败原因
3. **方案制定**：能够设计改进方案
4. **自主实施**：能够执行修复代码
5. **验证反馈**：能够测试修复效果

---

## 核心机制

### 1. 失败感知机制

#### 1.1 Trace 日志记录

**当前实现**：
```python
# backend/app/session/session.py
def log_event(self, event_type: str, data: dict):
    """记录事件到 trace.jsonl"""
    event = {
        "ts": time.time(),
        "event": event_type,
        "run_id": self.current_run_id,
        **data
    }
    with open(self.trace_file, "a") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
```

**关键事件**：
- `run.start` - 任务开始
- `llm.turn` - 每轮决策
- `tool.call` - 工具调用
- `tool.result` - 工具结果（包含 ok/error）
- `llm.response` - LLM 响应

#### 1.2 失败检测规则

在 MEMORY.md 中定义失败模式：

```markdown
## 失败检测规则

### 工具调用失败
- `tool.result` 中 `ok: false`
- 返回内容包含 "Error:", "❌", "SyntaxError"

### 任务超时
- 同一任务超过 30 轮次
- 重复相同的工具调用 >5 次

### 输出质量差
- 最终输出包含 "任务失败"、"无法完成"
- 没有返回预期的数据格式
```

### 2. 根因分析能力

#### 2.1 Reflection Subagent

创建专门的反思子 Agent：

```python
# backend/app/subagents/reflection_agent.py
class ReflectionAgent:
    """
    反思 Agent - 分析失败原因

    输入：
    - trace.jsonl 文件路径
    - 任务描述

    输出：
    - 失败原因分析
    - 改进建议
    """

    def analyze_failure(self, trace_file: str, task: str) -> dict:
        """
        分析任务失败原因

        返回：
        {
            "failure_type": "javascript_error" | "strategy_failure" | "timeout",
            "root_cause": "具体原因描述",
            "failed_attempts": [
                {"turn": 5, "tool": "cdp_browser", "error": "SyntaxError..."}
            ],
            "suggestions": [
                "使用 IIFE 包装 JavaScript",
                "切换到 URL 构造策略"
            ]
        }
        """
```

#### 2.2 分析提示词模板

```markdown
# 任务失败分析

你是一个专业的 Agent 调试专家。请分析以下失败的任务执行记录。

## 任务描述
{task_description}

## Trace 日志
{trace_content}

## 分析要求

1. **识别失败模式**：
   - 工具调用失败（语法错误、超时、权限问题）
   - 策略选择错误（方法不适用、效率低下）
   - 逻辑错误（日期计算、数据解析）

2. **定位根本原因**：
   - 不要只看表面错误
   - 找出导致失败的核心问题
   - 区分症状和病因

3. **提出改进方案**：
   - 代码层面的修复
   - 策略层面的优化
   - 记忆层面的补充

## 输出格式

```json
{
  "failure_type": "...",
  "root_cause": "...",
  "failed_attempts": [...],
  "suggestions": [...]
}
```
```

### 3. 方案制定能力

#### 3.1 Plan Subagent

使用 Plan 模式生成改进方案：

```python
# backend/app/subagents/improvement_planner.py
class ImprovementPlanner:
    """
    改进方案规划 Agent

    基于失败分析，制定具体的改进方案
    """

    def create_plan(self, analysis: dict) -> dict:
        """
        创建改进计划

        返回：
        {
            "changes": [
                {
                    "type": "code_fix",
                    "file": "backend/app/tools/cdp_tool.py",
                    "description": "添加 IIFE 包装",
                    "priority": "high"
                },
                {
                    "type": "memory_update",
                    "file": ".memory/MEMORY.md",
                    "description": "添加 URL 构造策略",
                    "priority": "medium"
                }
            ],
            "test_plan": "创建测试脚本验证修复效果"
        }
        """
```

#### 3.2 规划提示词模板

```markdown
# 改进方案规划

基于以下失败分析，制定具体的改进方案。

## 失败分析
{analysis_json}

## 规划要求

1. **代码修复**：
   - 需要修改哪些文件
   - 具体的修改内容
   - 修改的优先级

2. **策略优化**：
   - 需要添加哪些规则到 MEMORY.md
   - 需要调整哪些工具参数

3. **测试验证**：
   - 如何验证修复效果
   - 需要创建哪些测试用例

## 输出格式

按照 TodoWrite 格式输出任务列表，每个任务包含：
- 阶段（代码修复/记忆优化/测试验证）
- 具体内容
- 优先级
```

### 4. 自主实施能力

#### 4.1 自动化修复流程

```python
# backend/app/self_healing.py
class SelfHealingAgent:
    """
    自我修复 Agent - 完整流程
    """

    def heal(self, failed_session_key: str):
        """
        自我修复流程

        1. 读取失败的 trace.jsonl
        2. 调用 ReflectionAgent 分析
        3. 调用 ImprovementPlanner 规划
        4. 执行修复任务
        5. 运行测试验证
        """

        # 1. 分析失败
        trace_file = f".sessions/{failed_session_key}/trace.jsonl"
        analysis = self.reflection_agent.analyze_failure(trace_file)

        # 2. 制定方案
        plan = self.planner.create_plan(analysis)

        # 3. 执行修复
        for change in plan["changes"]:
            if change["type"] == "code_fix":
                self.apply_code_fix(change)
            elif change["type"] == "memory_update":
                self.update_memory(change)

        # 4. 验证修复
        test_result = self.run_tests(plan["test_plan"])

        return {
            "analysis": analysis,
            "plan": plan,
            "test_result": test_result
        }
```

#### 4.2 技能化（Skill）

将自我修复封装为技能：

```markdown
# .skills/self-heal/skill.md

# Self-Healing Skill

## Trigger
当用户说：
- "分析上次失败的原因"
- "修复上次的问题"
- "为什么任务失败了"
- "@.sessions/{key}/trace.jsonl 分析失败原因"

## Workflow

1. **读取 Trace**：
   ```python
   trace_file = ".sessions/{session_key}/trace.jsonl"
   ```

2. **分析失败**：
   - 使用 Reflection subagent
   - 识别失败模式
   - 定位根本原因

3. **制定方案**：
   - 使用 Plan subagent
   - 生成改进任务列表
   - 使用 TodoWrite 跟踪进度

4. **实施修复**：
   - 修改代码文件
   - 更新 MEMORY.md
   - 创建测试脚本

5. **验证效果**：
   - 运行测试
   - 确认修复成功

## Example

用户：@.sessions/20260310_015346/trace.jsonl agent没有完成任务，分析一下原因

Agent：
1. 读取 trace 文件
2. 分析发现：JavaScript 语法错误、策略选择不当、日期处理错误
3. 制定方案：修改 cdp_tool.py、更新 MEMORY.md、创建测试
4. 执行修复
5. 验证通过
```

### 5. 验证反馈机制

#### 5.1 自动化测试

```python
# scripts/test_self_healing.py
def test_self_healing():
    """
    测试自我修复效果

    1. 重现失败场景
    2. 应用修复
    3. 验证是否成功
    """

    # 重现失败
    result_before = agent.run("查询北京到上海的机票 明天的")
    assert "任务失败" in result_before

    # 应用修复
    healing_agent.heal(session_key)

    # 验证修复
    result_after = agent.run("查询北京到上海的机票 明天的")
    assert "航班号" in result_after
    assert "价格" in result_after
```

#### 5.2 持续学习

将成功的修复经验写入 MEMORY.md：

```python
def save_healing_experience(analysis, plan, result):
    """
    保存修复经验到记忆
    """
    experience = f"""
## 修复案例 {datetime.now().strftime('%Y-%m-%d')}

### 问题
{analysis['root_cause']}

### 解决方案
{plan['changes']}

### 效果
{result['test_result']}
"""

    append_to_memory(experience)
```

---

## 实施步骤

### 阶段 1: 基础设施（1-2 天）

1. ✅ 完善 Trace 日志记录
2. ✅ 创建 ReflectionAgent 子 Agent
3. ✅ 创建 ImprovementPlanner 子 Agent

### 阶段 2: 自动化流程（2-3 天）

1. ✅ 实现 SelfHealingAgent 主流程
2. ✅ 封装为 Skill
3. ✅ 添加自动化测试

### 阶段 3: 持续优化（持续）

1. ✅ 收集失败案例
2. ✅ 优化分析算法
3. ✅ 扩展修复模式库

---

## 关键设计原则

### 1. 分离关注点

- **Reflection**：只负责分析，不做修复
- **Planning**：只负责规划，不执行
- **Execution**：只负责执行，不决策

### 2. 可观测性

- 所有操作记录到 Trace
- 修复过程可回溯
- 效果可量化

### 3. 渐进式改进

- 从简单的模式匹配开始
- 逐步增加复杂度
- 持续积累经验

### 4. 人机协作

- 重大修改需要用户确认
- 提供详细的修复说明
- 支持手动干预

---

## 示例：完整的自我修复流程

```python
# 用户触发
user_input = "@.sessions/20260310_015346/trace.jsonl agent没有完成任务，分析一下原因"

# 1. Reflection Agent 分析
analysis = reflection_agent.analyze(
    trace_file=".sessions/20260310_015346/trace.jsonl",
    task="查询北京到上海的机票 明天的"
)
# 输出：
# {
#   "failure_type": "javascript_error",
#   "root_cause": "CDP execute 在全局作用域使用 return 导致语法错误",
#   "suggestions": ["使用 IIFE 包装", "添加 eval 动作"]
# }

# 2. Planning Agent 规划
plan = planner.create_plan(analysis)
# 输出：
# {
#   "changes": [
#     {"type": "code_fix", "file": "cdp_tool.py", "desc": "添加 IIFE 包装"},
#     {"type": "memory_update", "file": "MEMORY.md", "desc": "添加策略规则"}
#   ]
# }

# 3. 执行修复
for change in plan["changes"]:
    execute_change(change)

# 4. 验证
test_result = run_test("查询北京到上海的机票 明天的")
# 输出：✅ 修复成功，任务完成

# 5. 保存经验
save_to_memory(analysis, plan, test_result)
```

---

## 与当前实现的对比

### 当前（手动修复）

```
用户报告问题
  → 人工分析 trace
  → 人工编写修复代码
  → 人工测试验证
```

### 目标（自动修复）

```
用户报告问题
  → Reflection Agent 分析
  → Planning Agent 规划
  → Execution Agent 修复
  → 自动测试验证
  → 保存经验到 MEMORY
```

---

## 参考资料

- **Reflexion 论文**：Reflexion: Language Agents with Verbal Reinforcement Learning
- **Self-Refine**：Iterative Refinement with Self-Feedback
- **Tree of Thoughts**：Deliberate Problem Solving with Large Language Models

---

## 下一步行动

1. 创建 `backend/app/subagents/reflection_agent.py`
2. 创建 `backend/app/subagents/improvement_planner.py`
3. 创建 `backend/app/self_healing.py`
4. 创建 `.skills/self-heal/skill.md`
5. 创建 `scripts/test_self_healing.py`
