# Subagents 模块企业级重构方案

> 将 `backend/app/subagents/__init__.py` 重构为符合企业级标准的模块化架构

**创建日期**: 2026-03-11
**状态**: 设计阶段
**优先级**: P1

---

## 📋 目录

1. [当前问题分析](#当前问题分析)
2. [重构目标](#重构目标)
3. [新架构设计](#新架构设计)
4. [实施计划](#实施计划)
5. [测试策略](#测试策略)
6. [风险评估](#风险评估)

---

## 当前问题分析

### 🔴 严重问题

#### 1. 违反单一职责原则 (SRP)
**问题**: 628 行代码混合了 6 种职责
- Agent 类型注册表 (224 行)
- ReAct 循环实现 (100 行)
- OODA 循环实现 (140 行)
- Subagent 运行器 (70 行)
- 工具函数 (50 行)
- 历史管理和压缩 (44 行)

**影响**:
- 难以测试（需要 mock 整个文件）
- 难以维护（修改一处影响多处）
- 难以扩展（添加新 agent 类型需要修改核心文件）

#### 2. 硬编码的魔法数字
```python
max_tokens=100000          # line 265 - 为什么是 100K？
if tokens > 80000:         # line 285 - 为什么是 80K？
if len(observations) > 10: # line 387 - 为什么是 10？
max_prompt_tokens = 100000 # line 536 - 重复定义
max_cycles: int = 6        # line 348 - 为什么是 6？
recursion_limit: int = 100 # line 243 - 为什么是 100？
```

**影响**:
- 无法动态调整参数
- 不同环境无法使用不同配置
- 难以理解业务含义

#### 3. 缺少类型注解
```python
def _run_react_loop(
    agent,              # ❌ 类型未知
    prompt: str,
    subagent_type: str,
    span_id: str,
    llm,                # ❌ 类型未知
    sub_system: str,
    recursion_limit: int = 100,
) -> tuple[str, int]:
```

**影响**:
- IDE 无法提供智能提示
- 类型错误在运行时才发现
- 代码可读性差

#### 4. 全局变量污染
```python
G = "\033[90m"  # 在 3 个函数中重复定义
R = "\033[0m"   # 在 3 个函数中重复定义
```

**影响**:
- 命名空间污染
- 代码重复
- 难以统一修改

### 🟡 次要问题

#### 5. 错误处理不完善
```python
try:
    obs_json = json.loads(obs_resp.content.strip().strip("```json").strip("```"))
    raw = _invoke_tools(obs_json.get("tools", []))
    observations.extend(raw)
except (json.JSONDecodeError, AttributeError):
    observations.append(obs_resp.content.strip())  # ❌ 静默失败，无日志
```

#### 6. 日志输出混乱
- 同时使用 `print()` 和 `logger`
- 日志级别不明确
- 缺少结构化日志

#### 7. 文档不完善
- 缺少模块级 docstring
- 函数 docstring 过于简单
- 缺少使用示例

---

## 重构目标

### ✅ SOLID 原则

1. **Single Responsibility**: 每个类/模块只负责一件事
2. **Open/Closed**: 对扩展开放，对修改关闭
3. **Liskov Substitution**: 子类可以替换父类
4. **Interface Segregation**: 接口隔离
5. **Dependency Inversion**: 依赖抽象而非具体实现

### ✅ 可测试性

- 每个模块可独立测试
- 依赖可注入
- 副作用可控

### ✅ 可维护性

- 代码结构清晰
- 命名语义化
- 文档完善

### ✅ 可扩展性

- 添加新 agent 类型无需修改核心代码
- 支持插件化扩展

---

## 新架构设计

### 📁 目录结构

```
backend/app/subagents/
├── __init__.py                    # 公共接口导出
├── config.py                      # 配置常量
├── exceptions.py                  # 自定义异常
│
├── registry/                      # Agent 注册表
│   ├── __init__.py
│   ├── base.py                    # AgentConfig 基类
│   ├── registry.py                # AgentRegistry 单例
│   └── configs/                   # Agent 配置
│       ├── __init__.py
│       ├── explore.py             # Explore agent
│       ├── general_purpose.py     # General-purpose agent
│       ├── plan.py                # Plan agent
│       ├── ooda.py                # OODA agent
│       └── ...                    # 其他 agent 类型
│
├── loops/                         # 执行循环
│   ├── __init__.py
│   ├── base.py                    # BaseLoop 抽象类
│   ├── react_loop.py              # ReAct 循环
│   └── ooda_loop.py               # OODA 循环
│
├── runner/                        # Subagent 运行器
│   ├── __init__.py
│   ├── runner.py                  # SubagentRunner 主类
│   ├── span_manager.py            # Span 管理（tracer）
│   └── prompt_validator.py        # Prompt 验证和截断
│
└── utils/                         # 工具函数
    ├── __init__.py
    ├── console.py                 # 控制台输出
    ├── compression.py             # 上下文压缩
    └── history_manager.py         # 历史管理
```

### 🏗️ 核心类设计

#### 1. AgentConfig (基类)

```python
# registry/base.py
from dataclasses import dataclass, field
from typing import List, Optional
from abc import ABC, abstractmethod


@dataclass
class AgentConfig(ABC):
    """Agent 配置基类"""

    name: str
    description: str
    tools: List[str]
    prompt: str
    loop_type: str = "react"  # "react" | "ooda" | "direct"

    # 可选配置
    max_recursion: int = 100
    max_cycles: int = 6
    enable_memory: bool = True

    @abstractmethod
    def validate(self) -> None:
        """验证配置有效性"""
        pass

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "name": self.name,
            "description": self.description,
            "tools": self.tools,
            "prompt": self.prompt,
            "loop_type": self.loop_type,
        }
```

#### 2. AgentRegistry (单例)

```python
# registry/registry.py
from typing import Dict, Optional
from .base import AgentConfig


class AgentRegistry:
    """Agent 注册表（单例模式）"""

    _instance: Optional['AgentRegistry'] = None
    _agents: Dict[str, AgentConfig] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def register(self, config: AgentConfig) -> None:
        """注册 Agent 配置"""
        config.validate()
        self._agents[config.name] = config

    def get(self, name: str) -> AgentConfig:
        """获取 Agent 配置"""
        if name not in self._agents:
            raise ValueError(f"Unknown agent type: {name}")
        return self._agents[name]

    def list_agents(self) -> List[str]:
        """列出所有 Agent 类型"""
        return list(self._agents.keys())

    def get_descriptions(self) -> str:
        """获取所有 Agent 描述"""
        return "\n".join(
            f"- {name}: {cfg.description}"
            for name, cfg in self._agents.items()
        )
```

#### 3. BaseLoop (抽象基类)

```python
# loops/base.py
from abc import ABC, abstractmethod
from typing import Tuple
from ..config import SubagentConfig


class BaseLoop(ABC):
    """执行循环抽象基类"""

    def __init__(self, config: SubagentConfig):
        self.config = config

    @abstractmethod
    def run(
        self,
        llm,
        tools: list,
        system_prompt: str,
        user_prompt: str,
        span_id: str,
        subagent_type: str,
    ) -> Tuple[str, int]:
        """
        执行循环

        Returns:
            (output, tool_count)
        """
        pass

    def _validate_inputs(self, llm, tools, system_prompt, user_prompt) -> None:
        """验证输入参数"""
        if not user_prompt:
            raise ValueError("user_prompt cannot be empty")
        if not system_prompt:
            raise ValueError("system_prompt cannot be empty")
```

#### 4. SubagentRunner (主运行器)

```python
# runner/runner.py
from typing import Optional
from ..registry.registry import AgentRegistry
from ..loops.react_loop import ReActLoop
from ..loops.ooda_loop import OODALoop
from ..config import SubagentConfig
from .span_manager import SpanManager
from .prompt_validator import PromptValidator


class SubagentRunner:
    """Subagent 运行器"""

    def __init__(self, config: Optional[SubagentConfig] = None):
        self.config = config or SubagentConfig()
        self.registry = AgentRegistry()
        self.span_manager = SpanManager()
        self.prompt_validator = PromptValidator(self.config)

        # 循环类型映射
        self._loops = {
            "react": ReActLoop(self.config),
            "ooda": OODALoop(self.config),
        }

    def run(
        self,
        sub_context,
        description: str,
        prompt: str,
        recursion_limit: Optional[int] = None,
    ) -> str:
        """
        运行 Subagent

        Args:
            sub_context: SubagentContext 实例
            description: 任务描述
            prompt: 用户输入
            recursion_limit: 递归限制（可选）

        Returns:
            Subagent 输出
        """
        # 1. 获取配置
        agent_config = self.registry.get(sub_context.subagent_type)

        # 2. 验证和截断 prompt
        prompt = self.prompt_validator.validate_and_truncate(
            prompt,
            sub_context.llm
        )

        # 3. 开始 span
        span_id = self.span_manager.start(
            subagent_type=sub_context.subagent_type,
            description=description,
            tools=sub_context.tools,
        )

        try:
            # 4. 选择执行循环
            loop = self._select_loop(agent_config.loop_type, sub_context)

            # 5. 执行
            output, tool_count = loop.run(
                llm=sub_context.llm,
                tools=sub_context.tools,
                system_prompt=sub_context.system_prompt,
                user_prompt=prompt,
                span_id=span_id,
                subagent_type=sub_context.subagent_type,
            )

            # 6. 保存 session
            sub_context.session_store.save_turn(
                sub_context.subagent_type,
                prompt,
                output,
                []
            )

            return output or "(subagent returned no text)"

        finally:
            # 7. 结束 span
            self.span_manager.end(
                span_id=span_id,
                subagent_type=sub_context.subagent_type,
                tool_count=tool_count,
                output=output,
            )

    def _select_loop(self, loop_type: str, sub_context):
        """选择执行循环"""
        if loop_type == "direct":
            # 无工具，直接 LLM 调用
            return DirectLoop(self.config)

        if loop_type not in self._loops:
            raise ValueError(f"Unknown loop type: {loop_type}")

        return self._loops[loop_type]
```

#### 5. SubagentConfig (配置类)

```python
# config.py
from dataclasses import dataclass


@dataclass
class SubagentConfig:
    """Subagent 全局配置"""

    # 上下文管理
    MAX_CONTEXT_TOKENS: int = 100_000
    COMPRESSION_THRESHOLD: int = 80_000
    MAX_PROMPT_TOKENS: int = 100_000

    # OODA 循环
    MAX_OODA_CYCLES: int = 6
    OBSERVATION_COMPRESSION_LIMIT: int = 10
    OODA_COMPRESSION_INTERVAL: int = 3  # 每 3 个 cycle 压缩一次

    # ReAct 循环
    DEFAULT_RECURSION_LIMIT: int = 100

    # 日志
    ENABLE_CONSOLE_OUTPUT: bool = True
    LOG_LEVEL: str = "INFO"

    # Tracer
    ENABLE_TRACER: bool = True

    @classmethod
    def from_env(cls) -> 'SubagentConfig':
        """从环境变量加载配置"""
        import os
        return cls(
            MAX_CONTEXT_TOKENS=int(os.getenv("SUBAGENT_MAX_TOKENS", 100_000)),
            COMPRESSION_THRESHOLD=int(os.getenv("SUBAGENT_COMPRESSION_THRESHOLD", 80_000)),
            # ... 其他配置
        )
```

---

## 实施计划

### Phase 1: 基础架构 (2 天)

#### 任务列表

- [ ] **Task 1.1**: 创建目录结构
  - 创建 `registry/`, `loops/`, `runner/`, `utils/` 目录
  - 创建所有 `__init__.py` 文件

- [ ] **Task 1.2**: 实现配置系统
  - `config.py` - SubagentConfig
  - `exceptions.py` - 自定义异常

- [ ] **Task 1.3**: 实现注册表
  - `registry/base.py` - AgentConfig 基类
  - `registry/registry.py` - AgentRegistry 单例

- [ ] **Task 1.4**: 编写单元测试
  - `tests/unit/subagents/test_config.py`
  - `tests/unit/subagents/test_registry.py`

### Phase 2: 循环实现 (3 天)

#### 任务列表

- [ ] **Task 2.1**: 实现 BaseLoop
  - `loops/base.py` - 抽象基类
  - 定义接口和验证逻辑

- [ ] **Task 2.2**: 重构 ReActLoop
  - 从 `__init__.py` 提取 `_run_react_loop`
  - 封装为 `ReActLoop` 类
  - 添加类型注解
  - 改进错误处理

- [ ] **Task 2.3**: 重构 OODALoop
  - 从 `__init__.py` 提取 `_run_ooda_loop`
  - 封装为 `OODALoop` 类
  - 添加类型注解
  - 改进错误处理

- [ ] **Task 2.4**: 实现 DirectLoop
  - 处理无工具的直接 LLM 调用

- [ ] **Task 2.5**: 编写单元测试
  - `tests/unit/subagents/loops/test_react_loop.py`
  - `tests/unit/subagents/loops/test_ooda_loop.py`

### Phase 3: 运行器实现 (2 天)

#### 任务列表

- [ ] **Task 3.1**: 实现 SpanManager
  - 封装 tracer 相关逻辑
  - `runner/span_manager.py`

- [ ] **Task 3.2**: 实现 PromptValidator
  - 封装 prompt 验证和截断逻辑
  - `runner/prompt_validator.py`

- [ ] **Task 3.3**: 实现 SubagentRunner
  - 主运行器逻辑
  - `runner/runner.py`

- [ ] **Task 3.4**: 编写单元测试
  - `tests/unit/subagents/runner/test_runner.py`

### Phase 4: Agent 配置迁移 (2 天)

#### 任务列表

- [ ] **Task 4.1**: 迁移 Explore Agent
  - `registry/configs/explore.py`

- [ ] **Task 4.2**: 迁移 General-Purpose Agent
  - `registry/configs/general_purpose.py`

- [ ] **Task 4.3**: 迁移 Plan Agent
  - `registry/configs/plan.py`

- [ ] **Task 4.4**: 迁移 OODA Agent
  - `registry/configs/ooda.py`

- [ ] **Task 4.5**: 迁移其他 Agent (10 个)
  - Coding, Reflect, Reflexion, SearchSubagent, IntentRecognition,
    Clarification, CDPBrowser, ToolRepair

- [ ] **Task 4.6**: 更新注册逻辑
  - 在 `registry/__init__.py` 中自动注册所有配置

### Phase 5: 工具函数重构 (1 天)

#### 任务列表

- [ ] **Task 5.1**: 实现 ConsoleOutput
  - `utils/console.py`
  - 统一控制台输出

- [ ] **Task 5.2**: 实现 ContextCompressor
  - `utils/compression.py`
  - 上下文压缩逻辑

- [ ] **Task 5.3**: 实现 HistoryManager
  - `utils/history_manager.py`
  - 历史管理逻辑

### Phase 6: 集成测试 (2 天)

#### 任务列表

- [ ] **Task 6.1**: 编写集成测试
  - `tests/integration/subagents/test_subagent_runner.py`
  - 测试完整流程

- [ ] **Task 6.2**: 性能测试
  - 对比重构前后性能
  - 确保无性能退化

- [ ] **Task 6.3**: 兼容性测试
  - 确保与现有代码兼容
  - 测试所有 agent 类型

### Phase 7: 文档和清理 (1 天)

#### 任务列表

- [ ] **Task 7.1**: 编写模块文档
  - 每个模块添加详细 docstring
  - 添加使用示例

- [ ] **Task 7.2**: 更新 ARCHITECTURE.md
  - 记录新架构
  - 添加架构图

- [ ] **Task 7.3**: 删除旧代码
  - 备份 `__init__.py`
  - 删除已迁移的代码

- [ ] **Task 7.4**: 更新导入路径
  - 更新所有引用 `subagents` 的代码

---

## 测试策略

### 单元测试

#### 测试覆盖率目标: 90%+

```python
# tests/unit/subagents/test_config.py
def test_subagent_config_defaults():
    config = SubagentConfig()
    assert config.MAX_CONTEXT_TOKENS == 100_000
    assert config.COMPRESSION_THRESHOLD == 80_000

def test_subagent_config_from_env(monkeypatch):
    monkeypatch.setenv("SUBAGENT_MAX_TOKENS", "200000")
    config = SubagentConfig.from_env()
    assert config.MAX_CONTEXT_TOKENS == 200_000
```

```python
# tests/unit/subagents/test_registry.py
def test_agent_registry_singleton():
    registry1 = AgentRegistry()
    registry2 = AgentRegistry()
    assert registry1 is registry2

def test_register_and_get_agent():
    registry = AgentRegistry()
    config = ExploreAgentConfig()
    registry.register(config)

    retrieved = registry.get("Explore")
    assert retrieved.name == "Explore"
```

### 集成测试

```python
# tests/integration/subagents/test_subagent_runner.py
def test_run_explore_agent(mock_llm, mock_context):
    runner = SubagentRunner()
    output = runner.run(
        sub_context=mock_context,
        description="Test exploration",
        prompt="Find all Python files",
    )
    assert output is not None
    assert "Python files" in output
```

### 性能测试

```python
# tests/performance/test_subagent_performance.py
import time

def test_react_loop_performance():
    start = time.time()
    # 运行 ReAct 循环
    elapsed = time.time() - start
    assert elapsed < 5.0  # 应在 5 秒内完成
```

---

## 风险评估

### 🔴 高风险

#### 1. 破坏现有功能
**风险**: 重构可能导致现有 agent 无法正常工作

**缓解措施**:
- 保留旧代码作为备份
- 完整的集成测试
- 分阶段迁移，每个 agent 类型单独测试
- 使用 feature flag 控制新旧代码切换

#### 2. 性能退化
**风险**: 新架构可能引入额外开销

**缓解措施**:
- 性能基准测试
- 对比重构前后性能
- 优化热路径代码

### 🟡 中风险

#### 3. 依赖关系复杂
**风险**: 其他模块依赖 `subagents/__init__.py` 的内部实现

**缓解措施**:
- 搜索所有引用
- 提供兼容层
- 逐步迁移依赖方

#### 4. 测试覆盖不足
**风险**: 测试无法覆盖所有边界情况

**缓解措施**:
- 提高测试覆盖率目标 (90%+)
- 添加边界测试
- 使用 property-based testing

### 🟢 低风险

#### 5. 文档不同步
**风险**: 文档更新不及时

**缓解措施**:
- 代码和文档同步更新
- Code review 检查文档

---

## 成功标准

### ✅ 功能完整性
- [ ] 所有现有 agent 类型正常工作
- [ ] 所有测试通过
- [ ] 无功能退化

### ✅ 代码质量
- [ ] 测试覆盖率 > 90%
- [ ] 无 pylint/mypy 错误
- [ ] 所有函数有类型注解
- [ ] 所有模块有完整文档

### ✅ 性能
- [ ] 性能无明显退化 (< 5%)
- [ ] 内存使用无明显增加

### ✅ 可维护性
- [ ] 代码结构清晰
- [ ] 易于添加新 agent 类型
- [ ] 易于修改配置

---

## 附录

### A. 代码示例

#### 添加新 Agent 类型

```python
# registry/configs/my_agent.py
from ..base import AgentConfig

class MyAgentConfig(AgentConfig):
    def __init__(self):
        super().__init__(
            name="MyAgent",
            description="My custom agent",
            tools=["bash", "read_file"],
            prompt="You are my custom agent...",
            loop_type="react",
        )

    def validate(self) -> None:
        if not self.tools:
            raise ValueError("MyAgent requires at least one tool")
```

```python
# registry/configs/__init__.py
from .my_agent import MyAgentConfig

# 自动注册
from ..registry import AgentRegistry
registry = AgentRegistry()
registry.register(MyAgentConfig())
```

#### 使用新架构

```python
# 旧代码
from backend.app.subagents import run_subagent_with_context

output = run_subagent_with_context(
    sub_context=context,
    description="Test",
    prompt="Hello",
)

# 新代码
from backend.app.subagents import SubagentRunner

runner = SubagentRunner()
output = runner.run(
    sub_context=context,
    description="Test",
    prompt="Hello",
)
```

### B. 架构图

```
┌─────────────────────────────────────────────────────────┐
│                    SubagentRunner                        │
│  - 主入口                                                │
│  - 协调各组件                                            │
└────────────┬────────────────────────────────────────────┘
             │
             ├──────────────┬──────────────┬──────────────┐
             │              │              │              │
             ▼              ▼              ▼              ▼
    ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐
    │  Registry  │  │   Loops    │  │   Utils    │  │   Config   │
    │            │  │            │  │            │  │            │
    │ - configs  │  │ - ReAct    │  │ - console  │  │ - 常量     │
    │ - get()    │  │ - OODA     │  │ - compress │  │ - 环境变量 │
    └────────────┘  └────────────┘  └────────────┘  └────────────┘
```

---

**文档版本**: v1.0
**最后更新**: 2026-03-11
**维护者**: Backend Team
