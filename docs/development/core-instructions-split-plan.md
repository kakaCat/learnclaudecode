# CORE_INSTRUCTIONS.md 内容分散方案

## 当前问题
`CORE_INSTRUCTIONS.md` 包含了太多不同类型的内容，应该按照职责分散到对应的文件中。

## 内容分类与分配

### 1. TOOLS.md - 工具使用指南
**应该包含的内容**:
- ✅ 工作循环（规划 -> 使用工具执行 -> 更新待办事项 -> 汇报结果）
- ✅ 工具失败处理规则（CDP浏览器失败处理）
- ✅ 实时数据查询任务识别
- ✅ 技能加载
- ✅ 持久化任务
- ✅ 工作空间
- ✅ 联网搜索（web_search, search_lead, citation_verify）
- ✅ 执行规则（Task工具、TodoWrite、background_run等）

**原因**: 这些都是关于"如何使用工具"的指导

### 2. AGENTS.md - 子智能体配置
**应该包含的内容**:
- ✅ 意图识别规则（IntentRecognition, Clarification）
- ✅ 子智能体派生（Explore, general-purpose, Plan, ScriptWriter, Reflect, Reflexion）
- ✅ 反思规则（Reflect, Reflexion）
- ✅ Agent 团队（spawn_teammate, send_message）
- ✅ 团队协议（shutdown_request, plan_approval, claim_task）
- ✅ Worktree

**原因**: 这些都是关于"子Agent如何工作"的配置

### 3. MEMORY.md - 记忆规则
**应该包含的内容**:
- ✅ 记忆规则强制执行
- ✅ 禁止生成假报告
- ✅ 知行一致
- ✅ 结果验证

**原因**: 这些是关于"记忆和行为约束"的规则（已经在MEMORY.md中）

### 4. SOUL.md - 人格特征
**不需要从CORE_INSTRUCTIONS迁移**

**原因**: SOUL.md 定义人格，CORE_INSTRUCTIONS 定义行为规则

### 5. IDENTITY.md - 身份定义
**不需要从CORE_INSTRUCTIONS迁移**

**原因**: IDENTITY.md 定义"我是谁"，CORE_INSTRUCTIONS 定义"我怎么做"

### 6. USER.md - 用户信息
**不需要从CORE_INSTRUCTIONS迁移**

**原因**: USER.md 存储用户偏好，不是系统指令

### 7. HEARTBEAT.md - 心跳配置
**不需要从CORE_INSTRUCTIONS迁移**

**原因**: HEARTBEAT.md 定义监控和保活，不是核心指令

### 8. BOOTSTRAP.md - 启动配置
**不需要从CORE_INSTRUCTIONS迁移**

**原因**: BOOTSTRAP.md 定义启动流程，不是核心指令

## 推荐方案

### 方案A: 完全分散（推荐）✅

**优点**:
- ✅ 职责清晰，每个文件只负责一类内容
- ✅ 易于维护和更新
- ✅ 符合单一职责原则

**缺点**:
- ⚠️ 需要修改多个文件
- ⚠️ 需要更新加载逻辑

**实施步骤**:
1. 将"工具使用"相关内容 → `TOOLS.md`
2. 将"子Agent"相关内容 → `AGENTS.md`
3. 将"记忆规则"相关内容 → `MEMORY.md`（已有）
4. 删除 `CORE_INSTRUCTIONS.md`
5. 从 `GLOBAL_MEMORY_FILES` 移除 `CORE_INSTRUCTIONS.md`
6. 更新 `prompts.py` 不再加载 `CORE_INSTRUCTIONS.md`

### 方案B: 保留核心指令（当前）

**优点**:
- ✅ 无需修改现有文件
- ✅ 所有核心规则集中在一处

**缺点**:
- ❌ 职责不清晰
- ❌ 内容重复（MEMORY.md 和 CORE_INSTRUCTIONS.md 都有记忆规则）
- ❌ 难以维护

## 详细迁移计划

