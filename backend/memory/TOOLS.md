# 工具使用指南

## 工具选择原则

1. **优先使用专用工具**: 使用 glob/grep/read_file 而非 bash 命令
2. **工具组合**: 复杂任务通过多个工具组合完成
3. **避免阻塞**: 长时间运行的命令使用 background_run
4. **并行执行**: 独立任务可以并行派发给子 agent

## 文件操作

- **探索**: glob (查找文件) → grep (搜索内容) → read_file (读取)
- **修改项目代码**: read_file → edit_file 或 write_file (写到项目目录)
- **生成新文件**: workspace_write (写到 session workspace)
- **验证**: 修改后调用 Reflect 子 agent 验证

**文件输出规则**：
- 修改现有项目文件 → 使用 write_file 或 edit_file
- 生成新内容（网页、报告、示例代码等）→ 使用 workspace_write

## 命令执行

- **短命令**: 直接使用 bash 工具
- **长命令**: 使用 background_run，返回 task_id
- **查询状态**: check_background 查询后台任务

## 子 Agent 派发

- **Plan**: 分析复杂任务（>3步骤）并创建持久化任务列表，存储在 .tasks/ 目录
- **Explore**: 探索代码库，查找文件和内容
- **Reflect**: 验证输出质量
- **Reflexion**: 深度改进和优化
- **general-purpose**: 全功能实现
- **CDPBrowser**: 网页数据提取（机票、酒店、商品等）

## 记忆管理

- **写入**: memory_write(content, category) - 保存重要事实
- **搜索**: memory_search(query, top_k) - 召回相关记忆
- **分类**: preference (偏好), fact (事实), context (上下文)

## 工作空间

- **临时文件**: workspace_write/workspace_read - 存储中间结果
- **持久任务**: task_create/task_update - 跨会话任务管理
- **团队协作**: spawn_teammate/send_message - 多 agent 协作

## 工作循环

规划 -> 使用工具执行 -> 更新待办事项 -> 汇报结果。

## 网页数据提取

需要从网页获取实时数据时（机票、酒店、商品价格等）：
- 使用 `Task(subagent_type="CDPBrowser", prompt="查询...")`
- CDPBrowser subagent 会自动处理页面交互、调试、数据提取
- 不要自己尝试网页操作，交给专业的subagent处理

## 技能加载

在处理不熟悉的主题前，使用 load_skill 加载专项知识。

## 持久化任务

持久化任务（在上下文压缩后仍保留）存储在 .tasks/ 目录中，跨会话工作请使用 task_* 工具。

## 联网搜索

- 需要查询实时信息、新闻、文档时，使用搜索工具
- web_search(query)：单次搜索，适合简单、明确的查询
- search_lead(topic)：复杂研究，自动拆解为多个子查询并行搜索，结果保存到文件，返回文件路径；适合需要多角度调研的主题
- citation_verify(report_path)：核查 search_lead 生成报告中的引用，确保声明可溯源；在需要高可信度时使用
- search_lead 返回文件路径后，按需用 read_file 读取内容，不要假设内容

## 执行规则

- 需要专注探索或实现的子任务，使用 Task 工具；单个 Task 处理的文件/条目不超过 4 个，超过时拆分为多个 Task 分批处理
- **计划和进度跟踪（强制规则）**：
  * **简单任务**（≤3步骤，预计≤3轮对话）：使用 TodoWrite 跟踪
  * **复杂任务**（>3步骤，或预计>3轮对话）：**必须使用 task 系统**
    1. 第一步：调用 Task(subagent_type="Plan") 分析任务并创建持久化任务
    2. 执行中：定期调用 task_list 检查状态（每3-5轮对话检查一次）
    3. 完成步骤：调用 task_update 更新状态
  * **判断标准**：如果不确定，默认使用 task 系统（更安全）
  * **中途切换**：如果使用 TodoWrite 的任务超过3步骤或5轮对话，立即切换到 task 系统
- 长时间运行的命令（构建、安装、测试）使用 background_run，立即返回 task_id 不阻塞；用 check_background 查询状态；下一轮对话会自动收到完成通知
- 多任务并行工作流：task_create 记录计划 → background_run 并行启动多个命令 → 收到 <background-results> 通知后 task_update 标记完成
- **先做后说原则**：优先使用工具而非文字描述。**禁止只说"让我做X"而不实际调用工具**。
- 使用 glob/grep/list_dir 探索文件。bash 仅用于执行（运行测试、git、npm）。
- 不要凭空捏造文件路径，不确定时先探索。
- 最小化改动，不要过度设计。
- **任务完成确认**：完成所有工具调用后，必须用文字回复用户，包括：
  1. 总结已完成的工作
  2. **明确告知交付物路径**（如文件路径、URL等）
  3. 直接引用工具返回的原始数据，不要编造任何 ID 或数值
- **状态检查机制**：每完成一个关键步骤后：
  1. 使用 workspace_write 保存当前状态到 _task_state.json
  2. 记录：已完成步骤、下一步行动、需要使用的工具
  3. 长对话中（>5轮）定期 task_list 或 workspace_read 检查状态
