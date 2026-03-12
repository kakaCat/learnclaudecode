# 后端项目整理方案

## 📊 当前问题

### 1. 目录冗余
- `subagents_v2/` - 几乎为空，可删除
- `context/` - 只剩2个文件，应移到其他位置

### 2. 命名不一致
- 单复数混用：`skill`(单) vs `tools`(复)
- 下划线使用：`search_agent` vs `searchagent`

### 3. 组织不清晰
- `compact/` - 应该在 `memory/` 下
- `reasoning/` - 用途不明确
- `mcp/` - 应该在 `tools/` 下

### 4. 新旧混杂
- 新架构：`core/`
- 旧架构：散落各处

## 🎯 整理目标

### 标准目录结构
```
backend/app/
├── core/              # 核心架构（新）
├── services/          # 服务层
├── tools/             # 工具实现
├── subagents/         # 子Agent
├── guards/            # 守卫
├── memory/            # 记忆管理
├── session/           # 会话管理
├── task/              # 任务管理
├── team/              # 团队协作
├── worktree/          # Worktree管理
├── utils/             # 工具函数
└── exceptions/        # 异常定义
```

## 📝 整理步骤

### 第1步：删除废弃目录
- [ ] 删除 `subagents_v2/`（空目录）
- [ ] 删除 `reasoning/`（如果未使用）

### 第2步：移动文件到合适位置
- [ ] `context/overflow_guard.py` → `core/overflow_guard.py`
- [ ] `context/tracer.py` → `core/tracer.py`
- [ ] 删除空的 `context/` 目录
- [ ] `compact/` → `memory/compact/`
- [ ] `mcp/` → `tools/mcp/`（如果是工具相关）

### 第3步：统一命名
- [ ] `skill/` → `skills/`（统一复数）
- [ ] `todo/` → `todos/`（统一复数）
- [ ] `search_agent/` → `search/agents/`（层次化）

### 第4步：清理 __pycache__
- [ ] 删除所有 `__pycache__` 目录

## ⚠️ 注意事项

1. 移动文件后需要更新所有导入语句
2. 保留 `agent.py` 和 team 相关代码（待迁移）
3. 测试确保功能正常

## 📋 执行清单

- [ ] 备份当前代码
- [ ] 执行整理步骤
- [ ] 更新导入语句
- [ ] 运行测试验证
- [ ] 更新文档
