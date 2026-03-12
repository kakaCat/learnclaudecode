# Agent 层级架构重构总结

## 重构目标

将单一的 Agent loop 拆分为三层架构：
1. **MainAgent**：主 Agent，可以调用所有工具
2. **TeamAgent**：团队 Agent，运行在独立线程，有通信能力
3. **Subagent**：子 Agent，执行专门任务，支持 ReAct 和 OODA 两种模式

## 架构图

```
User Input
    ↓
MainAgent Loop (主循环)
    ├─ 普通工具 (bash, read_file, write_file, etc.) ✅
    ├─ Task 工具 (spawn Subagent) ✅
    └─ spawn_teammate 工具 (spawn TeamAgent) ✅
         ↓
    ┌────────────────────┬─────────────────────┐
    ↓                    ↓                     ↓
TeamAgent Loop      Subagent (ReAct)    Subagent (OODA)
    ├─ 普通工具 ✅       ├─ 普通工具 ✅        ├─ 普通工具 ✅
    ├─ Task 工具 ✅      └─ 根据配置过滤       └─ 根据配置过滤
    ├─ spawn_teammate ❌
    └─ 通信工具 ✅
       (send_message, read_inbox, claim_task, report_progress)
```

## 已完成的工作

### 1. 创建 TeamAgentContext

**文件**: [backend/app/context/team_context.py](backend/app/context/team_context.py)

**功能**:
- 继承 `BaseContext`
- 添加 `name` 和 `role` 属性
- 获取 team scope 的工具（排除 spawn_teammate）
- 动态创建通信工具（绑定到当前 teammate）
- 创建 Agent 实例

### 2. 扩展 ToolsManager 支持 team scope

**文件**: [backend/app/tools/manager.py](backend/app/tools/manager.py)

**修改**:
- 新增 `get_team_tools()` 方法
- 扩展 `get_tools(scope)` 支持 `"team"` scope
- 权限矩阵：
  - `tags=["main"]` → 只有 MainAgent 可用
  - `tags=["team"]` → 只有 TeamAgent 可用
  - `tags=["both"]` → 所有 Agent 可用

### 3. 创建 MainAgentService

**文件**: [backend/app/services/main_agent_service.py](backend/app/services/main_agent_service.py)

**功能**:
- 继承 `AgentService`
- 使用 `MainAgentContext`
- 拥有完整的工具集（包括 Task 和 spawn_teammate）

### 4. 创建 TeamAgentService

**文件**: [backend/app/services/team_agent_service.py](backend/app/services/team_agent_service.py)

**功能**:
- 继承 `AgentService`
- 使用 `TeamAgentContext`
- 实现 `run_loop()` 方法（独立线程主循环）
- 支持：
  - 检查收件箱
  - 认领任务
  - 执行任务
  - 报告进度
  - 空闲超时自动关闭

### 5. 更新 TeammateManager

**文件**: [backend/app/team/teammate_manager.py](backend/app/team/teammate_manager.py)

**修改**:
- 简化 `_loop()` 方法
- 使用 `TeamAgentService` 替代原有的复杂逻辑
- 所有工具和通信逻辑由 `TeamAgentContext` 管理

### 6. 更新 spawn_teammate 工具权限

**文件**: [backend/app/tools/implementations/system/team_tool.py](backend/app/tools/implementations/system/team_tool.py)

**修改**:
- 将 `tags=["both"]` 改为 `tags=["main"]`
- 确保只有 MainAgent 可以 spawn TeamAgent

### 7. 更新 main.py

**文件**: [backend/main.py](backend/main.py)

**修改**:
- 导入 `MainAgentService` 替代 `AgentService`
- 使用 `MainAgentService` 创建 agent 实例

### 8. 添加 get_teammate_system_prompt

**文件**: [backend/app/prompts.py](backend/app/prompts.py)

**功能**:
- 为 TeamAgent 生成专门的 system prompt
- 包含身份信息、通信指南、工作流程

## 架构优势

### 1. 职责分离
- **MainAgent**: 用户交互、任务分发
- **TeamAgent**: 独立执行、团队协作
- **Subagent**: 专门任务、隔离上下文

### 2. 权限隔离
- 通过 `tags` 机制控制工具访问权限
- 防止无限递归（TeamAgent 不能 spawn TeamAgent）
- 清晰的工具边界

### 3. 可扩展性
- 新增 Agent 类型只需：
  1. 创建 Context 类
  2. 创建 Service 类
  3. 注册工具权限
- 统一的 `AgentService` 基类

### 4. 通信机制
- TeamAgent 通过消息总线通信
- 支持任务队列和认领机制
- 支持进度报告和状态同步

## Subagent 双模式

### ReAct Loop (默认)
- 适用于大多数任务
- Reason → Act → Observe → repeat
- 例如：Explore, Plan, Coding, general-purpose

### OODA Loop (迭代探索)
- 适用于不确定性高的任务
- Observe → Orient → Decide → Act → repeat
- 例如：需要多轮探索的复杂分析

## 下一步工作

1. **测试完整流程**:
   - 测试 MainAgent 调用普通工具
   - 测试 MainAgent spawn Subagent
   - 测试 MainAgent spawn TeamAgent
   - 测试 TeamAgent 调用 Subagent

2. **完善通信机制**:
   - 优化消息总线
   - 添加任务优先级
   - 添加超时处理

3. **监控和日志**:
   - 添加 Agent 层级追踪
   - 优化日志输出
   - 添加性能监控

4. **文档完善**:
   - 添加使用示例
   - 添加架构图
   - 添加最佳实践

## 文件清单

### 新增文件
- `backend/app/context/team_context.py` - TeamAgent 上下文
- `backend/app/services/main_agent_service.py` - MainAgent 服务
- `backend/app/services/team_agent_service.py` - TeamAgent 服务
- `docs/architecture/agent-hierarchy.md` - 架构设计文档

### 修改文件
- `backend/app/tools/manager.py` - 添加 team scope 支持
- `backend/app/team/teammate_manager.py` - 简化为使用 TeamAgentService
- `backend/app/tools/implementations/system/team_tool.py` - 更新 spawn_teammate tags
- `backend/main.py` - 使用 MainAgentService
- `backend/app/prompts.py` - 添加 get_teammate_system_prompt

## 语法验证

所有新增和修改的文件已通过 `python -m py_compile` 验证，无语法错误。
