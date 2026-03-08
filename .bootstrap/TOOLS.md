# 工具使用指南

## 工具选择原则

1. **优先使用专用工具**: 使用 glob/grep/read_file 而非 bash 命令
2. **工具组合**: 复杂任务通过多个工具组合完成
3. **避免阻塞**: 长时间运行的命令使用 background_run
4. **并行执行**: 独立任务可以并行派发给子 agent

## 文件操作

- **探索**: glob (查找文件) → grep (搜索内容) → read_file (读取)
- **修改**: read_file (先读取) → edit_file (精确替换) 或 write_file (重写)
- **验证**: 修改后调用 Reflect 子 agent 验证

## 命令执行

- **短命令**: 直接使用 bash 工具
- **长命令**: 使用 background_run，返回 task_id
- **查询状态**: check_background 查询后台任务

## 子 Agent 派发

- **Explore**: 只读探索，查找文件和搜索内容
- **Plan**: 规划复杂任务的实现策略
- **Reflect**: 验证输出质量
- **Reflexion**: 深度改进和优化
- **general-purpose**: 全功能实现

## 记忆管理

- **写入**: memory_write(content, category) - 保存重要事实
- **搜索**: memory_search(query, top_k) - 召回相关记忆
- **分类**: preference (偏好), fact (事实), context (上下文)

## 工作空间

- **临时文件**: workspace_write/workspace_read - 存储中间结果
- **持久任务**: task_create/task_update - 跨会话任务管理
- **团队协作**: spawn_teammate/send_message - 多 agent 协作
