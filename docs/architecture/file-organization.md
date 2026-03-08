# Backend App 文件归类分析

## 📊 当前结构概览

### 根目录文件（15个）
```
backend/app/
├── agent.py              # Agent 核心
├── config.py             # 配置管理
├── config_v2.py          # 配置管理 v2
├── exceptions.py         # 异常定义
├── insight.py            # 洞察分析
├── llm.py                # LLM 接口
├── llm_insight.py        # LLM 洞察
├── monitoring.py         # 性能监控
├── notifications.py      # 通知服务
├── prompts.py            # 提示词管理
├── session_context.py    # 会话上下文
├── tools_enhanced.py     # 增强工具
├── tools_manager.py      # 工具管理器
└── tracer.py             # 追踪器
```

### 子目录（19个）
```
├── background/           # 后台任务
├── compact/              # 压缩功能
├── context/              # 上下文管理
├── guards/               # 守卫系统
├── mcp/                  # MCP 协议
├── memory/               # 记忆系统
├── reasoning/            # 推理引擎
├── reliability/          # 可靠性保障 ⭐
├── search/               # 搜索功能
├── search_agent/         # 搜索代理
├── session/              # 会话管理
├── skill/                # 技能系统
├── skills/               # 技能集合
├── subagents/            # 子代理
├── task/                 # 任务管理
├── team/                 # 团队协作
├── todo/                 # TODO 管理
├── tools/                # 工具集合
└── worktree/             # Git worktree
```

---

## 🎯 功能归类

### 1. 核心模块（Core）
**功能**: Agent 核心逻辑、配置、LLM 接口

**当前位置**:
- `agent.py` - Agent 主逻辑
- `config.py` - 配置管理
- `config_v2.py` - 配置管理 v2
- `llm.py` - LLM 接口

**建议**:
- ✅ 保持在根目录
- ⚠️ `config.py` 和 `config_v2.py` 重复，需要合并

---

### 2. 工具系统（Tools）
**功能**: 工具定义、管理、增强

**当前位置**:
- `tools/` - 工具集合 ✓
- `tools_manager.py` - 工具管理器
- `tools_enhanced.py` - 增强工具

**建议重组**:
```
tools/
├── __init__.py
├── manager.py           # tools_manager.py 移入
├── enhanced.py          # tools_enhanced.py 移入
├── bash_tool.py
├── file_tool.py
└── ...
```

---

### 3. 可靠性保障（Reliability）
**功能**: 心跳、守护、监控、异常处理

**当前位置**:
- `reliability/` - 可靠性系统 ✓
- `monitoring.py` - 性能监控
- `exceptions.py` - 异常定义

**建议重组**:
```
reliability/
├── __init__.py
├── heartbeat.py         # 已存在 ✓
├── guards.py            # 已存在 ✓
├── restart.py           # 已存在 ✓
├── lifecycle.py         # 已存在 ✓
├── health.py            # 已存在 ✓
├── monitoring.py        # 从根目录移入 ⭐
└── exceptions.py        # 从根目录移入 ⭐
```

---

### 4. 上下文与会话（Context & Session）
**功能**: 上下文管理、会话管理、记忆系统

**当前位置**:
- `context/` - 上下文管理 ✓
- `session/` - 会话管理 ✓
- `session_context.py` - 会话上下文
- `memory/` - 记忆系统 ✓

**问题**:
- ⚠️ `session_context.py` 与 `session/` 功能重复
- ⚠️ `context/` 和 `session/` 职责不清

**建议重组**:
```
context/
├── __init__.py
├── context.py           # 已存在
├── overflow_guard.py    # 已存在
├── tracer.py            # 从根目录移入 ⭐
└── session/             # session/ 移入作为子模块
    ├── __init__.py
    ├── manager.py
    └── storage.py

memory/
├── __init__.py
├── compaction.py        # 已存在
├── guard.py             # 已存在
└── ...
```

---

### 5. 推理与洞察（Reasoning & Insight）
**功能**: 推理引擎、洞察分析

**当前位置**:
- `reasoning/` - 推理引擎 ✓
- `insight.py` - 洞察分析
- `llm_insight.py` - LLM 洞察

**建议重组**:
```
reasoning/
├── __init__.py
├── chain_of_thought.py  # 已存在 ✓
├── insight.py           # 从根目录移入 ⭐
└── llm_insight.py       # 从根目录移入 ⭐
```

---

