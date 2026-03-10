# 智能化功能使用指南

> 已实现的三个核心功能：主动记忆召回、智能重试、自我监控

## 1. 主动记忆召回 ✅

### 功能说明
每次对话开始时，自动从历史记忆中召回相关内容，让 agent 能利用过去的经验。

### 实现位置
- `backend/app/agent.py:107-113`
- 自动调用 `auto_recall_memory(session_key, prompt)`

### 使用方式
无需手动调用，agent 会自动：
1. 分析用户输入
2. 搜索相关历史记忆
3. 注入到对话上下文

### 示例
```python
# 用户第一次问：我喜欢用 Python
# Agent 保存到记忆：store.write_memory("用户喜欢 Python", category="preference")

# 用户第二次问：帮我写个脚本
# Agent 自动召回："用户喜欢 Python"
# Agent 回答：我用 Python 给你写...
```

---

## 2. 智能重试策略 ✅

### 功能说明
工具调用失败时，自动判断是否可重试、调整参数或切换备选工具。

### 实现位置
- `backend/app/reliability/retry.py`

### 使用方式

```python
from backend.app.reliability import get_retry_strategy

retry = get_retry_strategy()

# 工具调用失败后
result = await retry.handle_failure(
    tool_name="read_file",
    args={"file_path": "test.py"},
    error="FileNotFoundError: test.py not found"
)

if result["retry"]:
    print(f"重试方法: {result['method']}")
    print(f"建议: {result['suggestion']}")
    # 根据建议重试
```

### 支持的重试策略

1. **参数调整**
   - `FileNotFoundError` → 添加 `./` 前缀
   - 适用于相对路径问题

2. **备选工具**
   - `read_file` 失败 → 尝试 `bash cat`
   - `glob` 失败 → 尝试 `bash find`

3. **重试限制**
   - 默认最多重试 2 次
   - 避免无限循环

---

## 3. 自我监控系统 ✅

### 功能说明
设定目标、追踪进度、检测是否偏离目标。

### 实现位置
- `backend/app/reliability/monitor.py`

### 使用方式

```python
from backend.app.reliability import get_monitor

monitor = get_monitor()

# 1. 设定目标
monitor.set_goal("实现用户登录功能", estimated_steps=5)

# 或设定详细计划
monitor.set_plan([
    "创建用户模型",
    "实现登录 API",
    "添加 JWT 认证",
    "编写测试",
    "更新文档"
])

# 2. 标记步骤完成
monitor.mark_step_done(0)  # 完成第一步
monitor.mark_step_done()    # 完成当前步骤

# 3. 查看进度
status = monitor.get_status()
print(f"进度: {status['progress']}")  # "40%"
print(f"当前步骤: {status['current_step']}/{status['total_steps']}")

# 4. 检查是否偏离（需要 LLM）
check = await monitor.check_on_track(llm)
if not check["on_track"]:
    print(f"⚠️ 偏离目标: {check['reason']}")
    print(f"💡 建议: {check['suggestion']}")

# 5. 判断是否应该检查
if monitor.should_check(tool_count=6, check_interval=3):
    # 每 3 个工具调用检查一次
    await monitor.check_on_track(llm)
```

---

## 集成到 Agent

### 在 agent.py 中使用

```python
from backend.app.reliability import get_retry_strategy, get_monitor

class AgentService:
    def __init__(self):
        # ... 现有代码 ...
        self.retry_strategy = get_retry_strategy()
        self.monitor = get_monitor()

    async def run(self, prompt: str, history: list = None) -> str:
        # 1. 设定目标
        self.monitor.set_goal(prompt, estimated_steps=5)

        # 2. 执行工具调用
        try:
            result = await self._execute_tool(tool_call)
        except Exception as e:
            # 3. 智能重试
            retry_result = await self.retry_strategy.handle_failure(
                tool_call["name"], tool_call["args"], str(e)
            )
            if retry_result["retry"]:
                # 根据建议重试
                pass

        # 4. 标记进度
        self.monitor.mark_step_done()

        # 5. 定期检查
        if self.monitor.should_check(total_tools):
            check = await self.monitor.check_on_track(llm)
            if not check["on_track"]:
                _log("⚠️", f"偏离: {check['reason']}")
```

---

## 配置选项

### RetryStrategy

```python
# 自定义最大重试次数
retry = RetryStrategy(max_retries=3)

# 添加自定义错误类型
RetryStrategy.RETRYABLE_ERRORS["CustomError"] = "custom_handler"

# 添加备选工具
RetryStrategy.ALTERNATIVE_TOOLS["my_tool"] = ["backup_tool1", "backup_tool2"]
```

### SelfMonitor

```python
# 自定义检查间隔
monitor.should_check(tool_count, check_interval=5)  # 每 5 个工具调用检查一次
```

---

## 最佳实践

1. **记忆召回**
   - 重要信息用 `category="preference"` 保存
   - 事实用 `category="fact"`
   - 上下文用 `category="context"`

2. **智能重试**
   - 只重试可恢复的错误
   - 记录重试日志便于调试
   - 避免无限重试

3. **自我监控**
   - 复杂任务设定详细计划
   - 定期检查避免偏离
   - 根据建议及时调整

---

## 测试

```bash
# 测试记忆召回
python -c "from backend.app.prompts import auto_recall_memory; print(auto_recall_memory('test', 'Python'))"

# 测试重试策略
python -c "from backend.app.reliability import get_retry_strategy; r=get_retry_strategy(); print(r.is_retryable('FileNotFoundError'))"

# 测试监控
python -c "from backend.app.reliability import get_monitor; m=get_monitor(); m.set_goal('test', 3); m.mark_step_done(); print(m.get_progress())"
```

---

## 下一步

- [ ] 在 agent.py 中集成 RetryStrategy
- [ ] 在 agent.py 中集成 SelfMonitor
- [ ] 添加更多备选工具映射
- [ ] 实现用户偏好自动学习
- [ ] 添加经验库（成功/失败案例）