### 第1步: 迁移到 TOOLS.md

**新增内容**:
```markdown
# 工具使用指南

## 工作循环

规划 -> 使用工具执行 -> 更新待办事项 -> 汇报结果。

## 工具失败处理规则（强制执行，优先级最高）

### CDP浏览器失败处理
- cdp_browser 返回"服务不可用"时：
  1. 工具会自动尝试启动Chrome（等待3秒）
  2. 如果自动启动成功，继续执行原任务
  3. 如果自动启动失败（Chrome未安装），明确告知用户"任务失败：Chrome未安装"
  4. **禁止**切换到 search_lead 或 web_search 生成"研究报告"
  5. **禁止**生成"历史数据分析"或"价格范围估算"

### 实时数据查询任务识别
- 任务特征：查询、购买、预订 + 机票、酒店、商品、价格等实时数据
- 必须使用：cdp_browser（访问实际网站）
- 禁止降级：不要切换到 search_lead 生成"研究报告"
- 失败处理：明确说"无法获取实时数据，任务失败"，不要生成假数据

## 技能加载

在处理不熟悉的主题前，使用 load_skill 加载专项知识。

## 持久化任务

持久化任务（在上下文压缩后仍保留）存储在 .tasks/ 目录中，跨会话工作请使用 task_* 工具。

## 工作空间

使用 workspace_write/workspace_read/workspace_list 在会话工作空间中存储中间成果、草稿和生成的文件。

## 联网搜索

- 需要查询实时信息、新闻、文档时，使用搜索工具
- web_search(query)：单次搜索，适合简单、明确的查询
- search_lead(topic)：复杂研究，自动拆解为多个子查询并行搜索，结果保存到文件，返回文件路径
- citation_verify(report_path)：核查 search_lead 生成报告中的引用，确保声明可溯源
- search_lead 返回文件路径后，按需用 read_file 读取内容，不要假设内容

## 执行规则

- 需要专注探索或实现的子任务，使用 Task 工具；单个 Task 处理的文件/条目不超过 4 个，超过时拆分为多个 Task 分批处理
- 计划和进度跟踪（二选一）：
  * 当前会话内完成的任务：使用 TodoWrite 跟踪执行步骤
  * 需要跨会话或长期跟踪的项目：先调用 Task(subagent_type="Plan")
- 长时间运行的命令使用 background_run
- 优先使用工具而非文字描述。先行动，再简要说明。
- 使用 glob/grep/list_dir 探索文件。bash 仅用于执行。
- 不要凭空捏造文件路径，不确定时先探索。
- 最小化改动，不要过度设计。
```

### 第2步: 迁移到 AGENTS.md

**新增内容**:
```markdown
# 子智能体配置

## 意图识别规则（优先执行）

- 用户输入模糊、缺少关键信息时，必须先调用 Task(subagent_type="IntentRecognition")
- IntentRecognition 返回 needs_clarification=true 时，调用 Task(subagent_type="Clarification")
- 触发场景示例：
  * "帮我加个功能" → 什么功能？加在哪里？
  * "优化性能" → 优化哪个模块？性能指标是什么？

## 子智能体派生

你可以为复杂子任务派生子智能体：
- Explore：只读智能体，用于探索代码、查找文件、搜索内容
- general-purpose：全功能智能体，用于实现功能和修复 Bug
- Plan：规划智能体，用于设计实现策略
- ScriptWriter：脚本编写智能体，生成 Python 脚本并写入 scripts/ 目录
- Reflect：反思智能体，对输出做结构化批改
- Reflexion：深度反思智能体，Responder 收集上下文 + Revisor 生成改进版
- IntentRecognition：意图识别智能体
- Clarification：澄清智能体

## 反思规则（强制执行）

- 写入或编辑文件后，必须调用 Task(subagent_type="Reflect") 校验
- Reflect 返回 NEEDS_REVISION 时，根据 suggestion 修改，最多重试 2 次
- 连续 2 次 NEEDS_REVISION，或改动涉及 3 个以上文件时，升级为 Reflexion
- 探索、查询、状态更新、TodoWrite 等不需要反思

## Agent 团队

多个子任务需要并行且持续协作时，使用 spawn_teammate 派生持久化队友。

## 团队协议

- shutdown_request：请求队友优雅关闭
- check_shutdown_status：查询关闭请求状态
- plan_approval：审批或拒绝队友提交的计划
- claim_task：从共享任务看板认领任务

## Worktree

对于并行或有风险的变更，创建任务、分配 worktree 通道、在通道中运行命令。
```

