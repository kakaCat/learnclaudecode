# Bootstrap 配置目录使用说明

## 目录结构

```
.bootstrap/
├── IDENTITY.md      # 身份定义
├── SOUL.md          # 人格特征
├── TOOLS.md         # 工具使用指南
├── USER.md          # 用户信息
├── HEARTBEAT.md     # 心跳配置
├── BOOTSTRAP.md     # 启动配置
├── AGENTS.md        # Agent 配置
└── MEMORY.md        # 长期记忆
```

## 与 session workspace 的区别

### 全局 .bootstrap/ 目录
- **位置**: 项目根目录 `.bootstrap/`
- **作用域**: 所有 session 共享
- **内容**: Agent 的核心配置（身份、人格、工具指南等）
- **修改频率**: 较低，定义 Agent 的基本特性
- **示例**: SOUL.md, IDENTITY.md, TOOLS.md

### Session workspace 目录
- **位置**: `.sessions/{session_key}/workspace/`
- **作用域**: 单个 session 独立
- **内容**: 会话级的记忆和临时文件
- **修改频率**: 较高，每次对话可能更新
- **示例**: `memory/daily/{date}.jsonl`（每日记忆）

## 加载机制

### Bootstrap 加载
```python
from backend.app.session import get_store

store = get_store()
store.set_current_key("my_session")

# 从全局 .bootstrap/ 加载配置
bootstrap_data = store.load_bootstrap(mode="full")
# 返回: {"SOUL.md": "...", "IDENTITY.md": "...", ...}
```

### 记忆管理
```python
# 写入记忆到 session workspace
store.write_memory("用户喜欢 Python", category="preference")
# 保存到: .sessions/my_session/workspace/memory/daily/2026-03-08.jsonl

# 搜索记忆
results = store.hybrid_search_memory("Python")
```

## 系统提示词组装

8 层结构中的数据来源：

1. **身份层** - `.bootstrap/IDENTITY.md`
2. **灵魂层** - `.bootstrap/SOUL.md`
3. **工具层** - `.bootstrap/TOOLS.md`
4. **技能层** - 动态加载的技能
5. **记忆层** - `.bootstrap/MEMORY.md` + `.sessions/{key}/workspace/memory/`
6. **Bootstrap 层** - `.bootstrap/HEARTBEAT.md`, `BOOTSTRAP.md`, `AGENTS.md`, `USER.md`
7. **运行时层** - 动态生成（session key, 时间等）
8. **核心指令层** - 硬编码的核心指令

## 修改 Bootstrap 文件

修改全局配置文件后，需要重启 agent 或重新设置 session key 才能生效：

```python
# 修改 .bootstrap/SOUL.md 后
store.set_current_key("my_session")  # 重新加载 Bootstrap 文件
```

## 最佳实践

1. **全局配置放 .bootstrap/**: Agent 的核心特性、工具指南、用户偏好
2. **会话数据放 workspace/**: 对话记忆、临时文件、中间结果
3. **版本控制**: `.bootstrap/` 可以提交到 git，`.sessions/` 应该忽略
4. **文档维护**: 定期更新 MEMORY.md 中的长期记忆