### 6. 任务管理（Task Management）
**功能**: 任务、TODO、后台任务

**当前位置**:
- `task/` - 任务管理 ✓
- `todo/` - TODO 管理 ✓
- `background/` - 后台任务 ✓

**建议**:
- ✅ 保持独立，职责清晰

---

### 7. 协作系统（Collaboration）
**功能**: 团队协作、子代理

**当前位置**:
- `team/` - 团队协作 ✓
- `subagents/` - 子代理 ✓

**建议**:
- ✅ 保持独立

---

### 8. 技能系统（Skills）
**功能**: 技能加载、管理

**当前位置**:
- `skill/` - 技能系统
- `skills/` - 技能集合

**问题**:
- ⚠️ `skill/` 和 `skills/` 命名混淆

**建议重组**:
```
skills/                  # 统一使用复数
├── __init__.py
├── loader.py            # 从 skill/ 移入
└── definitions/         # 技能定义
```

---

### 9. 搜索系统（Search）
**功能**: 搜索、搜索代理

**当前位置**:
- `search/` - 搜索功能
- `search_agent/` - 搜索代理

**建议重组**:
```
search/
├── __init__.py
├── engine.py
└── agent/               # search_agent/ 移入
    ├── __init__.py
    └── ...
```

---

### 10. 其他功能模块
**当前位置**:
- `guards/` - 守卫系统 ✓
- `mcp/` - MCP 协议 ✓
- `worktree/` - Git worktree ✓
- `compact/` - 压缩功能 ✓
- `notifications.py` - 通知服务
- `prompts.py` - 提示词管理

**建议**:
- `notifications.py` → `core/notifications.py`
- `prompts.py` → `core/prompts.py`

---

## 📋 重组优先级

### 🔴 高优先级（立即处理）

1. **合并重复配置**
   - 合并 `config.py` 和 `config_v2.py`

2. **移动监控和异常到 reliability**
   - `monitoring.py` → `reliability/monitoring.py`
   - `exceptions.py` → `reliability/exceptions.py`

3. **统一技能系统**
   - 合并 `skill/` 和 `skills/`

### 🟡 中优先级（建议处理）

4. **整理推理模块**
   - `insight.py` → `reasoning/insight.py`
   - `llm_insight.py` → `reasoning/llm_insight.py`

5. **整理工具模块**
   - `tools_manager.py` → `tools/manager.py`
   - `tools_enhanced.py` → `tools/enhanced.py`

6. **整理搜索模块**
   - `search_agent/` → `search/agent/`

### 🟢 低优先级（可选）

7. **整理上下文模块**
   - `session_context.py` → `context/session/`
   - `tracer.py` → `context/tracer.py`

8. **创建 core 包**
   - `notifications.py` → `core/notifications.py`
   - `prompts.py` → `core/prompts.py`

---

## 🎯 推荐的最终结构

```
backend/app/
├── agent.py                    # Agent 核心
├── config.py                   # 统一配置
├── llm.py                      # LLM 接口
│
├── core/                       # 核心功能
│   ├── notifications.py
│   └── prompts.py
│
├── reliability/                # 可靠性保障 ⭐
│   ├── heartbeat.py
│   ├── guards.py
│   ├── monitoring.py           # 移入
│   ├── exceptions.py           # 移入
│   └── ...
│
├── tools/                      # 工具系统
│   ├── manager.py              # 移入
│   ├── enhanced.py             # 移入
│   └── ...
│
├── reasoning/                  # 推理系统
│   ├── chain_of_thought.py
│   ├── insight.py              # 移入
│   └── llm_insight.py          # 移入
│
├── context/                    # 上下文管理
│   ├── context.py
│   ├── tracer.py               # 移入
│   └── session/                # 移入
│
├── memory/                     # 记忆系统
├── skills/                     # 技能系统（统一）
├── search/                     # 搜索系统
│   └── agent/                  # 移入
├── task/                       # 任务管理
├── todo/                       # TODO 管理
├── background/                 # 后台任务
├── team/                       # 团队协作
├── subagents/                  # 子代理
├── guards/                     # 守卫系统
├── mcp/                        # MCP 协议
├── worktree/                   # Git worktree
└── compact/                    # 压缩功能
```

---

## 📊 统计

- **当前文件数**: 15个根文件 + 19个子目录
- **建议移动**: 8个文件
- **建议合并**: 2组重复
- **建议创建**: 1个新包（core）