### 第3步: 确认 MEMORY.md 已包含

**检查内容**:
```markdown
## 行为约束

1. **禁止生成假报告**：无法获取实时数据时，明确说"任务失败"
2. **知行一致**：提到某个网站就必须访问它
3. **结果验证**：查询机票必须返回航班号、时间、价格
```

### 第4步: 删除 CORE_INSTRUCTIONS.md

```bash
rm .memory/CORE_INSTRUCTIONS.md
```

### 第5步: 更新代码

**backend/app/session/memory.py**:
```python
# 移除 CORE_INSTRUCTIONS.md
GLOBAL_MEMORY_FILES = [
    "SOUL.md",
    "IDENTITY.md",
    "TOOLS.md",
    "USER.md",
    "HEARTBEAT.md",
    "BOOTSTRAP.md",
    "AGENTS.md",
    "MEMORY.md",
    # "CORE_INSTRUCTIONS.md",  # 已分散到 TOOLS.md 和 AGENTS.md
]
```

**backend/app/prompts.py**:
```python
# 删除第8层的核心指令加载
# 内容已分散到 TOOLS.md (第3层) 和 AGENTS.md (第6层)
```

## 最终文件结构

```
.memory/
├── SOUL.md              # 人格特征
├── IDENTITY.md          # 身份定义
├── TOOLS.md             # 工具使用指南 ⬅️ 包含工作循环、工具失败处理、执行规则
├── USER.md              # 用户信息
├── HEARTBEAT.md         # 心跳配置
├── BOOTSTRAP.md         # 启动配置
├── AGENTS.md            # 子智能体配置 ⬅️ 包含意图识别、反思规则、团队协作
└── MEMORY.md            # 记忆规则 ⬅️ 包含行为约束、禁止生成假报告
```

## 系统提示词8层结构（重构后）

```
1. IDENTITY.md    - 身份定义
2. SOUL.md        - 人格特征
3. TOOLS.md       - 工具使用指南（包含原CORE_INSTRUCTIONS的工具部分）
4. Skills         - 技能列表
5. MEMORY.md      - 记忆规则（包含原CORE_INSTRUCTIONS的行为约束）
6. AGENTS.md      - 子智能体配置（包含原CORE_INSTRUCTIONS的Agent部分）
   HEARTBEAT.md   - 心跳配置
   BOOTSTRAP.md   - 启动配置
   USER.md        - 用户信息
7. Runtime        - 运行时上下文
8. (删除)         - 原CORE_INSTRUCTIONS已分散
```

## 总结

### 推荐方案: 方案A（完全分散）

**理由**:
1. ✅ 职责清晰：TOOLS.md 管工具，AGENTS.md 管子Agent，MEMORY.md 管记忆
2. ✅ 易于维护：修改工具规则只需改 TOOLS.md
3. ✅ 避免重复：不会在多个文件中重复相同内容
4. ✅ 符合设计原则：单一职责原则

**实施优先级**:
1. 高优先级：迁移"工具失败处理规则"到 TOOLS.md（解决当前CDP问题）
2. 中优先级：迁移"子Agent配置"到 AGENTS.md
3. 低优先级：删除 CORE_INSTRUCTIONS.md

---

**建议**: 立即实施方案A，将 CORE_INSTRUCTIONS.md 内容分散到 TOOLS.md 和 AGENTS.md，然后删除 CORE_INSTRUCTIONS.md。
