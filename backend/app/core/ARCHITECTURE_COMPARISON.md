# 架构重构对比

## 📊 重构前 vs 重构后

### 1. 依赖关系对比

**重构前（存在循环依赖）：**
```
MainAgentContext
    ↓
ToolManager.build_task_tool(main_context)  # 传入 context
    ↓
Task Tool (持有 main_context 引用)
    ↓
创建 SubagentContext
    ↓
需要访问 MainAgentContext 的 session_key  # 循环依赖 ❌
```

**重构后（单向依赖）：**
```
ToolRegistry (独立初始化)
    ↑
    ├── MainContext.get_tools()
    ├── SubContext.get_tools()
    └── TeamContext.get_tools()

Task Tool (通过回调解耦)
    ↓
spawn_callback (在应用启动时注入)
    ↓
使用 ContextFactory 创建 SubContext  # 无循环依赖 ✅
```

### 2. 类职责对比

**重构前：**
```
AgentService (533 行)
├── 执行 LLM 循环
├── 历史压缩和召回
├── 守卫检查和注入
├── 通知管理
├── 监控追踪
└── 错误处理
```
