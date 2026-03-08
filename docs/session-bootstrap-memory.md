# Session Bootstrap 和记忆系统集成

## 概述

参考 `s06_intelligence.py` 的设计，为后端项目的 session 机制添加了：
1. **Bootstrap 文件加载器** - 从 workspace 加载配置文件（SOUL.md, IDENTITY.md 等）
2. **记忆存储系统** - 两层存储（MEMORY.md + daily/*.jsonl）+ 混合搜索

## 新增文件

### 1. `backend/app/session/bootstrap.py`
Bootstrap 文件加载器，支持：
- 加载 8 个标准文件（SOUL.md, IDENTITY.md, TOOLS.md, USER.md, HEARTBEAT.md, BOOTSTRAP.md, AGENTS.md, MEMORY.md）
- 文件截断（单个文件最大 20000 字符）
- 总字符数限制（150000 字符）
- 三种加载模式：full/minimal/none

### 2. `backend/app/session/memory_store.py`
记忆存储管理器，支持：
- 写入记忆到每日日志（`workspace/memory/daily/{date}.jsonl`）
- 加载长期记忆（`workspace/MEMORY.md`）
- TF-IDF + 余弦相似度搜索
- 混合搜索（关键词 + 向量 + 时间衰减 + MMR 重排序）

### 3. `backend/app/tools/memory_tools.py`
记忆工具：
- `memory_write(content, category)` - 写入记忆
- `memory_search(query, top_k)` - 搜索记忆

## 修改文件

### 1. `backend/app/session/session.py`
SessionStore 类新增方法：
- `get_bootstrap_loader()` - 获取 Bootstrap 加载器
- `load_bootstrap(mode)` - 加载 Bootstrap 文件
- `load_soul()` - 加载 SOUL.md
- `get_memory_store()` - 获取记忆存储
- `write_memory(content, category)` - 写入记忆
- `search_memory(query, top_k)` - 简单搜索
- `hybrid_search_memory(query, top_k)` - 混合搜索
- `get_memory_stats()` - 获取统计信息

### 2. `backend/app/session/__init__.py`
导出新增的类和函数：
- `BootstrapLoader`
- `MemoryStore`
- `load_soul`

### 3. `backend/app/prompts.py`
重构为 8 层系统提示词组装：
- `build_system_prompt(session_key, mode, memory_context)` - 核心构建函数
- `get_system_prompt(session_key)` - 向后兼容接口
- `auto_recall_memory(session_key, user_message)` - 自动召回记忆

## 使用方式

### 1. 创建 Bootstrap 文件

在 session workspace 目录创建配置文件：

```bash
.sessions/{session_key}/workspace/
├── SOUL.md          # 人格定义
├── IDENTITY.md      # 身份定义
├── TOOLS.md         # 工具使用指南
├── MEMORY.md        # 长期记忆
└── memory/
    └── daily/
        └── 2026-03-08.jsonl  # 每日记忆
```

### 2. 使用 Bootstrap 加载

```python
from backend.app.session import get_store

store = get_store()
store.set_current_key("my_session")

# 加载所有 Bootstrap 文件
bootstrap_data = store.load_bootstrap(mode="full")
# 返回: {"SOUL.md": "...", "IDENTITY.md": "...", ...}

# 加载灵魂文件
soul = store.load_soul()
```

### 3. 使用记忆系统

```python
# 写入记忆
store.write_memory("用户喜欢使用 Python", category="preference")
store.write_memory("项目使用 FastAPI 框架", category="fact")

# 搜索记忆（简单 TF-IDF）
results = store.search_memory("Python", top_k=5)

# 混合搜索（推荐）
results = store.hybrid_search_memory("Python 偏好", top_k=5)
# 返回: [{"path": "2026-03-08.jsonl [preference]", "score": 0.85, "snippet": "..."}]

# 获取统计信息
stats = store.get_memory_stats()
# 返回: {"evergreen_chars": 1234, "daily_files": 5, "daily_entries": 42}
```

### 4. 使用记忆工具

```python
from backend.app.tools.memory_tools import memory_write, memory_search

# Agent 可以调用这些工具
result = memory_write.invoke({"content": "用户喜欢简洁的代码", "category": "preference"})
results = memory_search.invoke({"query": "代码风格", "top_k": 3})
```

### 5. 构建系统提示词

```python
from backend.app.prompts import build_system_prompt, auto_recall_memory

# 自动召回相关记忆
memory_context = auto_recall_memory("my_session", "帮我写 Python 代码")

# 构建完整系统提示词（8 层组装）
prompt = build_system_prompt(
    session_key="my_session",
    mode="full",
    memory_context=memory_context
)
```

## 系统提示词 8 层结构

参考 `s06_intelligence.py` 的设计：

1. **身份层** - IDENTITY.md 或默认身份
2. **灵魂层** - SOUL.md（人格定义）
3. **工具层** - TOOLS.md（工具使用指南）
4. **技能层** - 可用技能列表
5. **记忆层** - MEMORY.md + 自动召回的记忆
6. **Bootstrap 层** - 其他 Bootstrap 文件
7. **运行时层** - session key, 时间, workspace 路径
8. **核心指令层** - 原有的系统提示词

## 记忆搜索算法

### 简单搜索（TF-IDF）
- 分词（英文 + 中文）
- 计算文档频率（DF）
- 计算 TF-IDF 向量
- 余弦相似度排序

### 混合搜索（推荐）
1. **关键词搜索** - TF-IDF + 余弦相似度
2. **向量搜索** - 基于哈希的模拟向量嵌入
3. **结果合并** - 加权组合（向量 0.7 + 关键词 0.3）
4. **时间衰减** - 指数衰减（decay_rate=0.01）
5. **MMR 重排序** - 最大边际相关性（平衡相关性和多样性）

## 目录结构

```
backend/app/
├── session/
│   ├── __init__.py          # 统一入口（新增导出）
│   ├── constants.py         # 常量配置
│   ├── session.py           # SessionStore（新增方法）
│   ├── bootstrap.py         # ✨ Bootstrap 加载器
│   └── memory_store.py      # ✨ 记忆存储系统
├── tools/
│   └── memory_tools.py      # ✨ 记忆工具
└── prompts.py               # ✨ 重构为 8 层组装

.sessions/{session_key}/
├── workspace/
│   ├── SOUL.md              # 人格定义
│   ├── IDENTITY.md          # 身份定义
│   ├── TOOLS.md             # 工具使用指南
│   ├── USER.md              # 用户信息
│   ├── HEARTBEAT.md         # 心跳配置
│   ├── BOOTSTRAP.md         # 启动配置
│   ├── AGENTS.md            # Agent 配置
│   ├── MEMORY.md            # 长期记忆
│   └── memory/
│       └── daily/
│           ├── 2026-03-08.jsonl
│           └── 2026-03-09.jsonl
├── tasks/
├── team/
└── board/
```

## 与 s06_intelligence.py 的对应关系

| s06_intelligence.py | 后端项目 | 说明 |
|---------------------|---------|------|
| `BootstrapLoader` | `backend/app/session/bootstrap.py` | Bootstrap 文件加载 |
| `MemoryStore` | `backend/app/session/memory_store.py` | 记忆存储和搜索 |
| `build_system_prompt()` | `backend/app/prompts.py::build_system_prompt()` | 8 层提示词组装 |
| `tool_memory_write()` | `backend/app/tools/memory_tools.py::memory_write` | 写入记忆工具 |
| `tool_memory_search()` | `backend/app/tools/memory_tools.py::memory_search` | 搜索记忆工具 |
| `_auto_recall()` | `backend/app/prompts.py::auto_recall_memory()` | 自动召回记忆 |
| `WORKSPACE_DIR` | `.sessions/{session_key}/workspace/` | 工作空间目录 |

## 下一步

1. 在 `AgentContext` 中集成自动记忆召回
2. 在每轮对话前自动调用 `auto_recall_memory()`
3. 创建示例 Bootstrap 文件（SOUL.md, IDENTITY.md 等）
4. 添加记忆管理的 REPL 命令（/memory, /search）
5. 测试混合搜索的效果
