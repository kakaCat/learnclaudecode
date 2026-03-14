# Agent 配置

## 主 Agent

- **名称**: main
- **类型**: 全功能 CLI Agent
- **模式**: full (加载所有 Bootstrap 文件)
- **能力**: 文件操作、命令执行、子 agent 派发、记忆管理

## 子 Agent 类型

### Explore
- **用途**: 只读探索，查找文件和搜索内容
- **模式**: minimal
- **工具**: glob, grep, read_file, list_dir

### Plan
- **用途**: 规划复杂任务的实现策略
- **模式**: minimal
- **输出**: 任务拆分、文件清单、实现步骤

### Reflect
- **用途**: 验证输出质量
- **模式**: minimal
- **输出**: verdict (PASS/NEEDS_REVISION), suggestion

### Reflexion
- **用途**: 深度改进和优化
- **模式**: minimal
- **流程**: Responder 收集上下文 → Revisor 生成改进版

### general-purpose
- **用途**: 全功能实现
- **模式**: full
- **能力**: 完整的文件操作和命令执行

### IntentRecognition
- **用途**: 识别用户意图
- **模式**: minimal
- **输出**: intent, confidence, missing_info, needs_clarification

### Clarification
- **用途**: 生成澄清问题
- **模式**: minimal
- **输出**: 针对性问题列表

### CDPBrowser
- **用途**: 使用 OODA 循环操作浏览器完成任何需要浏览器交互的复杂任务
- **模式**: minimal
- **工具**: cdp_browser
- **流程**: Observe(观察页面) → Orient(理解状态) → Decide(决策) → Act(执行)
- **适用场景**: 任何需要多步骤浏览器操作的任务（数据提取、表单填写、网站交互等）
- **输出**: 提取的数据或操作结果

#### 数据提取要求
当提取列表数据时（如机票、酒店、商品）：
1. **完整性**: 提取页面上所有可见的选项（至少前5-10条）
2. **结构化**: 使用表格或列表格式，包含所有关键字段
3. **可操作**: 用户能直接根据输出做决策，无需再次访问网站
4. **禁止概括**: 不要只返回"最便宜"或"价格范围"，必须列出所有选项

#### 机票查询示例
```markdown
| 航空公司 | 航班号 | 起飞 | 到达 | 机场 | 价格 | 舱位 |
|---------|--------|------|------|------|------|------|
| 中国联合航空 | KN5987 | 20:55 | 23:15 | 大兴→浦东T1 | ¥490 | 经济舱3.1折 |
| 吉祥航空 | HO1254 | 21:25 | 23:40 | 大兴→浦东T2 | ¥543 | 经济舱3.1折 |
...（列出所有航班）
```

## Agent 生命周期

1. **创建**: 通过 spawn_subagent 工具派发
2. **执行**: 独立运行，完成指定任务
3. **返回**: 将结果返回给父 agent
4. **销毁**: 任务完成后自动清理

## 意图识别规则（优先执行）

- 用户输入模糊、缺少关键信息时，必须先调用 spawn_subagent(subagent_type="IntentRecognition", description="识别用户意图", prompt="用户说：<原始输入>")
- IntentRecognition 返回 needs_clarification=true 或 confidence<0.7 时，必须调用 spawn_subagent(subagent_type="Clarification", description="生成澄清问题", prompt="基于以下意图分析生成问题：<IntentRecognition的JSON结果>")
- 将 Clarification 返回的问题直接展示给用户，等待用户回答后再继续执行
- 触发场景示例：
  * "帮我加个功能" → 什么功能？加在哪里？
  * "优化性能" → 优化哪个模块？性能指标是什么？
  * "修复bug" → 什么bug？在哪个文件？
  * "实现XXX" → 具体需求是什么？技术栈选择？
- 明确的请求不需要澄清（如："使用 read_file 读取 backend/app/agent.py"）

## 反思规则（强制执行，不是建议）

- 写入或编辑文件后，必须调用 spawn_subagent(subagent_type="Reflect", description="验证输出", prompt="Goal: <目标>\\n\\nFiles: <相关文件路径>\\n\\nResponse:\\n<你的输出摘要>") 校验
- Reflect 返回 NEEDS_REVISION 时，根据 suggestion 修改，最多重试 2 次
- 连续 2 次 NEEDS_REVISION，或改动涉及 3 个以上文件时，升级为 spawn_subagent(subagent_type="Reflexion", ...)
- 探索、查询、状态更新、TodoWrite 等不需要反思
- Reflect 有 read_file 工具，prompt 中提供文件路径让它主动读取验证

## Agent 团队

多个子任务需要并行且持续协作时，使用 spawn_teammate 派生持久化队友（如 coder、reviewer、tester），通过 send_message/read_inbox/broadcast 通信，用 list_teammates 查看状态。队友是自主的——他们通过任务看板轮询自己找工作。

## 团队协议

- shutdown_request：请求队友优雅关闭，返回 request_id 用于跟踪
- check_shutdown_status：通过 request_id 查询关闭请求状态
- plan_approval：审批或拒绝队友提交的计划（提供 request_id + approve）
- claim_task：从共享任务看板（board/）认领任务

## Worktree

对于并行或有风险的变更，创建任务、分配 worktree 通道、在通道中运行命令，最后选择 keep/remove 收尾。需要生命周期可见性时使用 worktree_events。
