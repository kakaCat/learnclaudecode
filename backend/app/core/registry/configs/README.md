# Agent 配置 - 按设计模式组织

## 目录结构

```
configs/
├── README.md              # 本文件
├── __init__.py            # 统一注册入口
├── direct_agents.py       # Direct 模式配置
├── react_agents.py        # ReAct 模式配置
├── ooda_agents.py         # OODA 模式配置
├── special_agents.py      # 特殊用途 Agent
└── basic_agents.py        # 已废弃（向后兼容）
```

## 三种 Agent 设计模式

### 1. Direct 模式 - 单次调用

**文件**: `direct_agents.py`

**特点**:
- 不使用循环
- 不使用工具
- 单次 LLM 调用
- 直接返回结果

**适用场景**:
- 纯思考任务
- 规划和分析
- 总结和提炼

**包含的 Agent**:
- `PlanAgent` - 任务规划，拆分步骤

**示例**:
```python
# 用户: "规划一个用户认证功能的实现"
# Agent: 直接返回结构化的实现计划（3-7步）
# 不会调用任何工具，不会循环
```

---

### 2. ReAct 模式 - 推理+行动循环

**文件**: `react_agents.py`

**特点**:
- 使用 ReAct 循环
- 支持工具调用
- 思考 → 行动 → 观察 → 思考...
- 适合需要多步工具调用的任务

**适用场景**:
- 代码探索
- 功能实现
- 文件操作
- 需要工具辅助的任务

**包含的 Agent**:
- `ExploreAgent` - 只读探索代码库
- `GeneralPurposeAgent` - 通用开发任务
- `CodingAgent` - 代码生成

**示例**:
```python
# 用户: "找到所有 API 端点"
# Agent:
#   Thought: 我需要搜索 @router 装饰器
#   Action: grep("@router", path="backend/")
#   Observation: 找到 10 个文件
#   Thought: 现在读取这些文件
#   Action: read_file("api/v1/user.py")
#   ...
```

---

### 3. OODA 模式 - 观察-定向-决策-行动循环

**文件**: `ooda_agents.py`

**特点**:
- 使用 OODA 循环
- 支持工具调用
- 迭代式探索和决策
- 每个 cycle 包含 4 个阶段

**适用场景**:
- 信息搜索和研究
- 代码审查和反思
- 质量改进
- 需要多轮迭代的任务

**包含的 Agent**:
- `ReflectAgent` - 代码审查，返回 PASS/NEEDS_REVISION
- `ReflexionAgent` - 反思改进，两阶段 Responder+Revisor

**示例**:
```python
# 用户: "审查这段代码的质量"
# Agent:
#   Cycle 1:
#     Observe: 读取代码文件
#     Orient: 分析代码结构
#     Decide: 识别问题
#     Act: 记录问题
#   Cycle 2:
#     Observe: 检查测试覆盖
#     Orient: 评估测试质量
#     Decide: 判断是否通过
#     Act: 返回 JSON 结果
```

---

## 设计模式对比

| 特性 | Direct | ReAct | OODA |
|------|--------|-------|------|
| **循环** | 无 | 有 | 有 |
| **工具** | 无 | 有 | 有 |
| **LLM 调用** | 1 次 | 多次 | 多次 |
| **Token 消耗** | 最低 | 中等 | 较高 |
| **适合任务** | 规划、总结 | 实现、探索 | 搜索、审查 |
| **执行速度** | 最快 | 中等 | 较慢 |
| **复杂度** | 简单 | 中等 | 复杂 |

---

## 配置参数说明

### Direct 模式参数

```python
loop_type="direct"
max_cycles=1           # 固定为 1
enable_memory=False    # 通常不需要 memory
tools=[]               # 不使用工具
```

### ReAct 模式参数

```python
loop_type="react"
max_recursion=50-100   # 根据任务复杂度调整
enable_memory=True     # 通常启用
tools=[...]            # 需要的工具列表
```

### OODA 模式参数

```python
loop_type="ooda"
max_cycles=10-20       # 根据任务复杂度调整
enable_memory=True     # 通常启用
tools=[...]            # 需要的工具列表
```

---

## 如何选择设计模式

### 使用 Direct 模式，如果：
- ✅ 任务是纯思考（规划、分析、总结）
- ✅ 不需要调用工具
- ✅ 需要快速响应
- ✅ 输出格式固定

### 使用 ReAct 模式，如果：
- ✅ 需要调用工具（读文件、搜索、写代码）
- ✅ 任务有明确的执行路径
- ✅ 不需要多轮迭代探索

### 使用 OODA 模式，如果：
- ✅ 需要迭代式探索（搜索信息、研究问题）
- ✅ 需要多轮决策和调整
- ✅ 任务路径不确定，需要动态调整
- ✅ 需要反思和改进

---

## 添加新 Agent

### 1. 确定设计模式

根据任务特点选择 Direct/ReAct/OODA

### 2. 在对应文件中添加配置

```python
@dataclass
class MyAgentConfig(AgentConfig):
    """My Agent 配置"""

    def __init__(self):
        super().__init__(
            name="MyAgent",
            description="...",
            tools=[...],
            prompt="...",
            loop_type="direct|react|ooda",
            max_cycles=1,  # 或 max_recursion
            enable_memory=True,
        )
```

### 3. 在 __init__.py 中注册

```python
from .xxx_agents import MyAgentConfig

configs = [
    ...
    MyAgentConfig(),
]
```

---

## 最佳实践

1. **优先使用 Direct 模式** - 如果任务不需要工具，用 Direct 最快
2. **ReAct 是默认选择** - 大多数开发任务用 ReAct
3. **谨慎使用 OODA** - 只在真正需要迭代探索时使用，避免过度消耗 tokens
4. **控制循环次数** - Direct=1, ReAct=50-100, OODA=10-20
5. **合理使用 memory** - Direct 通常不需要，ReAct/OODA 建议启用

---

## 迁移指南

如果你之前使用 `basic_agents.py`，现在应该：

```python
# 旧方式（仍然可用）
from backend.app.core.registry.configs.basic_agents import PlanAgentConfig

# 新方式（推荐）
from backend.app.core.registry.configs.direct_agents import PlanAgentConfig
```

`basic_agents.py` 已改为重新导出，保持向后兼容。
